from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Mapping, Protocol, cast
from uuid import UUID

__all__ = ["PendingTransfer", "build_pending_transfer"]


@dataclass(slots=True, frozen=True)
class PendingTransfer:
    transfer_id: UUID
    guild_id: int
    initiator_id: int
    target_id: int
    amount: int
    status: str
    checks: dict[str, Any]
    retry_count: int
    expires_at: datetime | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class _PendingTransferRecordLike(Protocol):
    transfer_id: UUID
    guild_id: int
    initiator_id: int
    target_id: int
    amount: int
    status: str
    checks: Mapping[str, Any] | None
    retry_count: int
    expires_at: datetime | None
    metadata: Mapping[str, Any] | None
    created_at: datetime
    updated_at: datetime


def _as_pending_transfer_record_like(record: Any) -> _PendingTransferRecordLike:
    if isinstance(record, dict):
        return cast(_PendingTransferRecordLike, SimpleNamespace(**record))
    return cast(_PendingTransferRecordLike, record)


def build_pending_transfer(record: Any) -> PendingTransfer:
    rec = _as_pending_transfer_record_like(record)
    checks = dict(rec.checks or {})
    metadata = dict(rec.metadata or {})
    return PendingTransfer(
        transfer_id=rec.transfer_id,
        guild_id=int(rec.guild_id),
        initiator_id=int(rec.initiator_id),
        target_id=int(rec.target_id),
        amount=int(rec.amount),
        status=str(rec.status),
        checks=checks,
        retry_count=int(rec.retry_count),
        expires_at=rec.expires_at,
        metadata=metadata,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )
