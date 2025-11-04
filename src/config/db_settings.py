from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PoolConfig(BaseSettings):
    """Configuration for the asyncpg connection pool."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(..., alias="DATABASE_URL", min_length=1)
    db_pool_min_size: int = Field(default=1, alias="DB_POOL_MIN_SIZE", ge=1)
    db_pool_max_size: int = Field(default=10, alias="DB_POOL_MAX_SIZE", ge=1)
    db_pool_timeout_seconds: float | None = Field(
        default=None, alias="DB_POOL_TIMEOUT_SECONDS", gt=0
    )

    @property
    def dsn(self) -> str:
        """Database connection string (DSN)."""
        return self.database_url

    @property
    def min_size(self) -> int:
        """Minimum pool size."""
        return self.db_pool_min_size

    @property
    def max_size(self) -> int:
        """Maximum pool size."""
        return self.db_pool_max_size

    @property
    def timeout(self) -> float | None:
        """Connection timeout in seconds."""
        return self.db_pool_timeout_seconds

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate that DATABASE_URL is set and starts with postgresql://."""
        if not v or not v.strip():
            raise ValueError("DATABASE_URL cannot be empty")
        url = v.strip()
        if not url.startswith("postgresql://"):
            raise ValueError(
                "DATABASE_URL must start with postgresql://. "
                "Got a URL starting with a different scheme."
            )
        return url

    def model_post_init(self, __context: Any) -> None:
        """Validate that max_size >= min_size after all fields are set."""
        if self.db_pool_max_size < self.db_pool_min_size:
            raise ValueError("DB_POOL_MAX_SIZE must be greater than or equal to DB_POOL_MIN_SIZE")
