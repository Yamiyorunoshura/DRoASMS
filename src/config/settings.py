from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DROASMS_", case_sensitive=False)

    license_types: list[str] = Field(default_factory=list)


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    token: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("DISCORD_BOT_TOKEN", "DISCORD_TOKEN"),
    )
    # Raw string from environment; parsed via property for flexibility
    guild_allowlist_raw: str = Field(default="", alias="DISCORD_GUILD_ALLOWLIST")

    @property
    def guild_allowlist(self) -> list[int]:
        s = str(self.guild_allowlist_raw).strip()
        if not s:
            return []
        if s.startswith("[") and s.endswith("]"):
            try:
                items = [p.strip() for p in s[1:-1].split(",") if p.strip()]
                return [int(i) for i in items]
            except Exception:
                # Fall through to comma parsing
                pass
        parts = [p.strip() for p in s.split(",") if p.strip()]
        return [int(p) for p in parts]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
