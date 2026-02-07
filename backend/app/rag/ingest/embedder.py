"""向量化：调用 OpenAI Embedding。"""
from typing import List

from openai import AsyncOpenAI

from app.config import get_settings


async def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    s = get_settings()
    client = AsyncOpenAI(api_key=s.openai_api_key)
    r = await client.embeddings.create(
        model=s.embedding_model,
        input=texts,
    )
    return [item.embedding for item in r.data]
