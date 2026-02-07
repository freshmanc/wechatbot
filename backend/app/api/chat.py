"""
POST /v1/chat/ask — 统一问答入口。
限额、风控、超时兜底、日志记录。
"""
import json
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.domain import is_allowed_domain
from app.core.errors import LimitExceededError, LLMTimeoutError
from app.core.limiter import check_limits_and_incr
from app.core.policies import append_disclaimer, truncate_answer
from app.db.models import UsageLog
from app.db.session import get_async_session_factory

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
# 超限时统一返回 200 + 此文案，便于 WeCom 等回调正确展示「今日次数已达上限」
LIMIT_EXCEEDED_ANSWER = "今日提问次数已达上限，明天再试哦。"


@router.post("/chat/ask", response_model=AskResponse)
async def chat_ask(req: AskRequest) -> AskResponse:
    request_id = str(uuid.uuid4())
    flags: dict[str, bool] = {"limited": False, "fallback": False}
    start = time.perf_counter()

    # 限额：超限时返回 200 + flags.limited，不抛 429，便于 WeCom 回调正确提示用户
    try:
        await check_limits_and_incr(req.user_id, req.group_id)
    except LimitExceededError:
        return AskResponse(
            request_id=request_id,
            answer=LIMIT_EXCEEDED_ANSWER,
            citations=[],
            flags={"limited": True, "fallback": False},
        )

    # 领域
    if not is_allowed_domain(req.domain):
        raise HTTPException(status_code=400, detail="不支持的领域")

    # RAG：检索 + 生成（若未实现 RAG 则直接走 LLM 或固定回复）
    answer = ""
    citations_raw: list[dict[str, Any]] = []
    try:
        from app.rag.runtime.answer import answer_with_rag
        answer, citations_raw, flags["fallback"] = await answer_with_rag(
            question=req.text,
            domain=req.domain,
            conversation_id=req.conversation_id,
        )
    except LLMTimeoutError:
        answer = FALLBACK_ANSWER
        flags["fallback"] = True
    except ImportError as e:
        # 依赖未装或 RAG 模块导入失败（如 chromadb / openai）
        err_str = str(e)
        missing = getattr(e, "name", None) or (err_str.split("'")[1] if "'" in err_str else err_str)
        answer = f"问答功能正在配置中，请稍后再试。若已配置 LM Studio，请执行：pip install -r requirements.txt（缺失：{missing}）"
        flags["fallback"] = True
    except Exception as e:
        answer = FALLBACK_ANSWER
        flags["fallback"] = True
        # 可写 usage_log 记错误

    answer = append_disclaimer(truncate_answer(answer))
    elapsed_ms = (time.perf_counter() - start) * 1000

    try:
        fac = get_async_session_factory()
        if fac is None:
            pass
        else:
            async with fac() as db:
                log = UsageLog(
                    request_id=request_id,
                    platform=req.platform,
                    group_id=req.group_id or None,
                    user_id=req.user_id,
                    domain=req.domain,
                    question=req.text,
                    answer=answer,
                    citations_json=json.dumps([c.get("source") for c in citations_raw], ensure_ascii=False),
                    elapsed_ms=round(elapsed_ms, 2),
                    token_used=None,
                    fallback=flags.get("fallback", False),
                    error_message=None,
                )
                db.add(log)
                await db.commit()
    except Exception:
        pass  # 无数据库时跳过日志，不影响返回

    citations: list[Citation] = [
        Citation(source=c.get("source", ""), title=c.get("title"), chunk_id=c.get("chunk_id"))
        for c in citations_raw
    ]
    return AskResponse(
        request_id=request_id,
        answer=answer,
        citations=citations,
        flags=flags,
    )
