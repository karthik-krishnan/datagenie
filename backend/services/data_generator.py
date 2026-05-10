import re
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from faker import Faker

fake = Faker()


# ---------------------------------------------------------------------------
# Field-type → generator mapping
# Covers all field_type values emitted by compliance_detector.py
# ---------------------------------------------------------------------------
def _gen_for_field_type(field_type: str) -> Any:
    ft = (field_type or "").lower()

    # Names
    if ft in ("person_name", "name"):             return fake.name()
    if ft == "first_name":                        return fake.first_name()
    if ft == "last_name":                         return fake.last_name()

    # Contact
    if ft == "email_address":                     return fake.email()
    if ft == "phone_number":                      return fake.phone_number()

    # Identity documents
    if ft == "social_security":                   return fake.ssn()
    if ft == "passport_number":                   return fake.bothify("??######").upper()
    if ft in ("drivers_license", "license_identifier"):
        return fake.bothify("??-###-###")
    if ft == "national_identifier":               return fake.bothify("ID-########")

    # Dates / age
    if ft == "date_of_birth":
        return fake.date_of_birth(minimum_age=18, maximum_age=85).isoformat()
    if ft == "age":                               return random.randint(18, 85)

    # Address / location
    if ft == "postal_address":                    return fake.street_address()
    if ft == "city":                              return fake.city()
    if ft == "country":                           return fake.country()
    if ft == "postal_code":                       return fake.postcode()
    if ft in ("location_data", "geolocation"):
        return f"{round(fake.latitude(), 6)},{round(fake.longitude(), 6)}"

    # Network / device
    if ft == "ip_address":                        return fake.ipv4()
    if ft in ("device_identifier", "cookie_id", "session_identifier"):
        return fake.uuid4()

    # Demographic / sensitive categories
    if ft == "demographic":                       return random.choice(["Male", "Female", "Non-binary"])
    if ft == "sensitive_category":                return "[SYNTHETIC]"
    if ft == "biometric_data":                    return "[SYNTHETIC-BIO]"

    # Payment / PCI
    if ft == "card_number":                       return fake.credit_card_number()
    if ft == "card_cvv":                          return fake.credit_card_security_code()
    if ft == "card_expiry":                       return fake.credit_card_expire()
    if ft == "account_number":                    return fake.bban()
    if ft == "routing_number":                    return fake.numerify("########")
    if ft == "bank_account":                      return fake.bban()
    if ft == "iban":                              return fake.iban()
    if ft == "swift_bic":                         return fake.swift()
    if ft == "sort_code":                         return fake.numerify("##-##-##")

    # HIPAA
    if ft == "medical_record_no":                 return fake.bothify("MRN-######")
    if ft == "patient_identifier":                return fake.bothify("PT-#######")
    if ft in ("medical_diagnosis", "diagnosis"):
        return random.choice(["Hypertension", "Type 2 Diabetes", "Asthma", "Migraine", "Anxiety Disorder"])
    if ft == "diagnosis_code":
        return random.choice(["I10", "E11.9", "J45.909", "G43.909", "F41.1"])
    if ft == "provider_id":                       return fake.numerify("##########")
    if ft == "provider_name":                     return f"Dr. {fake.last_name()}"
    if ft in ("insurance_info", "insurance_number", "insurance_member_id"):
        return fake.bothify("INS-########")
    if ft in ("prescription", "medication"):
        return random.choice(["Lisinopril 10mg", "Metformin 500mg", "Atorvastatin 20mg", "Levothyroxine 50mcg"])
    if ft in ("treatment_info", "medical_procedure"):
        return random.choice(["Physical Therapy", "MRI Scan", "Blood Panel", "Colonoscopy", "X-Ray"])
    if ft == "lab_result":
        return random.choice(["Normal", "Elevated", "Within Range", "Below Threshold"])
    if ft == "dea_number":                        return fake.bothify("?#######")
    if ft == "service_date":
        return (datetime.utcnow() - timedelta(days=random.randint(1, 365))).date().isoformat()

    # SOX / Financial
    if ft == "compensation":                      return round(random.uniform(40000, 250000), 2)
    if ft == "financial_data":                    return round(random.uniform(1000, 1000000), 2)
    if ft == "tax_identifier":                    return fake.numerify("##-#######")
    if ft == "employer_id":                       return fake.numerify("##-#######")
    if ft == "taxpayer_id":                       return fake.numerify("###-##-####")
    if ft == "audit_trail":                       return fake.sentence()

    # FERPA
    if ft == "student_identifier":               return fake.bothify("STU-######")
    if ft == "academic_record":                  return round(random.uniform(0, 4.0), 2)
    if ft == "enrollment_info":
        return random.choice(["Full-time", "Part-time", "Online"])
    if ft == "course_info":
        return random.choice(["CS101", "MATH201", "ENG301", "BIO150", "HIST220"])
    if ft == "financial_aid":                    return round(random.uniform(1000, 25000), 2)

    # General identifiers
    if ft == "identifier":                        return fake.uuid4()

    return None   # caller falls through to type/pattern based generation


# ---------------------------------------------------------------------------
# Apply a custom masking rule described in plain text
# ---------------------------------------------------------------------------
def _apply_custom_rule(value: str, custom_rule: str) -> str:
    rule = (custom_rule or "").lower()

    # "last N digits visible / show only last N digits"
    m = re.search(r"last\s+(\d+)\s+digits?", rule)
    if m:
        n = int(m.group(1))
        s = re.sub(r"[^0-9]", "", str(value))   # strip non-digits for counting
        if len(s) > n:
            masked = re.sub(r"\d", "*", str(value))   # mask ALL digits first
            # Now un-mask the last n digits
            unmasked = list(masked)
            digit_positions = [i for i, c in enumerate(str(value)) if c.isdigit()]
            for pos in digit_positions[-n:]:
                unmasked[pos] = str(value)[pos]
            return "".join(unmasked)
        return value

    # "first N digits visible"
    m = re.search(r"first\s+(\d+)\s+digits?", rule)
    if m:
        n = int(m.group(1))
        digit_positions = [i for i, c in enumerate(str(value)) if c.isdigit()]
        result = list(str(value))
        for pos in digit_positions[n:]:
            result[pos] = "*"
        return "".join(result)

    # "mask" / "masked"
    if re.search(r"\bmask\b|\bmasked\b|\bhide\b", rule):
        return re.sub(r"[A-Za-z0-9]", "*", str(value))

    # "redact"
    if "redact" in rule:
        return "[REDACTED]"

    return value


# ---------------------------------------------------------------------------
# Core value generator — single column, single row
# ---------------------------------------------------------------------------
def _gen_value_for_column(col: Dict[str, Any], compliance_rules: Dict[str, Any]) -> Any:
    name     = col["name"]
    ctype    = col.get("type", "string")
    pattern  = col.get("pattern", "generic")
    pii      = col.get("pii", {})           # compliance metadata

    # Resolve compliance rule (try bare column name, then table.column)
    rule = compliance_rules.get(name) or compliance_rules.get(f"{col.get('_table', '')}.{name}")

    # Read field_type from the compliance detector (preferred) or legacy pii_type
    field_type = pii.get("field_type") or pii.get("pii_type") or ""
    is_sensitive = pii.get("is_sensitive") or pii.get("is_pii", False)

    # --- If a compliance rule exists, apply it ---
    if rule:
        action      = rule.get("action", "fake_realistic")
        custom_rule = rule.get("custom_rule") or ""

        if action == "redact":
            return "[REDACTED]"

        if action == "mask":
            raw = _gen_for_field_type(field_type) or _gen_by_type_pattern(col, ctype, pattern, name)
            return re.sub(r"[A-Za-z0-9]", "*", str(raw))

        if action == "Custom" and custom_rule:
            # Generate a realistic value first, then apply the custom masking rule
            raw = _gen_for_field_type(field_type) or _gen_by_type_pattern(col, ctype, pattern, name)
            return _apply_custom_rule(str(raw), custom_rule)

        if action == "format_preserving":
            val = _gen_for_field_type(field_type)
            if val is not None:
                return val
            # Fall through to type/pattern generation

        # fake_realistic or unknown → generate normally (handled below)

    # --- Generate based on field_type from compliance detector ---
    if is_sensitive and field_type:
        val = _gen_for_field_type(field_type)
        if val is not None:
            return val

    # --- Name-based heuristics (catch common column names not in compliance catalog) ---
    nl = name.lower()
    if "first" in nl and "name" in nl:  return fake.first_name()
    if "last"  in nl and "name" in nl:  return fake.last_name()
    if "ssn"   in nl or "social" in nl: return fake.ssn()
    if "email" in nl:                   return fake.email()
    if "phone" in nl or "mobile" in nl: return fake.phone_number()
    if "zip"   in nl or "postal" in nl: return fake.postcode()
    if "city"  in nl:                   return fake.city()
    if "country" in nl:                 return fake.country()
    if "state"   in nl:                 return fake.state()
    if "address" in nl:                 return fake.street_address()
    if "company" in nl:                 return fake.company()
    if "description" in nl or "note" in nl or "comment" in nl:
                                        return fake.sentence()
    if "url" in nl or "website" in nl:  return fake.url()
    if "salary" in nl or "wage" in nl:  return round(random.uniform(30000, 200000), 2)
    if "price"  in nl or "amount" in nl or "cost" in nl or "total" in nl:
                                        return round(random.uniform(1, 5000), 2)
    if "age"    in nl:                  return random.randint(18, 85)
    if "gender" in nl or "sex" in nl:   return random.choice(["Male", "Female", "Non-binary"])
    if "status" in nl:                  return random.choice(["Active", "Inactive", "Pending"])
    if "uuid"   in nl:                  return fake.uuid4()

    # --- Fall back to Faker by schema type ---
    return _gen_by_type_pattern(col, ctype, pattern, name)


def _gen_by_type_pattern(col: Dict[str, Any], ctype: str, pattern: str, name: str) -> Any:
    if ctype == "email":     return fake.email()
    if ctype == "phone":     return fake.phone_number()
    if ctype == "boolean":   return random.choice([True, False])
    if ctype == "integer":   return random.randint(1, 10000)
    if ctype == "float":     return round(random.uniform(1.0, 1000.0), 2)
    if ctype == "date":
        return (datetime.utcnow() - timedelta(days=random.randint(0, 730))).date().isoformat()
    if ctype == "enum":
        vals = col.get("enum_values") or ["Option A", "Option B", "Option C"]
        return random.choice(vals)

    if pattern == "identifier": return random.randint(1000, 99999)
    if pattern == "name":       return fake.name()
    if pattern == "currency":   return round(random.uniform(5.0, 5000.0), 2)

    # Last resort: fake.word() generates nonsense for sensitive fields,
    # so use a more contextual fallback
    return fake.word()


# ---------------------------------------------------------------------------
# Temporal aging helper
# ---------------------------------------------------------------------------
def _apply_temporal_aging(days_back: int) -> str:
    return (datetime.utcnow() - timedelta(days=days_back)).date().isoformat()


# ---------------------------------------------------------------------------
# Enum distribution helper
# ---------------------------------------------------------------------------
def _apply_enum_distribution(col: Dict[str, Any], distribution: Dict[str, float], n: int) -> List[Any]:
    vals    = list(distribution.keys())
    weights = [float(w) for w in distribution.values()]
    if not vals:
        vals    = col.get("enum_values") or ["A", "B", "C"]
        weights = [1.0] * len(vals)
    return random.choices(vals, weights=weights, k=n)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def generate_data(
    schema: Dict[str, Any],
    characteristics: Dict[str, Any],
    compliance_rules: Dict[str, Any],
    relationships: List[Dict[str, Any]],
    volume: int = 100,
    llm_settings: Optional[Dict[str, Any]] = None,
    preview: bool = False,
) -> Dict[str, List[Dict[str, Any]]]:

    tables        = schema.get("tables", [])
    distributions = (characteristics or {}).get("distributions", {})
    temporal      = (characteristics or {}).get("temporal", {})

    # Order tables: parents before children (referential integrity)
    parents, children = set(), set()
    for r in relationships or schema.get("relationships", []):
        children.add(r["source_table"])
        parents.add(r["target_table"])

    ordered = sorted(
        tables,
        key=lambda t: 0 if (t["table_name"] in parents and t["table_name"] not in children) else 1
    )

    pk_cache: Dict[str, List[Any]] = {}
    fk_map:   Dict[str, Dict[str, Any]] = {}
    for r in (relationships or schema.get("relationships", [])):
        fk_map.setdefault(r["source_table"], {})[r["source_column"]] = {
            "target_table":  r["target_table"],
            "target_column": r["target_column"],
        }

    out: Dict[str, List[Dict[str, Any]]] = {}

    for tbl in ordered:
        tname = tbl["table_name"]
        cols  = tbl["columns"]
        n     = volume

        # Pre-compute distributed columns (enum / boolean with explicit distribution)
        precomputed: Dict[str, List[Any]] = {}
        for col in cols:
            cname    = col["name"]
            dist_key = f"{tname}.{cname}"
            dist     = distributions.get(dist_key) or distributions.get(cname)

            if col.get("type") == "enum" and isinstance(dist, dict) and dist:
                precomputed[cname] = _apply_enum_distribution(col, dist, n)

            elif col.get("type") == "boolean" and isinstance(dist, dict) and "true_ratio" in dist:
                ratio = float(dist.get("true_ratio", 0.5))
                precomputed[cname] = [random.random() < ratio for _ in range(n)]

            elif col.get("name", "").lower() == "gender" or col.get("enum_values"):
                # Gender or any enum column with distribution keyed by value
                if isinstance(dist, dict) and dist:
                    precomputed[cname] = _apply_enum_distribution(col, dist, n)

        rows: List[Dict[str, Any]] = []
        for i in range(n):
            row: Dict[str, Any] = {}

            for col in cols:
                cname = col["name"]
                col_with_table = {**col, "_table": tname}

                # FK reference — use a parent PK value
                fk = fk_map.get(tname, {}).get(cname)
                if fk:
                    parent_pk = pk_cache.get(f"{fk['target_table']}.{fk['target_column']}", [])
                    if parent_pk:
                        row[cname] = random.choice(parent_pk)
                        continue

                # Pre-computed distribution
                if cname in precomputed:
                    row[cname] = precomputed[cname][i]
                    continue

                # Auto-increment PK
                if cname.lower() == "id":
                    row[cname] = i + 1
                    continue

                # Generate value
                val = _gen_value_for_column(col_with_table, compliance_rules)

                # Apply temporal aging for date columns
                if col.get("type") == "date":
                    aging = temporal.get(f"{tname}.{cname}") or temporal.get(cname)
                    if aging:
                        try:
                            days = int(aging.get("days_back", 0)) if isinstance(aging, dict) else int(aging)
                            if days:
                                val = _apply_temporal_aging(days)
                        except Exception:
                            pass

                row[cname] = val

            # Cache PKs for FK resolution in child tables
            for col in cols:
                if col["name"].lower() == "id":
                    pk_cache.setdefault(f"{tname}.{col['name']}", []).append(row[col["name"]])

            rows.append(row)

        out[tname] = rows

    return out
