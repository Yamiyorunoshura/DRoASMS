from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from src.infra.types.db import ConnectionProtocol


@dataclass(frozen=True, slots=True)
class TransferProcedureResult:
    """Result payload returned by the fn_transfer_currency stored procedure."""

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

    @classmethod
    def from_record(cls, record: asyncpg.Record) -> "TransferProcedureResult":
        metadata: dict[str, Any] = dict(record["metadata"] or {})
        return cls(
            transaction_id=record["transaction_id"],
            guild_id=record["guild_id"],
            initiator_id=record["initiator_id"],
            target_id=record["target_id"],
            amount=record["amount"],
            direction=str(record["direction"]),
            created_at=record["created_at"],
            initiator_balance=record["initiator_balance"],
            target_balance=record["target_balance"],
            throttled_until=record["throttled_until"],
            metadata=metadata,
        )


class EconomyTransferGateway:
    """Encapsulate access to database-side transfer functionality."""

    def __init__(self, *, schema: str = "economy") -> None:
        self._schema = schema

    async def transfer_currency(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        initiator_id: int,
        target_id: int,
        amount: int,
        metadata: dict[str, Any] | None = None,
    ) -> TransferProcedureResult:
        sql = f"SELECT * FROM {self._schema}.fn_transfer_currency($1, $2, $3, $4, $5)"
        record = await connection.fetchrow(
            sql,
            guild_id,
            initiator_id,
            target_id,
            amount,
            metadata or {},
        )
        if record is None:
            raise RuntimeError("fn_transfer_currency returned no result.")
        return TransferProcedureResult.from_record(record)
