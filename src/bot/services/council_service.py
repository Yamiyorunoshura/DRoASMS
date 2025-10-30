from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import UUID

import asyncpg
import structlog

from src.bot.services.transfer_service import TransferError, TransferService
from src.db.gateway.council_governance import (
    CouncilConfig,
    CouncilGovernanceGateway,
    Proposal,
    Tally,
)
from src.db.pool import get_pool
from src.infra.events.council_events import CouncilEvent, publish as publish_council_event

LOGGER = structlog.get_logger(__name__)


class GovernanceNotConfiguredError(RuntimeError):
    pass


class PermissionDeniedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VoteTotals:
    approve: int
    reject: int
    abstain: int
    threshold_t: int
    snapshot_n: int
    remaining_unvoted: int


class CouncilService:
    """Coordinates council governance operations and business rules."""

    def __init__(
        self,
        *,
        gateway: CouncilGovernanceGateway | None = None,
        transfer_service: TransferService | None = None,
    ) -> None:
        self._gateway = gateway or CouncilGovernanceGateway()
        self._transfer = transfer_service or TransferService(get_pool())

    # --- Configuration ---
    @staticmethod
    def derive_council_account_id(guild_id: int) -> int:
        # Deterministic pseudo member id: 9e15 + guild_id to avoid collisions with real user IDs
        return 9_000_000_000_000_000 + int(guild_id)

    async def set_config(
        self,
        *,
        guild_id: int,
        council_role_id: int,
    ) -> CouncilConfig:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._gateway.upsert_config(
                conn,
                guild_id=guild_id,
                council_role_id=council_role_id,
                council_account_member_id=self.derive_council_account_id(guild_id),
            )

    async def get_config(self, *, guild_id: int) -> CouncilConfig:
        pool = get_pool()
        async with pool.acquire() as conn:
            cfg = await self._gateway.fetch_config(conn, guild_id=guild_id)
        if cfg is None:
            raise GovernanceNotConfiguredError(
                "Council governance is not configured for this guild."
            )
        return cfg

    # --- Proposal lifecycle ---
    async def create_transfer_proposal(
        self,
        *,
        guild_id: int,
        proposer_id: int,
        target_id: int,
        amount: int,
        description: str | None,
        attachment_url: str | None,
        snapshot_member_ids: Sequence[int],
    ) -> Proposal:
        if amount <= 0:
            raise ValueError("Amount must be a positive integer.")
        if proposer_id == target_id:
            raise ValueError("Proposer and target must be distinct.")
        if not snapshot_member_ids:
            raise PermissionDeniedError(
                "No council members to snapshot. Configure role or members."
            )

        pool = get_pool()
        async with pool.acquire() as conn:
            proposal = await self._gateway.create_proposal(
                conn,
                guild_id=guild_id,
                proposer_id=proposer_id,
                target_id=target_id,
                amount=amount,
                description=description,
                attachment_url=attachment_url,
                snapshot_member_ids=list(dict.fromkeys(int(x) for x in snapshot_member_ids)),
            )
        await publish_council_event(
            CouncilEvent(
                guild_id=guild_id,
                proposal_id=proposal.proposal_id,
                kind="proposal_created",
                status=proposal.status,
            )
        )
        return proposal

    async def cancel_proposal(self, *, proposal_id: UUID) -> bool:
        pool = get_pool()
        proposal = None
        async with pool.acquire() as conn:
            proposal = await self._gateway.fetch_proposal(conn, proposal_id=proposal_id)
            if proposal is None:
                return False
            # Only allow if no vote exists yet
            votes = await conn.fetchval(
                "SELECT COUNT(*) FROM governance.votes WHERE proposal_id=$1",
                proposal_id,
            )
            if int(votes or 0) > 0:
                return False
            ok = await self._gateway.cancel_proposal(conn, proposal_id=proposal_id)
        if ok:
            await publish_council_event(
                CouncilEvent(
                    guild_id=proposal.guild_id,
                    proposal_id=proposal_id,
                    kind="proposal_cancelled",
                    status="已撤案",
                )
            )
        return ok

    # --- Voting & evaluation ---
    async def vote(
        self, *, proposal_id: UUID, voter_id: int, choice: str
    ) -> tuple[VoteTotals, str]:
        if choice not in ("approve", "reject", "abstain"):
            raise ValueError("Invalid vote choice.")
        pool = get_pool()
        totals: VoteTotals
        final_status: str
        event: CouncilEvent | None = None
        async with pool.acquire() as conn:
            proposal = await self._gateway.fetch_proposal(conn, proposal_id=proposal_id)
            if proposal is None:
                raise RuntimeError("Proposal not found.")
            if proposal.status != "進行中":
                totals = await self._compute_totals(conn, proposal_id, proposal)
                final_status = proposal.status
                event = CouncilEvent(
                    guild_id=proposal.guild_id,
                    proposal_id=proposal.proposal_id,
                    kind="proposal_status_changed",
                    status=final_status,
                )
            else:
                snapshot = await self._gateway.fetch_snapshot(conn, proposal_id=proposal_id)
                if voter_id not in snapshot:
                    raise PermissionDeniedError("Voter is not in the snapshot for this proposal.")

                async with conn.transaction():
                    await self._gateway.upsert_vote(
                        conn,
                        proposal_id=proposal_id,
                        voter_id=voter_id,
                        choice=choice,
                    )
                    totals = await self._compute_totals(conn, proposal_id, proposal)
                    final_status = "進行中"

                    # Passing threshold
                    if totals.approve >= proposal.threshold_t:
                        await self._gateway.mark_status(
                            conn,
                            proposal_id=proposal_id,
                            status="已通過",
                        )
                        # Attempt execution immediately
                        await self._attempt_execution(conn, proposal)
                        # Re-fetch status after execution
                        updated = await self._gateway.fetch_proposal(conn, proposal_id=proposal_id)
                        if updated is not None:
                            final_status = updated.status
                        else:  # pragma: no cover - defensive fallback
                            final_status = "已通過"

                    # Early rejection: even if all remaining unvoted approve, cannot reach T
                    elif totals.approve + totals.remaining_unvoted < proposal.threshold_t:
                        await self._gateway.mark_status(
                            conn,
                            proposal_id=proposal_id,
                            status="已否決",
                        )
                        final_status = "已否決"

                event = CouncilEvent(
                    guild_id=proposal.guild_id,
                    proposal_id=proposal.proposal_id,
                    kind="proposal_status_changed" if final_status != "進行中" else "proposal_updated",
                    status=final_status,
                )

        if event is not None:
            await publish_council_event(event)
        return totals, final_status

    async def _compute_totals(
        self, connection: asyncpg.Connection, proposal_id: UUID, proposal: Proposal
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

    async def _attempt_execution(self, connection: asyncpg.Connection, proposal: Proposal) -> None:
        # Fetch config for council account
        cfg = await self._gateway.fetch_config(connection, guild_id=proposal.guild_id)
        if cfg is None:
            await self._gateway.mark_status(
                connection,
                proposal_id=proposal.proposal_id,
                status="執行失敗",
                execution_error="Missing council configuration at execution stage.",
            )
            return

        try:
            result = await self._transfer.transfer_currency(
                guild_id=proposal.guild_id,
                initiator_id=cfg.council_account_member_id,
                target_id=proposal.target_id,
                amount=proposal.amount,
                reason=proposal.description or "council_proposal",
                connection=connection,
            )
            await self._gateway.mark_status(
                connection,
                proposal_id=proposal.proposal_id,
                status="已執行",
                execution_tx_id=result.transaction_id,
                execution_error=None,
            )
        except TransferError as exc:  # insufficient funds, throttled, etc.
            await self._gateway.mark_status(
                connection,
                proposal_id=proposal.proposal_id,
                status="執行失敗",
                execution_error=str(exc),
            )

    # --- Timeout & reminders ---
    async def expire_due_proposals(self) -> int:
        pool = get_pool()
        changed = 0
        events: list[CouncilEvent] = []
        async with pool.acquire() as conn:
            for p in await self._gateway.list_due_proposals(conn):
                totals = await self._compute_totals(conn, p.proposal_id, p)
                if totals.approve >= p.threshold_t:
                    # In case we crossed threshold but scheduler fired late, ensure execution
                    await self._gateway.mark_status(
                        conn,
                        proposal_id=p.proposal_id,
                        status="已通過",
                    )
                    await self._attempt_execution(conn, p)
                    updated = await self._gateway.fetch_proposal(conn, proposal_id=p.proposal_id)
                    status = updated.status if updated is not None else "已通過"
                else:
                    await self._gateway.mark_status(
                        conn,
                        proposal_id=p.proposal_id,
                        status="已逾時",
                    )
                    status = "已逾時"
                changed += 1
                events.append(
                    CouncilEvent(
                        guild_id=p.guild_id,
                        proposal_id=p.proposal_id,
                        kind="proposal_status_changed",
                        status=status,
                    )
                )
        for event in events:
            await publish_council_event(event)
        return changed

    async def list_unvoted_members(self, *, proposal_id: UUID) -> Sequence[int]:
        pool = get_pool()
        async with pool.acquire() as conn:
            snapshot = await self._gateway.fetch_snapshot(conn, proposal_id=proposal_id)
            rows = await conn.fetch(
                "SELECT voter_id FROM governance.votes WHERE proposal_id=$1",
                proposal_id,
            )
            voted = {int(r["voter_id"]) for r in rows}
            return [mid for mid in snapshot if mid not in voted]

    async def mark_reminded(self, *, proposal_id: UUID) -> None:
        pool = get_pool()
        async with pool.acquire() as conn:
            await self._gateway.mark_reminded(conn, proposal_id=proposal_id)

    # --- Export ---
    async def export_interval(
        self, *, guild_id: int, start: datetime, end: datetime
    ) -> list[dict[str, object]]:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._gateway.export_interval(
                conn,
                guild_id=guild_id,
                start=start,
                end=end,
            )

    async def get_snapshot(self, *, proposal_id: UUID) -> Sequence[int]:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._gateway.fetch_snapshot(conn, proposal_id=proposal_id)

    async def get_votes_detail(self, *, proposal_id: UUID) -> Sequence[tuple[int, str]]:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._gateway.fetch_votes_detail(conn, proposal_id=proposal_id)

    async def get_proposal(self, *, proposal_id: UUID) -> Proposal | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._gateway.fetch_proposal(conn, proposal_id=proposal_id)

    # --- Queries for UI ---
    async def list_active_proposals(self) -> Sequence[Proposal]:
        """列出所有進行中提案（供面板或啟動註冊使用）。

        注意：Gateway 目前未以 guild 過濾，此方法回傳跨 guild 結果；
        呼叫端若需僅顯示特定 guild，請自行過濾 `p.guild_id`。
        """
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._gateway.list_active_proposals(conn)


__all__ = [
    "CouncilService",
    "GovernanceNotConfiguredError",
    "PermissionDeniedError",
    "VoteTotals",
]
