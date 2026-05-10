import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database import get_db
from models import LLMSettings as LLMSettingsModel

router = APIRouter()


class SettingsPayload(BaseModel):
    provider: str
    api_key: Optional[str] = ""
    model: Optional[str] = ""
    extra_config: Optional[Dict[str, Any]] = {}


@router.get("/")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Returns non-sensitive settings only. API keys are stored in the browser, not here."""
    result = await db.execute(select(LLMSettingsModel).order_by(LLMSettingsModel.id.desc()).limit(1))
    row = result.scalar_one_or_none()
    if not row:
        return {"provider": "demo", "model": "", "extra_config": {}}
    try:
        extra = json.loads(row.extra_config or "{}")
    except Exception:
        extra = {}
    return {
        "provider": row.provider,
        "model": row.model,
        "extra_config": extra,
    }


@router.post("/test")
async def test_connection(payload: SettingsPayload):
    """Test the supplied LLM credentials. The key comes directly from the browser — never stored."""
    from services.llm_service import get_provider, DemoProvider

    if payload.provider == "demo":
        return {"ok": False, "message": "Demo mode uses sample data — no connection needed."}

    api_key = (payload.api_key or "").strip()
    if not api_key and payload.provider not in ("demo", "ollama"):
        return {"ok": False, "message": "No API key provided — enter your key and try again."}

    settings = {
        "provider": payload.provider,
        "api_key": api_key,
        "model": payload.model or "",
        "extra_config": payload.extra_config or {},
    }
    try:
        provider = get_provider(settings)
        if isinstance(provider, DemoProvider):
            return {"ok": False, "message": "No API key found — enter your key and try again."}
        result = provider.generate("Reply with the single word: ok", "You are a test.")
        if result and "error" not in result.lower()[:30]:
            return {"ok": True, "message": "Connected successfully. Model responded."}
        return {"ok": False, "message": f"Provider returned: {result[:120]}"}
    except Exception as e:
        return {"ok": False, "message": str(e)[:200]}


@router.post("/")
async def save_settings(payload: SettingsPayload, db: AsyncSession = Depends(get_db)):
    """Saves non-sensitive settings (provider, model, endpoint) for self-hosted deployments.
    API keys are no longer saved server-side — they live in the browser's localStorage."""
    await db.execute(delete(LLMSettingsModel))
    rec = LLMSettingsModel(
        provider=payload.provider,
        api_key="",  # never store API keys server-side
        model=payload.model or "",
        extra_config=json.dumps(payload.extra_config or {}),
    )
    db.add(rec)
    await db.commit()
    return {"ok": True, "provider": payload.provider}
