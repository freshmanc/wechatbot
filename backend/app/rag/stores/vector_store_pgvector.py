"""
pgvector 向量存储：需启用 pgvector 扩展，表 chunks 含 embedding vector(1536)。
"""
from typing import List, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings

# 使用与 app 相同的 database_url，但需 async
_settings = get_settings()
url = _settings.database_url
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

# 单独 engine 用于 raw SQL（若与 ORM 共用可复用 app.db.session.engine）
_engine = create_async_engine(url, echo=False)


async def _ensure_schema():
    """确保有 vector 扩展和 rag_chunks 表。"""
    async with _engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id SERIAL PRIMARY KEY,
                domain VARCHAR(64) NOT NULL,
                doc_id VARCHAR(128) NOT NULL,
                source VARCHAR(512),
                title VARCHAR(256),
                content TEXT NOT NULL,
                chunk_index INT DEFAULT 0,
                embedding vector(1536)
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rag_chunks_domain ON rag_chunks(domain)"))


async def add_chunks(
    domain: str,
    doc_id: str,
    source: str,
    title: str,
    chunks: List[str],
    embeddings: List[List[float]],
) -> int:
    await _ensure_schema()
    async with _engine.begin() as conn:
        for i, (content, emb) in enumerate(zip(chunks, embeddings)):
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            await conn.execute(
                text("""
                    INSERT INTO rag_chunks (domain, doc_id, source, title, content, chunk_index, embedding)
                    VALUES (:domain, :doc_id, :source, :title, :content, :chunk_index, :embedding::vector)
                """),
                {
                    "domain": domain,
                    "doc_id": doc_id,
                    "source": source or "",
                    "title": title or "",
                    "content": content,
                    "chunk_index": i,
                    "embedding": emb_str,
                },
            )
    return len(chunks)


async def search(domain: str, question: str, top_k: int = 5) -> List[Tuple[str, str, str, float]]:
    """需先将 question 向量化，再按 domain 过滤 + 余弦相似度检索。"""
    from app.rag.ingest.embedder import embed_texts
    await _ensure_schema()
    q_emb = (await embed_texts([question]))[0]
    emb_str = "[" + ",".join(str(x) for x in q_emb) + "]"
    async with _engine.connect() as conn:
        # 余弦相似度：embedding <=> :emb 返回距离，1 - 距离可作相似度
        r = await conn.execute(
            text("""
                SELECT content, source, id::text, 1 - (embedding <=> :emb::vector) as score
                FROM rag_chunks
                WHERE domain = :domain
                ORDER BY embedding <=> :emb::vector
                LIMIT :top_k
            """),
            {"domain": domain, "emb": emb_str, "top_k": top_k},
        )
        rows = r.fetchall()
    return [(row[0], row[1] or "", row[2], float(row[3])) for row in rows]
