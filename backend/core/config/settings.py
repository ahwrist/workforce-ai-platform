from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "WorkforceAI Platform"
    app_version: str = "0.1.0"
    debug: bool = False
    secret_key: str = "changeme_in_production"
    admin_api_key: str = "changeme_admin_key"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/workforce_ai"

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    synthesizer_model: str = "claude-haiku-4-5-20251001"
    taxonomist_model: str = "claude-haiku-4-5-20251001"
    interviewer_model: str = "claude-sonnet-4-6"
    embedding_model: str = "text-embedding-3-small"

    # Scraping
    scraper_proxy_url: str = ""
    scraper_delay_seconds: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
