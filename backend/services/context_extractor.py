"""
Extracts structured generation parameters from free-form natural language context.
Uses LLM when available, falls back to regex heuristics for demo mode.
"""
import re
import json
from typing import Any, Dict


def _normalise_compliance_rules(compliance_rules: Dict[str, Any], llm_provider=None) -> None:
    """
    For any compliance rule with action="Custom" and a custom_rule string,
    normalise it to a structured masking_op in-place.

    This runs once at schema-inference time so generation is fully deterministic.
    Uses LLM when available; always falls back to keyword matching.
    """
    if not compliance_rules:
        return
    try:
        from services.masking import normalize_masking_rule
    except ImportError:
        return

    for col_name, rule in compliance_rules.items():
        if not isinstance(rule, dict):
            continue
        custom_rule = rule.get("custom_rule") or ""
        action = rule.get("action", "")
        # Normalise whenever there's a custom_rule text, regardless of action label
        if custom_rule and not rule.get("masking_op"):
            op = normalize_masking_rule(custom_rule, llm_provider)
            if op:
                rule["masking_op"] = op


from prompts.extraction import SYSTEM as EXTRACTION_SYSTEM, TEMPLATE as EXTRACTION_PROMPT


def _regex_fallback(context: str) -> Dict[str, Any]:
    """Best-effort extraction without LLM."""
    text = context.lower()

    # Volume
    volume = None
    m = re.search(r"(\d+)\s*(?:users?|records?|rows?|entries?|people|customers?|orders?|items?)", text)
    if not m:
        m = re.search(r"generate\s+(\d+)", text)
    if not m:
        m = re.search(r"(\d+)\s+(?:of|sample)", text)
    if m:
        volume = int(m.group(1))

    # Entity type
    entity_match = re.search(r"(?:for|of|generate)\s+(\w+)\s+data", text) or \
                   re.search(r"(\d+)\s+(\w+)", text)
    entity_type = "records"
    if entity_match:
        candidate = entity_match.group(2) if entity_match.lastindex == 2 else entity_match.group(1)
        if candidate not in ("of", "for", "generate", "with", "and", "the"):
            entity_type = candidate.rstrip("s")

    # Columns from explicit list patterns like "with fields: a, b, c" or "columns: a, b"
    cols_raw = []
    col_match = re.search(
        r"(?:with\s+)?(?:fields?|columns?|attributes?|properties)\s*[:\-]?\s*(.+?)(?:\.|$)",
        context, re.I | re.DOTALL
    )
    if col_match:
        raw = col_match.group(1)
        cols_raw = [c.strip().lower().replace(" ", "_") for c in re.split(r"[,\n;]+", raw) if c.strip()]
    else:
        # Try to extract capitalised or snake_case words that look like field names
        cols_raw = re.findall(
            r"\b(first_?name|last_?name|full_?name|age|gender|sex|email|phone|mobile|"
            r"ssn|social_?security|dob|date_?of_?birth|address|city|state|country|zip|postal|"
            r"credit_?card|account_?number|ip_?address|passport|diagnosis|mrn|npi|"
            r"status|type|category|amount|price|total|created_?at|updated_?at|id|uuid)\b",
            text
        )
        # Also grab "first name" style (space-separated)
        space_cols = re.findall(
            r"\b(first name|last name|full name|date of birth|credit card|account number|ip address)\b",
            context, re.I
        )
        cols_raw += [c.replace(" ", "_").lower() for c in space_cols]
        cols_raw = list(dict.fromkeys(cols_raw))  # dedupe preserving order

    TYPE_MAP = {
        "id": "integer", "age": "integer", "count": "integer",
        "email": "email", "phone": "phone", "mobile": "phone",
        "ssn": "string", "social_security": "string", "dob": "date",
        "date_of_birth": "date", "created_at": "date", "updated_at": "date",
        "amount": "float", "price": "float", "total": "float",
        "gender": "enum", "sex": "enum", "status": "enum", "type": "enum", "category": "enum",
    }
    ENUM_VALS = {
        "gender": ["Male", "Female", "Non-binary"],
        "sex": ["Male", "Female"],
        "status": ["Active", "Inactive", "Pending"],
    }

    columns = []
    for c in cols_raw:
        if not c or len(c) > 50:
            continue
        ctype = TYPE_MAP.get(c, "string")
        columns.append({
            "name": c,
            "type": ctype,
            "enum_values": ENUM_VALS.get(c, []),
        })

    # Distributions — handle both word orders:
    #   "80% male"  →  number then label
    #   "men should be 80%"  →  label then number
    #   "male: 80%"  →  label colon number
    distributions = {}

    GENDER_WORDS  = {
        "male": "Male", "men": "Male", "man": "Male",
        "female": "Female", "women": "Female", "woman": "Female",
        "non-binary": "Non-binary", "nonbinary": "Non-binary", "nb": "Non-binary",
        "not-specified": "Not specified", "notspecified": "Not specified",
        "unspecified": "Not specified", "not_specified": "Not specified",
        "other": "Other", "others": "Other",
        "unknown": "Unknown",
        "prefer-not-to-say": "Prefer not to say",
        "transgender": "Transgender", "trans": "Transgender",
        "genderfluid": "Gender fluid", "gender-fluid": "Gender fluid",
        "agender": "Agender",
    }
    STATUS_WORDS  = {"active", "inactive", "pending", "enabled", "disabled", "approved", "rejected"}
    BOOL_WORDS    = {"yes", "no", "true", "false"}

    def _classify_label(word: str):
        w = word.lower()
        if w in GENDER_WORDS:  return ("gender", GENDER_WORDS[w])
        if w in STATUS_WORDS:  return ("status", w.capitalize())
        if w in BOOL_WORDS:    return ("flag",   w.capitalize())
        return None

    buckets: Dict[str, Dict[str, int]] = {}

    # Pattern A: "80% male" / "80% men"
    for m in re.finditer(r"(\d+)\s*%\s*(?:of\s+(?:the\s+)?(?:mix|total|records?)?\s*)?(\w[\w-]*)", text):
        pct, word = int(m.group(1)), m.group(2)
        res = _classify_label(word)
        if res:
            col_key, norm_val = res
            buckets.setdefault(col_key, {})[norm_val] = pct

    # Pattern B: "men should be 80%" / "male: 80%" / "men → 80%"
    for m in re.finditer(r"(\w[\w-]*)\s*(?:should\s+be|must\s+be|:|\-|→|=)\s*(\d+)\s*%", text):
        word, pct = m.group(1), int(m.group(2))
        res = _classify_label(word)
        if res:
            col_key, norm_val = res
            buckets.setdefault(col_key, {})[norm_val] = pct

    # Pattern C: "X% of them should be <label>" / "X% <label>"
    for m in re.finditer(r"(\d+)\s*%\s+(?:of\s+them\s+)?(?:should\s+be\s+)?(\w[\w-]*)", text):
        pct, word = int(m.group(1)), m.group(2)
        res = _classify_label(word)
        if res:
            col_key, norm_val = res
            buckets.setdefault(col_key, {}).setdefault(norm_val, pct)

    # Auto-fill remainder ONLY for boolean flags (Yes/No), not for gender.
    # Gender can have 3+ values (Non-binary, Not specified, etc.) so we never assume
    # the rest is the binary opposite — use exactly what was stated.
    for col_key, vals in buckets.items():
        total = sum(vals.values())
        if col_key == "flag" and total < 100 and len(vals) == 1:
            [(only_val, _)] = vals.items()
            vals["No" if only_val == "Yes" else "Yes"] = 100 - total
        distributions[col_key] = vals

    # Compliance rules — detect PII mentions and masking instructions
    PII_KEYWORDS = {
        "ssn": ("PII", "ssn"), "social_security": ("PII", "ssn"),
        "email": ("PII", "email"), "phone": ("PII", "phone"), "mobile": ("PII", "phone"),
        "dob": ("PII", "date_of_birth"), "date_of_birth": ("PII", "date_of_birth"),
        "credit_card": ("PCI", "credit_card"), "account_number": ("PCI", "account_number"),
        "ip_address": ("PII", "ip_address"), "passport": ("PII", "passport"),
        "diagnosis": ("HIPAA", "diagnosis"), "mrn": ("HIPAA", "mrn"),
    }

    compliance_rules = {}
    for col in columns:
        cn = col["name"].lower()
        for kw, (cat, ptype) in PII_KEYWORDS.items():
            if kw in cn:
                # Check for masking instructions in context
                custom_rule = None
                action = "fake_realistic"

                # "last 4 digits" / "last N digits visible"
                m4 = re.search(
                    r"(?:last\s+(\d+)\s+digits?\s+(?:only\s+)?(?:visible|shown?)|"
                    r"mask\s+(?:all\s+)?(?:but\s+)?(?:last\s+(\d+)))",
                    text, re.I
                )
                if m4:
                    digits = m4.group(1) or m4.group(2) or "4"
                    custom_rule = f"Show only last {digits} digits, mask the rest with *"
                    action = "custom"
                elif re.search(r"\bmask\b|\bmasked?\b|\bredact\b|\bhide\b", text, re.I):
                    action = "mask"
                elif re.search(r"\bfake\b|\bsynthetic\b|\bgenerate\b", text, re.I):
                    action = "fake_realistic"

                compliance_rules[col["name"]] = {
                    "pii_type": cat,
                    "action": action,
                    "custom_rule": custom_rule,
                }
                break

    return {
        "volume": volume,
        "entity_type": entity_type,
        "columns": columns,
        "distributions": distributions,
        "compliance_rules": compliance_rules,
        "temporal": {},
    }


def extract_from_context(
    context_text: str,
    llm_provider=None,
    allow_fallback: bool = True,
    warnings: list = None,
) -> Dict[str, Any]:
    """
    Main entry point. Uses LLM if available.

    allow_fallback: if True (default) and the LLM call fails, fall back to
      regex heuristics and append a notice to `warnings` (if provided).
      If False and the LLM call fails, raises LLMUnavailableError — the
      caller is responsible for surfacing this to the user.
    """
    from services.llm_service import LLMUnavailableError

    if not context_text.strip():
        return {
            "volume": None, "entity_type": "records", "columns": [],
            "distributions": {}, "compliance_rules": {}, "temporal": {},
        }

    # Try LLM first (skip for local/demo providers — go straight to regex)
    if llm_provider is not None and getattr(llm_provider, "sends_data_to_external_api", True):
        try:
            # Truncate context to avoid hitting provider token limits.
            # Context extraction only needs the user's description, not file rows.
            truncated = context_text.strip()[:4000]
            prompt = EXTRACTION_PROMPT.format(context=truncated)
            raw = llm_provider.generate(prompt, EXTRACTION_SYSTEM)
            # Strip markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)
            # Discard if the LLM returned an error object (e.g. from Azure config issues)
            if "error" in parsed and len(parsed) == 1:
                raise ValueError(f"LLM returned error: {parsed['error']}")
            # Ensure required keys exist
            parsed.setdefault("volume", None)
            parsed.setdefault("columns", [])
            parsed.setdefault("tables", [])
            parsed.setdefault("relationships", [])
            parsed.setdefault("distributions", {})
            parsed.setdefault("compliance_rules", {})
            parsed.setdefault("temporal", {})
            # Normalise entity_type — some LLMs return the string "null" or None
            raw_et = parsed.get("entity_type")
            if not raw_et or str(raw_et).strip().lower() in ("null", "none", ""):
                parsed["entity_type"] = "records"
            else:
                parsed["entity_type"] = str(raw_et).strip()
            # Normalise any custom masking rules → structured masking_op
            _normalise_compliance_rules(parsed["compliance_rules"], llm_provider)
            return parsed
        except Exception as exc:
            if not allow_fallback:
                raise LLMUnavailableError(
                    f"Context extraction failed: {exc}. "
                    "Enable rule-based fallback in Settings or check your LLM provider."
                ) from exc
            if warnings is not None:
                warnings.append("Schema extraction used rule-based fallback — LLM call failed.")

    result = _regex_fallback(context_text)
    # Normalise any custom masking rules from the regex fallback too
    _normalise_compliance_rules(result.get("compliance_rules", {}), llm_provider)
    return result
