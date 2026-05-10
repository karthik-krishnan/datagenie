"""
Multi-framework regulatory compliance detector.

Identifies applicable frameworks (HIPAA, PCI, GDPR, CCPA, PII, SOX, FERPA)
for each field — based on:
  1. Domain context extracted from free-form text (e.g. "healthcare data" → HIPAA)
  2. LLM-based batch classification (when a real LLM provider is available)
     — handles typos, synonyms, semantic similarity, context-aware variants
  3. Column name keyword matching against a comprehensive field catalog (fallback)
  4. Value pattern matching from sample data (regex / Luhn)

Each detected field returns ALL applicable frameworks, not just one.
"""

import json
import re
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Regex patterns for value-based detection
# ---------------------------------------------------------------------------
EMAIL_RE    = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SSN_RE      = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")
PHONE_RE    = re.compile(r"^[+\d][\d\s\-\(\)\.]{6,}$")
IP4_RE      = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
IP6_RE      = re.compile(r"^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$")
CC_RE       = re.compile(r"^\d{13,19}$")
PASSPORT_RE = re.compile(r"^[A-Z]{1,2}\d{6,9}$")
IBAN_RE     = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$")


def _luhn(num: str) -> bool:
    digits = [int(c) for c in num if c.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    parity = (len(digits) - 2) % 2
    for i, d in enumerate(digits[:-1]):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (total + digits[-1]) % 10 == 0


# ---------------------------------------------------------------------------
# Domain → framework mapping
# Keywords in the free-form context trigger additional frameworks
# ---------------------------------------------------------------------------
DOMAIN_SIGNALS: List[tuple] = [
    # (regex pattern, frameworks implied)
    (r"\bhipaa\b|phi\b|patient|clinical|ehr|emr|healthcare|medical record|diagnosis|physician|hospital|prescription",
     ["HIPAA"]),
    (r"\bpci\b|pci.?dss|payment card|credit card|cardholder|card number|cvv|billing|checkout|merchant",
     ["PCI"]),
    (r"\bgdpr\b|european union|eu resident|data subject|right to erasure|right to forget|consent|lawful basis|dpa\b",
     ["GDPR"]),
    (r"\bccpa\b|california consumer|california privacy|opt.out|do not sell",
     ["CCPA"]),
    (r"\bsox\b|sarbanes.oxley|financial report|audit trail|executive compensation|public company|sec filing",
     ["SOX"]),
    (r"\bferpa\b|student record|academic record|enrollment|gpa|transcript|school|university|educational institution",
     ["FERPA"]),
    (r"\bpii\b|personally identifiable|personal data|personal information",
     ["PII"]),
    (r"\bemployee|hr data|human resources|payroll|personnel|workforce|w-?2\b",
     ["PII", "SOX"]),
    (r"\bfinancial\b|banking|bank account|iban|routing number|wire transfer",
     ["PCI", "SOX"]),
]


def detect_domain_frameworks(context_text: str) -> Set[str]:
    """Return set of frameworks implied by the free-form context text."""
    frameworks: Set[str] = set()
    if not context_text:
        return frameworks
    text = context_text.lower()
    for pattern, fws in DOMAIN_SIGNALS:
        if re.search(pattern, text, re.I):
            frameworks.update(fws)
    return frameworks


# ---------------------------------------------------------------------------
# Field catalog — comprehensive mapping of column name keywords → compliance
# Format: keyword → {frameworks, field_type, default_action, recommendation}
#
# default_action values: fake_realistic | format_preserving | mask | redact
# ---------------------------------------------------------------------------
FIELD_CATALOG: Dict[str, Dict] = {

    # ── PII ──────────────────────────────────────────────────────────────
    "first_name":       {"frameworks": ["PII", "GDPR"],         "field_type": "person_name",         "default_action": "fake_realistic"},
    "last_name":        {"frameworks": ["PII", "GDPR"],         "field_type": "person_name",         "default_action": "fake_realistic"},
    "full_name":        {"frameworks": ["PII", "GDPR"],         "field_type": "person_name",         "default_action": "fake_realistic"},
    "email":            {"frameworks": ["PII", "GDPR", "CCPA"], "field_type": "email_address",       "default_action": "fake_realistic"},
    "phone":            {"frameworks": ["PII", "GDPR", "CCPA"], "field_type": "phone_number",        "default_action": "fake_realistic"},
    "mobile":           {"frameworks": ["PII", "GDPR", "CCPA"], "field_type": "phone_number",        "default_action": "fake_realistic"},
    "fax":              {"frameworks": ["PII"],                  "field_type": "phone_number",        "default_action": "fake_realistic"},
    "address":          {"frameworks": ["PII", "GDPR", "CCPA"], "field_type": "postal_address",      "default_action": "fake_realistic"},
    "street":           {"frameworks": ["PII", "GDPR"],         "field_type": "postal_address",      "default_action": "fake_realistic"},
    "city":             {"frameworks": ["PII", "GDPR"],         "field_type": "city",                "default_action": "fake_realistic"},
    "country":          {"frameworks": ["PII", "GDPR"],         "field_type": "country",             "default_action": "fake_realistic"},
    "state":            {"frameworks": ["PII"],                  "field_type": "state",               "default_action": "fake_realistic"},
    "region":           {"frameworks": ["PII"],                  "field_type": "state",               "default_action": "fake_realistic"},
    "ssn":              {"frameworks": ["PII", "HIPAA"],         "field_type": "social_security",     "default_action": "format_preserving"},
    "social_security":  {"frameworks": ["PII", "HIPAA"],         "field_type": "social_security",     "default_action": "format_preserving"},
    "national_id":      {"frameworks": ["PII", "GDPR"],         "field_type": "national_identifier", "default_action": "format_preserving"},
    "dob":              {"frameworks": ["PII", "GDPR", "HIPAA"],"field_type": "date_of_birth",       "default_action": "fake_realistic"},
    "date_of_birth":    {"frameworks": ["PII", "GDPR", "HIPAA"],"field_type": "date_of_birth",       "default_action": "fake_realistic"},
    "birth_date":       {"frameworks": ["PII", "GDPR", "HIPAA"],"field_type": "date_of_birth",       "default_action": "fake_realistic"},
    "birth_year":       {"frameworks": ["PII", "GDPR"],         "field_type": "date_of_birth",       "default_action": "fake_realistic"},
    "age":              {"frameworks": ["PII", "GDPR"],         "field_type": "age",                 "default_action": "fake_realistic"},
    "passport":         {"frameworks": ["PII", "GDPR"],         "field_type": "passport_number",     "default_action": "format_preserving"},
    "driver_license":   {"frameworks": ["PII"],                  "field_type": "drivers_license",     "default_action": "format_preserving"},
    "license_number":   {"frameworks": ["PII"],                  "field_type": "license_identifier",  "default_action": "format_preserving"},
    "ip_address":       {"frameworks": ["PII", "GDPR"],         "field_type": "ip_address",          "default_action": "mask"},
    "ip":               {"frameworks": ["PII", "GDPR"],         "field_type": "ip_address",          "default_action": "mask"},
    "device_id":        {"frameworks": ["PII", "GDPR", "CCPA"], "field_type": "device_identifier",   "default_action": "mask"},
    "mac_address":      {"frameworks": ["PII", "GDPR"],         "field_type": "device_identifier",   "default_action": "mask"},
    "cookie":           {"frameworks": ["GDPR", "CCPA"],        "field_type": "cookie_id",           "default_action": "mask"},
    "session_id":       {"frameworks": ["GDPR"],                "field_type": "session_identifier",  "default_action": "mask"},
    "geolocation":      {"frameworks": ["PII", "GDPR", "CCPA"], "field_type": "location_data",       "default_action": "mask"},
    "latitude":         {"frameworks": ["PII", "GDPR"],         "field_type": "location_data",       "default_action": "mask"},
    "longitude":        {"frameworks": ["PII", "GDPR"],         "field_type": "location_data",       "default_action": "mask"},
    "gender":           {"frameworks": ["PII", "GDPR"],         "field_type": "demographic",         "default_action": "fake_realistic"},
    "race":             {"frameworks": ["PII", "GDPR"],         "field_type": "sensitive_category",  "default_action": "redact"},
    "ethnicity":        {"frameworks": ["PII", "GDPR"],         "field_type": "sensitive_category",  "default_action": "redact"},
    "religion":         {"frameworks": ["PII", "GDPR"],         "field_type": "sensitive_category",  "default_action": "redact"},
    "political":        {"frameworks": ["GDPR"],                "field_type": "sensitive_category",  "default_action": "redact"},
    "sexual":           {"frameworks": ["PII", "GDPR"],         "field_type": "sensitive_category",  "default_action": "redact"},
    "biometric":        {"frameworks": ["PII", "GDPR", "CCPA"], "field_type": "biometric_data",      "default_action": "redact"},
    "fingerprint":      {"frameworks": ["PII", "GDPR", "CCPA"], "field_type": "biometric_data",      "default_action": "redact"},
    "retina":           {"frameworks": ["PII", "GDPR"],         "field_type": "biometric_data",      "default_action": "redact"},
    "username":         {"frameworks": ["PII"],                  "field_type": "user_identifier",     "default_action": "fake_realistic"},

    # ── PCI DSS ──────────────────────────────────────────────────────────
    "credit_card":      {"frameworks": ["PCI"],                  "field_type": "card_number",         "default_action": "format_preserving"},
    "card_number":      {"frameworks": ["PCI"],                  "field_type": "card_number",         "default_action": "format_preserving"},
    "cc_number":        {"frameworks": ["PCI"],                  "field_type": "card_number",         "default_action": "format_preserving"},
    "pan":              {"frameworks": ["PCI"],                  "field_type": "card_number",         "default_action": "format_preserving"},
    "cvv":              {"frameworks": ["PCI"],                  "field_type": "card_cvv",            "default_action": "redact"},
    "cvc":              {"frameworks": ["PCI"],                  "field_type": "card_cvv",            "default_action": "redact"},
    "card_expiry":      {"frameworks": ["PCI"],                  "field_type": "card_expiry",         "default_action": "fake_realistic"},
    "expiry_date":      {"frameworks": ["PCI"],                  "field_type": "card_expiry",         "default_action": "fake_realistic"},
    "account_number":   {"frameworks": ["PCI", "SOX"],          "field_type": "account_number",      "default_action": "format_preserving"},
    "routing_number":   {"frameworks": ["PCI"],                  "field_type": "routing_number",      "default_action": "format_preserving"},
    "iban":             {"frameworks": ["PCI", "GDPR"],         "field_type": "bank_account",        "default_action": "format_preserving"},
    "bank_account":     {"frameworks": ["PCI"],                  "field_type": "bank_account",        "default_action": "format_preserving"},
    "swift":            {"frameworks": ["PCI"],                  "field_type": "swift_bic",           "default_action": "format_preserving"},
    "sort_code":        {"frameworks": ["PCI"],                  "field_type": "sort_code",           "default_action": "format_preserving"},

    # ── HIPAA ─────────────────────────────────────────────────────────────
    "diagnosis":        {"frameworks": ["HIPAA"],               "field_type": "medical_diagnosis",   "default_action": "fake_realistic"},
    "icd":              {"frameworks": ["HIPAA"],               "field_type": "diagnosis_code",      "default_action": "fake_realistic"},
    "mrn":              {"frameworks": ["HIPAA"],               "field_type": "medical_record_no",   "default_action": "format_preserving"},
    "medical_record":   {"frameworks": ["HIPAA"],               "field_type": "medical_record_no",   "default_action": "format_preserving"},
    "npi":              {"frameworks": ["HIPAA"],               "field_type": "provider_id",         "default_action": "fake_realistic"},
    "patient_id":       {"frameworks": ["HIPAA"],               "field_type": "patient_identifier",  "default_action": "format_preserving"},
    "health_plan":      {"frameworks": ["HIPAA"],               "field_type": "insurance_info",      "default_action": "fake_realistic"},
    "insurance_id":     {"frameworks": ["HIPAA", "PII"],        "field_type": "insurance_number",    "default_action": "format_preserving"},
    "member_id":        {"frameworks": ["HIPAA", "PII"],        "field_type": "insurance_member_id", "default_action": "format_preserving"},
    "prescription":     {"frameworks": ["HIPAA"],               "field_type": "prescription",        "default_action": "fake_realistic"},
    "medication":       {"frameworks": ["HIPAA"],               "field_type": "medication",          "default_action": "fake_realistic"},
    "drug":             {"frameworks": ["HIPAA"],               "field_type": "medication",          "default_action": "fake_realistic"},
    "treatment":        {"frameworks": ["HIPAA"],               "field_type": "treatment_info",      "default_action": "fake_realistic"},
    "procedure":        {"frameworks": ["HIPAA"],               "field_type": "medical_procedure",   "default_action": "fake_realistic"},
    "lab_result":       {"frameworks": ["HIPAA"],               "field_type": "lab_result",          "default_action": "fake_realistic"},
    "test_result":      {"frameworks": ["HIPAA"],               "field_type": "lab_result",          "default_action": "fake_realistic"},
    "dea_number":       {"frameworks": ["HIPAA"],               "field_type": "dea_number",          "default_action": "format_preserving"},
    "admission_date":   {"frameworks": ["HIPAA"],               "field_type": "service_date",        "default_action": "fake_realistic"},
    "discharge_date":   {"frameworks": ["HIPAA"],               "field_type": "service_date",        "default_action": "fake_realistic"},
    "service_date":     {"frameworks": ["HIPAA"],               "field_type": "service_date",        "default_action": "fake_realistic"},
    "provider_name":    {"frameworks": ["HIPAA"],               "field_type": "provider_name",       "default_action": "fake_realistic"},
    "attending":        {"frameworks": ["HIPAA"],               "field_type": "provider_name",       "default_action": "fake_realistic"},

    # ── SOX ──────────────────────────────────────────────────────────────
    "salary":           {"frameworks": ["SOX", "PII"],          "field_type": "compensation",        "default_action": "mask"},
    "compensation":     {"frameworks": ["SOX", "PII"],          "field_type": "compensation",        "default_action": "mask"},
    "bonus":            {"frameworks": ["SOX", "PII"],          "field_type": "compensation",        "default_action": "mask"},
    "revenue":          {"frameworks": ["SOX"],                  "field_type": "financial_data",      "default_action": "mask"},
    "earnings":         {"frameworks": ["SOX"],                  "field_type": "financial_data",      "default_action": "mask"},
    "tax_id":           {"frameworks": ["SOX", "PII"],          "field_type": "tax_identifier",      "default_action": "format_preserving"},
    "ein":              {"frameworks": ["SOX"],                  "field_type": "employer_id",         "default_action": "format_preserving"},
    "tin":              {"frameworks": ["SOX", "PII"],          "field_type": "taxpayer_id",         "default_action": "format_preserving"},
    "audit_log":        {"frameworks": ["SOX"],                  "field_type": "audit_trail",         "default_action": "fake_realistic"},

    # ── FERPA ─────────────────────────────────────────────────────────────
    "student_id":       {"frameworks": ["FERPA", "PII"],        "field_type": "student_identifier",  "default_action": "format_preserving"},
    "gpa":              {"frameworks": ["FERPA"],               "field_type": "academic_record",     "default_action": "fake_realistic"},
    "grade":            {"frameworks": ["FERPA"],               "field_type": "academic_record",     "default_action": "fake_realistic"},
    "transcript":       {"frameworks": ["FERPA"],               "field_type": "academic_record",     "default_action": "fake_realistic"},
    "enrollment":       {"frameworks": ["FERPA"],               "field_type": "enrollment_info",     "default_action": "fake_realistic"},
    "course":           {"frameworks": ["FERPA"],               "field_type": "course_info",         "default_action": "fake_realistic"},
    "academic":         {"frameworks": ["FERPA"],               "field_type": "academic_record",     "default_action": "fake_realistic"},
    "financial_aid":    {"frameworks": ["FERPA", "SOX"],        "field_type": "financial_aid",       "default_action": "mask"},
}

# Per-framework default recommendation text shown to users
FRAMEWORK_RECOMMENDATIONS: Dict[str, str] = {
    "PII":   "Generate realistic but completely synthetic values — no real personal data",
    "PCI":   "Use format-valid non-live values (Luhn-valid card numbers, valid IBANs) — never real card data",
    "HIPAA": "Apply HIPAA Safe Harbor de-identification: replace with synthetic equivalents preserving statistical utility",
    "GDPR":  "Pseudonymize or anonymize — output must not be re-linkable to an EU/EEA data subject",
    "CCPA":  "Anonymize for California consumer data — support right-to-delete patterns",
    "SOX":   "Use masked or range-bucketed financial values; preserve referential integrity for audit trails",
    "FERPA": "Replace with synthetic student identifiers; preserve grade distribution patterns",
}

FRAMEWORK_COLORS: Dict[str, str] = {
    "PII":   "bg-red-100 text-red-700",
    "PCI":   "bg-orange-100 text-orange-700",
    "HIPAA": "bg-purple-100 text-purple-700",
    "GDPR":  "bg-blue-100 text-blue-700",
    "CCPA":  "bg-cyan-100 text-cyan-700",
    "SOX":   "bg-yellow-100 text-yellow-700",
    "FERPA": "bg-green-100 text-green-700",
}


def _match_field_catalog(column_name: str) -> Dict | None:
    """Find the best catalog entry for a column name using substring matching."""
    name_lower = column_name.lower().replace(" ", "_")
    # Exact keyword match first
    for keyword, entry in FIELD_CATALOG.items():
        if keyword == name_lower:
            return entry
    # Substring match (longer keywords first to avoid false positives)
    sorted_keys = sorted(FIELD_CATALOG.keys(), key=len, reverse=True)
    for keyword in sorted_keys:
        if keyword in name_lower or name_lower in keyword:
            return FIELD_CATALOG[keyword]
    return None


def detect_compliance(
    column_name: str,
    sample_values: List[Any],
    domain_frameworks: Set[str] | None = None,
) -> Dict[str, Any]:
    """
    Detect regulatory compliance requirements for a single column.

    Returns:
    {
        "is_sensitive": bool,
        "frameworks": ["PII", "GDPR", ...],   # ALL applicable frameworks
        "field_type": str,
        "default_action": str,
        "recommendations": {framework: recommendation_text},
        "confidence": float,
    }
    """
    domain_frameworks = domain_frameworks or set()
    name_lower = column_name.lower().replace(" ", "_")

    # 1. Catalog match
    catalog_entry = _match_field_catalog(column_name)

    if catalog_entry:
        frameworks = list(set(catalog_entry["frameworks"]) | _domain_boost(catalog_entry["frameworks"], domain_frameworks))
        return {
            "is_sensitive": True,
            "frameworks": frameworks,
            "field_type": catalog_entry["field_type"],
            "default_action": catalog_entry["default_action"],
            "recommendations": {fw: FRAMEWORK_RECOMMENDATIONS[fw] for fw in frameworks if fw in FRAMEWORK_RECOMMENDATIONS},
            "confidence": 0.95,
        }

    # 2. Value pattern matching
    cleaned = [str(v).strip() for v in sample_values if v not in (None, "", "null", "NaN")]
    if cleaned:
        result = _detect_from_values(cleaned, domain_frameworks)
        if result:
            return result

    # 3. Domain-only boost — if domain implies a framework and column looks sensitive
    if domain_frameworks:
        sensitive_hints = ["id", "number", "code", "key", "token", "secret", "hash"]
        if any(hint in name_lower for hint in sensitive_hints):
            fws = list(domain_frameworks)
            return {
                "is_sensitive": True,
                "frameworks": fws,
                "field_type": "identifier",
                "default_action": "format_preserving",
                "recommendations": {fw: FRAMEWORK_RECOMMENDATIONS.get(fw, "") for fw in fws},
                "confidence": 0.5,
            }

    return {
        "is_sensitive": False,
        "frameworks": [],
        "field_type": None,
        "default_action": None,
        "recommendations": {},
        "confidence": 0.0,
    }


def _domain_boost(base_frameworks: List[str], domain_frameworks: Set[str]) -> Set[str]:
    """Add domain-implied frameworks that don't conflict with the base."""
    # Only add GDPR/CCPA if they're in domain context (jurisdictional frameworks)
    extras = set()
    for fw in domain_frameworks:
        if fw in ("GDPR", "CCPA") and "PII" in base_frameworks:
            extras.add(fw)
        elif fw in ("HIPAA",) and any(f in base_frameworks for f in ("PII", "HIPAA")):
            extras.add(fw)
    return extras


def _detect_from_values(cleaned: List[str], domain_frameworks: Set[str]) -> Dict | None:
    sample = cleaned[:15]
    total = len(sample)
    counts = {k: 0 for k in ("email", "ssn", "phone", "ip", "cc", "iban", "passport")}

    for v in sample:
        if EMAIL_RE.match(v):           counts["email"] += 1
        if SSN_RE.match(v):             counts["ssn"] += 1
        if PHONE_RE.match(v) and sum(c.isdigit() for c in v) >= 9:
                                         counts["phone"] += 1
        if IP4_RE.match(v) or IP6_RE.match(v):
                                         counts["ip"] += 1
        if CC_RE.match(v) and _luhn(v): counts["cc"] += 1
        if IBAN_RE.match(v):            counts["iban"] += 1
        if PASSPORT_RE.match(v):        counts["passport"] += 1

    threshold = 0.6

    if counts["email"] / total > threshold:
        fws = list({"PII", "GDPR"} | (domain_frameworks & {"HIPAA", "FERPA"}))
        return _build_result(fws, "email_address", "fake_realistic", 0.92)

    if counts["ssn"] / total > threshold:
        return _build_result(["PII"], "social_security", "format_preserving", 0.97)

    if counts["cc"] / total > threshold:
        return _build_result(["PCI"], "card_number", "format_preserving", 0.99)

    if counts["iban"] / total > threshold:
        return _build_result(["PCI", "GDPR"], "bank_account", "format_preserving", 0.93)

    if counts["ip"] / total > threshold:
        fws = list({"PII", "GDPR"} | (domain_frameworks & {"HIPAA"}))
        return _build_result(fws, "ip_address", "mask", 0.88)

    if counts["passport"] / total > threshold:
        return _build_result(["PII", "GDPR"], "passport_number", "format_preserving", 0.82)

    if counts["phone"] / total > threshold:
        fws = list({"PII", "GDPR"} | (domain_frameworks & {"HIPAA"}))
        return _build_result(fws, "phone_number", "fake_realistic", 0.80)

    return None


def _build_result(frameworks: List[str], field_type: str, default_action: str, confidence: float) -> Dict:
    return {
        "is_sensitive": True,
        "frameworks": frameworks,
        "field_type": field_type,
        "default_action": default_action,
        "recommendations": {fw: FRAMEWORK_RECOMMENDATIONS.get(fw, "") for fw in frameworks},
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# LLM-based batch compliance detection
# ---------------------------------------------------------------------------

_COMPLIANCE_SYSTEM_PROMPT = """\
You are a regulatory compliance expert specialising in data-privacy frameworks:
PII, PCI, HIPAA, GDPR, CCPA, SOX, and FERPA.

Classify each database column supplied by the user.

Rules:
- Apply ALL frameworks that genuinely apply — a column may belong to several.
- Handle typos, synonyms, abbreviations, and domain-specific variants
  (e.g. "pt_id" → HIPAA patient identifier; "cc_num" → PCI card number).
- Use domain context (healthcare, payments, education …) to assign HIPAA / PCI /
  FERPA even when the column name alone is ambiguous.
- default_action MUST be one of:
    fake_realistic      – replace with synthetic realistic value
    format_preserving   – preserve format/length, change digits (card#, SSN, IBAN)
    mask                – replace with *** / range-bucketed value (IPs, salaries)
    redact              – remove entirely (CVV, biometrics, political opinion)
- Respond with ONLY valid JSON — no markdown, no code fences, no explanation.

Framework quick-reference:
  PII   → names, emails, phones, addresses, DOBs, SSNs, IPs, device IDs, demographics
  PCI   → card numbers, CVV/CVC, expiry dates, bank accounts, routing/IBAN, SWIFT
  HIPAA → patient IDs, MRNs, diagnoses, prescriptions, lab results, DOBs (medical),
           SSNs, dates-of-service, provider names/IDs
  GDPR  → any PII field for EU residents; national IDs, consent, IP addresses
  CCPA  → any PII field for California residents
  SOX   → salary, compensation, bonus, revenue, tax IDs, EINs, audit trails
  FERPA → student IDs, grades, GPA, transcripts, enrollment, financial-aid records

Response schema (one key per column name supplied):
{
  "<column_name>": {
    "is_sensitive": true,
    "frameworks": ["PII", "GDPR"],
    "field_type": "email_address",
    "default_action": "fake_realistic",
    "confidence": 0.95
  }
}
"""


def detect_compliance_batch_llm(
    columns: List[Dict],
    llm_provider,
    context_text: str = "",
    domain_frameworks: Optional[Set[str]] = None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Classify all columns in a single LLM call, with validation + retry.

    Parameters
    ----------
    columns        : list of {"name": str, "sample_values": [...]}
    llm_provider   : any LLMProvider instance (skipped automatically for DemoProvider)
    context_text   : free-form user description (for domain cues)
    domain_frameworks : frameworks already inferred from domain signals
    max_retries    : how many times to retry when the response is incomplete/invalid

    Returns
    -------
    {
        "results":  dict mapping column_name → compliance dict,
        "warning":  str | None  — set when retries exhausted or call failed,
        "attempts": int         — number of LLM calls made,
    }
    Caller falls back to detect_compliance() for any column absent from results["results"].
    """
    from services.llm_service import DemoProvider  # local import to avoid circular dep

    _empty = {"results": {}, "warning": None, "attempts": 0}

    if isinstance(llm_provider, DemoProvider) or not columns:
        return _empty

    domain_frameworks = domain_frameworks or set()

    # Whether this provider applies strict content filtering (e.g. Azure OpenAI).
    # When True, raw sample values from uploaded files are NEVER sent — they may
    # contain real PII/PCI data that would trigger content policy blocks.
    safe_samples = not getattr(llm_provider, "content_filter_strict", False)
    _valid_actions = {"fake_realistic", "format_preserving", "mask", "redact"}

    # ── Build column list text ────────────────────────────────────────────────
    def _col_lines(col_subset: List[Dict]) -> List[str]:
        lines = []
        for col in col_subset:
            name = col.get("name", "")
            if not name:
                continue
            sample_str = ""
            if safe_samples:
                samples = col.get("sample_values") or []
                clean = [str(v)[:60] for v in samples[:4] if v not in (None, "", "null", "NaN")]
                if clean:
                    sample_str = f"  [samples: {', '.join(repr(s) for s in clean)}]"
            lines.append(f"  {name}{sample_str}")
        return lines

    def _build_prompt(col_subset: List[Dict], missing: Optional[List[str]] = None) -> str:
        lines = _col_lines(col_subset)
        context_block = ""
        if context_text:
            context_block += f"\nUser description: {context_text[:600]}"
        if domain_frameworks:
            context_block += f"\nDomain frameworks already detected: {', '.join(sorted(domain_frameworks))}"
        if missing:
            context_block += (
                f"\n\nIMPORTANT: Your previous response was missing or invalid for these columns: "
                f"{', '.join(missing)}. You MUST include all of them in your response."
            )
        return (
            f"Classify these {len(lines)} columns:{context_block}\n\n"
            + "\n".join(lines)
            + "\n\nReturn a JSON object with one key per column name."
        )

    # ── Parse and normalise a raw LLM response ────────────────────────────────
    def _parse(raw: str) -> Optional[Dict]:
        try:
            text = (raw or "").strip()
            if text.startswith("```"):
                parts = text.split("```")
                text = parts[1] if len(parts) >= 2 else text
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _normalise_entry(name: str, entry: dict) -> Optional[Dict]:
        """Return a valid compliance dict, or None if the entry is unusable."""
        if not isinstance(entry, dict):
            return None
        raw_fws = entry.get("frameworks") or []
        if not isinstance(raw_fws, list):
            raw_fws = []
        valid_fws = [f for f in raw_fws if f in FRAMEWORK_RECOMMENDATIONS]
        boosted = set(valid_fws) | _domain_boost(valid_fws, domain_frameworks)
        final_fws = sorted(boosted)
        is_sensitive = bool(entry.get("is_sensitive", False)) and bool(final_fws)
        action = entry.get("default_action")
        if action not in _valid_actions:
            action = "fake_realistic" if is_sensitive else None
        confidence = float(entry.get("confidence", 0.8))
        field_type = entry.get("field_type") or None
        return {
            "is_sensitive": is_sensitive,
            "frameworks": final_fws,
            "field_type": field_type,
            "default_action": action,
            "recommendations": {fw: FRAMEWORK_RECOMMENDATIONS.get(fw, "") for fw in final_fws},
            "confidence": confidence,
        }

    # ── Retry loop ────────────────────────────────────────────────────────────
    valid_names = [c["name"] for c in columns if c.get("name")]
    results: Dict[str, Dict] = {}
    missing = list(valid_names)   # start: all columns are "missing"
    warning: Optional[str] = None
    attempts = 0

    for attempt in range(1, max_retries + 1):
        attempts = attempt
        remaining_cols = [c for c in columns if c.get("name") in missing]

        prompt = _build_prompt(
            remaining_cols,
            missing=(missing if attempt > 1 else None),
        )
        try:
            raw = llm_provider.generate(prompt, system_prompt=_COMPLIANCE_SYSTEM_PROMPT)
        except Exception:
            warning = (
                "LLM compliance detection failed (network/API error). "
                "Built-in rules were used instead."
            )
            break

        parsed = _parse(raw)

        # If the provider returned an error JSON from us (e.g. bad Azure config)
        if parsed and "error" in parsed and len(parsed) == 1:
            warning = (
                f"LLM compliance detection error: {parsed['error']} "
                "Built-in rules were used instead."
            )
            break

        if not parsed:
            # Invalid JSON — will retry
            continue

        # Absorb any newly classified columns
        for name in list(missing):
            entry = parsed.get(name)
            norm = _normalise_entry(name, entry) if entry else None
            if norm is not None:
                results[name] = norm
                missing.remove(name)

        if not missing:
            break   # all columns accounted for

    # If columns remain unclassified after all retries, emit a warning
    if missing and not warning:
        warning = (
            f"LLM compliance detection was incomplete after {attempts} attempt(s) — "
            f"{len(missing)} column(s) classified using built-in rules instead: "
            f"{', '.join(missing[:10])}{'…' if len(missing) > 10 else ''}."
        )

    return {"results": results, "warning": warning, "attempts": attempts}


# ---------------------------------------------------------------------------
# Backward-compatible shim so existing code that imports detect_pii still works
# ---------------------------------------------------------------------------
def detect_pii(column_name: str, sample_values: List[Any]) -> Dict[str, Any]:
    """Legacy shim — wraps detect_compliance into the old detect_pii response shape."""
    result = detect_compliance(column_name, sample_values)
    primary_fw = result["frameworks"][0] if result["frameworks"] else None
    return {
        "is_pii": result["is_sensitive"],
        "category": primary_fw,
        "frameworks": result["frameworks"],
        "pii_type": result.get("field_type"),
        "default_action": result.get("default_action"),
        "recommendations": result.get("recommendations", {}),
        "confidence": result["confidence"],
    }
