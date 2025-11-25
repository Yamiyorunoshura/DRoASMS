"""Unit tests for currency_config command."""

from __future__ import annotations

import secrets
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord import Interaction, app_commands

from src.bot.commands.currency_config import (
    build_currency_config_command,
    get_help_data,
    register,
)
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


@pytest.mark.unit
class TestCurrencyConfigHelpData:
    """Test cases for get_help_data function."""

    def test_get_help_data_returns_valid_structure(self) -> None:
        """Test that get_help_data returns valid help data structure."""
        help_data = get_help_data()

        assert "currency_config" in help_data
        data = help_data["currency_config"]
        assert data["name"] == "currency_config"
        assert "description" in data
        assert data["category"] == "economy"
        assert "parameters" in data
        assert len(data["parameters"]) == 2
        assert "permissions" in data
        assert "administrator" in data["permissions"]
        assert "examples" in data
        assert len(data["examples"]) >= 3
        assert "tags" in data


@pytest.mark.unit
class TestCurrencyConfigRegister:
    """Test cases for register function."""

    def test_register_with_container(self) -> None:
        """Test register with dependency container."""
        mock_container = MagicMock()
        mock_service = MagicMock(spec=CurrencyConfigService)
        mock_container.resolve.return_value = mock_service

        mock_client = MagicMock()
        mock_client.http = MagicMock()
        mock_client._connection = MagicMock()
        mock_client._connection._command_tree = None

        tree = app_commands.CommandTree(mock_client)

        register(tree, container=mock_container)

        # Verify container.resolve was called
        mock_container.resolve.assert_called_once_with(CurrencyConfigService)

        # Verify command was added
        commands = tree.get_commands()
        command_names = [cmd.name for cmd in commands]
        assert "currency_config" in command_names

    def test_register_without_container_fallback(self) -> None:
        """Test register without container uses fallback pool."""
        mock_client = MagicMock()
        mock_client.http = MagicMock()
        mock_client._connection = MagicMock()
        mock_client._connection._command_tree = None

        tree = app_commands.CommandTree(mock_client)

        # Mock the pool module - it's imported inside the register function
        with patch("src.db.pool.get_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_get_pool.return_value = mock_pool

            register(tree, container=None)

            # Verify get_pool was called
            mock_get_pool.assert_called_once()

        # Verify command was added
        commands = tree.get_commands()
        command_names = [cmd.name for cmd in commands]
        assert "currency_config" in command_names
