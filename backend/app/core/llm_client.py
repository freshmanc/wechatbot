"""
可插拔 LLM 客户端：OpenAI 兼容接口，支持超时与兜底。
"""
import asyncio
from typing import AsyncIterator, Optional

from openai import AsyncOpenAI

from app.config import get_settings
from app.core.errors import LLMTimeoutError


async def chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    timeout_sec: Optional[int] = None,
) -> str:
    """
    调用 LLM 获取单条回复文本。超时则抛 LLMTimeoutError，由上层做兜底文案。
    """
    s = get_settings()
    model = model or s.llm_model
    timeout = timeout_sec if timeout_sec is not None else s.llm_timeout_sec
    client = AsyncOpenAI(api_key=s.openai_api_key)

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1024,
                temperature=0.3,
            ),
            timeout=float(timeout),
        )
    except asyncio.TimeoutError:
        raise LLMTimeoutError("服务繁忙，请稍后再试")
    except Exception as e:
        raise LLMTimeoutError(str(e))

    choice = response.choices[0] if response.choices else None
    if not choice or not getattr(choice.message, "content", None):
        raise LLMTimeoutError("模型未返回有效内容")
    return (choice.message.content or "").strip()


async def chat_completion_stream(
    messages: list[dict],
    model: Optional[str] = None,
    timeout_sec: Optional[int] = None,
) -> AsyncIterator[str]:
    """流式返回（可选，用于长答）。"""
    s = get_settings()
    model = model or s.llm_model
    timeout = timeout_sec if timeout_sec is not None else s.llm_timeout_sec
    client = AsyncOpenAI(api_key=s.openai_api_key)

    try:
        stream = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1024,
                temperature=0.3,
                stream=True,
            ),
            timeout=float(timeout),
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except asyncio.TimeoutError:
        raise LLMTimeoutError("服务繁忙，请稍后再试")
