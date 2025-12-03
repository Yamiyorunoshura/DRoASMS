"""Unit tests for BalanceService."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from faker import Faker

from src.bot.services.balance_service import (
    BalanceError,
    BalancePermissionError,
    BalanceService,
)
from src.cython_ext.economy_balance_models import (
    BalanceSnapshot,
    HistoryEntry,
    HistoryPage,
)
from src.cython_ext.economy_query_models import BalanceRecord, HistoryRecord
from src.db.gateway.economy_queries import EconomyQueryGateway
from src.infra.result import DatabaseError, Err, Ok


def _snowflake(faker: Faker) -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return faker.random_int(min=1, max=9223372036854775807)


def _create_balance_record(
    *,
    guild_id: int,
    member_id: int,
    balance: int = 1000,
    last_modified_at: datetime | None = None,
    throttled_until: datetime | None = None,
) -> BalanceRecord:
    """Create a mock BalanceRecord."""
    return BalanceRecord(
        guild_id=guild_id,
        member_id=member_id,
        balance=balance,
        last_modified_at=last_modified_at or datetime.now(timezone.utc),
        throttled_until=throttled_until,
    )


def _create_history_record(
    *,
    guild_id: int,
    initiator_id: int,
    target_id: int | None = None,
    amount: int = 100,
    direction: str = "adjust",
    created_at: datetime | None = None,
) -> HistoryRecord:
    """Create a mock HistoryRecord."""
    return HistoryRecord(
        transaction_id=uuid4(),
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        direction=direction,
        reason=None,
        created_at=created_at or datetime.now(timezone.utc),
        metadata={},
        balance_after_initiator=1000,
        balance_after_target=500 if target_id else None,
    )


class FakeConnection:
    """Fake connection for testing."""

    def __init__(self, has_more: bool = False) -> None:
        self.has_more = has_more
        self.sql_seen: str | None = None

    async def fetchval(
        self, sql: str, guild_id: int, member_id: int, last_created: datetime
    ) -> bool:
        self.sql_seen = sql
        return self.has_more


class FakeAcquire:
    """Fake acquire context manager."""

    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self._conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class FakePool:
    """Fake pool for testing."""

    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self._conn)


# ============================================================================
# get_balance_snapshot - Legacy Mode (with connection)
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_balance_snapshot_legacy_mode_success(faker: Faker) -> None:
    """Test get_balance_snapshot with explicit connection (legacy mode)."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    balance_record = _create_balance_record(guild_id=guild_id, member_id=member_id, balance=5000)

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_balance.return_value = Ok(balance_record)

    mock_conn = AsyncMock()
    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act
    snapshot = await service.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=member_id,
        target_member_id=member_id,
        can_view_others=False,
        connection=mock_conn,
    )

    # Assert
    assert isinstance(snapshot, BalanceSnapshot)
    assert snapshot.guild_id == guild_id
    assert snapshot.member_id == member_id
    assert snapshot.balance == 5000
    mock_gateway.fetch_balance.assert_called_once_with(
        mock_conn, guild_id=guild_id, member_id=member_id
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_balance_snapshot_legacy_mode_permission_denied(faker: Faker) -> None:
    """Test get_balance_snapshot raises BalancePermissionError when permission denied."""
    guild_id = _snowflake(faker)
    requester_id = _snowflake(faker)
    target_member_id = _snowflake(faker)

    # Arrange
    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_conn = AsyncMock()
    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act & Assert
    with pytest.raises(BalancePermissionError) as exc_info:
        await service.get_balance_snapshot(
            guild_id=guild_id,
            requester_id=requester_id,
            target_member_id=target_member_id,
            can_view_others=False,
            connection=mock_conn,
        )

    assert "permission" in str(exc_info.value).lower()
    mock_gateway.fetch_balance.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_balance_snapshot_legacy_mode_database_error(faker: Faker) -> None:
    """Test get_balance_snapshot raises DatabaseError from gateway."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    db_error = DatabaseError(message="Connection failed", context={})
    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_balance.return_value = Err(db_error)

    mock_conn = AsyncMock()
    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act & Assert
    with pytest.raises(DatabaseError) as exc_info:
        await service.get_balance_snapshot(
            guild_id=guild_id,
            requester_id=member_id,
            target_member_id=member_id,
            can_view_others=False,
            connection=mock_conn,
        )

    assert exc_info.value == db_error


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_balance_snapshot_legacy_mode_with_admin_permission(
    faker: Faker,
) -> None:
    """Test get_balance_snapshot allows admin to view others' balance."""
    guild_id = _snowflake(faker)
    requester_id = _snowflake(faker)
    target_member_id = _snowflake(faker)

    # Arrange
    balance_record = _create_balance_record(
        guild_id=guild_id, member_id=target_member_id, balance=3000
    )

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_balance.return_value = Ok(balance_record)

    mock_conn = AsyncMock()
    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act
    snapshot = await service.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=requester_id,
        target_member_id=target_member_id,
        can_view_others=True,
        connection=mock_conn,
    )

    # Assert
    assert isinstance(snapshot, BalanceSnapshot)
    assert snapshot.member_id == target_member_id
    assert snapshot.balance == 3000


# ============================================================================
# get_balance_snapshot - Result Mode (without connection)
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_balance_snapshot_result_mode_success(faker: Faker) -> None:
    """Test get_balance_snapshot in Result mode returns Ok."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    balance_record = _create_balance_record(guild_id=guild_id, member_id=member_id, balance=7500)

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_balance.return_value = Ok(balance_record)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act
    result = await service.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=member_id,
        target_member_id=member_id,
        can_view_others=False,
    )

    # Assert
    assert isinstance(result, Ok)
    snapshot = result.unwrap()
    assert isinstance(snapshot, BalanceSnapshot)
    assert snapshot.balance == 7500


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_balance_snapshot_result_mode_permission_error(faker: Faker) -> None:
    """Test get_balance_snapshot in Result mode returns Err for permission denied."""
    guild_id = _snowflake(faker)
    requester_id = _snowflake(faker)
    target_member_id = _snowflake(faker)

    # Arrange
    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act
    result = await service.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=requester_id,
        target_member_id=target_member_id,
        can_view_others=False,
    )

    # Assert
    assert isinstance(result, Err)
    error = result.unwrap_err()
    assert isinstance(error, DatabaseError)
    assert "permission" in error.message.lower()
    assert error.context["requester_id"] == requester_id
    assert error.context["target_member_id"] == target_member_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_balance_snapshot_result_mode_database_error(faker: Faker) -> None:
    """Test get_balance_snapshot in Result mode propagates database errors."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    db_error = DatabaseError(message="Query failed", context={})
    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_balance.return_value = Err(db_error)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act
    result = await service.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=member_id,
        target_member_id=member_id,
        can_view_others=False,
    )

    # Assert
    assert isinstance(result, Err)
    error = result.unwrap_err()
    assert error == db_error


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_balance_snapshot_defaults_to_requester_id(faker: Faker) -> None:
    """Test get_balance_snapshot defaults target_member_id to requester_id."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    balance_record = _create_balance_record(guild_id=guild_id, member_id=member_id, balance=2000)

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_balance.return_value = Ok(balance_record)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act - target_member_id is None
    result = await service.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=member_id,
        target_member_id=None,
        can_view_others=False,
    )

    # Assert
    assert isinstance(result, Ok)
    snapshot = result.unwrap()
    assert snapshot.member_id == member_id
    mock_gateway.fetch_balance.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_balance_snapshot_with_throttled_balance(faker: Faker) -> None:
    """Test get_balance_snapshot returns throttled balance correctly."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)
    throttled_until = datetime.now(timezone.utc) + timedelta(hours=1)

    # Arrange
    balance_record = _create_balance_record(
        guild_id=guild_id,
        member_id=member_id,
        balance=500,
        throttled_until=throttled_until,
    )

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_balance.return_value = Ok(balance_record)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act
    result = await service.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=member_id,
        can_view_others=False,
    )

    # Assert
    assert isinstance(result, Ok)
    snapshot = result.unwrap()
    assert snapshot.throttled_until == throttled_until
    assert snapshot.is_throttled is True


# ============================================================================
# get_history - Legacy Mode (with connection)
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_legacy_mode_success(faker: Faker) -> None:
    """Test get_history with explicit connection (legacy mode)."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    now = datetime.now(timezone.utc)
    history_records = [
        _create_history_record(
            guild_id=guild_id,
            initiator_id=member_id,
            amount=100,
            created_at=now - timedelta(minutes=i),
        )
        for i in range(3)
    ]

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_history.return_value = Ok(history_records)

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = False

    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act
    page = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        target_member_id=member_id,
        can_view_others=False,
        limit=3,
        connection=mock_conn,
    )

    # Assert
    assert isinstance(page, HistoryPage)
    assert len(page.items) == 3
    assert all(isinstance(entry, HistoryEntry) for entry in page.items)
    mock_gateway.fetch_history.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_legacy_mode_permission_denied(faker: Faker) -> None:
    """Test get_history raises BalancePermissionError when permission denied."""
    guild_id = _snowflake(faker)
    requester_id = _snowflake(faker)
    target_member_id = _snowflake(faker)

    # Arrange
    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_conn = AsyncMock()
    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act & Assert
    with pytest.raises(BalancePermissionError):
        await service.get_history(
            guild_id=guild_id,
            requester_id=requester_id,
            target_member_id=target_member_id,
            can_view_others=False,
            connection=mock_conn,
        )

    mock_gateway.fetch_history.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_legacy_mode_invalid_limit() -> None:
    """Test get_history raises ValueError for invalid limit."""
    service = BalanceService(AsyncMock())

    # Act & Assert - limit too small
    with pytest.raises(ValueError, match="limit must be between 1 and 50"):
        await service.get_history(
            guild_id=1,
            requester_id=1,
            limit=0,
            connection=AsyncMock(),
        )

    # Act & Assert - limit too large
    with pytest.raises(ValueError, match="limit must be between 1 and 50"):
        await service.get_history(
            guild_id=1,
            requester_id=1,
            limit=51,
            connection=AsyncMock(),
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_legacy_mode_with_cursor(faker: Faker) -> None:
    """Test get_history with cursor for pagination."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)
    cursor = datetime.now(timezone.utc) - timedelta(hours=1)

    # Arrange
    history_records = [
        _create_history_record(
            guild_id=guild_id, initiator_id=member_id, created_at=cursor - timedelta(minutes=i)
        )
        for i in range(2)
    ]

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_history.return_value = Ok(history_records)

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = False

    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act
    page = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        limit=5,
        cursor=cursor,
        connection=mock_conn,
    )

    # Assert
    assert isinstance(page, HistoryPage)
    assert len(page.items) == 2
    mock_gateway.fetch_history.assert_called_once_with(
        mock_conn, guild_id=guild_id, member_id=member_id, limit=5, cursor=cursor
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_legacy_mode_has_more_true(faker: Faker) -> None:
    """Test get_history sets next_cursor when has_more is True."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange - return exactly 3 items (matching limit)
    now = datetime.now(timezone.utc)
    history_records = [
        _create_history_record(
            guild_id=guild_id,
            initiator_id=member_id,
            created_at=now - timedelta(minutes=i),
        )
        for i in range(3)
    ]

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_history.return_value = Ok(history_records)

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = True  # has_more = True

    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act
    page = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        limit=3,
        connection=mock_conn,
    )

    # Assert
    assert isinstance(page, HistoryPage)
    assert page.next_cursor is not None
    assert page.next_cursor == page.items[-1].created_at
    mock_conn.fetchval.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_legacy_mode_has_more_false(faker: Faker) -> None:
    """Test get_history sets next_cursor to None when has_more is False."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    now = datetime.now(timezone.utc)
    history_records = [
        _create_history_record(
            guild_id=guild_id,
            initiator_id=member_id,
            created_at=now - timedelta(minutes=i),
        )
        for i in range(3)
    ]

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_history.return_value = Ok(history_records)

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = False  # has_more = False

    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act
    page = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        limit=3,
        connection=mock_conn,
    )

    # Assert
    assert isinstance(page, HistoryPage)
    assert page.next_cursor is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_legacy_mode_fewer_items_than_limit(faker: Faker) -> None:
    """Test get_history with fewer items than limit doesn't check has_more."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange - return 2 items, limit is 5
    history_records = [
        _create_history_record(guild_id=guild_id, initiator_id=member_id) for _ in range(2)
    ]

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_history.return_value = Ok(history_records)

    mock_conn = AsyncMock()
    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act
    page = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        limit=5,
        connection=mock_conn,
    )

    # Assert
    assert len(page.items) == 2
    assert page.next_cursor is None
    mock_conn.fetchval.assert_not_called()  # Should not check has_more


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_legacy_mode_database_error(faker: Faker) -> None:
    """Test get_history raises DatabaseError from gateway."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    db_error = DatabaseError(message="Query failed", context={})
    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_history.return_value = Err(db_error)

    mock_conn = AsyncMock()
    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act & Assert
    with pytest.raises(DatabaseError) as exc_info:
        await service.get_history(
            guild_id=guild_id,
            requester_id=member_id,
            limit=10,
            connection=mock_conn,
        )

    assert exc_info.value == db_error


# ============================================================================
# get_history - Result Mode (without connection)
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_result_mode_success(faker: Faker) -> None:
    """Test get_history in Result mode returns Ok."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    now = datetime.now(timezone.utc)
    history_records = [
        _create_history_record(
            guild_id=guild_id,
            initiator_id=member_id,
            created_at=now - timedelta(minutes=i),
        )
        for i in range(3)
    ]

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_history.return_value = Ok(history_records)

    fake_conn = FakeConnection(has_more=False)
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act
    result = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        limit=3,
    )

    # Assert
    assert isinstance(result, Ok)
    page = result.unwrap()
    assert isinstance(page, HistoryPage)
    assert len(page.items) == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_result_mode_permission_error(faker: Faker) -> None:
    """Test get_history in Result mode returns Err for permission denied."""
    guild_id = _snowflake(faker)
    requester_id = _snowflake(faker)
    target_member_id = _snowflake(faker)

    # Arrange
    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act
    result = await service.get_history(
        guild_id=guild_id,
        requester_id=requester_id,
        target_member_id=target_member_id,
        can_view_others=False,
        limit=10,
    )

    # Assert
    assert isinstance(result, Err)
    error = result.unwrap_err()
    assert isinstance(error, DatabaseError)
    assert "permission" in error.message.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_result_mode_database_error(faker: Faker) -> None:
    """Test get_history in Result mode propagates database errors."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    db_error = DatabaseError(message="Connection lost", context={})
    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_history.return_value = Err(db_error)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act
    result = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        limit=10,
    )

    # Assert
    assert isinstance(result, Err)
    error = result.unwrap_err()
    assert error == db_error


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_result_mode_with_pagination(faker: Faker) -> None:
    """Test get_history in Result mode handles pagination correctly."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange - exactly 5 items matching limit
    now = datetime.now(timezone.utc)
    history_records = [
        _create_history_record(
            guild_id=guild_id,
            initiator_id=member_id,
            created_at=now - timedelta(minutes=i),
        )
        for i in range(5)
    ]

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_history.return_value = Ok(history_records)

    fake_conn = FakeConnection(has_more=True)
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act
    result = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        limit=5,
    )

    # Assert
    assert isinstance(result, Ok)
    page = result.unwrap()
    assert len(page.items) == 5
    assert page.next_cursor is not None
    assert page.next_cursor == page.items[-1].created_at


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_defaults_to_requester_id(faker: Faker) -> None:
    """Test get_history defaults target_member_id to requester_id."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    history_records = [_create_history_record(guild_id=guild_id, initiator_id=member_id)]

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_history.return_value = Ok(history_records)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act - target_member_id is None
    result = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        target_member_id=None,
        limit=10,
    )

    # Assert
    assert isinstance(result, Ok)
    mock_gateway.fetch_history.assert_called_once()
    call_kwargs = mock_gateway.fetch_history.call_args.kwargs
    assert call_kwargs["member_id"] == member_id


# ============================================================================
# _to_snapshot and _to_history_entry
# ============================================================================


@pytest.mark.unit
def test_to_snapshot_conversion(faker: Faker) -> None:
    """Test _to_snapshot correctly converts BalanceRecord to BalanceSnapshot."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    balance_record = _create_balance_record(guild_id=guild_id, member_id=member_id, balance=12345)
    service = BalanceService(AsyncMock())

    # Act
    snapshot = service._to_snapshot(balance_record)

    # Assert
    assert isinstance(snapshot, BalanceSnapshot)
    assert snapshot.guild_id == guild_id
    assert snapshot.member_id == member_id
    assert snapshot.balance == 12345
    assert snapshot.last_modified_at == balance_record.last_modified_at
    assert snapshot.throttled_until == balance_record.throttled_until


@pytest.mark.unit
def test_to_history_entry_conversion(faker: Faker) -> None:
    """Test _to_history_entry correctly converts HistoryRecord to HistoryEntry."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)

    # Arrange
    history_record = _create_history_record(
        guild_id=guild_id, initiator_id=initiator_id, target_id=target_id, amount=999
    )
    service = BalanceService(AsyncMock())

    # Act
    entry = service._to_history_entry(history_record, initiator_id)

    # Assert
    assert isinstance(entry, HistoryEntry)
    assert entry.guild_id == guild_id
    assert entry.member_id == initiator_id
    assert entry.initiator_id == initiator_id
    assert entry.target_id == target_id
    assert entry.amount == 999
    assert entry.transaction_id == history_record.transaction_id


# ============================================================================
# _assert_permission
# ============================================================================


@pytest.mark.unit
def test_assert_permission_same_user(faker: Faker) -> None:
    """Test _assert_permission allows user to view own data."""
    member_id = _snowflake(faker)
    service = BalanceService(AsyncMock())

    # Act & Assert - should not raise
    service._assert_permission(member_id, member_id, can_view_others=False)


@pytest.mark.unit
def test_assert_permission_admin_can_view_others(faker: Faker) -> None:
    """Test _assert_permission allows admin to view others."""
    requester_id = _snowflake(faker)
    target_id = _snowflake(faker)
    service = BalanceService(AsyncMock())

    # Act & Assert - should not raise
    service._assert_permission(requester_id, target_id, can_view_others=True)


@pytest.mark.unit
def test_assert_permission_non_admin_cannot_view_others(faker: Faker) -> None:
    """Test _assert_permission denies non-admin from viewing others."""
    requester_id = _snowflake(faker)
    target_id = _snowflake(faker)
    service = BalanceService(AsyncMock())

    # Act & Assert
    with pytest.raises(BalancePermissionError):
        service._assert_permission(requester_id, target_id, can_view_others=False)


# ============================================================================
# Connection management
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_with_connection_uses_provided_connection() -> None:
    """Test _with_connection uses provided connection instead of pool."""
    # Arrange
    mock_conn = AsyncMock()
    mock_pool = AsyncMock()
    service = BalanceService(mock_pool)

    async def test_func(conn: Any) -> str:
        return "success"

    # Act
    result = await service._with_connection(mock_conn, test_func)

    # Assert
    assert result == "success"
    mock_pool.acquire.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_with_connection_acquires_from_pool_when_none() -> None:
    """Test _with_connection acquires connection from pool when connection is None."""
    # Arrange
    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool)

    async def test_func(conn: Any) -> str:
        assert conn == fake_conn
        return "pooled"

    # Act
    result = await service._with_connection(None, test_func)

    # Assert
    assert result == "pooled"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_with_connection_result_returns_ok() -> None:
    """Test _with_connection_result handles Ok result."""
    # Arrange
    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool)

    async def test_func(conn: Any) -> Ok[str]:
        return Ok("result")

    # Act
    result = await service._with_connection_result(None, test_func)

    # Assert
    assert isinstance(result, Ok)
    assert result.unwrap() == "result"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_with_connection_result_returns_err() -> None:
    """Test _with_connection_result handles Err result."""
    # Arrange
    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool)

    error = DatabaseError(message="test error", context={})

    async def test_func(conn: Any) -> Err[DatabaseError]:
        return Err(error)

    # Act
    result = await service._with_connection_result(None, test_func)

    # Assert
    assert isinstance(result, Err)
    assert result.unwrap_err() == error


# ============================================================================
# Default gateway
# ============================================================================


@pytest.mark.unit
def test_balance_service_creates_default_gateway() -> None:
    """Test BalanceService creates default gateway when none provided."""
    # Arrange
    mock_pool = AsyncMock()

    # Act
    service = BalanceService(mock_pool)

    # Assert
    assert service._gateway is not None
    assert isinstance(service._gateway, EconomyQueryGateway)


@pytest.mark.unit
def test_balance_service_uses_provided_gateway() -> None:
    """Test BalanceService uses provided gateway."""
    # Arrange
    mock_pool = AsyncMock()
    mock_gateway = AsyncMock(spec=EconomyQueryGateway)

    # Act
    service = BalanceService(mock_pool, gateway=mock_gateway)

    # Assert
    assert service._gateway == mock_gateway


# ============================================================================
# Legacy gateway compatibility (non-Result returns)
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_legacy_gateway_non_result_return(faker: Faker) -> None:
    """Test get_history handles legacy gateway that returns list directly."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange - simulate old gateway that returns list instead of Result
    history_records = [_create_history_record(guild_id=guild_id, initiator_id=member_id)]

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    # Return plain list, not Result
    mock_gateway.fetch_history.return_value = history_records

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = False

    service = BalanceService(AsyncMock(), gateway=mock_gateway)

    # Act
    page = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        limit=10,
        connection=mock_conn,
    )

    # Assert
    assert isinstance(page, HistoryPage)
    assert len(page.items) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_result_mode_legacy_gateway_non_result(faker: Faker) -> None:
    """Test get_history in Result mode handles legacy gateway list return."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange
    history_records = [
        _create_history_record(guild_id=guild_id, initiator_id=member_id) for _ in range(2)
    ]

    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    # Return plain list
    mock_gateway.fetch_history.return_value = history_records

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act
    result = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        limit=10,
    )

    # Assert
    assert isinstance(result, Ok)
    page = result.unwrap()
    assert len(page.items) == 2


# ============================================================================
# Connection management - Awaitable path
# ============================================================================


class AsyncMockAcquire:
    """Async mock that returns context manager after await."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def __await__(self) -> Any:
        async def _awaitable() -> AsyncMockAcquire._CM:
            return AsyncMockAcquire._CM(self._conn)

        return _awaitable().__await__()

    class _CM:
        def __init__(self, conn: Any) -> None:
            self._conn = conn

        async def __aenter__(self) -> Any:
            return self._conn

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass


@pytest.mark.unit
@pytest.mark.asyncio
async def test_with_connection_handles_awaitable_acquire() -> None:
    """Test _with_connection handles pool.acquire() returning awaitable."""
    # Arrange
    mock_conn = MagicMock()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = AsyncMockAcquire(mock_conn)

    service = BalanceService(mock_pool)

    async def test_func(conn: Any) -> str:
        assert conn == mock_conn
        return "awaitable-success"

    # Act
    result = await service._with_connection(None, test_func)

    # Assert
    assert result == "awaitable-success"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_with_connection_result_handles_awaitable_acquire() -> None:
    """Test _with_connection_result handles awaitable acquire."""
    # Arrange
    mock_conn = MagicMock()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = AsyncMockAcquire(mock_conn)

    service = BalanceService(mock_pool)

    async def test_func(conn: Any) -> Ok[str]:
        return Ok("awaitable-result-success")

    # Act
    result = await service._with_connection_result(None, test_func)

    # Assert
    assert isinstance(result, Ok)
    assert result.unwrap() == "awaitable-result-success"


class DirectAwaitableConnection:
    """Awaitable that returns connection directly (no context manager)."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def __await__(self) -> Any:
        async def _awaitable() -> Any:
            return self._conn

        return _awaitable().__await__()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_with_connection_handles_awaitable_direct_conn() -> None:
    """Test _with_connection handles awaitable that returns connection directly."""

    # Arrange
    # Create a simple object without __aenter__ to avoid MagicMock auto-creation
    class SimpleConn:
        pass

    simple_conn = SimpleConn()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = DirectAwaitableConnection(simple_conn)

    service = BalanceService(mock_pool)

    async def test_func(conn: Any) -> str:
        assert isinstance(conn, SimpleConn)
        return "direct-conn-success"

    # Act
    result = await service._with_connection(None, test_func)

    # Assert
    assert result == "direct-conn-success"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_with_connection_result_with_provided_connection() -> None:
    """Test _with_connection_result uses provided connection."""
    # Arrange
    mock_conn = AsyncMock()
    mock_pool = AsyncMock()
    service = BalanceService(mock_pool)

    async def test_func(conn: Any) -> Ok[str]:
        assert conn == mock_conn
        return Ok("provided-conn")

    # Act
    result = await service._with_connection_result(mock_conn, test_func)

    # Assert
    assert isinstance(result, Ok)
    assert result.unwrap() == "provided-conn"
    mock_pool.acquire.assert_not_called()


class DirectConnectionObject:
    """Object that acts as connection directly (no context manager or await)."""

    def __init__(self) -> None:
        self.used = False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_with_connection_handles_direct_connection_object() -> None:
    """Test _with_connection fallback to using acquire result as connection."""
    # Arrange
    direct_conn = DirectConnectionObject()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = direct_conn

    service = BalanceService(mock_pool)

    async def test_func(conn: Any) -> str:
        assert isinstance(conn, DirectConnectionObject)
        conn.used = True
        return "direct-object-success"

    # Act
    result = await service._with_connection(None, test_func)

    # Assert
    assert result == "direct-object-success"
    assert direct_conn.used is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_with_connection_result_handles_direct_connection_object() -> None:
    """Test _with_connection_result fallback to using acquire result as connection."""
    # Arrange
    direct_conn = DirectConnectionObject()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = direct_conn

    service = BalanceService(mock_pool)

    async def test_func(conn: Any) -> Ok[str]:
        assert isinstance(conn, DirectConnectionObject)
        return Ok("direct-result-success")

    # Act
    result = await service._with_connection_result(None, test_func)

    # Assert
    assert isinstance(result, Ok)
    assert result.unwrap() == "direct-result-success"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_empty_results(faker: Faker) -> None:
    """Test get_history with empty results returns empty page."""
    guild_id = _snowflake(faker)
    member_id = _snowflake(faker)

    # Arrange - no history records
    mock_gateway = AsyncMock(spec=EconomyQueryGateway)
    mock_gateway.fetch_history.return_value = Ok([])

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)
    service = BalanceService(fake_pool, gateway=mock_gateway)

    # Act
    result = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        limit=10,
    )

    # Assert
    assert isinstance(result, Ok)
    page = result.unwrap()
    assert len(page.items) == 0
    assert page.next_cursor is None


# ============================================================================
# Error hierarchy
# ============================================================================


@pytest.mark.unit
def test_balance_error_hierarchy() -> None:
    """Test BalanceError exception hierarchy."""
    # Assert
    assert issubclass(BalanceError, RuntimeError)
    assert issubclass(BalancePermissionError, BalanceError)


@pytest.mark.unit
def test_balance_permission_error_message() -> None:
    """Test BalancePermissionError has meaningful message."""
    # Arrange & Act
    error = BalancePermissionError("Access denied")

    # Assert
    assert str(error) == "Access denied"
    assert isinstance(error, BalanceError)
    assert isinstance(error, RuntimeError)
