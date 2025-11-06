from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

import pytest

from src.bot.services.balance_service import (
    BalancePermissionError,
    BalanceService,
    BalanceSnapshot,
)


def _snowflake() -> int:
    """Generate a random Discord snowflake for deterministic isolation."""
    return secrets.randbits(63)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_balance_view_self_initialises_ledger(
    db_pool: Any,
    db_connection: Any,
) -> None:
    service = BalanceService(db_pool)
    guild_id = _snowflake()
    member_id = _snowflake()

    snapshot = await service.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=member_id,
        target_member_id=None,
        can_view_others=False,
        connection=db_connection,
    )

    assert isinstance(snapshot, BalanceSnapshot)
    assert snapshot.guild_id == guild_id
    assert snapshot.member_id == member_id
    assert snapshot.balance == 0
    assert snapshot.last_modified_at.tzinfo is not None

    ledger_balance = await db_connection.fetchval(
        """
        SELECT current_balance
        FROM economy.guild_member_balances
        WHERE guild_id = $1 AND member_id = $2
        """,
        guild_id,
        member_id,
    )
    assert ledger_balance == 0


@pytest.mark.asyncio
async def test_balance_view_other_requires_permission(
    db_pool: Any,
    db_connection: Any,
) -> None:
    service = BalanceService(db_pool)
    guild_id = _snowflake()
    requester_id = _snowflake()
    target_id = _snowflake()
    updated = datetime(2025, 10, 20, 18, 45, tzinfo=timezone.utc)

    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (
            guild_id,
            member_id,
            current_balance,
            last_modified_at,
            created_at
        )
        VALUES ($1, $2, $3, $4, $4)
        ON CONFLICT (guild_id, member_id) DO UPDATE
        SET current_balance = EXCLUDED.current_balance,
            last_modified_at = EXCLUDED.last_modified_at
        """,
        guild_id,
        target_id,
        725,
        updated,
    )

    with pytest.raises(BalancePermissionError):
        await service.get_balance_snapshot(
            guild_id=guild_id,
            requester_id=requester_id,
            target_member_id=target_id,
            can_view_others=False,
            connection=db_connection,
        )

    snapshot = await service.get_balance_snapshot(
        guild_id=guild_id,
        requester_id=requester_id,
        target_member_id=target_id,
        can_view_others=True,
        connection=db_connection,
    )

    assert snapshot.member_id == target_id
    assert snapshot.balance == 725
    assert snapshot.last_modified_at == updated
