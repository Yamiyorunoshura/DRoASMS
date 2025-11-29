"""Balance and history querying service for the Discord economy bot."""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any, Awaitable, Callable, TypeVar, cast

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
from src.infra.result import DatabaseError, Err, Ok, Result
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
    ) -> BalanceSnapshot | Result[BalanceSnapshot, DatabaseError]:
        """Return the balance snapshot for the target member (defaults to requester).

        Dual-mode 合約：
        - 若明確提供 `connection`，採用舊行為：直接回傳 BalanceSnapshot 或丟出例外
          （例如 BalancePermissionError / DatabaseError）。
        - 若 `connection is None`，則採用 Result 合約，回傳 Result[BalanceSnapshot, DatabaseError]，
          以供 Result 型 service 測試與 DI 容器使用。
        """
        target_id = target_member_id or requester_id

        # --- Domain / legacy mode: explicit connection, raise exceptions,
        #     and return BalanceSnapshot ---
        if connection is not None:
            # 權限不足時直接丟出 BalancePermissionError，符合經濟與整合測試期待。
            self._assert_permission(requester_id, target_id, can_view_others)

            async def _run(conn: ConnectionProtocol) -> BalanceSnapshot:
                result = await self._gateway.fetch_balance(
                    conn,
                    guild_id=guild_id,
                    member_id=target_id,
                )
                if result.is_err():
                    raise result.unwrap_err()
                record = result.unwrap()
                return self._to_snapshot(record)

            return await self._with_connection(connection, _run)

        # --- Result mode: for DI / Result integration tests ---
        try:
            self._assert_permission(requester_id, target_id, can_view_others)
        except BalancePermissionError as exc:
            # 將權限錯誤轉為 DatabaseError，以符合 Result 模式與整合測試期望
            return Err(
                DatabaseError(
                    message=str(exc),
                    context={
                        "original_exception": f"{type(exc).__name__}: {exc}",
                        "requester_id": requester_id,
                        "target_member_id": target_id,
                        "can_view_others": can_view_others,
                    },
                    cause=exc,
                )
            )

        async def _run_result(
            conn: ConnectionProtocol,
        ) -> Result[BalanceSnapshot, DatabaseError]:
            result = await self._gateway.fetch_balance(
                conn,
                guild_id=guild_id,
                member_id=target_id,
            )
            if result.is_err():
                return Err(result.unwrap_err())
            record = result.unwrap()
            return Ok(self._to_snapshot(record))

        return await self._with_connection_result(connection, _run_result)

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
    ) -> HistoryPage | Result[HistoryPage, DatabaseError]:
        """Return a paginated set of transactions for the target member.

        Dual-mode 合約：
        - 明確提供 `connection` 時：直接回傳 HistoryPage 或丟出例外
        - `connection is None` 時：採用 Result 合約，回傳 Result[HistoryPage, DatabaseError]
        """
        if limit < 1 or limit > 50:
            raise ValueError("History limit must be between 1 and 50.")

        target_id = target_member_id or requester_id

        # --- Domain / legacy mode: explicit connection, return HistoryPage or raise ---
        if connection is not None:
            # 權限不足時直接丟出 BalancePermissionError，讓呼叫端（例如 slash 指令或 service 呼叫）
            # 以 user-facing 訊息處理。
            self._assert_permission(requester_id, target_id, can_view_others)

            async def _run(conn: ConnectionProtocol) -> HistoryPage:
                result = await self._gateway.fetch_history(
                    conn,
                    guild_id=guild_id,
                    member_id=target_id,
                    limit=limit,
                    cursor=cursor,
                )

                # 同時支援 Result[Sequence[HistoryRecord], Error] 與舊版直接回傳 list[HistoryRecord]
                if hasattr(result, "is_err") and callable(cast(Any, result).is_err):
                    if result.is_err():
                        raise result.unwrap_err()
                    records = result.unwrap()
                else:
                    records = cast(list[HistoryRecord], result)

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

        # --- Result mode: keep Result[HistoryPage, DatabaseError] contract for tests/commands ---
        try:
            self._assert_permission(requester_id, target_id, can_view_others)
        except BalancePermissionError as exc:
            return Err(
                DatabaseError(
                    message=str(exc),
                    context={
                        "original_exception": f"{type(exc).__name__}: {exc}",
                        "requester_id": requester_id,
                        "target_member_id": target_id,
                        "can_view_others": can_view_others,
                    },
                    cause=exc,
                )
            )

        async def _run_result(conn: ConnectionProtocol) -> Result[HistoryPage, DatabaseError]:
            result = await self._gateway.fetch_history(
                conn,
                guild_id=guild_id,
                member_id=target_id,
                limit=limit,
                cursor=cursor,
            )

            # 同時支援 Result[Sequence[HistoryRecord], Error] 與舊版直接回傳 list[HistoryRecord]
            if hasattr(result, "is_err") and callable(cast(Any, result).is_err):
                if result.is_err():
                    return Err(result.unwrap_err())
                records = result.unwrap()
            else:
                records = cast(list[HistoryRecord], result)

            entries = [self._to_history_entry(record, target_id) for record in records]

            next_cursor_value: datetime | None = None
            if len(entries) == limit and entries:
                last_created = entries[-1].created_at
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

            return Ok(HistoryPage(items=entries, next_cursor=next_cursor_value))

        return await self._with_connection_result(connection, _run_result)

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
        """Yield a connection, handling both pooled and injected connections.

        - 若呼叫端已傳入 `connection`，直接使用該連線（舊行為）。
        - 否則，透過 `self._pool.acquire()` 取得連線。

        為了同時支援：
        - 真實 asyncpg pool：`pool.acquire()` 回傳 async context manager
        - 測試中的 AsyncMock：`pool.acquire()` 先回傳 coroutine，await 之後才得到
          async context manager（其 `__aenter__` 會回傳 mock connection）
        """
        if connection is not None:
            return await func(connection)

        cm_or_conn: Any = self._pool.acquire()

        # 首選：asyncpg / 假 pool，直接回傳 async context manager
        if hasattr(cm_or_conn, "__aenter__"):
            async with cm_or_conn as pooled_connection:
                return await func(pooled_connection)

        # Fallback：若為 coroutine/awaitable（例如 AsyncMock），先 await 再判斷
        if inspect.isawaitable(cm_or_conn):
            awaited = await cm_or_conn
            if hasattr(awaited, "__aenter__"):
                async with awaited as pooled_connection:
                    return await func(pooled_connection)
            # 最後退路：視為已取得的連線物件
            return await func(awaited)

        # 非預期情況：直接將 acquire() 結果當作連線使用（主要給測試假物件用）
        return await func(cm_or_conn)

    async def _with_connection_result(
        self,
        connection: ConnectionProtocol | None,
        func: Callable[[ConnectionProtocol], Awaitable[Result[T, DatabaseError]]],
    ) -> Result[T, DatabaseError]:
        """與 `_with_connection` 類似，但保留 Result 形態以配合 Result 型服務。"""
        if connection is not None:
            return await func(connection)

        cm_or_conn: Any = self._pool.acquire()

        if hasattr(cm_or_conn, "__aenter__"):
            async with cm_or_conn as pooled_connection:
                return await func(pooled_connection)

        if inspect.isawaitable(cm_or_conn):
            awaited = await cm_or_conn
            if hasattr(awaited, "__aenter__"):
                async with awaited as pooled_connection:
                    return await func(pooled_connection)
            return await func(awaited)

        return await func(cm_or_conn)

    def _to_snapshot(self, record: BalanceRecord) -> BalanceSnapshot:
        return make_balance_snapshot(record)

    def _to_history_entry(
        self,
        record: HistoryRecord,
        member_id: int,
    ) -> HistoryEntry:
        return make_history_entry(record, member_id)
