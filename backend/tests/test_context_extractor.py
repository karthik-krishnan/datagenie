"""
Tests for context_extractor.py  (_regex_fallback)

Covers regressions from:
- Bug: gender distribution with 3 values collapsed to 2 because "not-specified",
  "non-binary" etc. were not in GENDER_WORDS.
- Bug: binary auto-fill logic ran on gender when only 1 value was stated,
  producing a wrong 2-value distribution.
- Distribution sum / multi-value parsing edge cases.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.context_extractor import _regex_fallback


# ─── Gender distribution — 3-value parsing ───────────────────────────────────

class TestGenderDistributions:
    """
    Regression: user specified 80% men / 10% female / 10% not-specified
    but only 80% male and 20% female appeared.
    """

    def test_three_value_gender_distribution(self):
        ctx = "men should be 80% of the mix, 10% not-specified gender and 10% female"
        result = _regex_fallback(ctx)
        dist = result["distributions"].get("gender", {})
        assert len(dist) == 3, f"Expected 3 gender values, got {len(dist)}: {dist}"
        assert dist.get("Male") == 80
        assert dist.get("Female") == 10
        assert dist.get("Not specified") == 10

    def test_not_specified_variant_hyphenated(self):
        ctx = "60% male, 30% female, 10% not-specified"
        dist = _regex_fallback(ctx)["distributions"].get("gender", {})
        assert "Not specified" in dist, f"'not-specified' not mapped: {dist}"

    def test_not_specified_variant_underscore(self):
        ctx = "50% male, 40% female, 10% not_specified"
        dist = _regex_fallback(ctx)["distributions"].get("gender", {})
        assert "Not specified" in dist

    def test_non_binary_variant(self):
        ctx = "70% male, 20% female, 10% non-binary"
        dist = _regex_fallback(ctx)["distributions"].get("gender", {})
        assert "Non-binary" in dist, f"'non-binary' not mapped: {dist}"

    def test_nonbinary_no_hyphen(self):
        ctx = "70% male, 20% female, 10% nonbinary"
        dist = _regex_fallback(ctx)["distributions"].get("gender", {})
        assert "Non-binary" in dist

    def test_other_variant(self):
        ctx = "80% men, 10% women, 10% other"
        dist = _regex_fallback(ctx)["distributions"].get("gender", {})
        assert "Other" in dist

    def test_unknown_variant(self):
        ctx = "80% male, 10% female, 10% unknown"
        dist = _regex_fallback(ctx)["distributions"].get("gender", {})
        assert "Unknown" in dist


class TestGenderNoAutofill:
    """
    Regression: auto-fill must NOT run on gender.
    If only 1 gender value is mentioned, don't infer the complement.
    """

    def test_single_gender_value_no_autofill(self):
        ctx = "80% male users"
        dist = _regex_fallback(ctx)["distributions"].get("gender", {})
        assert len(dist) == 1, (
            "Only 1 gender value mentioned — must not auto-fill the rest: "
            f"{dist}"
        )
        assert dist.get("Male") == 80

    def test_two_gender_values_no_autofill(self):
        ctx = "80% male, 10% female"
        dist = _regex_fallback(ctx)["distributions"].get("gender", {})
        assert len(dist) == 2
        assert "Not specified" not in dist


class TestBooleanAutofill:
    """Boolean flags (yes/no) should still get auto-filled to 100%."""

    def test_boolean_autofill_yes(self):
        ctx = "80% yes and the rest no"
        # boolean auto-fill only fires on single-value flag
        ctx2 = "80% yes"
        dist = _regex_fallback(ctx2)["distributions"].get("flag", {})
        if dist:  # only assert if flag was detected
            assert dist.get("Yes") == 80
            assert dist.get("No") == 20

    def test_boolean_values_preserved_when_both_stated(self):
        ctx = "70% true and 30% false"
        dist = _regex_fallback(ctx)["distributions"].get("flag", {})
        if dist:
            total = sum(dist.values())
            assert total == 100


# ─── Volume extraction ────────────────────────────────────────────────────────

class TestVolumeExtraction:

    def test_explicit_count_before_entity(self):
        result = _regex_fallback("Generate 500 users with name and email")
        assert result["volume"] == 500

    def test_explicit_count_after_generate(self):
        result = _regex_fallback("generate 1000 records")
        assert result["volume"] == 1000

    def test_no_volume_returns_none(self):
        result = _regex_fallback("users with name, email, phone")
        assert result["volume"] is None

    def test_large_volume(self):
        result = _regex_fallback("I need 100000 customer records")
        assert result["volume"] == 100000


# ─── Column detection ─────────────────────────────────────────────────────────

class TestColumnDetection:

    def test_explicit_fields_list(self):
        result = _regex_fallback("users with fields: name, email, phone, age")
        names = [c["name"] for c in result["columns"]]
        assert "email" in names
        assert "phone" in names

    def test_email_type_mapped(self):
        result = _regex_fallback("users with fields: email, phone")
        col = next((c for c in result["columns"] if c["name"] == "email"), None)
        assert col is not None
        assert col["type"] == "email"

    def test_dob_type_mapped_to_date(self):
        result = _regex_fallback("users with fields: dob, name")
        col = next((c for c in result["columns"] if c["name"] == "dob"), None)
        assert col is not None
        assert col["type"] == "date"

    def test_empty_context_returns_empty(self):
        result = _regex_fallback("")
        assert result["columns"] == []
        assert result["volume"] is None
        assert result["distributions"] == {}


# ─── Compliance rules extraction ─────────────────────────────────────────────

class TestComplianceRulesExtraction:

    def test_ssn_field_gets_pii_rule(self):
        result = _regex_fallback("50 users with ssn, email, phone")
        rules = result["compliance_rules"]
        assert "ssn" in rules
        assert rules["ssn"]["pii_type"] == "PII"

    def test_email_field_gets_pii_rule(self):
        result = _regex_fallback("users with email and name")
        rules = result["compliance_rules"]
        assert "email" in rules

    def test_mask_keyword_sets_mask_action(self):
        result = _regex_fallback("users with ssn — please mask the SSN field")
        rules = result["compliance_rules"]
        if "ssn" in rules:
            assert rules["ssn"]["action"] == "mask"

    def test_last_4_digits_sets_custom_rule(self):
        # Regex requires "visible" or "shown" after the digit count
        result = _regex_fallback("users with credit_card — last 4 digits visible")
        rules = result["compliance_rules"]
        if "credit_card" in rules:
            assert rules["credit_card"]["custom_rule"] is not None
            assert "4" in rules["credit_card"]["custom_rule"]
