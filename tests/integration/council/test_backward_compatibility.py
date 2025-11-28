"""Contract tests: Ensure backward compatibility with old proposals."""

from __future__ import annotations

from typing import Any

import pytest

from src.bot.services.council_service import CouncilService
from src.bot.services.department_registry import get_registry
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
async def test_old_proposal_without_department_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """契約測試：舊提案（無 target_department_id）仍可正常顯示與操作"""
    gw = _FakeGatewayWithList()
    conn = FakeConnection(gw)
    pool = FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    # Create old-style proposal (without target_department_id)
    p = (
        await svc.create_transfer_proposal(
            guild_id=100,
            proposer_id=10,
            target_id=20,
            amount=50,
            description="舊提案",
            attachment_url=None,
            snapshot_member_ids=[10, 11, 12],
            # Explicitly not providing target_department_id to simulate old proposal
        )
    ).unwrap()

    # Verify old proposal works correctly
    assert p.target_id == 20
    assert p.target_department_id is None  # Old proposals have None
    assert p.status == "進行中"

    # Verify proposal can be fetched
    fetched = (await svc.get_proposal(proposal_id=p.proposal_id)).unwrap()
    assert fetched is not None
    assert fetched.target_id == 20
    assert fetched.target_department_id is None

    # Verify proposal appears in active list
    items = (await svc.list_active_proposals()).unwrap()
    assert any(x.proposal_id == p.proposal_id for x in items)

    # Verify voting still works
    _, status = (await svc.vote(proposal_id=p.proposal_id, voter_id=10, choice="approve")).unwrap()
    assert status == "進行中"

    # Verify cancellation still works (before votes)
    # First cancel current proposal
    await svc.cancel_proposal(proposal_id=p.proposal_id)

    # Create another proposal and verify cancellation after vote fails
    p2 = (
        await svc.create_transfer_proposal(
            guild_id=100,
            proposer_id=10,
            target_id=20,
            amount=50,
            description="舊提案2",
            attachment_url=None,
            snapshot_member_ids=[10, 11, 12],
        )
    ).unwrap()
    await svc.vote(proposal_id=p2.proposal_id, voter_id=10, choice="approve")
    ok = (await svc.cancel_proposal(proposal_id=p2.proposal_id)).unwrap()
    assert ok is False  # Cannot cancel after vote


@pytest.mark.asyncio
async def test_mixed_old_and_new_proposals(monkeypatch: pytest.MonkeyPatch) -> None:
    """契約測試：舊提案與新提案（有 target_department_id）可共存"""
    gw = _FakeGatewayWithList()
    conn = FakeConnection(gw)
    pool = FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    registry = get_registry()
    dept = registry.get_by_id("finance")
    assert dept is not None

    # Create old-style proposal
    p_old = (
        await svc.create_transfer_proposal(
            guild_id=100,
            proposer_id=10,
            target_id=20,
            amount=100,
            description="舊提案",
            attachment_url=None,
            snapshot_member_ids=[10, 11, 12],
        )
    ).unwrap()

    # Create new-style proposal with department
    p_new = (
        await svc.create_transfer_proposal(
            guild_id=100,
            proposer_id=10,
            target_id=9500000000000002,  # Finance department account ID
            amount=200,
            description="新提案（部門）",
            attachment_url=None,
            snapshot_member_ids=[10, 11, 12],
            target_department_id="finance",
        )
    ).unwrap()

    # Verify both proposals exist and are different
    assert p_old.proposal_id != p_new.proposal_id
    assert p_old.target_department_id is None
    assert p_new.target_department_id == "finance"

    # Verify both appear in active list
    items = (await svc.list_active_proposals()).unwrap()
    assert any(x.proposal_id == p_old.proposal_id for x in items)
    assert any(x.proposal_id == p_new.proposal_id for x in items)

    # Verify both can be fetched
    fetched_old = (await svc.get_proposal(proposal_id=p_old.proposal_id)).unwrap()
    fetched_new = (await svc.get_proposal(proposal_id=p_new.proposal_id)).unwrap()

    assert fetched_old is not None
    assert fetched_new is not None
    assert fetched_old.target_department_id is None
    assert fetched_new.target_department_id == "finance"


@pytest.mark.asyncio
async def test_proposal_display_formatting() -> None:
    """契約測試：驗證提案顯示格式化函式正確處理舊提案與新提案"""
    from datetime import datetime, timezone
    from uuid import uuid4

    from src.bot.commands.council import (
        _format_proposal_title,  # type: ignore[attr-defined]  # noqa: SLF001
    )
    from src.db.gateway.council_governance import Proposal

    # Test old proposal (user target)
    p_old = Proposal(
        proposal_id=uuid4(),
        guild_id=100,
        proposer_id=10,
        target_id=20,
        amount=100,
        description="舊提案",
        attachment_url=None,
        snapshot_n=3,
        threshold_t=2,
        deadline_at=datetime.now(timezone.utc),
        status="進行中",
        reminder_sent=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        target_department_id=None,
    )

    title_old = _format_proposal_title(p_old)
    assert "<@20>" in title_old  # Should show user mention

    # Test new proposal (department target)
    p_new = Proposal(
        proposal_id=uuid4(),
        guild_id=100,
        proposer_id=10,
        target_id=9500000000000001,
        amount=200,
        description="新提案",
        attachment_url=None,
        snapshot_n=3,
        threshold_t=2,
        deadline_at=datetime.now(timezone.utc),
        status="進行中",
        reminder_sent=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        target_department_id="interior_affairs",
    )

    title_new = _format_proposal_title(p_new)
    assert "內政部" in title_new  # Should show department name
    assert "<@9500000000000001>" not in title_new  # Should not show account ID
