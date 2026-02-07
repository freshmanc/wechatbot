"""统计接口（占位）。"""
from fastapi import APIRouter, Query

router = APIRouter(prefix="/v1", tags=["stats"])


@router.get("/stats/usage")
async def usage_stats(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    domain: str | None = Query(None),
):
    """用量统计（占位）。"""
    return {"total": 0, "by_domain": {}, "by_day": []}
