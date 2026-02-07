"""知识入库：切分 → 向量化 → 写入向量库。"""
from pathlib import Path
from typing import List

from app.config import get_settings
from app.rag.ingest.embedder import embed_texts
from app.rag.ingest.splitter import split_by_paragraphs


async def index_document(
    content: str,
    domain: str,
    doc_id: str,
    source: str = "",
    title: str = "",
) -> int:
    """
    将一篇文档切分、向量化并写入当前配置的向量库。返回写入的 chunk 数。
    """
    chunks = split_by_paragraphs(content)
    if not chunks:
        return 0
    embeddings = await embed_texts(chunks)
    s = get_settings()
    if s.vector_store == "pgvector":
        from app.rag.stores.vector_store_pgvector import add_chunks
        return await add_chunks(domain, doc_id, source, title, chunks, embeddings)
    if s.vector_store == "chroma":
        from app.rag.stores.vector_store_chroma import add_chunks
        return await add_chunks(domain, doc_id, source, title, chunks, embeddings)
    raise ValueError(f"Unknown vector_store: {s.vector_store}")
