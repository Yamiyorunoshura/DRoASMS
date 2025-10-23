from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg
import structlog

from src.db.gateway.economy_transfers import (
    EconomyTransferGateway,
    TransferProcedureResult,
)

LOGGER = structlog.get_logger(__name__)


class TransferError(RuntimeError):
    """Base error raised for transfer-related failures."""


class TransferValidationError(TransferError):
    """Raised when validation fails before reaching the database."""


class InsufficientBalanceError(TransferError):
    """Raised when the initiator lacks sufficient balance."""


class TransferThrottleError(TransferError):
    """Raised when the initiator is throttled by daily limits."""


@dataclass(frozen=True, slots=True)
class TransferResult:
    """Value object returned after a successful transfer."""

    transaction_id: UUID
    guild_id: int
    initiator_id: int
    target_id: int
    amount: int
    initiator_balance: int
    target_balance: int
    direction: str
    created_at: datetime
    throttled_until: datetime | None
    metadata: dict[str, Any]


class TransferService:
    """Coordinate validation and database interaction for currency transfers."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        gateway: EconomyTransferGateway | None = None,
    ) -> None:
        self._pool = pool
        self._gateway = gateway or EconomyTransferGateway()

    async def transfer_currency(
        self,
        *,
        guild_id: int,
        initiator_id: int,
        target_id: int,
        amount: int,
        reason: str | None = None,
        connection: asyncpg.Connection | None = None,
    ) -> TransferResult:
        if initiator_id == target_id:
            raise TransferValidationError("Initiator and target must be different members.")
        if amount <= 0:
            raise TransferValidationError("Transfer amount must be a positive whole number.")

        metadata: dict[str, Any] = {}
        if reason:
            metadata["reason"] = reason

        if connection is not None:
            return await self._execute_transfer(
                connection,
                guild_id=guild_id,
                initiator_id=initiator_id,
                target_id=target_id,
                amount=amount,
                metadata=metadata,
            )

        async with self._pool.acquire() as pooled_connection:
            return await self._execute_transfer(
                pooled_connection,
                guild_id=guild_id,
                initiator_id=initiator_id,
                target_id=target_id,
                amount=amount,
                metadata=metadata,
            )

    async def _execute_transfer(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        initiator_id: int,
        target_id: int,
        amount: int,
        metadata: dict[str, Any],
    ) -> TransferResult:
        async with connection.transaction():
            try:
                result = await self._gateway.transfer_currency(
                    connection,
                    guild_id=guild_id,
                    initiator_id=initiator_id,
                    target_id=target_id,
                    amount=amount,
                    metadata=metadata,
                )
            except asyncpg.PostgresError as exc:
                self._handle_postgres_error(exc)
                raise  # pragma: no cover

        return self._to_result(result)

    def _to_result(self, db_result: TransferProcedureResult) -> TransferResult:
        target_balance = db_result.target_balance if db_result.target_balance is not None else 0
        metadata = dict(db_result.metadata or {})
        return TransferResult(
            transaction_id=db_result.transaction_id,
            guild_id=db_result.guild_id,
            initiator_id=db_result.initiator_id,
            target_id=db_result.target_id,
            amount=db_result.amount,
            initiator_balance=db_result.initiator_balance,
            target_balance=target_balance,
            direction=db_result.direction,
            created_at=db_result.created_at,
            throttled_until=db_result.throttled_until,
            metadata=metadata,
        )

    @staticmethod
    def _handle_postgres_error(exc: asyncpg.PostgresError) -> None:
        message = (exc.args[0] if exc.args else "").lower()
        if exc.sqlstate == "P0001" and "insufficient" in message:
            raise InsufficientBalanceError(exc.args[0]) from exc
        if exc.sqlstate == "P0001" and "throttle" in message:
            raise TransferThrottleError(exc.args[0]) from exc
        if exc.sqlstate == "22023":
            raise TransferValidationError(exc.args[0]) from exc

        LOGGER.exception("transfer_service.database_error", sqlstate=exc.sqlstate)
        raise TransferError("Transfer failed due to an unexpected database error.") from exc
