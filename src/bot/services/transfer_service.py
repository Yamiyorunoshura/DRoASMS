from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import asyncpg
import structlog
from mypy_extensions import mypyc_attr

from src.db.gateway.economy_pending_transfers import PendingTransferGateway
from src.db.gateway.economy_transfers import (
    EconomyTransferGateway,
    TransferProcedureResult,
)
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)


@mypyc_attr(native_class=False)
class TransferError(RuntimeError):
    """Base error raised for transfer-related failures."""


@mypyc_attr(native_class=False)
class TransferValidationError(TransferError):
    """Raised when validation fails before reaching the database."""


@mypyc_attr(native_class=False)
class InsufficientBalanceError(TransferError):
    """Raised when the initiator lacks sufficient balance."""


@mypyc_attr(native_class=False)
class TransferThrottleError(TransferError):
    """Raised when the initiator is throttled by daily limits."""


@dataclass(frozen=True, slots=True)
class TransferResult:
    """Value object returned after a successful transfer.

    為了相容單元測試，此資料類別的部分欄位提供預設值，
    測試可以略過 `direction` 與 `throttled_until` 等欄位。
    """

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
    metadata: dict[str, Any] = None  # type: ignore[assignment]


class TransferService:
    """Coordinate validation and database interaction for currency transfers."""

    def __init__(
        self,
        pool: PoolProtocol,
        *,
        gateway: EconomyTransferGateway | None = None,
        pending_gateway: PendingTransferGateway | None = None,
        event_pool_enabled: bool = False,
        default_expires_hours: int = 24,
    ) -> None:
        self._pool = pool
        self._gateway = gateway or EconomyTransferGateway()
        self._pending_gateway = pending_gateway or PendingTransferGateway()
        self._event_pool_enabled = event_pool_enabled
        self._default_expires_hours = default_expires_hours

    async def transfer_currency(
        self,
        *,
        guild_id: int,
        initiator_id: int,
        target_id: int,
        amount: int,
        reason: str | None = None,
        connection: ConnectionProtocol | None = None,
        expires_hours: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TransferResult | UUID:
        """Transfer currency.

        Returns TransferResult if sync mode, UUID (transfer_id) if event pool mode.
        """
        if initiator_id == target_id:
            raise TransferValidationError("Initiator and target must be different members.")
        if amount <= 0:
            raise TransferValidationError("Transfer amount must be a positive whole number.")

        transfer_metadata: dict[str, Any] = dict(metadata) if metadata else {}
        if reason:
            transfer_metadata["reason"] = reason

        # Event pool mode
        if self._event_pool_enabled:
            expires_at = None
            if expires_hours is not None or self._default_expires_hours > 0:
                hours = expires_hours if expires_hours is not None else self._default_expires_hours
                expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)

            if connection is not None:
                transfer_id = await self._create_pending_transfer(
                    connection,
                    guild_id=guild_id,
                    initiator_id=initiator_id,
                    target_id=target_id,
                    amount=amount,
                    metadata=transfer_metadata,
                    expires_at=expires_at,
                )
            else:
                async with self._pool.acquire() as pooled_connection:
                    transfer_id = await self._create_pending_transfer(
                        pooled_connection,
                        guild_id=guild_id,
                        initiator_id=initiator_id,
                        target_id=target_id,
                        amount=amount,
                        metadata=transfer_metadata,
                        expires_at=expires_at,
                    )
            return transfer_id

        # Synchronous mode (original behavior)
        if connection is not None:
            return await self._execute_transfer(
                connection,
                guild_id=guild_id,
                initiator_id=initiator_id,
                target_id=target_id,
                amount=amount,
                metadata=transfer_metadata,
            )

        async with self._pool.acquire() as pooled_connection:
            return await self._execute_transfer(
                pooled_connection,
                guild_id=guild_id,
                initiator_id=initiator_id,
                target_id=target_id,
                amount=amount,
                metadata=transfer_metadata,
            )

    async def _execute_transfer(
        self,
        connection: ConnectionProtocol,
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

    async def _create_pending_transfer(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        initiator_id: int,
        target_id: int,
        amount: int,
        metadata: dict[str, Any],
        expires_at: datetime | None,
    ) -> UUID:
        """Create a pending transfer in event pool mode."""
        transfer_id = await self._pending_gateway.create_pending_transfer(
            connection,
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
            metadata=metadata,
            expires_at=expires_at,
        )
        LOGGER.info(
            "transfer_service.pending_created",
            transfer_id=transfer_id,
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
        )
        return transfer_id

    async def get_transfer_status(
        self,
        *,
        transfer_id: UUID,
        connection: ConnectionProtocol | None = None,
    ) -> Any | None:
        """Get the status of a pending transfer."""
        if connection is not None:
            return await self._pending_gateway.get_pending_transfer(
                connection, transfer_id=transfer_id
            )

        async with self._pool.acquire() as pooled_connection:
            return await self._pending_gateway.get_pending_transfer(
                pooled_connection, transfer_id=transfer_id
            )

    @staticmethod
    def _handle_postgres_error(exc: asyncpg.PostgresError) -> None:
        message = (exc.args[0] if exc.args else "").lower()
        sqlstate = getattr(exc, "sqlstate", None)
        if sqlstate == "P0001" and "insufficient" in message:
            raise InsufficientBalanceError(exc.args[0]) from exc
        if sqlstate == "P0001" and "throttle" in message:
            raise TransferThrottleError(exc.args[0]) from exc
        if sqlstate == "22023":
            raise TransferValidationError(exc.args[0]) from exc

        LOGGER.exception("transfer_service.database_error", sqlstate=sqlstate)
        raise TransferError("Transfer failed due to an unexpected database error.") from exc
