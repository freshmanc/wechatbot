"""组装系统 Prompt + 检索上下文 + 用户问题。"""
from typing import List, Tuple


SYSTEM_PROMPT = """你是一个基于知识库的问答助手。请仅根据下面提供的「参考内容」回答问题。
如果参考内容中没有与问题相关的信息，请明确说「知识库暂无相关内容」，不要编造。
回答请简洁、准确。"""


def build_messages(
    question: str,
    retrieved: List[Tuple[str, str, str, float]],
) -> list[dict]:
    """
    构建发给 LLM 的 messages：system(含参考) + user(问题)。
    """
    if not retrieved:
        context = "（暂无参考内容）"
        refs = []
    else:
        lines = []
        refs = []
        for i, (content, source, chunk_id, _) in enumerate(retrieved, 1):
            lines.append(f"[{i}]\n{content}")
            refs.append({"source": source, "title": source, "chunk_id": chunk_id})
        context = "\n\n---\n\n".join(lines)
    system = f"{SYSTEM_PROMPT}\n\n【参考内容】\n{context}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ], refs
