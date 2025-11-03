from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from src.bot.services.balance_service import BalanceService, HistoryPage


def _snowflake() -> int:
    return secrets.randbits(63)


@pytest.mark.asyncio
async def test_history_returns_paginated_entries(
    db_pool: Any,
    db_connection: Any,
) -> None:
    service = BalanceService(db_pool)
    guild_id = _snowflake()
    member_id = _snowflake()
    counterparty_id = _snowflake()

    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, 0), ($1, $3, 0)
        ON CONFLICT DO NOTHING
        """,
        guild_id,
        member_id,
        counterparty_id,
    )

    base_time = datetime(2025, 10, 22, 12, 0, tzinfo=timezone.utc)
    for index in range(6):
        created_at = base_time - timedelta(minutes=index)
        await db_connection.execute(
            """
            INSERT INTO economy.currency_transactions (
                guild_id,
                initiator_id,
                target_id,
                amount,
                direction,
                reason,
                balance_after_initiator,
                balance_after_target,
                metadata,
                created_at
            )
            VALUES ($1, $2, $3, $4, 'transfer', $6, $7, $8, '{}'::jsonb, $5)
            """,
            guild_id,
            member_id if index % 2 == 0 else counterparty_id,
            counterparty_id if index % 2 == 0 else member_id,
            100 + index,
            created_at,
            f"Reason {index}",
            1000 - index,
            500 + index,
        )

    first_page = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        target_member_id=None,
        can_view_others=False,
        limit=3,
        cursor=None,
        connection=db_connection,
    )

    assert isinstance(first_page, HistoryPage)
    assert len(first_page.items) == 3
    assert first_page.next_cursor is not None
    first_times = [entry.created_at for entry in first_page.items]
    assert first_times == sorted(first_times, reverse=True)

    second_page = await service.get_history(
        guild_id=guild_id,
        requester_id=member_id,
        target_member_id=None,
        can_view_others=False,
        limit=3,
        cursor=first_page.next_cursor,
        connection=db_connection,
    )

    assert len(second_page.items) == 3
    assert all(entry.created_at < first_page.items[-1].created_at for entry in second_page.items)


@pytest.mark.asyncio
async def test_history_limit_validation(
    db_pool: Any,
    db_connection: Any,
) -> None:
    service = BalanceService(db_pool)
    guild_id = _snowflake()
    member_id = _snowflake()

    with pytest.raises(ValueError):
        await service.get_history(
            guild_id=guild_id,
            requester_id=member_id,
            target_member_id=None,
            can_view_others=False,
            limit=0,
            cursor=None,
            connection=db_connection,
        )

    with pytest.raises(ValueError):
        await service.get_history(
            guild_id=guild_id,
            requester_id=member_id,
            target_member_id=None,
            can_view_others=False,
            limit=51,
            cursor=None,
            connection=db_connection,
        )
