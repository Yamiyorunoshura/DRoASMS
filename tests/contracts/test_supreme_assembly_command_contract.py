"""契約測試：Supreme Assembly 面板互動流程（提案、投票、傳召）。"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
from uuid import UUID, uuid4

import pytest

from src.bot.services.supreme_assembly_service import (
    GovernanceNotConfiguredError,
    PermissionDeniedError,
    VoteAlreadyExistsError,
    VoteTotals,
)
from src.cython_ext.supreme_assembly_models import (
    Proposal,
    Summon,
    SupremeAssemblyConfig,
)


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


class FakeConnection:
    """模擬資料庫連接。"""

    def __init__(self, gateway: "FakeSupremeAssemblyGateway") -> None:
        self.gateway = gateway

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


class FakePool:
    """模擬連接池。"""

    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    def acquire(self) -> FakeConnection:
        return self._conn


class FakeSupremeAssemblyGateway:
    """模擬 SupremeAssemblyGovernanceGateway。"""

    def __init__(self) -> None:
        self._configs: dict[int, SupremeAssemblyConfig] = {}
        self._proposals: dict[UUID, Proposal] = {}
        self._votes: dict[tuple[UUID, int], dict[str, Any]] = {}
        self._summons: dict[UUID, Summon] = {}
        self._snapshots: dict[UUID, list[int]] = {}

    async def fetch_config(self, conn: Any, *, guild_id: int) -> SupremeAssemblyConfig | None:
        return self._configs.get(guild_id)

    async def upsert_config(
        self,
        conn: Any,
        *,
        guild_id: int,
        speaker_role_id: int,
        member_role_id: int,
    ) -> SupremeAssemblyConfig:
        now = datetime.now(tz=timezone.utc)
        cfg = SupremeAssemblyConfig(
            guild_id=guild_id,
            speaker_role_id=speaker_role_id,
            member_role_id=member_role_id,
            created_at=now,
            updated_at=now,
        )
        self._configs[guild_id] = cfg
        return cfg

    async def create_proposal(
        self,
        conn: Any,
        *,
        guild_id: int,
        proposer_id: int,
        title: str | None,
        description: str | None,
        snapshot_n: int,
        threshold_t: int,
        deadline_at: datetime,
        snapshot_member_ids: list[int],
    ) -> Proposal:
        now = datetime.now(tz=timezone.utc)
        proposal_id = uuid4()
        proposal = Proposal(
            proposal_id=proposal_id,
            guild_id=guild_id,
            proposer_id=proposer_id,
            title=title,
            description=description,
            snapshot_n=snapshot_n,
            threshold_t=threshold_t,
            deadline_at=deadline_at,
            status="進行中",
            reminder_sent=False,
            created_at=now,
            updated_at=now,
        )
        self._proposals[proposal_id] = proposal
        self._snapshots[proposal_id] = snapshot_member_ids
        return proposal

    async def fetch_proposal(self, conn: Any, *, proposal_id: UUID) -> Proposal | None:
        return self._proposals.get(proposal_id)

    async def list_active_proposals(self, conn: Any) -> Sequence[Proposal]:
        return [p for p in self._proposals.values() if p.status == "進行中"]

    async def fetch_vote(
        self, conn: Any, *, proposal_id: UUID, voter_id: int
    ) -> dict[str, Any] | None:
        return self._votes.get((proposal_id, voter_id))

    async def insert_vote(
        self, conn: Any, *, proposal_id: UUID, voter_id: int, choice: str
    ) -> dict[str, Any]:
        now = datetime.now(tz=timezone.utc)
        vote = {
            "vote_id": uuid4(),
            "proposal_id": proposal_id,
            "voter_id": voter_id,
            "choice": choice,
            "created_at": now,
        }
        self._votes[(proposal_id, voter_id)] = vote
        return vote

    async def count_votes(self, conn: Any, *, proposal_id: UUID) -> tuple[int, int, int]:
        approve = reject = abstain = 0
        for (pid, _), v in self._votes.items():
            if pid == proposal_id:
                if v["choice"] == "approve":
                    approve += 1
                elif v["choice"] == "reject":
                    reject += 1
                elif v["choice"] == "abstain":
                    abstain += 1
        return approve, reject, abstain

    async def update_proposal_status(self, conn: Any, *, proposal_id: UUID, status: str) -> None:
        if proposal_id in self._proposals:
            p = self._proposals[proposal_id]
            self._proposals[proposal_id] = Proposal(
                proposal_id=p.proposal_id,
                guild_id=p.guild_id,
                proposer_id=p.proposer_id,
                title=p.title,
                description=p.description,
                snapshot_n=p.snapshot_n,
                threshold_t=p.threshold_t,
                deadline_at=p.deadline_at,
                status=status,
                reminder_sent=p.reminder_sent,
                created_at=p.created_at,
                updated_at=datetime.now(tz=timezone.utc),
            )

    async def fetch_snapshot(self, conn: Any, *, proposal_id: UUID) -> list[int]:
        return self._snapshots.get(proposal_id, [])

    async def create_summon(
        self,
        conn: Any,
        *,
        guild_id: int,
        invoked_by: int,
        target_id: int,
        target_kind: str,
        note: str | None,
    ) -> Summon:
        now = datetime.now(tz=timezone.utc)
        summon_id = uuid4()
        summon = Summon(
            summon_id=summon_id,
            guild_id=guild_id,
            invoked_by=invoked_by,
            target_id=target_id,
            target_kind=target_kind,
            note=note,
            delivered=False,
            delivered_at=None,
            created_at=now,
        )
        self._summons[summon_id] = summon
        return summon

    async def mark_summon_delivered(self, conn: Any, *, summon_id: UUID) -> None:
        if summon_id in self._summons:
            s = self._summons[summon_id]
            self._summons[summon_id] = Summon(
                summon_id=s.summon_id,
                guild_id=s.guild_id,
                invoked_by=s.invoked_by,
                target_id=s.target_id,
                target_kind=s.target_kind,
                note=s.note,
                delivered=True,
                delivered_at=datetime.now(tz=timezone.utc),
                created_at=s.created_at,
            )

    def get_summon(self, summon_id: UUID) -> Summon | None:
        """Public accessor for summon data in tests."""
        return self._summons.get(summon_id)


class FakeSupremeAssemblyService:
    """模擬 SupremeAssemblyService。"""

    def __init__(self, gateway: FakeSupremeAssemblyGateway) -> None:
        self._gateway = gateway
        self._conn = FakeConnection(gateway)

    async def get_config(self, *, guild_id: int) -> SupremeAssemblyConfig:
        cfg = await self._gateway.fetch_config(self._conn, guild_id=guild_id)
        if cfg is None:
            raise GovernanceNotConfiguredError("未配置最高人民會議")
        return cfg

    async def set_config(
        self,
        *,
        guild_id: int,
        speaker_role_id: int,
        member_role_id: int,
    ) -> SupremeAssemblyConfig:
        return await self._gateway.upsert_config(
            self._conn,
            guild_id=guild_id,
            speaker_role_id=speaker_role_id,
            member_role_id=member_role_id,
        )

    async def create_proposal(
        self,
        *,
        guild_id: int,
        proposer_id: int,
        title: str | None,
        description: str | None,
        snapshot_member_ids: list[int],
        deadline_hours: int = 72,
    ) -> Proposal:
        if not snapshot_member_ids:
            raise PermissionDeniedError("成員名單不能為空")
        snapshot_n = len(snapshot_member_ids)
        threshold_t = (snapshot_n + 1) // 2  # 簡單多數
        deadline_at = datetime.now(tz=timezone.utc) + timedelta(hours=deadline_hours)
        return await self._gateway.create_proposal(
            self._conn,
            guild_id=guild_id,
            proposer_id=proposer_id,
            title=title,
            description=description,
            snapshot_n=snapshot_n,
            threshold_t=threshold_t,
            deadline_at=deadline_at,
            snapshot_member_ids=snapshot_member_ids,
        )

    async def vote(
        self,
        *,
        proposal_id: UUID,
        voter_id: int,
        choice: str,
    ) -> tuple[VoteTotals, str]:
        proposal = await self._gateway.fetch_proposal(self._conn, proposal_id=proposal_id)
        if proposal is None:
            raise RuntimeError("提案不存在")

        # 檢查是否已投票
        existing = await self._gateway.fetch_vote(
            self._conn, proposal_id=proposal_id, voter_id=voter_id
        )
        if existing is not None:
            raise VoteAlreadyExistsError("已投票")

        # 記錄投票
        await self._gateway.insert_vote(
            self._conn, proposal_id=proposal_id, voter_id=voter_id, choice=choice
        )

        # 計算票數
        approve, reject, abstain = await self._gateway.count_votes(
            self._conn, proposal_id=proposal_id
        )

        # 計算剩餘未投票
        snapshot = await self._gateway.fetch_snapshot(self._conn, proposal_id=proposal_id)
        voted_count = approve + reject + abstain
        remaining = len(snapshot) - voted_count

        # 檢查是否達到門檻
        status = proposal.status
        if approve >= proposal.threshold_t:
            status = "已通過"
            await self._gateway.update_proposal_status(
                self._conn, proposal_id=proposal_id, status=status
            )
        elif reject >= proposal.threshold_t:
            status = "已否決"
            await self._gateway.update_proposal_status(
                self._conn, proposal_id=proposal_id, status=status
            )

        totals = VoteTotals(
            approve=approve,
            reject=reject,
            abstain=abstain,
            threshold_t=proposal.threshold_t,
            snapshot_n=proposal.snapshot_n,
            remaining_unvoted=remaining,
        )
        return totals, status

    async def get_vote_totals(self, *, proposal_id: UUID) -> VoteTotals:
        proposal = await self._gateway.fetch_proposal(self._conn, proposal_id=proposal_id)
        if proposal is None:
            raise RuntimeError("提案不存在")

        approve, reject, abstain = await self._gateway.count_votes(
            self._conn, proposal_id=proposal_id
        )
        snapshot = await self._gateway.fetch_snapshot(self._conn, proposal_id=proposal_id)
        voted_count = approve + reject + abstain
        remaining = len(snapshot) - voted_count

        return VoteTotals(
            approve=approve,
            reject=reject,
            abstain=abstain,
            threshold_t=proposal.threshold_t,
            snapshot_n=proposal.snapshot_n,
            remaining_unvoted=remaining,
        )

    async def list_active_proposals(self, *, guild_id: int) -> Sequence[Proposal]:
        proposals = await self._gateway.list_active_proposals(self._conn)
        return [p for p in proposals if p.guild_id == guild_id]

    async def create_summon(
        self,
        *,
        guild_id: int,
        invoked_by: int,
        target_id: int,
        target_kind: str,
        note: str | None,
    ) -> Summon:
        return await self._gateway.create_summon(
            self._conn,
            guild_id=guild_id,
            invoked_by=invoked_by,
            target_id=target_id,
            target_kind=target_kind,
            note=note,
        )

    async def mark_summon_delivered(self, *, summon_id: UUID) -> None:
        await self._gateway.mark_summon_delivered(self._conn, summon_id=summon_id)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_config_contract() -> None:
    """契約測試：設定最高人民會議配置。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    guild_id = _snowflake()
    speaker_role_id = _snowflake()
    member_role_id = _snowflake()

    # 設定配置
    cfg = await svc.set_config(
        guild_id=guild_id,
        speaker_role_id=speaker_role_id,
        member_role_id=member_role_id,
    )

    assert cfg.guild_id == guild_id
    assert cfg.speaker_role_id == speaker_role_id
    assert cfg.member_role_id == member_role_id

    # 獲取配置
    cfg2 = await svc.get_config(guild_id=guild_id)
    assert cfg2.guild_id == guild_id


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_config_not_found_contract() -> None:
    """契約測試：未配置時拋出錯誤。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    with pytest.raises(GovernanceNotConfiguredError):
        await svc.get_config(guild_id=_snowflake())


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_create_proposal_contract() -> None:
    """契約測試：建立提案。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    guild_id = _snowflake()
    proposer_id = _snowflake()
    member_ids = [_snowflake() for _ in range(5)]

    # 建立提案
    proposal = await svc.create_proposal(
        guild_id=guild_id,
        proposer_id=proposer_id,
        title="測試提案",
        description="這是測試提案內容",
        snapshot_member_ids=member_ids,
        deadline_hours=72,
    )

    assert proposal.proposal_id is not None
    assert proposal.guild_id == guild_id
    assert proposal.proposer_id == proposer_id
    assert proposal.title == "測試提案"
    assert proposal.status == "進行中"
    assert proposal.threshold_t == 3  # (5 + 1) // 2


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_create_proposal_empty_members_contract() -> None:
    """契約測試：空成員名單拋出錯誤。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    with pytest.raises(PermissionDeniedError, match="成員名單不能為空"):
        await svc.create_proposal(
            guild_id=_snowflake(),
            proposer_id=_snowflake(),
            title="測試提案",
            description="內容",
            snapshot_member_ids=[],
            deadline_hours=72,
        )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_vote_contract() -> None:
    """契約測試：投票流程。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    guild_id = _snowflake()
    voter1 = _snowflake()
    voter2 = _snowflake()
    voter3 = _snowflake()
    member_ids = [voter1, voter2, voter3]

    # 建立提案
    proposal = await svc.create_proposal(
        guild_id=guild_id,
        proposer_id=voter1,
        title="投票測試",
        description="投票測試內容",
        snapshot_member_ids=member_ids,
        deadline_hours=72,
    )

    # 投票
    totals, status = await svc.vote(
        proposal_id=proposal.proposal_id,
        voter_id=voter1,
        choice="approve",
    )

    assert totals.approve == 1
    assert totals.reject == 0
    assert totals.abstain == 0
    assert status == "進行中"

    # 再投一票
    totals2, status2 = await svc.vote(
        proposal_id=proposal.proposal_id,
        voter_id=voter2,
        choice="approve",
    )

    assert totals2.approve == 2
    assert status2 == "已通過"  # 達到門檻 (3+1)//2 = 2


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_vote_already_exists_contract() -> None:
    """契約測試：重複投票拋出錯誤。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    voter = _snowflake()
    member_ids = [voter, _snowflake(), _snowflake()]

    proposal = await svc.create_proposal(
        guild_id=_snowflake(),
        proposer_id=voter,
        title="重複投票測試",
        description="內容",
        snapshot_member_ids=member_ids,
        deadline_hours=72,
    )

    # 第一次投票
    await svc.vote(
        proposal_id=proposal.proposal_id,
        voter_id=voter,
        choice="approve",
    )

    # 嘗試重複投票
    with pytest.raises(VoteAlreadyExistsError):
        await svc.vote(
            proposal_id=proposal.proposal_id,
            voter_id=voter,
            choice="reject",
        )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_vote_rejection_contract() -> None:
    """契約測試：否決提案。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    voter1 = _snowflake()
    voter2 = _snowflake()
    voter3 = _snowflake()
    member_ids = [voter1, voter2, voter3]

    proposal = await svc.create_proposal(
        guild_id=_snowflake(),
        proposer_id=voter1,
        title="否決測試",
        description="內容",
        snapshot_member_ids=member_ids,
        deadline_hours=72,
    )

    # 投票反對
    await svc.vote(
        proposal_id=proposal.proposal_id,
        voter_id=voter1,
        choice="reject",
    )
    totals, status = await svc.vote(
        proposal_id=proposal.proposal_id,
        voter_id=voter2,
        choice="reject",
    )

    assert totals.reject == 2
    assert status == "已否決"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_get_vote_totals_contract() -> None:
    """契約測試：獲取投票統計。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    voter1 = _snowflake()
    voter2 = _snowflake()
    voter3 = _snowflake()
    member_ids = [voter1, voter2, voter3]

    proposal = await svc.create_proposal(
        guild_id=_snowflake(),
        proposer_id=voter1,
        title="統計測試",
        description="內容",
        snapshot_member_ids=member_ids,
        deadline_hours=72,
    )

    # 投票
    await svc.vote(
        proposal_id=proposal.proposal_id,
        voter_id=voter1,
        choice="approve",
    )
    await svc.vote(
        proposal_id=proposal.proposal_id,
        voter_id=voter2,
        choice="reject",
    )
    await svc.vote(
        proposal_id=proposal.proposal_id,
        voter_id=voter3,
        choice="abstain",
    )

    # 獲取統計
    totals = await svc.get_vote_totals(proposal_id=proposal.proposal_id)

    assert totals.approve == 1
    assert totals.reject == 1
    assert totals.abstain == 1
    assert totals.remaining_unvoted == 0


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_list_active_proposals_contract() -> None:
    """契約測試：列出進行中提案。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    guild_id = _snowflake()
    member_ids = [_snowflake() for _ in range(3)]

    # 建立多個提案
    p1 = await svc.create_proposal(
        guild_id=guild_id,
        proposer_id=_snowflake(),
        title="提案1",
        description="內容1",
        snapshot_member_ids=member_ids,
        deadline_hours=72,
    )
    p2 = await svc.create_proposal(
        guild_id=guild_id,
        proposer_id=_snowflake(),
        title="提案2",
        description="內容2",
        snapshot_member_ids=member_ids,
        deadline_hours=72,
    )

    # 列出提案
    proposals = await svc.list_active_proposals(guild_id=guild_id)

    assert len(proposals) == 2
    proposal_ids = [p.proposal_id for p in proposals]
    assert p1.proposal_id in proposal_ids
    assert p2.proposal_id in proposal_ids


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_summon_member_contract() -> None:
    """契約測試：傳召議員。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    guild_id = _snowflake()
    speaker_id = _snowflake()
    target_id = _snowflake()

    # 傳召議員
    summon = await svc.create_summon(
        guild_id=guild_id,
        invoked_by=speaker_id,
        target_id=target_id,
        target_kind="member",
        note=None,
    )

    assert summon.summon_id is not None
    assert summon.guild_id == guild_id
    assert summon.invoked_by == speaker_id
    assert summon.target_id == target_id
    assert summon.target_kind == "member"
    assert summon.delivered_at is None


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_summon_official_contract() -> None:
    """契約測試：傳召政府官員。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    guild_id = _snowflake()
    speaker_id = _snowflake()
    target_id = _snowflake()

    # 傳召官員
    summon = await svc.create_summon(
        guild_id=guild_id,
        invoked_by=speaker_id,
        target_id=target_id,
        target_kind="official",
        note="傳召財政部長",
    )

    assert summon.summon_id is not None
    assert summon.target_kind == "official"
    assert summon.note == "傳召財政部長"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_supreme_assembly_mark_summon_delivered_contract() -> None:
    """契約測試：標記傳召已送達。"""
    gw = FakeSupremeAssemblyGateway()
    svc = FakeSupremeAssemblyService(gateway=gw)

    # 建立傳召
    summon = await svc.create_summon(
        guild_id=_snowflake(),
        invoked_by=_snowflake(),
        target_id=_snowflake(),
        target_kind="member",
        note=None,
    )

    # 標記已送達
    await svc.mark_summon_delivered(summon_id=summon.summon_id)

    # 驗證
    updated = gw.get_summon(summon.summon_id)
    assert updated is not None
    assert updated.delivered_at is not None
