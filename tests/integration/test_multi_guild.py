"""整合測試：多租戶場景（多個 guild 同時操作，資料隔離）。"""

from __future__ import annotations

import secrets
from typing import Any

import pytest

from src.bot.services.balance_service import BalanceService
from src.bot.services.transfer_service import TransferService


def _snowflake() -> int:
    """生成 Discord snowflake ID。"""
    return secrets.randbits(63)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_guild_data_isolation(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """測試多個 guild 的資料隔離：不同 guild 的餘額和轉帳記錄互不影響。"""
    guild_1 = _snowflake()
    guild_2 = _snowflake()
    user_1 = _snowflake()
    user_2 = _snowflake()

    # 為兩個 guild 分別設置初始餘額
    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3), ($4, $5, $6)
        """,
        guild_1,
        user_1,
        1000,
        guild_2,
        user_2,
        2000,
    )

    transfer_service = TransferService(db_pool)
    balance_service = BalanceService(db_pool)

    # Guild 1: 轉帳操作
    result_1 = await transfer_service.transfer_currency(
        guild_id=guild_1,
        initiator_id=user_1,
        target_id=_snowflake(),
        amount=100,
        reason="guild 1 transfer",
        connection=db_connection,
    )
    assert result_1.guild_id == guild_1
    assert result_1.initiator_balance == 900

    # Guild 2: 轉帳操作
    result_2 = await transfer_service.transfer_currency(
        guild_id=guild_2,
        initiator_id=user_2,
        target_id=_snowflake(),
        amount=200,
        reason="guild 2 transfer",
        connection=db_connection,
    )
    assert result_2.guild_id == guild_2
    assert result_2.initiator_balance == 1800

    # 驗證資料隔離：Guild 1 的餘額不受 Guild 2 操作影響
    balance_1 = await balance_service.get_balance_snapshot(
        guild_id=guild_1,
        requester_id=user_1,
        connection=db_connection,
    )
    assert balance_1.balance == 900

    balance_2 = await balance_service.get_balance_snapshot(
        guild_id=guild_2,
        requester_id=user_2,
        connection=db_connection,
    )
    assert balance_2.balance == 1800

    # 驗證歷史記錄隔離
    history_1 = await balance_service.get_history(
        guild_id=guild_1,
        requester_id=user_1,
        limit=10,
        connection=db_connection,
    )
    assert len(history_1.items) >= 1
    assert all(item.guild_id == guild_1 for item in history_1.items)

    history_2 = await balance_service.get_history(
        guild_id=guild_2,
        requester_id=user_2,
        limit=10,
        connection=db_connection,
    )
    assert len(history_2.items) >= 1
    assert all(item.guild_id == guild_2 for item in history_2.items)

    # 驗證不同 guild 的記錄不會混在一起
    assert not any(item.guild_id == guild_2 for item in history_1.items)
    assert not any(item.guild_id == guild_1 for item in history_2.items)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_guild_concurrent_operations(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """測試多個 guild 同時操作的並發場景。"""
    guild_1 = _snowflake()
    guild_2 = _snowflake()
    guild_3 = _snowflake()
    users = [_snowflake() for _ in range(3)]

    # 為三個 guild 設置初始餘額
    for i, guild_id in enumerate([guild_1, guild_2, guild_3]):
        await db_connection.execute(
            """
            INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
            VALUES ($1, $2, $3)
            """,
            guild_id,
            users[i],
            5000,
        )

    transfer_service = TransferService(db_pool)

    # 模擬並發操作：三個 guild 同時進行轉帳
    results = []
    for i, guild_id in enumerate([guild_1, guild_2, guild_3]):
        result = await transfer_service.transfer_currency(
            guild_id=guild_id,
            initiator_id=users[i],
            target_id=_snowflake(),
            amount=100 * (i + 1),  # 不同金額：100, 200, 300
            reason=f"concurrent transfer from guild {i+1}",
            connection=db_connection,
        )
        results.append((guild_id, result))

    # 驗證每個 guild 的操作都成功且獨立
    assert len(results) == 3
    assert results[0][1].guild_id == guild_1
    assert results[0][1].amount == 100
    assert results[0][1].initiator_balance == 4900

    assert results[1][1].guild_id == guild_2
    assert results[1][1].amount == 200
    assert results[1][1].initiator_balance == 4800

    assert results[2][1].guild_id == guild_3
    assert results[2][1].amount == 300
    assert results[2][1].initiator_balance == 4700


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_guild_same_user_different_guilds(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """測試同一用戶在不同 guild 中的餘額是獨立的。"""
    guild_1 = _snowflake()
    guild_2 = _snowflake()
    same_user = _snowflake()

    # 同一用戶在兩個 guild 中有不同的初始餘額
    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3), ($4, $2, $5)
        """,
        guild_1,
        same_user,
        1000,
        guild_2,
        same_user,
        2000,
    )

    transfer_service = TransferService(db_pool)
    balance_service = BalanceService(db_pool)

    # Guild 1 中的轉帳
    await transfer_service.transfer_currency(
        guild_id=guild_1,
        initiator_id=same_user,
        target_id=_snowflake(),
        amount=100,
        reason="guild 1",
        connection=db_connection,
    )

    # Guild 2 中的轉帳
    await transfer_service.transfer_currency(
        guild_id=guild_2,
        initiator_id=same_user,
        target_id=_snowflake(),
        amount=200,
        reason="guild 2",
        connection=db_connection,
    )

    # 驗證兩個 guild 中的餘額互不影響
    balance_guild_1 = await balance_service.get_balance_snapshot(
        guild_id=guild_1,
        requester_id=same_user,
        connection=db_connection,
    )
    assert balance_guild_1.balance == 900

    balance_guild_2 = await balance_service.get_balance_snapshot(
        guild_id=guild_2,
        requester_id=same_user,
        connection=db_connection,
    )
    assert balance_guild_2.balance == 1800
