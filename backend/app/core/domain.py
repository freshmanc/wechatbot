"""
领域隔离：知识入库与检索均按 domain 过滤。
"""
from typing import List

# 默认支持的领域（可与 DB domains 表同步）
DEFAULT_DOMAINS = ["montreal_realestate"]


def normalize_domain(domain: str) -> str:
    return (domain or "").strip().lower() or "default"


def is_allowed_domain(domain: str, allowed: List[str] | None = None) -> bool:
    if not domain:
        return False
    allowed = allowed or DEFAULT_DOMAINS
    return normalize_domain(domain) in [normalize_domain(d) for d in allowed]
