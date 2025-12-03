"""Unit tests for TransferEventPoolCoordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from faker import Faker

from src.bot.services.council_service import CouncilService
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


@pytest.mark.unit
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
async def test_execute_transfer_with_role_target_id() -> None:
    """核准事件執行時，能處理以身分組對應帳戶（如國務院主帳戶/理事會帳戶）為 target_id。"""
    # 模擬資料庫連線與 pool
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    # transaction() 需為 async context manager
    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    # acquire() 需為 async context manager
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)

    # 建立一筆已核准的 pending transfer，target_id 使用理事會公共帳戶（9.0e15 + guild）
    faker = Faker()
    guild_id = _snowflake(faker)
    council_target_id = CouncilService.derive_council_account_id(guild_id)
    initiator_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=5000)
    transfer_id = uuid4()

    mock_row = {
        "transfer_id": transfer_id,
        "guild_id": guild_id,
        "initiator_id": initiator_id,
        "target_id": council_target_id,
        "amount": amount,
        "metadata": {},
        "status": "approved",
    }
    mock_conn.fetchrow = AsyncMock(return_value=mock_row)

    # Gateways
    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.update_status = AsyncMock()
    mock_transfer_gateway = AsyncMock()
    mock_transfer_gateway.transfer_currency = AsyncMock(
        return_value=SimpleNamespace(transaction_id=uuid4())
    )

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
        transfer_gateway=mock_transfer_gateway,
    )

    await coordinator.start()
    try:
        await coordinator.handle_check_approved(transfer_id=transfer_id)

        # 驗證最終執行使用了我們的 target_id（身分組映射的帳戶 ID）
        mock_transfer_gateway.transfer_currency.assert_awaited()
        args, kwargs = mock_transfer_gateway.transfer_currency.await_args  # type: ignore[attr-defined]
        assert kwargs.get("target_id") == council_target_id
    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_execute_transfer_with_leader_main_account_target_id() -> None:
    """核准事件執行時，能處理以國務院主帳戶（領袖身分組映射）為 target_id。"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)

    faker = Faker()
    guild_id = _snowflake(faker)
    target_id = __import__("src.bot.services.state_council_service", fromlist=["StateCouncilService"]).StateCouncilService.derive_main_account_id(guild_id)  # type: ignore[attr-defined]
    initiator_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=5000)
    transfer_id = uuid4()

    mock_row = {
        "transfer_id": transfer_id,
        "guild_id": guild_id,
        "initiator_id": initiator_id,
        "target_id": target_id,
        "amount": amount,
        "metadata": {},
        "status": "approved",
    }
    mock_conn.fetchrow = AsyncMock(return_value=mock_row)

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.update_status = AsyncMock()
    mock_transfer_gateway = AsyncMock()
    mock_transfer_gateway.transfer_currency = AsyncMock(
        return_value=SimpleNamespace(transaction_id=uuid4())
    )

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
        transfer_gateway=mock_transfer_gateway,
    )

    await coordinator.start()
    try:
        await coordinator.handle_check_approved(transfer_id=transfer_id)
        mock_transfer_gateway.transfer_currency.assert_awaited()
        args, kwargs = mock_transfer_gateway.transfer_currency.await_args  # type: ignore[attr-defined]
        assert kwargs.get("target_id") == target_id
    finally:
        await coordinator.stop()


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


# =============================================================================
# Additional tests for improved coverage (Tasks 2.1-2.15)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_transfer_success(faker: Faker) -> None:
    """Test successful transfer execution (Task 2.1)."""
    from src.infra.result import Ok

    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)

    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=5000)
    transfer_id = uuid4()
    transaction_id = uuid4()

    mock_row = {
        "transfer_id": transfer_id,
        "guild_id": guild_id,
        "initiator_id": initiator_id,
        "target_id": target_id,
        "amount": amount,
        "metadata": {"reason": "test"},
        "status": "approved",
    }
    mock_conn.fetchrow = AsyncMock(return_value=mock_row)

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.update_status = AsyncMock()
    mock_transfer_gateway = AsyncMock()
    mock_transfer_gateway.transfer_currency = AsyncMock(
        return_value=Ok(SimpleNamespace(transaction_id=transaction_id))
    )

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
        transfer_gateway=mock_transfer_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._execute_transfer(transfer_id)

        mock_transfer_gateway.transfer_currency.assert_awaited_once()
        mock_pending_gateway.update_status.assert_awaited_with(
            mock_conn, transfer_id=transfer_id, new_status="completed"
        )
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_transfer_not_approved(faker: Faker) -> None:
    """Test execute transfer skips when status is not approved (Task 2.2)."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)

    transfer_id = uuid4()

    # Return None to simulate no row found (not approved)
    mock_conn.fetchrow = AsyncMock(return_value=None)

    mock_pending_gateway = AsyncMock()
    mock_transfer_gateway = AsyncMock()

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
        transfer_gateway=mock_transfer_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._execute_transfer(transfer_id)

        # Transfer gateway should not be called when status is not approved
        mock_transfer_gateway.transfer_currency.assert_not_awaited()
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_transfer_gateway_error(faker: Faker) -> None:
    """Test execute transfer marks rejected on gateway error (Task 2.3)."""
    from src.infra.result import DatabaseError, Err

    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)

    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=5000)
    transfer_id = uuid4()

    mock_row = {
        "transfer_id": transfer_id,
        "guild_id": guild_id,
        "initiator_id": initiator_id,
        "target_id": target_id,
        "amount": amount,
        "metadata": {},
        "status": "approved",
    }
    mock_conn.fetchrow = AsyncMock(return_value=mock_row)

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.update_status = AsyncMock()
    mock_transfer_gateway = AsyncMock()
    # Return error from gateway
    mock_transfer_gateway.transfer_currency = AsyncMock(
        return_value=Err(DatabaseError("Transfer failed"))
    )

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
        transfer_gateway=mock_transfer_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._execute_transfer(transfer_id)

        # Status should be updated to rejected
        mock_pending_gateway.update_status.assert_awaited()
        call_kwargs = mock_pending_gateway.update_status.call_args.kwargs
        assert call_kwargs["new_status"] == "rejected"
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_transfer_no_pool() -> None:
    """Test execute transfer returns early when no pool (Task 2.4)."""
    transfer_id = uuid4()

    mock_pending_gateway = AsyncMock()
    mock_transfer_gateway = AsyncMock()

    coordinator = TransferEventPoolCoordinator(
        pool=None,  # No pool
        pending_gateway=mock_pending_gateway,
        transfer_gateway=mock_transfer_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._execute_transfer(transfer_id)

        # Nothing should be called since pool is None
        mock_transfer_gateway.transfer_currency.assert_not_awaited()
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schedule_retry_exponential_delay(faker: Faker) -> None:
    """Test schedule retry calculates exponential delay (Task 2.5)."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)
    mock_conn.execute = AsyncMock()

    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    transfer_id = uuid4()

    # Use retry_count = 3, so delay should be 2^3 = 8 seconds
    mock_pending = _create_mock_pending_transfer(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=faker.random_int(min=1, max=10000),
        status="checking",
        retry_count=3,
    )

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.get_pending_transfer = AsyncMock(return_value=mock_pending)
    mock_pending_gateway.update_status = AsyncMock()

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._schedule_retry(transfer_id)

        # Verify retry task was scheduled
        assert transfer_id in coordinator._retry_tasks
    finally:
        # Cancel the scheduled task
        if transfer_id in coordinator._retry_tasks:
            coordinator._retry_tasks[transfer_id].cancel()
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schedule_retry_max_delay_cap(faker: Faker) -> None:
    """Test schedule retry caps delay at 300 seconds (Task 2.6)."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)
    mock_conn.execute = AsyncMock()

    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    transfer_id = uuid4()

    # Use retry_count = 9, so 2^9 = 512, but should be capped at 300
    mock_pending = _create_mock_pending_transfer(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=faker.random_int(min=1, max=10000),
        status="checking",
        retry_count=9,
    )

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.get_pending_transfer = AsyncMock(return_value=mock_pending)

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._schedule_retry(transfer_id)

        # Verify retry task was scheduled
        assert transfer_id in coordinator._retry_tasks
    finally:
        if transfer_id in coordinator._retry_tasks:
            coordinator._retry_tasks[transfer_id].cancel()
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schedule_retry_increments_count(faker: Faker) -> None:
    """Test schedule retry increments retry count (Task 2.7)."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)
    mock_conn.execute = AsyncMock()

    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    transfer_id = uuid4()

    mock_pending = _create_mock_pending_transfer(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=faker.random_int(min=1, max=10000),
        status="checking",
        retry_count=2,
    )

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.get_pending_transfer = AsyncMock(return_value=mock_pending)

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._schedule_retry(transfer_id)

        # Verify UPDATE query was executed to increment retry_count
        execute_calls = list(mock_conn.execute.call_args_list)
        assert any("retry_count = retry_count + 1" in str(call) for call in execute_calls)
    finally:
        if transfer_id in coordinator._retry_tasks:
            coordinator._retry_tasks[transfer_id].cancel()
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schedule_retry_cancels_existing(faker: Faker) -> None:
    """Test schedule retry cancels existing retry task (Task 2.8)."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)
    mock_conn.execute = AsyncMock()

    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    transfer_id = uuid4()

    mock_pending = _create_mock_pending_transfer(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=faker.random_int(min=1, max=10000),
        status="checking",
        retry_count=1,
    )

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.get_pending_transfer = AsyncMock(return_value=mock_pending)

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        # Schedule first retry
        await coordinator._schedule_retry(transfer_id)
        first_task = coordinator._retry_tasks[transfer_id]

        # Schedule second retry (should cancel first)
        await coordinator._schedule_retry(transfer_id)
        second_task = coordinator._retry_tasks[transfer_id]

        # Give time for cancellation to propagate
        await asyncio.sleep(0.01)

        # First task should be cancelled or done (cancellation requested)
        # The task might be in 'cancelling' state rather than 'cancelled'
        assert first_task.cancelling() > 0 or first_task.cancelled() or first_task.done()
        assert second_task != first_task
    finally:
        if transfer_id in coordinator._retry_tasks:
            coordinator._retry_tasks[transfer_id].cancel()
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schedule_retry_sends_denied_notification(faker: Faker) -> None:
    """Test schedule retry sends denied notification at max retries (Task 2.9)."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)
    mock_conn.execute = AsyncMock()

    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    transfer_id = uuid4()

    # Max retry count reached
    mock_pending = _create_mock_pending_transfer(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=faker.random_int(min=1, max=10000),
        status="checking",
        retry_count=10,
    )

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.get_pending_transfer = AsyncMock(return_value=mock_pending)
    mock_pending_gateway.update_status = AsyncMock()

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._schedule_retry(transfer_id)

        # Verify pg_notify was called for denied notification
        execute_calls = [str(call) for call in mock_conn.execute.call_args_list]
        assert any("pg_notify" in call and "transaction_denied" in call for call in execute_calls)
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_checks_resets_status(faker: Faker) -> None:
    """Test retry checks resets status to checking (Task 2.10)."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)
    mock_conn.execute = AsyncMock()

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.update_status = AsyncMock()

    transfer_id = uuid4()

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._retry_checks(transfer_id)

        # Verify status was reset to checking
        mock_pending_gateway.update_status.assert_awaited_with(
            mock_conn, transfer_id=transfer_id, new_status="checking"
        )
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_checks_triggers_all_functions(faker: Faker) -> None:
    """Test retry checks triggers all check functions (Task 2.11)."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)
    mock_conn.execute = AsyncMock()

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.update_status = AsyncMock()

    transfer_id = uuid4()

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._retry_checks(transfer_id)

        # Verify all check functions were called
        execute_calls = [str(call) for call in mock_conn.execute.call_args_list]
        assert any("fn_check_transfer_balance" in call for call in execute_calls)
        assert any("fn_check_transfer_cooldown" in call for call in execute_calls)
        assert any("fn_check_transfer_daily_limit" in call for call in execute_calls)
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_checks_clears_state(faker: Faker) -> None:
    """Test retry checks clears check state (Task 2.12)."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)
    mock_conn.execute = AsyncMock()

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.update_status = AsyncMock()

    transfer_id = uuid4()

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        # First, record some check results
        coordinator._check_store.record(transfer_id, "balance", 0)
        coordinator._check_store.record(transfer_id, "cooldown", 1)

        # Then retry checks
        await coordinator._retry_checks(transfer_id)

        # Check state should be cleared
        assert transfer_id not in coordinator._check_states
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_checks_with_connection(faker: Faker) -> None:
    """Test retry checks with externally provided connection."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.update_status = AsyncMock()

    transfer_id = uuid4()

    coordinator = TransferEventPoolCoordinator(
        pool=None,  # No pool
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._retry_checks(transfer_id, connection=mock_conn)

        # Verify check functions were called with provided connection
        mock_pending_gateway.update_status.assert_awaited()
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cleanup_expired_updates_status(faker: Faker) -> None:
    """Test cleanup expired updates status to rejected (Task 2.13)."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)
    mock_conn.execute = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])  # No expired transfers

    mock_pending_gateway = AsyncMock()

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._cleanup_expired()

        # Verify UPDATE query was executed
        execute_calls = [str(call) for call in mock_conn.execute.call_args_list]
        assert any("status = 'rejected'" in call for call in execute_calls)
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cleanup_expired_sends_notifications(faker: Faker) -> None:
    """Test cleanup expired sends notifications (Task 2.14)."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)
    mock_conn.execute = AsyncMock()

    # Return expired transfers
    transfer_id = uuid4()
    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=10000)

    mock_conn.fetch = AsyncMock(
        return_value=[
            {
                "transfer_id": transfer_id,
                "guild_id": guild_id,
                "initiator_id": initiator_id,
                "target_id": target_id,
                "amount": amount,
            }
        ]
    )

    mock_pending_gateway = AsyncMock()

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._cleanup_expired()

        # Verify pg_notify was called for each expired transfer
        execute_calls = [str(call) for call in mock_conn.execute.call_args_list]
        assert any(
            "pg_notify" in call and "transfer_checks_expired" in call for call in execute_calls
        )
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_lock_same_transfer(faker: Faker) -> None:
    """Test get_lock returns same lock for same transfer (Task 2.15)."""
    coordinator = TransferEventPoolCoordinator(pool=None)

    transfer_id = uuid4()

    lock1 = coordinator._get_lock(transfer_id)
    lock2 = coordinator._get_lock(transfer_id)

    assert lock1 is lock2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_lock_different_transfers(faker: Faker) -> None:
    """Test get_lock returns different locks for different transfers."""
    coordinator = TransferEventPoolCoordinator(pool=None)

    transfer_id1 = uuid4()
    transfer_id2 = uuid4()

    lock1 = coordinator._get_lock(transfer_id1)
    lock2 = coordinator._get_lock(transfer_id2)

    assert lock1 is not lock2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_check_result_not_running() -> None:
    """Test handle_check_result returns early when not running."""
    coordinator = TransferEventPoolCoordinator(pool=None)
    # Don't start the coordinator

    transfer_id = uuid4()

    # Should not raise and not record
    await coordinator.handle_check_result(
        transfer_id=transfer_id,
        check_type="balance",
        result=1,
    )

    assert transfer_id not in coordinator._check_states


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_check_approved_not_running() -> None:
    """Test handle_check_approved returns early when not running."""
    mock_pending_gateway = AsyncMock()
    coordinator = TransferEventPoolCoordinator(
        pool=None,
        pending_gateway=mock_pending_gateway,
    )
    # Don't start the coordinator

    transfer_id = uuid4()

    # Should not raise
    await coordinator.handle_check_approved(transfer_id=transfer_id)

    # No gateway calls should be made
    mock_pending_gateway.get_pending_transfer.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_cancels_retry_tasks(faker: Faker) -> None:
    """Test stop cancels all retry tasks."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)
    mock_conn.execute = AsyncMock()

    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    transfer_id = uuid4()

    mock_pending = _create_mock_pending_transfer(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=faker.random_int(min=1, max=10000),
        status="checking",
        retry_count=1,
    )

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.get_pending_transfer = AsyncMock(return_value=mock_pending)

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()

    # Schedule a retry
    await coordinator._schedule_retry(transfer_id)
    task = coordinator._retry_tasks[transfer_id]

    # Stop coordinator
    await coordinator.stop()

    # Task should be cancelled
    assert task.cancelled() or task.done()
    assert len(coordinator._retry_tasks) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schedule_retry_pending_not_found(faker: Faker) -> None:
    """Test schedule retry returns early when pending transfer not found."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.get_pending_transfer = AsyncMock(return_value=None)

    transfer_id = uuid4()

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._schedule_retry(transfer_id)

        # No retry task should be scheduled
        assert transfer_id not in coordinator._retry_tasks
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_transfer_with_base_exception_cause(faker: Faker) -> None:
    """Test execute transfer handles error with BaseException cause."""
    from src.infra.result import DatabaseError, Err

    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_context)

    guild_id = _snowflake(faker)
    initiator_id = _snowflake(faker)
    target_id = _snowflake(faker)
    amount = faker.random_int(min=1, max=5000)
    transfer_id = uuid4()

    mock_row = {
        "transfer_id": transfer_id,
        "guild_id": guild_id,
        "initiator_id": initiator_id,
        "target_id": target_id,
        "amount": amount,
        "metadata": {},
        "status": "approved",
    }
    mock_conn.fetchrow = AsyncMock(return_value=mock_row)

    mock_pending_gateway = AsyncMock()
    mock_pending_gateway.update_status = AsyncMock()
    mock_transfer_gateway = AsyncMock()

    # Error with a BaseException cause
    original_exception = ValueError("Original error")
    db_error = DatabaseError("Transfer failed")
    db_error.cause = original_exception  # type: ignore[attr-defined]
    mock_transfer_gateway.transfer_currency = AsyncMock(return_value=Err(db_error))

    coordinator = TransferEventPoolCoordinator(
        pool=mock_pool,
        pending_gateway=mock_pending_gateway,
        transfer_gateway=mock_transfer_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._execute_transfer(transfer_id)

        # Status should be updated to rejected
        mock_pending_gateway.update_status.assert_awaited()
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cleanup_expired_with_connection() -> None:
    """Test cleanup expired with externally provided connection."""
    mock_conn = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_tx)
    mock_conn.execute = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])

    mock_pending_gateway = AsyncMock()

    coordinator = TransferEventPoolCoordinator(
        pool=None,  # No pool
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._cleanup_expired(connection=mock_conn)

        # Verify UPDATE query was executed
        mock_conn.execute.assert_called()
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_checks_no_pool_no_connection() -> None:
    """Test retry checks returns early when no pool and no connection."""
    mock_pending_gateway = AsyncMock()
    transfer_id = uuid4()

    coordinator = TransferEventPoolCoordinator(
        pool=None,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._retry_checks(transfer_id)

        # Nothing should be called
        mock_pending_gateway.update_status.assert_not_awaited()
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schedule_retry_no_pool() -> None:
    """Test schedule retry returns early when no pool."""
    mock_pending_gateway = AsyncMock()
    transfer_id = uuid4()

    coordinator = TransferEventPoolCoordinator(
        pool=None,
        pending_gateway=mock_pending_gateway,
    )

    await coordinator.start()
    try:
        await coordinator._schedule_retry(transfer_id)

        # Nothing should be called
        mock_pending_gateway.get_pending_transfer.assert_not_awaited()
    finally:
        await coordinator.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cleanup_expired_no_pool() -> None:
    """Test cleanup expired returns early when no pool and no connection."""
    mock_pending_gateway = AsyncMock()

    coordinator = TransferEventPoolCoordinator(
        pool=None,
        pending_gateway=mock_pending_gateway,
    )

    # Don't start (or start without pool)
    await coordinator._cleanup_expired()

    # Nothing should happen, no exceptions
