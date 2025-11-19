from __future__ import annotations

# noqa: D104
from typing import Any

from src.cython_ext.economy_transfer_models import (
    TransferProcedureResult,
    build_transfer_procedure_result,
)
from src.infra.result import DatabaseError, async_returns_result
from src.infra.types.db import ConnectionProtocol


class EconomyTransferGateway:
    """Encapsulate access to database-side transfer functionality."""

    def __init__(self, *, schema: str = "economy") -> None:
        self._schema = schema

    @async_returns_result(DatabaseError, exception_map={RuntimeError: DatabaseError})
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
        return build_transfer_procedure_result(record)
