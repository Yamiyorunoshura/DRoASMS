from __future__ import annotations

import warnings
from datetime import datetime
from typing import Any, Sequence, cast
from uuid import UUID

import structlog

from src.bot.services.council_errors import (
    CouncilPermissionDeniedError,
    CouncilValidationError,
    ExecutionFailedError,
    GovernanceNotConfiguredError,
    InvalidProposalStatusError,
    ProposalLimitExceededError,
    ProposalNotFoundError,
    VotingNotAllowedError,
)
from src.bot.services.council_service_result import CouncilServiceResult, VoteTotals
from src.bot.services.transfer_service import TransferService
from src.db.gateway.council_governance import (
    CouncilConfig,
    CouncilGovernanceGateway,
    CouncilRoleConfig,
    Proposal,
)
from src.db.pool import get_pool
from src.infra.result import Ok, Result

LOGGER = structlog.get_logger(__name__)


class PermissionDeniedError(RuntimeError):
    pass


class CouncilService:
    """Coordinates council governance operations and business rules.

    DEPRECATED: This service uses exception-based error handling.
    Consider migrating to CouncilServiceResult for type-safe Result pattern.
    This implementation now delegates to CouncilServiceResult internally.
    """

    def __init__(
        self,
        *,
        gateway: CouncilGovernanceGateway | None = None,
        transfer_service: TransferService | None = None,
    ) -> None:
        warnings.warn(
            "CouncilService is deprecated. Migrate to CouncilServiceResult for Result pattern.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._result_service = CouncilServiceResult(
            gateway=gateway,
            transfer_service=transfer_service,
        )

    @property
    def _gateway(self) -> CouncilGovernanceGateway:
        """Backward compatibility property for tests."""
        return self._result_service._gateway  # pyright: ignore[reportPrivateUsage]

    @property
    def _transfer(self) -> TransferService:
        """Backward compatibility property for tests."""
        return self._result_service._transfer  # pyright: ignore[reportPrivateUsage]

    def _unwrap_result(self, result: Result[Any, Any]) -> Any:
        """Convert Result to value or raise exception for backward compatibility."""
        if isinstance(result, Ok):
            return result.value
        else:
            # Map CouncilError types to traditional exceptions
            error = result.error
            if isinstance(error, CouncilValidationError):
                raise ValueError(str(error))
            elif isinstance(error, CouncilPermissionDeniedError):
                raise PermissionDeniedError(str(error))
            elif isinstance(error, GovernanceNotConfiguredError):
                raise GovernanceNotConfiguredError(str(error))
            elif isinstance(error, ProposalNotFoundError):
                raise ValueError(str(error))
            elif isinstance(error, InvalidProposalStatusError):
                raise ValueError(str(error))
            elif isinstance(error, VotingNotAllowedError):
                raise PermissionDeniedError(str(error))
            elif isinstance(error, ProposalLimitExceededError):
                raise ValueError(str(error))
            elif isinstance(error, ExecutionFailedError):
                raise RuntimeError(str(error))
            else:
                # Fallback for any other error types
                raise RuntimeError(f"Unexpected error: {error}")

    # --- Configuration ---
    @staticmethod
    def derive_council_account_id(guild_id: int) -> int:
        # Deterministic pseudo member id: 9e15 + guild_id to avoid collisions with real user IDs
        return CouncilServiceResult.derive_council_account_id(guild_id)

    async def set_config(self, *, guild_id: int, council_role_id: int) -> CouncilConfig:
        result = await self._result_service.set_config(
            guild_id=guild_id,
            council_role_id=council_role_id,
        )
        return cast(CouncilConfig, self._unwrap_result(result))

    async def get_config(self, *, guild_id: int) -> CouncilConfig:
        result = await self._result_service.get_config(guild_id=guild_id)
        return cast(CouncilConfig, self._unwrap_result(result))

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
        result = await self._result_service.create_transfer_proposal(
            guild_id=guild_id,
            proposer_id=proposer_id,
            target_id=target_id,
            amount=amount,
            description=description,
            attachment_url=attachment_url,
            snapshot_member_ids=snapshot_member_ids,
            target_department_id=target_department_id,
        )
        return cast(Proposal, self._unwrap_result(result))

    async def cancel_proposal(self, *, proposal_id: UUID) -> bool:
        result = await self._result_service.cancel_proposal(proposal_id=proposal_id)
        return cast(bool, self._unwrap_result(result))

    # --- Voting & evaluation ---
    async def vote(
        self, *, proposal_id: UUID, voter_id: int, choice: str
    ) -> tuple[VoteTotals, str]:
        result = await self._result_service.vote(
            proposal_id=proposal_id,
            voter_id=voter_id,
            choice=choice,
        )
        return cast(tuple[VoteTotals, str], self._unwrap_result(result))

    # --- Timeout & reminders ---
    async def expire_due_proposals(self) -> int:
        result = await self._result_service.expire_due_proposals()
        return cast(int, self._unwrap_result(result))

    async def list_unvoted_members(self, *, proposal_id: UUID) -> Sequence[int]:
        result = await self._result_service.list_unvoted_members(proposal_id=proposal_id)
        return cast(Sequence[int], self._unwrap_result(result))

    async def mark_reminded(self, *, proposal_id: UUID) -> None:
        result = await self._result_service.mark_reminded(proposal_id=proposal_id)
        return cast(None, self._unwrap_result(result))

    # --- Export ---
    async def export_interval(
        self, *, guild_id: int, start: datetime, end: datetime
    ) -> list[dict[str, object]]:
        result = await self._result_service.export_interval(guild_id=guild_id, start=start, end=end)
        return cast(list[dict[str, object]], self._unwrap_result(result))

    async def get_snapshot(self, *, proposal_id: UUID) -> Sequence[int]:
        result = await self._result_service.get_snapshot(proposal_id=proposal_id)
        return cast(Sequence[int], self._unwrap_result(result))

    async def get_votes_detail(self, *, proposal_id: UUID) -> Sequence[tuple[int, str]]:
        result = await self._result_service.get_votes_detail(proposal_id=proposal_id)
        return cast(Sequence[tuple[int, str]], self._unwrap_result(result))

    async def get_proposal(self, *, proposal_id: UUID) -> Proposal | None:
        result = await self._result_service.get_proposal(proposal_id=proposal_id)
        return cast(Proposal | None, self._unwrap_result(result))

    # --- Council Role Management ---
    async def get_council_role_ids(self, *, guild_id: int) -> Sequence[int]:
        """獲取所有常任理事身分組 ID"""
        result = await self._result_service.get_council_role_ids(guild_id=guild_id)
        return cast(Sequence[int], self._unwrap_result(result))

    async def add_council_role(self, *, guild_id: int, role_id: int) -> bool:
        """添加常任理事身分組"""
        result = await self._result_service.add_council_role(guild_id=guild_id, role_id=role_id)
        return cast(bool, self._unwrap_result(result))

    async def remove_council_role(self, *, guild_id: int, role_id: int) -> bool:
        """移除常任理事身分組"""
        result = await self._result_service.remove_council_role(guild_id=guild_id, role_id=role_id)
        return cast(bool, self._unwrap_result(result))

    async def check_council_permission(self, *, guild_id: int, user_roles: Sequence[int]) -> bool:
        """檢查用戶是否具備常任理事權限（基於身分組）"""
        result = await self._result_service.check_council_permission(
            guild_id=guild_id, user_roles=user_roles
        )
        return cast(bool, self._unwrap_result(result))

    async def list_council_role_configs(self, guild_id: int) -> Sequence[CouncilRoleConfig]:
        """列出公會的常任理事身分組配置"""
        result = await self._result_service.list_council_role_configs(guild_id=guild_id)
        return cast(Sequence[CouncilRoleConfig], self._unwrap_result(result))

    # --- Queries for UI ---
    async def list_active_proposals(self) -> Sequence[Proposal]:
        """列出所有進行中提案（供面板或啟動註冊使用）。

        注意：Gateway 目前未以 guild 過濾，此方法回傳跨 guild 結果；
        呼叫端若需僅顯示特定 guild，請自行過濾 `p.guild_id`。
        """
        result = await self._result_service.list_active_proposals()
        return cast(Sequence[Proposal], self._unwrap_result(result))


__all__ = [
    "CouncilService",
    "GovernanceNotConfiguredError",
    "PermissionDeniedError",
    "VoteTotals",
    "get_pool",
]
