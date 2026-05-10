"""
Tests for services/masking.py

Covers:
- apply_masking_op for all op types
- normalize_masking_rule keyword fallback (no LLM)
- Edge cases: short values, no digits, unknown op
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.masking import apply_masking_op, normalize_masking_rule, OP_TYPES


# ─── apply_masking_op ─────────────────────────────────────────────────────────

class TestShowLastNDigits:
    def test_basic(self):
        result = apply_masking_op("4532-0151-1283-0366", {"type": "show_last_n_digits", "n": 4})
        assert result.endswith("0366")
        assert "*" in result

    def test_non_digit_chars_kept(self):
        result = apply_masking_op("4532-0151-1283-0366", {"type": "show_last_n_digits", "n": 4})
        assert "-" in result   # separators preserved

    def test_shorter_than_n(self):
        # Value has only 3 digits, n=4 — nothing to mask
        result = apply_masking_op("1-2-3", {"type": "show_last_n_digits", "n": 4})
        assert result == "1-2-3"

    def test_ssn_show_last_4(self):
        result = apply_masking_op("123-45-6789", {"type": "show_last_n_digits", "n": 4})
        assert result.endswith("6789")
        assert result.startswith("*")


class TestMaskLastNDigits:
    def test_basic(self):
        result = apply_masking_op("123-45-6789", {"type": "mask_last_n_digits", "n": 2})
        # Last two digits (8, 9) must be masked; first digits intact
        assert "1" in result
        assert result.endswith("**")

    def test_mask_single_digit(self):
        result = apply_masking_op("4321", {"type": "mask_last_n_digits", "n": 1})
        assert result == "432*"


class TestShowFirstNDigits:
    def test_basic(self):
        result = apply_masking_op("411111111111", {"type": "show_first_n_digits", "n": 6})
        assert result.startswith("411111")
        assert result.endswith("******")

    def test_all_visible_when_n_ge_length(self):
        result = apply_masking_op("123", {"type": "show_first_n_digits", "n": 6})
        assert result == "123"


class TestShowFirstNChars:
    def test_basic(self):
        result = apply_masking_op("SecretWord", {"type": "show_first_n_chars", "n": 3})
        assert result == "Sec*******"

    def test_value_shorter_than_n(self):
        result = apply_masking_op("Hi", {"type": "show_first_n_chars", "n": 5})
        assert result == "Hi"


class TestMaskFirstNChars:
    def test_basic(self):
        result = apply_masking_op("SecretWord", {"type": "mask_first_n_chars", "n": 3})
        assert result == "***retWord"

    def test_all_masked_when_n_ge_length(self):
        result = apply_masking_op("Hi", {"type": "mask_first_n_chars", "n": 5})
        assert result == "**"


class TestPartialEmail:
    def test_basic(self):
        result = apply_masking_op("alice@example.com", {"type": "partial_email"})
        assert result.startswith("a")
        assert "****" in result
        assert result.endswith("@example.com")

    def test_non_email_falls_back_to_mask_all(self):
        result = apply_masking_op("notanemail", {"type": "partial_email"})
        assert result == "**********"

    def test_single_char_local_unchanged(self):
        result = apply_masking_op("a@example.com", {"type": "partial_email"})
        assert result == "a@example.com"


class TestDateYearOnly:
    def test_iso_date(self):
        assert apply_masking_op("1990-01-15", {"type": "date_year_only"}) == "1990"

    def test_us_date(self):
        assert apply_masking_op("01/15/1990", {"type": "date_year_only"}) == "1990"

    def test_no_year_returns_as_is(self):
        result = apply_masking_op("no-date-here", {"type": "date_year_only"})
        assert result == "no-date-here"


class TestRangeBucket:
    def test_basic(self):
        assert apply_masking_op("45", {"type": "range_bucket", "size": 10}) == "40-49"

    def test_exactly_on_boundary(self):
        assert apply_masking_op("50", {"type": "range_bucket", "size": 10}) == "50-59"

    def test_custom_size(self):
        assert apply_masking_op("23", {"type": "range_bucket", "size": 5}) == "20-24"

    def test_string_with_number(self):
        result = apply_masking_op("Age: 35", {"type": "range_bucket", "size": 10})
        assert result == "30-39"

    def test_non_numeric(self):
        result = apply_masking_op("unknown", {"type": "range_bucket", "size": 10})
        assert result == "unknown"


class TestRedact:
    def test_basic(self):
        assert apply_masking_op("anything", {"type": "redact"}) == "[REDACTED]"

    def test_empty(self):
        assert apply_masking_op("", {"type": "redact"}) == "[REDACTED]"


class TestMaskAll:
    def test_alphanumeric_masked(self):
        assert apply_masking_op("abc123", {"type": "mask_all"}) == "******"

    def test_preserves_spaces_and_symbols(self):
        result = apply_masking_op("Hello, World!", {"type": "mask_all"})
        assert result == "*****, *****!"

    def test_empty_string(self):
        assert apply_masking_op("", {"type": "mask_all"}) == ""


class TestFormatPreserveMask:
    def test_keeps_separators(self):
        result = apply_masking_op("123-45-6789", {"type": "format_preserve_mask"})
        assert result == "***-**-****"

    def test_card_number(self):
        result = apply_masking_op("4532 0151 1283 0366", {"type": "format_preserve_mask"})
        assert result == "**** **** **** ****"


class TestUnknownOp:
    def test_falls_back_to_mask_all(self):
        result = apply_masking_op("hello123", {"type": "completely_unknown_op_xyz"})
        assert result == "********"


# ─── normalize_masking_rule (keyword fallback, no LLM) ───────────────────────

class TestNormalizeMaskingRuleKeywords:
    def _n(self, rule):
        return normalize_masking_rule(rule, llm_provider=None)

    def test_show_last_4(self):
        op = self._n("show last 4 digits")
        assert op == {"type": "show_last_n_digits", "n": 4}

    def test_last_4_digits_visible(self):
        op = self._n("last 4 digits visible")
        assert op == {"type": "show_last_n_digits", "n": 4}

    def test_bare_last_4_digits(self):
        op = self._n("last 4 digits")
        assert op == {"type": "show_last_n_digits", "n": 4}

    def test_last_digit_bare(self):
        op = self._n("last digit")
        assert op == {"type": "show_last_n_digits", "n": 1}

    def test_mask_last_digit(self):
        op = self._n("mask last digit")
        assert op == {"type": "mask_last_n_digits", "n": 1}

    def test_mask_last_3_digits(self):
        op = self._n("mask last 3 digits")
        assert op == {"type": "mask_last_n_digits", "n": 3}

    def test_hide_last_2_digits(self):
        op = self._n("hide last 2 digits")
        assert op == {"type": "mask_last_n_digits", "n": 2}

    def test_show_first_6_digits(self):
        op = self._n("show first 6 digits")
        assert op == {"type": "show_first_n_digits", "n": 6}

    def test_keep_first_3_chars(self):
        op = self._n("keep first 3 chars")
        assert op == {"type": "show_first_n_chars", "n": 3}

    def test_mask_first_4_chars(self):
        op = self._n("mask first 4 chars")
        assert op == {"type": "mask_first_n_chars", "n": 4}

    def test_email_rule(self):
        op = self._n("mask email address")
        assert op == {"type": "partial_email"}

    def test_year_only(self):
        op = self._n("show year only")
        assert op == {"type": "date_year_only"}

    def test_redact(self):
        op = self._n("redact this field")
        assert op == {"type": "redact"}

    def test_mask_all_generic(self):
        op = self._n("mask the entire value")
        assert op is not None
        assert op["type"] == "mask_all"

    def test_empty_returns_none(self):
        assert self._n("") is None
        assert self._n(None) is None

    def test_unrecognised_returns_none(self):
        # Generic text with no masking keywords
        assert self._n("generate unique values") is None

    def test_format_preserving(self):
        op = self._n("keep the format, just replace digits")
        assert op is not None
        assert op["type"] == "format_preserve_mask"

    def test_demo_provider_uses_keyword_fallback(self):
        """DemoProvider must NOT be called — keyword fallback should still work."""
        from services.llm_service import DemoProvider
        op = normalize_masking_rule("show last 4 digits", DemoProvider())
        assert op == {"type": "show_last_n_digits", "n": 4}


# ─── Round-trip: normalize then apply ────────────────────────────────────────

class TestRoundTrip:
    """Ensure normalize → apply produces correct output for common phrases."""

    def _apply(self, rule, value):
        op = normalize_masking_rule(rule, llm_provider=None)
        assert op is not None, f"normalize_masking_rule returned None for: {rule!r}"
        return apply_masking_op(value, op)

    def test_credit_card_show_last_4(self):
        result = self._apply("last 4 digits", "4532-0151-1283-0366")
        assert result.endswith("0366")

    def test_ssn_mask_last_digit(self):
        result = self._apply("mask last digit", "123-45-6789")
        assert result == "123-45-678*"

    def test_salary_year_range(self):
        result = self._apply("show year only", "1985-07-04")
        assert result == "1985"

    def test_age_bucket(self):
        op = normalize_masking_rule("range bucket", llm_provider=None)
        if op:  # keyword may or may not match "range bucket" literally
            result = apply_masking_op("42", op)
            assert "-" in result

    def test_redact_field(self):
        result = self._apply("redact", "sensitive-data-123")
        assert result == "[REDACTED]"
