"""
Tests for compliance_detector.py

Covers regressions from:
- Bug: SSN was mapped to ["PII"] only — HIPAA was missing, so selecting HIPAA
  in the UI showed "no fields require special handling".
- Bug: domain framework detection not firing for healthcare/payment contexts.
- Value-pattern matching (email, credit card, SSN) via sample data.
- LLM batch detection: normalisation, fallback to catalog, DemoProvider skip.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.compliance_detector import (
    detect_compliance,
    detect_compliance_batch_llm,
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


# ─── LLM batch compliance detection ──────────────────────────────────────────

class _StubLLMProvider:
    """Minimal stub — returns canned JSON for a fixed set of columns."""

    def __init__(self, response: str):
        self._response = response

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return self._response


class _BrokenLLMProvider:
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise RuntimeError("network error")


class TestBatchLLMDetection:
    """detect_compliance_batch_llm: normalisation, resilience, DemoProvider skip."""

    def _good_response(self):
        import json
        return json.dumps({
            "email": {
                "is_sensitive": True,
                "frameworks": ["PII", "GDPR"],
                "field_type": "email_address",
                "default_action": "fake_realistic",
                "confidence": 0.95,
            },
            "cvv": {
                "is_sensitive": True,
                "frameworks": ["PCI"],
                "field_type": "card_cvv",
                "default_action": "redact",
                "confidence": 0.99,
            },
            "order_id": {
                "is_sensitive": False,
                "frameworks": [],
                "field_type": None,
                "default_action": None,
                "confidence": 0.1,
            },
        })

    # Helper: unwrap the results sub-dict for concise assertions
    def _r(self, batch_result):
        return batch_result["results"]

    def test_returns_correct_frameworks_for_email(self):
        provider = _StubLLMProvider(self._good_response())
        cols = [
            {"name": "email", "sample_values": ["a@b.com"]},
            {"name": "cvv", "sample_values": ["123"]},
            {"name": "order_id", "sample_values": ["1001"]},
        ]
        r = self._r(detect_compliance_batch_llm(cols, provider))
        assert "PII" in r["email"]["frameworks"]
        assert "GDPR" in r["email"]["frameworks"]
        assert r["email"]["default_action"] == "fake_realistic"

    def test_cvv_gets_redact_action(self):
        provider = _StubLLMProvider(self._good_response())
        cols = [{"name": "cvv", "sample_values": []}]
        r = self._r(detect_compliance_batch_llm(cols, provider))
        assert r["cvv"]["default_action"] == "redact"
        assert r["cvv"]["is_sensitive"] is True

    def test_nonsensitive_column_excluded_from_results_or_not_sensitive(self):
        provider = _StubLLMProvider(self._good_response())
        cols = [{"name": "order_id", "sample_values": []}]
        r = self._r(detect_compliance_batch_llm(cols, provider))
        assert "order_id" not in r or r["order_id"]["is_sensitive"] is False

    def test_demo_provider_returns_empty_results(self):
        """DemoProvider must be skipped — no LLM call, empty results."""
        from services.llm_service import DemoProvider
        out = detect_compliance_batch_llm(
            [{"name": "email", "sample_values": []}],
            DemoProvider(),
        )
        assert out["results"] == {}
        assert out["warning"] is None
        assert out["attempts"] == 0

    def test_llm_exception_returns_warning(self):
        """Network or API failure must not raise — results empty, warning set."""
        out = detect_compliance_batch_llm(
            [{"name": "email", "sample_values": []}],
            _BrokenLLMProvider(),
        )
        assert out["results"] == {}
        assert out["warning"] is not None
        assert "error" in out["warning"].lower() or "failed" in out["warning"].lower()

    def test_invalid_json_triggers_retry_then_warning(self):
        """Persistent invalid JSON exhausts retries and sets a warning."""
        provider = _StubLLMProvider("this is not json {{{{")
        out = detect_compliance_batch_llm(
            [{"name": "email", "sample_values": []}],
            provider,
            max_retries=2,
        )
        assert out["results"] == {}
        assert out["warning"] is not None
        assert out["attempts"] == 2

    def test_markdown_fenced_json_is_parsed(self):
        """LLMs sometimes wrap JSON in ```json ... ``` — strip it."""
        import json
        payload = json.dumps({"ssn": {"is_sensitive": True, "frameworks": ["PII", "HIPAA"],
                                      "field_type": "social_security",
                                      "default_action": "format_preserving", "confidence": 0.97}})
        fenced = f"```json\n{payload}\n```"
        provider = _StubLLMProvider(fenced)
        r = self._r(detect_compliance_batch_llm([{"name": "ssn", "sample_values": []}], provider))
        assert "HIPAA" in r["ssn"]["frameworks"]

    def test_unknown_framework_is_filtered_out(self):
        """LLM may hallucinate framework names — only keep known ones."""
        import json
        payload = json.dumps({"data": {
            "is_sensitive": True,
            "frameworks": ["PII", "UNKNOWN_FW"],
            "field_type": "misc",
            "default_action": "mask",
            "confidence": 0.5,
        }})
        provider = _StubLLMProvider(payload)
        r = self._r(detect_compliance_batch_llm([{"name": "data", "sample_values": []}], provider))
        if "data" in r:
            assert "UNKNOWN_FW" not in r["data"]["frameworks"]

    def test_invalid_action_is_normalised(self):
        """default_action values outside the allowed set must be corrected."""
        import json
        payload = json.dumps({"col": {
            "is_sensitive": True,
            "frameworks": ["PII"],
            "field_type": "misc",
            "default_action": "encrypt",   # not in allowed set
            "confidence": 0.7,
        }})
        provider = _StubLLMProvider(payload)
        r = self._r(detect_compliance_batch_llm([{"name": "col", "sample_values": []}], provider))
        if "col" in r:
            assert r["col"]["default_action"] in (
                "fake_realistic", "format_preserving", "mask", "redact"
            )

    def test_empty_columns_list_returns_empty(self):
        from services.llm_service import DemoProvider
        out = detect_compliance_batch_llm([], DemoProvider())
        assert out["results"] == {}
        assert out["attempts"] == 0

    def test_domain_frameworks_boost_applied(self):
        """Columns classified with PII should gain GDPR when domain implies it."""
        import json
        payload = json.dumps({"user_name": {
            "is_sensitive": True,
            "frameworks": ["PII"],
            "field_type": "person_name",
            "default_action": "fake_realistic",
            "confidence": 0.9,
        }})
        provider = _StubLLMProvider(payload)
        domain = {"GDPR"}
        r = self._r(detect_compliance_batch_llm(
            [{"name": "user_name", "sample_values": []}],
            provider,
            domain_frameworks=domain,
        ))
        if "user_name" in r:
            assert "GDPR" in r["user_name"]["frameworks"]

    def test_partial_response_triggers_retry(self):
        """When first call misses columns, retry prompt should include missing list."""
        import json
        call_count = {"n": 0}
        class PartialThenFullProvider:
            def generate(self, prompt, system_prompt=""):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    # First call: only email, skip ssn
                    return json.dumps({"email": {"is_sensitive": True, "frameworks": ["PII"],
                                                  "field_type": "email_address",
                                                  "default_action": "fake_realistic", "confidence": 0.9}})
                # Second call: return ssn
                assert "ssn" in prompt   # retry prompt must mention the missing column
                return json.dumps({"ssn": {"is_sensitive": True, "frameworks": ["PII", "HIPAA"],
                                            "field_type": "social_security",
                                            "default_action": "format_preserving", "confidence": 0.95}})

        cols = [{"name": "email", "sample_values": []}, {"name": "ssn", "sample_values": []}]
        out = detect_compliance_batch_llm(cols, PartialThenFullProvider(), max_retries=3)
        assert "email" in out["results"]
        assert "ssn" in out["results"]
        assert call_count["n"] == 2          # second call needed for ssn
        assert out["warning"] is None        # all columns resolved

    def test_all_retries_exhausted_sets_warning(self):
        """When retries run out, warning must be set and name missing columns."""
        import json
        class AlwaysMissingProvider:
            def generate(self, prompt, system_prompt=""):
                return json.dumps({"email": {"is_sensitive": True, "frameworks": ["PII"],
                                              "field_type": "email_address",
                                              "default_action": "fake_realistic", "confidence": 0.9}})

        cols = [{"name": "email", "sample_values": []}, {"name": "mystery_col", "sample_values": []}]
        out = detect_compliance_batch_llm(cols, AlwaysMissingProvider(), max_retries=2)
        assert "email" in out["results"]
        assert "mystery_col" not in out["results"]
        assert out["warning"] is not None
        assert "mystery_col" in out["warning"]
        assert out["attempts"] == 2
