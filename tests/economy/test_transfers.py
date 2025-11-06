from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

import pytest

from src.bot.services.transfer_service import (
    InsufficientBalanceError,
    TransferResult,
    TransferService,
    TransferValidationError,
)


def _snowflake() -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    # Discord snowflakes fit in 64-bit; reserve sign bit to stay positive.
    return secrets.randbits(63)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_success(
    db_pool: Any,
    db_connection: Any,
) -> None:
    service = TransferService(db_pool)
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3)
        """,
        guild_id,
        initiator_id,
        500,
    )

    result = await service.transfer_currency(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=200,
        reason="Guild event prize",
        connection=db_connection,
    )

    assert isinstance(result, TransferResult)
    assert result.transaction_id is not None
    assert result.guild_id == guild_id
    assert result.initiator_id == initiator_id
    assert result.target_id == target_id
    assert result.amount == 200
    assert result.initiator_balance == 300
    assert result.target_balance == 200
    assert isinstance(result.created_at, datetime)
    assert result.created_at.tzinfo is not None
    assert result.direction == "transfer"
    assert result.throttled_until is None
    assert result.metadata.get("reason") == "Guild event prize"


@pytest.mark.asyncio
async def test_transfer_insufficient_balance(
    db_pool: Any,
    db_connection: Any,
) -> None:
    service = TransferService(db_pool)
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3)
        """,
        guild_id,
        initiator_id,
        50,
    )

    with pytest.raises(InsufficientBalanceError):
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=200,
            reason=None,
            connection=db_connection,
        )

    balance = await db_connection.fetchval(
        """
        SELECT current_balance
        FROM economy.guild_member_balances
        WHERE guild_id = $1 AND member_id = $2
        """,
        guild_id,
        initiator_id,
    )
    assert balance == 50


@pytest.mark.asyncio
async def test_transfer_invalid_target(
    db_pool: Any,
    db_connection: Any,
) -> None:
    service = TransferService(db_pool)
    guild_id = _snowflake()
    initiator_id = _snowflake()

    with pytest.raises(TransferValidationError):
        await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=initiator_id,
            amount=10,
            reason=None,
            connection=db_connection,
        )
