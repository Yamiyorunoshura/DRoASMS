from __future__ import annotations

from datetime import datetime
from typing import Sequence, cast
from uuid import UUID

import structlog

from src.bot.services.transfer_service import TransferService
from src.cython_ext.supreme_assembly_models import VoteTotals
from src.db.gateway.supreme_assembly_governance import (
    Proposal,
    Summon,
    SupremeAssemblyConfig,
    SupremeAssemblyGovernanceGateway,
    Tally,
)
from src.db.pool import get_pool
from src.infra.events.supreme_assembly_events import (
    SupremeAssemblyEvent,
    publish,
)
from src.infra.result import (
    Error,
    Result,
    ValidationError,
    async_returns_result,
)
from src.infra.result import (
    PermissionDeniedError as BasePermissionDeniedError,
)
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)


class SupremeAssemblyError(Error):
    """Base error for supreme assembly governance operations."""


class GovernanceNotConfiguredError(SupremeAssemblyError):
    """Raised when governance configuration is missing for a guild."""


class PermissionDeniedError(SupremeAssemblyError, BasePermissionDeniedError):
    """Raised when an operation is not allowed for the caller."""


class VoteAlreadyExistsError(SupremeAssemblyError):
    """Raised when a duplicate vote is detected."""


class SupremeAssemblyValidationError(SupremeAssemblyError, ValidationError):
    """Raised when validation fails for supreme assembly operations."""


_EXCEPTION_MAP: dict[type[Exception], type[SupremeAssemblyError]] = {
    GovernanceNotConfiguredError: GovernanceNotConfiguredError,
    PermissionDeniedError: PermissionDeniedError,
    VoteAlreadyExistsError: VoteAlreadyExistsError,
    ValueError: SupremeAssemblyValidationError,
    RuntimeError: SupremeAssemblyError,
}


class SupremeAssemblyService:
    """Coordinates supreme assembly governance operations and business rules."""

    def __init__(
        self,
        *,
        gateway: SupremeAssemblyGovernanceGateway | None = None,
        transfer_service: TransferService | None = None,
    ) -> None:
        self._gateway = gateway or SupremeAssemblyGovernanceGateway()
        # 延後建立 TransferService，以避免於同步情境（如命令註冊測試）中強制要求事件迴圈
        self._transfer: TransferService | None = transfer_service

    def _get_transfer_service(self) -> TransferService:
        if self._transfer is None:
            self._transfer = TransferService(get_pool())
        return self._transfer

    # --- Configuration ---
    @staticmethod
    def derive_account_id(guild_id: int) -> int:
        """導出最高人民會議帳戶 ID，與政府帳戶表一致。

        使用政府帳戶統一區段 9.5e15，最高人民會議部門代碼為 200：
        account_id = 9_500_000_000_000_000 + guild_id + 200
        """
        base = 9_500_000_000_000_000
        return int(base + int(guild_id) + 200)

    async def get_or_create_account_id(self, guild_id: int) -> int:
        """取得最高人民會議帳戶 ID，若已存在則沿用，否則使用推導值建立。

        - 若資料庫已有帳戶但採用舊公式，會嘗試更新為新公式的 account_id
          （避免面板與轉帳使用不同帳號）
        - 若不存在，使用 derive_account_id 推導並確保建立記錄
        """
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            derived_id = self.derive_account_id(guild_id)
            existing = await self._gateway.fetch_account(c, guild_id=guild_id)
            if existing is not None:
                current_id = int(existing[0])
                if current_id != derived_id:
                    try:
                        migrated = await self._gateway.update_account_id(
                            c, guild_id=guild_id, new_account_id=derived_id
                        )
                        LOGGER.info(
                            "supreme_assembly.account.migrated",
                            guild_id=guild_id,
                            old_account_id=current_id,
                            new_account_id=derived_id,
                        )
                        if migrated is not None:
                            return int(migrated[0])
                    except Exception as exc:  # pragma: no cover - 防禦性
                        LOGGER.warning(
                            "supreme_assembly.account.migrate_failed",
                            guild_id=guild_id,
                            old_account_id=current_id,
                            new_account_id=derived_id,
                            error=str(exc),
                        )
                return current_id

            await self._gateway.ensure_account(c, guild_id=guild_id, account_id=derived_id)
            return derived_id

    async def set_config(
        self,
        *,
        guild_id: int,
        speaker_role_id: int,
        member_role_id: int,
    ) -> Result[SupremeAssemblyConfig, SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> SupremeAssemblyConfig:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                config = await self._gateway.upsert_config(
                    c,
                    guild_id=guild_id,
                    speaker_role_id=speaker_role_id,
                    member_role_id=member_role_id,
                )
                _ = await self.get_or_create_account_id(guild_id)
                return config

        return await _impl()

    async def get_config(
        self, *, guild_id: int
    ) -> Result[SupremeAssemblyConfig, SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> SupremeAssemblyConfig:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                cfg = await self._gateway.fetch_config(c, guild_id=guild_id)
            if cfg is None:
                raise GovernanceNotConfiguredError(
                    "Supreme assembly governance is not configured for this guild."
                )
            return cfg

        return await _impl()

    async def get_account_balance(self, *, guild_id: int) -> Result[int, SupremeAssemblyError]:
        """Get the balance of the supreme assembly account for a guild."""

        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> int:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                result = await self._gateway.fetch_account(c, guild_id=guild_id)
                if result is None:
                    return 0
                return result[1]

        return await _impl()

    # --- Proposal lifecycle ---
    async def create_proposal(
        self,
        *,
        guild_id: int,
        proposer_id: int,
        title: str | None,
        description: str | None,
        snapshot_member_ids: Sequence[int],
        deadline_hours: int = 72,
    ) -> Result[Proposal, SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> Proposal:
            if not snapshot_member_ids:
                raise PermissionDeniedError(
                    "No members to snapshot. Configure member role or ensure members exist."
                )

            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                active_count = await self._gateway.count_active_by_guild(c, guild_id=guild_id)
                if active_count >= 5:
                    raise RuntimeError(
                        (
                            f"Active proposal limit reached for guild {guild_id}. "
                            "Maximum 5 active proposals allowed."
                        )
                    )

                proposal = await self._gateway.create_proposal(
                    c,
                    guild_id=guild_id,
                    proposer_id=proposer_id,
                    title=title,
                    description=description,
                    snapshot_member_ids=list(dict.fromkeys(int(x) for x in snapshot_member_ids)),
                    deadline_hours=deadline_hours,
                )
            await publish(
                SupremeAssemblyEvent(
                    guild_id=guild_id,
                    proposal_id=proposal.proposal_id,
                    kind="proposal_created",
                    status=proposal.status,
                )
            )
            return proposal

        return await _impl()

    async def cancel_proposal(self, *, proposal_id: UUID) -> Result[bool, SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> bool:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            proposal = None
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                proposal = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
                if proposal is None:
                    return False
                ok = await self._gateway.cancel_proposal(c, proposal_id=proposal_id)
            if ok and proposal:
                await publish(
                    SupremeAssemblyEvent(
                        guild_id=proposal.guild_id,
                        proposal_id=proposal_id,
                        kind="proposal_status_changed",
                        status="已撤案",
                    )
                )
            return ok

        return await _impl()

    # --- Voting & evaluation ---
    async def vote(
        self, *, proposal_id: UUID, voter_id: int, choice: str
    ) -> Result[tuple[VoteTotals, str], SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> tuple[VoteTotals, str]:
            if choice not in ("approve", "reject", "abstain"):
                raise ValueError("Invalid vote choice. Must be 'approve', 'reject', or 'abstain'.")

            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            totals: VoteTotals
            final_status: str
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                proposal = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
                if proposal is None:
                    raise RuntimeError("Proposal not found.")
                if proposal.status != "進行中":
                    totals = await self._compute_totals(c, proposal_id, proposal)
                    final_status = proposal.status
                else:
                    snapshot = await self._gateway.fetch_snapshot(c, proposal_id=proposal_id)
                    if voter_id not in snapshot:
                        raise PermissionDeniedError(
                            "Voter is not in the snapshot for this proposal."
                        )

                    async with c.transaction():
                        try:
                            await self._gateway.upsert_vote(
                                c,
                                proposal_id=proposal_id,
                                voter_id=voter_id,
                                choice=choice,
                            )
                        except RuntimeError as exc:
                            if "already exists" in str(exc).lower():
                                raise VoteAlreadyExistsError(
                                    "Vote already exists and cannot be changed."
                                ) from exc
                            raise

                        totals = await self._compute_totals(c, proposal_id, proposal)
                        final_status = "進行中"

                        if totals.approve >= proposal.threshold_t:
                            await self._gateway.mark_status(
                                c,
                                proposal_id=proposal_id,
                                status="已通過",
                            )
                            final_status = "已通過"
                            await publish(
                                SupremeAssemblyEvent(
                                    guild_id=proposal.guild_id,
                                    proposal_id=proposal_id,
                                    kind="proposal_status_changed",
                                    status="已通過",
                                )
                            )
                        elif totals.approve + totals.remaining_unvoted < proposal.threshold_t:
                            await self._gateway.mark_status(
                                c,
                                proposal_id=proposal_id,
                                status="已否決",
                            )
                            final_status = "已否決"
                            await publish(
                                SupremeAssemblyEvent(
                                    guild_id=proposal.guild_id,
                                    proposal_id=proposal_id,
                                    kind="proposal_status_changed",
                                    status="已否決",
                                )
                            )
                        else:
                            await publish(
                                SupremeAssemblyEvent(
                                    guild_id=proposal.guild_id,
                                    proposal_id=proposal_id,
                                    kind="vote_cast",
                                    status="進行中",
                                )
                            )

            return (totals, final_status)

        return await _impl()

    async def get_vote_totals(
        self, *, proposal_id: UUID
    ) -> Result[VoteTotals, SupremeAssemblyError]:
        """Get vote totals for a proposal."""

        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> VoteTotals:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                proposal = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
                if proposal is None:
                    raise RuntimeError("Proposal not found.")
                return await self._compute_totals(c, proposal_id, proposal)

        return await _impl()

    async def _compute_totals(
        self, connection: ConnectionProtocol, proposal_id: UUID, proposal: Proposal
    ) -> VoteTotals:
        tally: Tally = await self._gateway.fetch_tally(connection, proposal_id=proposal_id)
        remaining = max(0, proposal.snapshot_n - tally.total_voted)
        return VoteTotals(
            approve=tally.approve,
            reject=tally.reject,
            abstain=tally.abstain,
            threshold_t=proposal.threshold_t,
            snapshot_n=proposal.snapshot_n,
            remaining_unvoted=remaining,
        )

    # --- Timeout & reminders ---
    async def expire_due_proposals(self) -> Result[int, SupremeAssemblyError]:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())

        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> int:
            changed = 0
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                for p in await self._gateway.list_due_proposals(c):
                    totals = await self._compute_totals(c, p.proposal_id, p)
                    if totals.approve >= p.threshold_t:
                        await self._gateway.mark_status(
                            c,
                            proposal_id=p.proposal_id,
                            status="已通過",
                        )
                        status = "已通過"
                    else:
                        await self._gateway.mark_status(
                            c,
                            proposal_id=p.proposal_id,
                            status="已逾時",
                        )
                        status = "已逾時"
                    changed += 1
                    await publish(
                        SupremeAssemblyEvent(
                            guild_id=p.guild_id,
                            proposal_id=p.proposal_id,
                            kind="proposal_status_changed",
                            status=status,
                        )
                    )
            return changed

        return await _impl()

    async def list_unvoted_members(
        self, *, proposal_id: UUID
    ) -> Result[Sequence[int], SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> Sequence[int]:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                members = await self._gateway.list_unvoted_members(c, proposal_id=proposal_id)
                return members

        return await _impl()

    async def mark_reminded(self, *, proposal_id: UUID) -> Result[None, SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> None:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                await self._gateway.mark_reminded(c, proposal_id=proposal_id)
                return None

        return await _impl()

    # --- Export ---
    async def export_interval(
        self, *, guild_id: int, start: datetime, end: datetime
    ) -> Result[list[dict[str, object]], SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> list[dict[str, object]]:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                rows = await self._gateway.export_interval(
                    c,
                    guild_id=guild_id,
                    start=start,
                    end=end,
                )
                return rows

        return await _impl()

    async def get_snapshot(
        self, *, proposal_id: UUID
    ) -> Result[Sequence[int], SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> Sequence[int]:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                snapshot = await self._gateway.fetch_snapshot(c, proposal_id=proposal_id)
                return snapshot

        return await _impl()

    async def get_votes_detail(
        self, *, proposal_id: UUID
    ) -> Result[Sequence[tuple[int, str]], SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> Sequence[tuple[int, str]]:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                details = await self._gateway.fetch_votes_detail(c, proposal_id=proposal_id)
                return details

        return await _impl()

    async def get_proposal(
        self, *, proposal_id: UUID
    ) -> Result[Proposal | None, SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> Proposal | None:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                proposal = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
                return proposal

        return await _impl()

    # --- Queries for UI ---
    async def list_active_proposals(
        self, *, guild_id: int | None = None
    ) -> Result[Sequence[Proposal], SupremeAssemblyError]:
        """List active proposals, optionally filtered by guild."""

        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> Sequence[Proposal]:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                proposals = await self._gateway.list_active_proposals(c)
                if guild_id is not None:
                    proposals = [p for p in proposals if p.guild_id == guild_id]
                return proposals

        return await _impl()

    # --- Summons ---
    async def create_summon(
        self,
        *,
        guild_id: int,
        invoked_by: int,
        target_id: int,
        target_kind: str,
        note: str | None = None,
    ) -> Result[Summon, SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> Summon:
            if target_kind not in ("member", "official"):
                raise ValueError("target_kind must be 'member' or 'official'")

            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                summon = await self._gateway.create_summon(
                    c,
                    guild_id=guild_id,
                    invoked_by=invoked_by,
                    target_id=target_id,
                    target_kind=target_kind,
                    note=note,
                )
                return summon

        return await _impl()

    async def mark_summon_delivered(self, *, summon_id: UUID) -> Result[None, SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> None:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                await self._gateway.mark_summon_delivered(c, summon_id=summon_id)
                return None

        return await _impl()

    async def list_summons(
        self, *, guild_id: int, limit: int = 50
    ) -> Result[Sequence[Summon], SupremeAssemblyError]:
        @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
        async def _impl() -> Sequence[Summon]:
            pool: PoolProtocol = cast(PoolProtocol, get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                summons = await self._gateway.list_summons(c, guild_id=guild_id, limit=limit)
                return summons

        return await _impl()


__all__ = [
    "SupremeAssemblyService",
    "SupremeAssemblyError",
    "GovernanceNotConfiguredError",
    "PermissionDeniedError",
    "VoteAlreadyExistsError",
    "SupremeAssemblyValidationError",
    "VoteTotals",
]
