"""Integration tests for transfer proposal UI flow with department support."""

from __future__ import annotations

from typing import Any, cast

import pytest

from src.bot.services.council_service import CouncilService
from src.bot.services.department_registry import get_registry
from tests.unit.test_council_service import (
    _FakeConnection,
    _FakeGateway,
    _FakePool,
    _FakeTransferService,
)


class _FakeGatewayWithList(_FakeGateway):
    async def list_active_proposals(self, conn: Any) -> Any:
        return [p for p in self._proposals.values() if p.status == "進行中"]


@pytest.mark.asyncio
async def test_transfer_to_user_full_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """完整流程：選擇轉帳給使用者 → 選擇使用者 → 填寫資訊 → 建立提案 → 投票"""
    gw = _FakeGatewayWithList()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw, transfer_service=cast(Any, _FakeTransferService()))
    await svc.set_config(guild_id=100, council_role_id=200)

    # Step 1: Create proposal for user transfer
    p = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=10,
        target_id=20,  # User ID
        amount=100,
        description="測試轉帳給使用者",
        attachment_url="https://example.com/doc.pdf",
        snapshot_member_ids=[10, 11, 12],
        target_department_id=None,  # Explicitly None for user transfer
    )

    # Step 2: Verify proposal created correctly
    assert p.target_id == 20
    assert p.target_department_id is None
    assert p.amount == 100
    assert p.description == "測試轉帳給使用者"
    assert p.attachment_url == "https://example.com/doc.pdf"
    assert p.status == "進行中"

    # Step 3: Verify proposal appears in active list
    items = await svc.list_active_proposals()
    assert any(x.proposal_id == p.proposal_id for x in items)

    # Step 4: Vote on proposal
    _, status = await svc.vote(proposal_id=p.proposal_id, voter_id=10, choice="approve")
    assert status == "進行中"

    _, status = await svc.vote(proposal_id=p.proposal_id, voter_id=11, choice="approve")
    assert status in ("已執行", "執行失敗")


@pytest.mark.asyncio
async def test_transfer_to_department_full_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """完整流程：選擇轉帳給政府部門 → 選擇部門 → 填寫資訊 → 建立提案 → 投票"""
    gw = _FakeGatewayWithList()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw, transfer_service=cast(Any, _FakeTransferService()))
    await svc.set_config(guild_id=100, council_role_id=200)

    # Get department registry
    registry = get_registry()
    dept = registry.get_by_id("interior_affairs")
    assert dept is not None

    # Step 1: Create proposal for department transfer
    p = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=10,
        target_id=9500000000000001,  # Department account ID (derived)
        amount=500,
        description="測試轉帳給內政部",
        attachment_url=None,
        snapshot_member_ids=[10, 11, 12],
        target_department_id="interior_affairs",
    )

    # Step 2: Verify proposal created correctly
    assert p.target_department_id == "interior_affairs"
    assert p.amount == 500
    assert p.description == "測試轉帳給內政部"
    assert p.status == "進行中"

    # Step 3: Verify proposal appears in active list
    items = await svc.list_active_proposals()
    assert any(x.proposal_id == p.proposal_id for x in items)

    # Step 4: Verify department can be retrieved
    fetched_dept = registry.get_by_id(p.target_department_id)
    assert fetched_dept is not None
    assert fetched_dept.name == "內政部"

    # Step 5: Vote on proposal
    _, status = await svc.vote(proposal_id=p.proposal_id, voter_id=10, choice="approve")
    assert status == "進行中"

    _, status = await svc.vote(proposal_id=p.proposal_id, voter_id=11, choice="approve")
    assert status in ("已執行", "執行失敗")


@pytest.mark.asyncio
async def test_department_registry_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試部門註冊表整合：驗證所有部門可正確載入與查詢"""
    registry = get_registry()

    # Test: List all departments
    departments = registry.list_all()
    assert len(departments) >= 4  # At least 4 departments

    # Test: Get by ID
    dept = registry.get_by_id("interior_affairs")
    assert dept is not None
    assert dept.name == "內政部"
    assert dept.code == 1

    # Test: Get by name (backward compatibility)
    dept_by_name = registry.get_by_name("內政部")
    assert dept_by_name is not None
    assert dept_by_name.id == "interior_affairs"

    # Test: Get by code
    dept_by_code = registry.get_by_code(2)
    assert dept_by_code is not None
    assert dept_by_code.name == "財政部"

    # Test: ID to name mapping
    name = registry.get_name_by_id("central_bank")
    assert name == "中央銀行"

    # Test: Name to ID mapping
    dept_id = registry.get_id_by_name("國土安全部")
    assert dept_id == "homeland_security"
