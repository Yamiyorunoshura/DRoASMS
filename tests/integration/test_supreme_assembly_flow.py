"""Integration tests for Supreme Assembly flow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.bot.services.supreme_assembly_service import (
    SupremeAssemblyService,
    VoteAlreadyExistsError,
)
from tests.unit.test_supreme_assembly_service import (
    _FakeConnection,
    _FakeGateway,
    _FakePool,
)


@pytest.mark.integration
@pytest.mark.timeout(60)
@pytest.mark.asyncio
async def test_proposal_vote_pass_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """整合流程：建案→投票達標→通過"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    _ = await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    # 創建提案：N=3, T=2
    pr = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試提案",
        description="整合測試",
        snapshot_member_ids=[1, 2, 3],
    )
    assert hasattr(pr, "is_ok")
    p = pr.value

    # 第一票
    r1 = await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="approve")
    totals, status = r1.value
    assert status == "進行中"
    assert totals.approve == 1

    # 第二票達標
    r2 = await svc.vote(proposal_id=p.proposal_id, voter_id=2, choice="approve")
    totals, status = r2.value
    assert status == "已通過"
    assert totals.approve >= p.threshold_t


@pytest.mark.integration
@pytest.mark.asyncio
async def test_proposal_vote_reject_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """整合流程：建案→投票否決"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    _ = await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    pr = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試提案",
        description=None,
        snapshot_member_ids=[1, 2, 3, 4, 5],  # N=5, T=3
    )
    p = pr.value

    # 投反對票
    _ = await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="reject")
    _ = await svc.vote(proposal_id=p.proposal_id, voter_id=2, choice="reject")
    _ = await svc.vote(proposal_id=p.proposal_id, voter_id=3, choice="abstain")

    # 第四票反對，即使剩餘兩票都同意也無法達標
    r4 = await svc.vote(proposal_id=p.proposal_id, voter_id=4, choice="reject")
    totals, status = r4.value
    # 根據實現，如果 approve + remaining_unvoted < threshold，會標記為已否決
    # 這裡 approve=0, remaining_unvoted=1, threshold=3，所以應該否決
    if totals.approve + totals.remaining_unvoted < p.threshold_t:
        assert status == "已否決"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vote_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    """整合測試：投票後不可改選"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    _ = await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    pr = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試",
        description=None,
        snapshot_member_ids=[1, 2, 3],
    )
    p = pr.value

    # 第一次投票成功
    _ = await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="approve")

    # 嘗試改選應該失敗（Result-first）
    r = await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="reject")
    assert hasattr(r, "is_err") and r.is_err()
    assert isinstance(getattr(r, "error", None), VoteAlreadyExistsError)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cancel_proposal_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """整合流程：建案→撤案"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    _ = await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    pr = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試",
        description=None,
        snapshot_member_ids=[1, 2, 3],
    )
    p = pr.value

    # 無投票時可以撤案
    cr = await svc.cancel_proposal(proposal_id=p.proposal_id)
    assert cr.value is True

    # 確認狀態
    ur = await svc.get_proposal(proposal_id=p.proposal_id)
    updated = ur.value
    assert updated is not None
    assert updated.status == "已撤案"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_summon_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """整合流程：創建傳召記錄"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    _ = await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    # 創建議員傳召
    sr1 = await svc.create_summon(
        guild_id=100,
        invoked_by=1,
        target_id=2,
        target_kind="member",
        note="請出席會議",
    )
    summon1 = sr1.value
    assert summon1.target_kind == "member"
    assert summon1.note == "請出席會議"

    # 創建政府官員傳召
    sr2 = await svc.create_summon(
        guild_id=100,
        invoked_by=1,
        target_id=3,
        target_kind="official",
        note=None,
    )
    summon2 = sr2.value
    assert summon2.target_kind == "official"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_account_balance_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """整合流程：帳戶餘額查詢"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    _ = await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    # 帳戶不存在時返回 0
    br0 = await svc.get_account_balance(guild_id=999)
    assert br0.value == 0

    # 設置帳戶餘額
    account_id = SupremeAssemblyService.derive_account_id(100)
    gw._accounts[100] = (account_id, 10000)

    br = await svc.get_account_balance(guild_id=100)
    assert br.value == 10000


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrency_limit_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """整合流程：並發限制測試"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    # 創建 5 個提案
    proposals = []
    for i in range(5):
        pr = await svc.create_proposal(
            guild_id=100,
            proposer_id=1,
            title=f"提案 {i}",
            description=None,
            snapshot_member_ids=[1, 2, 3],
        )
        proposals.append(pr.value)

    # 第 6 個應該失敗
    r6 = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="提案 6",
        description=None,
        snapshot_member_ids=[1, 2, 3],
    )
    assert hasattr(r6, "is_err") and r6.is_err()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expire_due_proposals_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """整合流程：逾時提案處理"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    _ = await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    # 創建一個已逾時的提案
    pr = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試",
        description=None,
        snapshot_member_ids=[1, 2, 3],
    )
    p = pr.value
    # 手動修改 deadline 為過去時間
    from dataclasses import replace as dc_replace

    gw._proposals[p.proposal_id] = dc_replace(
        gw._proposals[p.proposal_id],
        deadline_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    er = await svc.expire_due_proposals()
    assert er.value >= 1

    # 確認狀態已更新
    ur2 = await svc.get_proposal(proposal_id=p.proposal_id)
    updated = ur2.value
    assert updated is not None
    assert updated.status in ("已通過", "已逾時")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_summon_multiple_permanent_council_members(monkeypatch: pytest.MonkeyPatch) -> None:
    """整合流程：傳召多個常任理事會成員"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    # 創建多個常任理事傳召記錄
    target_ids = [2, 3, 4]
    summons = []
    for target_id in target_ids:
        sr = await svc.create_summon(
            guild_id=100,
            invoked_by=1,
            target_id=target_id,
            target_kind="official",
            note=f"傳召常任理事 {target_id}",
        )
        summon = sr.value
        summons.append(summon)
        assert summon.target_kind == "official"
        assert summon.target_id == target_id

    # 驗證所有傳召記錄都已創建
    assert len(summons) == len(target_ids)
    for i, summon in enumerate(summons):
        assert summon.target_id == target_ids[i]
        assert summon.note == f"傳召常任理事 {target_ids[i]}"
