from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

__all__ = [
    "BalanceSnapshot",
    "HistoryEntry",
    "HistoryPage",
    "make_balance_snapshot",
    "make_history_entry",
    "ensure_view_permission",
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, frozen=True)
class BalanceSnapshot:
    """Python fallback implementation mirrored by the Cython cdef class."""

    guild_id: int = 0
    member_id: int = 0
    balance: int = 0
    last_modified_at: datetime = field(default_factory=_now_utc)
    throttled_until: datetime | None = None

    def __init__(
        self,
        *,
        guild_id: int = 0,
        member_id: int = 0,
        balance: int = 0,
        last_modified_at: datetime | None = None,
        throttled_until: datetime | None = None,
        is_throttled: bool | None = None,  # Backward compatibility
    ) -> None:
        object.__setattr__(self, "guild_id", guild_id)
        object.__setattr__(self, "member_id", member_id)
        object.__setattr__(self, "balance", balance)
        object.__setattr__(self, "last_modified_at", last_modified_at or _now_utc())
        object.__setattr__(self, "throttled_until", throttled_until)

    @property
    def is_throttled(self) -> bool:
        if self.throttled_until is None:
            return False
        return self.throttled_until > _now_utc()


@dataclass(slots=True, frozen=True)
class HistoryEntry:
    """Python fallback implementation mirrored by the Cython cdef class."""

    transaction_id: object
    guild_id: int
    member_id: int
    initiator_id: int
    target_id: int | None
    amount: int
    direction: str
    reason: str | None
    created_at: datetime
    metadata: dict[str, object]
    balance_after_initiator: int
    balance_after_target: int | None

    @property
    def is_credit(self) -> bool:
        return self.target_id == self.member_id

    @property
    def is_debit(self) -> bool:
        return self.initiator_id == self.member_id and not self.is_credit


@dataclass(slots=True, frozen=True)
class HistoryPage:
    """Container for history entries."""

    items: Sequence[HistoryEntry]
    next_cursor: datetime | None


def make_balance_snapshot(record: Any) -> BalanceSnapshot:
    """Convert BalanceRecord-like object to BalanceSnapshot."""
    return BalanceSnapshot(
        guild_id=record.guild_id,
        member_id=record.member_id,
        balance=record.balance,
        last_modified_at=record.last_modified_at,
        throttled_until=record.throttled_until,
    )


def make_history_entry(record: Any, member_id: int) -> HistoryEntry:
    """Convert HistoryRecord-like object to HistoryEntry."""
    metadata = dict(getattr(record, "metadata", {}) or {})
    return HistoryEntry(
        transaction_id=record.transaction_id,
        guild_id=record.guild_id,
        member_id=member_id,
        initiator_id=record.initiator_id,
        target_id=record.target_id,
        amount=record.amount,
        direction=record.direction,
        reason=record.reason,
        created_at=record.created_at,
        metadata=metadata,
        balance_after_initiator=record.balance_after_initiator,
        balance_after_target=record.balance_after_target,
    )


def ensure_view_permission(
    requester_id: int, target_id: int, can_view_others: bool, error_type: type[Exception]
) -> None:
    """Validate permissions, raising the provided error type on violation."""
    if requester_id != target_id and not can_view_others:
        raise error_type("You do not have permission to view other members' balances.")
