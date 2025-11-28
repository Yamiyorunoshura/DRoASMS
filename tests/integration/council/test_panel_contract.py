from __future__ import annotations

from typing import Any

import pytest

from src.bot.services.council_service import CouncilService
from tests.unit.test_council_service import (
    FakeConnection,
    FakeGateway,
    FakePool,
)


class _FakeGatewayWithList(FakeGateway):
    async def list_active_proposals(self, conn: Any) -> Any:
        return [p for p in self._proposals.values() if p.status == "進行中"]


@pytest.mark.integration
@pytest.mark.timeout(60)
@pytest.mark.asyncio
async def test_panel_contract_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """合約測試（服務層）：建案→面板列出→投票→撤案（條件）。"""
    gw = _FakeGatewayWithList()
    conn = FakeConnection(gw)
    pool = FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    # 建案
    p = (
        await svc.create_transfer_proposal(
            guild_id=100,
            proposer_id=10,
            target_id=20,
            amount=30,
            description="panel",
            attachment_url=None,
            snapshot_member_ids=[10, 11, 12],
        )
    ).unwrap()

    # 面板列出（list_active_proposals）
    items = (await svc.list_active_proposals()).unwrap()
    assert any(x.proposal_id == p.proposal_id for x in items)

    # 撤案在未有投票前可行
    ok = (await svc.cancel_proposal(proposal_id=p.proposal_id)).unwrap()
    assert ok is True

    # 重新建一筆，再投第一票後撤案應失敗
    p2 = (
        await svc.create_transfer_proposal(
            guild_id=100,
            proposer_id=10,
            target_id=20,
            amount=30,
            description="panel2",
            attachment_url=None,
            snapshot_member_ids=[10, 11, 12],
        )
    ).unwrap()
    await svc.vote(proposal_id=p2.proposal_id, voter_id=10, choice="approve")
    ok2 = (await svc.cancel_proposal(proposal_id=p2.proposal_id)).unwrap()
    assert ok2 is False
