"""
RAG 回答：检索 → 组装 Prompt → LLM 生成 → 超时兜底。
检索为空时仍用 LLM 直接回答（无知识库），便于未装 chromadb 时也能用本地 Qwen。
"""
from typing import List, Tuple

from app.config import get_settings
from app.core.errors import LLMTimeoutError
from app.core.llm_client import chat_completion
from app.rag.runtime.composer import build_messages
from app.rag.runtime.retriever import retrieve

# 无检索时直接问 LLM 的系统提示
_NO_CONTEXT_SYSTEM = "你是一个有帮助的助手。请根据用户问题简要、准确地回答。若无法回答请如实说明。"


async def answer_with_rag(
    question: str,
    domain: str,
    conversation_id: str | None = None,
    top_k: int = 5,
) -> Tuple[str, List[dict], bool]:
    """
    返回 (answer, citations, fallback)。
    检索为空时不再抛错，改为用 LLM 直接回答（无知识库）；LLM 超时则 fallback=True。
    """
    s = get_settings()
    fallback = False
    try:
        retrieved = await retrieve(question, domain, top_k=top_k)
    except Exception:
        retrieved = []
    if not retrieved:
        messages = [
            {"role": "system", "content": _NO_CONTEXT_SYSTEM},
            {"role": "user", "content": question},
        ]
        citations = []
    else:
        messages, citations = build_messages(question, retrieved)
    try:
        answer = await chat_completion(messages, timeout_sec=s.llm_timeout_sec)
    except LLMTimeoutError:
        answer = "服务繁忙，请稍后再试。"
        fallback = True
    return answer, citations, fallback
