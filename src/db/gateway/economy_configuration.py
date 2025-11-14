"""Gateway for economy configuration operations."""

from __future__ import annotations

from typing import Any, Mapping

from src.cython_ext.economy_configuration_models import CurrencyConfig
from src.infra.types.db import ConnectionProtocol as AsyncPGConnectionProto


def _currency_config_from_record(record: Mapping[str, Any]) -> CurrencyConfig:
    return CurrencyConfig(
        int(record["guild_id"]),
        str(record["currency_name"]),
        str(record["currency_icon"]),
    )


class EconomyConfigurationGateway:
    """Gateway for accessing economy configuration data."""

    def __init__(self, *, schema: str = "economy") -> None:
        self._schema = schema

    async def get_currency_config(
        self,
        connection: AsyncPGConnectionProto,
        *,
        guild_id: int,
    ) -> CurrencyConfig | None:
        """Get currency configuration for a guild."""
        sql = f"""
            SELECT guild_id, currency_name, currency_icon
            FROM {self._schema}.economy_configurations
            WHERE guild_id = $1
        """
        record = await connection.fetchrow(sql, guild_id)
        if record is None:
            return None
        return _currency_config_from_record(record)

    async def update_currency_config(
        self,
        connection: AsyncPGConnectionProto,
        *,
        guild_id: int,
        currency_name: str | None = None,
        currency_icon: str | None = None,
    ) -> CurrencyConfig:
        """Update currency configuration for a guild.

        If currency_name or currency_icon is None, that field will not be updated.
        Creates a new record if one doesn't exist.
        """
        # First, check if record exists
        existing = await self.get_currency_config(connection, guild_id=guild_id)

        if existing is None:
            # Create new record with defaults
            sql = f"""
                INSERT INTO {self._schema}.economy_configurations
                    (guild_id, currency_name, currency_icon, admin_role_ids, created_at, updated_at)
                VALUES ($1, $2, $3, '[]'::jsonb, timezone('utc', now()), timezone('utc', now()))
                RETURNING guild_id, currency_name, currency_icon
            """
            name = currency_name if currency_name is not None else "點"
            icon = currency_icon if currency_icon is not None else ""
            record = await connection.fetchrow(sql, guild_id, name, icon)
        else:
            # Update existing record
            updates: list[str] = []
            params: list[str | int] = []
            param_idx = 1

            if currency_name is not None:
                updates.append(f"currency_name = ${param_idx}")
                params.append(currency_name)
                param_idx += 1

            if currency_icon is not None:
                updates.append(f"currency_icon = ${param_idx}")
                params.append(currency_icon)
                param_idx += 1

            if not updates:
                # No changes, return existing
                return existing

            updates.append("updated_at = timezone('utc', clock_timestamp())")
            params.append(guild_id)

            sql = f"""
                UPDATE {self._schema}.economy_configurations
                SET {', '.join(updates)}
                WHERE guild_id = ${param_idx}
                RETURNING guild_id, currency_name, currency_icon
            """
            record = await connection.fetchrow(sql, *params)

        if record is None:
            raise RuntimeError("Failed to update currency configuration.")
        return _currency_config_from_record(record)


__all__ = ["CurrencyConfig", "EconomyConfigurationGateway"]
