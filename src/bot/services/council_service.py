from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, cast
from uuid import UUID

import structlog

from src.bot.services.transfer_service import TransferError, TransferService
from src.db.gateway.council_governance import (
    CouncilConfig,
    CouncilGovernanceGateway,
    CouncilRoleConfig,
    Proposal,
    Tally,
)
from src.db.pool import get_pool
from src.infra.events.council_events import CouncilEvent
from src.infra.events.council_events import publish as publish_council_event
from src.infra.types.db import ConnectionProtocol, PoolProtocol

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
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.upsert_config(
                c,
                guild_id=guild_id,
                council_role_id=council_role_id,
                council_account_member_id=self.derive_council_account_id(guild_id),
            )

    async def get_config(self, *, guild_id: int) -> CouncilConfig:
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            cfg = await self._gateway.fetch_config(c, guild_id=guild_id)
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
        target_department_id: str | None = None,
    ) -> Proposal:
        if amount <= 0:
            raise ValueError("Amount must be a positive integer.")
        if proposer_id == target_id:
            raise ValueError("Proposer and target must be distinct.")
        if not snapshot_member_ids:
            raise PermissionDeniedError(
                "No council members to snapshot. Configure role or members."
            )
        # Validate that either a valid target_id or a department id is provided
        if target_department_id is None and target_id <= 0:
            raise ValueError("Either a valid target_id or target_department_id must be provided.")

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            active = await self._gateway.count_active_by_guild(c, guild_id=guild_id)
            if active >= 5:
                raise RuntimeError(
                    "There are already 5 進行中 proposals for this guild. "
                    "Please結束或撤案後再建立新提案。"
                )
            proposal = await self._gateway.create_proposal(
                c,
                guild_id=guild_id,
                proposer_id=proposer_id,
                target_id=target_id,
                amount=amount,
                description=description,
                attachment_url=attachment_url,
                snapshot_member_ids=list(dict.fromkeys(int(x) for x in snapshot_member_ids)),
                target_department_id=target_department_id,
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
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        proposal = None
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            proposal = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
            if proposal is None:
                return False
            ok = await self._gateway.cancel_proposal(c, proposal_id=proposal_id)
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
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        totals: VoteTotals
        final_status: str
        event: CouncilEvent | None = None
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            proposal = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
            if proposal is None:
                raise RuntimeError("Proposal not found.")
            if proposal.status != "進行中":
                totals = await self._compute_totals(c, proposal_id, proposal)
                final_status = proposal.status
                event = CouncilEvent(
                    guild_id=proposal.guild_id,
                    proposal_id=proposal.proposal_id,
                    kind="proposal_status_changed",
                    status=final_status,
                )
            else:
                snapshot = await self._gateway.fetch_snapshot(c, proposal_id=proposal_id)
                if voter_id not in snapshot:
                    raise PermissionDeniedError("Voter is not in the snapshot for this proposal.")

                async with c.transaction():
                    await self._gateway.upsert_vote(
                        c,
                        proposal_id=proposal_id,
                        voter_id=voter_id,
                        choice=choice,
                    )
                    totals = await self._compute_totals(c, proposal_id, proposal)
                    final_status = "進行中"

                    # Passing threshold
                    if totals.approve >= proposal.threshold_t:
                        await self._gateway.mark_status(
                            c,
                            proposal_id=proposal_id,
                            status="已通過",
                        )
                        # Attempt execution immediately
                        await self._attempt_execution(c, proposal)
                        # Re-fetch status after execution
                        updated = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
                        if updated is not None:
                            final_status = updated.status
                        else:  # pragma: no cover - defensive fallback
                            final_status = "已通過"

                    # Early rejection: even if all remaining unvoted approve, cannot reach T
                    elif totals.approve + totals.remaining_unvoted < proposal.threshold_t:
                        await self._gateway.mark_status(
                            c,
                            proposal_id=proposal_id,
                            status="已否決",
                        )
                        final_status = "已否決"

                event = CouncilEvent(
                    guild_id=proposal.guild_id,
                    proposal_id=proposal.proposal_id,
                    kind=(
                        "proposal_status_changed"
                        if final_status != "進行中"
                        else "proposal_updated"
                    ),
                    status=final_status,
                )

        await publish_council_event(event)
        return totals, final_status

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

    async def _attempt_execution(self, connection: ConnectionProtocol, proposal: Proposal) -> None:
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

        # Determine target account ID: use department account if target_department_id is set
        target_account_id = proposal.target_id
        if proposal.target_department_id is not None:
            # Import here to avoid circular dependency
            from src.bot.services.department_registry import get_registry
            from src.bot.services.state_council_service import StateCouncilService

            registry = get_registry()
            dept = registry.get_by_id(proposal.target_department_id)
            if dept is None:
                await self._gateway.mark_status(
                    connection,
                    proposal_id=proposal.proposal_id,
                    status="執行失敗",
                    execution_error=f"Department ID {proposal.target_department_id} not found.",
                )
                return
            # Use StateCouncilService to derive department account ID
            target_account_id = StateCouncilService.derive_department_account_id(
                proposal.guild_id, dept.name
            )

        try:
            result = await self._transfer.transfer_currency(
                guild_id=proposal.guild_id,
                initiator_id=cfg.council_account_member_id,
                target_id=target_account_id,
                amount=proposal.amount,
                reason=proposal.description or "council_proposal",
                connection=connection,
            )
            if isinstance(result, UUID):
                # Event pool mode - this shouldn't happen in sync mode
                await self._gateway.mark_status(
                    connection,
                    proposal_id=proposal.proposal_id,
                    status="執行失敗",
                    execution_error="Transfer returned UUID in sync mode.",
                )
                return
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
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        changed = 0
        events: list[CouncilEvent] = []
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            for p in await self._gateway.list_due_proposals(c):
                totals = await self._compute_totals(c, p.proposal_id, p)
                if totals.approve >= p.threshold_t:
                    # In case we crossed threshold but scheduler fired late, ensure execution
                    await self._gateway.mark_status(
                        c,
                        proposal_id=p.proposal_id,
                        status="已通過",
                    )
                    await self._attempt_execution(c, p)
                    updated = await self._gateway.fetch_proposal(c, proposal_id=p.proposal_id)
                    status = updated.status if updated is not None else "已通過"
                else:
                    await self._gateway.mark_status(
                        c,
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

    # --- Council Role Management ---
    async def get_council_role_ids(self, *, guild_id: int) -> Sequence[int]:
        """獲取所有常任理事身分組 ID"""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.get_council_role_ids(c, guild_id=guild_id)

    async def add_council_role(self, *, guild_id: int, role_id: int) -> bool:
        """添加常任理事身分組"""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.add_council_role(c, guild_id=guild_id, role_id=role_id)

    async def remove_council_role(self, *, guild_id: int, role_id: int) -> bool:
        """移除常任理事身分組"""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.remove_council_role(c, guild_id=guild_id, role_id=role_id)

    async def check_council_permission(self, *, guild_id: int, user_roles: Sequence[int]) -> bool:
        """檢查用戶是否具備常任理事權限（基於身分組）"""
        try:
            council_role_ids = await self.get_council_role_ids(guild_id=guild_id)
            if not council_role_ids:
                # 向下相容：檢查傳統的單一身分組配置
                cfg = await self.get_config(guild_id=guild_id)
                return cfg.council_role_id in user_roles

            # 檢查用戶是否具備任一常任理事身分組
            has_multiple_role = bool(set(council_role_ids) & set(user_roles))

            # 同時檢查傳統的單一身分組配置（向下相容）
            cfg = await self.get_config(guild_id=guild_id)
            has_single_role = cfg.council_role_id in user_roles

            return has_multiple_role or has_single_role
        except GovernanceNotConfiguredError:
            return False

    async def list_council_role_configs(self, guild_id: int) -> Sequence[CouncilRoleConfig]:
        """列出公會的常任理事身分組配置"""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            return await self._gateway.list_council_role_configs(c, guild_id=guild_id)

    # --- Queries for UI ---
    async def list_active_proposals(self) -> Sequence[Proposal]:
        """列出所有進行中提案（供面板或啟動註冊使用）。

        注意：Gateway 目前未以 guild 過濾，此方法回傳跨 guild 結果；
        呼叫端若需僅顯示特定 guild，請自行過濾 `p.guild_id`。
        """
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            return await self._gateway.list_active_proposals(conn)


__all__ = [
    "CouncilService",
    "GovernanceNotConfiguredError",
    "PermissionDeniedError",
    "VoteTotals",
]
