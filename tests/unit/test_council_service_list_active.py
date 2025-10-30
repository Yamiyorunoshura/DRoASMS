from __future__ import annotations

import pytest

from src.bot.services.council_service import CouncilService
from tests.unit.test_council_service import _FakeConnection, _FakeGateway, _FakePool


class _FakeGatewayWithList(_FakeGateway):
    async def list_active_proposals(self, conn):  # type: ignore[override]
        return [p for p in self._proposals.values() if p.status == "進行中"]


@pytest.mark.asyncio
async def test_list_active_proposals_returns_in_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    gw = _FakeGatewayWithList()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=10, council_role_id=20)

    # 建兩筆：一筆進行中、一筆標記為已撤案
    p1 = await gw.create_proposal(
        conn,
        guild_id=10,
        proposer_id=1,
        target_id=2,
        amount=5,
        description="a",
        attachment_url=None,
        snapshot_member_ids=[1, 2, 3],
    )
    p2 = await gw.create_proposal(
        conn,
        guild_id=10,
        proposer_id=3,
        target_id=4,
        amount=6,
        description="b",
        attachment_url=None,
        snapshot_member_ids=[3, 4, 5],
    )
    # 標記第二筆為已撤案
    await gw.mark_status(conn, proposal_id=p2.proposal_id, status="已撤案")

    items = await svc.list_active_proposals()
    ids = {p.proposal_id for p in items}
    assert p1.proposal_id in ids and p2.proposal_id not in ids
