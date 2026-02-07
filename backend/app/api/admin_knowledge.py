"""管理端：知识上传、启停、标签。"""
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document
from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/knowledge/documents")
async def list_documents(
    domain: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """文档列表（documents 表）。"""
    q = select(Document).order_by(Document.id.desc())
    if domain:
        q = q.where(Document.domain == domain)
    r = await db.execute(q)
    rows = r.scalars().all()
    return [
        {
            "id": row.id,
            "domain": row.domain,
            "title": row.title,
            "source_path": row.source_path,
            "tags": row.tags,
            "enabled": row.enabled,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/knowledge/upload")
async def upload_document(
    file: UploadFile = File(...),
    domain: str = "montreal_realestate",
    tags: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """上传知识文档：写入 documents 表并调用 RAG 入库。"""
    content = (await file.read()).decode("utf-8", errors="ignore")
    title = file.filename or "untitled"
    doc = Document(domain=domain, title=title, source_path=file.filename, tags=tags or "", enabled=True)
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    try:
        from app.rag.ingest.indexer import index_document
        count = await index_document(
            content=content,
            domain=domain,
            doc_id=str(doc.id),
            source=file.filename or "",
            title=title,
        )
        return {"filename": file.filename, "domain": domain, "status": "ok", "chunks": count}
    except Exception as e:
        return {"filename": file.filename, "domain": domain, "status": "error", "error": str(e)}


@router.patch("/knowledge/documents/{doc_id}")
async def update_document(
    doc_id: str,
    enabled: bool | None = None,
    tags: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """启停/标签。"""
    from sqlalchemy import update
    doc_id_int = int(doc_id)
    upd = {}
    if enabled is not None:
        upd["enabled"] = enabled
    if tags is not None:
        upd["tags"] = tags
    if upd:
        await db.execute(update(Document).where(Document.id == doc_id_int).values(**upd))
        await db.commit()
    return {"ok": True}
