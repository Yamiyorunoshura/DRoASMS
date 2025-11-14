from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Mapping, Protocol, cast
from uuid import UUID

__all__ = [
    "AdjustmentProcedureResult",
    "AdjustmentResult",
    "build_adjustment_procedure_result",
    "adjustment_result_from_procedure",
]


@dataclass(slots=True, frozen=True)
class AdjustmentProcedureResult:
    transaction_id: UUID
    guild_id: int
    admin_id: int
    target_id: int
    amount: int
    direction: str
    created_at: datetime
    target_balance_after: int
    metadata: dict[str, Any]


@dataclass(slots=True, frozen=True)
class AdjustmentResult:
    transaction_id: UUID
    guild_id: int
    admin_id: int
    target_id: int
    amount: int
    direction: str
    created_at: datetime
    target_balance_after: int
    metadata: dict[str, Any]


class _AdjustmentRecordLike(Protocol):
    transaction_id: UUID
    guild_id: int
    admin_id: int
    target_id: int
    amount: int
    direction: str
    created_at: datetime
    target_balance_after: int
    metadata: Mapping[str, Any] | None


def _as_adjustment_record_like(record: Any) -> _AdjustmentRecordLike:
    if isinstance(record, dict):
        # asyncpg.Record and plain dict can both be converted safely
        return cast(_AdjustmentRecordLike, SimpleNamespace(**record))
    return cast(_AdjustmentRecordLike, record)


def build_adjustment_procedure_result(record: Any) -> AdjustmentProcedureResult:
    rec = _as_adjustment_record_like(record)
    metadata = dict(rec.metadata or {})
    return AdjustmentProcedureResult(
        transaction_id=rec.transaction_id,
        guild_id=int(rec.guild_id),
        admin_id=int(rec.admin_id),
        target_id=int(rec.target_id),
        amount=int(rec.amount),
        direction=str(rec.direction),
        created_at=rec.created_at,
        target_balance_after=int(rec.target_balance_after),
        metadata=metadata,
    )


def adjustment_result_from_procedure(record: AdjustmentProcedureResult) -> AdjustmentResult:
    metadata = dict(record.metadata or {})
    return AdjustmentResult(
        transaction_id=record.transaction_id,
        guild_id=record.guild_id,
        admin_id=record.admin_id,
        target_id=record.target_id,
        amount=record.amount,
        direction=record.direction,
        created_at=record.created_at,
        target_balance_after=record.target_balance_after,
        metadata=metadata,
    )
