"""效能測試：Council 提案投票流程的效能（P95 延遲 < 3s）。"""

from __future__ import annotations

import os
import secrets
import statistics
import time
from typing import Any, cast

import pytest

from src.bot.services.council_service import CouncilService
from src.bot.services.transfer_service import TransferService
from tests.unit.test_council_service import (
    FakeConnection,
    FakeGateway,
    FakePool,
)


def _snowflake() -> int:
    """生成 Discord snowflake ID。"""
    return secrets.randbits(63)


class _FakeGatewayWithPerformance(FakeGateway):
    """擴展的 Fake Gateway，支援效能測試。"""

    async def list_active_proposals(self, connection: Any) -> Any:
        return [p for p in self._proposals.values() if p.status == "進行中"]


class FakeTransferService:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[int, int, int]] = []

    async def transfer_currency(
        self,
        *,
        guild_id: int,
        initiator_id: int,
        target_id: int,
        amount: int,
        reason: str | None = None,
        connection: Any | None = None,
    ) -> Any:
        from datetime import datetime, timezone
        from uuid import uuid4

        from src.bot.services.transfer_service import TransferError, TransferResult

        if self.should_fail:
            raise TransferError("insufficient funds")
        self.calls.append((initiator_id, target_id, amount))
        # 假回傳成功結果
        return TransferResult(
            transaction_id=uuid4(),
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
            initiator_balance=0,
            target_balance=0,
            direction="transfer",
            created_at=datetime.now(timezone.utc),
            throttled_until=None,
            metadata={},
        )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_council_voting_latency_p95_under_3s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """效能測試：Council 投票流程 P95 延遲應小於 3 秒。"""
    # 允許透過環境變數調整測試規模
    total_votes = int(os.getenv("PERF_COUNCIL_VOTE_COUNT", "100"))

    gw = _FakeGatewayWithPerformance()
    conn = FakeConnection(gw)
    pool = FakePool(conn)
    fake_transfer = FakeTransferService()
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw, transfer_service=cast(TransferService, fake_transfer))
    await svc.set_config(guild_id=100, council_role_id=200)

    # 建立一個提案（需要多票才能通過）
    snapshot_size = 10
    snapshot_member_ids = [_snowflake() for _ in range(snapshot_size)]
    proposal = (
        await svc.create_transfer_proposal(
            guild_id=100,
            proposer_id=snapshot_member_ids[0],
            target_id=_snowflake(),
            amount=100,
            description="performance test",
            attachment_url=None,
            snapshot_member_ids=snapshot_member_ids,
        )
    ).unwrap()

    latencies: list[float] = []

    # 執行多次投票操作
    for i in range(min(total_votes, snapshot_size)):
        voter_id = snapshot_member_ids[i % len(snapshot_member_ids)]
        choice = "approve" if i % 2 == 0 else "reject"

        t0 = time.perf_counter()
        await svc.vote(proposal_id=proposal.proposal_id, voter_id=voter_id, choice=choice)
        latencies.append(time.perf_counter() - t0)

    # 計算 P95 延遲
    if latencies:
        latencies_sorted = sorted(latencies)
        p95_index = int(len(latencies_sorted) * 0.95)
        p95_latency = (
            latencies_sorted[p95_index]
            if p95_index < len(latencies_sorted)
            else latencies_sorted[-1]
        )

        # 驗證 P95 延遲小於 3 秒
        assert (
            p95_latency < 3.0
        ), f"P95 voting latency {p95_latency:.3f}s exceeds 3s budget. Max: {max(latencies):.3f}s, Mean: {statistics.mean(latencies):.3f}s"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_council_proposal_creation_latency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """效能測試：Council 提案建立延遲。"""
    total_proposals = int(os.getenv("PERF_COUNCIL_PROPOSAL_COUNT", "50"))

    gw = _FakeGatewayWithPerformance()
    conn = FakeConnection(gw)
    pool = FakePool(conn)
    fake_transfer = FakeTransferService()
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw, transfer_service=cast(TransferService, fake_transfer))
    await svc.set_config(guild_id=100, council_role_id=200)

    latencies: list[float] = []

    for i in range(total_proposals):
        snapshot_member_ids = [_snowflake() for _ in range(5 + (i % 10))]

        t0 = time.perf_counter()
        await svc.create_transfer_proposal(
            guild_id=100,
            proposer_id=_snowflake(),
            target_id=_snowflake(),
            amount=100 + i,
            description=f"performance test {i}",
            attachment_url=None,
            snapshot_member_ids=snapshot_member_ids,
        )
        latencies.append(time.perf_counter() - t0)

    # 驗證平均延遲合理（提案建立應該很快）
    if latencies:
        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)
        assert (
            avg_latency < 1.0
        ), f"Average proposal creation latency {avg_latency:.3f}s exceeds 1s budget. Max: {max_latency:.3f}s"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_council_list_active_proposals_latency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """效能測試：Council 列出進行中提案的延遲。"""
    # 建立多個提案
    total_proposals = int(os.getenv("PERF_COUNCIL_LIST_PROPOSAL_COUNT", "20"))

    gw = _FakeGatewayWithPerformance()
    conn = FakeConnection(gw)
    pool = FakePool(conn)
    fake_transfer = FakeTransferService()
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw, transfer_service=cast(TransferService, fake_transfer))
    await svc.set_config(guild_id=100, council_role_id=200)

    # 預先建立多個提案
    for i in range(total_proposals):
        await svc.create_transfer_proposal(
            guild_id=100,
            proposer_id=_snowflake(),
            target_id=_snowflake(),
            amount=100 + i,
            description=f"list test {i}",
            attachment_url=None,
            snapshot_member_ids=[_snowflake() for _ in range(5)],
        )

    # 測試列出操作的延遲
    latencies: list[float] = []
    iterations = 50

    for _ in range(iterations):
        t0 = time.perf_counter()
        await svc.list_active_proposals()
        latencies.append(time.perf_counter() - t0)

    # 驗證列出操作應該很快
    if latencies:
        avg_latency = statistics.mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        assert (
            p95_latency < 1.0
        ), f"P95 list latency {p95_latency:.3f}s exceeds 1s budget. Avg: {avg_latency:.3f}s"
