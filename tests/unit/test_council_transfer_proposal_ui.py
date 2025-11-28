"""Unit tests for Council transfer proposal UI components.

Tests the transfer type selection view and company transfer flow
for the Council panel (enhance-transfer-target-selection change).
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.commands.council import (
    CouncilCompanySelectView,
    TransferTypeSelectionView,
)

pytestmark = pytest.mark.asyncio


class MockUser:
    """Mock Discord user."""

    def __init__(self, user_id: int) -> None:
        self.id = user_id


class MockResponse:
    """Mock interaction response."""

    def __init__(self) -> None:
        self.send_message = AsyncMock()
        self.send_modal = AsyncMock()


class MockInteraction:
    """Mock Discord interaction."""

    def __init__(self, user_id: int, guild_id: int = 12345) -> None:
        self.user = MockUser(user_id)
        self.response = MockResponse()
        self.data: dict[str, Any] | None = None
        self.guild_id = guild_id


class MockCompany:
    """Mock company object."""

    def __init__(
        self, company_id: int, name: str, account_id: int, license_status: str = "active"
    ) -> None:
        self.id = company_id
        self.name = name
        self.account_id = account_id
        self.license_status = license_status


@pytest.fixture
def mock_service() -> MagicMock:
    """Create a mock council service."""
    service = MagicMock()
    service.create_transfer_proposal = AsyncMock()
    return service


@pytest.fixture
def mock_guild() -> MagicMock:
    """Create a mock Discord guild."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 12345
    guild.get_member = MagicMock(return_value=None)
    return guild


class TestTransferTypeSelectionView:
    """Tests for TransferTypeSelectionView (Council)."""

    async def test_init_creates_three_type_buttons(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test that initialization creates user, department, and company buttons."""
        view = TransferTypeSelectionView(service=mock_service, guild=mock_guild)

        # Check that view has children (buttons)
        assert len(view.children) == 3

        # Check button labels using emoji and label
        button_info = [
            (getattr(child, "emoji", None), getattr(child, "label", "")) for child in view.children
        ]
        labels = [info[1] for info in button_info]

        assert "轉帳給使用者" in labels
        assert "轉帳給政府部門" in labels
        assert "轉帳給公司" in labels

    async def test_view_has_user_button(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test view has user selection button."""
        view = TransferTypeSelectionView(service=mock_service, guild=mock_guild)
        labels = [getattr(c, "label", "") for c in view.children]
        assert "轉帳給使用者" in labels

    async def test_view_has_department_button(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test view has department selection button."""
        view = TransferTypeSelectionView(service=mock_service, guild=mock_guild)
        labels = [getattr(c, "label", "") for c in view.children]
        assert "轉帳給政府部門" in labels

    async def test_view_has_company_button(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test view has company selection button."""
        view = TransferTypeSelectionView(service=mock_service, guild=mock_guild)
        labels = [getattr(c, "label", "") for c in view.children]
        assert "轉帳給公司" in labels


class TestCouncilCompanySelectView:
    """Tests for CouncilCompanySelectView."""

    async def test_init(self, mock_service: MagicMock, mock_guild: MagicMock) -> None:
        """Test initialization."""
        view = CouncilCompanySelectView(service=mock_service, guild=mock_guild)

        assert view.service == mock_service
        assert view.guild == mock_guild
        assert view._companies == {}  # pyright: ignore[reportPrivateUsage]

    async def test_setup_returns_false_when_no_companies(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test setup returns False when there are no active companies."""
        view = CouncilCompanySelectView(service=mock_service, guild=mock_guild)

        with patch(
            "src.bot.ui.company_select.get_active_companies",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await view.setup()
            assert result is False

    async def test_setup_returns_true_with_companies(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test setup returns True when companies are available."""
        view = CouncilCompanySelectView(service=mock_service, guild=mock_guild)

        mock_companies = [
            MockCompany(1, "公司 A", 9600000000000001),
            MockCompany(2, "公司 B", 9600000000000002),
        ]

        with patch(
            "src.bot.ui.company_select.get_active_companies",
            new_callable=AsyncMock,
            return_value=mock_companies,
        ):
            result = await view.setup()
            assert result is True
            assert len(view._companies) == 2  # pyright: ignore[reportPrivateUsage]
            assert 1 in view._companies  # pyright: ignore[reportPrivateUsage]
            assert 2 in view._companies  # pyright: ignore[reportPrivateUsage]

    async def test_setup_creates_select_menu(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test setup creates a select menu with company options."""
        view = CouncilCompanySelectView(service=mock_service, guild=mock_guild)

        mock_companies = [
            MockCompany(1, "公司 A", 9600000000000001),
            MockCompany(2, "公司 B", 9600000000000002),
        ]

        with patch(
            "src.bot.ui.company_select.get_active_companies",
            new_callable=AsyncMock,
            return_value=mock_companies,
        ):
            await view.setup()

        # Should have a select menu
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        assert len(selects) == 1

        select = selects[0]
        assert len(select.options) == 2

    async def test_on_select_shows_transfer_modal(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test selecting a company shows the transfer proposal modal."""
        view = CouncilCompanySelectView(service=mock_service, guild=mock_guild)

        mock_companies = [
            MockCompany(1, "公司 A", 9600000000000001),
        ]

        with patch(
            "src.bot.ui.company_select.get_active_companies",
            new_callable=AsyncMock,
            return_value=mock_companies,
        ):
            await view.setup()

        view._companies = {1: mock_companies[0]}  # pyright: ignore[reportPrivateUsage]

        interaction = MockInteraction(user_id=100)
        interaction.data = {"values": ["1"]}

        await view._on_select(
            cast(discord.Interaction, interaction)
        )  # pyright: ignore[reportPrivateUsage]

        # Should show transfer modal
        interaction.response.send_modal.assert_called_once()

    async def test_on_select_handles_invalid_company(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test selecting an invalid company shows error."""
        view = CouncilCompanySelectView(service=mock_service, guild=mock_guild)
        view._companies = {}  # Empty  # pyright: ignore[reportPrivateUsage]

        interaction = MockInteraction(user_id=100)
        interaction.data = {"values": ["999"]}  # Non-existent company

        await view._on_select(
            cast(discord.Interaction, interaction)
        )  # pyright: ignore[reportPrivateUsage]

        # Should show error message
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        content = call_args.kwargs.get("content", call_args.args[0] if call_args.args else "")
        assert "找不到" in content or "不存在" in content or "請選擇" in content


class TestCouncilCompanyTransferIntegration:
    """Integration tests for council company transfer proposal flow."""

    async def test_type_selection_view_has_all_options(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test the type selection view has all required options."""
        type_view = TransferTypeSelectionView(service=mock_service, guild=mock_guild)

        labels = [getattr(c, "label", "") for c in type_view.children]
        assert "轉帳給使用者" in labels
        assert "轉帳給政府部門" in labels
        assert "轉帳給公司" in labels

    async def test_company_select_view_setup_with_companies(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test company select view can be set up with companies."""
        view = CouncilCompanySelectView(service=mock_service, guild=mock_guild)

        mock_companies = [
            MockCompany(1, "測試公司", 9600000000000001),
        ]

        with patch(
            "src.bot.ui.company_select.get_active_companies",
            new_callable=AsyncMock,
            return_value=mock_companies,
        ):
            result = await view.setup()

        assert result is True
        assert len(view.children) == 1
