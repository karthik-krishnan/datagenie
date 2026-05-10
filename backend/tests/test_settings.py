"""
Tests for settings router and schema LLM override.

Router tests require FastAPI (available inside Docker / CI).
They are skipped gracefully when running locally without the full stack.

Covers regressions from:
- Bug: test endpoint used USE_SAVED sentinel — now key is passed directly.
- Bug: empty key fell back to demo and returned misleading message.
- Migration: api_key must never be stored server-side.
- LLM override: request-level config takes priority over DB.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, MagicMock

# Skip this entire module gracefully if FastAPI / app deps not installed
fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed — run inside Docker")


# ─── Settings router: POST /test ──────────────────────────────────────────────

class TestTestConnectionEndpoint:
    """test_connection uses the supplied key directly; no DB lookup."""

    def _payload(self, provider="anthropic", api_key="sk-test", model="claude-3-5-sonnet-20241022"):
        from routers.settings import SettingsPayload
        return SettingsPayload(provider=provider, api_key=api_key, model=model, extra_config={})

    @pytest.mark.asyncio
    async def test_demo_provider_returns_no_connection_needed(self):
        from routers.settings import test_connection
        result = await test_connection(self._payload(provider="demo", api_key=""))
        assert result["ok"] is False
        assert "demo" in result["message"].lower() or "no connection" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_empty_key_returns_descriptive_error(self):
        """
        Regression: empty key used to silently fall back to DB → demo provider
        returning "Demo mode — no connection needed" even for non-demo providers.
        """
        from routers.settings import test_connection
        result = await test_connection(self._payload(provider="anthropic", api_key=""))
        assert result["ok"] is False
        msg = result["message"].lower()
        assert "key" in msg or "api" in msg, (
            f"Error should mention missing API key, got: '{result['message']}'"
        )

    @pytest.mark.asyncio
    async def test_use_saved_sentinel_is_not_special(self):
        """
        USE_SAVED was a sentinel in the old implementation. After the localStorage
        migration it's just a wrong key string — should fail with a bad-key error,
        not trigger a DB lookup.
        """
        from routers.settings import test_connection
        result = await test_connection(self._payload(provider="anthropic", api_key="USE_SAVED"))
        assert result["ok"] is False
        # Should NOT return "no connection needed" (old demo fallback message)
        assert "no connection needed" not in result["message"].lower()


# ─── Settings router: POST / (save) ──────────────────────────────────────────

class TestSaveSettingsEndpoint:

    @pytest.mark.asyncio
    async def test_save_does_not_store_api_key(self):
        """
        After the localStorage migration, POST /settings must save provider/model
        but must NOT write the api_key to the database.
        """
        from routers.settings import save_settings, SettingsPayload

        payload = SettingsPayload(
            provider="anthropic",
            api_key="sk-ant-real-key-that-must-not-be-stored",
            model="claude-3-5-sonnet-20241022",
            extra_config={},
        )

        saved_records = []

        class FakeSession:
            async def execute(self, *a, **kw):
                return MagicMock()
            def add(self, rec):
                saved_records.append(rec)
            async def commit(self):
                pass

        await save_settings(payload, db=FakeSession())

        assert len(saved_records) == 1
        assert saved_records[0].api_key == "", (
            "api_key must not be stored server-side; "
            f"got: '{saved_records[0].api_key}'"
        )
        assert saved_records[0].provider == "anthropic"


# ─── Schema router: LLM override ─────────────────────────────────────────────

class TestSchemaLLMOverride:

    @pytest.mark.asyncio
    async def test_demo_override_returns_demo_provider(self):
        from routers.schema import _get_llm_provider
        from services.llm_service import DemoProvider

        provider = await _get_llm_provider(
            db=AsyncMock(),
            override={"provider": "demo", "api_key": "", "model": ""},
        )
        assert isinstance(provider, DemoProvider)

    @pytest.mark.asyncio
    async def test_no_override_empty_db_returns_demo(self):
        """Without an override and no DB record, must fall back to DemoProvider."""
        from routers.schema import _get_llm_provider
        from services.llm_service import DemoProvider

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result_mock)

        provider = await _get_llm_provider(db, override=None)
        assert isinstance(provider, DemoProvider)

    @pytest.mark.asyncio
    async def test_real_override_skips_db_entirely(self):
        """
        If the browser supplies a real provider+key, the DB must never be queried —
        user's key stays only in their browser.
        """
        from routers.schema import _get_llm_provider
        from services.llm_service import AnthropicProvider

        db = AsyncMock()
        db.execute = AsyncMock()

        provider = await _get_llm_provider(db, override={
            "provider": "anthropic",
            "api_key": "sk-ant-fake",
            "model": "claude-3-5-sonnet-20241022",
            "extra_config": {},
        })

        assert isinstance(provider, AnthropicProvider)
        db.execute.assert_not_called()
