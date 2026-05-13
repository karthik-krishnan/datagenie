from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
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
    # Kept for backwards-compatibility with older frontend payloads; not used.
    llm_config: Optional[Dict[str, Any]] = None


@router.post("/preview")
async def preview(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
    data = generate_data(
        schema=req.schema,
        characteristics=req.characteristics,
        compliance_rules=req.compliance_rules,
        relationships=req.relationships,
        volume=5,
        preview=True,
    )
    return {"preview": data}


@router.post("/")
async def generate_full(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
    data = generate_data(
        schema=req.schema,
        characteristics=req.characteristics,
        compliance_rules=req.compliance_rules,
        relationships=req.relationships,
        volume=req.volume,
        preview=False,
    )

    formats = req.formats or ["csv"]
    fmt = formats[0]
    content, mime, filename = format_output(data, fmt, req.output_options or {})
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
