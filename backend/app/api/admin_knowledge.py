"""管理端：知识上传、启停、标签。"""
from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/knowledge/documents")
async def list_documents(domain: str | None = None):
    """文档列表（占位）。"""
    return []


@router.post("/knowledge/upload")
async def upload_document(
    file: UploadFile = File(...),
    domain: str = "montreal_realestate",
    tags: str | None = None,
):
    """上传知识文档（占位：入库走 RAG ingest）。"""
    return {"filename": file.filename, "domain": domain, "status": "pending"}


@router.patch("/knowledge/documents/{doc_id}")
async def update_document(doc_id: str, enabled: bool | None = None, tags: str | None = None):
    """启停/标签（占位）。"""
    return {"ok": True}
