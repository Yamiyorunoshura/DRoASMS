from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Mapping, Protocol, cast
from uuid import UUID

__all__ = [
    "TransferProcedureResult",
    "TransferResult",
    "build_transfer_procedure_result",
    "transfer_result_from_procedure",
]


@dataclass(slots=True, frozen=True)
class TransferProcedureResult:
    transaction_id: UUID
    guild_id: int
    initiator_id: int
    target_id: int
    amount: int
    direction: str
    created_at: datetime
    initiator_balance: int
    target_balance: int | None
    throttled_until: datetime | None
    metadata: dict[str, Any]


@dataclass(slots=True, frozen=True)
class TransferResult:
    transaction_id: UUID | None
    guild_id: int
    initiator_id: int
    target_id: int
    amount: int
    initiator_balance: int
    target_balance: int | None
    direction: str = "transfer"
    created_at: datetime | None = None
    throttled_until: datetime | None = None
    metadata: dict[str, Any] | None = None


class _TransferRecordLike(Protocol):
    transaction_id: UUID
    guild_id: int
    initiator_id: int
    target_id: int
    amount: int
    direction: str
    created_at: datetime
    initiator_balance: int
    target_balance: int | None
    throttled_until: datetime | None
    metadata: Mapping[str, Any] | None


def _as_transfer_record_like(record: Any) -> _TransferRecordLike:
    # 已經是具備屬性存取的物件（例如測試中的 MagicMock）
    if hasattr(record, "transaction_id") and hasattr(record, "guild_id"):
        return cast(_TransferRecordLike, record)

    if isinstance(record, Mapping):
        mapping = cast(Mapping[str, Any], record)
        return cast(_TransferRecordLike, SimpleNamespace(**dict(mapping)))

    if hasattr(record, "keys") and hasattr(record, "__getitem__"):
        data: dict[str, Any] = {str(k): record[k] for k in record.keys()}
        return cast(_TransferRecordLike, SimpleNamespace(**data))

    return cast(_TransferRecordLike, record)


def build_transfer_procedure_result(record: Any) -> TransferProcedureResult:
    # Create deep copy of metadata to prevent mutation
    rec = _as_transfer_record_like(record)
    metadata = dict(getattr(rec, "metadata", {}) or {})
    return TransferProcedureResult(
        transaction_id=rec.transaction_id,
        guild_id=int(rec.guild_id),
        initiator_id=int(rec.initiator_id),
        target_id=int(rec.target_id),
        amount=int(rec.amount),
        direction=str(rec.direction),
        created_at=rec.created_at,
        initiator_balance=int(rec.initiator_balance),
        target_balance=rec.target_balance,
        throttled_until=rec.throttled_until,
        metadata=metadata,
    )


def transfer_result_from_procedure(record: TransferProcedureResult) -> TransferResult:
    metadata = dict(record.metadata or {})
    target_balance = record.target_balance if record.target_balance is not None else 0
    return TransferResult(
        transaction_id=record.transaction_id,
        guild_id=record.guild_id,
        initiator_id=record.initiator_id,
        target_id=record.target_id,
        amount=record.amount,
        initiator_balance=record.initiator_balance,
        target_balance=target_balance,
        direction=record.direction,
        created_at=record.created_at,
        throttled_until=record.throttled_until,
        metadata=metadata,
    )
