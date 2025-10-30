from __future__ import annotations

from dataclasses import replace as dc_replace
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
from uuid import UUID, uuid4

import pytest

from src.bot.services.council_service import CouncilService, PermissionDeniedError
from src.db.gateway.council_governance import CouncilConfig, Proposal, Tally

# ---- Fakes (no DB required) ----


class _FakeTxn:
    async def __aenter__(self):  # noqa: D401
        return None

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
        return False


class _FakeConnection:
    def __init__(self, gw: "_FakeGateway") -> None:
        self._gw = gw

    def transaction(self) -> _FakeTxn:  # type: ignore[override]
        return _FakeTxn()

    async def fetchval(self, sql: str, proposal_id: UUID) -> int:  # minimal SQL hook
        # "SELECT COUNT(*) FROM governance.votes WHERE proposal_id=$1"
        if "FROM governance.votes" in sql:
            return len(self._gw._votes.get(proposal_id, {}))
        return 0

    async def fetch(self, sql: str, proposal_id: UUID) -> list[dict[str, Any]]:  # minimal SQL hook
        # SELECT voter_id FROM governance.votes WHERE proposal_id=$1
        items = []
        for vid in self._gw._votes.get(proposal_id, {}).keys():
            items.append({"voter_id": vid})
        return items


class _FakeAcquire:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConnection:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        return None


class _FakePool:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    def acquire(self) -> _FakeAcquire:  # type: ignore[override]
        return _FakeAcquire(self._conn)


class _FakeGateway:
    def __init__(self) -> None:
        self._cfg: dict[int, CouncilConfig] = {}
        self._proposals: dict[UUID, Proposal] = {}
        self._snapshot: dict[UUID, list[int]] = {}
        self._votes: dict[UUID, dict[int, str]] = {}

    # config
    async def upsert_config(
        self, conn: Any, *, guild_id: int, council_role_id: int, council_account_member_id: int
    ) -> CouncilConfig:
        cfg = CouncilConfig(
            guild_id=guild_id,
            council_role_id=council_role_id,
            council_account_member_id=council_account_member_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._cfg[guild_id] = cfg
        return cfg

    async def fetch_config(self, conn: Any, *, guild_id: int) -> CouncilConfig | None:
        return self._cfg.get(guild_id)

    # proposals
    async def create_proposal(
        self,
        conn: Any,
        *,
        guild_id: int,
        proposer_id: int,
        target_id: int,
        amount: int,
        description: str | None,
        attachment_url: str | None,
        snapshot_member_ids: Sequence[int],
        deadline_hours: int = 72,
    ) -> Proposal:
        p_id = uuid4()
        n = len(snapshot_member_ids)
        t = n // 2 + 1
        now = datetime.now(timezone.utc)
        p = Proposal(
            proposal_id=p_id,
            guild_id=guild_id,
            proposer_id=proposer_id,
            target_id=target_id,
            amount=amount,
            description=description,
            attachment_url=attachment_url,
            snapshot_n=n,
            threshold_t=t,
            deadline_at=now + timedelta(hours=deadline_hours),
            status="進行中",
            reminder_sent=False,
            created_at=now,
            updated_at=now,
        )
        self._proposals[p_id] = p
        self._snapshot[p_id] = list(dict.fromkeys(snapshot_member_ids))
        self._votes[p_id] = {}
        return p

    async def fetch_proposal(self, conn: Any, *, proposal_id: UUID) -> Proposal | None:
        return self._proposals.get(proposal_id)

    async def fetch_snapshot(self, conn: Any, *, proposal_id: UUID) -> Sequence[int]:
        return list(self._snapshot.get(proposal_id, []))

    async def cancel_proposal(self, conn: Any, *, proposal_id: UUID) -> bool:
        p = self._proposals.get(proposal_id)
        if p is None or p.status != "進行中":
            return False
        self._proposals[proposal_id] = dataclass_replace(p, status="已撤案")
        return True

    async def upsert_vote(
        self,
        conn: Any,
        *,
        proposal_id: UUID,
        voter_id: int,
        choice: str,
    ) -> None:
        self._votes.setdefault(proposal_id, {})[voter_id] = choice

    async def fetch_tally(self, conn: Any, *, proposal_id: UUID) -> Tally:
        votes = self._votes.get(proposal_id, {})
        counts = {"approve": 0, "reject": 0, "abstain": 0}
        for c in votes.values():
            counts[c] += 1
        return Tally(
            approve=counts["approve"],
            reject=counts["reject"],
            abstain=counts["abstain"],
            total_voted=sum(counts.values()),
        )

    async def mark_status(
        self,
        conn: Any,
        *,
        proposal_id: UUID,
        status: str,
        execution_tx_id: UUID | None = None,
        execution_error: str | None = None,
    ) -> None:
        p = self._proposals[proposal_id]
        self._proposals[proposal_id] = dataclass_replace(
            p,
            status=status,
            updated_at=datetime.now(timezone.utc),
        )

    async def fetch_votes_detail(
        self,
        conn: Any,
        *,
        proposal_id: UUID,
    ) -> Sequence[tuple[int, str]]:
        return list(self._votes.get(proposal_id, {}).items())

    async def list_due_proposals(self, conn: Any) -> Sequence[Proposal]:
        now = datetime.now(timezone.utc)
        return [
            p for p in self._proposals.values() if p.status == "進行中" and p.deadline_at <= now
        ]

    async def mark_reminded(self, conn: Any, *, proposal_id: UUID) -> None:
        p = self._proposals[proposal_id]
        self._proposals[proposal_id] = dataclass_replace(p, reminder_sent=True)


class _FakeTransferService:
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


def dataclass_replace(obj: Any, **changes: Any) -> Any:
    """使用 dataclasses.replace 支援 slots 資料類別。"""
    return dc_replace(obj, **changes)


# ---- Tests ----


@pytest.mark.asyncio
async def test_vote_threshold_executes_success(monkeypatch: pytest.MonkeyPatch) -> None:
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw, transfer_service=_FakeTransferService())
    # 設定 config（含 council 帳戶）
    await svc.set_config(guild_id=100, council_role_id=200)

    # 建案：N=3, T=2
    p = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=1,
        target_id=99,
        amount=50,
        description="test",
        attachment_url=None,
        snapshot_member_ids=[1, 2, 3],
    )

    # 兩票同意達標 → 立即執行，狀態最終應為已執行/執行失敗其中之一
    totals, status = await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="approve")
    assert status == "進行中"
    totals, status = await svc.vote(proposal_id=p.proposal_id, voter_id=2, choice="approve")
    assert status in ("已執行", "執行失敗")


@pytest.mark.asyncio
async def test_early_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw, transfer_service=_FakeTransferService())
    await svc.set_config(guild_id=100, council_role_id=200)
    p = await svc.create_transfer_proposal(
        guild_id=100,
        proposer_id=10,
        target_id=99,
        amount=25,
        description="rej",
        attachment_url=None,
        snapshot_member_ids=[1, 2, 3, 4, 5],  # N=5, T=3
    )

    await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="approve")
    await svc.vote(proposal_id=p.proposal_id, voter_id=2, choice="reject")
    await svc.vote(proposal_id=p.proposal_id, voter_id=3, choice="abstain")
    totals, status = await svc.vote(proposal_id=p.proposal_id, voter_id=4, choice="reject")
    assert status == "已否決"
    assert totals.approve == 1 and totals.reject == 2 and totals.abstain == 1


@pytest.mark.asyncio
async def test_cancel_proposal_rejected_after_first_vote(monkeypatch: pytest.MonkeyPatch) -> None:
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw, transfer_service=_FakeTransferService())
    await svc.set_config(guild_id=5, council_role_id=6)
    p = await svc.create_transfer_proposal(
        guild_id=5,
        proposer_id=11,
        target_id=12,
        amount=10,
        description="cancel",
        attachment_url=None,
        snapshot_member_ids=[11, 12, 13],
    )

    # 無票前可撤
    ok = await svc.cancel_proposal(proposal_id=p.proposal_id)
    assert ok is True

    # 重新建立一筆，投第一票後不可撤
    p = await svc.create_transfer_proposal(
        guild_id=5,
        proposer_id=11,
        target_id=12,
        amount=10,
        description="cancel2",
        attachment_url=None,
        snapshot_member_ids=[11, 12, 13],
    )
    await svc.vote(proposal_id=p.proposal_id, voter_id=11, choice="approve")
    ok = await svc.cancel_proposal(proposal_id=p.proposal_id)
    assert ok is False


@pytest.mark.asyncio
async def test_expire_due_proposals_exec_or_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)

    # 一筆會通過並執行、一筆逾時
    svc_ok = CouncilService(gateway=gw, transfer_service=_FakeTransferService())
    await svc_ok.set_config(guild_id=1, council_role_id=2)
    p1 = await svc_ok.create_transfer_proposal(
        guild_id=1,
        proposer_id=1,
        target_id=2,
        amount=5,
        description="ok",
        attachment_url=None,
        snapshot_member_ids=[1, 2, 3],
    )
    # 將 deadline 改成已過去
    gw._proposals[p1.proposal_id] = dataclass_replace(
        gw._proposals[p1.proposal_id], deadline_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    await svc_ok.vote(proposal_id=p1.proposal_id, voter_id=1, choice="approve")
    await svc_ok.vote(proposal_id=p1.proposal_id, voter_id=2, choice="approve")  # T 達成

    svc_to = CouncilService(gateway=gw, transfer_service=_FakeTransferService())
    p2 = await svc_to.create_transfer_proposal(
        guild_id=1,
        proposer_id=3,
        target_id=4,
        amount=9,
        description="timeout",
        attachment_url=None,
        snapshot_member_ids=[3, 4, 5],
    )
    gw._proposals[p2.proposal_id] = dataclass_replace(
        gw._proposals[p2.proposal_id], deadline_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )

    changed = await svc_ok.expire_due_proposals()
    assert changed >= 1
    # p1 最終不為進行中；若 scheduler 補執行，會標成已執行
    assert gw._proposals[p1.proposal_id].status in ("已通過", "已執行", "執行失敗")
    assert gw._proposals[p2.proposal_id].status == "已逾時"


@pytest.mark.asyncio
async def test_non_snapshot_voter_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service.get_pool", lambda: pool)
    svc = CouncilService(gateway=gw, transfer_service=_FakeTransferService())
    await svc.set_config(guild_id=7, council_role_id=8)
    p = await svc.create_transfer_proposal(
        guild_id=7,
        proposer_id=1,
        target_id=9,
        amount=1,
        description="x",
        attachment_url=None,
        snapshot_member_ids=[1, 2, 3],
    )
    with pytest.raises(PermissionDeniedError):
        await svc.vote(proposal_id=p.proposal_id, voter_id=999, choice="approve")
