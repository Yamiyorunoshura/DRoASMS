from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from discord import AppCommandOptionType, Interaction

from src.bot.commands.adjust import build_adjust_command
from src.bot.services.adjustment_service import AdjustmentResult, AdjustmentService
from src.bot.services.council_service import CouncilServiceResult
from src.bot.services.currency_config_service import (
    CurrencyConfigResult,
    CurrencyConfigService,
)
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.supreme_assembly_service import SupremeAssemblyService
from src.infra.result import Err


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
    def __init__(self, guild_id: int, user_id: int, *, is_admin: bool) -> None:
        self.guild_id = guild_id
        self.user = SimpleNamespace(
            id=user_id,
            display_name="Admin",
            mention=f"<@{user_id}>",
            guild_permissions=SimpleNamespace(administrator=is_admin, manage_guild=is_admin),
            roles=[],
        )
        self.response = _StubResponse()
        self.client = SimpleNamespace(loop=asyncio.get_event_loop())
        # simulate permission
        self.user_is_admin = is_admin


class _StubMember(SimpleNamespace):
    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


def _create_mock_services() -> tuple[MagicMock, MagicMock, MagicMock]:
    """建立測試用的 mock 服務實例。"""
    state_council_service = MagicMock(spec=StateCouncilService)
    state_council_service.check_leader_permission = AsyncMock(return_value=False)
    state_council_service.find_department_by_role = AsyncMock(return_value=None)

    council_service = MagicMock(spec=CouncilServiceResult)
    council_service.get_config = AsyncMock(return_value=Err(Exception("Not configured")))

    supreme_assembly_service = MagicMock(spec=SupremeAssemblyService)
    supreme_assembly_service.get_config = AsyncMock(side_effect=Exception("Not configured"))

    return state_council_service, council_service, supreme_assembly_service


@pytest.mark.contract
@pytest.mark.asyncio
async def test_adjust_command_contract() -> None:
    guild_id = _snowflake()
    admin_id = _snowflake()
    target_id = _snowflake()

    service = SimpleNamespace(
        adjust_balance=AsyncMock(
            return_value=AdjustmentResult(
                transaction_id=UUID("00000000-0000-0000-0000-0000000000aa"),
                guild_id=guild_id,
                admin_id=admin_id,
                target_id=target_id,
                amount=150,
                target_balance_after=350,
                direction="adjustment_grant",
                created_at=datetime(2025, 10, 22, tzinfo=timezone.utc),
                metadata={"reason": "Bonus"},
            )
        )
    )
    currency_service = SimpleNamespace(
        get_currency_config=AsyncMock(
            return_value=CurrencyConfigResult(currency_name="點", currency_icon="")
        )
    )

    state_council_service, council_service, supreme_assembly_service = _create_mock_services()
    command = build_adjust_command(
        cast(AdjustmentService, service),
        cast(CurrencyConfigService, currency_service),
        state_council_service=state_council_service,
        council_service=council_service,
        supreme_assembly_service=supreme_assembly_service,
    )
    assert command.name == "adjust"
    assert "currency" in command.description.lower() or "點數" in command.description
    names = [p.name for p in command.parameters]
    assert names == ["target", "amount", "reason"]
    # 參數改為 mentionable（成員或身分組）
    assert command.parameters[0].type == AppCommandOptionType.mentionable
    assert command.parameters[1].type == AppCommandOptionType.integer
    assert command.parameters[1].required is True
    assert command.parameters[2].required is True  # reason required by spec

    interaction = _StubInteraction(guild_id=guild_id, user_id=admin_id, is_admin=True)
    target = _StubMember(id=target_id, display_name="Member")

    await command._callback(  # type: ignore[protected-access]
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
    assert interaction.response.kwargs is not None
    assert interaction.response.kwargs["ephemeral"] is True
    content = interaction.response.kwargs["content"]
    assert str(target_id) in content
    assert "150" in content
