"""Async context manager for database connection acquisition.

This module provides a unified connection acquisition context manager
that handles both real asyncpg pools and test mocks gracefully.
"""

from __future__ import annotations

import inspect
from types import TracebackType
from typing import Any

import structlog

LOGGER = structlog.get_logger(__name__)


class AcquireConnectionContext:
    """Async context manager wrapper for pool.acquire() results.

    Handles both real asyncpg pool connections and test mocks (AsyncMock)
    by detecting and adapting to different acquisition patterns:

    1. If acquire() returns an async context manager with __aenter__/__aexit__,
       delegates to those methods.
    2. If acquire() returns an awaitable, awaits it and manages release manually.
    3. For test mocks, checks for return_value attributes to extract connections.

    Usage:
        pool = get_pool()
        cm = AcquireConnectionContext(pool, pool.acquire())
        async with cm as conn:
            # Use connection
            await conn.execute(...)
    """

    def __init__(self, pool_obj: Any, acq_obj: Any) -> None:
        """Initialize the connection context.

        Args:
            pool_obj: The database pool instance.
            acq_obj: The result of pool.acquire() call.
        """
        self._pool = pool_obj
        self._acq = acq_obj
        self._conn: Any | None = None

    async def __aenter__(self) -> Any:
        """Enter the async context and acquire a connection.

        Returns:
            The database connection object.
        """
        aenter = getattr(self._acq, "__aenter__", None)
        if aenter is not None:
            try:
                LOGGER.debug(
                    "acquire_cm_aenter",
                    aenter_type=type(aenter).__name__,
                    has_rv=hasattr(aenter, "return_value"),
                )
            except Exception:
                pass
            # Check for mock return_value first (test support)
            rv = getattr(aenter, "return_value", None)
            if rv is not None:
                try:
                    LOGGER.debug(
                        "acquire_cm_aenter_rv",
                        rv_type=type(rv).__name__,
                    )
                except Exception:
                    pass
                self._conn = rv
                return rv
            # Real async context manager
            self._conn = await aenter()
            return self._conn

        # Fallback: acquire() returned an awaitable directly
        conn = self._acq
        if inspect.isawaitable(conn):
            conn = await conn
        self._conn = conn
        return conn

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit the async context and release the connection.

        Args:
            exc_type: Exception type if an exception occurred.
            exc: Exception instance if an exception occurred.
            tb: Traceback if an exception occurred.
        """
        aexit = getattr(self._acq, "__aexit__", None)
        if aexit is not None:
            await aexit(exc_type, exc, tb)
            return None

        # Manual release for non-context-manager acquisition
        if self._conn is not None:
            release = getattr(self._pool, "release", None)
            if release is not None:
                try:
                    if inspect.iscoroutinefunction(release):
                        await release(self._conn)
                    else:
                        release(self._conn)
                except Exception:
                    LOGGER.debug("acquire_cm_release_failed", exc_info=True)
        return None


def acquire_connection(pool: Any) -> AcquireConnectionContext:
    """Convenience function to acquire a connection from a pool.

    Args:
        pool: The database pool instance.

    Returns:
        An async context manager for the connection.

    Usage:
        async with acquire_connection(pool) as conn:
            await conn.execute(...)
    """
    return AcquireConnectionContext(pool, pool.acquire())
