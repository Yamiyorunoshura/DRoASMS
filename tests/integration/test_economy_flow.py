from __future__ import annotations

import secrets
from datetime import datetime

import pytest

from src.bot.services.adjustment_service import AdjustmentResult, AdjustmentService
from src.bot.services.balance_service import BalanceService, HistoryPage
from src.bot.services.transfer_service import TransferResult, TransferService


def _snowflake() -> int:
    return secrets.randbits(63)


@pytest.mark.asyncio
async def test_transfer_history_adjust_flow(
    db_pool,  # type: ignore[no-untyped-call]
    db_connection,  # type: ignore[no-untyped-call]
) -> None:
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()
    admin_id = _snowflake()

    # Seed initiator balance
    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3)
        """,
        guild_id,
        initiator_id,
        300,
    )

    transfers = TransferService(db_pool)
    balances = BalanceService(db_pool)
    adjustments = AdjustmentService(db_pool)

    # Step 1: transfer
    tr: TransferResult = await transfers.transfer_currency(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=150,
        reason="integration: prize",
        connection=db_connection,
    )
    assert tr.amount == 150
    assert tr.initiator_balance == 150
    assert tr.target_balance == 150
    assert isinstance(tr.created_at, datetime)

    # Step 2: history and balances after transfer
    snap_initiator = await balances.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=initiator_id,
        connection=db_connection,
    )
    snap_target = await balances.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=target_id,
        connection=db_connection,
    )
    assert snap_initiator.balance == 150
    assert snap_target.balance == 150

    page_initiator: HistoryPage = await balances.get_history(
        guild_id=guild_id,
        requester_id=initiator_id,
        limit=5,
        connection=db_connection,
    )
    assert any(e.transaction_id == tr.transaction_id for e in page_initiator.items)

    # Step 3: admin adjustment to target (+25)
    adj: AdjustmentResult = await adjustments.adjust_balance(
        guild_id=guild_id,
        admin_id=admin_id,
        target_id=target_id,
        amount=25,
        reason="integration: top up",
        can_adjust=True,
        connection=db_connection,
    )
    assert adj.target_balance_after == 175

    # Final: confirm target history reflects both operations
    page_target: HistoryPage = await balances.get_history(
        guild_id=guild_id,
        requester_id=target_id,
        limit=10,
        connection=db_connection,
    )
    kinds = {e.direction for e in page_target.items}
    assert "transfer" in kinds and ("adjustment_grant" in kinds or "adjustment_deduct" in kinds)
