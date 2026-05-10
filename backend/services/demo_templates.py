"""
Pre-built schema templates for Demo mode.
No parsing, no regex, no LLM — just realistic canned data that demonstrates
all features of the app (compliance, distributions, relationships, etc.)

Multi-table templates (tables key) generate a master-detail schema with FK
relationships so the Relationships stage and volume scaling are exercised.
Single-table templates (columns key) keep the original single-entity demos.
"""

from typing import Any, Dict

# ── Multi-table templates ───────────────────────────────────────────────────

MULTI_TEMPLATES: Dict[str, Dict[str, Any]] = {

    "ecommerce": {
        "keywords": [
            "order", "purchase", "transaction", "invoice", "sale", "product",
            "ecommerce", "e-commerce", "checkout", "payment", "customer", "shop",
            "cart", "item", "line item", "catalogue",
        ],
        "entity_type": "customers",
        "volume": 50,          # number of customers
        "per_parent_counts": {"orders": 4, "order_items": 3},
        "frameworks_detected": ["PCI", "PII", "GDPR"],
        "sensitive_detected": True,
        "tables": [
            {
                "table_name": "customers",
                "columns": [
                    {"name": "customer_id",    "type": "integer", "sample_values": ["1001", "1002", "1003"]},
                    {"name": "first_name",     "type": "string",  "sample_values": ["James", "Maria", "Priya"]},
                    {"name": "last_name",      "type": "string",  "sample_values": ["Carter", "Lopez", "Sharma"]},
                    {"name": "email",          "type": "email",   "sample_values": ["james.carter@example.com", "m.lopez@mail.com"]},
                    {"name": "phone",          "type": "phone",   "sample_values": ["+1-555-0142", "+44-20-7946-0958"]},
                    {"name": "country",        "type": "string",  "sample_values": ["United States", "United Kingdom", "India"]},
                    {"name": "city",           "type": "string",  "sample_values": ["New York", "London", "Mumbai"]},
                    {"name": "registered_at",  "type": "date",    "sample_values": ["2022-03-15", "2021-11-08"],
                     "date_format": "YYYY-MM-DD"},
                    {"name": "status",         "type": "enum",    "sample_values": ["active", "inactive"],
                     "enum_values": ["active", "inactive", "suspended"]},
                ],
                "distributions": {
                    "status": {"active": 80, "inactive": 15, "suspended": 5},
                },
                "compliance_rules": {
                    "email": {"action": "fake_realistic", "custom_rule": None, "frameworks": ["PII", "GDPR"]},
                    "phone": {"action": "fake_realistic", "custom_rule": None, "frameworks": ["PII"]},
                },
            },
            {
                "table_name": "orders",
                "columns": [
                    {"name": "order_id",        "type": "integer", "sample_values": ["5001", "5002", "5003"]},
                    {"name": "customer_id",     "type": "integer", "sample_values": ["1001", "1002", "1001"]},
                    {"name": "order_date",      "type": "date",    "sample_values": ["2024-01-15", "2024-02-20"],
                     "date_format": "YYYY-MM-DD"},
                    {"name": "order_status",    "type": "enum",    "sample_values": ["shipped", "pending", "delivered"],
                     "enum_values": ["pending", "processing", "shipped", "delivered", "cancelled"]},
                    {"name": "total_amount",    "type": "float",   "sample_values": ["129.99", "49.50", "320.00"]},
                    {"name": "shipping_address","type": "string",  "sample_values": ["123 Maple St, Austin TX"]},
                    {"name": "payment_method",  "type": "enum",    "sample_values": ["credit_card", "paypal"],
                     "enum_values": ["credit_card", "paypal", "bank_transfer", "crypto"]},
                    {"name": "credit_card",     "type": "string",  "sample_values": ["****-****-****-4821"]},
                    {"name": "cvv",             "type": "string",  "sample_values": ["***"]},
                    {"name": "card_expiry",     "type": "string",  "sample_values": ["12/26", "08/27"]},
                ],
                "distributions": {
                    "order_status": {
                        "pending": 10, "processing": 15, "shipped": 30,
                        "delivered": 40, "cancelled": 5,
                    },
                    "payment_method": {
                        "credit_card": 55, "paypal": 30, "bank_transfer": 12, "crypto": 3,
                    },
                },
                "compliance_rules": {
                    "shipping_address": {"action": "fake_realistic",     "custom_rule": None, "frameworks": ["PII", "GDPR"]},
                    "credit_card":      {"action": "format_preserving",  "custom_rule": None, "frameworks": ["PCI"]},
                    "cvv":              {"action": "redact",              "custom_rule": None, "frameworks": ["PCI"]},
                    "card_expiry":      {"action": "fake_realistic",     "custom_rule": None, "frameworks": ["PCI"]},
                },
            },
            {
                "table_name": "order_items",
                "columns": [
                    {"name": "item_id",      "type": "integer", "sample_values": ["9001", "9002", "9003"]},
                    {"name": "order_id",     "type": "integer", "sample_values": ["5001", "5001", "5002"]},
                    {"name": "product_name", "type": "string",  "sample_values": ["Wireless Headphones", "USB-C Hub", "Desk Lamp"]},
                    {"name": "category",     "type": "enum",    "sample_values": ["electronics", "home"],
                     "enum_values": ["electronics", "clothing", "home", "books", "sports", "beauty"]},
                    {"name": "quantity",     "type": "integer", "sample_values": ["1", "2", "1"]},
                    {"name": "unit_price",   "type": "float",   "sample_values": ["49.99", "129.00", "19.95"]},
                ],
                "distributions": {
                    "category": {
                        "electronics": 35, "clothing": 25, "home": 20,
                        "books": 10, "sports": 7, "beauty": 3,
                    },
                },
                "compliance_rules": {},
            },
        ],
        "relationships": [
            {
                "source_table": "orders",
                "source_column": "customer_id",
                "target_table": "customers",
                "target_column": "customer_id",
                "cardinality": "many_to_one",
                "confidence": 0.95,
            },
            {
                "source_table": "order_items",
                "source_column": "order_id",
                "target_table": "orders",
                "target_column": "order_id",
                "cardinality": "many_to_one",
                "confidence": 0.95,
            },
        ],
    },

}

# ── Single-table templates ──────────────────────────────────────────────────

TEMPLATES: Dict[str, Dict[str, Any]] = {

    "users": {
        "keywords": ["user", "person", "people", "member", "contact", "profile", "account"],
        "entity_type": "users",
        "volume": 100,
        "table_name": "users",
        "columns": [
            {"name": "user_id",       "type": "integer", "sample_values": ["1001", "1002", "1003"]},
            {"name": "first_name",    "type": "string",  "sample_values": ["James", "Maria", "Priya"]},
            {"name": "last_name",     "type": "string",  "sample_values": ["Carter", "Lopez", "Sharma"]},
            {"name": "email",         "type": "email",   "sample_values": ["james.carter@example.com", "m.lopez@mail.com"]},
            {"name": "phone",         "type": "phone",   "sample_values": ["+1-555-0142", "+1-555-0287"]},
            {"name": "gender",        "type": "enum",    "sample_values": ["Male", "Female", "Non-binary"],
             "enum_values": ["Male", "Female", "Non-binary", "Not specified"]},
            {"name": "dob",           "type": "date",    "sample_values": ["1990-04-15", "1985-11-22"]},
            {"name": "ssn",           "type": "string",  "sample_values": ["***-**-4821", "***-**-3374"]},
            {"name": "credit_card",   "type": "string",  "sample_values": ["****-****-****-4821", "****-****-****-3374"]},
            {"name": "ip_address",    "type": "string",  "sample_values": ["192.168.1.1", "10.0.0.42"]},
            {"name": "city",          "type": "string",  "sample_values": ["Austin", "Chicago", "San Jose"]},
            {"name": "country",       "type": "string",  "sample_values": ["United States", "United States", "India"]},
            {"name": "created_at",    "type": "date",    "sample_values": ["2023-06-12", "2024-01-08"]},
        ],
        "distributions": {
            "gender": {"Male": 60, "Female": 30, "Non-binary": 7, "Not specified": 3},
        },
        "compliance_rules": {
            "ssn":         {"action": "mask",              "custom_rule": None, "frameworks": ["PII", "HIPAA"]},
            "dob":         {"action": "format_preserving", "custom_rule": None, "frameworks": ["PII", "GDPR"]},
            "credit_card": {"action": "format_preserving", "custom_rule": None, "frameworks": ["PCI"]},
            "ip_address":  {"action": "mask",              "custom_rule": None, "frameworks": ["PII", "GDPR"]},
            "email":       {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GDPR"]},
            "phone":       {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII"]},
        },
        "frameworks_detected": ["PII", "GDPR", "PCI"],
        "sensitive_detected": True,
    },

    "patients": {
        "keywords": ["patient", "clinical", "health", "medical", "hospital", "diagnosis", "hipaa", "ehr", "emr", "physician"],
        "entity_type": "patients",
        "volume": 50,
        "table_name": "patients",
        "columns": [
            {"name": "patient_id",    "type": "string",  "sample_values": ["PAT-00421", "PAT-00422"]},
            {"name": "first_name",    "type": "string",  "sample_values": ["Dorothy", "Marcus"]},
            {"name": "last_name",     "type": "string",  "sample_values": ["Nguyen", "Williams"]},
            {"name": "dob",           "type": "date",    "sample_values": ["1978-03-15", "1965-11-02"]},
            {"name": "gender",        "type": "enum",    "sample_values": ["Female", "Male"],
             "enum_values": ["Male", "Female", "Non-binary", "Not specified"]},
            {"name": "ssn",           "type": "string",  "sample_values": ["***-**-9182", "***-**-4430"]},
            {"name": "mrn",           "type": "string",  "sample_values": ["MRN-884421", "MRN-884422"]},
            {"name": "diagnosis",     "type": "string",  "sample_values": ["Type 2 Diabetes", "Hypertension"]},
            {"name": "prescription",  "type": "string",  "sample_values": ["Metformin 500mg", "Lisinopril 10mg"]},
            {"name": "physician",     "type": "string",  "sample_values": ["Dr. Sandra Lee", "Dr. Raj Patel"]},
            {"name": "admission_date","type": "date",    "sample_values": ["2024-03-10", "2024-04-22"]},
            {"name": "insurance_id",  "type": "string",  "sample_values": ["INS-7764210", "INS-3382104"]},
            {"name": "email",         "type": "email",   "sample_values": ["d.nguyen@email.com"]},
        ],
        "distributions": {
            "gender": {"Male": 48, "Female": 48, "Non-binary": 3, "Not specified": 1},
        },
        "compliance_rules": {
            "ssn":         {"action": "mask",              "custom_rule": None, "frameworks": ["PII", "HIPAA"]},
            "mrn":         {"action": "format_preserving", "custom_rule": None, "frameworks": ["HIPAA"]},
            "patient_id":  {"action": "format_preserving", "custom_rule": None, "frameworks": ["HIPAA", "PII"]},
            "insurance_id":{"action": "format_preserving", "custom_rule": None, "frameworks": ["HIPAA", "PII"]},
            "dob":         {"action": "format_preserving", "custom_rule": None, "frameworks": ["PII", "GDPR", "HIPAA"]},
            "diagnosis":   {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["HIPAA"]},
            "prescription":{"action": "fake_realistic",    "custom_rule": None, "frameworks": ["HIPAA"]},
            "email":       {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GDPR"]},
        },
        "frameworks_detected": ["PII", "HIPAA", "GDPR"],
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
            {"name": "bonus",       "type": "float",   "sample_values": ["8000", "12000", "5000"]},
            {"name": "hire_date",   "type": "date",    "sample_values": ["2021-03-15", "2019-08-01"]},
            {"name": "manager",     "type": "string",  "sample_values": ["Sarah Kim", "David Osei"]},
            {"name": "phone",       "type": "phone",   "sample_values": ["+1-555-0199"]},
            {"name": "ssn",         "type": "string",  "sample_values": ["***-**-6612"]},
            {"name": "tax_id",      "type": "string",  "sample_values": ["EIN-45-1234567"]},
        ],
        "distributions": {
            "department": {"Engineering": 35, "Sales": 25, "HR": 10, "Finance": 15, "Marketing": 10, "Operations": 5},
        },
        "compliance_rules": {
            "ssn":     {"action": "mask",              "custom_rule": None, "frameworks": ["PII"]},
            "salary":  {"action": "mask",              "custom_rule": None, "frameworks": ["SOX", "PII"]},
            "bonus":   {"action": "mask",              "custom_rule": None, "frameworks": ["SOX", "PII"]},
            "tax_id":  {"action": "format_preserving", "custom_rule": None, "frameworks": ["SOX", "PII"]},
            "email":   {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GDPR"]},
            "phone":   {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII"]},
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
            {"name": "grade",        "type": "string",  "sample_values": ["A", "B+", "A-"]},
            {"name": "enrollment",   "type": "enum",    "sample_values": ["Full-time", "Part-time"],
             "enum_values": ["Full-time", "Part-time", "Online"]},
            {"name": "major",        "type": "string",  "sample_values": ["Computer Science", "Biology"]},
            {"name": "year",         "type": "enum",    "sample_values": ["Sophomore", "Junior"],
             "enum_values": ["Freshman", "Sophomore", "Junior", "Senior", "Graduate"]},
            {"name": "dob",          "type": "date",    "sample_values": ["2001-07-14", "2000-11-30"]},
            {"name": "financial_aid","type": "float",   "sample_values": ["5000", "8500", "0"]},
        ],
        "distributions": {
            "enrollment": {"Full-time": 70, "Part-time": 20, "Online": 10},
            "year": {"Freshman": 25, "Sophomore": 25, "Junior": 20, "Senior": 20, "Graduate": 10},
        },
        "compliance_rules": {
            "student_id":   {"action": "format_preserving", "custom_rule": None, "frameworks": ["FERPA", "PII"]},
            "gpa":          {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["FERPA"]},
            "grade":        {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["FERPA"]},
            "financial_aid":{"action": "mask",              "custom_rule": None, "frameworks": ["FERPA", "SOX"]},
            "dob":          {"action": "format_preserving", "custom_rule": None, "frameworks": ["PII", "GDPR"]},
            "email":        {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GDPR"]},
        },
        "frameworks_detected": ["PII", "FERPA", "GDPR"],
        "sensitive_detected": True,
    },
}

DEFAULT_TEMPLATE = "ecommerce"   # multi-table master-detail is the showcase default


def pick_template(context_text: str) -> tuple:
    """
    Returns (template_key, is_multi) — chooses the best template across both
    multi-table and single-table dicts based on keyword matches.
    """
    text = context_text.lower() if context_text else ""

    best_key = DEFAULT_TEMPLATE
    best_score = 0
    best_multi = True

    for key, tmpl in MULTI_TEMPLATES.items():
        score = sum(1 for kw in tmpl["keywords"] if kw in text)
        if score > best_score:
            best_score, best_key, best_multi = score, key, True

    for key, tmpl in TEMPLATES.items():
        score = sum(1 for kw in tmpl["keywords"] if kw in text)
        if score > best_score:
            best_score, best_key, best_multi = score, key, False

    return best_key, best_multi


def _build_column(c: Dict[str, Any], compliance_rules: Dict[str, Any]) -> Dict[str, Any]:
    """Attach compliance metadata to a column definition."""
    from services.compliance_detector import detect_compliance

    compliance = detect_compliance(c["name"], c.get("sample_values", []))
    stored_rule = compliance_rules.get(c["name"])
    if stored_rule and stored_rule.get("action") not in (None, "fake_realistic"):
        if compliance["default_action"] == "fake_realistic" or not compliance["is_sensitive"]:
            compliance = {**compliance, "default_action": stored_rule["action"]}
            if not compliance["is_sensitive"]:
                compliance = {
                    **compliance,
                    "is_sensitive": True,
                    "frameworks": stored_rule.get("frameworks", ["PII"]),
                    "field_type": c["name"],
                    "recommendations": {},
                    "confidence": 0.9,
                }

    col: Dict[str, Any] = {
        "name": c["name"],
        "type": c["type"],
        "sample_values": c.get("sample_values", []),
        "pattern": c["name"],
        "enum_values": c.get("enum_values", []),
        "pii": compliance,
    }
    if c.get("date_format"):
        col["date_format"] = c["date_format"]
    return col


def get_demo_schema(context_text: str = "") -> Dict[str, Any]:
    """
    Return a pre-built demo schema with no parsing or LLM calls.
    Picks the most relevant template from the context keywords.
    Multi-table templates produce a relational schema with FK relationships.
    """
    key, is_multi = pick_template(context_text)

    if is_multi:
        tmpl = MULTI_TEMPLATES[key]

        # Build each table
        schema_tables = []
        all_compliance_rules: Dict[str, Any] = {}
        all_distributions: Dict[str, Any] = {}

        for tbl in tmpl["tables"]:
            tname = tbl["table_name"]
            t_rules = tbl.get("compliance_rules", {})
            cols = [_build_column(c, t_rules) for c in tbl["columns"]]
            schema_tables.append({
                "table_name": tname,
                "filename": None,
                "columns": cols,
                "row_count": 0,
            })
            # Merge compliance rules with table prefix for frontend
            for col_name, rule in t_rules.items():
                all_compliance_rules[col_name] = rule
            # Keep distributions as raw percentages (0-100); the frontend divides by 100
            for col_name, dist in tbl.get("distributions", {}).items():
                tkey = f"{tname}.{col_name}"
                all_distributions[tkey] = dist

        return {
            "tables": schema_tables,
            "relationships": tmpl["relationships"],
            "pii_detected": tmpl["sensitive_detected"],
            "sensitive_detected": tmpl["sensitive_detected"],
            "frameworks_detected": tmpl["frameworks_detected"],
            "domain_frameworks": [],
            "context": context_text,
            "extracted": {
                "volume": tmpl["volume"],
                "entity_type": tmpl["entity_type"],
                "columns": [
                    {"name": c["name"], "type": c["type"]}
                    for tbl in tmpl["tables"]
                    for c in tbl["columns"]
                ],
                "distributions": all_distributions,
                "compliance_rules": all_compliance_rules,
                "temporal": {},
                "per_parent_counts": tmpl.get("per_parent_counts", {}),
            },
            "llm_warning": None,
        }

    else:
        # Single-table template (original behaviour)
        tmpl = TEMPLATES[key]
        cols = [_build_column(c, tmpl["compliance_rules"]) for c in tmpl["columns"]]

        return {
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
                # Raw percentages (0-100); frontend divides by 100 on ingest
                "distributions": tmpl["distributions"],
                "compliance_rules": tmpl["compliance_rules"],
                "temporal": {},
            },
            "llm_warning": None,
        }
