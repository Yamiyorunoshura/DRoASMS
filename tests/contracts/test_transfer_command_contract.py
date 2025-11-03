from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from discord import AppCommandOptionType, Interaction

from src.bot.commands.transfer import build_transfer_command
from src.bot.services.transfer_service import TransferResult, TransferService


def _snowflake() -> int:
    return secrets.randbits(63)


class _StubResponse:
    def __init__(self) -> None:
        self.sent = False
        self.kwargs: dict[str, Any] | None = None

    async def send_message(self, **kwargs: Any) -> None:
        self.sent = True
        self.kwargs = kwargs


class _StubFollowup:
    def __init__(self) -> None:
        self.sent = False
        self.kwargs: dict[str, Any] | None = None

    async def send(self, **kwargs: Any) -> None:
        self.sent = True
        self.kwargs = kwargs


class _StubInteraction:
    def __init__(self, guild_id: int, user_id: int) -> None:
        self.guild_id = guild_id
        self.user = SimpleNamespace(id=user_id, display_name="Sender", mention=f"<@{user_id}>")
        self.response = _StubResponse()
        self.followup = _StubFollowup()
        self.client = SimpleNamespace(loop=asyncio.get_event_loop())


class _StubMember(SimpleNamespace):
    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


@pytest.mark.asyncio
async def test_transfer_command_contract() -> None:
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    service = SimpleNamespace(
        transfer_currency=AsyncMock(
            return_value=TransferResult(
                transaction_id=UUID("00000000-0000-0000-0000-000000000001"),
                guild_id=guild_id,
                initiator_id=initiator_id,
                target_id=target_id,
                amount=250,
                initiator_balance=750,
                target_balance=250,
                direction="transfer",
                created_at=datetime(2025, 10, 22, tzinfo=timezone.utc),
                throttled_until=None,
                metadata={"reason": "Congrats!"},
            )
        )
    )

    command = build_transfer_command(cast(TransferService, service))
    assert command.name == "transfer"
    assert "currency" in command.description.lower()
    parameter_names = [param.name for param in command.parameters]
    assert parameter_names == ["target", "amount", "reason"]
    # 參數改為 mentionable（成員或身分組）
    assert command.parameters[0].type == AppCommandOptionType.mentionable
    assert command.parameters[1].type == AppCommandOptionType.integer
    assert command.parameters[1].required is True
    assert command.parameters[2].required is False

    interaction = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    target = _StubMember(id=target_id, display_name="Receiver")

    await command._callback(
        cast(Interaction[Any], interaction), cast(Interaction[Any], target), 250, "Congrats!"
    )

    service.transfer_currency.assert_awaited_once_with(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=250,
        reason="Congrats!",
        connection=None,
        metadata=None,
    )
    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert interaction.response.kwargs["ephemeral"] is True
    content = interaction.response.kwargs["content"]
    assert str(target_id) in content
    assert "250" in content
