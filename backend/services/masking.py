"""
Structured masking operations for test data generation.

Architecture:
  1. At schema-inference time: normalize_masking_rule(text, llm_provider)
     converts a plain-English masking instruction into a MaskingOp dict ONCE.
  2. At generation time: apply_masking_op(value, op) executes the op
     deterministically — no regex guessing, no LLM call.

Supported op types:
  show_last_n_digits    → mask all digits, reveal last n   (e.g. ****-****-****-4321)
  mask_last_n_digits    → reveal all digits, mask last n   (e.g. 1234-5678-****-****)
  show_first_n_digits   → reveal first n digits, mask rest
  show_last_n_chars     → reveal last n characters, mask rest  (e.g. *****3)
  mask_last_n_chars     → mask last n characters, reveal rest  (e.g. abc***)
  show_first_n_chars    → reveal first n chars, mask rest
  mask_first_n_chars    → mask first n chars, reveal rest
  partial_email         → j***@example.com style
  date_year_only        → keep only the year portion
  range_bucket          → numeric value → "X0-X9" bucket
  redact                → [REDACTED]
  mask_all              → replace every alphanumeric char with *
  format_preserve_mask  → keep separators/symbols, replace digit positions with *
"""

import re
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─── Canonical op type names ─────────────────────────────────────────────────
OP_TYPES = {
    "show_last_n_digits",
    "mask_last_n_digits",
    "show_first_n_digits",
    "show_last_n_chars",
    "mask_last_n_chars",
    "show_first_n_chars",
    "mask_first_n_chars",
    "partial_email",
    "date_year_only",
    "range_bucket",
    "redact",
    "mask_all",
    "format_preserve_mask",
}

# ─── LLM normalisation prompt ─────────────────────────────────────────────────
_NORM_SYSTEM = (
    "You are a data-masking rule parser. Convert plain-English masking instructions "
    "into a structured JSON operation. Return ONLY valid JSON, no explanation."
)

_NORM_PROMPT = """Convert this masking rule to a structured operation:

Rule: "{rule}"

Return a JSON object with EXACTLY one of these forms:
  {{"type": "show_last_n_digits",  "n": <integer>}}
  {{"type": "mask_last_n_digits",  "n": <integer>}}
  {{"type": "show_first_n_digits", "n": <integer>}}
  {{"type": "show_last_n_chars",   "n": <integer>}}
  {{"type": "mask_last_n_chars",   "n": <integer>}}
  {{"type": "show_first_n_chars",  "n": <integer>}}
  {{"type": "mask_first_n_chars",  "n": <integer>}}
  {{"type": "partial_email"}}
  {{"type": "date_year_only"}}
  {{"type": "range_bucket", "size": <integer>}}
  {{"type": "redact"}}
  {{"type": "mask_all"}}
  {{"type": "format_preserve_mask"}}

Guidelines:
- "last 4 digits visible" / "show last 4 digits" / "****1234" → show_last_n_digits, n=4
- "mask last 4 digits" / "hide last digit" → mask_last_n_digits, n=<N or 1>
- "show first 6 digits" → show_first_n_digits, n=6
- "mask everything except last character" / "show only last char" → show_last_n_chars, n=1
- "mask everything except last 3 characters" → show_last_n_chars, n=3
- "show last 4 characters" / "reveal last 4 chars" → show_last_n_chars, n=4
- "mask last 3 characters" / "hide last 2 chars" → mask_last_n_chars, n=<N>
- "keep first 3 characters" / "show first 3 chars" → show_first_n_chars, n=3
- "mask first 4 chars" → mask_first_n_chars, n=4
- "mask email" / "obfuscate email" → partial_email
- "year only" / "just the year" → date_year_only
- "age range" / "bucket" / "10-year range" → range_bucket, size=10
- "redact" / "remove" / "blank out" → redact
- "mask everything" / "full mask" / "hide all" (with no exception) → mask_all
- "keep format" / "format-preserving" → format_preserve_mask
- If n is not stated, default to 4 for digit ops, 1 for "last char" ops, 3 for other char ops.
- IMPORTANT: "mask everything except last N chars" means SHOW last N chars → show_last_n_chars

Return ONLY the JSON object.
"""


# ─── Keyword-based fallback (no LLM required) ────────────────────────────────
def _keyword_normalize(rule: str) -> Optional[Dict[str, Any]]:
    """Best-effort keyword matching when LLM is unavailable."""
    t = rule.lower().strip()

    # ── "except" patterns — must be checked BEFORE generic mask/hide ──────────
    # "mask everything except last N char(s)" → show_last_n_chars
    m = re.search(
        r"except\s+(?:the\s+)?last\s+(\d+)\s+chars?"
        r"|except\s+(?:the\s+)?last\s+char(?:acter)?\b"
        r"|all\s+except\s+(?:the\s+)?last\s+(\d+)\s+chars?"
        r"|all\s+except\s+(?:the\s+)?last\s+char(?:acter)?\b",
        t,
    )
    if m:
        n = int(m.group(1) or m.group(2) or 1) if (m.group(1) or m.group(2)) else 1
        return {"type": "show_last_n_chars", "n": n}

    # "mask everything except last N digit(s)" → show_last_n_digits
    m = re.search(
        r"except\s+(?:the\s+)?last\s+(\d+)\s+digits?"
        r"|except\s+(?:the\s+)?last\s+digit\b",
        t,
    )
    if m:
        n = int(m.group(1)) if m.group(1) else 1
        return {"type": "show_last_n_digits", "n": n}

    # "mask everything except first N char(s)" → show_first_n_chars
    m = re.search(
        r"except\s+(?:the\s+)?first\s+(\d+)\s+chars?"
        r"|except\s+(?:the\s+)?first\s+char(?:acter)?\b",
        t,
    )
    if m:
        n = int(m.group(1)) if m.group(1) else 1
        return {"type": "show_first_n_chars", "n": n}

    # ── digit-specific ops ────────────────────────────────────────────────────
    # "mask last N digit(s)" / "hide last digit"
    m = re.search(r"(?:mask|hide)\s+(?:only\s+)?(?:the\s+)?last\s+(\d+)\s+digits?", t)
    if m:
        return {"type": "mask_last_n_digits", "n": int(m.group(1))}
    if re.search(r"(?:mask|hide)\s+(?:only\s+)?(?:the\s+)?last\s+digit\b", t):
        return {"type": "mask_last_n_digits", "n": 1}

    # "show/keep last N digit(s)" / "last N digits visible"
    m = re.search(
        r"(?:show|keep|visible|reveal)\s+(?:only\s+)?(?:the\s+)?last\s+(\d+)\s+digits?"
        r"|last\s+(\d+)\s+digits?\s+(?:visible|only|shown?)"
        r"|only\s+last\s+(\d+)\s+digits?",
        t,
    )
    if m:
        n = int(next(g for g in m.groups() if g is not None))
        return {"type": "show_last_n_digits", "n": n}
    # bare "last N digits" (credit-card convention)
    m = re.search(r"\blast\s+(\d+)\s+digits?\b", t)
    if m:
        return {"type": "show_last_n_digits", "n": int(m.group(1))}
    if re.search(r"\blast\s+digit\b", t) and "char" not in t:
        return {"type": "show_last_n_digits", "n": 1}

    # "show first N digit(s)"
    m = re.search(
        r"(?:show|keep|visible)\s+(?:the\s+)?first\s+(\d+)\s+digits?"
        r"|first\s+(\d+)\s+digits?\s+(?:visible|only)",
        t,
    )
    if m:
        n = int(next(g for g in m.groups() if g is not None))
        return {"type": "show_first_n_digits", "n": n}

    # ── character-level ops ───────────────────────────────────────────────────
    # "show/keep last N char(s)"
    m = re.search(
        r"(?:show|keep|reveal|visible)\s+(?:only\s+)?(?:the\s+)?last\s+(\d+)\s+chars?"
        r"|(?:show|keep|reveal|visible)\s+(?:only\s+)?(?:the\s+)?last\s+char(?:acter)?\b"
        r"|last\s+(\d+)\s+chars?\s+(?:visible|only|shown?)"
        r"|only\s+last\s+(\d+)\s+chars?",
        t,
    )
    if m:
        raw_n = m.group(1) or m.group(2) or m.group(3)
        n = int(raw_n) if raw_n else 1
        return {"type": "show_last_n_chars", "n": n}

    # "mask last N char(s)"
    m = re.search(
        r"(?:mask|hide)\s+(?:the\s+)?last\s+(\d+)\s+chars?"
        r"|(?:mask|hide)\s+(?:the\s+)?last\s+char(?:acter)?\b",
        t,
    )
    if m:
        n = int(m.group(1)) if m.group(1) else 1
        return {"type": "mask_last_n_chars", "n": n}

    # "show/keep first N char(s)"
    m = re.search(r"(?:show|keep)\s+(?:the\s+)?first\s+(\d+)\s+chars?", t)
    if m:
        return {"type": "show_first_n_chars", "n": int(m.group(1))}

    # "mask first N char(s)"
    m = re.search(r"mask\s+(?:the\s+)?first\s+(\d+)\s+chars?", t)
    if m:
        return {"type": "mask_first_n_chars", "n": int(m.group(1))}

    # ── other ops ─────────────────────────────────────────────────────────────
    if re.search(r"\bemail\b", t):
        return {"type": "partial_email"}

    if re.search(r"\byear\b", t):
        return {"type": "date_year_only"}

    m = re.search(r"(?:range|bucket)", t)
    if m:
        size_m = re.search(r"(\d+)\s*[-–]\s*year|(\d+)\s*bucket", t)
        size = int(size_m.group(1) or size_m.group(2)) if size_m else 10
        return {"type": "range_bucket", "size": size}

    if re.search(r"\bredact\b|\bremove\b|\bblank\b", t):
        return {"type": "redact"}

    if re.search(
        r"format.?preserv|keep.{0,10}format|preserv.{0,5}format"
        r"|replace.{0,10}digit|mask.{0,10}digit.{0,10}keep.{0,10}format",
        t,
    ):
        return {"type": "format_preserve_mask"}

    # Generic mask/hide — only if no "except" clause (already handled above)
    if re.search(r"\bmask\b|\bhide\b|\bobfuscat\b|\bconceal\b", t):
        return {"type": "mask_all"}

    return None


# ─── Public: normalize rule text → structured op ─────────────────────────────
def normalize_masking_rule(
    rule_text: str,
    llm_provider=None,
) -> Optional[Dict[str, Any]]:
    """
    Convert a plain-English masking instruction to a MaskingOp dict.

    Tries LLM first (if provider is not DemoProvider), then falls back to
    keyword matching.  Returns None if the rule is empty or unrecognised.
    """
    if not rule_text or not rule_text.strip():
        return None

    # ── LLM path ──────────────────────────────────────────────────────────────
    if llm_provider is not None:
        try:
            if not llm_provider.is_demo:
                prompt = _NORM_PROMPT.format(rule=rule_text.strip())
                raw = llm_provider.generate(prompt, _NORM_SYSTEM)
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw.strip())
                op = json.loads(raw)
                if isinstance(op, dict) and op.get("type") in OP_TYPES:
                    for k in ("n", "size"):
                        if k in op:
                            op[k] = int(op[k])
                    return op
        except Exception as exc:
            logger.debug("normalize_masking_rule LLM failed: %s", exc)

    # ── Keyword fallback ──────────────────────────────────────────────────────
    return _keyword_normalize(rule_text)


# ─── Public: apply a structured MaskingOp to a value ─────────────────────────
def apply_masking_op(value: Any, op: Dict[str, Any]) -> str:
    """
    Execute a structured MaskingOp deterministically.

    Args:
        value: The generated value (will be coerced to str).
        op:    A MaskingOp dict with at least {"type": "<op_type>"}.

    Returns:
        The masked string.  Falls back to mask_all if op type is unknown.
    """
    sv = str(value) if value is not None else ""
    op_type = (op or {}).get("type", "mask_all")

    # ── show_last_n_digits ────────────────────────────────────────────────────
    if op_type == "show_last_n_digits":
        n = max(1, int(op.get("n", 4)))
        digit_positions = [i for i, c in enumerate(sv) if c.isdigit()]
        if len(digit_positions) <= n:
            return sv
        result = list(re.sub(r"\d", "*", sv))
        for pos in digit_positions[-n:]:
            result[pos] = sv[pos]
        return "".join(result)

    # ── mask_last_n_digits ────────────────────────────────────────────────────
    if op_type == "mask_last_n_digits":
        n = max(1, int(op.get("n", 4)))
        digit_positions = [i for i, c in enumerate(sv) if c.isdigit()]
        result = list(sv)
        for pos in digit_positions[-n:]:
            result[pos] = "*"
        return "".join(result)

    # ── show_first_n_digits ───────────────────────────────────────────────────
    if op_type == "show_first_n_digits":
        n = max(1, int(op.get("n", 4)))
        digit_positions = [i for i, c in enumerate(sv) if c.isdigit()]
        result = list(sv)
        for pos in digit_positions[n:]:
            result[pos] = "*"
        return "".join(result)

    # ── show_last_n_chars ─────────────────────────────────────────────────────
    if op_type == "show_last_n_chars":
        n = max(1, int(op.get("n", 1)))
        if len(sv) <= n:
            return sv
        return "*" * (len(sv) - n) + sv[-n:]

    # ── mask_last_n_chars ─────────────────────────────────────────────────────
    if op_type == "mask_last_n_chars":
        n = max(1, int(op.get("n", 1)))
        if len(sv) <= n:
            return "*" * len(sv)
        return sv[:-n] + "*" * n

    # ── show_first_n_chars ────────────────────────────────────────────────────
    if op_type == "show_first_n_chars":
        n = max(1, int(op.get("n", 3)))
        if len(sv) <= n:
            return sv
        return sv[:n] + "*" * (len(sv) - n)

    # ── mask_first_n_chars ────────────────────────────────────────────────────
    if op_type == "mask_first_n_chars":
        n = max(1, int(op.get("n", 3)))
        if len(sv) <= n:
            return "*" * len(sv)
        return "*" * n + sv[n:]

    # ── partial_email ─────────────────────────────────────────────────────────
    if op_type == "partial_email":
        if "@" in sv:
            local, domain = sv.split("@", 1)
            if len(local) <= 1:
                return sv
            return local[0] + "*" * (len(local) - 1) + "@" + domain
        return re.sub(r"[A-Za-z0-9]", "*", sv)

    # ── date_year_only ────────────────────────────────────────────────────────
    if op_type == "date_year_only":
        m = re.search(r"\b((?:19|20)\d{2})\b", sv)
        if m:
            return m.group(1)
        return sv

    # ── range_bucket ──────────────────────────────────────────────────────────
    if op_type == "range_bucket":
        size = max(1, int(op.get("size", 10)))
        m = re.search(r"\d+", sv)
        if m:
            num = int(m.group())
            low = (num // size) * size
            return f"{low}-{low + size - 1}"
        return sv

    # ── redact ────────────────────────────────────────────────────────────────
    if op_type == "redact":
        return "[REDACTED]"

    # ── format_preserve_mask ──────────────────────────────────────────────────
    if op_type == "format_preserve_mask":
        return re.sub(r"\d", "*", sv)

    # ── mask_all (default / fallback) ─────────────────────────────────────────
    return re.sub(r"[A-Za-z0-9]", "*", sv)
