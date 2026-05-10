"""
Tests for llm_service.py — pure provider selection logic.
No FastAPI dependency; runs locally or in Docker.

Covers regressions from:
- Bug: missing API key should fall back to DemoProvider, not raise an exception.
- Bug: demo provider test returned misleading "no connection needed" when a real
  provider was configured but the key lookup silently fell back.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.llm_service import get_provider, DemoProvider, AnthropicProvider, OpenAIProvider


class TestGetProvider:

    def test_demo_returns_demo_provider(self):
        p = get_provider({"provider": "demo"})
        assert isinstance(p, DemoProvider)

    def test_missing_api_key_falls_back_to_demo(self):
        """
        Regression: a missing key must fall back to DemoProvider gracefully —
        not raise, and not produce a misleading provider.
        """
        p = get_provider({"provider": "anthropic", "api_key": "", "model": ""})
        assert isinstance(p, DemoProvider), (
            "Empty API key must fall back to DemoProvider, not raise or return a broken provider"
        )

    def test_none_api_key_falls_back_to_demo(self):
        p = get_provider({"provider": "openai", "api_key": None, "model": "gpt-4o"})
        assert isinstance(p, DemoProvider)

    def test_anthropic_with_key_returns_anthropic_provider(self):
        p = get_provider({
            "provider": "anthropic",
            "api_key": "sk-ant-fake-key",
            "model": "claude-3-5-sonnet-20241022",
            "extra_config": {},
        })
        assert isinstance(p, AnthropicProvider)
        assert p.api_key == "sk-ant-fake-key"
        assert p.model == "claude-3-5-sonnet-20241022"

    def test_openai_with_key_returns_openai_provider(self):
        p = get_provider({
            "provider": "openai",
            "api_key": "sk-fake",
            "model": "gpt-4o",
            "extra_config": {},
        })
        assert isinstance(p, OpenAIProvider)

    def test_unknown_provider_falls_back_to_demo(self):
        p = get_provider({"provider": "unknown_llm", "api_key": "key"})
        assert isinstance(p, DemoProvider)

    def test_demo_provider_generate_returns_valid_json(self):
        """DemoProvider must return valid JSON — it's used as a stub."""
        import json
        p = DemoProvider()
        result = p.generate("test prompt")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
