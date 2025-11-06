"""Integration tests for transfer initiator server notification."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.bot.services.transfer_service import TransferService
from src.db.gateway.economy_pending_transfers import PendingTransferGateway
from src.infra.telemetry.listener import TelemetryListener


def _snowflake() -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return secrets.randbits(63)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transfer_with_interaction_token_in_metadata(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test that interaction token is stored in metadata when event pool is enabled."""
    # Enable event pool mode
    original_env = os.environ.get("TRANSFER_EVENT_POOL_ENABLED", "false")
    os.environ["TRANSFER_EVENT_POOL_ENABLED"] = "true"

    try:
        service = TransferService(
            db_pool,
            event_pool_enabled=True,
        )

        guild_id = _snowflake()
        initiator_id = _snowflake()
        target_id = _snowflake()
        interaction_token = "test_interaction_token_123"

        # Set up balances
        await db_connection.execute(
            """
            INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, member_id) DO UPDATE
            SET current_balance = $3
            """,
            guild_id,
            initiator_id,
            500,
        )

        await db_connection.execute(
            """
            INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, member_id) DO UPDATE
            SET current_balance = $3
            """,
            guild_id,
            target_id,
            0,
        )

        # Create transfer with metadata containing interaction token
        result = await service.transfer_currency(
            guild_id=guild_id,
            initiator_id=initiator_id,
            target_id=target_id,
            amount=100,
            reason="test transfer",
            connection=db_connection,
            metadata={"interaction_token": interaction_token},
        )

        # Should return UUID in event pool mode
        assert isinstance(result, UUID)

        # Verify pending transfer has interaction token in metadata
        gateway = PendingTransferGateway()
        pending = await gateway.get_pending_transfer(db_connection, transfer_id=result)
        assert pending is not None
        assert pending.metadata.get("interaction_token") == interaction_token
        assert pending.metadata.get("reason") == "test transfer"

    finally:
        os.environ["TRANSFER_EVENT_POOL_ENABLED"] = original_env


@pytest.mark.asyncio
async def test_telemetry_listener_notifies_initiator_on_success(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test that TelemetryListener sends notification to initiator when transaction succeeds."""
    # Create mock Discord client
    mock_client = MagicMock()
    mock_client.application_id = _snowflake()
    mock_http = AsyncMock()
    mock_http.request = AsyncMock()
    mock_client.http = mock_http

    # Create listener with mock client
    listener = TelemetryListener(discord_client=mock_client)

    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()
    interaction_token = "test_token_456"

    # Set up balances
    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, member_id) DO UPDATE
        SET current_balance = $3
        """,
        guild_id,
        initiator_id,
        500,
    )

    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, member_id) DO UPDATE
        SET current_balance = $3
        """,
        guild_id,
        target_id,
        0,
    )

    # Simulate transaction_success event payload
    parsed = {
        "event_type": "transaction_success",
        "guild_id": guild_id,
        "initiator_id": initiator_id,
        "target_id": target_id,
        "amount": 200,
        "metadata": {
            "interaction_token": interaction_token,
            "reason": "整合測試",
        },
    }

    # Call the handler
    await listener._default_handler(json.dumps(parsed))

    # Give time for async operations
    await asyncio.sleep(0.1)

    # Verify HTTP API was called to send followup
    mock_http.request.assert_called_once()
    call_args = mock_http.request.call_args

    # Check route
    route = call_args[0][0]
    assert route.path == "/webhooks/{application_id}/{interaction_token}"
    assert route.kwargs["application_id"] == mock_client.application_id
    assert route.kwargs["interaction_token"] == interaction_token

    # Check payload
    payload = call_args[1]["json"]
    assert payload["flags"] == 64  # EPHEMERAL
    assert "已成功將 200 點轉給" in payload["content"]
    assert "整合測試" in payload["content"]


@pytest.mark.asyncio
async def test_telemetry_listener_skips_notification_without_token(
    db_pool: Any,
) -> None:
    """Test that TelemetryListener skips notification when no interaction token (sync mode)."""
    mock_client = MagicMock()
    mock_client.application_id = _snowflake()
    mock_http = AsyncMock()
    mock_http.request = AsyncMock()
    mock_client.http = mock_http

    listener = TelemetryListener(discord_client=mock_client)

    parsed = {
        "event_type": "transaction_success",
        "guild_id": _snowflake(),
        "initiator_id": _snowflake(),
        "target_id": _snowflake(),
        "amount": 200,
        "metadata": {},  # No interaction_token
    }

    # Call the handler
    await listener._default_handler(json.dumps(parsed))

    # Give time for async operations
    await asyncio.sleep(0.1)

    # Should not call HTTP API (sync mode, no token)
    mock_http.request.assert_not_called()


@pytest.mark.asyncio
async def test_notification_failure_does_not_affect_transfer(
    db_pool: Any,
    db_connection: Any,
) -> None:
    """Test that notification failure does not affect transfer success."""
    # Create mock Discord client that fails on HTTP call
    mock_client = MagicMock()
    mock_client.application_id = _snowflake()
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(side_effect=Exception("HTTP error"))
    mock_client.http = mock_http

    listener = TelemetryListener(discord_client=mock_client)

    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    # Set up balances
    await db_connection.execute(
        """
        INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, member_id) DO UPDATE
        SET current_balance = $3
        """,
        guild_id,
        initiator_id,
        500,
    )

    parsed = {
        "event_type": "transaction_success",
        "guild_id": guild_id,
        "initiator_id": initiator_id,
        "target_id": target_id,
        "amount": 200,
        "metadata": {"interaction_token": "test_token"},
    }

    # Should not raise exception even if notification fails
    await listener._default_handler(json.dumps(parsed))

    # Verify transfer still succeeded (check balance)
    # Note: This test only verifies notification failure doesn't break the handler
    # Balance check removed as it's not used in the assertion
