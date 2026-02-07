from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin_knowledge, admin_limits, admin_logs, admin_prompts, chat, stats
from app.wecom import webhook as wecom_webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时可选：初始化 DB、预连 Redis 等
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
