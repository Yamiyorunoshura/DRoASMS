"""Unit tests for currency_config command."""

from __future__ import annotations

import secrets
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from discord import Interaction

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
        guild_id: int | None,
        user_id: int,
        *,
        is_admin: bool = False,
    ) -> None:
        self.guild_id = guild_id
        self.user = SimpleNamespace(
            id=user_id,
            guild_permissions=SimpleNamespace(administrator=is_admin, manage_guild=is_admin),
        )
        self.response = _StubResponse()


@pytest.mark.unit
class TestCurrencyConfigCommand:
    """Test cases for currency_config command."""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """Create a mock currency config service."""
        return AsyncMock(spec=CurrencyConfigService)

    @pytest.mark.asyncio
    async def test_currency_config_requires_guild(self, mock_service: AsyncMock) -> None:
        """Test that currency_config command requires guild context."""
        command = build_currency_config_command(mock_service)
        interaction = _StubInteraction(guild_id=None, user_id=_snowflake())  # type: ignore

        await command._callback(cast(Interaction[Any], interaction), None, None)

        assert interaction.response.sent is True
        assert interaction.response.kwargs is not None
        assert "伺服器內" in interaction.response.kwargs.get("content", "")
        mock_service.update_currency_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_currency_config_requires_permission(self, mock_service: AsyncMock) -> None:
        """Test that currency_config command requires admin permission."""
        guild_id = _snowflake()
        command = build_currency_config_command(mock_service)
        interaction = _StubInteraction(guild_id=guild_id, user_id=_snowflake(), is_admin=False)

        await command._callback(cast(Interaction[Any], interaction), "金幣", None)

        assert interaction.response.sent is True
        assert interaction.response.kwargs is not None
        assert "管理員" in interaction.response.kwargs.get("content", "")
        mock_service.update_currency_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_currency_config_validates_name_length(self, mock_service: AsyncMock) -> None:
        """Test that currency_config validates name length."""
        guild_id = _snowflake()
        command = build_currency_config_command(mock_service)
        interaction = _StubInteraction(guild_id=guild_id, user_id=_snowflake(), is_admin=True)

        # Test empty name
        await command._callback(cast(Interaction[Any], interaction), "", None)

        assert interaction.response.sent is True
        assert interaction.response.kwargs is not None
        assert "1-20" in interaction.response.kwargs.get("content", "")
        mock_service.update_currency_config.assert_not_called()

        # Test name too long
        interaction.response.sent = False
        long_name = "a" * 21
        await command._callback(cast(Interaction[Any], interaction), long_name, None)

        assert interaction.response.sent is True
        assert "1-20" in interaction.response.kwargs.get("content", "")
        mock_service.update_currency_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_currency_config_validates_icon_length(self, mock_service: AsyncMock) -> None:
        """Test that currency_config validates icon length."""
        guild_id = _snowflake()
        command = build_currency_config_command(mock_service)
        interaction = _StubInteraction(guild_id=guild_id, user_id=_snowflake(), is_admin=True)

        long_icon = "a" * 11
        await command._callback(cast(Interaction[Any], interaction), None, long_icon)

        assert interaction.response.sent is True
        assert interaction.response.kwargs is not None
        assert "10" in interaction.response.kwargs.get("content", "")
        mock_service.update_currency_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_currency_config_requires_at_least_one_parameter(
        self, mock_service: AsyncMock
    ) -> None:
        """Test that currency_config requires at least one parameter."""
        guild_id = _snowflake()
        command = build_currency_config_command(mock_service)
        interaction = _StubInteraction(guild_id=guild_id, user_id=_snowflake(), is_admin=True)

        await command._callback(cast(Interaction[Any], interaction), None, None)

        assert interaction.response.sent is True
        assert interaction.response.kwargs is not None
        assert "至少提供" in interaction.response.kwargs.get("content", "")
        mock_service.update_currency_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_currency_config_success_update_name(self, mock_service: AsyncMock) -> None:
        """Test successful currency config update with name only."""
        guild_id = _snowflake()
        currency_name = "金幣"

        mock_service.update_currency_config.return_value = CurrencyConfigResult(
            currency_name=currency_name,
            currency_icon="",
        )

        command = build_currency_config_command(mock_service)
        interaction = _StubInteraction(guild_id=guild_id, user_id=_snowflake(), is_admin=True)

        await command._callback(cast(Interaction[Any], interaction), currency_name, None)

        assert interaction.response.sent is True
        assert interaction.response.kwargs is not None
        content = interaction.response.kwargs.get("content", "")
        assert "已更新" in content
        assert currency_name in content
        mock_service.update_currency_config.assert_awaited_once_with(
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=None,
        )

    @pytest.mark.asyncio
    async def test_currency_config_success_update_icon(self, mock_service: AsyncMock) -> None:
        """Test successful currency config update with icon only."""
        guild_id = _snowflake()
        currency_icon = "🪙"

        mock_service.update_currency_config.return_value = CurrencyConfigResult(
            currency_name="點",
            currency_icon=currency_icon,
        )

        command = build_currency_config_command(mock_service)
        interaction = _StubInteraction(guild_id=guild_id, user_id=_snowflake(), is_admin=True)

        await command._callback(cast(Interaction[Any], interaction), None, currency_icon)

        assert interaction.response.sent is True
        assert interaction.response.kwargs is not None
        content = interaction.response.kwargs.get("content", "")
        assert "已更新" in content
        assert currency_icon in content
        mock_service.update_currency_config.assert_awaited_once_with(
            guild_id=guild_id,
            currency_name=None,
            currency_icon=currency_icon,
        )

    @pytest.mark.asyncio
    async def test_currency_config_success_update_both(self, mock_service: AsyncMock) -> None:
        """Test successful currency config update with both name and icon."""
        guild_id = _snowflake()
        currency_name = "金幣"
        currency_icon = "🪙"

        mock_service.update_currency_config.return_value = CurrencyConfigResult(
            currency_name=currency_name,
            currency_icon=currency_icon,
        )

        command = build_currency_config_command(mock_service)
        interaction = _StubInteraction(guild_id=guild_id, user_id=_snowflake(), is_admin=True)

        await command._callback(cast(Interaction[Any], interaction), currency_name, currency_icon)

        assert interaction.response.sent is True
        assert interaction.response.kwargs is not None
        content = interaction.response.kwargs.get("content", "")
        assert "已更新" in content
        assert currency_name in content
        assert currency_icon in content
        mock_service.update_currency_config.assert_awaited_once_with(
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=currency_icon,
        )

    @pytest.mark.asyncio
    async def test_currency_config_handles_exception(self, mock_service: AsyncMock) -> None:
        """Test that currency_config handles exceptions gracefully."""
        guild_id = _snowflake()
        currency_name = "金幣"

        mock_service.update_currency_config.side_effect = Exception("Database error")

        command = build_currency_config_command(mock_service)
        interaction = _StubInteraction(guild_id=guild_id, user_id=_snowflake(), is_admin=True)

        await command._callback(cast(Interaction[Any], interaction), currency_name, None)

        assert interaction.response.sent is True
        assert interaction.response.kwargs is not None
        assert "錯誤" in interaction.response.kwargs.get("content", "")
