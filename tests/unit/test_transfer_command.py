"""Unit tests for transfer command logic."""

from __future__ import annotations

import secrets
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from discord import Interaction

from src.bot.commands.transfer import build_transfer_command
from src.bot.services.transfer_service import (
    InsufficientBalanceError,
    TransferResult,
    TransferService,
    TransferThrottleError,
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
    def __init__(self, guild_id: int, user_id: int) -> None:
        self.guild_id = guild_id
        self.user = SimpleNamespace(id=user_id)
        self.response = _StubResponse()
        self.token = None

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
async def test_transfer_command_requires_guild() -> None:
    """Test that transfer command requires guild context."""
    service = SimpleNamespace(transfer_currency=AsyncMock())
    command = build_transfer_command(cast(TransferService, service))
    interaction = _StubInteraction(guild_id=None, user_id=_snowflake())  # type: ignore
    target = _StubMember(id=_snowflake())

    await command._callback(cast(Interaction[Any], interaction), target, 100, None)

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert "伺服器內" in interaction.response.kwargs.get("content", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_validates_insufficient_balance() -> None:
    """Test that transfer command handles insufficient balance error."""
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    service = SimpleNamespace(
        transfer_currency=AsyncMock(side_effect=InsufficientBalanceError("餘額不足"))
    )

    command = build_transfer_command(cast(TransferService, service))
    interaction = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    target = _StubMember(id=target_id)

    await command._callback(cast(Interaction[Any], interaction), target, 1000, None)

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert "餘額不足" in interaction.response.kwargs.get("content", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_validates_throttle() -> None:
    """Test that transfer command handles throttle error."""
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    service = SimpleNamespace(
        transfer_currency=AsyncMock(side_effect=TransferThrottleError("冷卻中"))
    )

    command = build_transfer_command(cast(TransferService, service))
    interaction = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    target = _StubMember(id=target_id)

    await command._callback(cast(Interaction[Any], interaction), target, 100, None)

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert "冷卻中" in interaction.response.kwargs.get("content", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_calls_service_with_correct_parameters() -> None:
    """Test that transfer command calls service with correct parameters."""
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    result = TransferResult(
        transaction_id=None,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=100,
        initiator_balance=900,
        target_balance=None,
        created_at=None,
        metadata={"reason": "Test"},
    )

    service = SimpleNamespace(transfer_currency=AsyncMock(return_value=result))

    command = build_transfer_command(cast(TransferService, service))
    interaction = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    target = _StubMember(id=target_id)

    await command._callback(cast(Interaction[Any], interaction), target, 100, "Test")

    service.transfer_currency.assert_awaited_once_with(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=100,
        reason="Test",
        connection=None,
        metadata=None,
    )
