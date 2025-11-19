from __future__ import annotations

# noqa: D104
from typing import Any

from src.cython_ext.economy_adjustment_models import (
    AdjustmentProcedureResult,
    build_adjustment_procedure_result,
)
from src.infra.result import DatabaseError, async_returns_result
from src.infra.types.db import ConnectionProtocol


class EconomyAdjustmentGateway:
    """Encapsulate access to database-side administrative adjustments."""

    def __init__(self, *, schema: str = "economy") -> None:
        self._schema = schema

    @async_returns_result(DatabaseError, exception_map={RuntimeError: DatabaseError})
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
        sql = f"SELECT * FROM {self._schema}.fn_adjust_balance($1, $2, $3, $4, $5, $6)"
        record = await connection.fetchrow(
            sql, guild_id, admin_id, target_id, amount, reason, metadata or {}
        )
        if record is None:
            raise RuntimeError("fn_adjust_balance returned no result.")
        return build_adjustment_procedure_result(record)
