"""检索：按 domain 过滤，返回 top_k 片段。"""
from typing import List, Tuple

from app.config import get_settings


async def retrieve(question: str, domain: str, top_k: int = 5) -> List[Tuple[str, str, str, float]]:
    """
    返回 [(chunk_content, source, chunk_id, score), ...]
    """
    s = get_settings()
    if s.vector_store == "pgvector":
        from app.rag.stores.vector_store_pgvector import search
        return await search(domain, question, top_k)
    if s.vector_store == "chroma":
        from app.rag.stores.vector_store_chroma import search
        return await search(domain, question, top_k)
    return []
