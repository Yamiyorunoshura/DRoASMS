"""Integration tests for transfer event pool flow."""

from __future__ import annotations

import asyncio
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest

from src.bot.services.transfer_event_pool import TransferEventPoolCoordinator
from src.bot.services.transfer_service import TransferService
from src.db.gateway.economy_pending_transfers import PendingTransferGateway


def _snowflake() -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return secrets.randbits(63)


@pytest.mark.asyncio
async def test_event_pool_success_flow(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test complete success flow: create → checks pass → execute."""
    # Set up coordinator
    coordinator = TransferEventPoolCoordinator(pool=db_pool)
    await coordinator.start()

    try:
        guild_id = _snowflake()
        initiator_id = _snowflake()
        target_id = _snowflake()

        # Set up balances
        await db_connection.execute(
            """
            INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, member_id) DO UPDATE
            SET current_balance = $3
            """,
            guild_id,
            initiator_id,
            500,
        )

        await db_connection.execute(
            """
            INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, member_id) DO UPDATE
            SET current_balance = $3
            """,
            guild_id,
            target_id,
            0,
        )

        # Create pending transfer
        gateway = PendingTransferGateway()
        transfer_id = await gateway.create_pending_transfer(
            db_connection,
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=100,
            metadata={"reason": "test"},
            expires_at=None,
        )

        # Manually trigger checks (simulating trigger behavior)
        await db_connection.execute(
            """
            SELECT economy.fn_check_transfer_balance($1);
            SELECT economy.fn_check_transfer_cooldown($1);
            SELECT economy.fn_check_transfer_daily_limit($1);
            """,
            transfer_id,
        )

        # Give time for checks to complete and approval to happen
        await asyncio.sleep(0.5)

        # Verify transfer was approved (status should be approved or completed)
        pending = await gateway.get_pending_transfer(db_connection, transfer_id=transfer_id)
        assert pending is not None
        assert pending.status in ("approved", "completed")

        # Verify checks are all set to 1
        assert pending.checks.get("balance") == 1
        assert pending.checks.get("cooldown") == 1
        assert pending.checks.get("daily_limit") == 1

    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_event_pool_retry_flow(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test retry flow: insufficient balance → retry → success."""
    coordinator = TransferEventPoolCoordinator(pool=db_pool)
    await coordinator.start()

    try:
        guild_id = _snowflake()
        initiator_id = _snowflake()
        target_id = _snowflake()

        # Start with insufficient balance
        await db_connection.execute(
            """
            INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, member_id) DO UPDATE
            SET current_balance = $3
            """,
            guild_id,
            initiator_id,
            50,  # Less than transfer amount
        )

        gateway = PendingTransferGateway()
        transfer_id = await gateway.create_pending_transfer(
            db_connection,
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=100,
            metadata={},
            expires_at=None,
        )

        # Trigger checks - balance should fail
        await db_connection.execute(
            """
            SELECT economy.fn_check_transfer_balance($1);
            SELECT economy.fn_check_transfer_cooldown($1);
            SELECT economy.fn_check_transfer_daily_limit($1);
            """,
            transfer_id,
        )

        await asyncio.sleep(0.2)

        # Verify balance check failed
        pending = await gateway.get_pending_transfer(db_connection, transfer_id=transfer_id)
        assert pending is not None
        assert pending.checks.get("balance") == 0

        # Now add more balance
        await db_connection.execute(
            """
            UPDATE economy.guild_member_balances
            SET current_balance = $3
            WHERE guild_id = $1 AND member_id = $2
            """,
            guild_id,
            initiator_id,
            500,
        )

        # Retry checks
        # 使用同一個測試連線觸發重試，避免跨連線看不到未提交的餘額更新
        await coordinator._retry_checks(transfer_id, connection=db_connection)

        await asyncio.sleep(0.3)

        # Verify checks now pass
        pending = await gateway.get_pending_transfer(db_connection, transfer_id=transfer_id)
        assert pending is not None
        assert pending.checks.get("balance") == 1

    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_transfer_service_event_pool_mode(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test TransferService in event pool mode."""
    # Temporarily enable event pool mode
    original_env = os.environ.get("TRANSFER_EVENT_POOL_ENABLED", "false")
    os.environ["TRANSFER_EVENT_POOL_ENABLED"] = "true"

    try:
        service = TransferService(
            db_pool,
            event_pool_enabled=True,
        )

        guild_id = _snowflake()
        initiator_id = _snowflake()
        target_id = _snowflake()

        # Create pending transfer via service
        result = await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=100,
            reason="test",
            connection=db_connection,
        )

        # Should return UUID in event pool mode
        assert isinstance(result, UUID)

        # Verify pending transfer exists
        gateway = PendingTransferGateway()
        pending = await gateway.get_pending_transfer(db_connection, transfer_id=result)
        assert pending is not None
        assert pending.amount == 100
        assert pending.metadata.get("reason") == "test"

        # Test status query
        status = await service.get_transfer_status(
            transfer_id=result,
            connection=db_connection,
        )
        assert status is not None
        assert status.transfer_id == result

    finally:
        os.environ["TRANSFER_EVENT_POOL_ENABLED"] = original_env


@pytest.mark.asyncio
async def test_expired_transfer_cleanup(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test expired transfer cleanup."""
    coordinator = TransferEventPoolCoordinator(pool=db_pool)
    await coordinator.start()

    try:
        guild_id = _snowflake()
        initiator_id = _snowflake()
        target_id = _snowflake()

        gateway = PendingTransferGateway()

        # Create expired transfer
        expired_at = datetime.now(timezone.utc) - timedelta(hours=1)
        transfer_id = await gateway.create_pending_transfer(
            db_connection,
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=100,
            metadata={},
            expires_at=expired_at,
        )

        # Manually run cleanup
        # 在同一交易連線中清理，確保可見剛建立（未提交）的測試資料
        await coordinator._cleanup_expired(connection=db_connection)

        # Verify expired transfer was marked as rejected
        pending = await gateway.get_pending_transfer(db_connection, transfer_id=transfer_id)
        assert pending is not None
        assert pending.status == "rejected"

    finally:
        await coordinator.stop()
