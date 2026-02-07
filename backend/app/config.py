from pydantic_settings import BaseSettings
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

    # RAG
    vector_store: str = "pgvector"
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_sec: int = 15
    openai_api_key: str = ""

    # 限额（每日）
    limit_user_daily: int = 50
    limit_group_daily: int = 200
    limit_global_daily: int = 10_000

    # 免责声明
    disclaimer_enabled: bool = True
    disclaimer_text: str = "以上内容仅供参考，不构成投资或法律建议。"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
