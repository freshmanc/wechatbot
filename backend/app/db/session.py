"""异步数据库会话。无 DB/asyncpg 时延迟创建失败，便于仅测 LLM 时启动。"""
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base

_engine = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _get_engine():
    global _engine
    if _engine is None:
        s = get_settings()
        url = s.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        _engine = create_async_engine(url, echo=False)
    return _engine


def get_async_session_factory() -> Optional[async_sessionmaker[AsyncSession]]:
    """首次使用时才建连；asyncpg 未装或 Postgres 不可用时返回 None。"""
    global _async_session_factory
    if _async_session_factory is not None:
        return _async_session_factory
    try:
        eng = _get_engine()
        _async_session_factory = async_sessionmaker(
            eng, class_=AsyncSession, expire_on_commit=False
        )
        return _async_session_factory
    except Exception:
        return None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    fac = get_async_session_factory()
    if fac is None:
        return
    async with fac() as session:
        yield session


async def init_db():
    """创建表（开发用）。DB 不可用时跳过。"""
    try:
        engine = _get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass
