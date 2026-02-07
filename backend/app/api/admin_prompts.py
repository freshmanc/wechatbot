"""管理端：Prompt 版本管理。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PromptVersion as PromptVersionModel
from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


class PromptVersion(BaseModel):
    id: int
    name: str
    domain: str | None
    content: str
    active: bool


@router.get("/prompts", response_model=list)
async def list_prompts(
    domain: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Prompt 版本列表。"""
    q = select(PromptVersionModel).order_by(PromptVersionModel.id.desc())
    if domain:
        q = q.where(PromptVersionModel.domain == domain)
    r = await db.execute(q)
    rows = r.scalars().all()
    return [
        PromptVersion(id=row.id, name=row.name, domain=row.domain, content=row.content, active=row.active)
        for row in rows
    ]


class CreatePromptBody(BaseModel):
    name: str
    domain: str | None = None
    content: str


@router.post("/prompts")
async def create_prompt(
    body: CreatePromptBody,
    db: AsyncSession = Depends(get_db),
):
    """创建版本。"""
    row = PromptVersionModel(name=body.name, domain=body.domain or None, content=body.content, active=False)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "active": False}


@router.patch("/prompts/{prompt_id}/active")
async def set_active_prompt(
    prompt_id: str,
    active: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """设为当前使用：同 domain 下先全部置为 False，再置当前为 active。"""
    pid = int(prompt_id)
    row = (await db.execute(select(PromptVersionModel).where(PromptVersionModel.id == pid))).scalar_one_or_none()
    if not row:
        return {"ok": False, "error": "not found"}
    if active:
        await db.execute(
            update(PromptVersionModel).where(PromptVersionModel.domain == row.domain).values(active=False)
        )
    await db.execute(update(PromptVersionModel).where(PromptVersionModel.id == pid).values(active=active))
    await db.commit()
    return {"ok": True}
