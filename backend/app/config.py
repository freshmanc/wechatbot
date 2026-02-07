from pydantic_settings import BaseSettings  # pyright: ignore[reportMissingImports]
from functools import lru_cache


class Settings(BaseSettings):
    # 应用
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # 数据库
    database_url: str = "postgresql+asyncpg://wxbot:wxbot_secret@localhost:5432/wxbot"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # 企业微信
    wecom_corp_id: str = ""
    wecom_agent_id: str = ""
    wecom_secret: str = ""
    wecom_token: str = ""
    wecom_aes_key: str = ""
    wecom_bot_user_id: str = ""  # 应用在群里的 userid，用于判断是否被 @（若回调有 MentionedList）
    wecom_bot_name: str = ""  # 机器人名，用于兜底：内容以 @机器人名 开头也触发

    # RAG / LLM（支持 OpenAI 或 LM Studio 等兼容接口）
    vector_store: str = "pgvector"
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_sec: int = 15
    openai_api_key: str = ""
    openai_base_url: str = ""  # 留空用官方；LM Studio 填如 http://127.0.0.1:1234/v1

    # 限额（每日）
    limit_user_daily: int = 50
    limit_group_daily: int = 200
    limit_global_daily: int = 10_000

    # 免责声明
    disclaimer_enabled: bool = True
    disclaimer_text: str = "以上内容仅供参考，不构成投资或法律建议。"

    # Chroma 持久化目录（留空则内存，重启丢失）
    chroma_persist_dir: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
