from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin_knowledge, admin_limits, admin_logs, admin_prompts, chat, stats
from app.wecom import webhook as wecom_webhook


class UTF8JSONResponse(JSONResponse):
    """JSON 响应统一 UTF-8，中文不转义，避免客户端解析乱码。"""
    media_type = "application/json; charset=utf-8"

    def render(self, content: bytes | str | dict | list) -> bytes:
        import json
        if isinstance(content, bytes):
            return content
        if isinstance(content, str):
            return content.encode("utf-8")
        return json.dumps(
            content, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":")
        ).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import init_db
    try:
        await init_db()
    except Exception:
        pass  # 无数据库时跳过建表，仅问答仍可测
    yield
    # 关闭时清理
    try:
        from app.core.limiter import _redis
        if _redis:
            await _redis.aclose()
    except Exception:
        pass


app = FastAPI(
    title="企业微信群内问答机器人",
    description="WeCom 自建应用 + RAG 问答",
    version="0.1.0",
    lifespan=lifespan,
    default_response_class=UTF8JSONResponse,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wecom_webhook.router)
app.include_router(chat.router)
app.include_router(stats.router)
app.include_router(admin_logs.router)
app.include_router(admin_knowledge.router)
app.include_router(admin_prompts.router)
app.include_router(admin_limits.router)


@app.get("/health")
def health():
    return {"status": "ok"}
