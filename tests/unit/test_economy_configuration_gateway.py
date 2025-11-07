"""Unit tests for Economy Configuration Gateway."""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock

import asyncpg
import pytest

from src.db.gateway.economy_configuration import (
    CurrencyConfig,
    EconomyConfigurationGateway,
)


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


@pytest.mark.unit
class TestEconomyConfigurationGateway:
    """Test cases for EconomyConfigurationGateway."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def gateway(self) -> EconomyConfigurationGateway:
        """Create gateway instance."""
        return EconomyConfigurationGateway()

    @pytest.mark.asyncio
    async def test_get_currency_config_success(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
    ) -> None:
        """Test successful currency config retrieval."""
        guild_id = _snowflake()
        mock_record = {
            "guild_id": guild_id,
            "currency_name": "金幣",
            "currency_icon": "🪙",
        }
        mock_connection.fetchrow.return_value = mock_record

        config = await gateway.get_currency_config(mock_connection, guild_id=guild_id)

        assert config is not None
        assert isinstance(config, CurrencyConfig)
        assert config.guild_id == guild_id
        assert config.currency_name == "金幣"
        assert config.currency_icon == "🪙"
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_currency_config_not_found(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
    ) -> None:
        """Test currency config retrieval when not found."""
        guild_id = _snowflake()
        mock_connection.fetchrow.return_value = None

        config = await gateway.get_currency_config(mock_connection, guild_id=guild_id)

        assert config is None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_currency_config_create_new(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
    ) -> None:
        """Test creating new currency config."""
        guild_id = _snowflake()
        currency_name = "金幣"
        currency_icon = "🪙"

        # First call returns None (not found)
        # Second call returns the created record
        mock_connection.fetchrow.side_effect = [
            None,  # get_currency_config returns None
            {
                "guild_id": guild_id,
                "currency_name": currency_name,
                "currency_icon": currency_icon,
            },
        ]

        config = await gateway.update_currency_config(
            mock_connection,
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=currency_icon,
        )

        assert config is not None
        assert config.guild_id == guild_id
        assert config.currency_name == currency_name
        assert config.currency_icon == currency_icon
        assert mock_connection.fetchrow.call_count == 2

    @pytest.mark.asyncio
    async def test_update_currency_config_update_existing(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
    ) -> None:
        """Test updating existing currency config."""
        guild_id = _snowflake()
        existing_config = {
            "guild_id": guild_id,
            "currency_name": "點",
            "currency_icon": "",
        }
        new_name = "金幣"
        new_icon = "🪙"

        # First call returns existing config
        # Second call returns updated record
        mock_connection.fetchrow.side_effect = [
            existing_config,  # get_currency_config returns existing
            {
                "guild_id": guild_id,
                "currency_name": new_name,
                "currency_icon": new_icon,
            },
        ]

        config = await gateway.update_currency_config(
            mock_connection,
            guild_id=guild_id,
            currency_name=new_name,
            currency_icon=new_icon,
        )

        assert config is not None
        assert config.guild_id == guild_id
        assert config.currency_name == new_name
        assert config.currency_icon == new_icon
        assert mock_connection.fetchrow.call_count == 2

    @pytest.mark.asyncio
    async def test_update_currency_config_partial_update_name_only(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
    ) -> None:
        """Test updating only currency name."""
        guild_id = _snowflake()
        existing_config = {
            "guild_id": guild_id,
            "currency_name": "點",
            "currency_icon": "💰",
        }
        new_name = "金幣"

        mock_connection.fetchrow.side_effect = [
            existing_config,
            {
                "guild_id": guild_id,
                "currency_name": new_name,
                "currency_icon": "💰",  # Unchanged
            },
        ]

        config = await gateway.update_currency_config(
            mock_connection,
            guild_id=guild_id,
            currency_name=new_name,
            currency_icon=None,
        )

        assert config is not None
        assert config.currency_name == new_name
        assert config.currency_icon == "💰"  # Should remain unchanged

    @pytest.mark.asyncio
    async def test_update_currency_config_partial_update_icon_only(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
    ) -> None:
        """Test updating only currency icon."""
        guild_id = _snowflake()
        existing_config = {
            "guild_id": guild_id,
            "currency_name": "點",
            "currency_icon": "",
        }
        new_icon = "🪙"

        mock_connection.fetchrow.side_effect = [
            existing_config,
            {
                "guild_id": guild_id,
                "currency_name": "點",  # Unchanged
                "currency_icon": new_icon,
            },
        ]

        config = await gateway.update_currency_config(
            mock_connection,
            guild_id=guild_id,
            currency_name=None,
            currency_icon=new_icon,
        )

        assert config is not None
        assert config.currency_name == "點"  # Should remain unchanged
        assert config.currency_icon == new_icon

    @pytest.mark.asyncio
    async def test_update_currency_config_no_changes(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
    ) -> None:
        """Test update with no changes returns existing config."""
        guild_id = _snowflake()
        existing_config = {
            "guild_id": guild_id,
            "currency_name": "點",
            "currency_icon": "",
        }

        mock_connection.fetchrow.return_value = existing_config

        config = await gateway.update_currency_config(
            mock_connection,
            guild_id=guild_id,
            currency_name=None,
            currency_icon=None,
        )

        assert config is not None
        assert config.currency_name == "點"
        assert config.currency_icon == ""
        # Should only call fetchrow once (for get_currency_config)
        assert mock_connection.fetchrow.call_count == 1

    @pytest.mark.asyncio
    async def test_update_currency_config_create_with_defaults(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
    ) -> None:
        """Test creating new config with default values when only one field provided."""
        guild_id = _snowflake()
        currency_name = "金幣"

        mock_connection.fetchrow.side_effect = [
            None,  # get_currency_config returns None
            {
                "guild_id": guild_id,
                "currency_name": currency_name,
                "currency_icon": "",  # Default
            },
        ]

        config = await gateway.update_currency_config(
            mock_connection,
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=None,
        )

        assert config is not None
        assert config.currency_name == currency_name
        assert config.currency_icon == ""  # Default value
