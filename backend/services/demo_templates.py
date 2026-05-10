"""
Pre-built schema templates for Demo mode.
No parsing, no regex, no LLM — just realistic canned data that demonstrates
all features of the app (compliance, distributions, relationships, etc.)
"""

from typing import Any, Dict

# ── Template definitions ────────────────────────────────────────────────────

TEMPLATES: Dict[str, Dict[str, Any]] = {

    "users": {
        "keywords": ["user", "person", "people", "customer", "member", "contact", "employee", "staff", "worker"],
        "entity_type": "users",
        "volume": 100,
        "table_name": "users",
        "columns": [
            {"name": "user_id",    "type": "integer", "sample_values": ["1001", "1002", "1003"]},
            {"name": "first_name", "type": "string",  "sample_values": ["James", "Maria", "Priya"]},
            {"name": "last_name",  "type": "string",  "sample_values": ["Carter", "Lopez", "Sharma"]},
            {"name": "email",      "type": "email",   "sample_values": ["james.carter@example.com", "m.lopez@mail.com"]},
            {"name": "phone",      "type": "phone",   "sample_values": ["+1-555-0142", "+1-555-0287"]},
            {"name": "gender",     "type": "enum",    "sample_values": ["Male", "Female", "Non-binary"],
             "enum_values": ["Male", "Female", "Non-binary", "Not specified"]},
            {"name": "age",        "type": "integer", "sample_values": ["28", "35", "42"]},
            {"name": "city",       "type": "string",  "sample_values": ["Austin", "Chicago", "San Jose"]},
            {"name": "country",    "type": "string",  "sample_values": ["US", "US", "IN"]},
            {"name": "ssn",        "type": "string",  "sample_values": ["***-**-4821", "***-**-3374"]},
            {"name": "created_at", "type": "date",    "sample_values": ["2023-06-12", "2024-01-08"]},
        ],
        "distributions": {
            "gender": {"Male": 60, "Female": 30, "Non-binary": 7, "Not specified": 3},
        },
        "compliance_rules": {
            "ssn":   {"action": "mask",         "custom_rule": None, "frameworks": ["PII", "HIPAA"]},
            "email": {"action": "fake_realistic","custom_rule": None, "frameworks": ["PII", "GDPR"]},
            "phone": {"action": "fake_realistic","custom_rule": None, "frameworks": ["PII"]},
        },
        "frameworks_detected": ["PII", "GDPR"],
        "sensitive_detected": True,
    },

    "patients": {
        "keywords": ["patient", "clinical", "health", "medical", "hospital", "diagnosis", "hipaa", "ehr", "emr", "physician"],
        "entity_type": "patients",
        "volume": 50,
        "table_name": "patients",
        "columns": [
            {"name": "patient_id",   "type": "string",  "sample_values": ["PAT-00421", "PAT-00422"]},
            {"name": "first_name",   "type": "string",  "sample_values": ["Dorothy", "Marcus"]},
            {"name": "last_name",    "type": "string",  "sample_values": ["Nguyen", "Williams"]},
            {"name": "dob",          "type": "date",    "sample_values": ["1978-03-15", "1965-11-02"]},
            {"name": "gender",       "type": "enum",    "sample_values": ["Female", "Male"],
             "enum_values": ["Male", "Female", "Non-binary", "Not specified"]},
            {"name": "ssn",          "type": "string",  "sample_values": ["***-**-9182", "***-**-4430"]},
            {"name": "mrn",          "type": "string",  "sample_values": ["MRN-884421", "MRN-884422"]},
            {"name": "diagnosis",    "type": "string",  "sample_values": ["Type 2 Diabetes", "Hypertension"]},
            {"name": "physician",    "type": "string",  "sample_values": ["Dr. Sandra Lee", "Dr. Raj Patel"]},
            {"name": "admission_date","type": "date",   "sample_values": ["2024-03-10", "2024-04-22"]},
            {"name": "insurance_id", "type": "string",  "sample_values": ["INS-7764210", "INS-3382104"]},
        ],
        "distributions": {
            "gender": {"Male": 48, "Female": 48, "Non-binary": 3, "Not specified": 1},
        },
        "compliance_rules": {
            "ssn":        {"action": "mask",          "custom_rule": None, "frameworks": ["PII", "HIPAA"]},
            "mrn":        {"action": "format_preserving", "custom_rule": None, "frameworks": ["HIPAA"]},
            "diagnosis":  {"action": "fake_realistic","custom_rule": None, "frameworks": ["HIPAA"]},
            "insurance_id":{"action": "format_preserving","custom_rule": None, "frameworks": ["HIPAA", "PII"]},
            "dob":        {"action": "fake_realistic","custom_rule": None, "frameworks": ["PII", "GDPR", "HIPAA"]},
        },
        "frameworks_detected": ["PII", "HIPAA", "GDPR"],
        "sensitive_detected": True,
    },

    "orders": {
        "keywords": ["order", "purchase", "transaction", "invoice", "sale", "product", "ecommerce", "e-commerce", "checkout"],
        "entity_type": "orders",
        "volume": 200,
        "table_name": "orders",
        "columns": [
            {"name": "order_id",         "type": "string",  "sample_values": ["ORD-10041", "ORD-10042"]},
            {"name": "customer_name",    "type": "string",  "sample_values": ["Alex Johnson", "Fiona Chan"]},
            {"name": "customer_email",   "type": "email",   "sample_values": ["alex.j@email.com", "fchan@mail.com"]},
            {"name": "product",          "type": "string",  "sample_values": ["Wireless Headphones", "USB-C Hub"]},
            {"name": "quantity",         "type": "integer", "sample_values": ["1", "2", "3"]},
            {"name": "unit_price",       "type": "float",   "sample_values": ["49.99", "129.00", "19.95"]},
            {"name": "status",           "type": "enum",    "sample_values": ["Shipped", "Pending", "Delivered"],
             "enum_values": ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"]},
            {"name": "shipping_address", "type": "string",  "sample_values": ["123 Maple St, Austin TX"]},
            {"name": "credit_card",      "type": "string",  "sample_values": ["****-****-****-4821"]},
            {"name": "order_date",       "type": "date",    "sample_values": ["2024-05-01", "2024-05-03"]},
        ],
        "distributions": {
            "status": {"Pending": 15, "Processing": 20, "Shipped": 35, "Delivered": 25, "Cancelled": 5},
        },
        "compliance_rules": {
            "credit_card":   {"action": "format_preserving", "custom_rule": None, "frameworks": ["PCI"]},
            "customer_email":{"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GDPR"]},
        },
        "frameworks_detected": ["PCI", "PII", "GDPR"],
        "sensitive_detected": True,
    },

    "employees": {
        "keywords": ["employee", "staff", "hr", "payroll", "salary", "workforce", "department", "hire"],
        "entity_type": "employees",
        "volume": 75,
        "table_name": "employees",
        "columns": [
            {"name": "employee_id", "type": "string",  "sample_values": ["EMP-0041", "EMP-0042"]},
            {"name": "first_name",  "type": "string",  "sample_values": ["Carlos", "Aisha"]},
            {"name": "last_name",   "type": "string",  "sample_values": ["Rivera", "Okonkwo"]},
            {"name": "email",       "type": "email",   "sample_values": ["c.rivera@corp.com"]},
            {"name": "department",  "type": "enum",    "sample_values": ["Engineering", "Sales", "HR"],
             "enum_values": ["Engineering", "Sales", "HR", "Finance", "Marketing", "Operations"]},
            {"name": "salary",      "type": "float",   "sample_values": ["85000", "92000", "74000"]},
            {"name": "hire_date",   "type": "date",    "sample_values": ["2021-03-15", "2019-08-01"]},
            {"name": "manager",     "type": "string",  "sample_values": ["Sarah Kim", "David Osei"]},
            {"name": "phone",       "type": "phone",   "sample_values": ["+1-555-0199"]},
            {"name": "ssn",         "type": "string",  "sample_values": ["***-**-6612"]},
        ],
        "distributions": {
            "department": {"Engineering": 35, "Sales": 25, "HR": 10, "Finance": 15, "Marketing": 10, "Operations": 5},
        },
        "compliance_rules": {
            "ssn":    {"action": "mask", "custom_rule": None, "frameworks": ["PII"]},
            "salary": {"action": "mask", "custom_rule": None, "frameworks": ["SOX", "PII"]},
            "email":  {"action": "fake_realistic", "custom_rule": None, "frameworks": ["PII", "GDPR"]},
        },
        "frameworks_detected": ["PII", "SOX", "GDPR"],
        "sensitive_detected": True,
    },

    "students": {
        "keywords": ["student", "school", "university", "grade", "course", "academic", "enrollment", "gpa", "ferpa"],
        "entity_type": "students",
        "volume": 60,
        "table_name": "students",
        "columns": [
            {"name": "student_id",   "type": "string",  "sample_values": ["STU-20041", "STU-20042"]},
            {"name": "first_name",   "type": "string",  "sample_values": ["Mei", "Jordan"]},
            {"name": "last_name",    "type": "string",  "sample_values": ["Zhang", "Brooks"]},
            {"name": "email",        "type": "email",   "sample_values": ["mzhang@university.edu"]},
            {"name": "gpa",          "type": "float",   "sample_values": ["3.7", "2.9", "3.4"]},
            {"name": "enrollment",   "type": "enum",    "sample_values": ["Full-time", "Part-time"],
             "enum_values": ["Full-time", "Part-time", "Online"]},
            {"name": "major",        "type": "string",  "sample_values": ["Computer Science", "Biology"]},
            {"name": "year",         "type": "enum",    "sample_values": ["Sophomore", "Junior"],
             "enum_values": ["Freshman", "Sophomore", "Junior", "Senior", "Graduate"]},
            {"name": "dob",          "type": "date",    "sample_values": ["2001-07-14", "2000-11-30"]},
        ],
        "distributions": {
            "enrollment": {"Full-time": 70, "Part-time": 20, "Online": 10},
            "year": {"Freshman": 25, "Sophomore": 25, "Junior": 20, "Senior": 20, "Graduate": 10},
        },
        "compliance_rules": {
            "student_id": {"action": "format_preserving", "custom_rule": None, "frameworks": ["FERPA", "PII"]},
            "gpa":        {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["FERPA"]},
            "email":      {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GDPR"]},
        },
        "frameworks_detected": ["PII", "FERPA", "GDPR"],
        "sensitive_detected": True,
    },
}

DEFAULT_TEMPLATE = "users"


def pick_template(context_text: str) -> str:
    """Pick the best template based on simple keyword presence in the context."""
    text = context_text.lower() if context_text else ""
    # Score each template by how many of its keywords appear
    scores = {}
    for key, tmpl in TEMPLATES.items():
        scores[key] = sum(1 for kw in tmpl["keywords"] if kw in text)
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else DEFAULT_TEMPLATE


def get_demo_schema(context_text: str = "") -> Dict[str, Any]:
    """
    Return a pre-built demo schema with no parsing or LLM calls.
    Picks the most relevant template from the context keywords.
    """
    from services.compliance_detector import detect_compliance

    key = pick_template(context_text)
    tmpl = TEMPLATES[key]

    # Build columns with compliance info attached
    cols = []
    for c in tmpl["columns"]:
        compliance = detect_compliance(c["name"], c.get("sample_values", []))
        cols.append({
            "name": c["name"],
            "type": c["type"],
            "sample_values": c.get("sample_values", []),
            "pattern": c["name"],
            "enum_values": c.get("enum_values", []),
            "pii": compliance,
        })

    schema = {
        "tables": [{
            "table_name": tmpl["table_name"],
            "filename": None,
            "columns": cols,
            "row_count": 0,
        }],
        "relationships": [],
        "pii_detected": tmpl["sensitive_detected"],
        "sensitive_detected": tmpl["sensitive_detected"],
        "frameworks_detected": tmpl["frameworks_detected"],
        "domain_frameworks": [],
        "context": context_text,
        "extracted": {
            "volume": tmpl["volume"],
            "entity_type": tmpl["entity_type"],
            "columns": [{"name": c["name"], "type": c["type"]} for c in tmpl["columns"]],
            "distributions": tmpl["distributions"],
            "compliance_rules": tmpl["compliance_rules"],
            "temporal": {},
        },
    }
    return schema
