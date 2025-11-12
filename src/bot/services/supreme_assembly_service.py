from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, cast
from uuid import UUID

import structlog
from mypy_extensions import mypyc_attr

from src.bot.services.transfer_service import TransferService
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
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)


@mypyc_attr(native_class=False)
class GovernanceNotConfiguredError(RuntimeError):
    pass


@mypyc_attr(native_class=False)
class PermissionDeniedError(RuntimeError):
    pass


@mypyc_attr(native_class=False)
class VoteAlreadyExistsError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VoteTotals:
    approve: int
    reject: int
    abstain: int
    threshold_t: int
    snapshot_n: int
    remaining_unvoted: int


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
        # Deterministic account id: 9.2e15 + guild_id
        return 9_200_000_000_000_000 + int(guild_id)

    async def set_config(
        self,
        *,
        guild_id: int,
        speaker_role_id: int,
        member_role_id: int,
    ) -> SupremeAssemblyConfig:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            config = await self._gateway.upsert_config(
                c,
                guild_id=guild_id,
                speaker_role_id=speaker_role_id,
                member_role_id=member_role_id,
            )
            # Ensure account exists
            account_id = self.derive_account_id(guild_id)
            await self._gateway.ensure_account(c, guild_id=guild_id, account_id=account_id)
            return config

    async def get_config(self, *, guild_id: int) -> SupremeAssemblyConfig:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            cfg = await self._gateway.fetch_config(c, guild_id=guild_id)
        if cfg is None:
            raise GovernanceNotConfiguredError(
                "Supreme assembly governance is not configured for this guild."
            )
        return cfg

    async def get_account_balance(self, *, guild_id: int) -> int:
        """Get the balance of the supreme assembly account for a guild."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            result = await self._gateway.fetch_account(c, guild_id=guild_id)
            if result is None:
                # Account doesn't exist yet, return 0
                return 0
            return result[1]

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
    ) -> Proposal:
        if not snapshot_member_ids:
            raise PermissionDeniedError(
                "No members to snapshot. Configure member role or ensure members exist."
            )

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            # Check concurrency limit
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
        # Publish event for proposal creation
        await publish(
            SupremeAssemblyEvent(
                guild_id=guild_id,
                proposal_id=proposal.proposal_id,
                kind="proposal_created",
                status=proposal.status,
            )
        )
        return proposal

    async def cancel_proposal(self, *, proposal_id: UUID) -> bool:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        proposal = None
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            proposal = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
            if proposal is None:
                return False
            ok = await self._gateway.cancel_proposal(c, proposal_id=proposal_id)
        if ok and proposal:
            # Publish event for proposal cancellation
            await publish(
                SupremeAssemblyEvent(
                    guild_id=proposal.guild_id,
                    proposal_id=proposal_id,
                    kind="proposal_status_changed",
                    status="已撤案",
                )
            )
        return ok

    # --- Voting & evaluation ---
    async def vote(
        self, *, proposal_id: UUID, voter_id: int, choice: str
    ) -> tuple[VoteTotals, str]:
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
                    raise PermissionDeniedError("Voter is not in the snapshot for this proposal.")

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

                    # Passing threshold
                    if totals.approve >= proposal.threshold_t:
                        await self._gateway.mark_status(
                            c,
                            proposal_id=proposal_id,
                            status="已通過",
                        )
                        final_status = "已通過"
                        # Publish event for proposal passed
                        await publish(
                            SupremeAssemblyEvent(
                                guild_id=proposal.guild_id,
                                proposal_id=proposal_id,
                                kind="proposal_status_changed",
                                status="已通過",
                            )
                        )
                    # Early rejection: even if all remaining unvoted approve, cannot reach T
                    elif totals.approve + totals.remaining_unvoted < proposal.threshold_t:
                        await self._gateway.mark_status(
                            c,
                            proposal_id=proposal_id,
                            status="已否決",
                        )
                        final_status = "已否決"
                        # Publish event for proposal rejected
                        await publish(
                            SupremeAssemblyEvent(
                                guild_id=proposal.guild_id,
                                proposal_id=proposal_id,
                                kind="proposal_status_changed",
                                status="已否決",
                            )
                        )
                    else:
                        # Publish event for vote update if still in progress
                        await publish(
                            SupremeAssemblyEvent(
                                guild_id=proposal.guild_id,
                                proposal_id=proposal_id,
                                kind="vote_cast",
                                status="進行中",
                            )
                        )

        return totals, final_status

    async def get_vote_totals(self, *, proposal_id: UUID) -> VoteTotals:
        """Get vote totals for a proposal."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            proposal = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
            if proposal is None:
                raise RuntimeError("Proposal not found.")
            return await self._compute_totals(c, proposal_id, proposal)

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
    async def expire_due_proposals(self) -> int:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        changed = 0
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            for p in await self._gateway.list_due_proposals(c):
                totals = await self._compute_totals(c, p.proposal_id, p)
                if totals.approve >= p.threshold_t:
                    # In case we crossed threshold but scheduler fired late, mark as passed
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
                # Publish event for proposal status change
                await publish(
                    SupremeAssemblyEvent(
                        guild_id=p.guild_id,
                        proposal_id=p.proposal_id,
                        kind="proposal_status_changed",
                        status=status,
                    )
                )
        return changed

    async def list_unvoted_members(self, *, proposal_id: UUID) -> Sequence[int]:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.list_unvoted_members(c, proposal_id=proposal_id)

    async def mark_reminded(self, *, proposal_id: UUID) -> None:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            await self._gateway.mark_reminded(c, proposal_id=proposal_id)

    # --- Export ---
    async def export_interval(
        self, *, guild_id: int, start: datetime, end: datetime
    ) -> list[dict[str, object]]:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.export_interval(
                c,
                guild_id=guild_id,
                start=start,
                end=end,
            )

    async def get_snapshot(self, *, proposal_id: UUID) -> Sequence[int]:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.fetch_snapshot(c, proposal_id=proposal_id)

    async def get_votes_detail(self, *, proposal_id: UUID) -> Sequence[tuple[int, str]]:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.fetch_votes_detail(c, proposal_id=proposal_id)

    async def get_proposal(self, *, proposal_id: UUID) -> Proposal | None:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.fetch_proposal(c, proposal_id=proposal_id)

    # --- Queries for UI ---
    async def list_active_proposals(self, *, guild_id: int | None = None) -> Sequence[Proposal]:
        """List active proposals, optionally filtered by guild."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            proposals = await self._gateway.list_active_proposals(c)
            if guild_id is not None:
                return [p for p in proposals if p.guild_id == guild_id]
            return proposals

    # --- Summons ---
    async def create_summon(
        self,
        *,
        guild_id: int,
        invoked_by: int,
        target_id: int,
        target_kind: str,
        note: str | None = None,
    ) -> Summon:
        if target_kind not in ("member", "official"):
            raise ValueError("target_kind must be 'member' or 'official'")

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.create_summon(
                c,
                guild_id=guild_id,
                invoked_by=invoked_by,
                target_id=target_id,
                target_kind=target_kind,
                note=note,
            )

    async def mark_summon_delivered(self, *, summon_id: UUID) -> None:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            await self._gateway.mark_summon_delivered(c, summon_id=summon_id)

    async def list_summons(self, *, guild_id: int, limit: int = 50) -> Sequence[Summon]:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.list_summons(c, guild_id=guild_id, limit=limit)


__all__ = [
    "SupremeAssemblyService",
    "GovernanceNotConfiguredError",
    "PermissionDeniedError",
    "VoteAlreadyExistsError",
    "VoteTotals",
]
