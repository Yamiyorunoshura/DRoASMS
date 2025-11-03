"""Unit tests for TelemetryListener initiator server notification."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.gateway.economy_queries import BalanceRecord
from src.infra.telemetry.listener import TelemetryListener


def _snowflake() -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return secrets.randbits(63)


@pytest.mark.asyncio
async def test_notify_initiator_server_with_token(
    db_pool: Any,
) -> None:
    """Test _notify_initiator_server sends followup when token is present."""
    # Create mock Discord client
    mock_client = MagicMock()
    mock_client.application_id = _snowflake()
    mock_http = AsyncMock()
    mock_http.request = AsyncMock()
    mock_client.http = mock_http

    # Create listener with mock client
    listener = TelemetryListener(discord_client=mock_client)

    # Create test payload
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()
    interaction_token = "test_token_123"

    parsed = {
        "event_type": "transaction_success",
        "guild_id": guild_id,
        "initiator_id": initiator_id,
        "target_id": target_id,
        "amount": 200,
        "metadata": {
            "interaction_token": interaction_token,
            "reason": "測試轉帳",
        },
    }

    # Mock the database pool and economy gateway
    with patch("src.infra.telemetry.listener.db_pool") as mock_db_pool_module:
        mock_db_pool_module.get_pool.return_value = db_pool

        with patch("src.infra.telemetry.listener.EconomyQueryGateway") as mock_gateway_class:
            mock_gateway = MagicMock()
            mock_gateway.fetch_balance = AsyncMock(
                return_value=BalanceRecord(
                    guild_id=guild_id,
                    member_id=initiator_id,
                    balance=300,
                    last_modified_at=datetime.now(timezone.utc),
                    throttled_until=None,
                )
            )
            mock_gateway_class.return_value = mock_gateway

            # Call the method
            await listener._notify_initiator_server(parsed)

    # Verify HTTP API was called
    mock_http.request.assert_called_once()
    call_args = mock_http.request.call_args

    # Check route
    route = call_args[0][0]
    assert route.path == "/webhooks/{application_id}/{interaction_token}"
    assert route.method == "POST"
    assert route.kwargs["application_id"] == mock_client.application_id
    assert route.kwargs["interaction_token"] == interaction_token

    # Check payload
    payload = call_args[1]["json"]
    assert payload["flags"] == 64  # EPHEMERAL
    assert "已成功將 200 點轉給" in payload["content"]
    assert "你目前的餘額為 300 點" in payload["content"]
    assert "備註：測試轉帳" in payload["content"]


@pytest.mark.asyncio
async def test_notify_initiator_server_no_token() -> None:
    """Test _notify_initiator_server skips when no token (sync mode)."""
    mock_client = MagicMock()
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

    await listener._notify_initiator_server(parsed)

    # Should not call HTTP API
    mock_http.request.assert_not_called()


@pytest.mark.asyncio
async def test_notify_initiator_server_no_discord_client() -> None:
    """Test _notify_initiator_server skips when no Discord client."""
    listener = TelemetryListener(discord_client=None)

    parsed = {
        "event_type": "transaction_success",
        "guild_id": _snowflake(),
        "initiator_id": _snowflake(),
        "target_id": _snowflake(),
        "amount": 200,
        "metadata": {"interaction_token": "test_token"},
    }

    # Should not raise exception
    await listener._notify_initiator_server(parsed)


@pytest.mark.asyncio
async def test_notify_initiator_server_no_application_id() -> None:
    """Test _notify_initiator_server handles missing application_id gracefully."""
    mock_client = MagicMock()
    mock_client.application_id = None  # No application_id
    listener = TelemetryListener(discord_client=mock_client)

    parsed = {
        "event_type": "transaction_success",
        "guild_id": _snowflake(),
        "initiator_id": _snowflake(),
        "target_id": _snowflake(),
        "amount": 200,
        "metadata": {"interaction_token": "test_token"},
    }

    # Should not raise exception
    await listener._notify_initiator_server(parsed)


@pytest.mark.asyncio
async def test_notify_initiator_server_balance_query_failure() -> None:
    """Test _notify_initiator_server handles balance query failure gracefully."""
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
        "metadata": {"interaction_token": "test_token"},
    }

    # Mock balance query failure
    with patch("src.infra.telemetry.listener.EconomyQueryGateway") as mock_gateway_class:
        mock_gateway = MagicMock()
        mock_gateway.fetch_balance = AsyncMock(side_effect=Exception("DB error"))
        mock_gateway_class.return_value = mock_gateway

        # Should not raise exception, should still send notification without balance
        await listener._notify_initiator_server(parsed)

    # Verify HTTP API was still called (without balance info)
    mock_http.request.assert_called_once()
    call_args = mock_http.request.call_args
    payload = call_args[1]["json"]
    assert "已成功將 200 點轉給" in payload["content"]
    # Should not contain balance info since query failed
    assert "餘額" not in payload["content"]


@pytest.mark.asyncio
async def test_notify_initiator_server_http_failure() -> None:
    """Test _notify_initiator_server handles HTTP API failure gracefully."""
    mock_client = MagicMock()
    mock_client.application_id = _snowflake()
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(side_effect=Exception("HTTP error"))
    mock_client.http = mock_http

    listener = TelemetryListener(discord_client=mock_client)

    parsed = {
        "event_type": "transaction_success",
        "guild_id": _snowflake(),
        "initiator_id": _snowflake(),
        "target_id": _snowflake(),
        "amount": 200,
        "metadata": {"interaction_token": "test_token"},
    }

    # Should not raise exception
    await listener._notify_initiator_server(parsed)

    # Verify HTTP API was attempted
    mock_http.request.assert_called_once()


@pytest.mark.asyncio
async def test_notify_initiator_server_message_formatting() -> None:
    """Test _notify_initiator_server formats message correctly."""
    mock_client = MagicMock()
    mock_client.application_id = _snowflake()
    mock_http = AsyncMock()
    mock_http.request = AsyncMock()
    mock_client.http = mock_http

    listener = TelemetryListener(discord_client=mock_client)

    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    parsed = {
        "event_type": "transaction_success",
        "guild_id": guild_id,
        "initiator_id": initiator_id,
        "target_id": target_id,
        "amount": 500,
        "metadata": {
            "interaction_token": "test_token",
            "reason": "生日禮物",
        },
    }

    # Mock the database pool and economy gateway
    mock_conn = MagicMock()
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context_manager.__aexit__ = AsyncMock(return_value=False)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_context_manager)

    with patch("src.infra.telemetry.listener.db_pool") as mock_db_pool_module:
        mock_db_pool_module.get_pool.return_value = mock_pool

        with patch("src.infra.telemetry.listener.EconomyQueryGateway") as mock_gateway_class:
            mock_gateway = MagicMock()
            mock_gateway.fetch_balance = AsyncMock(
                return_value=BalanceRecord(
                    guild_id=guild_id,
                    member_id=initiator_id,
                    balance=1000,
                    last_modified_at=datetime.now(timezone.utc),
                    throttled_until=None,
                )
            )
            mock_gateway_class.return_value = mock_gateway

            await listener._notify_initiator_server(parsed)

    call_args = mock_http.request.call_args
    payload = call_args[1]["json"]
    content = payload["content"]

    # Check message contains all required information
    assert f"<@{target_id}>" in content or "收款人" in content
    assert "500" in content  # Amount
    assert "1,000" in content or "1000" in content  # Balance
    assert "生日禮物" in content  # Reason
