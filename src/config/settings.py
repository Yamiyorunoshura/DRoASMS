from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Configuration values required to bootstrap the Discord bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    discord_token: str = Field(..., alias="DISCORD_TOKEN", min_length=1)
    discord_guild_allowlist: str = Field(default="", alias="DISCORD_GUILD_ALLOWLIST")

    @property
    def token(self) -> str:
        """Discord bot token."""
        return self.discord_token

    @property
    def guild_allowlist(self) -> Sequence[int]:
        """List of allowed guild IDs. Returns empty tuple if not set."""
        if not self.discord_guild_allowlist:
            return ()

        parsed_ids = [
            int(value.strip()) for value in self.discord_guild_allowlist.split(",") if value.strip()
        ]
        # 以保序去重，避免同一 guild 被重複同步造成潛在副作用或額外延遲
        return tuple(dict.fromkeys(parsed_ids))

    @field_validator("discord_token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Validate that token is not empty."""
        if not v or not v.strip():
            raise ValueError("DISCORD_TOKEN cannot be empty")
        return v.strip()
