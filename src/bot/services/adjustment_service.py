from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg
import structlog
from mypy_extensions import mypyc_attr

from src.db.gateway.economy_adjustments import (
    AdjustmentProcedureResult,
    EconomyAdjustmentGateway,
)

LOGGER = structlog.get_logger(__name__)


@mypyc_attr(native_class=False)
class AdjustmentError(RuntimeError):
    """Base error raised for adjustment-related failures."""


@mypyc_attr(native_class=False)
class UnauthorizedAdjustmentError(AdjustmentError):
    """Raised when a requester lacks permission to perform adjustments."""


@mypyc_attr(native_class=False)
class ValidationError(AdjustmentError):
    """Raised when validation fails before reaching the database."""


@dataclass(frozen=True, slots=True)
class AdjustmentResult:
    """Value object returned after a successful admin adjustment."""

    transaction_id: UUID
    guild_id: int
    admin_id: int
    target_id: int
    amount: int
    direction: str
    created_at: datetime
    target_balance_after: int
    metadata: dict[str, Any]


class AdjustmentService:
    """Coordinate permission checks and DB interaction for admin adjustments."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        gateway: EconomyAdjustmentGateway | None = None,
    ) -> None:
        self._pool = pool
        self._gateway = gateway or EconomyAdjustmentGateway()

    async def adjust_balance(
        self,
        *,
        guild_id: int,
        admin_id: int,
        target_id: int,
        amount: int,
        reason: str,
        can_adjust: bool,
        connection: asyncpg.Connection | None = None,
    ) -> AdjustmentResult:
        if not can_adjust:
            raise UnauthorizedAdjustmentError(
                "You do not have permission to adjust member balances."
            )
        if not reason or not reason.strip():
            raise ValidationError("Adjustment reason is required.")
        if amount == 0:
            raise ValidationError("Adjustment amount must be non-zero.")

        metadata: dict[str, Any] = {"reason": reason}

        async def _run(conn: asyncpg.Connection) -> AdjustmentResult:
            try:
                result = await self._gateway.adjust_balance(
                    conn,
                    guild_id=guild_id,
                    admin_id=admin_id,
                    target_id=target_id,
                    amount=amount,
                    reason=reason,
                    metadata=metadata,
                )
            except asyncpg.PostgresError as exc:
                self._handle_postgres_error(exc)
                raise  # pragma: no cover
            return self._to_result(result)

        if connection is not None:
            return await _run(connection)

        async with self._pool.acquire() as pooled_connection:
            return await _run(pooled_connection)

    def _handle_postgres_error(self, exc: asyncpg.PostgresError) -> None:
        message = str(exc).lower()
        if "cannot drop below zero" in message:
            raise ValidationError("Adjustment denied: balance cannot drop below zero.") from exc
        LOGGER.exception("adjustment.unexpected_db_error", error=str(exc))
        raise AdjustmentError("Unexpected error while applying adjustment.") from exc

    def _to_result(self, record: AdjustmentProcedureResult) -> AdjustmentResult:
        return AdjustmentResult(
            transaction_id=record.transaction_id,
            guild_id=record.guild_id,
            admin_id=record.admin_id,
            target_id=record.target_id,
            amount=record.amount,
            direction=record.direction,
            created_at=record.created_at,
            target_balance_after=record.target_balance_after,
            metadata=record.metadata,
        )
