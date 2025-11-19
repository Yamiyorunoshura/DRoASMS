"""Lightweight typing protocols for database pool/connection.

This module exists purely to make Pyright/Pylance happy in strict mode
without depending on third‑party stub packages for `asyncpg`.

Only the small surface area we actually use is described here. Real
objects from `asyncpg` satisfy these protocols at runtime (structural
typing), so there is no runtime dependency.
"""

from __future__ import annotations

from typing import Any, AsyncContextManager, Protocol, Self


class TransactionProtocol(Protocol):
    async def start(self) -> None: ...
    async def rollback(self) -> None: ...
    async def commit(self) -> None: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...  # type: ignore[no-untyped-def]


class ConnectionProtocol(Protocol):
    async def fetchval(
        self,
        query: Any,
        *args: Any,
        column: int = 0,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> Any: ...

    async def fetchrow(
        self, query: Any, *args: Any, timeout: float | None = None  # noqa: ASYNC109
    ) -> Any: ...
    async def fetch(
        self, query: Any, *args: Any, timeout: float | None = None  # noqa: ASYNC109
    ) -> list[Any]: ...

    async def execute(
        self, query: Any, *args: Any, timeout: float | None = None  # noqa: ASYNC109
    ) -> Any: ...

    def transaction(
        self,
        *,
        isolation: Any | None = None,
        readonly: bool = False,
        deferrable: bool = False,
    ) -> TransactionProtocol: ...


class PoolProtocol(Protocol):
    def acquire(
        self, *, timeout: float | None = None
    ) -> AsyncContextManager[ConnectionProtocol]: ...


__all__ = [
    "ConnectionProtocol",
    "PoolProtocol",
    "TransactionProtocol",
]
