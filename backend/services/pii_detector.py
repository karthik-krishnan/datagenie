import re
from typing import List, Any, Dict

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SSN_RE = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")
PHONE_RE = re.compile(r"^[+\d][\d\s\-\(\)]{6,}$")
IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
CC_RE = re.compile(r"^\d{13,19}$")
PASSPORT_RE = re.compile(r"^[A-Z]{1,2}\d{6,9}$")

NAME_KEYWORDS = {
    "email": ("PII", "email"),
    "ssn": ("PII", "ssn"),
    "social_security": ("PII", "ssn"),
    "dob": ("PII", "date_of_birth"),
    "date_of_birth": ("PII", "date_of_birth"),
    "birth_date": ("PII", "date_of_birth"),
    "phone": ("PII", "phone"),
    "mobile": ("PII", "phone"),
    "credit_card": ("PCI", "credit_card"),
    "cc_number": ("PCI", "credit_card"),
    "card_number": ("PCI", "credit_card"),
    "account_number": ("PCI", "account_number"),
    "iban": ("PCI", "iban"),
    "ip_address": ("PII", "ip_address"),
    "ip": ("PII", "ip_address"),
    "passport": ("PII", "passport"),
    "diagnosis": ("HIPAA", "diagnosis"),
    "icd": ("HIPAA", "diagnosis_code"),
    "mrn": ("HIPAA", "medical_record_number"),
    "npi": ("HIPAA", "national_provider_id"),
    "patient_id": ("HIPAA", "patient_id"),
}


def _luhn(num: str) -> bool:
    digits = [int(c) for c in num if c.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    parity = (len(digits) - 2) % 2
    for i, d in enumerate(digits[:-1]):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return (checksum + digits[-1]) % 10 == 0


def detect_pii(column_name: str, sample_values: List[Any]) -> Dict[str, Any]:
    name_lower = column_name.lower().replace(" ", "_")

    for kw, (cat, ptype) in NAME_KEYWORDS.items():
        if kw in name_lower:
            return {"is_pii": True, "category": cat, "pii_type": ptype, "confidence": 0.95}

    cleaned = [str(v).strip() for v in sample_values if v not in (None, "")]
    if not cleaned:
        return {"is_pii": False, "category": None, "pii_type": None, "confidence": 0.0}

    sample = cleaned[:10]
    matches = {"email": 0, "ssn": 0, "phone": 0, "ip": 0, "cc": 0, "passport": 0}
    for v in sample:
        if EMAIL_RE.match(v):
            matches["email"] += 1
        if SSN_RE.match(v):
            matches["ssn"] += 1
        if PHONE_RE.match(v):
            matches["phone"] += 1
        if IP_RE.match(v):
            matches["ip"] += 1
        if CC_RE.match(v) and _luhn(v):
            matches["cc"] += 1
        if PASSPORT_RE.match(v):
            matches["passport"] += 1

    total = len(sample)
    if matches["email"] / total > 0.7:
        return {"is_pii": True, "category": "PII", "pii_type": "email", "confidence": 0.9}
    if matches["ssn"] / total > 0.7:
        return {"is_pii": True, "category": "PII", "pii_type": "ssn", "confidence": 0.95}
    if matches["cc"] / total > 0.7:
        return {"is_pii": True, "category": "PCI", "pii_type": "credit_card", "confidence": 0.95}
    if matches["ip"] / total > 0.7:
        return {"is_pii": True, "category": "PII", "pii_type": "ip_address", "confidence": 0.85}
    if matches["passport"] / total > 0.7:
        return {"is_pii": True, "category": "PII", "pii_type": "passport", "confidence": 0.8}
    if matches["phone"] / total > 0.7 and any(sum(c.isdigit() for c in v) >= 9 for v in sample):
        return {"is_pii": True, "category": "PII", "pii_type": "phone", "confidence": 0.8}

    return {"is_pii": False, "category": None, "pii_type": None, "confidence": 0.0}
