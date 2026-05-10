import re
import random
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from faker import Faker
from services.masking import apply_masking_op, normalize_masking_rule

fake = Faker()


# ---------------------------------------------------------------------------
# Country → cities lookup (real places, city within country is consistent)
# ---------------------------------------------------------------------------
COUNTRY_CITIES: Dict[str, List[str]] = {
    "United States":    ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
                         "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose",
                         "Austin", "Jacksonville", "Fort Worth", "Columbus", "Charlotte"],
    "United Kingdom":   ["London", "Birmingham", "Manchester", "Leeds", "Glasgow",
                         "Liverpool", "Bristol", "Edinburgh", "Cardiff", "Sheffield"],
    "Canada":           ["Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton",
                         "Ottawa", "Winnipeg", "Quebec City", "Hamilton", "Halifax"],
    "Australia":        ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide",
                         "Gold Coast", "Canberra", "Newcastle", "Hobart", "Darwin"],
    "Germany":          ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt",
                         "Stuttgart", "Düsseldorf", "Dortmund", "Essen", "Leipzig"],
    "France":           ["Paris", "Marseille", "Lyon", "Toulouse", "Nice",
                         "Nantes", "Strasbourg", "Montpellier", "Bordeaux", "Lille"],
    "India":            ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
                         "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Surat"],
    "China":            ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu",
                         "Wuhan", "Xi'an", "Hangzhou", "Nanjing", "Tianjin"],
    "Japan":            ["Tokyo", "Osaka", "Nagoya", "Sapporo", "Fukuoka",
                         "Kobe", "Kyoto", "Kawasaki", "Saitama", "Hiroshima"],
    "Brazil":           ["São Paulo", "Rio de Janeiro", "Brasília", "Salvador",
                         "Fortaleza", "Belo Horizonte", "Manaus", "Curitiba", "Recife"],
    "Mexico":           ["Mexico City", "Guadalajara", "Monterrey", "Puebla", "Toluca",
                         "Tijuana", "León", "Juárez", "Zapopan", "Mérida"],
    "Spain":            ["Madrid", "Barcelona", "Valencia", "Seville", "Zaragoza",
                         "Málaga", "Murcia", "Palma", "Bilbao", "Alicante"],
    "Italy":            ["Rome", "Milan", "Naples", "Turin", "Palermo",
                         "Genoa", "Bologna", "Florence", "Catania", "Venice"],
    "Netherlands":      ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven",
                         "Tilburg", "Groningen", "Almere", "Breda", "Nijmegen"],
    "Singapore":        ["Singapore"],
    "South Korea":      ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon",
                         "Gwangju", "Suwon", "Ulsan", "Changwon", "Seongnam"],
    "South Africa":     ["Johannesburg", "Cape Town", "Durban", "Pretoria",
                         "Port Elizabeth", "Bloemfontein", "East London", "Nelspruit"],
    "Nigeria":          ["Lagos", "Kano", "Ibadan", "Abuja", "Port Harcourt",
                         "Benin City", "Maiduguri", "Zaria", "Aba", "Jos"],
    "Argentina":        ["Buenos Aires", "Córdoba", "Rosario", "Mendoza", "Tucumán",
                         "La Plata", "Mar del Plata", "Salta", "Santa Fe"],
    "Sweden":           ["Stockholm", "Gothenburg", "Malmö", "Uppsala", "Västerås",
                         "Örebro", "Linköping", "Helsingborg", "Jönköping"],
    "Poland":           ["Warsaw", "Kraków", "Łódź", "Wrocław", "Poznań",
                         "Gdańsk", "Szczecin", "Bydgoszcz", "Lublin", "Katowice"],
    "Turkey":           ["Istanbul", "Ankara", "İzmir", "Bursa", "Adana",
                         "Gaziantep", "Konya", "Antalya", "Kayseri", "Mersin"],
    "Indonesia":        ["Jakarta", "Surabaya", "Bandung", "Medan", "Semarang",
                         "Makassar", "Palembang", "Tangerang", "Depok", "Bekasi"],
    "Pakistan":         ["Karachi", "Lahore", "Islamabad", "Faisalabad", "Rawalpindi",
                         "Multan", "Hyderabad", "Gujranwala", "Peshawar", "Quetta"],
    "Bangladesh":       ["Dhaka", "Chittagong", "Sylhet", "Rajshahi", "Khulna",
                         "Comilla", "Mymensingh", "Narayanganj", "Rangpur"],
    "Russia":           ["Moscow", "Saint Petersburg", "Novosibirsk", "Yekaterinburg",
                         "Nizhny Novgorod", "Kazan", "Chelyabinsk", "Omsk", "Samara"],
    "Kenya":            ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret",
                         "Thika", "Malindi", "Kitale", "Kakamega", "Garissa"],
    "New Zealand":      ["Auckland", "Wellington", "Christchurch", "Hamilton",
                         "Tauranga", "Dunedin", "Palmerston North", "Napier"],
    "Ireland":          ["Dublin", "Cork", "Limerick", "Galway", "Waterford",
                         "Drogheda", "Dundalk", "Swords", "Bray", "Navan"],
    "Portugal":         ["Lisbon", "Porto", "Amadora", "Braga", "Setúbal",
                         "Coimbra", "Funchal", "Almada", "Agualva-Cacém"],
    "Belgium":          ["Brussels", "Antwerp", "Ghent", "Charleroi", "Liège",
                         "Bruges", "Namur", "Leuven", "Mons", "Mechelen"],
}

_COUNTRY_LIST = list(COUNTRY_CITIES.keys())


def _pick_country() -> str:
    return random.choice(_COUNTRY_LIST)


def _pick_city_for_country(country: str) -> str:
    cities = COUNTRY_CITIES.get(country)
    if cities:
        return random.choice(cities)
    # Fallback if country isn't in our map
    return fake.city()


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
# Delegates to structured masking ops via services/masking.py
# ---------------------------------------------------------------------------
def _apply_custom_rule(value: str, custom_rule: str, masking_op: dict = None) -> str:
    """Apply a masking instruction to a single generated value.

    Prefers a pre-normalised masking_op (structured dict) when available.
    Falls back to normalising the plain-text rule on the fly (no LLM, keyword-only).
    """
    op = masking_op
    if not op and custom_rule:
        # Keyword-only fallback — no LLM call at generation time
        op = normalize_masking_rule(custom_rule, llm_provider=None)
    if op:
        return apply_masking_op(value, op)
    # Ultimate fallback: mask all alphanumeric
    import re as _re
    return _re.sub(r"[A-Za-z0-9]", "*", str(value))


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
            # Generate a realistic value first, then apply the custom masking rule.
            # Use pre-normalised masking_op when present (set at schema-inference time).
            raw = _gen_for_field_type(field_type) or _gen_by_type_pattern(col, ctype, pattern, name)
            masking_op = rule.get("masking_op")
            return _apply_custom_rule(str(raw), custom_rule, masking_op)

        if action == "format_preserving":
            val = _gen_for_field_type(field_type)
            if val is not None:
                return val
            # Fall through to type/pattern generation

        # fake_realistic or unknown → generate normally (handled below)

    # --- Generate based on field_type from compliance detector ---
    # Skip for city/country/state — fall through to name-based heuristics below
    # which have country-consistency logic (city within the right country).
    if is_sensitive and field_type and field_type not in ("city", "country", "state"):
        val = _gen_for_field_type(field_type)
        if val is not None:
            return val

    # --- Enum with explicit values: always honour the schema definition ---
    if ctype == "enum":
        vals = col.get("enum_values") or ["Option A", "Option B", "Option C"]
        return random.choice(vals)

    # --- Name-based heuristics (catch common column names not in compliance catalog) ---
    nl = name.lower()
    if "first" in nl and "name" in nl:  return fake.first_name()
    if "last"  in nl and "name" in nl:  return fake.last_name()
    if "product" in nl and "name" in nl: return fake.catch_phrase()
    if "drug"    in nl and "name" in nl: return random.choice(["Metformin 500mg", "Lisinopril 10mg", "Atorvastatin 20mg", "Amoxicillin 250mg", "Omeprazole 20mg"])
    if "course"  in nl and "name" in nl: return fake.catch_phrase()
    if "company" in nl and "name" in nl: return fake.company()
    if "job"     in nl and "title" in nl: return fake.job()
    if "physician" in nl or "doctor" in nl: return "Dr. " + fake.name()
    if "ssn"   in nl or "social" in nl: return fake.ssn()
    if "email" in nl:                   return fake.email()
    if "phone" in nl or "mobile" in nl: return fake.phone_number()
    if "zip"   in nl or "postal" in nl: return fake.postcode()
    if "country" in nl:                 return _pick_country()
    if "city"  in nl:
        # If the partial row already has a country, pick a city within it
        row_ctx = col.get("_row_context") or {}
        country_val = next(
            (v for k, v in row_ctx.items() if "country" in k.lower()),
            None,
        )
        return _pick_city_for_country(country_val) if country_val else _pick_city_for_country(_pick_country())
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


_DATE_FORMAT_MAP = {
    "YYYY-MM-DD":            "%Y-%m-%d",
    "MM/DD/YYYY":            "%m/%d/%Y",
    "DD/MM/YYYY":            "%d/%m/%Y",
    "YYYY-MM-DD HH:mm:ss":   "%Y-%m-%d %H:%M:%S",
    "MM/DD/YYYY HH:mm:ss":   "%m/%d/%Y %H:%M:%S",
}


def _format_date(dt_obj, fmt: Optional[str]) -> str:
    """Format a date/datetime using the user-specified format token string."""
    strfmt = _DATE_FORMAT_MAP.get(fmt or "YYYY-MM-DD", "%Y-%m-%d")
    return dt_obj.strftime(strfmt)


def _gen_by_type_pattern(col: Dict[str, Any], ctype: str, pattern: str, name: str) -> Any:
    if ctype == "email":     return fake.email()
    if ctype == "phone":     return fake.phone_number()
    if ctype == "boolean":   return random.choice([True, False])
    if ctype == "integer":   return random.randint(1, 10000)
    if ctype == "float":     return round(random.uniform(1.0, 1000.0), 2)
    if ctype == "date":
        dt = (datetime.utcnow() - timedelta(days=random.randint(0, 730)))
        return _format_date(dt, col.get("date_format"))
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
def _apply_temporal_aging(days_back: int, fmt: Optional[str] = None) -> str:
    dt = datetime.utcnow() - timedelta(days=days_back)
    return _format_date(dt, fmt)


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
# Per-table volume calculation
#
# Root tables (no inbound FK) get `volume` rows.
# Child tables in a many_to_one relationship scale up so the relationship
# feels realistic:
#
#   depth 0  (root)            →  volume
#   depth 1  (direct child)    →  volume × children_per_parent
#   depth 2  (grandchild)      →  volume × children_per_parent²
#
# one_to_one children always get the same count as their parent.
#
# `per_table_volumes` (from characteristics) overrides everything for a
# specific table.  Preview mode always uses the passed volume unchanged.
# ---------------------------------------------------------------------------
def _compute_table_volumes(
    table_names:         List[str],
    all_rels:            List[Dict[str, Any]],
    parent_to_children:  Dict[str, List[str]],   # adj from topological sort
    base_volume:         int,
    per_table_volumes:   Dict[str, int],
    children_per_parent: int,
    preview:             bool,
) -> Dict[str, int]:
    if preview:
        return {t: base_volume for t in table_names}

    tname_set = set(table_names)

    # BFS from roots to assign depth
    child_set = {
        r["source_table"] for r in all_rels
        if r["source_table"] in tname_set and r["target_table"] in tname_set
    }
    depth: Dict[str, int] = {}
    queue: deque = deque()
    for t in table_names:
        if t not in child_set:
            depth[t] = 0
            queue.append((t, 0))
    while queue:
        tname, d = queue.popleft()
        for child in parent_to_children.get(tname, []):
            if child not in depth or depth[child] < d + 1:
                depth[child] = d + 1
                queue.append((child, d + 1))

    # Dominant incoming cardinality per table
    # (many_to_one beats one_to_one — if any parent sends many children, scale up)
    incoming: Dict[str, str] = {}
    for r in all_rels:
        src  = r["source_table"]
        card = r.get("cardinality", "many_to_one")
        if src not in incoming or card == "many_to_one":
            incoming[src] = card

    result: Dict[str, int] = {}
    for t in table_names:
        if t in per_table_volumes:
            result[t] = max(1, int(per_table_volumes[t]))
        else:
            d    = depth.get(t, 0)
            card = incoming.get(t, "many_to_one")
            if d == 0 or card == "one_to_one":
                result[t] = base_volume
            else:
                result[t] = max(base_volume, int(base_volume * (children_per_parent ** d)))
    return result


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

    tables               = schema.get("tables", [])
    characteristics      = characteristics or {}
    distributions        = characteristics.get("distributions", {})
    temporal             = characteristics.get("temporal", {})
    per_table_volumes    = characteristics.get("per_table_volumes", {})
    children_per_parent  = int(characteristics.get("children_per_parent", 3))

    all_rels = relationships or schema.get("relationships", [])

    # ── Topological sort (Kahn's algorithm) — supports multi-hop chains A→B→C ──
    # source_table = child (has the FK), target_table = parent (owns the PK).
    table_names = [t["table_name"] for t in tables]
    in_degree:  Dict[str, int]       = {t: 0 for t in table_names}
    adj:        Dict[str, List[str]] = defaultdict(list)   # parent → [children]

    for r in all_rels:
        src, tgt = r["source_table"], r["target_table"]
        if src in in_degree and tgt in in_degree and tgt != src:
            adj[tgt].append(src)
            in_degree[src] += 1

    queue = deque(sorted([t for t in table_names if in_degree[t] == 0]))
    ordered_names: List[str] = []
    while queue:
        node = queue.popleft()
        ordered_names.append(node)
        for child in adj[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    # Any tables not reachable via the DAG (isolated or circular) come last
    remaining = [t for t in table_names if t not in ordered_names]
    ordered_names.extend(remaining)

    name_to_table = {t["table_name"]: t for t in tables}
    ordered = [name_to_table[n] for n in ordered_names if n in name_to_table]

    # Per-table row counts — children in many:1 relationships scale up
    table_volumes = _compute_table_volumes(
        table_names         = table_names,
        all_rels            = all_rels,
        parent_to_children  = adj,
        base_volume         = volume,
        per_table_volumes   = per_table_volumes,
        children_per_parent = children_per_parent,
        preview             = preview,
    )

    pk_cache: Dict[str, List[Any]] = {}
    fk_map:   Dict[str, Dict[str, Any]] = {}
    for r in all_rels:
        fk_map.setdefault(r["source_table"], {})[r["source_column"]] = {
            "target_table":  r["target_table"],
            "target_column": r["target_column"],
            "cardinality":   r.get("cardinality", "many_to_one"),
        }

    out: Dict[str, List[Dict[str, Any]]] = {}

    for tbl in ordered:
        tname = tbl["table_name"]
        cols  = tbl["columns"]
        n     = table_volumes.get(tname, volume)

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

        # Sort columns so location-parent fields (country, state) come before
        # location-child fields (city) — ensures city can reference country in the row.
        def _col_order(c: Dict[str, Any]) -> int:
            nl = c["name"].lower()
            if "country" in nl: return 0
            if "state"   in nl: return 1
            if "city"    in nl: return 2
            return 3

        cols_ordered = sorted(cols, key=_col_order)

        rows: List[Dict[str, Any]] = []
        for i in range(n):
            row: Dict[str, Any] = {}

            for col in cols_ordered:
                cname = col["name"]
                # Pass partial row as context so city can read the country already set
                col_with_table = {**col, "_table": tname, "_row_context": row}

                # FK reference — use a parent PK value
                fk = fk_map.get(tname, {}).get(cname)
                if fk:
                    parent_pk = pk_cache.get(f"{fk['target_table']}.{fk['target_column']}", [])
                    if parent_pk:
                        if fk.get("cardinality") == "one_to_one":
                            # Maintain a shuffle pool so each parent PK is used at most once.
                            pool_key = f"__1to1__{fk['target_table']}.{fk['target_column']}__{tname}.{cname}"
                            if pool_key not in pk_cache:
                                pool = list(parent_pk)
                                random.shuffle(pool)
                                pk_cache[pool_key] = pool
                            pool = pk_cache[pool_key]
                            row[cname] = pool.pop(0) if pool else random.choice(parent_pk)
                        else:
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
                                val = _apply_temporal_aging(days, col.get("date_format"))
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
