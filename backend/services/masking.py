"""
Masking operations for test data generation.

Architecture:
  1. At rule-entry time: normalize_masking_rule(text, llm_provider)
     asks the LLM to produce a Python lambda string ONCE and stores it as
     {"fn": "lambda v: ..."}.
  2. At generation time: apply_masking_op(value, op) evals the lambda and
     applies it — no LLM call, deterministic for all rows.

Backward-compatible: legacy structured ops ({"type": "show_last_n_digits", ...})
are still handled by apply_masking_op.
"""

import re
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from prompts.masking_normalize import SYSTEM as _NORM_SYSTEM, TEMPLATE as _NORM_PROMPT


def normalize_masking_rule(
    rule_text: str,
    llm_provider=None,
) -> Optional[Dict[str, Any]]:
    """Ask the LLM to produce a Python lambda for the masking rule.

    Returns {"fn": "lambda v: ..."} on success, None for empty rules or demo mode.
    Raises on LLM failure.
    """
    if not rule_text or not rule_text.strip():
        return None

    if llm_provider is None or not getattr(llm_provider, "sends_data_to_external_api", True):
        return None

    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            prompt = _NORM_PROMPT.format(rule=rule_text.strip())
            raw = llm_provider.generate(prompt, _NORM_SYSTEM)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw.strip())
            op = json.loads(raw)
            if not isinstance(op, dict) or "fn" not in op:
                raise ValueError(f"Expected {{\"fn\": \"lambda v: ...\"}} but got: {op}")
            # Validate: must eval without error and return a string on a test value
            fn = eval(op["fn"])  # noqa: S307
            result = fn("test123")
            if not isinstance(result, str):
                raise ValueError(f"Lambda must return str, got {type(result)}")
            return op
        except Exception as exc:
            last_exc = exc
            logger.debug("normalize_masking_rule attempt %d failed: %s", attempt, exc)
            if "network" in str(exc).lower() or "connection" in str(exc).lower():
                break  # no point retrying network errors

    raise last_exc


def apply_masking_op(value: Any, op: Dict[str, Any]) -> str:
    """Apply a masking op to a value deterministically (no LLM call).

    Handles:
      - Lambda ops: {"fn": "lambda v: ..."}  — eval and apply
      - Legacy structured ops: {"type": "show_last_n_digits", ...}
    """
    sv = str(value) if value is not None else ""
    if not op:
        return re.sub(r"[A-Za-z0-9]", "*", sv)

    # ── Lambda op (new) ───────────────────────────────────────────────────────
    if "fn" in op:
        try:
            return str(eval(op["fn"])(sv))  # noqa: S307
        except Exception as exc:
            logger.warning("Lambda masking failed (%s), falling back to mask_all", exc)
            return re.sub(r"[A-Za-z0-9]", "*", sv)

    # ── Legacy structured ops ─────────────────────────────────────────────────
    op_type = op.get("type", "mask_all")

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
