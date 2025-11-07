"""Contract tests for currency_config command."""

from __future__ import annotations

import secrets
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from discord import AppCommandOptionType, Interaction

from src.bot.commands.currency_config import build_currency_config_command
from src.bot.services.currency_config_service import (
    CurrencyConfigResult,
    CurrencyConfigService,
)


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


class _StubResponse:
    def __init__(self) -> None:
        self.sent = False
        self.kwargs: dict[str, Any] | None = None

    async def send_message(self, **kwargs: Any) -> None:
        self.sent = True
        self.kwargs = kwargs


class _StubInteraction:
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        *,
        is_admin: bool = True,
    ) -> None:
        self.guild_id = guild_id
        self.user = SimpleNamespace(
            id=user_id,
            guild_permissions=SimpleNamespace(administrator=is_admin, manage_guild=is_admin),
        )
        self.response = _StubResponse()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_currency_config_command_contract() -> None:
    """Test currency_config command contract (structure and parameters)."""
    guild_id = _snowflake()
    admin_id = _snowflake()

    service = AsyncMock(spec=CurrencyConfigService)
    service.update_currency_config.return_value = CurrencyConfigResult(
        currency_name="金幣",
        currency_icon="🪙",
    )

    command = build_currency_config_command(service)

    # Verify command structure
    assert command.name == "currency_config"
    assert "貨幣" in command.description or "currency" in command.description.lower()
    assert len(command.parameters) == 2

    # Verify parameters
    names = [p.name for p in command.parameters]
    assert "name" in names
    assert "icon" in names

    name_param = next(p for p in command.parameters if p.name == "name")
    icon_param = next(p for p in command.parameters if p.name == "icon")

    assert name_param.type == AppCommandOptionType.string
    assert name_param.required is False
    assert icon_param.type == AppCommandOptionType.string
    assert icon_param.required is False

    # Test command execution
    interaction = _StubInteraction(guild_id=guild_id, user_id=admin_id, is_admin=True)

    await command._callback(cast(Interaction[Any], interaction), "金幣", "🪙")

    # Verify service was called correctly
    service.update_currency_config.assert_awaited_once_with(
        guild_id=guild_id,
        currency_name="金幣",
        currency_icon="🪙",
    )

    # Verify response
    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert interaction.response.kwargs["ephemeral"] is True
    content = interaction.response.kwargs["content"]
    assert "金幣" in content
    assert "🪙" in content
