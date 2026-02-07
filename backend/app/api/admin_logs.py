"""管理端：日志回看、质量标注。"""
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])


class LogItem(BaseModel):
    id: str
    request_id: str
    question: str
    answer: str
    domain: str
    created_at: str
    fallback: bool


@router.get("/logs", response_model=list)
async def list_logs(
    domain: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """日志列表（占位，后续接 DB usage_logs）。"""
    return []


@router.post("/logs/{log_id}/rate")
async def rate_log(log_id: str, rating: str = Query(..., pattern="^(good|normal|bad)$")):
    """质量标注（占位）。"""
    return {"ok": True}
