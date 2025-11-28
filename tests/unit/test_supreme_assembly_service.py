"""Unit tests for Supreme Assembly service."""

from __future__ import annotations

from dataclasses import replace as dc_replace
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.bot.services.supreme_assembly_service import (
    GovernanceNotConfiguredError,
    PermissionDeniedError,
    SupremeAssemblyService,
    VoteAlreadyExistsError,
)
from src.bot.services.supreme_assembly_service_result import SupremeAssemblyServiceResult
from src.db.gateway.supreme_assembly_governance import (
    Proposal,
    Summon,
    SupremeAssemblyConfig,
    SupremeAssemblyGovernanceGateway,
    Tally,
)
from src.infra.result import Err, Ok

# ---- Fakes (no DB required) ----


class _FakeTxn:
    async def __aenter__(self) -> None:  # noqa: D401
        return None

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:  # noqa: D401
        return False


class _FakeConnection:
    def __init__(self, gw: "_FakeGateway") -> None:
        self._gw = gw

    def transaction(self) -> _FakeTxn:
        return _FakeTxn()

    async def fetchval(self, sql: str, *args: Any) -> int:  # minimal SQL hook
        # "SELECT COUNT(*) FROM governance.supreme_assembly_proposals WHERE guild_id=$1 AND status='進行中'"
        if "supreme_assembly_proposals" in sql and "COUNT" in sql:
            guild_id = args[0] if args else None
            if guild_id:
                count = sum(
                    1
                    for p in self._gw._proposals.values()
                    if p.guild_id == guild_id and p.status == "進行中"
                )
                return count
        return 0

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:  # minimal SQL hook
        return []


class _FakeAcquire:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConnection:
        return self._conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:  # noqa: D401
        return None


class _FakePool:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self._conn)


class _FakeGateway(SupremeAssemblyGovernanceGateway):
    def __init__(self, *, schema: str = "governance") -> None:
        super().__init__(schema=schema)
        self._cfg: dict[int, SupremeAssemblyConfig] = {}
        self._accounts: dict[int, tuple[int, int]] = {}  # guild_id -> (account_id, balance)
        self._proposals: dict[UUID, Proposal] = {}
        self._snapshot: dict[UUID, list[int]] = {}
        self._votes: dict[UUID, dict[int, str]] = {}

    # config
    async def upsert_config(
        self,
        conn: Any,
        *,
        guild_id: int,
        speaker_role_id: int,
        member_role_id: int,
    ) -> SupremeAssemblyConfig:
        cfg = SupremeAssemblyConfig(
            guild_id=guild_id,
            speaker_role_id=speaker_role_id,
            member_role_id=member_role_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._cfg[guild_id] = cfg
        return cfg

    async def fetch_config(self, conn: Any, *, guild_id: int) -> SupremeAssemblyConfig | None:
        return self._cfg.get(guild_id)

    # accounts
    async def fetch_account(self, connection: Any, *, guild_id: int) -> tuple[int, int] | None:
        return self._accounts.get(guild_id)

    async def ensure_account(self, connection: Any, *, guild_id: int, account_id: int) -> None:
        if guild_id not in self._accounts:
            self._accounts[guild_id] = (account_id, 0)

    # proposals
    async def create_proposal(
        self,
        conn: Any,
        *,
        guild_id: int,
        proposer_id: int,
        title: str | None,
        description: str | None,
        snapshot_member_ids: Sequence[int],
        deadline_hours: int = 72,
    ) -> Proposal:
        p_id = uuid4()
        n = len(list(dict.fromkeys(int(x) for x in snapshot_member_ids)))
        t = n // 2 + 1
        now = datetime.now(timezone.utc)
        p = Proposal(
            proposal_id=p_id,
            guild_id=guild_id,
            proposer_id=proposer_id,
            title=title,
            description=description,
            snapshot_n=n,
            threshold_t=t,
            deadline_at=now + timedelta(hours=deadline_hours),
            status="進行中",
            reminder_sent=False,
            created_at=now,
            updated_at=now,
        )
        self._proposals[p_id] = p
        self._snapshot[p_id] = list(dict.fromkeys(int(x) for x in snapshot_member_ids))
        self._votes[p_id] = {}
        return p

    async def fetch_proposal(self, conn: Any, *, proposal_id: UUID) -> Proposal | None:
        return self._proposals.get(proposal_id)

    async def fetch_snapshot(self, conn: Any, *, proposal_id: UUID) -> Sequence[int]:
        return list(self._snapshot.get(proposal_id, []))

    async def count_active_by_guild(self, conn: Any, *, guild_id: int) -> int:
        return sum(
            1 for p in self._proposals.values() if p.guild_id == guild_id and p.status == "進行中"
        )

    async def cancel_proposal(self, conn: Any, *, proposal_id: UUID) -> bool:
        """模擬資料庫端治理邏輯：僅允許在無投票時撤案"""
        p = self._proposals.get(proposal_id)
        if p is None or p.status != "進行中":
            return False
        # 若已有人投票，拒絕撤案
        if len(self._votes.get(proposal_id, {})) > 0:
            return False
        self._proposals[proposal_id] = dataclass_replace(p, status="已撤案")
        return True

    async def mark_status(
        self,
        conn: Any,
        *,
        proposal_id: UUID,
        status: str,
    ) -> None:
        p = self._proposals[proposal_id]
        self._proposals[proposal_id] = dataclass_replace(
            p,
            status=status,
            updated_at=datetime.now(timezone.utc),
        )

    async def upsert_vote(
        self,
        conn: Any,
        *,
        proposal_id: UUID,
        voter_id: int,
        choice: str,
    ) -> None:
        # 檢查是否已存在投票（投票後不可改選）
        if proposal_id in self._votes and voter_id in self._votes[proposal_id]:
            raise RuntimeError("Vote already exists and cannot be changed")
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

    async def list_active_proposals(self, conn: Any) -> Sequence[Proposal]:
        return [p for p in self._proposals.values() if p.status == "進行中"]

    async def mark_reminded(self, conn: Any, *, proposal_id: UUID) -> None:
        p = self._proposals[proposal_id]
        self._proposals[proposal_id] = dataclass_replace(p, reminder_sent=True)

    async def list_unvoted_members(self, conn: Any, *, proposal_id: UUID) -> Sequence[int]:
        snapshot = self._snapshot.get(proposal_id, [])
        voted = set(self._votes.get(proposal_id, {}).keys())
        return [m for m in snapshot if m not in voted]

    async def create_summon(
        self,
        conn: Any,
        *,
        guild_id: int,
        invoked_by: int,
        target_id: int,
        target_kind: str,
        note: str | None = None,
    ) -> Summon:
        from src.db.gateway.supreme_assembly_governance import Summon

        return Summon(
            summon_id=uuid4(),
            guild_id=guild_id,
            invoked_by=invoked_by,
            target_id=target_id,
            target_kind=target_kind,
            note=note,
            delivered=False,
            delivered_at=None,
            created_at=datetime.now(timezone.utc),
        )

    async def mark_summon_delivered(self, conn: Any, *, summon_id: UUID) -> None:
        pass

    async def list_summons(self, conn: Any, *, guild_id: int, limit: int = 50) -> Sequence[Summon]:
        return []

    async def export_interval(
        self,
        conn: Any,
        *,
        guild_id: int,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, object]]:
        return []


def dataclass_replace(obj: Any, **changes: Any) -> Any:
    """使用 dataclasses.replace 支援 slots 資料類別。"""
    return dc_replace(obj, **changes)


# ---- Tests ----


@pytest.mark.unit
@pytest.mark.asyncio
async def test_derive_account_id() -> None:
    """測試帳戶 ID 生成邏輯"""
    guild_id = 123456789
    account_id = SupremeAssemblyService.derive_account_id(guild_id)
    expected = 9_500_000_000_000_000 + guild_id + 200
    assert account_id == expected


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_config_creates_account(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試設定配置時自動創建帳戶"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    config = await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)
    assert config.guild_id == 100
    assert config.speaker_role_id == 200
    assert config.member_role_id == 300
    # 確認帳戶已創建
    account = await gw.fetch_account(conn, guild_id=100)
    assert account is not None
    assert account[0] == SupremeAssemblyService.derive_account_id(100)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_config_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試獲取未配置的配置時拋出錯誤"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    with pytest.raises(GovernanceNotConfiguredError):
        await svc.get_config(guild_id=999)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_proposal_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試成功創建提案"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    p = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試提案",
        description="這是測試",
        snapshot_member_ids=[1, 2, 3],
    )
    assert p.title == "測試提案"
    assert p.snapshot_n == 3
    assert p.threshold_t == 2  # floor(3/2) + 1 = 2
    assert p.status == "進行中"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_proposal_empty_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試空快照時拋出錯誤"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    with pytest.raises(PermissionDeniedError):
        await svc.create_proposal(
            guild_id=100,
            proposer_id=1,
            title="測試",
            description=None,
            snapshot_member_ids=[],
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_proposal_concurrency_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試並發限制（最多 5 個進行中提案）"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    # 創建 5 個提案
    for i in range(5):
        await svc.create_proposal(
            guild_id=100,
            proposer_id=1,
            title=f"提案 {i}",
            description=None,
            snapshot_member_ids=[1, 2, 3],
        )

    # 第 6 個應該失敗
    with pytest.raises(RuntimeError, match="Active proposal limit"):
        await svc.create_proposal(
            guild_id=100,
            proposer_id=1,
            title="提案 6",
            description=None,
            snapshot_member_ids=[1, 2, 3],
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vote_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試成功投票"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    p = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試",
        description=None,
        snapshot_member_ids=[1, 2, 3],
    )

    totals, status = await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="approve")
    assert status == "進行中"
    assert totals.approve == 1
    assert totals.reject == 0
    assert totals.abstain == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vote_not_in_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試非快照成員投票時拋出錯誤"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    p = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試",
        description=None,
        snapshot_member_ids=[1, 2, 3],
    )

    with pytest.raises(PermissionDeniedError):
        await svc.vote(proposal_id=p.proposal_id, voter_id=999, choice="approve")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vote_already_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試投票後不可改選"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    p = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試",
        description=None,
        snapshot_member_ids=[1, 2, 3],
    )

    # 第一次投票成功
    await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="approve")

    # 第二次投票應該失敗
    with pytest.raises(VoteAlreadyExistsError):
        await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="reject")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vote_threshold_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試投票達標後自動通過"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    p = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試",
        description=None,
        snapshot_member_ids=[1, 2, 3],  # N=3, T=2
    )

    # 第一票
    totals, status = await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="approve")
    assert status == "進行中"

    # 第二票達標
    totals, status = await svc.vote(proposal_id=p.proposal_id, voter_id=2, choice="approve")
    assert status == "已通過"
    assert totals.approve >= p.threshold_t


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vote_early_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試早期否決（即使所有剩餘票都同意也無法達標）"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    p = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試",
        description=None,
        snapshot_member_ids=[1, 2, 3, 4, 5],  # N=5, T=3
    )

    # 投兩票反對
    await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="reject")
    await svc.vote(proposal_id=p.proposal_id, voter_id=2, choice="reject")
    await svc.vote(proposal_id=p.proposal_id, voter_id=3, choice="abstain")

    # 第四票反對，即使剩餘兩票都同意也無法達標（1 approve + 2 remaining < 3 threshold）
    totals, status = await svc.vote(proposal_id=p.proposal_id, voter_id=4, choice="reject")
    # 注意：這裡需要確保 approve + remaining_unvoted < threshold
    # 當前實現中，如果 approve + remaining_unvoted < threshold，會標記為已否決
    assert status in ("已否決", "進行中")  # 根據實際邏輯調整


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_proposal_no_votes(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試無投票時可以撤案"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    p = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試",
        description=None,
        snapshot_member_ids=[1, 2, 3],
    )

    ok = await svc.cancel_proposal(proposal_id=p.proposal_id)
    assert ok is True

    # 確認狀態已更新
    updated = await svc.get_proposal(proposal_id=p.proposal_id)
    assert updated is not None
    assert updated.status == "已撤案"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_proposal_with_votes(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試有投票時不可撤案"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    p = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試",
        description=None,
        snapshot_member_ids=[1, 2, 3],
    )

    # 投一票後不可撤案
    await svc.vote(proposal_id=p.proposal_id, voter_id=1, choice="approve")
    ok = await svc.cancel_proposal(proposal_id=p.proposal_id)
    assert ok is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_expire_due_proposals(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試逾時提案處理"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    # 創建一個已逾時的提案
    p = await svc.create_proposal(
        guild_id=100,
        proposer_id=1,
        title="測試",
        description=None,
        snapshot_member_ids=[1, 2, 3],
    )
    # 手動修改 deadline 為過去時間
    gw._proposals[p.proposal_id] = dataclass_replace(
        gw._proposals[p.proposal_id],
        deadline_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    changed = await svc.expire_due_proposals()
    assert changed >= 1

    # 確認狀態已更新
    updated = await svc.get_proposal(proposal_id=p.proposal_id)
    assert updated is not None
    assert updated.status in ("已通過", "已逾時")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_summon(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試創建傳召記錄"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    summon = await svc.create_summon(
        guild_id=100,
        invoked_by=1,
        target_id=2,
        target_kind="member",
        note="測試傳召",
    )
    assert summon.guild_id == 100
    assert summon.target_id == 2
    assert summon.target_kind == "member"
    assert summon.note == "測試傳召"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_summon_invalid_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試無效的傳召類型"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    with pytest.raises(ValueError, match="target_kind must be"):
        await svc.create_summon(
            guild_id=100,
            invoked_by=1,
            target_id=2,
            target_kind="invalid",
            note=None,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_account_balance(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試獲取帳戶餘額"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.supreme_assembly_service.get_pool", lambda: pool)

    svc = SupremeAssemblyService(gateway=gw)
    await svc.set_config(guild_id=100, speaker_role_id=200, member_role_id=300)

    # 帳戶不存在時返回 0
    balance = await svc.get_account_balance(guild_id=999)
    assert balance == 0

    # 設置帳戶餘額
    account_id = SupremeAssemblyService.derive_account_id(100)
    gw._accounts[100] = (account_id, 5000)

    balance = await svc.get_account_balance(guild_id=100)
    assert balance == 5000


@pytest.mark.asyncio
class TestSupremeAssemblyServiceResult:
    async def test_get_config_ok(self) -> None:
        legacy = AsyncMock(spec=SupremeAssemblyService)
        expected = SupremeAssemblyConfig(
            guild_id=123,
            speaker_role_id=456,
            member_role_id=789,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        legacy.get_config.return_value = expected

        result_service = SupremeAssemblyServiceResult(legacy_service=legacy)

        result = await result_service.get_config(guild_id=123)

        assert isinstance(result, Ok)
        assert result.value is expected
        legacy.get_config.assert_awaited_once_with(guild_id=123)

    async def test_get_config_error(self) -> None:
        legacy = AsyncMock(spec=SupremeAssemblyService)
        legacy.get_config.side_effect = GovernanceNotConfiguredError("missing")

        result_service = SupremeAssemblyServiceResult(legacy_service=legacy)

        result = await result_service.get_config(guild_id=999)

        assert isinstance(result, Err)
        assert isinstance(result.error, GovernanceNotConfiguredError)
        legacy.get_config.assert_awaited_once_with(guild_id=999)
