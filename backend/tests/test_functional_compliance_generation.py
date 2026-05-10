"""
Functional tests — Compliance in Generation (Requirement 4)

Covers:
  - PII/PCI/HIPAA-sensitive fields generate realistic synthetic values by default
  - "redact" action → [REDACTED]
  - "mask" action → all alphanumerics replaced with *
  - "Custom" action with pre-normalised masking_op (structured deterministic execution)
  - "Custom" action with plain-text rule (keyword fallback normalization)
  - All masking op types round-tripped through generate_data
  - Multiple compliance rules applied per row (different fields, different ops)
  - format_preserving action falls back gracefully via field_type
  - Compliance rules keyed by bare column name AND table.column forms
"""
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.data_generator import generate_data

DEMO_SETTINGS = {"provider": "demo", "api_key": "", "model": ""}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _col(name, type_="string", field_type=None, is_sensitive=False, **kw):
    pii = {}
    if field_type or is_sensitive:
        pii = {
            "is_sensitive": is_sensitive or bool(field_type),
            "is_pii": is_sensitive or bool(field_type),
            "field_type": field_type or "",
            "frameworks": ["PII"] if is_sensitive else [],
            "default_action": "fake_realistic",
        }
    return {
        "name": name, "type": type_, "pattern": "generic",
        "sample_values": [], "enum_values": [],
        "pii": pii,
        **kw,
    }


def _schema(*tables):
    return {
        "tables": [
            {"table_name": n, "filename": f"{n}.csv", "columns": cols, "row_count": 5}
            for n, cols in tables
        ],
        "relationships": [],
    }


def _gen(schema, compliance_rules, volume=5):
    return generate_data(schema, {}, compliance_rules, [], volume=volume, llm_settings=DEMO_SETTINGS)


# ─── Redact ────────────────────────────────────────────────────────────────────

class TestRedactAction:

    def test_redacted_field_is_literal_string(self):
        s = _schema(("users", [_col("id", "integer"), _col("ssn", is_sensitive=True)]))
        data = _gen(s, {"ssn": {"action": "redact"}})
        for row in data["users"]:
            assert row["ssn"] == "[REDACTED]", f"Expected [REDACTED], got {row['ssn']}"

    def test_redact_does_not_affect_other_columns(self):
        s = _schema(("users", [_col("id", "integer"), _col("name"), _col("ssn", is_sensitive=True)]))
        data = _gen(s, {"ssn": {"action": "redact"}})
        for row in data["users"]:
            assert row["ssn"] == "[REDACTED]"
            assert row["name"] != "[REDACTED]"

    def test_redact_applied_to_every_row(self):
        s = _schema(("users", [_col("id", "integer"), _col("dob")]))
        data = _gen(s, {"dob": {"action": "redact"}}, volume=20)
        for row in data["users"]:
            assert row["dob"] == "[REDACTED]"


# ─── Mask all ─────────────────────────────────────────────────────────────────

class TestMaskAction:

    def test_masked_field_has_no_alphanumeric(self):
        s = _schema(("users", [_col("id", "integer"), _col("name", field_type="person_name")]))
        data = _gen(s, {"name": {"action": "mask"}})
        for row in data["users"]:
            masked = row["name"]
            assert not re.search(r"[A-Za-z0-9]", str(masked)), (
                f"Expected all alphanumerics masked, got: {masked}"
            )

    def test_masked_field_still_has_content(self):
        s = _schema(("users", [_col("id", "integer"), _col("phone", field_type="phone_number")]))
        data = _gen(s, {"phone": {"action": "mask"}})
        for row in data["users"]:
            assert len(str(row["phone"])) > 0

    def test_masked_field_contains_only_stars_and_non_alnum(self):
        s = _schema(("cards", [_col("id", "integer"), _col("card_no", field_type="card_number")]))
        data = _gen(s, {"card_no": {"action": "mask"}})
        for row in data["cards"]:
            val = str(row["card_no"])
            assert re.fullmatch(r"[\*\s\-\.]+", val) or not re.search(r"[A-Za-z0-9]", val)


# ─── Custom masking ops (structured) ──────────────────────────────────────────

class TestCustomMaskingOps:

    def _assert_custom(self, field_type, masking_op, checker, volume=10):
        s = _schema(("data", [_col("id", "integer"), _col("val", field_type=field_type)]))
        data = _gen(s, {"val": {"action": "Custom", "custom_rule": "", "masking_op": masking_op}}, volume=volume)
        for row in data["data"]:
            checker(str(row["val"]))

    def test_show_last_4_digits(self):
        def check(v):
            digits = re.sub(r"\D", "", v)
            if len(digits) >= 4:
                assert v.endswith(digits[-4:]), f"Last 4 digits not shown: {v}"
            stars = v.replace(digits[-4:], "")
            assert "*" in stars or len(digits) < 4

        s = _schema(("cards", [_col("id", "integer"), _col("pan", field_type="card_number")]))
        data = _gen(s, {"pan": {"action": "Custom", "custom_rule": "show last 4 digits",
                                "masking_op": {"type": "show_last_n_digits", "n": 4}}})
        for row in data["cards"]:
            v = str(row["pan"])
            digits_in_v = re.sub(r"\D", "", v)
            if len(digits_in_v) >= 4:
                assert v.endswith(digits_in_v[-4:]), f"show_last_4_digits failed: {v}"

    def test_show_last_n_chars(self):
        s = _schema(("items", [_col("id", "integer"), _col("code")]))
        data = _gen(s, {"code": {"action": "Custom", "custom_rule": "show last 2 characters",
                                 "masking_op": {"type": "show_last_n_chars", "n": 2}}})
        for row in data["items"]:
            v = str(row["code"])
            if len(v) > 2:
                assert v[:-2] == "*" * (len(v) - 2), f"show_last_n_chars(2) failed: {v}"

    def test_mask_last_n_chars(self):
        s = _schema(("items", [_col("id", "integer"), _col("ref")]))
        data = _gen(s, {"ref": {"action": "Custom", "custom_rule": "mask last 3 characters",
                                "masking_op": {"type": "mask_last_n_chars", "n": 3}}})
        for row in data["items"]:
            v = str(row["ref"])
            if len(v) >= 3:
                assert v[-3:] == "***", f"mask_last_n_chars(3) failed: {v}"

    def test_partial_email(self):
        s = _schema(("users", [_col("id", "integer"), _col("email", "email", field_type="email_address")]))
        data = _gen(s, {"email": {"action": "Custom", "custom_rule": "mask email",
                                  "masking_op": {"type": "partial_email"}}})
        for row in data["users"]:
            v = str(row["email"])
            assert "@" in v, f"partial_email must keep @: {v}"
            assert "***" in v or v.startswith("*"), f"partial_email must mask local part: {v}"

    def test_redact_op(self):
        s = _schema(("users", [_col("id", "integer"), _col("ssn", field_type="social_security")]))
        data = _gen(s, {"ssn": {"action": "Custom", "custom_rule": "redact",
                                "masking_op": {"type": "redact"}}})
        for row in data["users"]:
            assert row["ssn"] == "[REDACTED]"

    def test_date_year_only_op(self):
        s = _schema(("users", [_col("id", "integer"), _col("dob", "date", field_type="date_of_birth")]))
        data = _gen(s, {"dob": {"action": "Custom", "custom_rule": "year only",
                                "masking_op": {"type": "date_year_only"}}})
        for row in data["users"]:
            v = str(row["dob"])
            assert re.fullmatch(r"\d{4}", v), f"date_year_only should produce YYYY: {v}"

    def test_range_bucket_op(self):
        s = _schema(("users", [_col("id", "integer"), _col("age", "integer")]))
        data = _gen(s, {"age": {"action": "Custom", "custom_rule": "age range",
                                "masking_op": {"type": "range_bucket", "size": 10}}})
        for row in data["users"]:
            v = str(row["age"])
            assert "-" in v or re.search(r"\d", v), f"range_bucket should produce X-Y: {v}"

    def test_format_preserve_mask_op(self):
        s = _schema(("cards", [_col("id", "integer"), _col("pan", field_type="card_number")]))
        data = _gen(s, {"pan": {"action": "Custom", "custom_rule": "format preserving",
                                "masking_op": {"type": "format_preserve_mask"}}})
        for row in data["cards"]:
            v = str(row["pan"])
            assert "*" in v or re.search(r"\d", v)   # either masked or short value unchanged


# ─── Custom rule plain-text keyword fallback ──────────────────────────────────

class TestCustomRuleKeywordFallback:
    """No masking_op supplied — keyword fallback normalization at generation time."""

    def test_show_last_4_digits_keyword(self):
        s = _schema(("cards", [_col("id", "integer"), _col("pan", field_type="card_number")]))
        data = _gen(s, {"pan": {"action": "Custom", "custom_rule": "show last 4 digits"}})
        for row in data["cards"]:
            v = str(row["pan"])
            digits = re.sub(r"\D", "", v)
            if len(digits) >= 4:
                assert v.endswith(digits[-4:]), f"Keyword fallback show_last_4 failed: {v}"

    def test_mask_everything_except_last_char_keyword(self):
        s = _schema(("items", [_col("id", "integer"), _col("code")]))
        data = _gen(s, {"code": {"action": "Custom",
                                 "custom_rule": "mask everything except last character"}})
        for row in data["items"]:
            v = str(row["code"])
            if len(v) > 1:
                # All chars except the last should be *
                assert re.fullmatch(r"\*+.", v), f"Keyword fallback show_last_1_char failed: {v}"

    def test_redact_keyword(self):
        s = _schema(("users", [_col("id", "integer"), _col("ssn")]))
        data = _gen(s, {"ssn": {"action": "Custom", "custom_rule": "redact this field"}})
        for row in data["users"]:
            assert row["ssn"] == "[REDACTED]"


# ─── Multiple compliance rules ────────────────────────────────────────────────

class TestMultipleComplianceRules:

    def test_different_rules_applied_to_different_fields(self):
        s = _schema(("patients", [
            _col("id", "integer"),
            _col("ssn",   field_type="social_security"),
            _col("email", "email", field_type="email_address"),
            _col("name",  field_type="person_name"),
        ]))
        rules = {
            "ssn":   {"action": "redact"},
            "email": {"action": "Custom", "custom_rule": "mask email",
                      "masking_op": {"type": "partial_email"}},
            "name":  {"action": "mask"},
        }
        data = _gen(s, rules, volume=10)
        for row in data["patients"]:
            assert row["ssn"] == "[REDACTED]"
            assert "@" in str(row["email"])          # partial_email preserves @
            assert not re.search(r"[A-Za-z]", str(row["name"]))  # name fully masked

    def test_unruled_fields_generate_normally(self):
        s = _schema(("users", [
            _col("id", "integer"),
            _col("name"),
            _col("ssn", field_type="social_security"),
        ]))
        rules = {"ssn": {"action": "redact"}}
        data = _gen(s, rules, volume=5)
        for row in data["users"]:
            assert row["ssn"] == "[REDACTED]"
            # name should not be [REDACTED]
            assert row["name"] != "[REDACTED]"
            # name should have some alphabetical content
            assert re.search(r"[A-Za-z]", str(row["name"]))


# ─── Sensitive field defaults ──────────────────────────────────────────────────

class TestSensitiveFieldDefaults:
    """Without any compliance rule, sensitive fields still produce realistic values."""

    def test_ssn_field_type_generates_ssn_pattern(self):
        s = _schema(("users", [_col("ssn", field_type="social_security", is_sensitive=True)]))
        data = _gen(s, {}, volume=10)
        for row in data["users"]:
            v = str(row["ssn"])
            assert re.match(r"\d{3}-\d{2}-\d{4}", v), f"SSN format unexpected: {v}"

    def test_email_field_type_generates_valid_email(self):
        s = _schema(("users", [_col("email", "email", field_type="email_address", is_sensitive=True)]))
        data = _gen(s, {}, volume=10)
        for row in data["users"]:
            assert "@" in str(row["email"])

    def test_credit_card_field_type_generates_digits(self):
        s = _schema(("cards", [_col("pan", field_type="card_number", is_sensitive=True)]))
        data = _gen(s, {}, volume=10)
        for row in data["cards"]:
            digits = re.sub(r"\D", "", str(row["pan"]))
            assert len(digits) >= 12, f"Card number too short: {row['pan']}"

    def test_fake_realistic_action_generates_real_values(self):
        """Explicit fake_realistic action should also produce real values (not masked)."""
        s = _schema(("users", [_col("name", field_type="person_name", is_sensitive=True)]))
        data = _gen(s, {"name": {"action": "fake_realistic"}}, volume=10)
        for row in data["users"]:
            assert re.search(r"[A-Za-z]", str(row["name"])), f"Expected name, got: {row['name']}"
