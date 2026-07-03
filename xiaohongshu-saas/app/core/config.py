"""Application configuration loaded from environment variables / .env file."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_name: str = "xhs-saas"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    app_secret: str = "change-me-please"

    # ---- Database ----
    database_url: str = "sqlite+aiosqlite:///./data/xhs_saas.db"

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/0"

    # ---- Channels ----
    default_channel: str = "xiaohongshu"
    enable_xiaohongshu: bool = True
    enable_douyin: bool = False
    enable_kuaishou: bool = False

    # ---- Anti-detection ----
    human_delay_min_ms: int = 1200
    human_delay_max_ms: int = 4500
    proxy_rotate_every: int = 20
    warmup_hours_before_solopost: int = 24

    # ---- Risk control ----
    daily_post_limit_per_account: int = 5
    hourly_post_limit_per_account: int = 2
    cool_down_minutes_after_fail: int = 30

    # ---- AI ----
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # ---- Admin bootstrap ----
    admin_username: str = "admin"
    admin_password: str = "admin"

    # ---- Misc ----
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])

    # ---- Upstream services (gateway targets) ----
    pbp_api_url: str = "http://localhost:8090"
    lakehouse_api_url: str = "http://localhost:8091"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()