"""Unit tests for TransferService."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import asyncpg
import pytest
from faker import Faker

from src.bot.services.transfer_service import (
    InsufficientBalanceError,
    TransferError,
    TransferService,
    TransferThrottleError,
    TransferValidationError,
)
from src.cython_ext.economy_transfer_models import (
    TransferProcedureResult,
    TransferResult,
)
from src.cython_ext.pending_transfer_models import PendingTransfer
from src.infra.result import (
    BusinessLogicError,
    DatabaseError,
    Err,
    Ok,
    ValidationError,
)


def _snowflake(faker: Faker) -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return faker.random_int(min=1, max=9223372036854775807)


def _create_transfer_procedure_result(
    *,
    guild_id: int,
    initiator_id: int,
    target_id: int,
    amount: int,
    initiator_balance: int = 10000,
    target_balance: int = 5000,
) -> TransferProcedureResult:
    """Create a mock TransferProcedureResult."""
    return TransferProcedureResult(
        transaction_id=uuid4(),
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        direction="transfer",
        created_at=datetime.now(timezone.utc),
        initiator_balance=initiator_balance,
        target_balance=target_balance,
        throttled_until=None,
        metadata={},
    )


def _create_pending_transfer(
    *,
    transfer_id: UUID,
    guild_id: int,
    initiator_id: int,
    target_id: int,
    amount: int,
    status: str = "pending",
) -> PendingTransfer:
    """Create a mock PendingTransfer."""
    now = datetime.now(timezone.utc)
    return PendingTransfer(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        status=status,
        checks={},
        retry_count=0,
        expires_at=None,
        metadata={},
        created_at=now,
        updated_at=now,
    )


class FakeTxn:
    """Fake transaction context manager for testing."""

    def __init__(self) -> None:
        self.started = False
        self.committed = False
        self.rolled_back = False

    async def start(self) -> None:
        self.started = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeConnection:
    """Fake connection for unit testing."""

    def __init__(self) -> None:
        self._txn: FakeTxn | None = None

    def transaction(self) -> FakeTxn:
        self._txn = FakeTxn()
        return self._txn


class FakeAcquire:
    """Fake acquire context manager."""

    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self._conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class FakePool:
    """Fake pool for unit testing."""

    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self._conn)


# =============================================================================
# Test: transfer_currency sync mode success (Task 1.2)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_sync_mode_success(faker: Faker) -> None:
    """Test successful currency transfer in sync mode."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    mock_procedure_result = _create_transfer_procedure_result(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
    )
    mock_gateway.transfer_currency.return_value = Ok(mock_procedure_result)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    result = await service.transfer_currency(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
    )

    assert isinstance(result, TransferResult)
    assert result.guild_id == guild_id
    assert result.initiator_id == initiator_id
    assert result.target_id == target_id
    assert result.amount == amount
    mock_gateway.transfer_currency.assert_awaited_once()


# =============================================================================
# Test: transfer_currency sync mode with external connection (Task 1.3)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_sync_mode_with_connection(faker: Faker) -> None:
    """Test transfer currency with externally provided connection."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    mock_procedure_result = _create_transfer_procedure_result(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
    )
    mock_gateway.transfer_currency.return_value = Ok(mock_procedure_result)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    # Use external connection directly
    result = await service.transfer_currency(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        connection=fake_conn,  # type: ignore[arg-type]
    )

    assert isinstance(result, TransferResult)
    assert result.amount == amount


# =============================================================================
# Test: transfer_currency with reason and metadata (Task 1.4)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_with_reason_metadata(faker: Faker) -> None:
    """Test transfer currency with reason and metadata."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)
    reason = faker.sentence()
    metadata = {"custom_key": faker.word()}

    mock_gateway = AsyncMock()
    mock_procedure_result = _create_transfer_procedure_result(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
    )
    mock_gateway.transfer_currency.return_value = Ok(mock_procedure_result)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    result = await service.transfer_currency(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        reason=reason,
        metadata=metadata,
    )

    assert isinstance(result, TransferResult)
    # Verify metadata passed to gateway includes reason
    call_kwargs = mock_gateway.transfer_currency.call_args.kwargs
    assert call_kwargs["metadata"]["reason"] == reason
    assert call_kwargs["metadata"]["custom_key"] == metadata["custom_key"]


# =============================================================================
# Test: same initiator and target validation error (Task 1.5)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_same_initiator_target(faker: Faker) -> None:
    """Test validation error when initiator and target are the same."""
    guild_id = _snowflake(faker)
    same_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        event_pool_enabled=False,
    )

    with pytest.raises(TransferValidationError) as exc_info:
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=same_id,
            target_id=same_id,  # Same as initiator
            amount=amount,
        )

    assert "different members" in str(exc_info.value)


# =============================================================================
# Test: invalid amount validation error (Task 1.6)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_invalid_amount_zero(faker: Faker) -> None:
    """Test validation error when amount is zero."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        event_pool_enabled=False,
    )

    with pytest.raises(TransferValidationError) as exc_info:
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=0,
        )

    assert "positive" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_invalid_amount_negative(faker: Faker) -> None:
    """Test validation error when amount is negative."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        event_pool_enabled=False,
    )

    with pytest.raises(TransferValidationError) as exc_info:
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=-100,
        )

    assert "positive" in str(exc_info.value)


# =============================================================================
# Test: insufficient balance error (Task 1.7)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_insufficient_balance(faker: Faker) -> None:
    """Test insufficient balance error from gateway."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    # Create a PostgresError with insufficient balance message
    pg_error = asyncpg.RaiseError("Insufficient balance for transfer")
    pg_error.sqlstate = "P0001"

    db_error = DatabaseError("Database error", cause=pg_error)
    mock_gateway.transfer_currency.return_value = Err(db_error)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    with pytest.raises(InsufficientBalanceError):
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
        )


# =============================================================================
# Test: throttle error (Task 1.8)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_throttle_error(faker: Faker) -> None:
    """Test throttle error from gateway."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    # Create a PostgresError with throttle message
    pg_error = asyncpg.RaiseError("Transfer throttled due to daily limits")
    pg_error.sqlstate = "P0001"

    db_error = DatabaseError("Database error", cause=pg_error)
    mock_gateway.transfer_currency.return_value = Err(db_error)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    with pytest.raises(TransferThrottleError):
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
        )


# =============================================================================
# Test: database error (Task 1.9)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_database_error(faker: Faker) -> None:
    """Test generic database error from gateway."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    db_error = DatabaseError("Connection failed")
    mock_gateway.transfer_currency.return_value = Err(db_error)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    with pytest.raises(TransferError) as exc_info:
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
        )

    assert "Connection failed" in str(exc_info.value)


# =============================================================================
# Test: PostgreSQL error mapping (Task 1.10)
# =============================================================================


@pytest.mark.unit
def test_handle_postgres_error_insufficient_balance() -> None:
    """Test PostgreSQL error mapping for insufficient balance."""
    pg_error = asyncpg.RaiseError("Insufficient balance for transfer")
    pg_error.sqlstate = "P0001"

    result = TransferService._handle_postgres_error(pg_error)

    assert isinstance(result, BusinessLogicError)
    assert result.context.get("error_type") == "insufficient_balance"


@pytest.mark.unit
def test_handle_postgres_error_throttle() -> None:
    """Test PostgreSQL error mapping for throttle."""
    pg_error = asyncpg.RaiseError("Transfer throttled")
    pg_error.sqlstate = "P0001"

    result = TransferService._handle_postgres_error(pg_error)

    assert isinstance(result, BusinessLogicError)
    assert result.context.get("error_type") == "throttle"


@pytest.mark.unit
def test_handle_postgres_error_validation() -> None:
    """Test PostgreSQL error mapping for validation error (sqlstate 22023)."""
    pg_error = asyncpg.RaiseError("Invalid parameter")
    pg_error.sqlstate = "22023"

    result = TransferService._handle_postgres_error(pg_error)

    assert isinstance(result, ValidationError)
    assert result.context.get("error_type") == "validation"


@pytest.mark.unit
def test_handle_postgres_error_unknown() -> None:
    """Test PostgreSQL error mapping for unknown error."""
    pg_error = asyncpg.RaiseError("Some unknown database error")
    pg_error.sqlstate = "99999"

    # Use pytest.raises context to suppress LOGGER.exception call
    # which requires actual exception context
    try:
        raise pg_error
    except asyncpg.RaiseError:
        result = TransferService._handle_postgres_error(pg_error)

    assert isinstance(result, DatabaseError)


# =============================================================================
# Test: event pool mode success (Task 1.11)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_event_pool_mode(faker: Faker) -> None:
    """Test successful pending transfer creation in event pool mode."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)
    expected_transfer_id = uuid4()

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.create_pending_transfer.return_value = expected_transfer_id

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        pending_gateway=mock_pending_gateway,
        event_pool_enabled=True,  # Enable event pool mode
    )

    result = await service.transfer_currency(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
    )

    # In event pool mode, should return UUID
    assert isinstance(result, UUID)
    assert result == expected_transfer_id
    mock_pending_gateway.create_pending_transfer.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_event_pool_with_connection(faker: Faker) -> None:
    """Test event pool mode with externally provided connection."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)
    expected_transfer_id = uuid4()

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.create_pending_transfer.return_value = expected_transfer_id

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        pending_gateway=mock_pending_gateway,
        event_pool_enabled=True,
    )

    result = await service.transfer_currency(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        connection=fake_conn,  # type: ignore[arg-type]
    )

    assert isinstance(result, UUID)
    assert result == expected_transfer_id


# =============================================================================
# Test: event pool mode with custom expires (Task 1.12)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_event_pool_expires(faker: Faker) -> None:
    """Test event pool mode with custom expiration hours."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)
    expires_hours = 48
    expected_transfer_id = uuid4()

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.create_pending_transfer.return_value = expected_transfer_id

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        pending_gateway=mock_pending_gateway,
        event_pool_enabled=True,
        default_expires_hours=24,
    )

    result = await service.transfer_currency(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        expires_hours=expires_hours,  # Custom expiration
    )

    assert isinstance(result, UUID)
    # Verify expires_at was calculated correctly
    call_kwargs = mock_pending_gateway.create_pending_transfer.call_args.kwargs
    assert call_kwargs["expires_at"] is not None
    # The expires_at should be approximately 48 hours from now
    expected_expires = datetime.now(timezone.utc) + timedelta(hours=48)
    actual_expires = call_kwargs["expires_at"]
    # Allow 1 minute tolerance
    assert abs((actual_expires - expected_expires).total_seconds()) < 60


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_event_pool_default_expires(faker: Faker) -> None:
    """Test event pool mode uses default expiration when not specified."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)
    expected_transfer_id = uuid4()

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.create_pending_transfer.return_value = expected_transfer_id

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    default_hours = 72
    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        pending_gateway=mock_pending_gateway,
        event_pool_enabled=True,
        default_expires_hours=default_hours,
    )

    await service.transfer_currency(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        # No expires_hours specified
    )

    # Verify expires_at uses default
    call_kwargs = mock_pending_gateway.create_pending_transfer.call_args.kwargs
    expected_expires = datetime.now(timezone.utc) + timedelta(hours=default_hours)
    actual_expires = call_kwargs["expires_at"]
    assert abs((actual_expires - expected_expires).total_seconds()) < 60


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_event_pool_error(faker: Faker) -> None:
    """Test event pool mode error handling."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.create_pending_transfer.side_effect = RuntimeError(
        "Database connection failed"
    )

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        pending_gateway=mock_pending_gateway,
        event_pool_enabled=True,
    )

    with pytest.raises(TransferError) as exc_info:
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
        )

    assert "pending transfer" in str(exc_info.value).lower()


# =============================================================================
# Test: get_transfer_status (Task 1.13)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_transfer_status_found(faker: Faker) -> None:
    """Test getting transfer status when transfer exists."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)
    transfer_id = uuid4()

    mock_pending = _create_pending_transfer(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        status="pending",
    )

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.get_pending_transfer.return_value = mock_pending

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        pending_gateway=mock_pending_gateway,
    )

    result = await service.get_transfer_status(transfer_id=transfer_id)

    assert result is not None
    assert result.transfer_id == transfer_id
    assert result.status == "pending"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_transfer_status_not_found(faker: Faker) -> None:
    """Test getting transfer status when transfer does not exist."""
    transfer_id = uuid4()

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.get_pending_transfer.return_value = None

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        pending_gateway=mock_pending_gateway,
    )

    result = await service.get_transfer_status(transfer_id=transfer_id)

    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_transfer_status_with_connection(faker: Faker) -> None:
    """Test getting transfer status with externally provided connection."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)
    transfer_id = uuid4()

    mock_pending = _create_pending_transfer(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        status="approved",
    )

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.get_pending_transfer.return_value = mock_pending

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        pending_gateway=mock_pending_gateway,
    )

    result = await service.get_transfer_status(
        transfer_id=transfer_id,
        connection=fake_conn,  # type: ignore[arg-type]
    )

    assert result is not None
    assert result.status == "approved"


# =============================================================================
# Test: _execute_transfer transaction behavior
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_transfer_commits_on_success(faker: Faker) -> None:
    """Test that _execute_transfer commits transaction on success."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    mock_procedure_result = _create_transfer_procedure_result(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
    )
    mock_gateway.transfer_currency.return_value = Ok(mock_procedure_result)

    fake_conn = FakeConnection()

    service = TransferService(
        pool=MagicMock(),  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    result = await service._execute_transfer(
        fake_conn,  # type: ignore[arg-type]
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        metadata={},
    )

    assert result.is_ok()
    assert fake_conn._txn is not None
    assert fake_conn._txn.committed is True
    assert fake_conn._txn.rolled_back is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_transfer_rollbacks_on_error(faker: Faker) -> None:
    """Test that _execute_transfer rollbacks transaction on error."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    db_error = DatabaseError("Transfer failed")
    mock_gateway.transfer_currency.return_value = Err(db_error)

    fake_conn = FakeConnection()

    service = TransferService(
        pool=MagicMock(),  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    result = await service._execute_transfer(
        fake_conn,  # type: ignore[arg-type]
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        metadata={},
    )

    assert result.is_err()
    assert fake_conn._txn is not None
    assert fake_conn._txn.rolled_back is True
    assert fake_conn._txn.committed is False


# =============================================================================
# Test: BusinessLogicError mapping
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_business_logic_error_insufficient(faker: Faker) -> None:
    """Test BusinessLogicError mapping for insufficient balance."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    error = BusinessLogicError(
        message="Insufficient balance",
        context={"error_type": "insufficient_balance"},
    )
    mock_gateway.transfer_currency.return_value = Err(error)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    with pytest.raises(InsufficientBalanceError):
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_business_logic_error_throttle(faker: Faker) -> None:
    """Test BusinessLogicError mapping for throttle."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    error = BusinessLogicError(
        message="Throttled",
        context={"error_type": "throttle"},
    )
    mock_gateway.transfer_currency.return_value = Err(error)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    with pytest.raises(TransferThrottleError):
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_business_logic_error_generic(faker: Faker) -> None:
    """Test BusinessLogicError mapping for generic business error."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    error = BusinessLogicError(
        message="Some business rule violation",
        context={"error_type": "other"},
    )
    mock_gateway.transfer_currency.return_value = Err(error)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    with pytest.raises(TransferError) as exc_info:
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
        )

    assert "business rule" in str(exc_info.value).lower()


# =============================================================================
# Test: ValidationError from gateway
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_validation_error_from_gateway(faker: Faker) -> None:
    """Test ValidationError from gateway is mapped to TransferValidationError."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    error = ValidationError(message="Invalid parameter value")
    mock_gateway.transfer_currency.return_value = Err(error)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    with pytest.raises(TransferValidationError):
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
        )


# =============================================================================
# Test: Edge cases for robustness
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_event_pool_no_expiration(faker: Faker) -> None:
    """Test event pool mode with no expiration (expires_hours=0, default=0)."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)
    expected_transfer_id = uuid4()

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.create_pending_transfer.return_value = expected_transfer_id

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        pending_gateway=mock_pending_gateway,
        event_pool_enabled=True,
        default_expires_hours=0,  # No default expiration
    )

    result = await service.transfer_currency(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        # No expires_hours specified
    )

    assert isinstance(result, UUID)
    # Verify expires_at is None when both are 0
    call_kwargs = mock_pending_gateway.create_pending_transfer.call_args.kwargs
    assert call_kwargs["expires_at"] is None


@pytest.mark.unit
def test_handle_postgres_error_no_args() -> None:
    """Test PostgreSQL error mapping when error has no args."""
    # Create a PostgresError without args
    pg_error = asyncpg.RaiseError()
    pg_error.sqlstate = "99999"

    try:
        raise pg_error
    except asyncpg.RaiseError:
        result = TransferService._handle_postgres_error(pg_error)

    assert isinstance(result, DatabaseError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_error_without_message_attr(faker: Faker) -> None:
    """Test handling of Error object without message attribute."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()

    # Create a custom error without message attribute
    class CustomError(DatabaseError):
        def __init__(self) -> None:
            # Don't call super().__init__, so no message attribute
            pass

        def __str__(self) -> str:
            return "Custom error string representation"

    error = CustomError()
    mock_gateway.transfer_currency.return_value = Err(error)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    with pytest.raises(TransferError) as exc_info:
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
        )

    # Should fall back to str(error)
    assert "Custom error string representation" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_currency_metadata_isolation(faker: Faker) -> None:
    """Test that metadata dict is copied and not modified in place."""
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=1000)
    reason = faker.sentence()

    original_metadata = {"key1": "value1", "key2": "value2"}
    metadata_copy = original_metadata.copy()

    mock_gateway = AsyncMock()
    mock_procedure_result = _create_transfer_procedure_result(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
    )
    mock_gateway.transfer_currency.return_value = Ok(mock_procedure_result)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = TransferService(
        pool=fake_pool,  # type: ignore[arg-type]
        gateway=mock_gateway,
        event_pool_enabled=False,
    )

    await service.transfer_currency(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        reason=reason,
        metadata=original_metadata,
    )

    # Original metadata should not be modified
    assert original_metadata == metadata_copy
    assert "reason" not in original_metadata

    # Gateway should receive metadata with reason added
    call_kwargs = mock_gateway.transfer_currency.call_args.kwargs
    assert call_kwargs["metadata"]["reason"] == reason
    assert call_kwargs["metadata"]["key1"] == "value1"
    assert call_kwargs["metadata"]["key2"] == "value2"
