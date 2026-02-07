"""管理端：日志回看、质量标注。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select  # pyright: ignore[reportMissingImports]
from sqlalchemy.ext.asyncio import AsyncSession  # pyright: ignore[reportMissingImports]

from app.db.models import Rating, UsageLog
from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


class LogItem(BaseModel):
    id: int
    request_id: str
    question: str
    answer: str
    domain: str
    created_at: str
    fallback: bool

    class Config:
        from_attributes = True


@router.get("/logs", response_model=list)
async def list_logs(
    domain: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """日志列表（usage_logs）。"""
    q = select(UsageLog).order_by(UsageLog.id.desc()).offset(offset).limit(limit)
    if domain:
        q = q.where(UsageLog.domain == domain)
    r = await db.execute(q)
    rows = r.scalars().all()
    return [
        LogItem(
            id=row.id,
            request_id=row.request_id,
            question=row.question[:200] + "..." if len(row.question) > 200 else row.question,
            answer=row.answer[:200] + "..." if len(row.answer) > 200 else row.answer,
            domain=row.domain,
            created_at=row.created_at.isoformat() if row.created_at else "",
            fallback=row.fallback,
        )
        for row in rows
    ]


@router.post("/logs/{log_id}/rate")
async def rate_log(
    log_id: str,
    rating: str = Query(..., pattern="^(good|normal|bad)$"),
    db: AsyncSession = Depends(get_db),
):
    """质量标注：写入 ratings 表。"""
    log_id_int = int(log_id)
    db.add(Rating(log_id=log_id_int, rating=rating))
    await db.commit()
    return {"ok": True}
