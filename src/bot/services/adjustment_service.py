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
from src.infra.result import DatabaseError, Err, Ok, Result, ValidationError
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)


class AdjustmentError(RuntimeError):
    """Base error raised for adjustment-related failures."""


class UnauthorizedAdjustmentError(AdjustmentError):
    """Raised when a requester lacks permission to perform adjustments."""


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
    ) -> AdjustmentResult | Result[AdjustmentResult, DatabaseError | ValidationError]:
        """Apply an administrative balance adjustment.

        Dual-mode 合約：
        - 當 `connection` 提供時，採用舊版 service 合約：
          - 無權限時丟出 UnauthorizedAdjustmentError
          - 驗證失敗（包含餘額不可 < 0）時丟出 ValidationError
          - 成功時直接回傳 AdjustmentResult
        - 當 `connection` 為 None 時，採用 Result 合約（供 DI / 指令層使用）：
          - 回傳 Result[AdjustmentResult, DatabaseError | ValidationError]
        """
        metadata: dict[str, Any] = {"reason": reason}

        async def _run(
            conn: ConnectionProtocol,
        ) -> Result[AdjustmentResult, DatabaseError | ValidationError]:
            """呼叫 Gateway 並將 asyncpg/Postgres 錯誤映射為 ValidationError / DatabaseError。"""
            result = await self._gateway.adjust_balance(
                conn,
                guild_id=guild_id,
                admin_id=admin_id,
                target_id=target_id,
                amount=amount,
                reason=reason,
                metadata=metadata,
            )
            if result.is_err():
                error = result.unwrap_err()
                cause = getattr(error, "cause", None)

                # 針對 asyncpg.PostgresError 依訊息內容做細部映射
                if isinstance(cause, asyncpg.PostgresError):
                    mapped = self._handle_postgres_error(cause)
                    if mapped.is_err():
                        return Err(mapped.unwrap_err())

                return Err(error)

            record = result.unwrap()
            return Ok(self._to_result(record))

        # --- Domain / legacy mode: explicit connection, raise exceptions,
        #     and return AdjustmentResult ---
        if connection is not None:
            # 前置驗證：失敗時以例外表示，符合舊有經濟與整合測試期待。
            if not can_adjust:
                raise UnauthorizedAdjustmentError(
                    "You do not have permission to adjust member balances."
                )
            if not reason or not reason.strip():
                raise ValidationError("Adjustment reason is required.")
            if amount == 0:
                raise ValidationError("Adjustment amount must be non-zero.")

            base_result = await _run(connection)
            if base_result.is_err():
                error = base_result.unwrap_err()
                # SQL constraint / 商業邏輯錯誤 → ValidationError
                if isinstance(error, ValidationError):
                    raise error
                # 其餘資料庫錯誤直接拋出，讓上層視情況包裝或記錄
                raise error

            return base_result.unwrap()

        # --- Result mode: for DI / slash command usage, keep Result contract ---
        # Validate input parameters and surface errors as ValidationError inside Result.
        if not can_adjust:
            return Err(ValidationError("You do not have permission to adjust member balances."))
        if not reason or not reason.strip():
            return Err(ValidationError("Adjustment reason is required."))
        if amount == 0:
            return Err(ValidationError("Adjustment amount must be non-zero."))

        async with self._pool.acquire() as pooled_connection:
            return await _run(pooled_connection)

    def _handle_postgres_error(
        self, exc: asyncpg.PostgresError
    ) -> Result[None, ValidationError | DatabaseError]:
        message = str(exc).lower()
        if "cannot drop below zero" in message:
            return Err(ValidationError("Adjustment denied: balance cannot drop below zero."))
        LOGGER.exception("adjustment.unexpected_db_error", error=str(exc))
        return Err(DatabaseError("Unexpected error while applying adjustment."))

    def _to_result(self, record: AdjustmentProcedureResult) -> AdjustmentResult:
        return adjustment_result_from_procedure(record)

    def _exception_to_result(self, exc: Exception) -> Err[AdjustmentResult, DatabaseError]:
        """Convert service exceptions to DatabaseError Result."""
        if isinstance(exc, (UnauthorizedAdjustmentError, ValidationError, AdjustmentError)):
            return Err(
                DatabaseError(message=str(exc), context={"original_exception": type(exc).__name__})
            )
        else:
            return Err(
                DatabaseError(
                    message=f"Unexpected error: {str(exc)}",
                    context={"original_exception": type(exc).__name__},
                )
            )
