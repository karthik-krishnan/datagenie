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
from prompts.masking_normalize import SYSTEM as _NORM_SYSTEM, TEMPLATE as _NORM_PROMPT


# ─── Public: normalize rule text → structured op ─────────────────────────────
def normalize_masking_rule(
    rule_text: str,
    llm_provider=None,
) -> Optional[Dict[str, Any]]:
    """
    Convert a plain-English masking instruction to a MaskingOp dict.

    Uses LLM when available (provider is not DemoProvider). If the LLM fails
    after retries, the exception is raised directly. Returns None if the rule
    is empty.
    """
    if not rule_text or not rule_text.strip():
        return None

    # ── LLM path (skip for demo/local providers) ──────────────────────────────
    if llm_provider is not None and getattr(llm_provider, "sends_data_to_external_api", True):
        last_exc: Exception | None = None
        for attempt in range(1, 4):  # up to 3 attempts
            try:
                # On retry, hint the LLM about valid op types so it self-corrects
                hint = ""
                if attempt > 1:
                    hint = (
                        f"\n\nIMPORTANT: Your previous response had an invalid or unrecognised op "
                        f"type. You MUST use one of these exact type names: "
                        f"{', '.join(sorted(OP_TYPES))}."
                    )
                prompt = _NORM_PROMPT.format(rule=rule_text.strip() + hint)
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
                # Valid JSON but unrecognised op type — retry with hint
                last_exc = ValueError(
                    f"LLM returned unrecognised masking op type '{op.get('type')}'"
                )
                logger.debug("normalize_masking_rule attempt %d: %s", attempt, last_exc)
            except (json.JSONDecodeError, ValueError, KeyError) as exc:
                last_exc = exc
                logger.debug("normalize_masking_rule attempt %d failed: %s", attempt, exc)
            except Exception as exc:
                # Network/API error — no point retrying
                last_exc = exc
                logger.debug("normalize_masking_rule LLM network error: %s", exc)
                break

        raise last_exc

    return None


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
