from __future__ import annotations

import os
import secrets
import time

import pytest

from src.bot.services.transfer_service import TransferService


def _snowflake() -> int:
    return secrets.randbits(63)


@pytest.mark.performance
@pytest.mark.asyncio
async def test_transfer_confirmation_latency_under_5s(
    db_pool,  # type: ignore[no-untyped-call]
    db_connection,  # type: ignore[no-untyped-call]
) -> None:
    # Allow tuning via env; default to 500 operations to simulate daily volume
    total_ops = int(os.getenv("PERF_TX_COUNT", "500"))

    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    # Seed a large balance to avoid insufficiency
    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3)
        """,
        guild_id,
        initiator_id,
        10_000_000,
    )

    svc = TransferService(db_pool)
    latencies: list[float] = []

    for _i in range(total_ops):
        t0 = time.perf_counter()
        await svc.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=1,
            reason=None,
            connection=db_connection,
        )
        latencies.append(time.perf_counter() - t0)

    # Assert max confirmation latency under 5 seconds
    worst = max(latencies) if latencies else 0.0
    assert worst < 5.0, f"Worst confirmation latency {worst:.3f}s exceeds 5s budget"
