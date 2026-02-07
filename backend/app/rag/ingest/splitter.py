"""文本切分（按段落/长度）。"""
import re
from typing import List


def split_by_paragraphs(text: str, max_chunk_chars: int = 800, overlap: int = 100) -> List[str]:
    """
    先按段落切，单段超长再按 max_chunk_chars 切，overlap 为重叠字符数。
    """
    if not text or not text.strip():
        return []
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chunks = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if len(p) <= max_chunk_chars:
            chunks.append(p)
            continue
        start = 0
        while start < len(p):
            end = min(start + max_chunk_chars, len(p))
            chunk = p[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - overlap if end < len(p) else len(p)
    return chunks
