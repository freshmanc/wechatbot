"""
POST /v1/chat/ask — 统一问答入口。
限额、风控、超时兜底、日志记录。
"""
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.domain import is_allowed_domain
from app.core.errors import LimitExceededError, LLMTimeoutError, NoRetrievalError
from app.core.limiter import check_limits_and_incr
from app.core.policies import append_disclaimer, truncate_answer

router = APIRouter(prefix="/v1", tags=["chat"])


class AskRequest(BaseModel):
    platform: str = "wecom"
    group_id: str = Field(..., description="群 ID")
    user_id: str = Field(..., description="提问用户 ID")
    text: str = Field(..., min_length=1, max_length=2000)
    domain: str = Field(default="montreal_realestate", description="领域")
    conversation_id: Optional[str] = None


class Citation(BaseModel):
    source: str
    title: Optional[str] = None
    chunk_id: Optional[str] = None


class AskResponse(BaseModel):
    request_id: str
    answer: str
    citations: list[Citation] = []
    flags: dict[str, bool] = Field(default_factory=lambda: {"limited": False, "fallback": False})


# 兜底文案（LLM 超时或异常时返回）
FALLBACK_ANSWER = "服务繁忙，请稍后再试。"


@router.post("/chat/ask", response_model=AskResponse)
async def chat_ask(req: AskRequest) -> AskResponse:
    request_id = str(uuid.uuid4())
    flags: dict[str, bool] = {"limited": False, "fallback": False}
    start = time.perf_counter()

    # 限额
    try:
        await check_limits_and_incr(req.user_id, req.group_id)
    except LimitExceededError as e:
        raise HTTPException(status_code=429, detail={"code": e.code, "message": e.message})

    # 领域
    if not is_allowed_domain(req.domain):
        raise HTTPException(status_code=400, detail="不支持的领域")

    # RAG：检索 + 生成（若未实现 RAG 则直接走 LLM 或固定回复）
    answer = ""
    citations: list[Citation] = []
    try:
        from app.rag.runtime.answer import answer_with_rag
        answer, citations, flags["fallback"] = await answer_with_rag(
            question=req.text,
            domain=req.domain,
            conversation_id=req.conversation_id,
        )
    except NoRetrievalError:
        answer = "知识库暂无相关内容。"
    except LLMTimeoutError:
        answer = FALLBACK_ANSWER
        flags["fallback"] = True
    except ImportError:
        # RAG 未实现时占位
        answer = "问答功能正在配置中，请稍后再试。"
        flags["fallback"] = True
    except Exception as e:
        answer = FALLBACK_ANSWER
        flags["fallback"] = True
        # 可写 usage_log 记错误

    answer = append_disclaimer(truncate_answer(answer))
    elapsed = time.perf_counter() - start

    # TODO: 写入 usage_logs（request_id, 问题, 答案, 引用, 耗时, token, fallback）
    return AskResponse(
        request_id=request_id,
        answer=answer,
        citations=[
            Citation(source=c.get("source", ""), title=c.get("title"), chunk_id=c.get("chunk_id"))
            for c in (citations if isinstance(citations, list) else [])
        ],
        flags=flags,
    )
