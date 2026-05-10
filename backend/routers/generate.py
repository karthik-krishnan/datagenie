import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import LLMSettings as LLMSettingsModel
from services.data_generator import generate_data
from services.output_formatter import format_output

router = APIRouter()


class GenerateRequest(BaseModel):
    schema: Dict[str, Any]
    characteristics: Dict[str, Any] = {}
    compliance_rules: Dict[str, Any] = {}
    relationships: List[Dict[str, Any]] = []
    volume: int = 100
    formats: List[str] = ["csv"]
    output_options: Dict[str, Any] = {}
    packaging: Optional[str] = "one_file_per_entity"


async def _get_llm_settings(db: AsyncSession):
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
        "api_key": row.api_key or "",
        "model": row.model or "",
        "extra_config": extra,
    }


@router.post("/preview")
async def preview(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
    settings = await _get_llm_settings(db)
    data = generate_data(
        schema=req.schema,
        characteristics=req.characteristics,
        compliance_rules=req.compliance_rules,
        relationships=req.relationships,
        volume=5,
        llm_settings=settings,
        preview=True,
    )
    return {"preview": data}


@router.post("/")
async def generate_full(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
    settings = await _get_llm_settings(db)
    data = generate_data(
        schema=req.schema,
        characteristics=req.characteristics,
        compliance_rules=req.compliance_rules,
        relationships=req.relationships,
        volume=req.volume,
        llm_settings=settings,
        preview=False,
    )

    formats = req.formats or ["csv"]
    fmt = formats[0]
    content, mime, filename = format_output(data, fmt, req.output_options or {}, packaging=req.packaging or "one_file_per_entity")
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
