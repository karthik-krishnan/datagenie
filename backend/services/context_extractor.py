"""
Extracts structured generation parameters from free-form natural language context.
Uses LLM when available, falls back to regex heuristics for demo mode.
"""
import re
import json
from typing import Any, Dict

from prompts.extraction import SYSTEM as EXTRACTION_SYSTEM, TEMPLATE as EXTRACTION_PROMPT


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _normalise_compliance_rules(compliance_rules: Dict[str, Any], llm_provider=None) -> None:
    """Normalise custom masking rules to structured masking_op in-place."""
    from services.masking import normalize_masking_rule
    for rule in compliance_rules.values():
        if isinstance(rule, dict) and rule.get("custom_rule") and not rule.get("masking_op"):
            op = normalize_masking_rule(rule["custom_rule"], llm_provider)
            if op:
                rule["masking_op"] = op


def _parse_llm_response(raw: str) -> Dict[str, Any]:
    """Parse and normalise the LLM JSON response."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    parsed = json.loads(raw)
    if "error" in parsed and len(parsed) == 1:
        raise ValueError(f"LLM returned error: {parsed['error']}")
    parsed.setdefault("volume", None)
    parsed.setdefault("columns", [])
    parsed.setdefault("tables", [])
    parsed.setdefault("relationships", [])
    parsed.setdefault("distributions", {})
    parsed.setdefault("compliance_rules", {})
    parsed.setdefault("temporal", {})
    raw_et = parsed.get("entity_type")
    parsed["entity_type"] = (
        str(raw_et).strip()
        if raw_et and str(raw_et).strip().lower() not in ("null", "none", "")
        else "records"
    )
    return parsed


# ─── Demo-mode regex fallback ─────────────────────────────────────────────────

def _regex_fallback(context: str) -> Dict[str, Any]:
    """Best-effort extraction without LLM (demo mode only)."""
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

    # Columns
    cols_raw = []
    col_match = re.search(
        r"(?:with\s+)?(?:fields?|columns?|attributes?|properties)\s*[:\-]?\s*(.+?)(?:\.|$)",
        context, re.I | re.DOTALL
    )
    if col_match:
        raw = col_match.group(1)
        cols_raw = [c.strip().lower().replace(" ", "_") for c in re.split(r"[,\n;]+", raw) if c.strip()]
    else:
        cols_raw = re.findall(
            r"\b(first_?name|last_?name|full_?name|age|gender|sex|email|phone|mobile|"
            r"ssn|social_?security|dob|date_?of_?birth|address|city|state|country|zip|postal|"
            r"credit_?card|account_?number|ip_?address|passport|diagnosis|mrn|npi|"
            r"status|type|category|amount|price|total|created_?at|updated_?at|id|uuid)\b",
            text
        )
        space_cols = re.findall(
            r"\b(first name|last name|full name|date of birth|credit card|account number|ip address)\b",
            context, re.I
        )
        cols_raw += [c.replace(" ", "_").lower() for c in space_cols]
        cols_raw = list(dict.fromkeys(cols_raw))

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

    columns = [
        {"name": c, "type": TYPE_MAP.get(c, "string"), "enum_values": ENUM_VALS.get(c, [])}
        for c in cols_raw if c and len(c) <= 50
    ]

    # Distributions
    GENDER_WORDS = {
        "male": "Male", "men": "Male", "man": "Male",
        "female": "Female", "women": "Female", "woman": "Female",
        "non-binary": "Non-binary", "nonbinary": "Non-binary", "nb": "Non-binary",
        "not-specified": "Not specified", "notspecified": "Not specified",
        "unspecified": "Not specified", "not_specified": "Not specified",
        "other": "Other", "others": "Other", "unknown": "Unknown",
        "prefer-not-to-say": "Prefer not to say",
        "transgender": "Transgender", "trans": "Transgender",
        "genderfluid": "Gender fluid", "gender-fluid": "Gender fluid", "agender": "Agender",
    }
    STATUS_WORDS = {"active", "inactive", "pending", "enabled", "disabled", "approved", "rejected"}
    BOOL_WORDS   = {"yes", "no", "true", "false"}

    def _classify_label(word: str):
        w = word.lower()
        if w in GENDER_WORDS: return ("gender", GENDER_WORDS[w])
        if w in STATUS_WORDS: return ("status", w.capitalize())
        if w in BOOL_WORDS:   return ("flag",   w.capitalize())
        return None

    buckets: Dict[str, Dict[str, int]] = {}
    for pattern in [
        r"(\d+)\s*%\s*(?:of\s+(?:the\s+)?(?:mix|total|records?)?\s*)?(\w[\w-]*)",
        r"(\w[\w-]*)\s*(?:should\s+be|must\s+be|:|\-|→|=)\s*(\d+)\s*%",
        r"(\d+)\s*%\s+(?:of\s+them\s+)?(?:should\s+be\s+)?(\w[\w-]*)",
    ]:
        for m in re.finditer(pattern, text):
            a, b = m.group(1), m.group(2)
            pct, word = (int(a), b) if a.isdigit() else (int(b), a)
            res = _classify_label(word)
            if res:
                col_key, norm_val = res
                buckets.setdefault(col_key, {}).setdefault(norm_val, pct)

    distributions = {}
    for col_key, vals in buckets.items():
        total = sum(vals.values())
        if col_key == "flag" and total < 100 and len(vals) == 1:
            [(only_val, _)] = vals.items()
            vals["No" if only_val == "Yes" else "Yes"] = 100 - total
        distributions[col_key] = vals

    # Compliance rules
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
        for kw, (cat, _) in PII_KEYWORDS.items():
            if kw in cn:
                m4 = re.search(
                    r"(?:last\s+(\d+)\s+digits?\s+(?:only\s+)?(?:visible|shown?)|"
                    r"mask\s+(?:all\s+)?(?:but\s+)?(?:last\s+(\d+)))",
                    text, re.I
                )
                if m4:
                    digits = m4.group(1) or m4.group(2) or "4"
                    compliance_rules[col["name"]] = {
                        "pii_type": cat, "action": "custom",
                        "custom_rule": f"Show only last {digits} digits, mask the rest with *",
                    }
                elif re.search(r"\bmask\b|\bmasked?\b|\bredact\b|\bhide\b", text, re.I):
                    compliance_rules[col["name"]] = {"pii_type": cat, "action": "mask", "custom_rule": None}
                else:
                    compliance_rules[col["name"]] = {"pii_type": cat, "action": "fake_realistic", "custom_rule": None}
                break

    return {
        "volume": volume,
        "entity_type": entity_type,
        "columns": columns,
        "distributions": distributions,
        "compliance_rules": compliance_rules,
        "temporal": {},
    }


# ─── Public entry point ───────────────────────────────────────────────────────

def extract_from_context(
    context_text: str,
    llm_provider=None,
) -> Dict[str, Any]:
    """Extract structured parameters from natural language context.

    - Empty context → returns empty defaults
    - Demo/local provider → regex fallback (no LLM call)
    - Real provider → LLM extraction; raises on failure
    """
    if not context_text.strip():
        return {
            "volume": None, "entity_type": "records", "columns": [],
            "distributions": {}, "compliance_rules": {}, "temporal": {},
        }

    if llm_provider is not None and getattr(llm_provider, "sends_data_to_external_api", True):
        raw = llm_provider.generate(
            EXTRACTION_PROMPT.format(context=context_text.strip()[:4000]),
            EXTRACTION_SYSTEM,
        )
        result = _parse_llm_response(raw)
    else:
        result = _regex_fallback(context_text)

    _normalise_compliance_rules(result.get("compliance_rules", {}), llm_provider)
    return result
