"""
Extracts structured generation parameters from free-form natural language context.
Requires a real LLM provider — demo/local mode returns empty defaults.
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



# ─── Public entry point ───────────────────────────────────────────────────────

def extract_from_context(
    context_text: str,
    llm_provider=None,
) -> Dict[str, Any]:
    """Extract structured parameters from natural language context.

    Returns empty defaults if context is empty or no real LLM provider is available.
    Raises on LLM failure.
    """
    _empty = {"volume": None, "entity_type": "records", "columns": [], "distributions": {}, "compliance_rules": {}, "temporal": {}}

    if not context_text.strip():
        return _empty

    if llm_provider is None or not getattr(llm_provider, "sends_data_to_external_api", True):
        return _empty

    raw = llm_provider.generate(
        EXTRACTION_PROMPT.format(context=context_text.strip()[:4000]),
        EXTRACTION_SYSTEM,
    )
    result = _parse_llm_response(raw)

    _normalise_compliance_rules(result.get("compliance_rules", {}), llm_provider)
    return result
