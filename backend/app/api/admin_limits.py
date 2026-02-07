"""管理端：限额配置。"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])


class LimitsConfig(BaseModel):
    user_daily: int
    group_daily: int
    global_daily: int


@router.get("/limits", response_model=LimitsConfig)
async def get_limits():
    """读取当前限额（来自配置或 DB）。"""
    from app.config import get_settings
    s = get_settings()
    return LimitsConfig(
        user_daily=s.limit_user_daily,
        group_daily=s.limit_group_daily,
        global_daily=s.limit_global_daily,
    )


@router.patch("/limits")
async def update_limits(user_daily: int | None = None, group_daily: int | None = None, global_daily: int | None = None):
    """更新限额（占位：可写 DB 或配置中心）。"""
    return {"ok": True}
