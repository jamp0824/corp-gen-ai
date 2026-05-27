"""
환경 설정.
pydantic-settings로 .env 파일 또는 환경 변수에서 로드.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Anthropic
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"

    # 크롤링
    crawl_budget_sec: float = 25.0
    crawl_max_pages: int = 12
    crawl_concurrency: int = 5
    crawl_page_timeout: float = 4.0

    # 전체 요청 timeout
    request_deadline_sec: float = 58.0

    # DB (향후 확장용)
    database_url: str = "sqlite+aiosqlite:///./ibkbox.db"

    # 앱
    debug: bool = False
    log_level: str = "INFO"


settings = Settings()
