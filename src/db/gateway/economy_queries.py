from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence, cast
from uuid import UUID

from src.cython_ext.economy_query_models import BalanceRecord, HistoryRecord
from src.infra.result import DatabaseError, async_returns_result
from src.infra.types.db import ConnectionProtocol as AsyncPGConnectionProto


def _balance_from_record(record: Mapping[str, Any]) -> BalanceRecord:
    return BalanceRecord(
        int(record["guild_id"]),
        int(record["member_id"]),
        int(record["balance"]),
        cast(datetime, record["last_modified_at"]),
        cast(datetime | None, record["throttled_until"]),
    )


def _history_from_record(record: Mapping[str, Any]) -> HistoryRecord:
    return HistoryRecord(
        cast(UUID, record["transaction_id"]),
        int(record["guild_id"]),
        int(record["initiator_id"]),
        cast(int | None, record["target_id"]),
        int(record["amount"]),
        str(record["direction"]),
        cast(str | None, record["reason"]),
        cast(datetime, record["created_at"]),
        dict(cast(Mapping[str, Any] | None, record.get("metadata")) or {}),
        int(record["balance_after_initiator"]),
        cast(int | None, record["balance_after_target"]),
    )


class EconomyQueryGateway:
    """Gateway wrapper around read-only economy stored functions."""

    def __init__(self, *, schema: str = "economy") -> None:
        self._schema = schema

    @async_returns_result(DatabaseError, exception_map={RuntimeError: DatabaseError})
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
        return _balance_from_record(record)

    @async_returns_result(DatabaseError)
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
        return _balance_from_record(record)

    @async_returns_result(DatabaseError)
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
        return [_history_from_record(record) for record in records]


__all__ = ["BalanceRecord", "EconomyQueryGateway", "HistoryRecord"]
