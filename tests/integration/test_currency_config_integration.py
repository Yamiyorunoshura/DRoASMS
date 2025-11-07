"""Integration tests for currency configuration feature."""

from __future__ import annotations

import secrets
from typing import Any

import pytest

from src.bot.services.currency_config_service import (
    CurrencyConfigResult,
    CurrencyConfigService,
)
from src.db.gateway.economy_configuration import EconomyConfigurationGateway


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_currency_config_defaults_when_not_set(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test that default currency config is returned when not configured."""
    guild_id = _snowflake()

    service = CurrencyConfigService(db_pool)

    config = await service.get_currency_config(guild_id=guild_id, connection=db_connection)

    assert isinstance(config, CurrencyConfigResult)
    assert config.currency_name == CurrencyConfigService.DEFAULT_CURRENCY_NAME
    assert config.currency_icon == CurrencyConfigService.DEFAULT_CURRENCY_ICON


@pytest.mark.integration
@pytest.mark.asyncio
async def test_currency_config_create_and_retrieve(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test creating and retrieving currency configuration."""
    guild_id = _snowflake()
    currency_name = "金幣"
    currency_icon = "🪙"

    service = CurrencyConfigService(db_pool)

    # Create configuration
    result = await service.update_currency_config(
        guild_id=guild_id,
        currency_name=currency_name,
        currency_icon=currency_icon,
        connection=db_connection,
    )

    assert isinstance(result, CurrencyConfigResult)
    assert result.currency_name == currency_name
    assert result.currency_icon == currency_icon

    # Retrieve configuration
    retrieved = await service.get_currency_config(guild_id=guild_id, connection=db_connection)

    assert isinstance(retrieved, CurrencyConfigResult)
    assert retrieved.currency_name == currency_name
    assert retrieved.currency_icon == currency_icon


@pytest.mark.integration
@pytest.mark.asyncio
async def test_currency_config_update_existing(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test updating existing currency configuration."""
    guild_id = _snowflake()

    service = CurrencyConfigService(db_pool)
    gateway = EconomyConfigurationGateway()

    # Create initial configuration
    await gateway.update_currency_config(
        db_connection,
        guild_id=guild_id,
        currency_name="點",
        currency_icon="",
    )

    # Update configuration
    result = await service.update_currency_config(
        guild_id=guild_id,
        currency_name="點數",
        currency_icon="💰",
        connection=db_connection,
    )

    assert result.currency_name == "點數"
    assert result.currency_icon == "💰"

    # Verify update persisted
    retrieved = await service.get_currency_config(guild_id=guild_id, connection=db_connection)
    assert retrieved.currency_name == "點數"
    assert retrieved.currency_icon == "💰"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_currency_config_partial_update(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test partial update of currency configuration (only name or only icon)."""
    guild_id = _snowflake()

    service = CurrencyConfigService(db_pool)

    # Create initial configuration
    await service.update_currency_config(
        guild_id=guild_id,
        currency_name="點",
        currency_icon="💰",
        connection=db_connection,
    )

    # Update only name
    result = await service.update_currency_config(
        guild_id=guild_id,
        currency_name="金幣",
        currency_icon=None,
        connection=db_connection,
    )

    assert result.currency_name == "金幣"
    assert result.currency_icon == "💰"  # Should remain unchanged

    # Update only icon
    result = await service.update_currency_config(
        guild_id=guild_id,
        currency_name=None,
        currency_icon="🪙",
        connection=db_connection,
    )

    assert result.currency_name == "金幣"  # Should remain unchanged
    assert result.currency_icon == "🪙"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_currency_config_multiple_guilds(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test that currency configuration is isolated per guild."""
    guild_id_1 = _snowflake()
    guild_id_2 = _snowflake()

    service = CurrencyConfigService(db_pool)

    # Configure different currencies for different guilds
    await service.update_currency_config(
        guild_id=guild_id_1,
        currency_name="金幣",
        currency_icon="🪙",
        connection=db_connection,
    )

    await service.update_currency_config(
        guild_id=guild_id_2,
        currency_name="點數",
        currency_icon="💰",
        connection=db_connection,
    )

    # Verify each guild has its own configuration
    config_1 = await service.get_currency_config(guild_id=guild_id_1, connection=db_connection)
    config_2 = await service.get_currency_config(guild_id=guild_id_2, connection=db_connection)

    assert config_1.currency_name == "金幣"
    assert config_1.currency_icon == "🪙"
    assert config_2.currency_name == "點數"
    assert config_2.currency_icon == "💰"
