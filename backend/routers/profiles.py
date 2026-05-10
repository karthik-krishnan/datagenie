from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Profile

router = APIRouter(prefix="/profiles", tags=["profiles"])


class ProfileIn(BaseModel):
    name: str
    description: Optional[str] = None
    schema_config: Optional[str] = None
    characteristics: Optional[str] = None
    compliance_rules: Optional[str] = None
    relationships: Optional[str] = None
    output_config: Optional[str] = None


def _summary(p: Profile) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "last_used_at": p.last_used_at.isoformat() if p.last_used_at else None,
    }


def _full(p: Profile) -> dict:
    return {
        **_summary(p),
        "schema_config": p.schema_config,
        "characteristics": p.characteristics,
        "compliance_rules": p.compliance_rules,
        "relationships": p.relationships,
        "output_config": p.output_config,
    }


@router.get("/")
async def list_profiles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Profile).order_by(Profile.updated_at.desc()))
    profiles = result.scalars().all()
    return [_summary(p) for p in profiles]


@router.post("/")
async def create_profile(payload: ProfileIn, db: AsyncSession = Depends(get_db)):
    p = Profile(
        name=payload.name,
        description=payload.description,
        schema_config=payload.schema_config,
        characteristics=payload.characteristics,
        compliance_rules=payload.compliance_rules,
        relationships=payload.relationships,
        output_config=payload.output_config,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _full(p)


@router.get("/{profile_id}")
async def get_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _full(p)


@router.put("/{profile_id}")
async def update_profile(profile_id: str, payload: ProfileIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    p.name = payload.name
    p.description = payload.description
    p.schema_config = payload.schema_config
    p.characteristics = payload.characteristics
    p.compliance_rules = payload.compliance_rules
    p.relationships = payload.relationships
    p.output_config = payload.output_config
    await db.commit()
    await db.refresh(p)
    return _full(p)


@router.delete("/{profile_id}")
async def delete_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    await db.delete(p)
    await db.commit()
    return {"ok": True, "id": profile_id}


@router.post("/{profile_id}/use")
async def use_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    p.last_used_at = datetime.utcnow()
    await db.commit()
    await db.refresh(p)
    return _full(p)
