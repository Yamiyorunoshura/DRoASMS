"""Tests for AcquireConnectionContext."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infra.db.connection_context import AcquireConnectionContext, acquire_connection


class TestAcquireConnectionContext:
    """Test suite for AcquireConnectionContext."""

    @pytest.mark.asyncio
    async def test_with_async_context_manager(self) -> None:
        """Test with acquire() returning an async context manager."""
        mock_conn = MagicMock()
        mock_pool = MagicMock()

        # Use a class-based async context manager to avoid mock complexity
        class MockAcquire:
            def __init__(self) -> None:
                self.entered = False
                self.exited = False

            async def __aenter__(self) -> MagicMock:
                self.entered = True
                return mock_conn

            async def __aexit__(
                self,
                exc_type: type[BaseException] | None,
                exc: BaseException | None,
                tb: object,
            ) -> None:
                self.exited = True

        mock_acq = MockAcquire()
        ctx = AcquireConnectionContext(mock_pool, mock_acq)
        async with ctx as conn:
            assert conn is mock_conn

        assert mock_acq.entered
        assert mock_acq.exited

    @pytest.mark.asyncio
    async def test_with_mock_return_value(self) -> None:
        """Test with mock that has return_value attribute on __aenter__."""
        mock_conn = MagicMock()
        mock_acq = MagicMock()
        mock_acq.__aenter__ = MagicMock()
        mock_acq.__aenter__.return_value = mock_conn
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool = MagicMock()

        ctx = AcquireConnectionContext(mock_pool, mock_acq)
        async with ctx as conn:
            assert conn is mock_conn

    @pytest.mark.asyncio
    async def test_with_awaitable(self) -> None:
        """Test with acquire() returning an awaitable directly."""
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.release = MagicMock()

        async def awaitable_acquire() -> MagicMock:
            return mock_conn

        ctx = AcquireConnectionContext(mock_pool, awaitable_acquire())
        async with ctx as conn:
            assert conn is mock_conn

        mock_pool.release.assert_called_once_with(mock_conn)

    @pytest.mark.asyncio
    async def test_with_async_release(self) -> None:
        """Test with async release function."""
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.release = AsyncMock()

        async def awaitable_acquire() -> MagicMock:
            return mock_conn

        ctx = AcquireConnectionContext(mock_pool, awaitable_acquire())
        async with ctx as conn:
            assert conn is mock_conn

        mock_pool.release.assert_awaited_once_with(mock_conn)

    @pytest.mark.asyncio
    async def test_release_failure_is_logged(self) -> None:
        """Test that release failures are handled gracefully."""
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.release = MagicMock(side_effect=RuntimeError("release failed"))

        async def awaitable_acquire() -> MagicMock:
            return mock_conn

        ctx = AcquireConnectionContext(mock_pool, awaitable_acquire())
        # Should not raise
        async with ctx as conn:
            assert conn is mock_conn


class TestAcquireConnectionHelper:
    """Test suite for acquire_connection helper."""

    @pytest.mark.asyncio
    async def test_acquire_connection_helper(self) -> None:
        """Test the acquire_connection convenience function."""
        mock_conn = MagicMock()
        mock_acq = AsyncMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acq)

        async with acquire_connection(mock_pool) as conn:
            assert conn is mock_conn

        mock_pool.acquire.assert_called_once()
