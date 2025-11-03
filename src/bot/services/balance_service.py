"""Balance and history querying service for the Discord economy bot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Sequence, TypeVar
from uuid import UUID

import asyncpg

from src.db.gateway.economy_queries import (
    BalanceRecord,
    EconomyQueryGateway,
    HistoryRecord,
)

T = TypeVar("T")


class BalanceError(RuntimeError):
    """Base error raised for balance-related failures."""


class BalancePermissionError(BalanceError):
    """Raised when a caller attempts to access another member without permission."""


@dataclass(frozen=True, slots=True)
class BalanceSnapshot:
    """Value object describing a member's current balance state."""

    guild_id: int
    member_id: int
    balance: int
    last_modified_at: datetime
    throttled_until: datetime | None

    @property
    def is_throttled(self) -> bool:
        """Return True if the member remains under an active throttle window."""
        if self.throttled_until is None:
            return False
        return self.throttled_until > datetime.now(tz=timezone.utc)


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """Represents a single transaction affecting the requested member."""

    transaction_id: UUID
    guild_id: int
    member_id: int
    initiator_id: int
    target_id: int | None
    amount: int
    direction: str
    reason: str | None
    created_at: datetime
    metadata: dict[str, Any]
    balance_after_initiator: int
    balance_after_target: int | None

    @property
    def is_credit(self) -> bool:
        """True when the member received funds for this transaction."""
        return self.target_id == self.member_id

    @property
    def is_debit(self) -> bool:
        """True when the member spent funds for this transaction."""
        return self.initiator_id == self.member_id and not self.is_credit


@dataclass(frozen=True, slots=True)
class HistoryPage:
    """Paginated slice of transaction history."""

    items: Sequence[HistoryEntry]
    next_cursor: datetime | None


class BalanceService:
    """Provide balance snapshots and transaction history with permission checks."""

    def __init__(
        self,
        pool: asyncpg.Pool,
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
        connection: asyncpg.Connection | None = None,
    ) -> BalanceSnapshot:
        """Return the balance snapshot for the target member (defaults to requester)."""
        target_id = target_member_id or requester_id
        self._assert_permission(requester_id, target_id, can_view_others)

        async def _run(conn: asyncpg.Connection) -> BalanceSnapshot:
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
        connection: asyncpg.Connection | None = None,
    ) -> HistoryPage:
        """Return a paginated set of transactions for the target member."""
        if limit < 1 or limit > 50:
            raise ValueError("History limit must be between 1 and 50.")

        target_id = target_member_id or requester_id
        self._assert_permission(requester_id, target_id, can_view_others)

        async def _run(conn: asyncpg.Connection) -> HistoryPage:
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
                has_more = await conn.fetchval(
                    "SELECT economy.fn_has_more_history($1,$2,$3)",
                    guild_id,
                    target_id,
                    last_created,
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
        if requester_id != target_id and not can_view_others:
            raise BalancePermissionError(
                "You do not have permission to view other members' balances."
            )

    async def _with_connection(
        self,
        connection: asyncpg.Connection | None,
        func: Callable[[asyncpg.Connection], Awaitable[T]],
    ) -> T:
        if connection is not None:
            return await func(connection)

        async with self._pool.acquire() as pooled_connection:
            return await func(pooled_connection)

    def _to_snapshot(self, record: BalanceRecord) -> BalanceSnapshot:
        return BalanceSnapshot(
            guild_id=record.guild_id,
            member_id=record.member_id,
            balance=record.balance,
            last_modified_at=record.last_modified_at,
            throttled_until=record.throttled_until,
        )

    def _to_history_entry(
        self,
        record: HistoryRecord,
        member_id: int,
    ) -> HistoryEntry:
        return HistoryEntry(
            transaction_id=record.transaction_id,
            guild_id=record.guild_id,
            member_id=member_id,
            initiator_id=record.initiator_id,
            target_id=record.target_id,
            amount=record.amount,
            direction=record.direction,
            reason=record.reason,
            created_at=record.created_at,
            metadata=dict(record.metadata or {}),
            balance_after_initiator=record.balance_after_initiator,
            balance_after_target=record.balance_after_target,
        )
