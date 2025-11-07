from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence
from uuid import UUID

import asyncpg


@dataclass(frozen=True, slots=True)
class BalanceRecord:
    """Row returned by the fn_get_balance stored function."""

    guild_id: int
    member_id: int
    balance: int
    last_modified_at: datetime
    throttled_until: datetime | None

    @classmethod
    def from_record(cls, record: asyncpg.Record) -> "BalanceRecord":
        return cls(
            guild_id=record["guild_id"],
            member_id=record["member_id"],
            balance=record["balance"],
            last_modified_at=record["last_modified_at"],
            throttled_until=record["throttled_until"],
        )


@dataclass(frozen=True, slots=True)
class HistoryRecord:
    """Row returned by the fn_get_history stored function."""

    transaction_id: UUID
    guild_id: int
    initiator_id: int
    target_id: int | None
    amount: int
    direction: str
    reason: str | None
    created_at: datetime
    metadata: dict[str, Any]
    balance_after_initiator: int
    balance_after_target: int | None

    @classmethod
    def from_record(cls, record: asyncpg.Record) -> "HistoryRecord":
        return cls(
            transaction_id=record["transaction_id"],
            guild_id=record["guild_id"],
            initiator_id=record["initiator_id"],
            target_id=record["target_id"],
            amount=record["amount"],
            direction=str(record["direction"]),
            reason=record["reason"],
            created_at=record["created_at"],
            metadata=dict(record["metadata"] or {}),
            balance_after_initiator=record["balance_after_initiator"],
            balance_after_target=record["balance_after_target"],
        )


class EconomyQueryGateway:
    """Gateway wrapper around read-only economy stored functions."""

    def __init__(self, *, schema: str = "economy") -> None:
        self._schema = schema

    async def fetch_balance(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        member_id: int,
    ) -> BalanceRecord:
        sql = f"SELECT * FROM {self._schema}.fn_get_balance($1, $2)"
        record = await connection.fetchrow(sql, guild_id, member_id)
        if record is None:
            raise RuntimeError("fn_get_balance returned no result.")
        return BalanceRecord.from_record(record)

    async def fetch_balance_snapshot(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        member_id: int,
    ) -> BalanceRecord | None:
        """Read-only balance query that skips fn_get_balance side effects."""
        sql = f"""
            SELECT
                guild_id,
                member_id,
                current_balance AS balance,
                last_modified_at,
                throttled_until
            FROM {self._schema}.guild_member_balances
            WHERE guild_id = $1 AND member_id = $2
        """
        record = await connection.fetchrow(sql, guild_id, member_id)
        if record is None:
            return None
        return BalanceRecord.from_record(record)

    async def fetch_history(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        member_id: int,
        limit: int,
        cursor: datetime | None,
    ) -> Sequence[HistoryRecord]:
        sql = f"SELECT * FROM {self._schema}.fn_get_history($1, $2, $3, $4)"
        records = await connection.fetch(sql, guild_id, member_id, limit, cursor)
        return [HistoryRecord.from_record(record) for record in records]


__all__ = ["BalanceRecord", "EconomyQueryGateway", "HistoryRecord"]
