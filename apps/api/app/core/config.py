"""Typed application settings.

All env access in the codebase goes through ``get_settings()``. Never read
``os.environ`` directly outside this module.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppEnv(StrEnum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnv = AppEnv.LOCAL

    api_host: str = "0.0.0.0"  # noqa: S104 — bound by container, not host network
    api_port: int = 8000

    database_url: str = "postgresql+asyncpg://vestrs:change_me_in_local@postgres:5432/vestrs"
    redis_url: str = "redis://redis:6379/0"

    # NoDecode disables pydantic-settings' implicit JSON parsing so the
    # validator below sees the raw env string and can accept comma-separated
    # input (more readable in .env files than embedded JSON).
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    log_level: str = "INFO"

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: Any) -> Any:
        # Accept JSON list (`["a","b"]`), comma-separated (`a,b`), or single value.
        if isinstance(value, str):
            import json

            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @property
    def is_local(self) -> bool:
        return self.app_env is AppEnv.LOCAL


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
