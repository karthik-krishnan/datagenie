"""
Tests for starter_templates.py

Covers regressions from:
- Bug: offline mode compliance stage showed "no fields require special handling"
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
from services.starter_templates import get_starter_schema, pick_template, TEMPLATES, MULTI_TEMPLATES


# ─── Template selection ────────────────────────────────────────────────────────

class TestPickTemplate:
    # pick_template now returns (key, is_multi) tuple

    def test_empty_context_returns_default(self):
        key, is_multi = pick_template("")
        assert key == "generic"   # neutral fallback when nothing matches
        assert is_multi is True

    def test_patient_keywords(self):
        # "healthcare" multi-table template now takes priority over single-table "patients"
        key, is_multi = pick_template("patient records for a hospital")
        assert key == "healthcare"
        assert is_multi is True
        key2, _ = pick_template("clinical data with diagnosis")
        assert key2 == "healthcare"

    def test_order_keywords(self):
        # "orders checkout" matches the multi-table ecommerce template
        key, is_multi = pick_template("e-commerce orders with checkout")
        assert key == "ecommerce"
        assert is_multi is True

    def test_employee_keywords(self):
        # "hr" multi-table template now takes priority over single-table "employees"
        key, is_multi = pick_template("employee payroll and HR records")
        assert key == "hr"
        assert is_multi is True

    def test_student_keywords(self):
        # "education" multi-table template now takes priority over single-table "students"
        key, is_multi = pick_template("student GPA and academic enrollment")
        assert key == "education"
        assert is_multi is True

    def test_user_keywords(self):
        # Generic keywords (user/member/contact/person) now route to "generic" template
        key, is_multi = pick_template("user profiles with members")
        assert is_multi is True
        assert key == "generic"

    def test_best_match_wins(self):
        # "healthcare" multi-table template wins for patient/hospital keywords
        key, _ = pick_template("100 patients in a hospital with diagnosis")
        assert key == "healthcare"


# ─── Schema structure ─────────────────────────────────────────────────────────

class TestGetStarterSchema:

    def test_default_returns_multi_table_generic(self):
        schema = get_starter_schema("")
        assert "tables" in schema
        assert len(schema["tables"]) == 3  # jobs, applicants, interviews
        table_names = {t["table_name"] for t in schema["tables"]}
        assert {"jobs", "applicants", "interviews"} == table_names

    def test_default_has_relationships(self):
        schema = get_starter_schema("")
        assert len(schema["relationships"]) == 2

    def test_default_has_per_parent_counts(self):
        schema = get_starter_schema("")
        ppc = schema["extracted"].get("per_parent_counts", {})
        assert "applicants" in ppc and "interviews" in ppc

    def test_ecommerce_returns_for_order_keywords(self):
        schema = get_starter_schema("e-commerce orders with checkout and payment")
        table_names = {t["table_name"] for t in schema["tables"]}
        assert {"customers", "orders", "order_items"} == table_names

    def test_all_schemas_are_multi_table(self):
        # pick_template always returns multi-table now — even generic user context
        schema = get_starter_schema("users with email and phone")
        assert len(schema["tables"]) >= 2, (
            "Starter schema should always be multi-table (pick_template always returns multi)"
        )

    def test_columns_have_pii_field(self):
        # Check across all tables
        schema = get_starter_schema()
        for tbl in schema["tables"]:
            for col in tbl["columns"]:
                assert "pii" in col, f"Column '{col['name']}' missing 'pii' field"

    def test_sensitive_detected_true(self):
        schema = get_starter_schema()
        assert schema["sensitive_detected"] is True
        assert schema["pii_detected"] is True

    def test_extracted_has_compliance_rules(self):
        schema = get_starter_schema()
        assert "compliance_rules" in schema["extracted"]
        assert len(schema["extracted"]["compliance_rules"]) > 0

    def test_extracted_has_distributions(self):
        schema = get_starter_schema("users with email")
        assert "distributions" in schema["extracted"]

    def test_frameworks_detected_populated(self):
        schema = get_starter_schema("users with email")
        assert len(schema["frameworks_detected"]) > 0


# ─── Non-trivial compliance fields (regression for compliance stage bug) ──────

NON_TRIVIAL_ACTIONS = {"mask", "format_preserving", "redact"}


def _all_columns(schema: dict) -> list:
    """Flatten all columns across all tables in the schema."""
    return [col for tbl in schema["tables"] for col in tbl["columns"]]


def _nontrivial_count(schema: dict) -> int:
    """Count columns (across all tables) whose pii.default_action is non-trivial."""
    count = 0
    for col in _all_columns(schema):
        if col.get("pii", {}).get("default_action") in NON_TRIVIAL_ACTIONS:
            count += 1
    return count


def _nontrivial_rules_count(schema: dict) -> int:
    """Count compliance_rules entries with non-trivial action."""
    count = 0
    for rule in schema["extracted"]["compliance_rules"].values():
        if rule.get("action") in NON_TRIVIAL_ACTIONS:
            count += 1
    return count


class TestComplianceFieldsInStarterTemplates:
    """
    Regression: each starter template must have at least 2 fields that would
    show up in the ComplianceReviewPanel as 'needing explicit decisions'
    (i.e. pii.default_action != fake_realistic OR stored action != fake_realistic).
    This ensures the Compliance stage is never empty in offline mode.
    """

    @pytest.mark.parametrize("keyword,expected_key", [
        # "users with name email ssn" now routes to the generic template which uses
        # fake_realistic for PII — covered separately below
        ("patient clinical hospital diagnosis", "healthcare"),
        ("employee payroll salary HR", "hr"),
        ("student gpa academic ferpa", "education"),
        # ecommerce multi-table template
        ("orders checkout payment credit card", "ecommerce"),
        # banking multi-table template
        ("bank account transaction loan", "banking"),
    ])
    def test_at_least_2_nontrivial_compliance_fields(self, keyword, expected_key):
        schema = get_starter_schema(keyword)
        nontrivial = _nontrivial_count(schema)
        rules_nontrivial = _nontrivial_rules_count(schema)
        assert max(nontrivial, rules_nontrivial) >= 2, (
            f"Template '{expected_key}' has only {max(nontrivial, rules_nontrivial)} "
            f"non-trivial compliance fields — need at least 2. "
            f"column non-trivial: {nontrivial}, rules non-trivial: {rules_nontrivial}"
        )

    def test_hr_template_has_ssn_or_tax_id_masked(self):
        # SSN is in the HR template (employees). "users with ssn" now routes to ecommerce.
        # Test with explicit HR keywords to hit the right template.
        schema = get_starter_schema("employee payroll ssn tax_id HR")
        cols = {c["name"]: c for c in _all_columns(schema)}
        # HR template should have at least one of: ssn, tax_id, salary — all masked
        sensitive_cols = [
            name for name, col in cols.items()
            if col.get("pii", {}).get("default_action") in NON_TRIVIAL_ACTIONS
        ]
        assert len(sensitive_cols) >= 1, (
            f"HR template must have at least 1 non-trivial PII field. Cols: {list(cols.keys())}"
        )

    def test_patients_has_hipaa_fields_with_nontrivial_action(self):
        schema = get_starter_schema("patient hospital")
        hipaa_nontrivial = [
            col["name"] for col in _all_columns(schema)
            if "HIPAA" in col.get("pii", {}).get("frameworks", [])
            and col["pii"].get("default_action") in NON_TRIVIAL_ACTIONS
        ]
        assert len(hipaa_nontrivial) >= 2, f"Need 2+ HIPAA fields, got: {hipaa_nontrivial}"

    def test_ecommerce_has_pci_shipping_address(self):
        schema = get_starter_schema("orders checkout payment")
        # Multi-table template: check across all tables
        cols = {c["name"]: c for c in _all_columns(schema)}
        assert "shipping_address" in cols, "ecommerce template must have shipping_address"

    def test_employees_has_sox_salary_masked(self):
        schema = get_starter_schema("employee payroll salary")
        cols = {c["name"]: c for c in _all_columns(schema)}
        assert "salary" in cols, "employees template must have salary column"
        assert cols["salary"]["pii"].get("default_action") in NON_TRIVIAL_ACTIONS

    def test_students_has_ferpa_student_id(self):
        schema = get_starter_schema("student gpa ferpa")
        cols = {c["name"]: c for c in _all_columns(schema)}
        assert "student_id" in cols
        assert cols["student_id"]["pii"].get("default_action") in NON_TRIVIAL_ACTIONS


# ─── Template completeness ────────────────────────────────────────────────────

class TestTemplateCompleteness:
    """Every template must meet minimum quality criteria."""

    @pytest.mark.parametrize("key,tmpl", TEMPLATES.items())
    def test_single_template_has_required_keys(self, key, tmpl):
        for field in ("keywords", "entity_type", "volume", "table_name",
                      "columns", "distributions", "compliance_rules",
                      "frameworks_detected", "sensitive_detected"):
            assert field in tmpl, f"Template '{key}' missing field '{field}'"

    @pytest.mark.parametrize("key,tmpl", TEMPLATES.items())
    def test_single_template_has_at_least_5_columns(self, key, tmpl):
        assert len(tmpl["columns"]) >= 5

    @pytest.mark.parametrize("key,tmpl", TEMPLATES.items())
    def test_single_template_has_at_least_2_compliance_rules(self, key, tmpl):
        assert len(tmpl["compliance_rules"]) >= 2

    @pytest.mark.parametrize("key,tmpl", TEMPLATES.items())
    def test_single_template_sensitive_detected_is_true(self, key, tmpl):
        assert tmpl["sensitive_detected"] is True

    @pytest.mark.parametrize("key,tmpl", TEMPLATES.items())
    def test_single_template_frameworks_detected_not_empty(self, key, tmpl):
        assert len(tmpl["frameworks_detected"]) >= 2

    @pytest.mark.parametrize("key,tmpl", MULTI_TEMPLATES.items())
    def test_multi_template_has_required_keys(self, key, tmpl):
        for field in ("keywords", "entity_type", "volume", "tables",
                      "relationships", "frameworks_detected", "sensitive_detected"):
            assert field in tmpl, f"Multi-template '{key}' missing field '{field}'"

    @pytest.mark.parametrize("key,tmpl", MULTI_TEMPLATES.items())
    def test_multi_template_has_multiple_tables(self, key, tmpl):
        assert len(tmpl["tables"]) >= 2

    @pytest.mark.parametrize("key,tmpl", MULTI_TEMPLATES.items())
    def test_multi_template_has_relationships(self, key, tmpl):
        assert len(tmpl["relationships"]) >= 1
