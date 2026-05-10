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
    result = await db.execute(select(LLMSettingsModel).order_by(LLMSettingsModel.id.desc()).limit(1))
    row = result.scalar_one_or_none()
    if not row:
        return {"provider": "demo", "api_key": "", "model": "", "extra_config": {}}
    try:
        extra = json.loads(row.extra_config or "{}")
    except Exception:
        extra = {}
    return {
        "provider": row.provider,
        "api_key": "***" if row.api_key else "",
        "model": row.model,
        "extra_config": extra,
    }


@router.post("/test")
async def test_connection(payload: SettingsPayload, db: AsyncSession = Depends(get_db)):
    """Try a minimal LLM call to verify the credentials work."""
    from services.llm_service import get_provider, DemoProvider

    api_key = payload.api_key or ""

    # If the frontend signals "use the saved key", fetch it from DB
    if api_key in ("USE_SAVED", "KEEP_SAVED", "***", ""):
        result = await db.execute(select(LLMSettingsModel).order_by(LLMSettingsModel.id.desc()).limit(1))
        row = result.scalar_one_or_none()
        if row and row.provider == payload.provider and row.api_key:
            api_key = row.api_key

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
    api_key = payload.api_key or ""

    # If frontend signals to keep the existing key, fetch it from DB instead of overwriting
    if api_key in ("KEEP_SAVED", "USE_SAVED", "***"):
        result = await db.execute(select(LLMSettingsModel).order_by(LLMSettingsModel.id.desc()).limit(1))
        row = result.scalar_one_or_none()
        api_key = (row.api_key if row else "") or ""

    await db.execute(delete(LLMSettingsModel))
    rec = LLMSettingsModel(
        provider=payload.provider,
        api_key=api_key,
        model=payload.model or "",
        extra_config=json.dumps(payload.extra_config or {}),
    )
    db.add(rec)
    await db.commit()
    return {"ok": True, "provider": payload.provider}
