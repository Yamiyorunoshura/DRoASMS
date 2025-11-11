from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence, cast
from uuid import UUID

from src.infra.types.db import ConnectionProtocol as AsyncPGConnectionProto


@dataclass(frozen=True, slots=True)
class BalanceRecord:
    """Row returned by the fn_get_balance stored function."""

    guild_id: int
    member_id: int
    balance: int
    last_modified_at: datetime
    throttled_until: datetime | None

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "BalanceRecord":
        return cls(
            guild_id=int(record["guild_id"]),
            member_id=int(record["member_id"]),
            balance=int(record["balance"]),
            last_modified_at=cast(datetime, record["last_modified_at"]),
            throttled_until=cast(datetime | None, record["throttled_until"]),
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
    def from_record(cls, record: Mapping[str, Any]) -> "HistoryRecord":
        return cls(
            transaction_id=cast(UUID, record["transaction_id"]),
            guild_id=int(record["guild_id"]),
            initiator_id=int(record["initiator_id"]),
            target_id=cast(int | None, record["target_id"]),
            amount=int(record["amount"]),
            direction=str(record["direction"]),
            reason=cast(str | None, record["reason"]),
            created_at=cast(datetime, record["created_at"]),
            metadata=dict(cast(Mapping[str, Any] | None, record.get("metadata")) or {}),
            balance_after_initiator=int(record["balance_after_initiator"]),
            balance_after_target=cast(int | None, record["balance_after_target"]),
        )


class EconomyQueryGateway:
    """Gateway wrapper around read-only economy stored functions."""

    def __init__(self, *, schema: str = "economy") -> None:
        self._schema = schema

    async def fetch_balance(
        self,
        connection: AsyncPGConnectionProto,
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
        connection: AsyncPGConnectionProto,
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
        connection: AsyncPGConnectionProto,
        *,
        guild_id: int,
        member_id: int,
        limit: int,
        cursor: datetime | None,
    ) -> Sequence[HistoryRecord]:
        sql = f"SELECT * FROM {self._schema}.fn_get_history($1, $2, $3, $4)"
        records = cast(
            list[Mapping[str, Any]], await connection.fetch(sql, guild_id, member_id, limit, cursor)
        )
        return [HistoryRecord.from_record(record) for record in records]


__all__ = ["BalanceRecord", "EconomyQueryGateway", "HistoryRecord"]
