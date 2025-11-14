from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from src.cython_ext.economy_adjustment_models import (
    AdjustmentResult,
    adjustment_result_from_procedure,
)
from src.db.gateway.economy_adjustments import (
    AdjustmentProcedureResult,
    EconomyAdjustmentGateway,
)
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)


class AdjustmentError(RuntimeError):
    """Base error raised for adjustment-related failures."""


class UnauthorizedAdjustmentError(AdjustmentError):
    """Raised when a requester lacks permission to perform adjustments."""


class ValidationError(AdjustmentError):
    """Raised when validation fails before reaching the database."""


class AdjustmentService:
    """Coordinate permission checks and DB interaction for admin adjustments."""

    def __init__(
        self,
        pool: PoolProtocol,
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
        connection: ConnectionProtocol | None = None,
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

        async def _run(conn: ConnectionProtocol) -> AdjustmentResult:
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
        return adjustment_result_from_procedure(record)
