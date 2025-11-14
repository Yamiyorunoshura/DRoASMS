"""Balance and history querying service for the Discord economy bot."""

from __future__ import annotations

from datetime import datetime
from typing import Awaitable, Callable, TypeVar, cast

from src.cython_ext.economy_balance_models import (
    BalanceSnapshot,
    HistoryEntry,
    HistoryPage,
    ensure_view_permission,
    make_balance_snapshot,
    make_history_entry,
)
from src.db.gateway.economy_queries import (
    BalanceRecord,
    EconomyQueryGateway,
    HistoryRecord,
)
from src.infra.types.db import ConnectionProtocol, PoolProtocol

T = TypeVar("T")


class BalanceError(RuntimeError):
    """Base error raised for balance-related failures."""


class BalancePermissionError(BalanceError):
    """Raised when a caller attempts to access another member without permission."""


class BalanceService:
    """Provide balance snapshots and transaction history with permission checks."""

    def __init__(
        self,
        pool: PoolProtocol,
        *,
        gateway: EconomyQueryGateway | None = None,
    ) -> None:
        self._pool = pool
        self._gateway = gateway or EconomyQueryGateway()

    async def get_balance_snapshot(
        self,
        *,
        guild_id: int,
        requester_id: int,
        target_member_id: int | None = None,
        can_view_others: bool = False,
        connection: ConnectionProtocol | None = None,
    ) -> BalanceSnapshot:
        """Return the balance snapshot for the target member (defaults to requester)."""
        target_id = target_member_id or requester_id
        self._assert_permission(requester_id, target_id, can_view_others)

        async def _run(conn: ConnectionProtocol) -> BalanceSnapshot:
            record = await self._gateway.fetch_balance(
                conn,
                guild_id=guild_id,
                member_id=target_id,
            )
            return self._to_snapshot(record)

        return await self._with_connection(connection, _run)

    async def get_history(
        self,
        *,
        guild_id: int,
        requester_id: int,
        target_member_id: int | None = None,
        can_view_others: bool = False,
        limit: int = 10,
        cursor: datetime | None = None,
        connection: ConnectionProtocol | None = None,
    ) -> HistoryPage:
        """Return a paginated set of transactions for the target member."""
        if limit < 1 or limit > 50:
            raise ValueError("History limit must be between 1 and 50.")

        target_id = target_member_id or requester_id
        self._assert_permission(requester_id, target_id, can_view_others)

        async def _run(conn: ConnectionProtocol) -> HistoryPage:
            records = await self._gateway.fetch_history(
                conn,
                guild_id=guild_id,
                member_id=target_id,
                limit=limit,
                cursor=cursor,
            )
            entries = [self._to_history_entry(record, target_id) for record in records]

            next_cursor_value: datetime | None = None
            if len(entries) == limit and entries:
                last_created = entries[-1].created_at
                # Pylance: 對 asyncpg.fetchval 回傳值進行顯式 cast，避免 Unknown 型別傳染
                has_more = cast(
                    bool | None,
                    await conn.fetchval(
                        "SELECT economy.fn_has_more_history($1,$2,$3)",
                        guild_id,
                        target_id,
                        last_created,
                    ),
                )
                if bool(has_more):
                    next_cursor_value = last_created

            return HistoryPage(items=entries, next_cursor=next_cursor_value)

        return await self._with_connection(connection, _run)

    def _assert_permission(
        self,
        requester_id: int,
        target_id: int,
        can_view_others: bool,
    ) -> None:
        ensure_view_permission(
            requester_id,
            target_id,
            can_view_others,
            BalancePermissionError,
        )

    async def _with_connection(
        self,
        connection: ConnectionProtocol | None,
        func: Callable[[ConnectionProtocol], Awaitable[T]],
    ) -> T:
        if connection is not None:
            return await func(connection)

        async with self._pool.acquire() as pooled_connection:
            return await func(pooled_connection)

    def _to_snapshot(self, record: BalanceRecord) -> BalanceSnapshot:
        return make_balance_snapshot(record)

    def _to_history_entry(
        self,
        record: HistoryRecord,
        member_id: int,
    ) -> HistoryEntry:
        return make_history_entry(record, member_id)
