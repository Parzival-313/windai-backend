"""Application settings, read from environment variables / `.env`.

pydantic-settings maps each field to an env var of the same name (case-insensitive),
so `database_url` <- DATABASE_URL. Values are validated once at startup: a bad or
missing value stops the app with a clear error instead of failing later.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Runtime
    environment: str = "development"
    log_level: str = "INFO"

    # Infrastructure
    database_url: str = "postgresql+psycopg://aeolus:aeolus@localhost:5433/aeolus"
    redis_url: str = "redis://localhost:6379/0"

    # Auth (used from Step 1). Required now so a misconfigured deployment fails fast.
    jwt_secret: SecretStr = Field(min_length=32)
    access_token_minutes: int = Field(default=30, ge=1, le=24 * 60)
    refresh_token_days: int = Field(default=7, ge=1, le=90)
    admin_email: str | None = None
    admin_password: SecretStr | None = None

    # Browser origins allowed to call the API. Comma-separated in the env file.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Storage directories (inside the container)
    data_dir: Path = Path("/data/raw")
    cache_dir: Path = Path("/data/cache")
    model_dir: Path = Path("/data/models")
    artifact_dir: Path = Path("/data/artifacts")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            value = [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, list) and "*" in value:
            raise ValueError("CORS_ORIGINS must list explicit origins; '*' is not allowed")
        return value

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, value: str) -> str:
        # Accept a plain postgresql:// URL and pin SQLAlchemy to the psycopg 3 driver.
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value


@lru_cache
def get_settings() -> Settings:
    """Settings singleton. Tests can call `get_settings.cache_clear()` after changing env."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
