from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

__all__ = ["CouncilConfig", "CouncilRoleConfig", "Proposal", "Tally"]


@dataclass(slots=True, frozen=True)
class CouncilConfig:
    guild_id: int
    council_role_id: int
    council_account_member_id: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class CouncilRoleConfig:
    guild_id: int
    role_id: int
    created_at: datetime
    updated_at: datetime
    id: int | None = None


@dataclass(slots=True, frozen=True)
class Proposal:
    proposal_id: UUID
    guild_id: int
    proposer_id: int
    target_id: int
    amount: int
    description: str | None
    attachment_url: str | None
    snapshot_n: int
    threshold_t: int
    deadline_at: datetime
    status: str
    reminder_sent: bool
    created_at: datetime
    updated_at: datetime
    target_department_id: str | None = None


@dataclass(slots=True, frozen=True)
class Tally:
    approve: int
    reject: int
    abstain: int
    total_voted: int
