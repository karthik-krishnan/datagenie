"""
Tests for compliance_detector.py

Covers regressions from:
- Bug: SSN was mapped to ["PII"] only — HIPAA was missing, so selecting HIPAA
  in the UI showed "no fields require special handling".
- Bug: domain framework detection not firing for healthcare/payment contexts.
- Value-pattern matching (email, credit card, SSN) via sample data.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.compliance_detector import (
    detect_compliance,
    detect_domain_frameworks,
    _match_field_catalog,
)


# ─── Field catalog matches ────────────────────────────────────────────────────

class TestSSNIncludesHIPAA:
    """Regression: SSN must include HIPAA as well as PII."""

    def test_ssn_has_hipaa(self):
        result = detect_compliance("ssn", [])
        assert "HIPAA" in result["frameworks"], (
            "SSN must include HIPAA — fixes the bug where selecting HIPAA "
            "showed 'no fields require special handling'"
        )

    def test_ssn_has_pii(self):
        result = detect_compliance("ssn", [])
        assert "PII" in result["frameworks"]

    def test_ssn_is_sensitive(self):
        result = detect_compliance("ssn", [])
        assert result["is_sensitive"] is True

    def test_ssn_default_action_is_not_fake_realistic(self):
        result = detect_compliance("ssn", [])
        assert result["default_action"] != "fake_realistic", (
            "SSN should have a non-trivial default action (mask or format_preserving) "
            "so it shows up in the compliance review"
        )

    def test_social_security_has_hipaa(self):
        """social_security column name must also include HIPAA."""
        result = detect_compliance("social_security", [])
        assert "HIPAA" in result["frameworks"]


class TestFieldCatalogCoverage:
    """Key fields must be detected with correct frameworks and actions."""

    @pytest.mark.parametrize("col_name,expected_frameworks,nontrivial_action", [
        ("email",        ["PII", "GDPR"],   False),  # fake_realistic is fine
        ("phone",        ["PII"],            False),
        ("credit_card",  ["PCI"],            True),   # format_preserving
        ("cvv",          ["PCI"],            True),   # redact
        ("mrn",          ["HIPAA"],          True),   # format_preserving
        ("patient_id",   ["HIPAA"],          True),
        ("salary",       ["SOX", "PII"],     True),   # mask
        ("student_id",   ["FERPA", "PII"],   True),   # format_preserving
        ("ip_address",   ["PII", "GDPR"],    True),   # mask
        ("dob",          ["PII", "GDPR", "HIPAA"], False),
    ])
    def test_field(self, col_name, expected_frameworks, nontrivial_action):
        result = detect_compliance(col_name, [])
        assert result["is_sensitive"] is True, f"{col_name} must be detected as sensitive"
        for fw in expected_frameworks:
            assert fw in result["frameworks"], f"{col_name} must include framework {fw}"
        if nontrivial_action:
            assert result["default_action"] != "fake_realistic", (
                f"{col_name} should have a non-trivial default action"
            )

    def test_nonsensitive_field_returns_not_sensitive(self):
        # "order_quantity" has no keyword or pattern match in the catalog
        result = detect_compliance("order_quantity", [])
        assert result["is_sensitive"] is False
        assert result["frameworks"] == []
        assert result["default_action"] is None

    def test_nonsensitive_field_has_no_confidence(self):
        result = detect_compliance("order_quantity", [])
        assert result["confidence"] == 0.0


class TestValuePatternDetection:
    """Fields without catalog entries should be detected from sample values."""

    def test_email_values_detected(self):
        samples = ["alice@example.com", "bob@test.org", "charlie@mail.com"]
        result = detect_compliance("contact_info", samples)
        assert result["is_sensitive"] is True
        assert "PII" in result["frameworks"]

    def test_credit_card_luhn_detected(self):
        # Luhn-valid card number
        samples = ["4532015112830366", "4532015112830366", "4532015112830366"]
        result = detect_compliance("payment_token", samples)
        assert result["is_sensitive"] is True
        assert "PCI" in result["frameworks"]

    def test_non_patterned_values_not_detected(self):
        samples = ["foo", "bar", "baz", "qux"]
        result = detect_compliance("random_field", samples)
        assert result["is_sensitive"] is False


# ─── Domain framework detection ───────────────────────────────────────────────

class TestDomainFrameworkDetection:
    """detect_domain_frameworks must identify regulatory context from free text."""

    @pytest.mark.parametrize("text,expected_fw", [
        ("Generate patient records for a hospital EHR system", "HIPAA"),
        ("Payment card data for PCI DSS compliance testing", "PCI"),
        ("EU resident personal data subject to GDPR", "GDPR"),
        ("California consumer privacy opt-out data", "CCPA"),
        ("Employee payroll and Sarbanes-Oxley audit trail", "SOX"),
        ("Student GPA and FERPA academic records", "FERPA"),
    ])
    def test_detects_framework(self, text, expected_fw):
        result = detect_domain_frameworks(text)
        assert expected_fw in result, (
            f"'{expected_fw}' not detected from: '{text}'"
        )

    def test_empty_context_returns_empty_set(self):
        assert detect_domain_frameworks("") == set()
        assert detect_domain_frameworks(None) == set()

    def test_multiple_frameworks_from_combined_context(self):
        text = "HIPAA patient records with GDPR compliance for EU users"
        result = detect_domain_frameworks(text)
        assert "HIPAA" in result
        assert "GDPR" in result

    def test_neutral_context_returns_empty(self):
        result = detect_domain_frameworks("Generate some test data with names and cities")
        assert len(result) == 0


# ─── Catalog matching edge cases ─────────────────────────────────────────────

class TestCatalogMatching:
    """_match_field_catalog must handle exact and substring matches."""

    def test_exact_match_wins(self):
        entry = _match_field_catalog("ssn")
        assert entry is not None
        assert "PII" in entry["frameworks"]

    def test_case_insensitive(self):
        entry = _match_field_catalog("SSN")
        assert entry is not None

    def test_space_in_name_normalised(self):
        entry = _match_field_catalog("credit card")
        assert entry is not None
        assert "PCI" in entry["frameworks"]

    def test_unknown_field_returns_none(self):
        entry = _match_field_catalog("completely_unknown_xyz")
        assert entry is None
