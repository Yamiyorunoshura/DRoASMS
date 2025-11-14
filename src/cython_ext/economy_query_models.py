from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

__all__ = ["BalanceRecord", "HistoryRecord"]


@dataclass(slots=True, frozen=True)
class BalanceRecord:
    guild_id: int
    member_id: int
    balance: int
    last_modified_at: datetime
    throttled_until: datetime | None


@dataclass(slots=True, frozen=True)
class HistoryRecord:
    transaction_id: UUID
    guild_id: int
    initiator_id: int
    target_id: int | None
    amount: int
    direction: str
    reason: str | None
    created_at: datetime
    metadata: dict[str, Any]
    balance_after_initiator: int
    balance_after_target: int | None
