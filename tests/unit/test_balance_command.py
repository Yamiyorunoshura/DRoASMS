"""Unit tests for balance and history command logic."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from discord import Interaction

from src.bot.commands.balance import build_balance_command, build_history_command
from src.bot.services.balance_service import (
    BalancePermissionError,
    BalanceService,
    BalanceSnapshot,
    HistoryPage,
)


def _snowflake() -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return secrets.randbits(63)


class _StubResponse:
    def __init__(self) -> None:
        self.deferred = False
        self.sent = False
        self.kwargs: dict[str, Any] | None = None

    async def defer(self, **kwargs: Any) -> None:
        self.deferred = True

    async def send_message(self, **kwargs: Any) -> None:
        self.sent = True
        self.kwargs = kwargs

    def is_done(self) -> bool:
        return self.deferred


class _StubInteraction:
    def __init__(self, guild_id: int, user_id: int, *, is_admin: bool = False) -> None:
        self.guild_id = guild_id
        self.user = SimpleNamespace(
            id=user_id,
            guild_permissions=SimpleNamespace(administrator=is_admin, manage_guild=is_admin),
        )
        self.response = _StubResponse()

    async def edit_original_response(self, **kwargs: Any) -> None:
        self.response.kwargs = kwargs


class _StubMember(SimpleNamespace):
    def __init__(self, *, id: int) -> None:
        super().__init__(id=id)

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_balance_command_requires_guild() -> None:
    """Test that balance command requires guild context."""
    service = SimpleNamespace(get_balance_snapshot=AsyncMock())
    command = build_balance_command(cast(BalanceService, service))
    interaction = _StubInteraction(guild_id=None, user_id=_snowflake())  # type: ignore

    await command._callback(cast(Interaction[Any], interaction), None)

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert "伺服器內" in interaction.response.kwargs.get("content", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_balance_command_validates_permission() -> None:
    """Test that balance command validates permission for viewing others."""
    guild_id = _snowflake()
    requester_id = _snowflake()
    target_id = _snowflake()

    service = SimpleNamespace(
        get_balance_snapshot=AsyncMock(side_effect=BalancePermissionError("無權限查看他人餘額"))
    )

    command = build_balance_command(cast(BalanceService, service))
    interaction = _StubInteraction(guild_id=guild_id, user_id=requester_id, is_admin=False)
    target = _StubMember(id=target_id)

    await command._callback(cast(Interaction[Any], interaction), target)

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert "無權限" in interaction.response.kwargs.get("content", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_balance_command_calls_service_correctly() -> None:
    """Test that balance command calls service with correct parameters."""
    guild_id = _snowflake()
    user_id = _snowflake()

    snapshot = BalanceSnapshot(
        balance=1000,
        last_modified_at=datetime.now(timezone.utc),
        is_throttled=False,
        throttled_until=None,
    )

    service = SimpleNamespace(get_balance_snapshot=AsyncMock(return_value=snapshot))

    command = build_balance_command(cast(BalanceService, service))
    interaction = _StubInteraction(guild_id=guild_id, user_id=user_id)

    await command._callback(cast(Interaction[Any], interaction), None)

    service.get_balance_snapshot.assert_awaited_once_with(
        guild_id=guild_id,
        requester_id=user_id,
        target_member_id=None,
        can_view_others=False,
        connection=None,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_history_command_validates_before_parameter() -> None:
    """Test that history command validates before ISO 8601 format."""
    guild_id = _snowflake()
    user_id = _snowflake()

    service = SimpleNamespace(get_history=AsyncMock())
    command = build_history_command(cast(BalanceService, service))
    interaction = _StubInteraction(guild_id=guild_id, user_id=user_id)

    await command._callback(cast(Interaction[Any], interaction), None, 10, "invalid-date")

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert "ISO 8601" in interaction.response.kwargs.get("content", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_history_command_calls_service_correctly() -> None:
    """Test that history command calls service with correct parameters."""
    guild_id = _snowflake()
    user_id = _snowflake()

    page = HistoryPage(
        items=[],
        next_cursor=None,
    )

    service = SimpleNamespace(get_history=AsyncMock(return_value=page))

    command = build_history_command(cast(BalanceService, service))
    interaction = _StubInteraction(guild_id=guild_id, user_id=user_id)

    await command._callback(cast(Interaction[Any], interaction), None, 20, None)

    service.get_history.assert_awaited_once_with(
        guild_id=guild_id,
        requester_id=user_id,
        target_member_id=None,
        can_view_others=False,
        limit=20,
        cursor=None,
        connection=None,
    )
