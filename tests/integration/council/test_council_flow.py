from __future__ import annotations

from typing import Any, cast

import pytest

from src.bot.services.council_service import CouncilService
from tests.unit.test_council_service import (
    FakeConnection,
    FakeGateway,
    FakePool,
    FakeTransferService,
)


@pytest.mark.integration
@pytest.mark.timeout(60)
@pytest.mark.asyncio
async def test_propose_vote_execute_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """整合流程（假件）：建案→投票達標→執行成功。"""
    gw = FakeGateway()
    conn = FakeConnection(gw)
    pool = FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw, transfer_service=cast(Any, FakeTransferService()))
    await svc.set_config(guild_id=100, council_role_id=200)
    p = (
        await svc.create_transfer_proposal(
            guild_id=100,
            proposer_id=10,
            target_id=20,
            amount=30,
            description="integration-ok",
            attachment_url=None,
            snapshot_member_ids=[10, 11, 12],
        )
    ).unwrap()
    _, status = (await svc.vote(proposal_id=p.proposal_id, voter_id=10, choice="approve")).unwrap()
    assert status == "進行中"
    _, status = (await svc.vote(proposal_id=p.proposal_id, voter_id=11, choice="approve")).unwrap()
    assert status in ("已執行", "執行失敗")


@pytest.mark.asyncio
async def test_propose_vote_execute_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """整合流程（假件）：建案→投票達標→執行失敗。"""
    gw = FakeGateway()
    conn = FakeConnection(gw)
    pool = FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(
        gateway=gw, transfer_service=cast(Any, FakeTransferService(should_fail=True))
    )
    await svc.set_config(guild_id=1, council_role_id=2)
    p = (
        await svc.create_transfer_proposal(
            guild_id=1,
            proposer_id=100,
            target_id=200,
            amount=5,
            description="integration-fail",
            attachment_url=None,
            snapshot_member_ids=[100, 101, 102],
        )
    ).unwrap()
    _, status = (await svc.vote(proposal_id=p.proposal_id, voter_id=100, choice="approve")).unwrap()
    _, status = (await svc.vote(proposal_id=p.proposal_id, voter_id=101, choice="approve")).unwrap()
    assert status == "執行失敗"
