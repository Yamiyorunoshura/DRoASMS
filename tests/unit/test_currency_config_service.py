"""Unit tests for Currency Config Service."""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock

import asyncpg
import pytest

from src.bot.services.currency_config_service import (
    CurrencyConfigResult,
    CurrencyConfigService,
)
from src.db.gateway.economy_configuration import (
    CurrencyConfig,
    EconomyConfigurationGateway,
)


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


@pytest.mark.unit
class TestCurrencyConfigService:
    """Test cases for CurrencyConfigService."""

    @pytest.fixture
    def mock_pool(self) -> AsyncMock:
        """Create a mock database pool."""
        return AsyncMock(spec=asyncpg.Pool)

    @pytest.fixture
    def mock_gateway(self) -> AsyncMock:
        """Create a mock gateway."""
        return AsyncMock(spec=EconomyConfigurationGateway)

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def service(self, mock_pool: AsyncMock, mock_gateway: AsyncMock) -> CurrencyConfigService:
        """Create service with mocked dependencies."""
        return CurrencyConfigService(pool=mock_pool, gateway=mock_gateway)

    @pytest.mark.asyncio
    async def test_get_currency_config_with_existing_config(
        self,
        service: CurrencyConfigService,
        mock_pool: AsyncMock,
        mock_connection: AsyncMock,
        mock_gateway: AsyncMock,
    ) -> None:
        """Test getting currency config when config exists."""
        guild_id = _snowflake()
        mock_config = CurrencyConfig(
            guild_id=guild_id,
            currency_name="金幣",
            currency_icon="🪙",
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_gateway.get_currency_config.return_value = mock_config

        result = await service.get_currency_config(guild_id=guild_id)

        assert isinstance(result, CurrencyConfigResult)
        assert result.currency_name == "金幣"
        assert result.currency_icon == "🪙"
        mock_gateway.get_currency_config.assert_called_once_with(mock_connection, guild_id=guild_id)

    @pytest.mark.asyncio
    async def test_get_currency_config_with_defaults(
        self,
        service: CurrencyConfigService,
        mock_pool: AsyncMock,
        mock_connection: AsyncMock,
        mock_gateway: AsyncMock,
    ) -> None:
        """Test getting currency config when no config exists (returns defaults)."""
        guild_id = _snowflake()

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_gateway.get_currency_config.return_value = None

        result = await service.get_currency_config(guild_id=guild_id)

        assert isinstance(result, CurrencyConfigResult)
        assert result.currency_name == CurrencyConfigService.DEFAULT_CURRENCY_NAME
        assert result.currency_icon == CurrencyConfigService.DEFAULT_CURRENCY_ICON

    @pytest.mark.asyncio
    async def test_get_currency_config_with_connection(
        self,
        service: CurrencyConfigService,
        mock_connection: AsyncMock,
        mock_gateway: AsyncMock,
    ) -> None:
        """Test getting currency config with provided connection."""
        guild_id = _snowflake()
        mock_config = CurrencyConfig(
            guild_id=guild_id,
            currency_name="點數",
            currency_icon="💰",
        )

        mock_gateway.get_currency_config.return_value = mock_config

        result = await service.get_currency_config(guild_id=guild_id, connection=mock_connection)

        assert isinstance(result, CurrencyConfigResult)
        assert result.currency_name == "點數"
        assert result.currency_icon == "💰"
        mock_gateway.get_currency_config.assert_called_once_with(mock_connection, guild_id=guild_id)

    @pytest.mark.asyncio
    async def test_update_currency_config_create_new(
        self,
        service: CurrencyConfigService,
        mock_pool: AsyncMock,
        mock_connection: AsyncMock,
        mock_gateway: AsyncMock,
    ) -> None:
        """Test updating currency config (creates new)."""
        guild_id = _snowflake()
        currency_name = "金幣"
        currency_icon = "🪙"

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.transaction.return_value.__aenter__.return_value = mock_connection

        mock_config = CurrencyConfig(
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=currency_icon,
        )
        mock_gateway.update_currency_config.return_value = mock_config

        result = await service.update_currency_config(
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=currency_icon,
        )

        assert isinstance(result, CurrencyConfigResult)
        assert result.currency_name == currency_name
        assert result.currency_icon == currency_icon
        mock_gateway.update_currency_config.assert_called_once_with(
            mock_connection,
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=currency_icon,
        )

    @pytest.mark.asyncio
    async def test_update_currency_config_update_existing(
        self,
        service: CurrencyConfigService,
        mock_pool: AsyncMock,
        mock_connection: AsyncMock,
        mock_gateway: AsyncMock,
    ) -> None:
        """Test updating existing currency config."""
        guild_id = _snowflake()
        currency_name = "點數"

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.transaction.return_value.__aenter__.return_value = mock_connection

        mock_config = CurrencyConfig(
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon="💰",
        )
        mock_gateway.update_currency_config.return_value = mock_config

        result = await service.update_currency_config(
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=None,
        )

        assert isinstance(result, CurrencyConfigResult)
        assert result.currency_name == currency_name
        mock_gateway.update_currency_config.assert_called_once_with(
            mock_connection,
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=None,
        )

    @pytest.mark.asyncio
    async def test_update_currency_config_with_connection(
        self,
        service: CurrencyConfigService,
        mock_connection: AsyncMock,
        mock_gateway: AsyncMock,
    ) -> None:
        """Test updating currency config with provided connection."""
        guild_id = _snowflake()
        currency_name = "金幣"
        currency_icon = "🪙"

        mock_config = CurrencyConfig(
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=currency_icon,
        )
        mock_gateway.update_currency_config.return_value = mock_config

        result = await service.update_currency_config(
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=currency_icon,
            connection=mock_connection,
        )

        assert isinstance(result, CurrencyConfigResult)
        assert result.currency_name == currency_name
        assert result.currency_icon == currency_icon
        # Should not use transaction when connection is provided
        mock_gateway.update_currency_config.assert_called_once_with(
            mock_connection,
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=currency_icon,
        )
