"""
Prompts for compliance_detector.py — detect applicable regulatory frameworks
from a free-form data description.

Usage:
    from prompts.compliance_domain import SYSTEM, TEMPLATE
    prompt = TEMPLATE.format(context=context_text[:2000])
    raw = llm_provider.generate(prompt, SYSTEM)
"""

SYSTEM = (
    "You are a compliance analyst. Identify applicable regulatory frameworks "
    "from a data description. Return ONLY valid JSON, no explanation."
)

TEMPLATE = """Given this data context:
"{context}"

Which regulatory frameworks apply? Return ONLY this JSON:
{{"frameworks": ["PII", "HIPAA", ...]}}

Choose only from: PII, PCI, HIPAA, GDPR, CCPA, SOX, FERPA, GLBA.
Return ONLY the JSON object."""
