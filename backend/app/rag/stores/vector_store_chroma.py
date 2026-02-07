"""
Chroma 向量存储。支持持久化目录，重启不丢索引。
"""
from pathlib import Path
from typing import List, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings
from app.rag.ingest.embedder import embed_texts

_client = None


def _get_client():
    global _client
    if _client is None:
        s = get_settings()
        if s.chroma_persist_dir:
            path = Path(s.chroma_persist_dir).resolve()
            path.mkdir(parents=True, exist_ok=True)
            _client = chromadb.PersistentClient(path=str(path), settings=ChromaSettings(anonymized_telemetry=False))
        else:
            _client = chromadb.Client(ChromaSettings(anonymized_telemetry=False))
    return _client


async def add_chunks(
    domain: str,
    doc_id: str,
    source: str,
    title: str,
    chunks: List[str],
    embeddings: List[List[float]],
) -> int:
    client = _get_client()
    coll_name = f"rag_{domain}".replace("-", "_")
    try:
        coll = client.get_collection(coll_name)
    except Exception:
        coll = client.create_collection(coll_name, metadata={"description": domain})
    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    meta = [{"source": source, "title": title} for _ in chunks]
    coll.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=meta)
    return len(chunks)


async def search(domain: str, question: str, top_k: int = 5) -> List[Tuple[str, str, str, float]]:
    client = _get_client()
    coll_name = f"rag_{domain}".replace("-", "_")
    try:
        coll = client.get_collection(coll_name)
    except Exception:
        return []
    q_emb = (await embed_texts([question]))[0]
    res = coll.query(query_embeddings=[q_emb], n_results=top_k, include=["documents", "metadatas", "distances"])
    out = []
    if res["documents"] and res["documents"][0]:
        for i, doc in enumerate(res["documents"][0]):
            meta = (res["metadatas"][0] or [{}])[i] if res["metadatas"] else {}
            dist = (res["distances"][0] or [0])[i] if res["distances"] else 0
            # Chroma 默认用 L2，这里用 1/(1+d) 近似相似度
            score = 1.0 / (1.0 + float(dist))
            source = meta.get("source") or meta.get("title") or ""
            chunk_id = (res["ids"][0] or [""])[i] if res["ids"] else ""
            out.append((doc, source, chunk_id, score))
    return out
