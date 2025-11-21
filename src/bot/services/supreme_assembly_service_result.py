"""Result-based wrapper for SupremeAssemblyService."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence
from uuid import UUID

from src.bot.services.supreme_assembly_service import (
    GovernanceNotConfiguredError,
    PermissionDeniedError,
    SupremeAssemblyError,
    SupremeAssemblyService,
    SupremeAssemblyValidationError,
    VoteAlreadyExistsError,
    VoteTotals,
)
from src.bot.services.transfer_service import (
    TransferError,
    TransferService,
    TransferValidationError,
)
from src.db.gateway.supreme_assembly_governance import (
    Proposal,
    Summon,
    SupremeAssemblyConfig,
    SupremeAssemblyGovernanceGateway,
)
from src.infra.result import Ok, Result, async_returns_result

_EXCEPTION_MAP: dict[type[Exception], type[SupremeAssemblyError]] = {
    GovernanceNotConfiguredError: GovernanceNotConfiguredError,
    PermissionDeniedError: PermissionDeniedError,
    VoteAlreadyExistsError: VoteAlreadyExistsError,
    TransferValidationError: SupremeAssemblyValidationError,
    ValueError: SupremeAssemblyValidationError,
    TransferError: SupremeAssemblyError,
    RuntimeError: SupremeAssemblyError,
}


class SupremeAssemblyServiceResult:
    """Result-first facade delegating to SupremeAssemblyService."""

    derive_account_id = staticmethod(SupremeAssemblyService.derive_account_id)

    def __init__(
        self,
        *,
        gateway: SupremeAssemblyGovernanceGateway | None = None,
        transfer_service: TransferService | None = None,
        legacy_service: SupremeAssemblyService | None = None,
    ) -> None:
        if legacy_service is not None:
            self._service = legacy_service
        else:
            self._service = SupremeAssemblyService(
                gateway=gateway,
                transfer_service=transfer_service,
            )

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def set_config(
        self,
        *,
        guild_id: int,
        speaker_role_id: int,
        member_role_id: int,
    ) -> Result[SupremeAssemblyConfig, SupremeAssemblyError]:
        config = await self._service.set_config(
            guild_id=guild_id,
            speaker_role_id=speaker_role_id,
            member_role_id=member_role_id,
        )
        return Ok(config)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def get_config(
        self, *, guild_id: int
    ) -> Result[SupremeAssemblyConfig, SupremeAssemblyError]:
        config = await self._service.get_config(guild_id=guild_id)
        return Ok(config)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def get_account_balance(self, *, guild_id: int) -> Result[int, SupremeAssemblyError]:
        balance = await self._service.get_account_balance(guild_id=guild_id)
        return Ok(balance)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
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
        proposal = await self._service.create_proposal(
            guild_id=guild_id,
            proposer_id=proposer_id,
            title=title,
            description=description,
            snapshot_member_ids=snapshot_member_ids,
            deadline_hours=deadline_hours,
        )
        return Ok(proposal)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def cancel_proposal(self, *, proposal_id: UUID) -> Result[bool, SupremeAssemblyError]:
        ok = await self._service.cancel_proposal(proposal_id=proposal_id)
        return Ok(ok)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def vote(
        self,
        *,
        proposal_id: UUID,
        voter_id: int,
        choice: str,
    ) -> Result[tuple[VoteTotals, str], SupremeAssemblyError]:
        result = await self._service.vote(
            proposal_id=proposal_id,
            voter_id=voter_id,
            choice=choice,
        )
        return Ok(result)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def get_vote_totals(
        self, *, proposal_id: UUID
    ) -> Result[VoteTotals, SupremeAssemblyError]:
        totals = await self._service.get_vote_totals(proposal_id=proposal_id)
        return Ok(totals)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def expire_due_proposals(self) -> Result[int, SupremeAssemblyError]:
        changed = await self._service.expire_due_proposals()
        return Ok(changed)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def list_unvoted_members(
        self, *, proposal_id: UUID
    ) -> Result[Sequence[int], SupremeAssemblyError]:
        members = await self._service.list_unvoted_members(proposal_id=proposal_id)
        return Ok(members)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def mark_reminded(self, *, proposal_id: UUID) -> Result[None, SupremeAssemblyError]:
        await self._service.mark_reminded(proposal_id=proposal_id)
        return Ok(None)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def export_interval(
        self,
        *,
        guild_id: int,
        start: datetime,
        end: datetime,
    ) -> Result[list[dict[str, object]], SupremeAssemblyError]:
        rows = await self._service.export_interval(guild_id=guild_id, start=start, end=end)
        return Ok(rows)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def get_snapshot(
        self, *, proposal_id: UUID
    ) -> Result[Sequence[int], SupremeAssemblyError]:
        snapshot = await self._service.get_snapshot(proposal_id=proposal_id)
        return Ok(snapshot)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def get_votes_detail(
        self, *, proposal_id: UUID
    ) -> Result[Sequence[tuple[int, str]], SupremeAssemblyError]:
        details = await self._service.get_votes_detail(proposal_id=proposal_id)
        return Ok(details)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def get_proposal(
        self, *, proposal_id: UUID
    ) -> Result[Proposal | None, SupremeAssemblyError]:
        proposal = await self._service.get_proposal(proposal_id=proposal_id)
        return Ok(proposal)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def list_active_proposals(
        self, *, guild_id: int | None = None
    ) -> Result[Sequence[Proposal], SupremeAssemblyError]:
        proposals = await self._service.list_active_proposals(guild_id=guild_id)
        return Ok(proposals)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def create_summon(
        self,
        *,
        guild_id: int,
        invoked_by: int,
        target_id: int,
        target_kind: str,
        note: str | None = None,
    ) -> Result[Summon, SupremeAssemblyError]:
        summon = await self._service.create_summon(
            guild_id=guild_id,
            invoked_by=invoked_by,
            target_id=target_id,
            target_kind=target_kind,
            note=note,
        )
        return Ok(summon)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def mark_summon_delivered(self, *, summon_id: UUID) -> Result[None, SupremeAssemblyError]:
        await self._service.mark_summon_delivered(summon_id=summon_id)
        return Ok(None)

    @async_returns_result(SupremeAssemblyError, exception_map=_EXCEPTION_MAP)
    async def list_summons(
        self, *, guild_id: int, limit: int = 50
    ) -> Result[Sequence[Summon], SupremeAssemblyError]:
        summons = await self._service.list_summons(guild_id=guild_id, limit=limit)
        return Ok(summons)


__all__ = ["SupremeAssemblyServiceResult", "VoteTotals"]
