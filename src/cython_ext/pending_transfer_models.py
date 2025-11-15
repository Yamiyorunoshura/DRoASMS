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

    @classmethod
    def from_record(cls, record: Any) -> "PendingTransfer":
        """建構 PendingTransfer，提供與 gateway 測試相容的簡易工廠。"""
        return build_pending_transfer(record)


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
    # 已經是具備屬性存取的物件（例如測試中的 MagicMock）
    if hasattr(record, "transfer_id") and hasattr(record, "guild_id"):
        return cast(_PendingTransferRecordLike, record)

    if isinstance(record, Mapping):
        # asyncpg.Record 或一般 dict 皆實作 Mapping 介面：
        # 轉成 SimpleNamespace 以支援屬性存取模式。
        mapping = cast(Mapping[str, Any], record)
        return cast(_PendingTransferRecordLike, SimpleNamespace(**dict(mapping)))

    # 部分實作僅提供 keys/__getitem__，但未註冊為 Mapping
    if hasattr(record, "keys") and hasattr(record, "__getitem__"):
        data: dict[str, Any] = {str(k): record[k] for k in record.keys()}
        return cast(_PendingTransferRecordLike, SimpleNamespace(**data))

    return cast(_PendingTransferRecordLike, record)


def build_pending_transfer(record: Any) -> PendingTransfer:
    rec = _as_pending_transfer_record_like(record)
    # 某些查詢（例如合約測試中的 fn_get_pending_transfer）可能尚未包含 checks 欄位，
    # 因此這裡以 getattr 提供向後相容的預設值。
    checks = dict(getattr(rec, "checks", {}) or {})
    metadata = dict(getattr(rec, "metadata", {}) or {})
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
