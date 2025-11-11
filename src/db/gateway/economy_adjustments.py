from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from src.infra.types.db import ConnectionProtocol


@dataclass(frozen=True, slots=True)
class AdjustmentProcedureResult:
    """Result payload returned by fn_adjust_balance stored procedure."""

    transaction_id: UUID
    guild_id: int
    admin_id: int
    target_id: int
    amount: int
    direction: str
    created_at: datetime
    target_balance_after: int
    metadata: dict[str, Any]

    @classmethod
    def from_record(cls, record: asyncpg.Record) -> "AdjustmentProcedureResult":
        metadata: dict[str, Any] = dict(record["metadata"] or {})
        return cls(
            transaction_id=record["transaction_id"],
            guild_id=record["guild_id"],
            admin_id=record["admin_id"],
            target_id=record["target_id"],
            amount=record["amount"],
            direction=str(record["direction"]),
            created_at=record["created_at"],
            target_balance_after=record["target_balance_after"],
            metadata=metadata,
        )


class EconomyAdjustmentGateway:
    """Encapsulate access to database-side administrative adjustments."""

    def __init__(self, *, schema: str = "economy") -> None:
        self._schema = schema

    async def adjust_balance(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        admin_id: int,
        target_id: int,
        amount: int,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> AdjustmentProcedureResult:
        sql = f"SELECT * FROM {self._schema}.fn_adjust_balance(" "$1, $2, $3, $4, $5, $6)"
        record = await connection.fetchrow(
            sql, guild_id, admin_id, target_id, amount, reason, metadata or {}
        )
        if record is None:
            raise RuntimeError("fn_adjust_balance returned no result.")
        return AdjustmentProcedureResult.from_record(record)
