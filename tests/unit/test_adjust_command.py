"""Unit tests for adjust command logic."""

from __future__ import annotations

import secrets
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from discord import Interaction

from src.bot.commands.adjust import build_adjust_command
from src.bot.services.adjustment_service import (
    AdjustmentResult,
    AdjustmentService,
    UnauthorizedAdjustmentError,
    ValidationError,
)


def _snowflake() -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return secrets.randbits(63)


class _StubResponse:
    def __init__(self) -> None:
        self.sent = False
        self.kwargs: dict[str, Any] | None = None

    async def send_message(self, **kwargs: Any) -> None:
        self.sent = True
        self.kwargs = kwargs


class _StubInteraction:
    def __init__(self, guild_id: int, user_id: int, *, is_admin: bool = False) -> None:
        self.guild_id = guild_id
        self.user = SimpleNamespace(
            id=user_id,
            guild_permissions=SimpleNamespace(administrator=is_admin, manage_guild=is_admin),
        )
        self.response = _StubResponse()

    @property
    def guild_permissions(self) -> Any:
        return self.user.guild_permissions


class _StubMember(SimpleNamespace):
    def __init__(self, *, id: int) -> None:
        super().__init__(id=id)

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adjust_command_validates_admin_permission() -> None:
    """Test that adjust command checks admin permission."""
    guild_id = _snowflake()
    admin_id = _snowflake()
    target_id = _snowflake()

    service = SimpleNamespace(
        adjust_balance=AsyncMock(side_effect=UnauthorizedAdjustmentError("權限不足"))
    )

    command = build_adjust_command(cast(AdjustmentService, service))
    interaction = _StubInteraction(guild_id=guild_id, user_id=admin_id, is_admin=False)
    target = _StubMember(id=target_id)

    await command._callback(
        cast(Interaction[Any], interaction), cast(Interaction[Any], target), 100, "Test"
    )

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert "權限不足" in interaction.response.kwargs.get("content", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adjust_command_validates_amount() -> None:
    """Test that adjust command validates amount parameter."""
    guild_id = _snowflake()
    admin_id = _snowflake()
    target_id = _snowflake()

    service = SimpleNamespace(adjust_balance=AsyncMock(side_effect=ValidationError("金額無效")))

    command = build_adjust_command(cast(AdjustmentService, service))
    interaction = _StubInteraction(guild_id=guild_id, user_id=admin_id, is_admin=True)
    target = _StubMember(id=target_id)

    await command._callback(
        cast(Interaction[Any], interaction), cast(Interaction[Any], target), 0, "Test"
    )

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert "金額無效" in interaction.response.kwargs.get("content", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adjust_command_calls_service_with_correct_parameters() -> None:
    """Test that adjust command calls service layer with correct parameters."""
    guild_id = _snowflake()
    admin_id = _snowflake()
    target_id = _snowflake()

    service = SimpleNamespace(
        adjust_balance=AsyncMock(
            return_value=AdjustmentResult(
                transaction_id=None,
                guild_id=guild_id,
                admin_id=admin_id,
                target_id=target_id,
                amount=150,
                target_balance_after=350,
                direction="adjustment_grant",
                created_at=None,
                metadata={"reason": "Bonus"},
            )
        )
    )

    command = build_adjust_command(cast(AdjustmentService, service))
    interaction = _StubInteraction(guild_id=guild_id, user_id=admin_id, is_admin=True)
    target = _StubMember(id=target_id)

    await command._callback(
        cast(Interaction[Any], interaction), cast(Interaction[Any], target), 150, "Bonus"
    )

    service.adjust_balance.assert_awaited_once_with(
        guild_id=guild_id,
        admin_id=admin_id,
        target_id=target_id,
        amount=150,
        reason="Bonus",
        can_adjust=True,
        connection=None,
    )
    assert interaction.response.sent is True
