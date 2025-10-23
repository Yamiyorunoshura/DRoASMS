from __future__ import annotations

import secrets
from datetime import datetime

import pytest

from src.bot.services.adjustment_service import (
    AdjustmentResult,
    AdjustmentService,
    UnauthorizedAdjustmentError,
    ValidationError,
)


def _snowflake() -> int:
    return secrets.randbits(63)


@pytest.mark.asyncio
async def test_admin_grant_success(
    db_pool,  # type: ignore[no-untyped-call]
    db_connection,  # type: ignore[no-untyped-call]
) -> None:
    service = AdjustmentService(db_pool)

    guild_id = _snowflake()
    admin_id = _snowflake()
    member_id = _snowflake()

    # Seed target balance row to ensure FK paths exist
    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3)
        """,
        guild_id,
        member_id,
        0,
    )

    result = await service.adjust_balance(
        guild_id=guild_id,
        admin_id=admin_id,
        target_id=member_id,
        amount=250,
        reason="Event reward",
        can_adjust=True,
        connection=db_connection,
    )

    assert isinstance(result, AdjustmentResult)
    assert result.guild_id == guild_id
    assert result.admin_id == admin_id
    assert result.target_id == member_id
    assert result.amount == 250
    assert result.direction == "adjustment_grant"
    assert isinstance(result.created_at, datetime)
    assert result.created_at.tzinfo is not None
    assert result.target_balance_after == 250
    assert result.metadata.get("reason") == "Event reward"


@pytest.mark.asyncio
async def test_unauthorized_adjustment_rejected(
    db_pool,  # type: ignore[no-untyped-call]
    db_connection,  # type: ignore[no-untyped-call]
) -> None:
    service = AdjustmentService(db_pool)

    guild_id = _snowflake()
    admin_id = _snowflake()
    member_id = _snowflake()

    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3)
        """,
        guild_id,
        member_id,
        100,
    )

    with pytest.raises(UnauthorizedAdjustmentError):
        await service.adjust_balance(
            guild_id=guild_id,
            admin_id=admin_id,
            target_id=member_id,
            amount=50,
            reason="Not an admin",
            can_adjust=False,  # critical: should block before DB
            connection=db_connection,
        )


@pytest.mark.asyncio
async def test_deduct_cannot_drop_below_zero(
    db_pool,  # type: ignore[no-untyped-call]
    db_connection,  # type: ignore[no-untyped-call]
) -> None:
    service = AdjustmentService(db_pool)

    guild_id = _snowflake()
    admin_id = _snowflake()
    member_id = _snowflake()

    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3)
        """,
        guild_id,
        member_id,
        40,
    )

    with pytest.raises(ValidationError):
        await service.adjust_balance(
            guild_id=guild_id,
            admin_id=admin_id,
            target_id=member_id,
            amount=-100,  # deduct beyond zero
            reason="Penalty",
            can_adjust=True,
            connection=db_connection,
        )
