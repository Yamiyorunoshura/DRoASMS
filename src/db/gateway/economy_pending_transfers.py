from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from src.infra.types.db import ConnectionProtocol


@dataclass(frozen=True, slots=True)
class PendingTransfer:
    """Data class representing a pending transfer record."""

    transfer_id: UUID
    guild_id: int
    initiator_id: int
    target_id: int
    amount: int
    status: str
    checks: dict[str, Any]
    retry_count: int
    expires_at: datetime | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: asyncpg.Record) -> "PendingTransfer":
        checks: dict[str, Any] = dict(record["checks"] or {})
        metadata: dict[str, Any] = dict(record["metadata"] or {})
        return cls(
            transfer_id=record["transfer_id"],
            guild_id=record["guild_id"],
            initiator_id=record["initiator_id"],
            target_id=record["target_id"],
            amount=record["amount"],
            status=str(record["status"]),
            checks=checks,
            retry_count=record["retry_count"],
            expires_at=record["expires_at"],
            metadata=metadata,
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )


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
        return PendingTransfer.from_record(record)

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
        return [PendingTransfer.from_record(record) for record in records]

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
