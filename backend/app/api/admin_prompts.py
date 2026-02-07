"""管理端：Prompt 版本管理。"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])


class PromptVersion(BaseModel):
    id: str
    name: str
    domain: str | None
    content: str
    active: bool


@router.get("/prompts", response_model=list)
async def list_prompts(domain: str | None = None):
    """Prompt 版本列表（占位）。"""
    return []


@router.post("/prompts")
async def create_prompt(name: str, domain: str | None, content: str):
    """创建版本（占位）。"""
    return {"id": "placeholder", "active": False}


@router.patch("/prompts/{prompt_id}/active")
async def set_active_prompt(prompt_id: str, active: bool = True):
    """设为当前使用（占位）。"""
    return {"ok": True}
