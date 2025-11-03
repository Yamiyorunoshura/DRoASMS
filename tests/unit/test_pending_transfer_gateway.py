"""Unit tests for PendingTransferGateway."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import asyncpg
import pytest

from src.db.gateway.economy_pending_transfers import (
    PendingTransfer,
    PendingTransferGateway,
)


def _snowflake() -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return secrets.randbits(63)


def _create_mock_record(
    transfer_id: UUID,
    guild_id: int,
    initiator_id: int,
    target_id: int,
    amount: int,
    status: str = "pending",
    checks: dict[str, Any] | None = None,
    retry_count: int = 0,
    expires_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> MagicMock:
    """Create a mock asyncpg.Record."""
    now = datetime.now(timezone.utc)
    data = {
        "transfer_id": transfer_id,
        "guild_id": guild_id,
        "initiator_id": initiator_id,
        "target_id": target_id,
        "amount": amount,
        "status": status,
        "checks": checks or {},
        "retry_count": retry_count,
        "expires_at": expires_at,
        "metadata": metadata or {},
        "created_at": created_at or now,
        "updated_at": updated_at or now,
    }
    mock_record = MagicMock()
    # Support dictionary-style access
    mock_record.__getitem__ = lambda self, key: data[key]
    # Also support attribute access
    for key, value in data.items():
        setattr(mock_record, key, value)
    return mock_record


@pytest.mark.asyncio
async def test_create_pending_transfer() -> None:
    """Test creating a pending transfer."""
    gateway = PendingTransferGateway()
    mock_conn = AsyncMock(spec=asyncpg.Connection)
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()
    transfer_id = uuid4()

    # Mock fetchval to return transfer_id
    mock_conn.fetchval = AsyncMock(return_value=transfer_id)

    result = await gateway.create_pending_transfer(
        mock_conn,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=100,
        metadata={"reason": "test"},
        expires_at=None,
    )

    assert result == transfer_id
    mock_conn.fetchval.assert_called_once()


@pytest.mark.asyncio
async def test_get_pending_transfer() -> None:
    """Test getting a pending transfer."""
    gateway = PendingTransferGateway()
    mock_conn = AsyncMock(spec=asyncpg.Connection)
    transfer_id = uuid4()
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    # Mock fetchrow to return a record
    mock_record = _create_mock_record(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=200,
        metadata={"test": "value"},
    )
    mock_conn.fetchrow = AsyncMock(return_value=mock_record)

    pending = await gateway.get_pending_transfer(mock_conn, transfer_id=transfer_id)
    assert pending is not None
    assert pending.transfer_id == transfer_id
    assert pending.guild_id == guild_id
    assert pending.amount == 200
    assert pending.metadata == {"test": "value"}

    # Test non-existent transfer
    mock_conn.fetchrow = AsyncMock(return_value=None)
    result = await gateway.get_pending_transfer(mock_conn, transfer_id=transfer_id)
    assert result is None


@pytest.mark.asyncio
async def test_list_pending_transfers() -> None:
    """Test listing pending transfers."""
    gateway = PendingTransferGateway()
    mock_conn = AsyncMock(spec=asyncpg.Connection)
    guild_id = _snowflake()
    transfer_id_1 = uuid4()
    transfer_id_2 = uuid4()

    # Mock fetch to return multiple records
    mock_records = [
        _create_mock_record(
            transfer_id=transfer_id_1,
            guild_id=guild_id,
            initiator_id=_snowflake(),
            target_id=_snowflake(),
            amount=100,
            status="pending",
        ),
        _create_mock_record(
            transfer_id=transfer_id_2,
            guild_id=guild_id,
            initiator_id=_snowflake(),
            target_id=_snowflake(),
            amount=200,
            status="pending",
        ),
    ]
    mock_conn.fetch = AsyncMock(return_value=mock_records)

    transfers = await gateway.list_pending_transfers(
        mock_conn,
        guild_id=guild_id,
        status=None,
        limit=10,
        offset=0,
    )

    assert len(transfers) == 2
    transfer_ids = {t.transfer_id for t in transfers}
    assert transfer_id_1 in transfer_ids
    assert transfer_id_2 in transfer_ids
    assert all(t.status == "pending" for t in transfers)


@pytest.mark.asyncio
async def test_update_status() -> None:
    """Test updating pending transfer status."""
    gateway = PendingTransferGateway()
    mock_conn = AsyncMock(spec=asyncpg.Connection)
    transfer_id = uuid4()

    # Mock execute (function returns void)
    mock_conn.execute = AsyncMock()

    await gateway.update_status(
        mock_conn,
        transfer_id=transfer_id,
        new_status="checking",
    )

    mock_conn.execute.assert_called_once()
    # Verify the SQL contains the correct status
    call_args = mock_conn.execute.call_args[0][0]
    assert "checking" in call_args or "fn_update_pending_transfer_status" in call_args


@pytest.mark.asyncio
async def test_pending_transfer_dataclass() -> None:
    """Test PendingTransfer dataclass mapping."""
    transfer_id = uuid4()
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)

    mock_record = _create_mock_record(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=150,
        status="pending",
        checks={"balance": 1},
        retry_count=0,
        expires_at=expires_at,
        metadata={"test": "value"},
        created_at=created_at,
        updated_at=updated_at,
    )

    pending = PendingTransfer.from_record(mock_record)

    assert isinstance(pending, PendingTransfer)
    assert pending.transfer_id == transfer_id
    assert pending.guild_id == guild_id
    assert pending.initiator_id == initiator_id
    assert pending.target_id == target_id
    assert pending.amount == 150
    assert pending.status == "pending"
    assert pending.checks == {"balance": 1}
    assert pending.retry_count == 0
    assert pending.metadata == {"test": "value"}
    assert pending.expires_at == expires_at
    assert pending.created_at == created_at
    assert pending.updated_at == updated_at
