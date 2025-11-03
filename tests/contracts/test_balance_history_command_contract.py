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

from src.bot.commands.balance import (
    build_balance_command,
    build_history_command,
)
from src.bot.services.balance_service import (
    BalanceService,
    BalanceSnapshot,
    HistoryEntry,
    HistoryPage,
)


def _snowflake() -> int:
    return secrets.randbits(63)


class _StubResponse:
    def __init__(self) -> None:
        self.sent = False
        self.kwargs: dict[str, Any] | None = None

    async def send_message(self, **kwargs: Any) -> None:
        self.sent = True
        self.kwargs = kwargs


class _StubInteraction:
    def __init__(self, guild_id: int, user_id: int, *, manage_guild: bool = False) -> None:
        self.guild_id = guild_id
        self.user = SimpleNamespace(
            id=user_id,
            mention=f"<@{user_id}>",
            display_name=f"User-{user_id}",
            guild_permissions=SimpleNamespace(
                administrator=manage_guild,
                manage_guild=manage_guild,
            ),
        )
        self.response = _StubResponse()
        self.client = SimpleNamespace(loop=asyncio.get_event_loop())


class _StubMember(SimpleNamespace):
    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


@pytest.mark.asyncio
async def test_balance_command_contract() -> None:
    guild_id = _snowflake()
    requester_id = _snowflake()
    target_id = requester_id

    service = SimpleNamespace(
        get_balance_snapshot=AsyncMock(
            return_value=BalanceSnapshot(
                guild_id=guild_id,
                member_id=target_id,
                balance=1234,
                last_modified_at=datetime(2025, 10, 22, tzinfo=timezone.utc),
                throttled_until=None,
            )
        )
    )

    command = build_balance_command(cast(BalanceService, service))
    assert command.name == "balance"
    assert "餘額" in command.description
    parameter_names = [param.name for param in command.parameters]
    assert parameter_names == ["member"]
    assert command.parameters[0].type == AppCommandOptionType.user
    assert command.parameters[0].required is False

    interaction = _StubInteraction(guild_id=guild_id, user_id=requester_id, manage_guild=False)
    await command._callback(cast(Interaction[Any], interaction), cast(Interaction[Any], None))

    service.get_balance_snapshot.assert_awaited_once_with(
        guild_id=guild_id,
        requester_id=requester_id,
        target_member_id=None,
        can_view_others=False,
        connection=None,
    )
    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert interaction.response.kwargs["ephemeral"] is True
    assert "1,234" in interaction.response.kwargs["content"]


@pytest.mark.asyncio
async def test_history_command_contract() -> None:
    guild_id = _snowflake()
    requester_id = _snowflake()
    target_id = _snowflake()

    service = SimpleNamespace(
        get_history=AsyncMock(
            return_value=HistoryPage(
                items=[
                    HistoryEntry(
                        transaction_id=UUID("00000000-0000-0000-0000-000000000101"),
                        guild_id=guild_id,
                        member_id=target_id,
                        initiator_id=requester_id,
                        target_id=target_id,
                        amount=200,
                        direction="transfer",
                        reason="Gift",
                        created_at=datetime(2025, 10, 22, 9, 0, tzinfo=timezone.utc),
                        metadata={},
                        balance_after_initiator=800,
                        balance_after_target=200,
                    )
                ],
                next_cursor=datetime(2025, 10, 22, 8, 55, tzinfo=timezone.utc),
            )
        )
    )

    command = build_history_command(cast(BalanceService, service))
    assert command.name == "history"
    assert "歷史" in command.description

    member_option = command.parameters[0]
    assert member_option.name == "member"
    assert member_option.type == AppCommandOptionType.user
    assert member_option.required is False

    limit_option = command.parameters[1]
    assert limit_option.name == "limit"
    assert limit_option.type == AppCommandOptionType.integer
    assert limit_option.required is False
    assert limit_option.min_value == 1
    assert limit_option.max_value == 50

    interaction = _StubInteraction(guild_id=guild_id, user_id=requester_id, manage_guild=True)
    member = _StubMember(id=target_id, display_name="Target")

    await command._callback(
        cast(Interaction[Any], interaction), cast(Interaction[Any], member), 10, None
    )

    service.get_history.assert_awaited_once_with(
        guild_id=guild_id,
        requester_id=requester_id,
        target_member_id=target_id,
        can_view_others=True,
        limit=10,
        cursor=None,
        connection=None,
    )
    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    content = interaction.response.kwargs["content"]
    assert interaction.response.kwargs["ephemeral"] is True
    assert "200" in content
    assert "Gift" in content
