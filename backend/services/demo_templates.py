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
            # Also catch generic user/contact/profile queries — ecommerce is the
            # best multi-table showcase for those concepts
            "user", "person", "people", "member", "contact", "profile", "account",
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
                "source_table": "customers",
                "source_column": "customer_id",
                "target_table": "orders",
                "target_column": "customer_id",
                "cardinality": "one_to_many",
                "confidence": 0.95,
            },
            {
                "source_table": "orders",
                "source_column": "order_id",
                "target_table": "order_items",
                "target_column": "order_id",
                "cardinality": "one_to_many",
                "confidence": 0.95,
            },
        ],
    },

    "healthcare": {
        "keywords": [
            "patient", "clinical", "health", "medical", "hospital",
            "diagnosis", "hipaa", "ehr", "emr", "physician", "visit",
        ],
        "entity_type": "patients",
        "volume": 40,
        "per_parent_counts": {"visits": 4, "prescriptions": 3},
        "frameworks_detected": ["HIPAA", "PII", "GDPR"],
        "sensitive_detected": True,
        "tables": [
            {
                "table_name": "patients",
                "columns": [
                    {"name": "patient_id",    "type": "string",  "sample_values": ["PAT-00421", "PAT-00422"]},
                    {"name": "first_name",    "type": "string",  "sample_values": ["Dorothy", "Marcus"]},
                    {"name": "last_name",     "type": "string",  "sample_values": ["Nguyen", "Williams"]},
                    {"name": "dob",           "type": "date",    "sample_values": ["1978-03-15", "1965-11-02"],
                     "date_format": "YYYY-MM-DD"},
                    {"name": "gender",        "type": "enum",    "sample_values": ["Female", "Male"],
                     "enum_values": ["Male", "Female", "Non-binary", "Not specified"]},
                    {"name": "ssn",           "type": "string",  "sample_values": ["***-**-9182", "***-**-4430"]},
                    {"name": "email",         "type": "email",   "sample_values": ["d.nguyen@email.com"]},
                    {"name": "phone",         "type": "phone",   "sample_values": ["+1-555-0177"]},
                    {"name": "insurance_id",  "type": "string",  "sample_values": ["INS-7764210", "INS-3382104"]},
                    {"name": "blood_type",    "type": "enum",    "sample_values": ["A+", "O-"],
                     "enum_values": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]},
                ],
                "distributions": {
                    "gender": {"Male": 48, "Female": 48, "Non-binary": 3, "Not specified": 1},
                    "blood_type": {"A+": 30, "O+": 38, "B+": 9, "AB+": 3, "A-": 8, "O-": 7, "B-": 2, "AB-": 1},
                },
                "compliance_rules": {
                    "ssn":         {"action": "mask",              "custom_rule": None, "frameworks": ["PII", "HIPAA"]},
                    "patient_id":  {"action": "format_preserving", "custom_rule": None, "frameworks": ["HIPAA", "PII"]},
                    "insurance_id":{"action": "format_preserving", "custom_rule": None, "frameworks": ["HIPAA", "PII"]},
                    "dob":         {"action": "format_preserving", "custom_rule": None, "frameworks": ["PII", "GDPR", "HIPAA"]},
                    "email":       {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GDPR"]},
                    "phone":       {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII"]},
                },
            },
            {
                "table_name": "visits",
                "columns": [
                    {"name": "visit_id",     "type": "integer", "sample_values": ["8001", "8002"]},
                    {"name": "patient_id",   "type": "string",  "sample_values": ["PAT-00421", "PAT-00422"]},
                    {"name": "visit_date",   "type": "date",    "sample_values": ["2024-03-10", "2024-04-22"],
                     "date_format": "YYYY-MM-DD"},
                    {"name": "physician",    "type": "string",  "sample_values": ["Dr. Sandra Lee", "Dr. Raj Patel"]},
                    {"name": "diagnosis",    "type": "string",  "sample_values": ["Type 2 Diabetes", "Hypertension"]},
                    {"name": "visit_type",   "type": "enum",    "sample_values": ["routine", "urgent"],
                     "enum_values": ["routine", "urgent", "follow-up", "specialist", "emergency"]},
                    {"name": "notes",        "type": "string",  "sample_values": ["Patient reports improvement"]},
                ],
                "distributions": {
                    "visit_type": {"routine": 45, "follow-up": 30, "urgent": 15, "specialist": 8, "emergency": 2},
                },
                "compliance_rules": {
                    "diagnosis": {"action": "fake_realistic", "custom_rule": None, "frameworks": ["HIPAA"]},
                    "notes":     {"action": "fake_realistic", "custom_rule": None, "frameworks": ["HIPAA"]},
                },
            },
            {
                "table_name": "prescriptions",
                "columns": [
                    {"name": "prescription_id", "type": "integer", "sample_values": ["7001", "7002"]},
                    {"name": "patient_id",       "type": "string",  "sample_values": ["PAT-00421"]},
                    {"name": "drug_name",        "type": "string",  "sample_values": ["Metformin 500mg", "Lisinopril 10mg"]},
                    {"name": "dosage",           "type": "string",  "sample_values": ["500mg", "10mg"]},
                    {"name": "frequency",        "type": "enum",    "sample_values": ["daily", "twice daily"],
                     "enum_values": ["daily", "twice daily", "weekly", "as needed"]},
                    {"name": "prescribed_date",  "type": "date",    "sample_values": ["2024-03-10"],
                     "date_format": "YYYY-MM-DD"},
                    {"name": "refills",          "type": "integer", "sample_values": ["3", "1", "0"]},
                ],
                "distributions": {
                    "frequency": {"daily": 50, "twice daily": 30, "weekly": 12, "as needed": 8},
                },
                "compliance_rules": {
                    "drug_name": {"action": "fake_realistic", "custom_rule": None, "frameworks": ["HIPAA"]},
                    "dosage":    {"action": "fake_realistic", "custom_rule": None, "frameworks": ["HIPAA"]},
                },
            },
        ],
        "relationships": [
            {
                "source_table": "patients",
                "source_column": "patient_id",
                "target_table": "visits",
                "target_column": "patient_id",
                "cardinality": "one_to_many",
                "confidence": 0.95,
            },
            {
                "source_table": "patients",
                "source_column": "patient_id",
                "target_table": "prescriptions",
                "target_column": "patient_id",
                "cardinality": "one_to_many",
                "confidence": 0.95,
            },
        ],
    },

    "hr": {
        "keywords": [
            "employee", "staff", "hr", "payroll", "salary", "workforce",
            "department", "hire", "leave", "timesheet",
        ],
        "entity_type": "employees",
        "volume": 60,
        "per_parent_counts": {"leave_requests": 3},
        "frameworks_detected": ["SOX", "PII", "GDPR"],
        "sensitive_detected": True,
        "tables": [
            {
                "table_name": "employees",
                "columns": [
                    {"name": "employee_id", "type": "string",  "sample_values": ["EMP-0041", "EMP-0042"]},
                    {"name": "first_name",  "type": "string",  "sample_values": ["Carlos", "Aisha"]},
                    {"name": "last_name",   "type": "string",  "sample_values": ["Rivera", "Okonkwo"]},
                    {"name": "email",       "type": "email",   "sample_values": ["c.rivera@corp.com"]},
                    {"name": "department",  "type": "enum",    "sample_values": ["Engineering", "Sales", "HR"],
                     "enum_values": ["Engineering", "Sales", "HR", "Finance", "Marketing", "Operations"]},
                    {"name": "job_title",   "type": "string",  "sample_values": ["Software Engineer", "Sales Manager"]},
                    {"name": "salary",      "type": "float",   "sample_values": ["85000", "92000", "74000"]},
                    {"name": "hire_date",   "type": "date",    "sample_values": ["2021-03-15", "2019-08-01"],
                     "date_format": "YYYY-MM-DD"},
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
                    "tax_id":  {"action": "format_preserving", "custom_rule": None, "frameworks": ["SOX", "PII"]},
                    "email":   {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GDPR"]},
                    "phone":   {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII"]},
                },
            },
            {
                "table_name": "leave_requests",
                "columns": [
                    {"name": "request_id",   "type": "integer", "sample_values": ["3001", "3002"]},
                    {"name": "employee_id",  "type": "string",  "sample_values": ["EMP-0041", "EMP-0042"]},
                    {"name": "leave_type",   "type": "enum",    "sample_values": ["annual", "sick"],
                     "enum_values": ["annual", "sick", "parental", "unpaid", "bereavement"]},
                    {"name": "start_date",   "type": "date",    "sample_values": ["2024-06-10"],
                     "date_format": "YYYY-MM-DD"},
                    {"name": "end_date",     "type": "date",    "sample_values": ["2024-06-14"],
                     "date_format": "YYYY-MM-DD"},
                    {"name": "days",         "type": "integer", "sample_values": ["5", "1", "3"]},
                    {"name": "status",       "type": "enum",    "sample_values": ["approved", "pending"],
                     "enum_values": ["pending", "approved", "rejected", "cancelled"]},
                ],
                "distributions": {
                    "leave_type": {"annual": 50, "sick": 30, "parental": 10, "unpaid": 7, "bereavement": 3},
                    "status":     {"approved": 70, "pending": 20, "rejected": 7, "cancelled": 3},
                },
                "compliance_rules": {},
            },
        ],
        "relationships": [
            {
                "source_table": "employees",
                "source_column": "employee_id",
                "target_table": "leave_requests",
                "target_column": "employee_id",
                "cardinality": "one_to_many",
                "confidence": 0.95,
            },
        ],
    },

    "banking": {
        "keywords": [
            "bank", "banking", "account", "transaction", "loan", "mortgage",
            "credit", "debit", "wire transfer", "swift", "iban", "routing",
            "ledger", "balance", "deposit", "withdrawal", "aml", "kyc",
            "glba", "fintech", "bsa", "sanctions",
        ],
        "entity_type": "customers",
        "volume": 50,
        "per_parent_counts": {"accounts": 2, "transactions": 8, "loans": 1},
        "frameworks_detected": ["PCI", "PII", "GDPR", "SOX", "GLBA"],
        "sensitive_detected": True,
        "tables": [
            {
                "table_name": "customers",
                "columns": [
                    {"name": "customer_id",    "type": "string",  "sample_values": ["CUST-10041", "CUST-10042", "CUST-10043"]},
                    {"name": "first_name",     "type": "string",  "sample_values": ["Sofia", "Marcus", "Wei"]},
                    {"name": "last_name",      "type": "string",  "sample_values": ["Martinez", "Johnson", "Chen"]},
                    {"name": "email",          "type": "email",   "sample_values": ["s.martinez@email.com", "m.johnson@mail.com"]},
                    {"name": "phone",          "type": "phone",   "sample_values": ["+1-555-0183", "+44-20-7946-0712"]},
                    {"name": "date_of_birth",  "type": "date",    "sample_values": ["1982-06-14", "1975-11-30"],
                     "date_format": "YYYY-MM-DD"},
                    {"name": "ssn",            "type": "string",  "sample_values": ["***-**-7841", "***-**-2293"]},
                    {"name": "address",        "type": "string",  "sample_values": ["210 Elm St, Chicago IL 60601"]},
                    {"name": "country",        "type": "string",  "sample_values": ["United States", "United Kingdom", "Singapore"]},
                    {"name": "kyc_status",     "type": "enum",    "sample_values": ["verified", "pending"],
                     "enum_values": ["verified", "pending", "rejected", "under_review"]},
                    {"name": "risk_rating",    "type": "enum",    "sample_values": ["low", "medium"],
                     "enum_values": ["low", "medium", "high"]},
                    {"name": "customer_since", "type": "date",    "sample_values": ["2018-03-01", "2015-07-22"],
                     "date_format": "YYYY-MM-DD"},
                ],
                "distributions": {
                    "kyc_status":  {"verified": 82, "pending": 10, "rejected": 4, "under_review": 4},
                    "risk_rating": {"low": 70, "medium": 22, "high": 8},
                },
                "compliance_rules": {
                    "ssn":         {"action": "mask",              "custom_rule": None, "frameworks": ["PII", "GLBA"]},
                    "date_of_birth":{"action": "format_preserving","custom_rule": None, "frameworks": ["PII", "GDPR", "GLBA"]},
                    "address":     {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GDPR", "GLBA"]},
                    "email":       {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GDPR"]},
                    "phone":       {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GLBA"]},
                },
            },
            {
                "table_name": "accounts",
                "columns": [
                    {"name": "account_id",     "type": "string",  "sample_values": ["ACC-88001", "ACC-88002", "ACC-88003"]},
                    {"name": "customer_id",    "type": "string",  "sample_values": ["CUST-10041", "CUST-10042"]},
                    {"name": "account_type",   "type": "enum",    "sample_values": ["checking", "savings"],
                     "enum_values": ["checking", "savings", "money_market", "cd", "credit"]},
                    {"name": "account_number", "type": "string",  "sample_values": ["****3821", "****7740"]},
                    {"name": "routing_number", "type": "string",  "sample_values": ["****4400", "****2291"]},
                    {"name": "iban",           "type": "string",  "sample_values": ["GB29****1872", "DE89****7461"]},
                    {"name": "balance",        "type": "float",   "sample_values": ["12450.00", "3200.50", "87600.00"]},
                    {"name": "currency",       "type": "enum",    "sample_values": ["USD", "GBP"],
                     "enum_values": ["USD", "EUR", "GBP", "SGD", "CHF"]},
                    {"name": "status",         "type": "enum",    "sample_values": ["active", "active", "frozen"],
                     "enum_values": ["active", "frozen", "closed", "dormant"]},
                    {"name": "opened_date",    "type": "date",    "sample_values": ["2018-03-01", "2020-11-15"],
                     "date_format": "YYYY-MM-DD"},
                ],
                "distributions": {
                    "account_type": {"checking": 40, "savings": 35, "money_market": 12, "cd": 8, "credit": 5},
                    "status":       {"active": 85, "frozen": 6, "dormant": 7, "closed": 2},
                    "currency":     {"USD": 60, "EUR": 15, "GBP": 12, "SGD": 8, "CHF": 5},
                },
                "compliance_rules": {
                    "account_number": {"action": "format_preserving", "custom_rule": None, "frameworks": ["PCI", "GLBA"]},
                    "routing_number": {"action": "format_preserving", "custom_rule": None, "frameworks": ["PCI", "GLBA"]},
                    "iban":           {"action": "format_preserving", "custom_rule": None, "frameworks": ["PCI", "GDPR", "GLBA"]},
                    "balance":        {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["SOX", "GLBA"]},
                },
            },
            {
                "table_name": "transactions",
                "columns": [
                    {"name": "transaction_id",   "type": "string",  "sample_values": ["TXN-20240301-0001", "TXN-20240301-0002"]},
                    {"name": "account_id",        "type": "string",  "sample_values": ["ACC-88001", "ACC-88002"]},
                    {"name": "transaction_date",  "type": "date",    "sample_values": ["2024-03-01", "2024-03-02"],
                     "date_format": "YYYY-MM-DD"},
                    {"name": "transaction_type",  "type": "enum",    "sample_values": ["debit", "credit"],
                     "enum_values": ["debit", "credit", "wire_transfer", "ach", "fee", "interest"]},
                    {"name": "amount",            "type": "float",   "sample_values": ["250.00", "1200.00", "45.50"]},
                    {"name": "currency",          "type": "enum",    "sample_values": ["USD", "EUR"],
                     "enum_values": ["USD", "EUR", "GBP", "SGD", "CHF"]},
                    {"name": "merchant_name",     "type": "string",  "sample_values": ["Whole Foods Market", "Amazon", "Shell"]},
                    {"name": "merchant_category", "type": "enum",    "sample_values": ["groceries", "retail", "fuel"],
                     "enum_values": ["groceries", "retail", "dining", "fuel", "travel", "utilities", "healthcare", "other"]},
                    {"name": "status",            "type": "enum",    "sample_values": ["completed", "completed", "pending"],
                     "enum_values": ["completed", "pending", "failed", "reversed"]},
                    {"name": "reference_number",  "type": "string",  "sample_values": ["REF-7823401", "REF-7823402"]},
                    {"name": "swift_code",        "type": "string",  "sample_values": ["BOFAUS3N", "CHASUS33"]},
                ],
                "distributions": {
                    "transaction_type":  {"debit": 50, "credit": 30, "wire_transfer": 8, "ach": 7, "fee": 3, "interest": 2},
                    "merchant_category": {"groceries": 20, "retail": 25, "dining": 18, "fuel": 10, "travel": 8, "utilities": 9, "healthcare": 5, "other": 5},
                    "status":            {"completed": 88, "pending": 7, "failed": 3, "reversed": 2},
                },
                "compliance_rules": {
                    "amount":       {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["SOX", "GLBA", "PCI"]},
                    "swift_code":   {"action": "format_preserving", "custom_rule": None, "frameworks": ["PCI", "GLBA"]},
                },
            },
            {
                "table_name": "loans",
                "columns": [
                    {"name": "loan_id",          "type": "string",  "sample_values": ["LOAN-55001", "LOAN-55002"]},
                    {"name": "customer_id",       "type": "string",  "sample_values": ["CUST-10041", "CUST-10042"]},
                    {"name": "loan_type",         "type": "enum",    "sample_values": ["mortgage", "personal"],
                     "enum_values": ["mortgage", "personal", "auto", "student", "business"]},
                    {"name": "principal_amount",  "type": "float",   "sample_values": ["250000.00", "15000.00", "42000.00"]},
                    {"name": "interest_rate",     "type": "float",   "sample_values": ["6.75", "11.50", "5.25"]},
                    {"name": "term_months",       "type": "integer", "sample_values": ["360", "60", "84"]},
                    {"name": "monthly_payment",   "type": "float",   "sample_values": ["1643.00", "325.00", "589.00"]},
                    {"name": "outstanding_balance","type": "float",  "sample_values": ["241500.00", "12300.00"]},
                    {"name": "loan_status",       "type": "enum",    "sample_values": ["current", "current", "delinquent"],
                     "enum_values": ["current", "delinquent", "default", "paid_off", "charged_off"]},
                    {"name": "origination_date",  "type": "date",    "sample_values": ["2021-05-15", "2023-01-10"],
                     "date_format": "YYYY-MM-DD"},
                    {"name": "credit_score",      "type": "integer", "sample_values": ["740", "620", "810"]},
                ],
                "distributions": {
                    "loan_type":   {"mortgage": 45, "personal": 25, "auto": 18, "student": 8, "business": 4},
                    "loan_status": {"current": 80, "delinquent": 10, "default": 4, "paid_off": 5, "charged_off": 1},
                },
                "compliance_rules": {
                    "principal_amount":   {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["SOX", "GLBA"]},
                    "outstanding_balance":{"action": "fake_realistic",    "custom_rule": None, "frameworks": ["SOX", "GLBA"]},
                    "monthly_payment":    {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["SOX", "GLBA"]},
                    "credit_score":       {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["GLBA", "PII"]},
                    "interest_rate":      {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["SOX", "GLBA"]},
                },
            },
        ],
        "relationships": [
            {
                "source_table": "customers",
                "source_column": "customer_id",
                "target_table": "accounts",
                "target_column": "customer_id",
                "cardinality": "one_to_many",
                "confidence": 0.97,
            },
            {
                "source_table": "accounts",
                "source_column": "account_id",
                "target_table": "transactions",
                "target_column": "account_id",
                "cardinality": "one_to_many",
                "confidence": 0.97,
            },
            {
                "source_table": "customers",
                "source_column": "customer_id",
                "target_table": "loans",
                "target_column": "customer_id",
                "cardinality": "one_to_many",
                "confidence": 0.95,
            },
        ],
    },

    "education": {
        "keywords": [
            "student", "school", "university", "grade", "course",
            "academic", "enrollment", "gpa", "ferpa", "class", "module",
        ],
        "entity_type": "students",
        "volume": 50,
        "per_parent_counts": {"enrollments": 4},
        "frameworks_detected": ["FERPA", "PII", "GDPR"],
        "sensitive_detected": True,
        "tables": [
            {
                "table_name": "students",
                "columns": [
                    {"name": "student_id",   "type": "string",  "sample_values": ["STU-20041", "STU-20042"]},
                    {"name": "first_name",   "type": "string",  "sample_values": ["Mei", "Jordan"]},
                    {"name": "last_name",    "type": "string",  "sample_values": ["Zhang", "Brooks"]},
                    {"name": "email",        "type": "email",   "sample_values": ["mzhang@university.edu"]},
                    {"name": "dob",          "type": "date",    "sample_values": ["2001-07-14"],
                     "date_format": "YYYY-MM-DD"},
                    {"name": "enrollment_status", "type": "enum", "sample_values": ["Full-time", "Part-time"],
                     "enum_values": ["Full-time", "Part-time", "Online"]},
                    {"name": "major",        "type": "string",  "sample_values": ["Computer Science", "Biology"]},
                    {"name": "year",         "type": "enum",    "sample_values": ["Sophomore", "Junior"],
                     "enum_values": ["Freshman", "Sophomore", "Junior", "Senior", "Graduate"]},
                    {"name": "gpa",          "type": "float",   "sample_values": ["3.7", "2.9", "3.4"]},
                    {"name": "financial_aid","type": "float",   "sample_values": ["5000", "8500", "0"]},
                ],
                "distributions": {
                    "enrollment_status": {"Full-time": 70, "Part-time": 20, "Online": 10},
                    "year": {"Freshman": 25, "Sophomore": 25, "Junior": 20, "Senior": 20, "Graduate": 10},
                },
                "compliance_rules": {
                    "student_id":   {"action": "format_preserving", "custom_rule": None, "frameworks": ["FERPA", "PII"]},
                    "gpa":          {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["FERPA"]},
                    "financial_aid":{"action": "mask",              "custom_rule": None, "frameworks": ["FERPA", "SOX"]},
                    "dob":          {"action": "format_preserving", "custom_rule": None, "frameworks": ["PII", "GDPR"]},
                    "email":        {"action": "fake_realistic",    "custom_rule": None, "frameworks": ["PII", "GDPR"]},
                },
            },
            {
                "table_name": "enrollments",
                "columns": [
                    {"name": "enrollment_id", "type": "integer", "sample_values": ["6001", "6002"]},
                    {"name": "student_id",    "type": "string",  "sample_values": ["STU-20041"]},
                    {"name": "course_code",   "type": "string",  "sample_values": ["CS101", "BIO202"]},
                    {"name": "course_name",   "type": "string",  "sample_values": ["Introduction to CS", "Cell Biology"]},
                    {"name": "semester",      "type": "enum",    "sample_values": ["Fall 2024", "Spring 2024"],
                     "enum_values": ["Fall 2024", "Spring 2025", "Summer 2025"]},
                    {"name": "grade",         "type": "enum",    "sample_values": ["A", "B+", "A-"],
                     "enum_values": ["A", "A-", "B+", "B", "B-", "C+", "C", "D", "F", "W"]},
                    {"name": "credits",       "type": "integer", "sample_values": ["3", "4", "2"]},
                ],
                "distributions": {
                    "grade": {"A": 20, "A-": 15, "B+": 18, "B": 17, "B-": 10, "C+": 8, "C": 6, "D": 3, "F": 2, "W": 1},
                    "semester": {"Fall 2024": 45, "Spring 2025": 45, "Summer 2025": 10},
                },
                "compliance_rules": {
                    "grade": {"action": "fake_realistic", "custom_rule": None, "frameworks": ["FERPA"]},
                },
            },
        ],
        "relationships": [
            {
                "source_table": "students",
                "source_column": "student_id",
                "target_table": "enrollments",
                "target_column": "student_id",
                "cardinality": "one_to_many",
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
    Returns (template_key, is_multi) — always picks a multi-table template so
    demo mode always showcases master-detail relationships.
    Falls back to DEFAULT_TEMPLATE (ecommerce) when nothing matches.
    """
    text = context_text.lower() if context_text else ""

    best_key = DEFAULT_TEMPLATE
    best_score = 0

    for key, tmpl in MULTI_TEMPLATES.items():
        score = sum(1 for kw in tmpl["keywords"] if kw in text)
        if score > best_score:
            best_score, best_key = score, key

    return best_key, True  # always multi-table


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
