"""
免责声明、引用、字数等策略（可配置开关）。
"""
from app.config import get_settings


def append_disclaimer(text: str) -> str:
    """若开启免责声明，在回答末尾追加。"""
    s = get_settings()
    if not s.disclaimer_enabled or not text:
        return text
    disclaimer = (s.disclaimer_text or "").strip()
    if not disclaimer:
        return text
    if text.rstrip().endswith(disclaimer):
        return text
    return f"{text.rstrip()}\n\n{disclaimer}"


def truncate_answer(text: str, max_chars: int = 2000) -> str:
    """限制回复长度，防止超长。"""
    if not text or len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
