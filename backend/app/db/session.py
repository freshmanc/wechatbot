"""异步数据库会话。"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base

_settings = get_settings()
# 确保 URL 为 async 驱动
url = _settings.database_url
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def init_db():
    """创建表（开发用；生产建议用 Alembic 迁移）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
