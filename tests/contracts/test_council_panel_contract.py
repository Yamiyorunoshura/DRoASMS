"""契約測試：Council 面板互動流程（提案、投票、執行、匯出）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

from src.bot.services.council_service import CouncilService
from src.bot.services.transfer_service import TransferResult
from tests.unit.test_council_service import (
    _FakeConnection,
    _FakeGateway,
    _FakePool,
)


class _FakeGatewayWithList(_FakeGateway):
    async def list_active_proposals(self, conn: Any) -> Any:
        return [p for p in self._proposals.values() if p.status == "進行中"]

    async def export_interval(
        self, conn: Any, *, guild_id: int, start: datetime, end: datetime
    ) -> list[dict[str, object]]:
        """模擬匯出功能：回傳指定時間範圍內的提案記錄。"""
        results = []
        for p in self._proposals.values():
            if p.guild_id == guild_id and start <= p.created_at <= end:
                results.append(
                    {
                        "proposal_id": str(p.proposal_id),
                        "guild_id": p.guild_id,
                        "proposer_id": p.proposer_id,
                        "target_id": p.target_id,
                        "amount": p.amount,
                        "status": p.status,
                        "created_at": p.created_at.isoformat(),
                    }
                )
        return results


class _FakeTransferService:
    def __init__(self) -> None:
        self.transfers: list[dict[str, Any]] = []

    async def transfer_currency(
        self,
        *,
        guild_id: int,
        initiator_id: int,
        target_id: int,
        amount: int,
        reason: str | None = None,
        connection: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> TransferResult:
        """模擬轉帳服務：記錄轉帳並回傳結果。"""
        result = TransferResult(
            transaction_id=uuid4(),
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
            initiator_balance=10000 - amount,
            target_balance=amount,
            direction="transfer",
            created_at=datetime.now(timezone.utc),
            throttled_until=None,
            metadata={"reason": reason} if reason else None,
        )
        self.transfers.append(
            {
                "guild_id": guild_id,
                "initiator_id": initiator_id,
                "target_id": target_id,
                "amount": amount,
            }
        )
        return result


@pytest.mark.contract
@pytest.mark.asyncio
async def test_council_panel_create_proposal_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """契約測試：面板建案流程。"""
    gw = _FakeGatewayWithList()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    # 建案
    p = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=10,
        target_id=20,
        amount=30,
        description="panel test",
        attachment_url=None,
        snapshot_member_ids=[10, 11, 12],
    )

    assert p.proposal_id is not None
    assert p.status == "進行中"
    assert p.amount == 30
    assert p.description == "panel test"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_council_panel_list_active_proposals_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """契約測試：面板列出進行中提案。"""
    gw = _FakeGatewayWithList()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    # 建立多個提案
    p1 = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=10,
        target_id=20,
        amount=30,
        description="proposal 1",
        attachment_url=None,
        snapshot_member_ids=[10, 11, 12],
    )
    p2 = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=11,
        target_id=21,
        amount=40,
        description="proposal 2",
        attachment_url=None,
        snapshot_member_ids=[10, 11, 12],
    )

    # 面板列出
    items = await svc.list_active_proposals()
    assert len(items) >= 2
    assert any(x.proposal_id == p1.proposal_id for x in items)
    assert any(x.proposal_id == p2.proposal_id for x in items)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_council_panel_vote_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """契約測試：面板投票流程。"""
    gw = _FakeGatewayWithList()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    # 建案
    p = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=10,
        target_id=20,
        amount=30,
        description="vote test",
        attachment_url=None,
        snapshot_member_ids=[10, 11, 12],
    )

    # 投票
    totals, status = await svc.vote(proposal_id=p.proposal_id, voter_id=10, choice="approve")
    assert totals.approve == 1
    assert totals.reject == 0
    assert totals.abstain == 0
    assert status == "進行中"  # 尚未達到門檻

    # 再投一票
    totals2, status2 = await svc.vote(proposal_id=p.proposal_id, voter_id=11, choice="reject")
    assert totals2.approve == 1
    assert totals2.reject == 1


@pytest.mark.contract
@pytest.mark.asyncio
async def test_council_panel_execute_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """契約測試：面板執行提案（通過後自動執行）。"""
    gw = _FakeGatewayWithList()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    fake_transfer = _FakeTransferService()
    svc = CouncilService(gateway=gw, transfer_service=fake_transfer)
    await svc.set_config(guild_id=100, council_role_id=200)

    # 建案（僅需 2 票即可通過）
    p = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=10,
        target_id=20,
        amount=30,
        description="execute test",
        attachment_url=None,
        snapshot_member_ids=[10, 11],  # 僅 2 人，門檻為 2
    )

    # 投兩票通過
    await svc.vote(proposal_id=p.proposal_id, voter_id=10, choice="approve")
    totals, status = await svc.vote(proposal_id=p.proposal_id, voter_id=11, choice="approve")

    # 應該已通過並執行
    assert totals.approve >= p.threshold_t
    assert status in ["已通過", "已執行"]

    # 驗證轉帳服務被呼叫
    assert len(fake_transfer.transfers) >= 1
    transfer = fake_transfer.transfers[0]
    assert transfer["amount"] == 30
    assert transfer["target_id"] == 20


@pytest.mark.contract
@pytest.mark.asyncio
async def test_council_panel_export_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """契約測試：面板匯出功能。"""
    gw = _FakeGatewayWithList()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    # 建立提案
    now = datetime.now(timezone.utc)
    p = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=10,
        target_id=20,
        amount=30,
        description="export test",
        attachment_url=None,
        snapshot_member_ids=[10, 11, 12],
    )

    # 匯出指定時間範圍
    start = now - timedelta(days=1)
    end = now + timedelta(days=1)
    results = await svc.export_interval(guild_id=100, start=start, end=end)

    assert len(results) >= 1
    assert any(r["proposal_id"] == str(p.proposal_id) for r in results)
    # 驗證匯出格式
    result = next(r for r in results if r["proposal_id"] == str(p.proposal_id))
    assert "guild_id" in result
    assert "proposer_id" in result
    assert "amount" in result
    assert "status" in result


@pytest.mark.contract
@pytest.mark.asyncio
async def test_council_panel_cancel_proposal_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """契約測試：面板撤案流程（有條件限制）。"""
    gw = _FakeGatewayWithList()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    # 建案後撤案（未有投票前可行）
    p = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=10,
        target_id=20,
        amount=30,
        description="cancel test",
        attachment_url=None,
        snapshot_member_ids=[10, 11, 12],
    )
    ok = await svc.cancel_proposal(proposal_id=p.proposal_id)
    assert ok is True

    # 重新建案，投票後撤案應失敗
    p2 = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=10,
        target_id=20,
        amount=30,
        description="cancel test 2",
        attachment_url=None,
        snapshot_member_ids=[10, 11, 12],
    )
    await svc.vote(proposal_id=p2.proposal_id, voter_id=10, choice="approve")
    ok2 = await svc.cancel_proposal(proposal_id=p2.proposal_id)
    assert ok2 is False


@pytest.mark.contract
@pytest.mark.asyncio
async def test_council_panel_error_handling_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """契約測試：面板錯誤處理（權限不足、參數錯誤）。"""
    gw = _FakeGatewayWithList()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    # 測試金額必須為正整數
    with pytest.raises(ValueError, match="Amount must be a positive integer"):
        await svc.create_transfer_proposal(
            guild_id=100,
            proposer_id=10,
            target_id=20,
            amount=0,  # 無效金額
            description="invalid",
            attachment_url=None,
            snapshot_member_ids=[10, 11, 12],
        )

    # 測試未配置的 guild
    from src.bot.services.council_service import GovernanceNotConfiguredError

    with pytest.raises(GovernanceNotConfiguredError):
        await svc.get_config(guild_id=999)  # 未配置的 guild
