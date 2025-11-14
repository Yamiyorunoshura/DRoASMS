from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

__all__ = ["SupremeAssemblyConfig", "Proposal", "Tally", "Summon", "VoteTotals"]


@dataclass(slots=True, frozen=True)
class SupremeAssemblyConfig:
    guild_id: int
    speaker_role_id: int
    member_role_id: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class Proposal:
    proposal_id: UUID
    guild_id: int
    proposer_id: int
    title: str | None
    description: str | None
    snapshot_n: int
    threshold_t: int
    deadline_at: datetime
    status: str
    reminder_sent: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class Tally:
    approve: int
    reject: int
    abstain: int
    total_voted: int


@dataclass(slots=True, frozen=True)
class Summon:
    summon_id: UUID
    guild_id: int
    invoked_by: int
    target_id: int
    target_kind: str
    note: str | None
    delivered: bool
    delivered_at: datetime | None
    created_at: datetime


@dataclass(slots=True, frozen=True)
class VoteTotals:
    approve: int
    reject: int
    abstain: int
    threshold_t: int
    snapshot_n: int
    remaining_unvoted: int
