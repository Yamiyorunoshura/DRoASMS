"""Contract tests for /personal_panel command."""

from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from src.bot.commands.personal_panel import build_personal_panel_command
from src.bot.services.balance_service import (
    BalanceService,
    BalanceSnapshot,
    HistoryEntry,
    HistoryPage,
)
from src.bot.services.currency_config_service import (
    CurrencyConfigResult,
    CurrencyConfigService,
)
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.transfer_service import TransferService


def _snowflake() -> int:
    return secrets.randbits(63)


class _StubResponse:
    def __init__(self) -> None:
        self.sent = False
        self.kwargs: dict[str, Any] | None = None

    def is_done(self) -> bool:
        return self.sent

    async def send_message(self, **kwargs: Any) -> None:
        self.sent = True
        self.kwargs = kwargs

    async def defer(self, **kwargs: Any) -> None:
        self.sent = True


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
        self.user = SimpleNamespace(id=user_id, display_name="TestUser", mention=f"<@{user_id}>")
        self.response = _StubResponse()
        self.followup = _StubFollowup()
        self.client = SimpleNamespace(loop=asyncio.get_event_loop())
        self._edited_kwargs: dict[str, Any] | None = None

    async def edit_original_response(self, **kwargs: Any) -> None:
        self._edited_kwargs = kwargs


def _make_mock_balance_snapshot(
    guild_id: int, member_id: int, balance: int = 10000
) -> BalanceSnapshot:
    """Create a mock BalanceSnapshot for testing."""
    return BalanceSnapshot(
        guild_id=guild_id,
        member_id=member_id,
        balance=balance,
        is_throttled=False,
        throttled_until=None,
        last_modified_at=datetime.now(timezone.utc),
    )


def _make_mock_history_page(
    guild_id: int, member_id: int, items: list[HistoryEntry] | None = None
) -> HistoryPage:
    """Create a mock HistoryPage for testing."""
    if items is None:
        items = []
    return HistoryPage(items=items, next_cursor=None)


@pytest.mark.contract
class TestPersonalPanelCommandContract:
    """Contract tests for /personal_panel command."""

    def test_command_registration(self) -> None:
        """Test that command is registered with correct metadata."""
        # Setup mock services
        balance_service = SimpleNamespace(
            get_balance_snapshot=AsyncMock(),
            get_history=AsyncMock(),
        )
        transfer_service = SimpleNamespace(
            transfer_currency=AsyncMock(),
        )
        currency_service = SimpleNamespace(
            get_currency_config=AsyncMock(
                return_value=CurrencyConfigResult(currency_name="測試幣", currency_icon="💰")
            ),
        )
        state_council_service = SimpleNamespace(
            get_department_account_id=AsyncMock(return_value=9_500_000_000_000_123)
        )

        command = build_personal_panel_command(
            cast(BalanceService, balance_service),
            cast(TransferService, transfer_service),
            cast(CurrencyConfigService, currency_service),
            cast(StateCouncilService, state_council_service),
        )

        # Verify command metadata
        assert command.name == "personal_panel"
        assert "個人面板" in command.description
        # Command should have no parameters
        assert len(command.parameters) == 0

    @pytest.mark.asyncio
    async def test_command_returns_embed_with_view(self) -> None:
        """Test that command returns an embed with a view."""
        guild_id = _snowflake()
        user_id = _snowflake()

        balance_snapshot = _make_mock_balance_snapshot(guild_id, user_id, balance=5000)
        history_page = _make_mock_history_page(guild_id, user_id, items=[])

        balance_service = SimpleNamespace(
            get_balance_snapshot=AsyncMock(return_value=balance_snapshot),
            get_history=AsyncMock(return_value=history_page),
        )
        transfer_service = SimpleNamespace(
            transfer_currency=AsyncMock(),
        )
        currency_service = SimpleNamespace(
            get_currency_config=AsyncMock(
                return_value=CurrencyConfigResult(currency_name="測試幣", currency_icon="💰")
            ),
        )
        state_council_service = SimpleNamespace(
            get_department_account_id=AsyncMock(return_value=9_500_000_000_000_123)
        )

        command = build_personal_panel_command(
            cast(BalanceService, balance_service),
            cast(TransferService, transfer_service),
            cast(CurrencyConfigService, currency_service),
            cast(StateCouncilService, state_council_service),
        )

        interaction = _StubInteraction(guild_id, user_id)

        # Execute command
        await command.callback(interaction)  # type: ignore[arg-type]

        # Verify response was sent
        assert interaction.response.sent or interaction._edited_kwargs is not None

        # If edited, check for embed and view
        if interaction._edited_kwargs:
            assert "embed" in interaction._edited_kwargs
            assert "view" in interaction._edited_kwargs

    @pytest.mark.asyncio
    async def test_command_requires_guild(self) -> None:
        """Test that command rejects DM usage."""
        user_id = _snowflake()

        balance_service = SimpleNamespace(
            get_balance_snapshot=AsyncMock(),
            get_history=AsyncMock(),
        )
        transfer_service = SimpleNamespace(
            transfer_currency=AsyncMock(),
        )
        currency_service = SimpleNamespace(
            get_currency_config=AsyncMock(),
        )
        state_council_service = SimpleNamespace(
            get_department_account_id=AsyncMock(return_value=9_500_000_000_000_123)
        )

        command = build_personal_panel_command(
            cast(BalanceService, balance_service),
            cast(TransferService, transfer_service),
            cast(CurrencyConfigService, currency_service),
            cast(StateCouncilService, state_council_service),
        )

        # Create interaction without guild
        interaction = _StubInteraction(0, user_id)
        interaction.guild_id = None  # type: ignore[assignment]

        await command.callback(interaction)  # type: ignore[arg-type]

        # Verify error response
        assert interaction.response.sent
        assert interaction.response.kwargs is not None
        assert "伺服器內" in interaction.response.kwargs.get("content", "")


@pytest.mark.contract
class TestPersonalPanelHelpData:
    """Contract tests for personal_panel help data."""

    def test_help_data_structure(self) -> None:
        """Test that help data has correct structure."""
        from src.bot.commands.personal_panel import get_help_data

        help_data = get_help_data()

        assert help_data["name"] == "personal_panel"
        assert help_data["category"] == "economy"
        assert isinstance(help_data["description"], str)
        assert isinstance(help_data["parameters"], list)
        assert isinstance(help_data["examples"], list)
        assert isinstance(help_data["tags"], list)

    def test_help_data_has_examples(self) -> None:
        """Test that help data includes examples."""
        from src.bot.commands.personal_panel import get_help_data

        help_data = get_help_data()

        assert len(help_data["examples"]) > 0
        assert "/personal_panel" in help_data["examples"]
