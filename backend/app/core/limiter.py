"""
基于 Redis 的每日限额：用户/群/全局。
Key: user:{user_id}:{yyyyMMdd}, group:{group_id}:{yyyyMMdd}, global:{yyyyMMdd}
Redis 未安装或不可用时跳过限额（便于本地仅测 LLM）。
"""
from datetime import datetime
from typing import Optional, Any

try:
    import redis.asyncio as aioredis  # pyright: ignore[reportMissingImports]
except ImportError:
    aioredis = None  # type: ignore

from app.config import get_settings
from app.core.errors import LimitExceededError

_redis: Optional[Any] = None


async def get_redis() -> Optional[Any]:
    global _redis
    if aioredis is None:
        return None
    if _redis is None:
        try:
            s = get_settings()
            _redis = aioredis.from_url(s.redis_url, decode_responses=True)
        except Exception:
            return None
    return _redis


def _date_suffix() -> str:
    return datetime.utcnow().strftime("%Y%m%d")


async def check_and_incr_user(user_id: str) -> None:
    """检查用户当日次数并 +1，超限抛 LimitExceededError。"""
    r = await get_redis()
    if r is None:
        return
    s = get_settings()
    key = f"user:{user_id}:{_date_suffix()}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 86400 * 2)  # 2 天过期
    if count > s.limit_user_daily:
        await r.decr(key)
        raise LimitExceededError("今日提问次数已达上限", details={"scope": "user", "limit": s.limit_user_daily})


async def check_and_incr_group(group_id: str) -> None:
    """检查群当日次数并 +1。"""
    r = await get_redis()
    if r is None:
        return
    s = get_settings()
    key = f"group:{group_id}:{_date_suffix()}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 86400 * 2)
    if count > s.limit_group_daily:
        await r.decr(key)
        raise LimitExceededError("今日该群提问次数已达上限", details={"scope": "group", "limit": s.limit_group_daily})


async def check_and_incr_global() -> None:
    """检查全局当日次数并 +1。"""
    r = await get_redis()
    if r is None:
        return
    s = get_settings()
    key = f"global:{_date_suffix()}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 86400 * 2)
    if count > s.limit_global_daily:
        await r.decr(key)
        raise LimitExceededError("系统今日请求已达上限", details={"scope": "global", "limit": s.limit_global_daily})


async def check_limits_and_incr(user_id: str, group_id: Optional[str] = None) -> None:
    """先检查全局、再群、再用户，任一超限即抛 LimitExceededError；全部通过则三者均 +1。Redis 不可用时跳过限额。"""
    try:
        await check_and_incr_global()
        if group_id:
            await check_and_incr_group(group_id)
        await check_and_incr_user(user_id)
    except LimitExceededError:
        raise
    except Exception:
        pass  # Redis 未启动/连接失败时跳过限额
