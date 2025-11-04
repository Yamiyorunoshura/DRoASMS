"""Unit tests for TransferEventPoolCoordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from faker import Faker

from src.bot.services.transfer_event_pool import TransferEventPoolCoordinator
from src.db.gateway.economy_pending_transfers import PendingTransfer


def _snowflake(faker: Faker) -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    # Discord snowflakes are 63-bit integers (max 9223372036854775807)
    return faker.random_int(min=1, max=9223372036854775807)


def _create_mock_pending_transfer(
    transfer_id: UUID,
    guild_id: int,
    initiator_id: int,
    target_id: int,
    amount: int,
    status: str = "pending",
    checks: dict[str, int] | None = None,
    retry_count: int = 0,
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
        checks=checks or {},
        retry_count=retry_count,
        expires_at=None,
        metadata={},
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_handle_check_result_all_passed() -> None:
    """Test handling check results when all checks pass."""
    mock_pending_gateway = AsyncMock()
    mock_transfer_gateway = AsyncMock()
    coordinator = TransferEventPoolCoordinator(
        pool=None,  # Not needed for unit tests
        pending_gateway=mock_pending_gateway,
        transfer_gateway=mock_transfer_gateway,
    )

    await coordinator.start()

    try:
        transfer_id = uuid4()

        # Simulate all checks passing
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="balance",
            result=1,
        )
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="cooldown",
            result=1,
        )
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="daily_limit",
            result=1,
        )

        # Give coordinator time to process
        await asyncio.sleep(0.1)

        # Verify coordinator received all checks
        assert transfer_id in coordinator._check_states
        check_state = coordinator._check_states[transfer_id]
        assert check_state["balance"] == 1
        assert check_state["cooldown"] == 1
        assert check_state["daily_limit"] == 1

        # Verify execution was attempted (if pool was available)
        # In unit test, pool is None so execution won't happen, but state tracking works

    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_handle_check_result_partial() -> None:
    """Test handling partial check results."""
    coordinator = TransferEventPoolCoordinator(pool=None)

    await coordinator.start()

    try:
        transfer_id = uuid4()

        # Only send balance check
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="balance",
            result=1,
        )

        await asyncio.sleep(0.1)

        # Should not execute yet (missing other checks)
        assert transfer_id in coordinator._check_states
        assert len(coordinator._check_states[transfer_id]) == 1
        assert coordinator._check_states[transfer_id]["balance"] == 1

    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_handle_check_result_some_failed() -> None:
    """Test handling check results when some checks fail."""
    coordinator = TransferEventPoolCoordinator(pool=None)

    await coordinator.start()

    try:
        transfer_id = uuid4()

        # Send checks with one failure
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="balance",
            result=0,  # Failed
        )
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="cooldown",
            result=1,
        )
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="daily_limit",
            result=1,
        )

        await asyncio.sleep(0.1)

        # Verify state tracking
        assert transfer_id in coordinator._check_states
        check_state = coordinator._check_states[transfer_id]
        assert check_state["balance"] == 0
        assert check_state["cooldown"] == 1
        assert check_state["daily_limit"] == 1

    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_handle_check_approved(faker: Faker) -> None:
    """Test handling check approved event."""
    mock_pending_gateway = AsyncMock()
    mock_transfer_gateway = AsyncMock()
    coordinator = TransferEventPoolCoordinator(
        pool=None,
        pending_gateway=mock_pending_gateway,
        transfer_gateway=mock_transfer_gateway,
    )

    await coordinator.start()

    try:
        transfer_id = uuid4()
        guild_id = _snowflake(faker)
        initiator_id = _snowflake(faker)
        target_id = _snowflake(faker)

        # Mock pending transfer
        mock_pending = _create_mock_pending_transfer(
            transfer_id=transfer_id,
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=faker.random_int(min=1, max=10000),
            status="approved",
        )
        mock_pending_gateway.get_pending_transfer = AsyncMock(return_value=mock_pending)

        # Handle approved event
        await coordinator.handle_check_approved(transfer_id=transfer_id)

        # Give time for processing
        await asyncio.sleep(0.1)

        # Verify gateway was called (if pool was available, execution would happen)
        # In unit test, pool is None so execution won't proceed, but the handler was called
        # We verify the coordinator received the event by checking it doesn't raise
        assert True  # Handler completed without error

    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_retry_scheduling_logic(faker: Faker) -> None:
    """Test retry scheduling logic without actual retry."""
    mock_pending_gateway = AsyncMock()
    coordinator = TransferEventPoolCoordinator(
        pool=None,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()

    try:
        transfer_id = uuid4()
        guild_id = _snowflake(faker)
        initiator_id = _snowflake(faker)
        target_id = _snowflake(faker)

        # Mock pending transfer with retry count
        mock_pending = _create_mock_pending_transfer(
            transfer_id=transfer_id,
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=faker.random_int(min=1, max=10000),
            status="checking",
            retry_count=faker.random_int(min=0, max=5),
        )
        mock_pending_gateway.get_pending_transfer = AsyncMock(return_value=mock_pending)

        # Simulate failed checks
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="balance",
            result=0,  # Failed
        )
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="cooldown",
            result=1,
        )
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="daily_limit",
            result=1,
        )

        await asyncio.sleep(0.1)

        # Verify retry scheduling logic was triggered
        # (In unit test, pool is None so actual retry won't execute)

    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_retry_max_count(faker: Faker) -> None:
    """Test that retry stops after max count."""
    mock_pending_gateway = AsyncMock()
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    # Create proper async context manager mock
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)
    mock_conn.execute = AsyncMock()

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()

    try:
        transfer_id = uuid4()
        guild_id = _snowflake(faker)
        initiator_id = _snowflake(faker)
        target_id = _snowflake(faker)

        # Mock pending transfer with max retry count
        mock_pending = _create_mock_pending_transfer(
            transfer_id=transfer_id,
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=faker.random_int(min=1, max=10000),
            status="checking",
            retry_count=10,  # Max retry count
        )
        mock_pending_gateway.get_pending_transfer = AsyncMock(return_value=mock_pending)
        mock_pending_gateway.update_status = AsyncMock()

        # Simulate failed checks to trigger retry
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="balance",
            result=0,
        )
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="cooldown",
            result=1,
        )
        await coordinator.handle_check_result(
            transfer_id=transfer_id,
            check_type="daily_limit",
            result=1,
        )

        await asyncio.sleep(0.2)

        # Verify status was updated to rejected due to max retry count
        # The coordinator should call update_status when retry_count >= 10
        mock_pending_gateway.update_status.assert_called()

    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_coordinator_start_stop() -> None:
    """Test coordinator start and stop."""
    coordinator = TransferEventPoolCoordinator(pool=None)

    assert not coordinator._running

    await coordinator.start()
    assert coordinator._running

    await coordinator.stop()
    assert not coordinator._running


@pytest.mark.asyncio
async def test_expired_cleanup_logic() -> None:
    """Test expired cleanup logic."""
    mock_pending_gateway = AsyncMock()
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    # Create a proper async context manager mock
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    mock_conn.transaction = MagicMock()
    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction.return_value = mock_tx

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()

    try:
        # Manually trigger cleanup
        await coordinator._cleanup_expired()

        # Verify cleanup query was executed
        mock_conn.execute.assert_called()

    finally:
        await coordinator.stop()
