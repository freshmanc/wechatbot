"""
RAG 回答：检索 → 组装 Prompt → LLM 生成 → 超时兜底。
"""
from typing import List, Tuple

from app.config import get_settings
from app.core.errors import LLMTimeoutError, NoRetrievalError
from app.core.llm_client import chat_completion
from app.rag.runtime.composer import build_messages
from app.rag.runtime.retriever import retrieve


async def answer_with_rag(
    question: str,
    domain: str,
    conversation_id: str | None = None,
    top_k: int = 5,
) -> Tuple[str, List[dict], bool]:
    """
    返回 (answer, citations, fallback)。
    检索为空时抛 NoRetrievalError；LLM 超时返回兜底文案并 fallback=True。
    """
    s = get_settings()
    fallback = False
    retrieved = await retrieve(question, domain, top_k=top_k)
    if not retrieved:
        raise NoRetrievalError("知识库暂无相关内容")
    messages, citations = build_messages(question, retrieved)
    try:
        answer = await chat_completion(messages, timeout_sec=s.llm_timeout_sec)
    except LLMTimeoutError:
        answer = "服务繁忙，请稍后再试。"
        fallback = True
    return answer, citations, fallback
