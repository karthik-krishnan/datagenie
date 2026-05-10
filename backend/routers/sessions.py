from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Session as SessionModel

router = APIRouter()


@router.post("/")
async def create_session(db: AsyncSession = Depends(get_db)):
    session = SessionModel()
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": str(session.id), "created_at": session.created_at.isoformat()}


@router.get("/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    import uuid as _uuid
    result = await db.execute(select(SessionModel).where(SessionModel.id == _uuid.UUID(session_id)))
    session = result.scalar_one_or_none()
    if not session:
        return {"error": "not found"}
    return {"session_id": str(session.id), "status": session.status}
