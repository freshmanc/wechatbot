from typing import Any, Optional


class AppError(Exception):
    """业务异常基类"""

    def __init__(
        self,
        message: str,
        code: str = "ERROR",
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class LimitExceededError(AppError):
    """限额超限"""

    def __init__(self, message: str = "今日提问次数已达上限", details: Optional[dict] = None):
        super().__init__(message, code="LIMIT_EXCEEDED", details=details)


class DomainNotFoundError(AppError):
    """领域不存在"""

    def __init__(self, domain: str):
        super().__init__(f"领域不存在: {domain}", code="DOMAIN_NOT_FOUND", details={"domain": domain})


class NoRetrievalError(AppError):
    """检索无结果，防胡说"""

    def __init__(self, message: str = "知识库暂无相关内容"):
        super().__init__(message, code="NO_RETRIEVAL", details={})


class LLMTimeoutError(AppError):
    """LLM 超时，走兜底"""

    def __init__(self, message: str = "服务繁忙，请稍后再试"):
        super().__init__(message, code="LLM_TIMEOUT", details={})
