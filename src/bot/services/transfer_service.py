from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import asyncpg
import structlog

from src.cython_ext.economy_transfer_models import (
    TransferResult,
    transfer_result_from_procedure,
)
from src.db.gateway.economy_pending_transfers import PendingTransferGateway
from src.db.gateway.economy_transfers import (
    EconomyTransferGateway,
    TransferProcedureResult,
)
from src.infra.result import (
    BusinessLogicError,
    DatabaseError,
    Err,
    Error,
    Ok,
    Result,
    ValidationError,
)
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)


class TransferError(Error):
    """Base error raised for transfer-related failures."""


class TransferValidationError(TransferError):
    """Raised when validation fails before reaching the database."""


class InsufficientBalanceError(TransferError):
    """Raised when the initiator lacks sufficient balance."""

    def __init__(self, message: str = "Insufficient balance for transfer", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class TransferThrottleError(TransferError):
    """Raised when the initiator is throttled by daily limits."""

    def __init__(
        self, message: str = "Transfer throttled due to daily limits", **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)


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

        Returns TransferResult in同步模式，或在事件池模式下回傳 transfer_id(UUID)。
        發生錯誤時以 TransferError / ValidationError / DatabaseError 等例外表示。
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

            try:
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
            except Exception as e:
                LOGGER.exception("transfer_service.pending_transfer_error")
                raise TransferError(f"Failed to create pending transfer: {e}") from e

        # Synchronous mode (original behavior)
        if connection is not None:
            base_result = await self._execute_transfer(
                connection,
                guild_id=guild_id,
                initiator_id=initiator_id,
                target_id=target_id,
                amount=amount,
                metadata=transfer_metadata,
            )
        else:
            async with self._pool.acquire() as pooled_connection:
                base_result = await self._execute_transfer(
                    pooled_connection,
                    guild_id=guild_id,
                    initiator_id=initiator_id,
                    target_id=target_id,
                    amount=amount,
                    metadata=transfer_metadata,
                )
        # 依 Result 映射為例外或成功結果
        if base_result.is_err():
            error = base_result.unwrap_err()
            # 驗證錯誤 → 轉成 TransferValidationError
            if isinstance(error, ValidationError):
                raise TransferValidationError(error.message)
            # 業務邏輯錯誤：依 context 映射為特定 TransferError
            if isinstance(error, BusinessLogicError):
                err_type = error.context.get("error_type")
                if err_type == "insufficient_balance":
                    raise InsufficientBalanceError(error.message)
                if err_type == "throttle":
                    raise TransferThrottleError(error.message)
                raise TransferError(error.message)
            # 其餘資料庫錯誤 → 一律視為 TransferError 包裝
            raise TransferError(getattr(error, "message", str(error)))

        return base_result.unwrap()

    async def _execute_transfer(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        initiator_id: int,
        target_id: int,
        amount: int,
        metadata: dict[str, Any],
    ) -> Result[TransferResult, DatabaseError | BusinessLogicError | ValidationError]:
        """Execute the transfer and map DB errors to domain errors.

        注意：EconomyTransferGateway.transfer_currency 已透過 async_returns_result
        轉為 Result 介面。我們在這裡自行管理一層 transaction/savepoint：
        - 成功時 commit，讓變更持久化於目前測試交易中；
        - 失敗時 rollback，此時仍保留 gateway 回傳的錯誤內容，以避免僅看到
          `InFailedSQLTransactionError` 而遺失真正的失敗原因（例如餘額不足）。
        """
        tx = connection.transaction()
        await tx.start()
        try:
            gateway_result = await self._gateway.transfer_currency(
                connection,
                guild_id=guild_id,
                initiator_id=initiator_id,
                target_id=target_id,
                amount=amount,
                metadata=metadata,
            )

            # EconomyTransferGateway is decorated with async_returns_result, so it always
            # returns Result[TransferProcedureResult, Error] rather than raising.
            if gateway_result.is_err():
                error = gateway_result.unwrap_err()
                cause = getattr(error, "cause", None)

                # If the underlying cause was a PostgresError, map it to business/validation errors.
                if isinstance(cause, asyncpg.PostgresError):
                    mapped_error = self._handle_postgres_error(cause)
                    await tx.rollback()
                    return Err(mapped_error)

                # Otherwise propagate DatabaseError as-is when possible.
                await tx.rollback()
                return Err(error)

            db_result = gateway_result.unwrap()
            await tx.commit()
            return Ok(self._to_result(db_result))
        except Exception as e:  # pragma: no cover - 防禦性日誌
            try:
                await tx.rollback()
            except Exception:
                pass
            LOGGER.exception("transfer_service.execute_transfer_internal_error")
            return Err(DatabaseError(f"Transaction failed: {e}"))

    def _to_result(self, db_result: TransferProcedureResult) -> TransferResult:
        return transfer_result_from_procedure(db_result)

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
    def _handle_postgres_error(
        exc: asyncpg.PostgresError,
    ) -> BusinessLogicError | ValidationError | DatabaseError:
        message = (exc.args[0] if exc.args else "").lower()
        sqlstate = getattr(exc, "sqlstate", None)
        if sqlstate == "P0001" and "insufficient" in message:
            return BusinessLogicError(
                message=exc.args[0],
                context={"sqlstate": sqlstate, "error_type": "insufficient_balance"},
            )
        if sqlstate == "P0001" and "throttle" in message:
            return BusinessLogicError(
                message=exc.args[0],
                context={"sqlstate": sqlstate, "error_type": "throttle"},
            )
        if sqlstate == "22023":
            return ValidationError(
                message=exc.args[0],
                context={"sqlstate": sqlstate, "error_type": "validation"},
            )

        LOGGER.exception("transfer_service.database_error", sqlstate=sqlstate)
        return DatabaseError("Transfer failed due to an unexpected database error.")
