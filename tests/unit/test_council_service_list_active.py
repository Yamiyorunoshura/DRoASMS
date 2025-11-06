from __future__ import annotations

from typing import Any

import pytest
from faker import Faker

from src.bot.services.council_service import CouncilService
from tests.unit.test_council_service import _FakeConnection, _FakeGateway, _FakePool


class _FakeGatewayWithList(_FakeGateway):
    async def list_active_proposals(self, conn: Any) -> list[Any]:
        return [p for p in self._proposals.values() if p.status == "進行中"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_active_proposals_returns_in_progress(
    monkeypatch: pytest.MonkeyPatch, faker: Faker
) -> None:
    gw = _FakeGatewayWithList()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    guild_id = faker.random_int(min=1, max=1000000)
    council_role_id = faker.random_int(min=1, max=1000000)
    await svc.set_config(guild_id=guild_id, council_role_id=council_role_id)

    # 建兩筆：一筆進行中、一筆標記為已撤案
    proposer_id_1 = faker.random_int(min=1, max=1000000)
    target_id_1 = faker.random_int(min=1, max=1000000)
    proposer_id_2 = faker.random_int(min=1, max=1000000)
    target_id_2 = faker.random_int(min=1, max=1000000)
    snapshot_member_ids_1 = [faker.random_int(min=1, max=1000000) for _ in range(3)]
    snapshot_member_ids_2 = [faker.random_int(min=1, max=1000000) for _ in range(3)]

    p1 = await gw.create_proposal(
        conn,
        guild_id=guild_id,
        proposer_id=proposer_id_1,
        target_id=target_id_1,
        amount=faker.random_int(min=1, max=10000),
        description=faker.text(max_nb_chars=50),
        attachment_url=None,
        snapshot_member_ids=snapshot_member_ids_1,
    )
    p2 = await gw.create_proposal(
        conn,
        guild_id=guild_id,
        proposer_id=proposer_id_2,
        target_id=target_id_2,
        amount=faker.random_int(min=1, max=10000),
        description=faker.text(max_nb_chars=50),
        attachment_url=None,
        snapshot_member_ids=snapshot_member_ids_2,
    )
    # 標記第二筆為已撤案
    await gw.mark_status(conn, proposal_id=p2.proposal_id, status="已撤案")

    items = await svc.list_active_proposals()
    ids = {p.proposal_id for p in items}
    assert p1.proposal_id in ids and p2.proposal_id not in ids
