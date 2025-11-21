from __future__ import annotations

# noqa: D104
from datetime import datetime
from typing import Any
from uuid import UUID

from src.cython_ext.pending_transfer_models import (
    PendingTransfer,
    build_pending_transfer,
)
from src.infra.result import DatabaseError, async_returns_result
from src.infra.types.db import ConnectionProtocol


class PendingTransferGateway:
    """Gateway for accessing pending transfer records."""

    def __init__(self, *, schema: str = "economy") -> None:
        self._schema = schema

    async def create_pending_transfer(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        initiator_id: int,
        target_id: int,
        amount: int,
        metadata: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> UUID:
        """Create a pending transfer record."""
        sql = f"""
        SELECT {self._schema}.fn_create_pending_transfer($1, $2, $3, $4, $5, $6)
        """
        transfer_id_raw = await connection.fetchval(
            sql,
            guild_id,
            initiator_id,
            target_id,
            amount,
            metadata or {},
            expires_at,
        )
        if transfer_id_raw is None:
            raise RuntimeError("fn_create_pending_transfer returned no result.")
        transfer_id = UUID(str(transfer_id_raw))
        return transfer_id

    async def get_pending_transfer(
        self,
        connection: ConnectionProtocol,
        *,
        transfer_id: UUID,
    ) -> PendingTransfer | None:
        """Get a pending transfer by transfer_id."""
        sql = f"SELECT * FROM {self._schema}.fn_get_pending_transfer($1)"
        record = await connection.fetchrow(sql, transfer_id)
        if record is None:
            return None
        return build_pending_transfer(record)

    async def list_pending_transfers(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PendingTransfer]:
        """List pending transfers with filtering and pagination."""
        sql = f"SELECT * FROM {self._schema}.fn_list_pending_transfers($1, $2, $3, $4)"
        records = await connection.fetch(sql, guild_id, status, limit, offset)
        return [build_pending_transfer(record) for record in records]

    async def update_status(
        self,
        connection: ConnectionProtocol,
        *,
        transfer_id: UUID,
        new_status: str,
    ) -> None:
        """Update pending transfer status."""
        sql = f"SELECT {self._schema}.fn_update_pending_transfer_status($1, $2)"
        # Function returns void, so we use execute
        await connection.execute(sql, transfer_id, new_status)

    # --- Result-based wrappers ---

    @async_returns_result(DatabaseError)
    async def create_pending_transfer_result(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        initiator_id: int,
        target_id: int,
        amount: int,
        metadata: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> UUID:
        return await self.create_pending_transfer(
            connection,
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=amount,
            metadata=metadata,
            expires_at=expires_at,
        )

    @async_returns_result(DatabaseError)
    async def get_pending_transfer_result(
        self,
        connection: ConnectionProtocol,
        *,
        transfer_id: UUID,
    ) -> PendingTransfer | None:
        return await self.get_pending_transfer(connection, transfer_id=transfer_id)

    @async_returns_result(DatabaseError)
    async def list_pending_transfers_result(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PendingTransfer]:
        return await self.list_pending_transfers(
            connection,
            guild_id=guild_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    @async_returns_result(DatabaseError)
    async def update_status_result(
        self,
        connection: ConnectionProtocol,
        *,
        transfer_id: UUID,
        new_status: str,
    ) -> None:
        await self.update_status(connection, transfer_id=transfer_id, new_status=new_status)
