"""
Tests for demo_templates.py

Covers regressions from:
- Bug: demo mode compliance stage showed "no fields require special handling"
  because template fields had default_action="fake_realistic" from detect_compliance
  even though the template stored non-trivial actions (mask/format_preserving).
- Template keyword selection.
- Each template must have 2+ non-trivial compliance fields so the Compliance
  stage has real decisions to demonstrate.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.demo_templates import get_demo_schema, pick_template, TEMPLATES


# ─── Template selection ────────────────────────────────────────────────────────

class TestPickTemplate:

    def test_empty_context_returns_default(self):
        assert pick_template("") == "users"
        assert pick_template(None) == "users"

    def test_patient_keywords(self):
        assert pick_template("patient records for a hospital") == "patients"
        assert pick_template("clinical data with diagnosis") == "patients"

    def test_order_keywords(self):
        assert pick_template("e-commerce orders with checkout") == "orders"
        assert pick_template("purchase transactions and invoices") == "orders"

    def test_employee_keywords(self):
        assert pick_template("employee payroll and HR records") == "employees"
        assert pick_template("staff salary and department data") == "employees"

    def test_student_keywords(self):
        assert pick_template("student GPA and academic enrollment") == "students"
        assert pick_template("university FERPA records") == "students"

    def test_user_keywords(self):
        assert pick_template("customer contact list with email") == "users"

    def test_best_match_wins(self):
        # "patient" and "hospital" both score for patients, not users
        result = pick_template("100 patients in a hospital with diagnosis")
        assert result == "patients"


# ─── Schema structure ─────────────────────────────────────────────────────────

class TestGetDemoSchema:

    def test_returns_tables(self):
        schema = get_demo_schema("users with email and phone")
        assert "tables" in schema
        assert len(schema["tables"]) == 1

    def test_columns_have_pii_field(self):
        schema = get_demo_schema()
        for col in schema["tables"][0]["columns"]:
            assert "pii" in col, f"Column '{col['name']}' missing 'pii' field"

    def test_sensitive_detected_true(self):
        schema = get_demo_schema()
        assert schema["sensitive_detected"] is True
        assert schema["pii_detected"] is True

    def test_extracted_has_compliance_rules(self):
        schema = get_demo_schema()
        assert "compliance_rules" in schema["extracted"]
        assert len(schema["extracted"]["compliance_rules"]) > 0

    def test_extracted_has_distributions(self):
        schema = get_demo_schema("users")
        assert "distributions" in schema["extracted"]

    def test_frameworks_detected_populated(self):
        schema = get_demo_schema("users")
        assert len(schema["frameworks_detected"]) > 0


# ─── Non-trivial compliance fields (regression for compliance stage bug) ──────

NON_TRIVIAL_ACTIONS = {"mask", "format_preserving", "redact"}


def _nontrivial_count(schema: dict) -> int:
    """Count columns whose pii.default_action is non-trivial."""
    count = 0
    for col in schema["tables"][0]["columns"]:
        action = col.get("pii", {}).get("default_action")
        if action in NON_TRIVIAL_ACTIONS:
            count += 1
    return count


def _nontrivial_rules_count(schema: dict) -> int:
    """Count compliance_rules entries with non-trivial action."""
    count = 0
    for rule in schema["extracted"]["compliance_rules"].values():
        if rule.get("action") in NON_TRIVIAL_ACTIONS:
            count += 1
    return count


class TestComplianceFieldsInDemoTemplates:
    """
    Regression: each demo template must have at least 2 fields that would
    show up in the ComplianceReviewPanel as 'needing explicit decisions'
    (i.e. pii.default_action != fake_realistic OR stored action != fake_realistic).
    This ensures the Compliance stage is never empty in demo mode.
    """

    @pytest.mark.parametrize("keyword,template_key", [
        ("users with name email ssn", "users"),
        ("patient clinical hospital diagnosis", "patients"),
        ("orders checkout payment credit card", "orders"),
        ("employee payroll salary HR", "employees"),
        ("student gpa academic ferpa", "students"),
    ])
    def test_at_least_2_nontrivial_compliance_fields(self, keyword, template_key):
        schema = get_demo_schema(keyword)
        nontrivial = _nontrivial_count(schema)
        rules_nontrivial = _nontrivial_rules_count(schema)
        # Either the column metadata OR the stored rules should have 2+ non-trivial entries
        assert max(nontrivial, rules_nontrivial) >= 2, (
            f"Template '{template_key}' has only {max(nontrivial, rules_nontrivial)} "
            f"non-trivial compliance fields — need at least 2 for a meaningful "
            f"compliance stage demo. column non-trivial: {nontrivial}, "
            f"rules non-trivial: {rules_nontrivial}"
        )

    def test_users_has_mask_or_format_preserving_on_ssn(self):
        schema = get_demo_schema("users")
        cols = {c["name"]: c for c in schema["tables"][0]["columns"]}
        assert "ssn" in cols, "users template must have ssn column"
        ssn_action = cols["ssn"]["pii"].get("default_action")
        assert ssn_action in NON_TRIVIAL_ACTIONS, (
            f"SSN default_action should be non-trivial, got: {ssn_action}"
        )

    def test_patients_has_hipaa_fields_with_nontrivial_action(self):
        schema = get_demo_schema("patient hospital")
        cols = {c["name"]: c for c in schema["tables"][0]["columns"]}
        hipaa_nontrivial = [
            name for name, col in cols.items()
            if "HIPAA" in col.get("pii", {}).get("frameworks", [])
            and col["pii"].get("default_action") in NON_TRIVIAL_ACTIONS
        ]
        assert len(hipaa_nontrivial) >= 2, (
            f"patients template needs 2+ HIPAA fields with non-trivial action, "
            f"got: {hipaa_nontrivial}"
        )

    def test_orders_has_pci_redact_cvv(self):
        schema = get_demo_schema("orders checkout payment")
        cols = {c["name"]: c for c in schema["tables"][0]["columns"]}
        assert "cvv" in cols, "orders template must have cvv column"
        cvv_action = cols["cvv"]["pii"].get("default_action")
        assert cvv_action in NON_TRIVIAL_ACTIONS, (
            f"CVV should be redacted/masked, got: {cvv_action}"
        )

    def test_employees_has_sox_salary_masked(self):
        schema = get_demo_schema("employee payroll salary")
        cols = {c["name"]: c for c in schema["tables"][0]["columns"]}
        assert "salary" in cols, "employees template must have salary column"
        salary_action = cols["salary"]["pii"].get("default_action")
        assert salary_action in NON_TRIVIAL_ACTIONS, (
            f"Salary should be masked (SOX), got: {salary_action}"
        )

    def test_students_has_ferpa_student_id(self):
        schema = get_demo_schema("student gpa ferpa")
        cols = {c["name"]: c for c in schema["tables"][0]["columns"]}
        assert "student_id" in cols
        student_id_action = cols["student_id"]["pii"].get("default_action")
        assert student_id_action in NON_TRIVIAL_ACTIONS


# ─── Template completeness ────────────────────────────────────────────────────

class TestTemplateCompleteness:
    """Every template must meet minimum quality criteria."""

    @pytest.mark.parametrize("key,tmpl", TEMPLATES.items())
    def test_template_has_required_keys(self, key, tmpl):
        for field in ("keywords", "entity_type", "volume", "table_name",
                      "columns", "distributions", "compliance_rules",
                      "frameworks_detected", "sensitive_detected"):
            assert field in tmpl, f"Template '{key}' missing field '{field}'"

    @pytest.mark.parametrize("key,tmpl", TEMPLATES.items())
    def test_template_has_at_least_5_columns(self, key, tmpl):
        assert len(tmpl["columns"]) >= 5, (
            f"Template '{key}' has only {len(tmpl['columns'])} columns"
        )

    @pytest.mark.parametrize("key,tmpl", TEMPLATES.items())
    def test_template_has_at_least_2_compliance_rules(self, key, tmpl):
        assert len(tmpl["compliance_rules"]) >= 2, (
            f"Template '{key}' has only {len(tmpl['compliance_rules'])} compliance rules"
        )

    @pytest.mark.parametrize("key,tmpl", TEMPLATES.items())
    def test_template_sensitive_detected_is_true(self, key, tmpl):
        assert tmpl["sensitive_detected"] is True

    @pytest.mark.parametrize("key,tmpl", TEMPLATES.items())
    def test_template_frameworks_detected_not_empty(self, key, tmpl):
        assert len(tmpl["frameworks_detected"]) >= 2
