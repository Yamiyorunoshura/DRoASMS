"""Council governance service implementation using Result pattern."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, cast
from uuid import UUID

import structlog

from src.bot.services.council_errors import (
    CouncilError,
    CouncilErrorCode,
    CouncilPermissionDeniedError,
    CouncilValidationError,
    ExecutionFailedError,
    GovernanceNotConfiguredError,
    InvalidProposalStatusError,
    ProposalLimitExceededError,
    ProposalNotFoundError,
    VotingNotAllowedError,
)
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
from src.infra.result import (
    DatabaseError,
    Err,
    Ok,
    Result,
    async_returns_result,
)
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class VoteTotals:
    approve: int
    reject: int
    abstain: int
    threshold_t: int
    snapshot_n: int
    remaining_unvoted: int


class CouncilService:
    """常任理事會治理服務，協調提案、投票、執行等操作。

    採用 Result<T, E> 模式提供類型安全的錯誤處理。
    """

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
        """導出常任理事會帳戶 ID。

        設計原則：
        - 與其他政府帳戶保持不重疊：常任理事會使用 9.0e15 區段，
          國務院主帳戶使用 9.1e15，部門帳戶使用 9.5e15。
        - 避免先前「乘以 10」造成的 int64 溢位，僅作加法偏移。

        公式：account_id = 9_000_000_000_000_000 + guild_id
        """
        base = 9_000_000_000_000_000
        return int(base + int(guild_id))

    @async_returns_result(
        CouncilError,
        exception_map={
            RuntimeError: CouncilError,
            Exception: CouncilError,
        },
    )
    async def set_config(
        self,
        *,
        guild_id: int,
        council_role_id: int,
    ) -> Result[CouncilConfig, CouncilError]:
        """Set council configuration for a guild."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            # 若已存在配置，沿用原帳戶 ID 以避免改變既有餘額紀錄
            existing = await self._gateway.fetch_config(c, guild_id=guild_id)
            council_account_id = (
                existing.council_account_member_id
                if existing is not None
                else self.derive_council_account_id(guild_id)
            )
            config = await self._gateway.upsert_config(
                c,
                guild_id=guild_id,
                council_role_id=council_role_id,
                council_account_member_id=council_account_id,
            )
            return Ok(config)

    @async_returns_result(
        CouncilError,
        exception_map={
            GovernanceNotConfiguredError: GovernanceNotConfiguredError,
            RuntimeError: CouncilError,
            Exception: CouncilError,
        },
    )
    async def get_config(self, *, guild_id: int) -> Result[CouncilConfig, CouncilError]:
        """Get council configuration for a guild."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            cfg = await self._gateway.fetch_config(c, guild_id=guild_id)
            if cfg is None:
                return Err(
                    GovernanceNotConfiguredError(
                        "此公會尚未配置常任理事會治理。",
                        context={"guild_id": guild_id},
                    )
                )
            return Ok(cfg)

    # --- Proposal lifecycle ---
    @async_returns_result(
        CouncilError,
        exception_map={
            ValueError: CouncilValidationError,
            CouncilPermissionDeniedError: CouncilPermissionDeniedError,
            RuntimeError: ProposalLimitExceededError,
            Exception: CouncilError,
        },
    )
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
    ) -> Result[Proposal, CouncilError]:
        """Create a new transfer proposal."""
        # Validation
        if amount <= 0:
            return Err(
                CouncilValidationError(
                    "金額必須為正整數。",
                    error_code=CouncilErrorCode.COUNCIL_VALIDATION_INVALID_AMOUNT,
                    context={"amount": amount},
                )
            )
        if proposer_id == target_id:
            return Err(
                CouncilValidationError(
                    "提案人與目標不可相同。",
                    error_code=CouncilErrorCode.COUNCIL_VALIDATION_SELF_TARGET,
                    context={"proposer_id": proposer_id, "target_id": target_id},
                )
            )
        if not snapshot_member_ids:
            return Err(
                CouncilPermissionDeniedError(
                    "沒有可快照的理事會成員，請先配置身分組或成員。",
                    error_code=CouncilErrorCode.COUNCIL_PERMISSION_NO_MEMBERS,
                    context={"guild_id": guild_id},
                )
            )
        # Validate that either a valid target_id or a department id is provided
        if target_department_id is None and target_id <= 0:
            return Err(
                CouncilValidationError(
                    "必須提供有效的目標用戶 ID 或部門 ID。",
                    error_code=CouncilErrorCode.COUNCIL_VALIDATION_INVALID_TARGET,
                    context={"target_id": target_id, "target_department_id": target_department_id},
                )
            )

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            active = await self._gateway.count_active_by_guild(c, guild_id=guild_id)
            if active >= 5:
                return Err(
                    ProposalLimitExceededError(
                        "此公會已有 5 個進行中提案，請先完成或取消現有提案。",
                        context={"guild_id": guild_id, "active_count": active},
                    )
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

        # Publish event
        await publish_council_event(
            CouncilEvent(
                guild_id=guild_id,
                proposal_id=proposal.proposal_id,
                kind="proposal_created",
                status=proposal.status,
            )
        )
        return Ok(proposal)

    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def cancel_proposal(self, *, proposal_id: UUID) -> Result[bool, CouncilError]:
        """Cancel a proposal."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        proposal = None
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            proposal = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
            if proposal is None:
                return Ok(False)  # Proposal not found, but cancellation is idempotent
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
        return Ok(ok)

    # --- Voting & evaluation ---
    @async_returns_result(
        CouncilError,
        exception_map={
            ValueError: CouncilValidationError,
            RuntimeError: InvalidProposalStatusError,
            CouncilPermissionDeniedError: VotingNotAllowedError,
            Exception: CouncilError,
        },
    )
    async def vote(
        self, *, proposal_id: UUID, voter_id: int, choice: str
    ) -> Result[tuple[VoteTotals, str], CouncilError]:
        """Cast a vote on a proposal."""
        if choice not in ("approve", "reject", "abstain"):
            return Err(
                CouncilValidationError(
                    "無效的投票選項。",
                    error_code=CouncilErrorCode.COUNCIL_VALIDATION_INVALID_CHOICE,
                    context={"choice": choice, "valid_choices": ["approve", "reject", "abstain"]},
                )
            )

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        totals: VoteTotals
        final_status: str
        event: CouncilEvent | None = None

        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            proposal = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
            if proposal is None:
                return Err(
                    ProposalNotFoundError(
                        "找不到指定的提案。",
                        context={"proposal_id": str(proposal_id)},
                    )
                )
            if proposal.status != "進行中":
                # Return current totals and status without voting
                totals = await self._compute_totals(c, proposal_id, proposal)
                final_status = proposal.status
                return Ok((totals, final_status))

            snapshot = await self._gateway.fetch_snapshot(c, proposal_id=proposal_id)
            if voter_id not in snapshot:
                return Err(
                    VotingNotAllowedError(
                        "投票人不在此提案的快照名單中。",
                        context={"voter_id": voter_id, "proposal_id": str(proposal_id)},
                    )
                )

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
                    exec_result = await self._attempt_execution(c, proposal)
                    if isinstance(exec_result, Err):
                        # Execution failed, but proposal still passed
                        LOGGER.error(
                            "proposal_execution_failed",
                            proposal_id=proposal_id,
                            error=exec_result.error,
                        )
                    # Re-fetch status after execution
                    updated = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
                    if updated is not None:
                        final_status = updated.status
                    else:
                        final_status = "已通過"

                # Early rejection: even if all remaining unvoted approve, cannot reach T
                elif totals.approve + totals.remaining_unvoted < proposal.threshold_t:
                    await self._gateway.mark_status(
                        c,
                        proposal_id=proposal_id,
                        status="已否決",
                    )
                    final_status = "已否決"

            # Publish event
            event = CouncilEvent(
                guild_id=proposal.guild_id,
                proposal_id=proposal.proposal_id,
                kind=(
                    "proposal_status_changed" if final_status != "進行中" else "proposal_updated"
                ),
                status=final_status,
            )

        if event:
            await publish_council_event(event)
        return Ok((totals, final_status))

    async def _compute_totals(
        self, connection: ConnectionProtocol, proposal_id: UUID, proposal: Proposal
    ) -> VoteTotals:
        """Compute vote totals for a proposal."""
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

    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: ExecutionFailedError,
        },
    )
    async def _attempt_execution(
        self, connection: ConnectionProtocol, proposal: Proposal
    ) -> Result[None, ExecutionFailedError]:
        """Attempt to execute a passed proposal."""
        # Fetch config for council account
        cfg = await self._gateway.fetch_config(connection, guild_id=proposal.guild_id)
        if cfg is None:
            error_msg = "執行階段缺少常任理事會配置。"
            await self._gateway.mark_status(
                connection,
                proposal_id=proposal.proposal_id,
                status="執行失敗",
                execution_error=error_msg,
            )
            return Err(
                ExecutionFailedError(
                    error_msg,
                    execution_error=error_msg,
                    error_code=CouncilErrorCode.COUNCIL_EXECUTION_NO_CONFIG,
                    proposal_id=str(proposal.proposal_id),
                    guild_id=proposal.guild_id,
                )
            )

        # Determine target account ID: use department account if target_department_id is set
        target_account_id = proposal.target_id
        if proposal.target_department_id is not None:
            # Import here to avoid circular dependency
            from src.bot.services.department_registry import get_registry
            from src.bot.services.state_council_service import StateCouncilService
            from src.db.gateway.state_council_governance import StateCouncilGovernanceGateway

            registry = get_registry()
            dept = registry.get_by_id(proposal.target_department_id)
            if dept is None:
                error_msg = f"找不到部門 ID: {proposal.target_department_id}。"
                await self._gateway.mark_status(
                    connection,
                    proposal_id=proposal.proposal_id,
                    status="執行失敗",
                    execution_error=error_msg,
                )
                return Err(
                    ExecutionFailedError(
                        error_msg,
                        execution_error=error_msg,
                        error_code=CouncilErrorCode.COUNCIL_EXECUTION_DEPARTMENT_NOT_FOUND,
                        proposal_id=str(proposal.proposal_id),
                        target_department_id=proposal.target_department_id,
                    )
                )

            # 優先讀取國務院配置中的實際帳戶 ID，避免與歷史資料不一致
            _dept_account_id: int | None = None
            try:
                sc_gateway = StateCouncilGovernanceGateway()
                sc_config = await sc_gateway.fetch_state_council_config(
                    connection, guild_id=proposal.guild_id
                )
                if sc_config is not None:
                    name_to_account = {
                        "內政部": sc_config.internal_affairs_account_id,
                        "財政部": sc_config.finance_account_id,
                        "國土安全部": sc_config.security_account_id,
                        "中央銀行": sc_config.central_bank_account_id,
                    }
                    # 新增法務部支援
                    justice_id = getattr(sc_config, "justice_account_id", None)
                    if justice_id is None:
                        justice_id = getattr(sc_config, "welfare_account_id", None)
                    if justice_id is not None:
                        name_to_account["法務部"] = justice_id

                    _dept_account_id = name_to_account.get(dept.name)
            except Exception:
                _dept_account_id = None

            # 若配置不存在對應帳戶，回退為演算法導出的穩定帳戶 ID
            if _dept_account_id is None:
                _dept_account_id = StateCouncilService.derive_department_account_id(
                    proposal.guild_id, dept.name
                )
            target_account_id = _dept_account_id

        # Attempt transfer using TransferService (same semantics as non-Result service).
        try:
            transfer_value_or_id = await self._transfer.transfer_currency(
                guild_id=proposal.guild_id,
                initiator_id=cfg.council_account_member_id,
                target_id=target_account_id,
                amount=proposal.amount,
                reason=proposal.description or "council_proposal",
                connection=connection,
            )
        except TransferError as exc:
            # Domain / validation failure (e.g. insufficient funds, throttled, etc.)
            error_msg = str(exc)
            await self._gateway.mark_status(
                connection,
                proposal_id=proposal.proposal_id,
                status="執行失敗",
                execution_error=error_msg,
            )
            return Err(
                ExecutionFailedError(
                    f"提案執行失敗: {error_msg}",
                    execution_error=error_msg,
                    error_code=CouncilErrorCode.COUNCIL_EXECUTION_TRANSFER_FAILED,
                    proposal_id=str(proposal.proposal_id),
                    error=error_msg,
                )
            )

        if isinstance(transfer_value_or_id, UUID):
            # 事件池模式：待核准/執行的 transfer_id（UUID）視為「已送出」
            await self._gateway.mark_status(
                connection,
                proposal_id=proposal.proposal_id,
                status="已執行",
                execution_tx_id=transfer_value_or_id,
                execution_error=None,
            )
            return Ok(None)

        transfer_value = transfer_value_or_id

        # Success - mark as executed
        await self._gateway.mark_status(
            connection,
            proposal_id=proposal.proposal_id,
            status="已執行",
            execution_tx_id=transfer_value.transaction_id,
            execution_error=None,
        )
        return Ok(None)

    # --- Timeout & reminders ---
    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def expire_due_proposals(self) -> Result[int, CouncilError]:
        """Expire proposals that have passed their deadline."""
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
                    exec_result = await self._attempt_execution(c, p)
                    if isinstance(exec_result, Err):
                        LOGGER.error(
                            "proposal_execution_failed",
                            proposal_id=p.proposal_id,
                            error=exec_result.error,
                        )
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
        return Ok(changed)

    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def list_unvoted_members(
        self, *, proposal_id: UUID
    ) -> Result[Sequence[int], CouncilError]:
        """List members who haven't voted on a proposal."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            members = await self._gateway.list_unvoted_members(c, proposal_id=proposal_id)
            return Ok(members)

    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def mark_reminded(self, *, proposal_id: UUID) -> Result[None, CouncilError]:
        """Mark a proposal as reminded."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            await self._gateway.mark_reminded(c, proposal_id=proposal_id)
            return Ok(None)

    # --- Export ---
    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def export_interval(
        self, *, guild_id: int, start: datetime, end: datetime
    ) -> Result[list[dict[str, object]], CouncilError]:
        """Export proposal data for a time interval."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            data = await self._gateway.export_interval(
                c,
                guild_id=guild_id,
                start=start,
                end=end,
            )
            return Ok(data)

    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def get_snapshot(self, *, proposal_id: UUID) -> Result[Sequence[int], CouncilError]:
        """Get the member snapshot for a proposal."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            snapshot = await self._gateway.fetch_snapshot(c, proposal_id=proposal_id)
            return Ok(snapshot)

    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def get_votes_detail(
        self, *, proposal_id: UUID
    ) -> Result[Sequence[tuple[int, str]], CouncilError]:
        """Get detailed vote information for a proposal."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            votes = await self._gateway.fetch_votes_detail(c, proposal_id=proposal_id)
            return Ok(votes)

    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def get_proposal(self, *, proposal_id: UUID) -> Result[Proposal | None, CouncilError]:
        """Get a proposal by ID."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            proposal = await self._gateway.fetch_proposal(c, proposal_id=proposal_id)
            return Ok(proposal)

    # --- Council Role Management ---
    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def get_council_role_ids(self, *, guild_id: int) -> Result[Sequence[int], CouncilError]:
        """Get all council role IDs for a guild."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            role_ids = await self._gateway.get_council_role_ids(c, guild_id=guild_id)
            return Ok(role_ids)

    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def add_council_role(self, *, guild_id: int, role_id: int) -> Result[bool, CouncilError]:
        """Add a council role for a guild."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            result = await self._gateway.add_council_role(c, guild_id=guild_id, role_id=role_id)
            return Ok(result)

    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def remove_council_role(
        self, *, guild_id: int, role_id: int
    ) -> Result[bool, CouncilError]:
        """Remove a council role from a guild."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            result = await self._gateway.remove_council_role(c, guild_id=guild_id, role_id=role_id)
            return Ok(result)

    @async_returns_result(
        CouncilError,
        exception_map={
            GovernanceNotConfiguredError: GovernanceNotConfiguredError,
            Exception: CouncilError,
        },
    )
    async def check_council_permission(
        self, *, guild_id: int, user_roles: Sequence[int]
    ) -> Result[bool, CouncilError]:
        """Check if a user has council permission based on their roles."""
        try:
            role_ids_result = await self.get_council_role_ids(guild_id=guild_id)
            if isinstance(role_ids_result, Err):
                # Propagate underlying CouncilError while preserving the boolean Result shape.
                return cast(Result[bool, CouncilError], Err(role_ids_result.error))

            council_role_ids = role_ids_result.unwrap()

            if not council_role_ids:
                # Downward compatibility: check traditional single role configuration
                config_result = await self.get_config(guild_id=guild_id)
                if isinstance(config_result, Err):
                    return Ok(False)  # No config means no permission

                cfg = cast(CouncilConfig, config_result.unwrap())
                return Ok(cfg.council_role_id in user_roles)

            # Check if user has any council role
            has_multiple_role = bool(set(council_role_ids) & set(user_roles))

            # Also check traditional single role configuration (downward compatibility)
            config_result = await self.get_config(guild_id=guild_id)
            if isinstance(config_result, Err):
                return Ok(has_multiple_role)

            cfg2 = cast(CouncilConfig, config_result.unwrap())
            has_single_role = cfg2.council_role_id in user_roles

            return Ok(has_multiple_role or has_single_role)
        except GovernanceNotConfiguredError:
            return Ok(False)

    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def list_council_role_configs(
        self, guild_id: int
    ) -> Result[Sequence[CouncilRoleConfig], CouncilError]:
        """List council role configurations for a guild."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            configs = await self._gateway.list_council_role_configs(c, guild_id=guild_id)
            return Ok(configs)

    # --- Queries for UI ---
    @async_returns_result(
        CouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def list_active_proposals(self) -> Result[Sequence[Proposal], CouncilError]:
        """List all active proposals across all guilds."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            proposals = await self._gateway.list_active_proposals(conn)
            return Ok(proposals)


# Backward compatibility aliases
CouncilServiceResult = CouncilService
PermissionDeniedError = CouncilPermissionDeniedError  # Deprecated, use CouncilPermissionDeniedError

__all__ = [
    "CouncilService",
    "CouncilServiceResult",  # Deprecated alias
    "VoteTotals",
    # Re-exported from council_errors for backward compatibility
    "GovernanceNotConfiguredError",
    "PermissionDeniedError",  # Deprecated, use CouncilPermissionDeniedError
    "CouncilPermissionDeniedError",
    "CouncilValidationError",
    "CouncilError",
    "CouncilErrorCode",
    "ProposalNotFoundError",
    "InvalidProposalStatusError",
    "VotingNotAllowedError",
    "ProposalLimitExceededError",
    "ExecutionFailedError",
]
