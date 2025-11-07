"""Service for managing currency configuration."""

from __future__ import annotations

import inspect
from dataclasses import dataclass

import asyncpg
import structlog

from src.db.gateway.economy_configuration import EconomyConfigurationGateway

LOGGER = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CurrencyConfigResult:
    """Result of currency configuration operations."""

    currency_name: str
    currency_icon: str


class CurrencyConfigService:
    """Service for managing currency configuration."""

    DEFAULT_CURRENCY_NAME = "點"
    DEFAULT_CURRENCY_ICON = ""

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        gateway: EconomyConfigurationGateway | None = None,
    ) -> None:
        self._pool = pool
        self._gateway = gateway or EconomyConfigurationGateway()

    async def get_currency_config(
        self,
        *,
        guild_id: int,
        connection: asyncpg.Connection | None = None,
    ) -> CurrencyConfigResult:
        """Get currency configuration for a guild, with defaults if not configured."""
        if connection is None:
            async with self._pool.acquire() as conn:
                return await self._get_config(conn, guild_id=guild_id)
        else:
            return await self._get_config(connection, guild_id=guild_id)

    async def _get_config(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
    ) -> CurrencyConfigResult:
        """Internal method to get configuration.

        Note: tests may inject a non-async mock for the gateway method.
        To be robust, we accept both sync and async results.
        """
        rv = self._gateway.get_currency_config(connection, guild_id=guild_id)
        config = await rv if inspect.isawaitable(rv) else rv
        if config is None:
            # Return defaults if no configuration exists
            return CurrencyConfigResult(
                currency_name=self.DEFAULT_CURRENCY_NAME,
                currency_icon=self.DEFAULT_CURRENCY_ICON,
            )
        return CurrencyConfigResult(
            currency_name=config.currency_name,
            currency_icon=config.currency_icon,
        )

    async def update_currency_config(
        self,
        *,
        guild_id: int,
        currency_name: str | None = None,
        currency_icon: str | None = None,
        connection: asyncpg.Connection | None = None,
    ) -> CurrencyConfigResult:
        """Update currency configuration for a guild."""
        if connection is None:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    return await self._update_config(
                        conn,
                        guild_id=guild_id,
                        currency_name=currency_name,
                        currency_icon=currency_icon,
                    )
        else:
            return await self._update_config(
                connection,
                guild_id=guild_id,
                currency_name=currency_name,
                currency_icon=currency_icon,
            )

    async def _update_config(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        currency_name: str | None = None,
        currency_icon: str | None = None,
    ) -> CurrencyConfigResult:
        """Internal method to update configuration.

        Accept both sync and async gateway implementations/mocks.
        """
        rv = self._gateway.update_currency_config(
            connection,
            guild_id=guild_id,
            currency_name=currency_name,
            currency_icon=currency_icon,
        )
        config = await rv if inspect.isawaitable(rv) else rv
        return CurrencyConfigResult(
            currency_name=config.currency_name,
            currency_icon=config.currency_icon,
        )


__all__ = ["CurrencyConfigService", "CurrencyConfigResult"]
