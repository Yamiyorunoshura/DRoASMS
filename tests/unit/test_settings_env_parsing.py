from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config.settings import BotSettings


@pytest.mark.unit
def test_token_alias_support(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setenv("DISCORD_TOKEN", "test-token-123")
    settings = BotSettings.model_validate({})
    assert settings.token == "test-token-123"


@pytest.mark.unit
def test_allowlist_single_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_GUILD_ALLOWLIST", "1391253095068991598")
    settings = BotSettings.model_validate({})
    assert settings.guild_allowlist == [1391253095068991598]


@pytest.mark.unit
def test_allowlist_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_GUILD_ALLOWLIST", "1, 2 , 3")
    settings = BotSettings.model_validate({})
    assert settings.guild_allowlist == [1, 2, 3]


@pytest.mark.unit
def test_allowlist_json_like(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_GUILD_ALLOWLIST", "[4,5, 6]")
    settings = BotSettings.model_validate({})
    assert settings.guild_allowlist == [4, 5, 6]


@pytest.mark.unit
def test_allowlist_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_GUILD_ALLOWLIST", "")
    settings = BotSettings.model_validate({})
    assert settings.guild_allowlist == []


@pytest.mark.unit
def test_token_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # 強制環境變數為空，確保會在設定解析階段即失敗
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "")
    monkeypatch.setenv("DISCORD_TOKEN", "")

    with pytest.raises(ValidationError):
        BotSettings.model_validate({})
