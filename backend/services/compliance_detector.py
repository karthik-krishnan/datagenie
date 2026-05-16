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
    (r"\bfinancial\b|banking|bank account|iban|routing number|wire transfer|glba|gramm.leach|loan|mortgage|credit score|kyc|aml",
     ["PCI", "SOX", "GLBA"]),
]


def _keyword_domain_frameworks(context_text: str) -> Set[str]:
    """Return set of frameworks implied by the free-form context text (keyword-only)."""
    frameworks: Set[str] = set()
    if not context_text:
        return frameworks
    text = context_text.lower()
    for pattern, fws in DOMAIN_SIGNALS:
        if re.search(pattern, text, re.I):
            frameworks.update(fws)
    return frameworks


from prompts.compliance_domain import SYSTEM as _DOMAIN_FRAMEWORK_SYSTEM, TEMPLATE as _DOMAIN_FRAMEWORK_PROMPT


def detect_domain_frameworks(
    context_text: str,
    llm_provider=None,
) -> Set[str]:
    """Return set of frameworks implied by context. Uses LLM when available.

    For demo/local providers (no external API calls), uses keyword matching directly.
    If the LLM call fails, the exception is raised directly — no silent fallback.
    """
    if not context_text:
        return set()
    # Skip LLM call for providers that don't make external API calls — use keyword
    # matching directly. Same result, no overhead (and no spurious delay in demo mode).
    if llm_provider is None or not getattr(llm_provider, "sends_data_to_external_api", True):
        return _keyword_domain_frameworks(context_text)
    import re as _re, json as _json
    prompt = _DOMAIN_FRAMEWORK_PROMPT.format(context=context_text.strip()[:2000])
    raw = llm_provider.generate(prompt, _DOMAIN_FRAMEWORK_SYSTEM)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = _re.sub(r"^```(?:json)?\s*", "", raw)
        raw = _re.sub(r"\s*```$", "", raw)
    result = _json.loads(raw)
    return set(result.get("frameworks", []))


# ---------------------------------------------------------------------------
# Field catalog — comprehensive mapping of column name keywords → compliance
# Format: keyword → {frameworks, field_type, default_action, recommendation}
#
# default_action values: fake_realistic | format_preserving | mask | redact
# ---------------------------------------------------------------------------
FIELD_CATALOG: Dict[str, Dict] = {

    # ══════════════════════════════════════════════════════════════════════
    # PII — general personally identifiable information
    # ══════════════════════════════════════════════════════════════════════
    "first_name":           {"frameworks": ["PII", "GDPR"],              "field_type": "person_name",          "default_action": "fake_realistic"},
    "last_name":            {"frameworks": ["PII", "GDPR"],              "field_type": "person_name",          "default_action": "fake_realistic"},
    "full_name":            {"frameworks": ["PII", "GDPR"],              "field_type": "person_name",          "default_action": "fake_realistic"},
    "name":                 {"frameworks": ["PII", "GDPR"],              "field_type": "person_name",          "default_action": "fake_realistic"},
    "email":                {"frameworks": ["PII", "GDPR", "CCPA"],      "field_type": "email_address",        "default_action": "fake_realistic"},
    "email_address":        {"frameworks": ["PII", "GDPR", "CCPA"],      "field_type": "email_address",        "default_action": "fake_realistic"},
    "phone":                {"frameworks": ["PII", "GDPR", "CCPA"],      "field_type": "phone_number",         "default_action": "fake_realistic"},
    "phone_number":         {"frameworks": ["PII", "GDPR", "CCPA"],      "field_type": "phone_number",         "default_action": "fake_realistic"},
    "mobile":               {"frameworks": ["PII", "GDPR", "CCPA"],      "field_type": "phone_number",         "default_action": "fake_realistic"},
    "cell":                 {"frameworks": ["PII", "GDPR"],              "field_type": "phone_number",         "default_action": "fake_realistic"},
    # HIPAA PHI #5 — fax numbers
    "fax":                  {"frameworks": ["PII", "HIPAA"],             "field_type": "fax_number",           "default_action": "fake_realistic"},
    "fax_number":           {"frameworks": ["PII", "HIPAA"],             "field_type": "fax_number",           "default_action": "fake_realistic"},
    # Postal address (HIPAA PHI #2 — geographic sub-state)
    "address":              {"frameworks": ["PII", "GDPR", "HIPAA", "CCPA"], "field_type": "postal_address",   "default_action": "fake_realistic"},
    "street":               {"frameworks": ["PII", "GDPR", "HIPAA"],    "field_type": "postal_address",       "default_action": "fake_realistic"},
    "street_address":       {"frameworks": ["PII", "GDPR", "HIPAA"],    "field_type": "postal_address",       "default_action": "fake_realistic"},
    "city":                 {"frameworks": ["PII", "GDPR"],             "field_type": "city",                 "default_action": "fake_realistic"},
    "state":                {"frameworks": ["PII"],                      "field_type": "state",                "default_action": "fake_realistic"},
    "region":               {"frameworks": ["PII"],                      "field_type": "state",                "default_action": "fake_realistic"},
    "country":              {"frameworks": ["PII", "GDPR"],             "field_type": "country",              "default_action": "fake_realistic"},
    # HIPAA PHI #2 — zip/postal code (3-digit prefix is PHI; full zip more so)
    "zip":                  {"frameworks": ["PII", "HIPAA", "GDPR"],    "field_type": "zip_code",             "default_action": "mask"},
    "zip_code":             {"frameworks": ["PII", "HIPAA", "GDPR"],    "field_type": "zip_code",             "default_action": "mask"},
    "postal_code":          {"frameworks": ["PII", "HIPAA", "GDPR"],    "field_type": "zip_code",             "default_action": "mask"},
    "postcode":             {"frameworks": ["PII", "HIPAA", "GDPR"],    "field_type": "zip_code",             "default_action": "mask"},
    "county":               {"frameworks": ["PII", "HIPAA"],            "field_type": "geographic_unit",      "default_action": "mask"},
    "district":             {"frameworks": ["PII", "HIPAA"],            "field_type": "geographic_unit",      "default_action": "mask"},
    # National identifiers
    "ssn":                  {"frameworks": ["PII", "HIPAA"],            "field_type": "social_security",      "default_action": "format_preserving"},
    "social_security":      {"frameworks": ["PII", "HIPAA"],            "field_type": "social_security",      "default_action": "format_preserving"},
    "national_id":          {"frameworks": ["PII", "GDPR"],             "field_type": "national_identifier",  "default_action": "format_preserving"},
    "national_insurance":   {"frameworks": ["PII", "GDPR"],             "field_type": "national_identifier",  "default_action": "format_preserving"},
    "nino":                 {"frameworks": ["PII", "GDPR"],             "field_type": "national_identifier",  "default_action": "format_preserving"},
    # Dates (HIPAA PHI #3 — all dates except year)
    "dob":                  {"frameworks": ["PII", "GDPR", "HIPAA"],    "field_type": "date_of_birth",        "default_action": "fake_realistic"},
    "date_of_birth":        {"frameworks": ["PII", "GDPR", "HIPAA"],    "field_type": "date_of_birth",        "default_action": "fake_realistic"},
    "birth_date":           {"frameworks": ["PII", "GDPR", "HIPAA"],    "field_type": "date_of_birth",        "default_action": "fake_realistic"},
    "birthday":             {"frameworks": ["PII", "GDPR", "HIPAA"],    "field_type": "date_of_birth",        "default_action": "fake_realistic"},
    "birth_year":           {"frameworks": ["PII", "GDPR"],             "field_type": "date_of_birth",        "default_action": "fake_realistic"},
    "age":                  {"frameworks": ["PII", "GDPR"],             "field_type": "age",                  "default_action": "fake_realistic"},
    # Travel documents (HIPAA PHI #11 — certificate/license numbers)
    "passport":             {"frameworks": ["PII", "GDPR", "HIPAA"],    "field_type": "passport_number",      "default_action": "format_preserving"},
    "passport_number":      {"frameworks": ["PII", "GDPR", "HIPAA"],    "field_type": "passport_number",      "default_action": "format_preserving"},
    "driver_license":       {"frameworks": ["PII", "HIPAA"],            "field_type": "drivers_license",      "default_action": "format_preserving"},
    "drivers_license":      {"frameworks": ["PII", "HIPAA"],            "field_type": "drivers_license",      "default_action": "format_preserving"},
    "license_number":       {"frameworks": ["PII", "HIPAA"],            "field_type": "license_identifier",   "default_action": "format_preserving"},
    "certificate_number":   {"frameworks": ["PII", "HIPAA"],            "field_type": "certificate_number",   "default_action": "format_preserving"},
    "certificate_id":       {"frameworks": ["PII", "HIPAA"],            "field_type": "certificate_number",   "default_action": "format_preserving"},
    # Vehicle identifiers (HIPAA PHI #12 — VINs and serial numbers)
    "vin":                  {"frameworks": ["PII", "HIPAA"],            "field_type": "vehicle_identifier",   "default_action": "format_preserving"},
    "vehicle_id":           {"frameworks": ["PII", "HIPAA"],            "field_type": "vehicle_identifier",   "default_action": "format_preserving"},
    "plate_number":         {"frameworks": ["PII", "HIPAA"],            "field_type": "vehicle_identifier",   "default_action": "format_preserving"},
    "license_plate":        {"frameworks": ["PII", "HIPAA"],            "field_type": "vehicle_identifier",   "default_action": "format_preserving"},
    # Network/device identifiers (HIPAA PHI #13-15 — device IDs, URLs, IPs)
    "ip_address":           {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "ip_address",           "default_action": "mask"},
    "ip":                   {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "ip_address",           "default_action": "mask"},
    "device_id":            {"frameworks": ["PII", "GDPR", "HIPAA", "CCPA"], "field_type": "device_identifier", "default_action": "mask"},
    "mac_address":          {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "device_identifier",    "default_action": "mask"},
    "imei":                 {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "device_identifier",    "default_action": "mask"},
    "url":                  {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "web_url",              "default_action": "mask"},
    "website":              {"frameworks": ["PII", "GDPR"],             "field_type": "web_url",              "default_action": "mask"},
    "web_url":              {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "web_url",              "default_action": "mask"},
    "profile_url":          {"frameworks": ["PII", "GDPR"],             "field_type": "web_url",              "default_action": "mask"},
    "cookie":               {"frameworks": ["GDPR", "CCPA"],           "field_type": "cookie_id",            "default_action": "mask"},
    "session_id":           {"frameworks": ["GDPR"],                    "field_type": "session_identifier",   "default_action": "mask"},
    # Photos (HIPAA PHI #17 — full-face photos)
    "photo":                {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "photo",                "default_action": "redact"},
    "avatar":               {"frameworks": ["PII", "GDPR"],             "field_type": "photo",                "default_action": "redact"},
    "profile_photo":        {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "photo",                "default_action": "redact"},
    "profile_image":        {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "photo",                "default_action": "redact"},
    "face_scan":            {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "biometric_data",       "default_action": "redact"},
    # Location
    "geolocation":          {"frameworks": ["PII", "GDPR", "CCPA"],    "field_type": "location_data",        "default_action": "mask"},
    "latitude":             {"frameworks": ["PII", "GDPR"],             "field_type": "location_data",        "default_action": "mask"},
    "longitude":            {"frameworks": ["PII", "GDPR"],             "field_type": "location_data",        "default_action": "mask"},
    # User identity
    "username":             {"frameworks": ["PII"],                     "field_type": "user_identifier",      "default_action": "fake_realistic"},
    "user_id":              {"frameworks": ["PII", "GDPR"],             "field_type": "user_identifier",      "default_action": "format_preserving"},
    "employee_id":          {"frameworks": ["PII", "SOX"],              "field_type": "employee_identifier",  "default_action": "format_preserving"},
    # Demographics
    "gender":               {"frameworks": ["PII", "GDPR"],             "field_type": "demographic",          "default_action": "fake_realistic"},
    "sex":                  {"frameworks": ["PII", "GDPR"],             "field_type": "demographic",          "default_action": "fake_realistic"},
    # GDPR Article 9 Special Categories — require explicit consent and carry highest protection
    "race":                 {"frameworks": ["PII", "GDPR"],             "field_type": "special_category",     "default_action": "redact"},
    "ethnicity":            {"frameworks": ["PII", "GDPR"],             "field_type": "special_category",     "default_action": "redact"},
    "ethnic_origin":        {"frameworks": ["PII", "GDPR"],             "field_type": "special_category",     "default_action": "redact"},
    "religion":             {"frameworks": ["PII", "GDPR"],             "field_type": "special_category",     "default_action": "redact"},
    "religious_belief":     {"frameworks": ["PII", "GDPR"],             "field_type": "special_category",     "default_action": "redact"},
    "political":            {"frameworks": ["GDPR"],                    "field_type": "special_category",     "default_action": "redact"},
    "political_opinion":    {"frameworks": ["GDPR"],                    "field_type": "special_category",     "default_action": "redact"},
    "political_affiliation":{"frameworks": ["GDPR"],                    "field_type": "special_category",     "default_action": "redact"},
    "political_party":      {"frameworks": ["GDPR"],                    "field_type": "special_category",     "default_action": "redact"},
    "trade_union":          {"frameworks": ["GDPR"],                    "field_type": "special_category",     "default_action": "redact"},
    "union_membership":     {"frameworks": ["GDPR"],                    "field_type": "special_category",     "default_action": "redact"},
    "sexual":               {"frameworks": ["PII", "GDPR"],             "field_type": "special_category",     "default_action": "redact"},
    "sexual_orientation":   {"frameworks": ["PII", "GDPR"],             "field_type": "special_category",     "default_action": "redact"},
    # Biometrics (GDPR Art.9 + HIPAA PHI #16)
    "biometric":            {"frameworks": ["PII", "GDPR", "HIPAA", "CCPA"], "field_type": "biometric_data", "default_action": "redact"},
    "fingerprint":          {"frameworks": ["PII", "GDPR", "HIPAA", "CCPA"], "field_type": "biometric_data", "default_action": "redact"},
    "retina":               {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "biometric_data",       "default_action": "redact"},
    "iris":                 {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "biometric_data",       "default_action": "redact"},
    "voice_print":          {"frameworks": ["PII", "GDPR", "HIPAA"],   "field_type": "biometric_data",       "default_action": "redact"},
    # Genetic data (GDPR Art.9)
    "genetic_data":         {"frameworks": ["PII", "GDPR"],             "field_type": "genetic_data",         "default_action": "redact"},
    "genome":               {"frameworks": ["PII", "GDPR"],             "field_type": "genetic_data",         "default_action": "redact"},
    "dna":                  {"frameworks": ["PII", "GDPR"],             "field_type": "genetic_data",         "default_action": "redact"},
    "snp":                  {"frameworks": ["PII", "GDPR"],             "field_type": "genetic_data",         "default_action": "redact"},

    # ══════════════════════════════════════════════════════════════════════
    # PCI DSS — cardholder data (CHD) and sensitive authentication data (SAD)
    # CHD: PAN, cardholder name, expiry, service code
    # SAD (must never be stored post-auth): CVV, PIN, full magnetic stripe
    # ══════════════════════════════════════════════════════════════════════
    "credit_card":          {"frameworks": ["PCI"],                     "field_type": "card_number",          "default_action": "format_preserving"},
    "card_number":          {"frameworks": ["PCI"],                     "field_type": "card_number",          "default_action": "format_preserving"},
    "cc_number":            {"frameworks": ["PCI"],                     "field_type": "card_number",          "default_action": "format_preserving"},
    "pan":                  {"frameworks": ["PCI"],                     "field_type": "card_number",          "default_action": "format_preserving"},
    "cardholder_name":      {"frameworks": ["PCI", "PII"],              "field_type": "cardholder_name",      "default_action": "fake_realistic"},
    "card_expiry":          {"frameworks": ["PCI"],                     "field_type": "card_expiry",          "default_action": "fake_realistic"},
    "expiry_date":          {"frameworks": ["PCI"],                     "field_type": "card_expiry",          "default_action": "fake_realistic"},
    "expiration_date":      {"frameworks": ["PCI"],                     "field_type": "card_expiry",          "default_action": "fake_realistic"},
    "service_code":         {"frameworks": ["PCI"],                     "field_type": "card_service_code",    "default_action": "redact"},
    # SAD — must be redacted (never stored post-auth per PCI-DSS Req.3.2)
    "cvv":                  {"frameworks": ["PCI"],                     "field_type": "card_cvv",             "default_action": "redact"},
    "cvc":                  {"frameworks": ["PCI"],                     "field_type": "card_cvv",             "default_action": "redact"},
    "csc":                  {"frameworks": ["PCI"],                     "field_type": "card_cvv",             "default_action": "redact"},
    "pin":                  {"frameworks": ["PCI"],                     "field_type": "pin_block",            "default_action": "redact"},
    "pin_block":            {"frameworks": ["PCI"],                     "field_type": "pin_block",            "default_action": "redact"},
    "track_data":           {"frameworks": ["PCI"],                     "field_type": "magnetic_stripe",      "default_action": "redact"},
    "magnetic_stripe":      {"frameworks": ["PCI"],                     "field_type": "magnetic_stripe",      "default_action": "redact"},
    # Bank / payment identifiers
    "account_number":       {"frameworks": ["PCI", "SOX", "GLBA"],     "field_type": "account_number",       "default_action": "format_preserving"},
    "bank_account":         {"frameworks": ["PCI", "GLBA"],             "field_type": "bank_account",         "default_action": "format_preserving"},
    "routing_number":       {"frameworks": ["PCI", "GLBA"],             "field_type": "routing_number",       "default_action": "format_preserving"},
    "iban":                 {"frameworks": ["PCI", "GDPR", "GLBA"],    "field_type": "bank_account",         "default_action": "format_preserving"},
    "swift":                {"frameworks": ["PCI", "GLBA"],             "field_type": "swift_bic",            "default_action": "format_preserving"},
    "sort_code":            {"frameworks": ["PCI", "GLBA"],             "field_type": "sort_code",            "default_action": "format_preserving"},
    "bsb":                  {"frameworks": ["PCI", "GLBA"],             "field_type": "sort_code",            "default_action": "format_preserving"},

    # ══════════════════════════════════════════════════════════════════════
    # GLBA — Gramm-Leach-Bliley: covers non-public personal financial info
    # ══════════════════════════════════════════════════════════════════════
    "credit_score":         {"frameworks": ["GLBA", "PII"],             "field_type": "credit_score",         "default_action": "fake_realistic"},
    "credit_rating":        {"frameworks": ["GLBA", "PII"],             "field_type": "credit_score",         "default_action": "fake_realistic"},
    "fico_score":           {"frameworks": ["GLBA", "PII"],             "field_type": "credit_score",         "default_action": "fake_realistic"},
    "loan_id":              {"frameworks": ["GLBA", "SOX"],             "field_type": "loan_identifier",      "default_action": "format_preserving"},
    "loan_number":          {"frameworks": ["GLBA", "SOX"],             "field_type": "loan_identifier",      "default_action": "format_preserving"},
    "principal_amount":     {"frameworks": ["SOX", "GLBA"],             "field_type": "loan_amount",          "default_action": "fake_realistic"},
    "loan_amount":          {"frameworks": ["SOX", "GLBA"],             "field_type": "loan_amount",          "default_action": "fake_realistic"},
    "outstanding_balance":  {"frameworks": ["SOX", "GLBA"],             "field_type": "loan_balance",         "default_action": "fake_realistic"},
    "annual_income":        {"frameworks": ["GLBA", "PII"],             "field_type": "income",               "default_action": "mask"},
    "gross_income":         {"frameworks": ["GLBA", "PII"],             "field_type": "income",               "default_action": "mask"},
    "net_worth":            {"frameworks": ["GLBA", "PII"],             "field_type": "income",               "default_action": "mask"},
    "investment_account":   {"frameworks": ["GLBA"],                    "field_type": "investment_data",      "default_action": "format_preserving"},
    "brokerage_account":    {"frameworks": ["GLBA"],                    "field_type": "investment_data",      "default_action": "format_preserving"},
    "kyc_status":           {"frameworks": ["GLBA", "PII"],             "field_type": "kyc_status",           "default_action": "fake_realistic"},
    "risk_rating":          {"frameworks": ["GLBA", "SOX"],             "field_type": "risk_rating",          "default_action": "fake_realistic"},
    "aml_flag":             {"frameworks": ["GLBA", "SOX"],             "field_type": "aml_data",             "default_action": "fake_realistic"},

    # ══════════════════════════════════════════════════════════════════════
    # HIPAA — 18 PHI Safe Harbor identifiers (45 CFR §164.514(b))
    # ══════════════════════════════════════════════════════════════════════
    "diagnosis":            {"frameworks": ["HIPAA"],                   "field_type": "medical_diagnosis",    "default_action": "fake_realistic"},
    "icd":                  {"frameworks": ["HIPAA"],                   "field_type": "diagnosis_code",       "default_action": "fake_realistic"},
    "icd_code":             {"frameworks": ["HIPAA"],                   "field_type": "diagnosis_code",       "default_action": "fake_realistic"},
    "mrn":                  {"frameworks": ["HIPAA"],                   "field_type": "medical_record_no",    "default_action": "format_preserving"},
    "medical_record":       {"frameworks": ["HIPAA"],                   "field_type": "medical_record_no",    "default_action": "format_preserving"},
    "medical_record_number":{"frameworks": ["HIPAA"],                   "field_type": "medical_record_no",    "default_action": "format_preserving"},
    "npi":                  {"frameworks": ["HIPAA"],                   "field_type": "provider_id",          "default_action": "fake_realistic"},
    "provider_id":          {"frameworks": ["HIPAA"],                   "field_type": "provider_id",          "default_action": "format_preserving"},
    "patient_id":           {"frameworks": ["HIPAA", "PII"],            "field_type": "patient_identifier",   "default_action": "format_preserving"},
    "patient_number":       {"frameworks": ["HIPAA", "PII"],            "field_type": "patient_identifier",   "default_action": "format_preserving"},
    # Health plan beneficiary numbers (PHI #9)
    "health_plan":          {"frameworks": ["HIPAA"],                   "field_type": "health_plan_number",   "default_action": "fake_realistic"},
    "health_plan_id":       {"frameworks": ["HIPAA"],                   "field_type": "health_plan_number",   "default_action": "format_preserving"},
    "beneficiary_id":       {"frameworks": ["HIPAA", "PII"],            "field_type": "health_plan_number",   "default_action": "format_preserving"},
    "plan_id":              {"frameworks": ["HIPAA"],                   "field_type": "health_plan_number",   "default_action": "format_preserving"},
    "insurance_id":         {"frameworks": ["HIPAA", "PII"],            "field_type": "insurance_number",     "default_action": "format_preserving"},
    "insurance_number":     {"frameworks": ["HIPAA", "PII"],            "field_type": "insurance_number",     "default_action": "format_preserving"},
    "member_id":            {"frameworks": ["HIPAA", "PII"],            "field_type": "insurance_member_id",  "default_action": "format_preserving"},
    "group_number":         {"frameworks": ["HIPAA"],                   "field_type": "health_plan_number",   "default_action": "format_preserving"},
    # Clinical data
    "prescription":         {"frameworks": ["HIPAA"],                   "field_type": "prescription",         "default_action": "fake_realistic"},
    "medication":           {"frameworks": ["HIPAA"],                   "field_type": "medication",           "default_action": "fake_realistic"},
    "drug":                 {"frameworks": ["HIPAA"],                   "field_type": "medication",           "default_action": "fake_realistic"},
    "drug_name":            {"frameworks": ["HIPAA"],                   "field_type": "medication",           "default_action": "fake_realistic"},
    "treatment":            {"frameworks": ["HIPAA"],                   "field_type": "treatment_info",       "default_action": "fake_realistic"},
    "procedure":            {"frameworks": ["HIPAA"],                   "field_type": "medical_procedure",    "default_action": "fake_realistic"},
    "procedure_code":       {"frameworks": ["HIPAA"],                   "field_type": "medical_procedure",    "default_action": "fake_realistic"},
    "cpt_code":             {"frameworks": ["HIPAA"],                   "field_type": "medical_procedure",    "default_action": "fake_realistic"},
    "lab_result":           {"frameworks": ["HIPAA"],                   "field_type": "lab_result",           "default_action": "fake_realistic"},
    "test_result":          {"frameworks": ["HIPAA"],                   "field_type": "lab_result",           "default_action": "fake_realistic"},
    "vital_sign":           {"frameworks": ["HIPAA"],                   "field_type": "clinical_observation", "default_action": "fake_realistic"},
    "blood_pressure":       {"frameworks": ["HIPAA"],                   "field_type": "clinical_observation", "default_action": "fake_realistic"},
    "dea_number":           {"frameworks": ["HIPAA"],                   "field_type": "dea_number",           "default_action": "format_preserving"},
    # Service/clinical dates (HIPAA PHI #3 — all dates except year)
    "admission_date":       {"frameworks": ["HIPAA"],                   "field_type": "service_date",         "default_action": "fake_realistic"},
    "discharge_date":       {"frameworks": ["HIPAA"],                   "field_type": "service_date",         "default_action": "fake_realistic"},
    "service_date":         {"frameworks": ["HIPAA"],                   "field_type": "service_date",         "default_action": "fake_realistic"},
    "death_date":           {"frameworks": ["HIPAA"],                   "field_type": "service_date",         "default_action": "fake_realistic"},
    # Provider identifiers
    "provider_name":        {"frameworks": ["HIPAA"],                   "field_type": "provider_name",        "default_action": "fake_realistic"},
    "attending":            {"frameworks": ["HIPAA"],                   "field_type": "provider_name",        "default_action": "fake_realistic"},
    "attending_physician":  {"frameworks": ["HIPAA"],                   "field_type": "provider_name",        "default_action": "fake_realistic"},
    "ordering_provider":    {"frameworks": ["HIPAA"],                   "field_type": "provider_name",        "default_action": "fake_realistic"},
    # Health conditions (GDPR Art.9 special category when outside US)
    "health_condition":     {"frameworks": ["HIPAA", "GDPR"],          "field_type": "health_data",          "default_action": "fake_realistic"},
    "medical_history":      {"frameworks": ["HIPAA", "GDPR"],          "field_type": "health_data",          "default_action": "redact"},
    "allergy":              {"frameworks": ["HIPAA", "GDPR"],          "field_type": "health_data",          "default_action": "fake_realistic"},
    "disability":           {"frameworks": ["HIPAA", "GDPR"],          "field_type": "health_data",          "default_action": "redact"},
    "mental_health":        {"frameworks": ["HIPAA", "GDPR"],          "field_type": "health_data",          "default_action": "redact"},

    # ══════════════════════════════════════════════════════════════════════
    # SOX — Sarbanes-Oxley: financial records and executive compensation
    # ══════════════════════════════════════════════════════════════════════
    "salary":               {"frameworks": ["SOX", "PII"],              "field_type": "compensation",         "default_action": "mask"},
    "compensation":         {"frameworks": ["SOX", "PII"],              "field_type": "compensation",         "default_action": "mask"},
    "bonus":                {"frameworks": ["SOX", "PII"],              "field_type": "compensation",         "default_action": "mask"},
    "wage":                 {"frameworks": ["SOX", "PII"],              "field_type": "compensation",         "default_action": "mask"},
    "hourly_rate":          {"frameworks": ["SOX", "PII"],              "field_type": "compensation",         "default_action": "mask"},
    "stock_option":         {"frameworks": ["SOX"],                     "field_type": "equity_data",          "default_action": "mask"},
    "equity_grant":         {"frameworks": ["SOX"],                     "field_type": "equity_data",          "default_action": "mask"},
    "revenue":              {"frameworks": ["SOX"],                     "field_type": "financial_data",       "default_action": "mask"},
    "earnings":             {"frameworks": ["SOX"],                     "field_type": "financial_data",       "default_action": "mask"},
    "net_income":           {"frameworks": ["SOX"],                     "field_type": "financial_data",       "default_action": "mask"},
    "tax_id":               {"frameworks": ["SOX", "PII"],              "field_type": "tax_identifier",       "default_action": "format_preserving"},
    "ein":                  {"frameworks": ["SOX"],                     "field_type": "employer_id",          "default_action": "format_preserving"},
    "tin":                  {"frameworks": ["SOX", "PII"],              "field_type": "taxpayer_id",          "default_action": "format_preserving"},
    "vat_number":           {"frameworks": ["SOX", "GDPR"],             "field_type": "tax_identifier",       "default_action": "format_preserving"},
    "audit_log":            {"frameworks": ["SOX"],                     "field_type": "audit_trail",          "default_action": "fake_realistic"},
    "audit_trail":          {"frameworks": ["SOX"],                     "field_type": "audit_trail",          "default_action": "fake_realistic"},
    "financial_statement":  {"frameworks": ["SOX"],                     "field_type": "financial_data",       "default_action": "mask"},
    "internal_control":     {"frameworks": ["SOX"],                     "field_type": "audit_trail",          "default_action": "fake_realistic"},

    # ══════════════════════════════════════════════════════════════════════
    # FERPA — educational records (20 U.S.C. § 1232g)
    # ══════════════════════════════════════════════════════════════════════
    "student_id":           {"frameworks": ["FERPA", "PII"],            "field_type": "student_identifier",   "default_action": "format_preserving"},
    "student_number":       {"frameworks": ["FERPA", "PII"],            "field_type": "student_identifier",   "default_action": "format_preserving"},
    "gpa":                  {"frameworks": ["FERPA"],                   "field_type": "academic_record",      "default_action": "fake_realistic"},
    "grade":                {"frameworks": ["FERPA"],                   "field_type": "academic_record",      "default_action": "fake_realistic"},
    "grade_point":          {"frameworks": ["FERPA"],                   "field_type": "academic_record",      "default_action": "fake_realistic"},
    "transcript":           {"frameworks": ["FERPA"],                   "field_type": "academic_record",      "default_action": "fake_realistic"},
    "enrollment":           {"frameworks": ["FERPA"],                   "field_type": "enrollment_info",      "default_action": "fake_realistic"},
    "enrollment_status":    {"frameworks": ["FERPA"],                   "field_type": "enrollment_info",      "default_action": "fake_realistic"},
    "course":               {"frameworks": ["FERPA"],                   "field_type": "course_info",          "default_action": "fake_realistic"},
    "course_id":            {"frameworks": ["FERPA"],                   "field_type": "course_info",          "default_action": "fake_realistic"},
    "academic":             {"frameworks": ["FERPA"],                   "field_type": "academic_record",      "default_action": "fake_realistic"},
    "financial_aid":        {"frameworks": ["FERPA", "SOX"],            "field_type": "financial_aid",        "default_action": "mask"},
    "scholarship":          {"frameworks": ["FERPA", "SOX"],            "field_type": "financial_aid",        "default_action": "mask"},
    "discipline_record":    {"frameworks": ["FERPA"],                   "field_type": "discipline_record",    "default_action": "redact"},
    "disciplinary":         {"frameworks": ["FERPA"],                   "field_type": "discipline_record",    "default_action": "redact"},
    "special_education":    {"frameworks": ["FERPA", "HIPAA"],         "field_type": "special_ed_record",    "default_action": "redact"},
    "iep":                  {"frameworks": ["FERPA", "HIPAA"],         "field_type": "special_ed_record",    "default_action": "redact"},
}

# Per-framework default recommendation text shown to users
FRAMEWORK_RECOMMENDATIONS: Dict[str, str] = {
    "PII":   "Generate realistic but completely synthetic values — no real personal data",
    "PCI":   "Use format-valid non-live values (Luhn-valid card numbers, valid IBANs) — never real CHD/SAD",
    "HIPAA": "Apply HIPAA Safe Harbor de-identification (45 CFR §164.514): replace all 18 PHI identifiers with synthetic equivalents",
    "GDPR":  "Pseudonymize or anonymize — output must not be re-linkable to an EU/EEA data subject; redact Article 9 special categories",
    "CCPA":  "Anonymize for California consumer data — support right-to-delete patterns",
    "SOX":   "Use masked or range-bucketed financial values; preserve referential integrity for audit trails",
    "FERPA": "Replace with synthetic student identifiers; preserve grade distribution patterns without linking to real students",
    "GLBA":  "Protect non-public personal financial information — use synthetic account numbers, masked income figures, fake credit scores",
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

from prompts.compliance_batch import SYSTEM as _COMPLIANCE_SYSTEM_PROMPT


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
    If the LLM call fails (network/API error), the exception is raised directly.
    """
    _empty = {"results": {}, "warning": None, "attempts": 0}

    if not columns:
        return _empty

    # Demo/local providers don't make external LLM calls — skip the batch loop
    # entirely and let the caller fall back to catalog-based detect_compliance().
    # No warning needed: built-in rules are the intended behaviour in this mode.
    if not getattr(llm_provider, "sends_data_to_external_api", True):
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
        raw = llm_provider.generate(prompt, system_prompt=_COMPLIANCE_SYSTEM_PROMPT)

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

    # ── Cross-check: validate LLM results against the field catalog ────────────
    # For columns the LLM classified as NOT sensitive but the catalog definitively
    # knows ARE sensitive, do one focused re-batch with a stronger prompt.
    # If the re-batch still disagrees, we fall back to the catalog result — the
    # catalog was purpose-built for these known-sensitive field names.
    suspect_cols = [
        col for col in columns
        if col.get("name") in results
        and not results[col["name"]].get("is_sensitive")
        and detect_compliance(col["name"], [], domain_frameworks).get("is_sensitive")
    ]

    if suspect_cols:
        suspect_names = [c["name"] for c in suspect_cols]
        retry_prompt = (
            _build_prompt(suspect_cols)
            + (
                "\n\nIMPORTANT: The following columns are known to be sensitive (PII/PCI/HIPAA/etc.) "
                "based on their names. Your previous classification marked them as NOT sensitive, "
                "which appears incorrect. Please reconsider carefully: "
                + ", ".join(suspect_names)
            )
        )
        try:
            raw_xcheck = llm_provider.generate(retry_prompt, system_prompt=_COMPLIANCE_SYSTEM_PROMPT)
            parsed_xcheck = _parse(raw_xcheck)
            if parsed_xcheck:
                for name in suspect_names:
                    entry = parsed_xcheck.get(name)
                    norm = _normalise_entry(name, entry) if entry else None
                    if norm is not None and norm.get("is_sensitive"):
                        # LLM now agrees — use updated result
                        results[name] = norm
                    else:
                        # LLM still disagrees — trust the catalog
                        results[name] = detect_compliance(name, [], domain_frameworks)
            else:
                # Unparseable response — trust the catalog for all suspects
                for name in suspect_names:
                    results[name] = detect_compliance(name, [], domain_frameworks)
        except Exception:
            # Error during cross-check — trust the catalog silently
            for name in suspect_names:
                results[name] = detect_compliance(name, [], domain_frameworks)

    return {"results": results, "warning": warning, "attempts": attempts}

