"""Unit tests for Supreme Assembly transfer UI components.

Tests the transfer type selection view and company transfer flow
for the Supreme Assembly panel (enhance-transfer-target-selection change).
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.commands.supreme_assembly import (
    SupremeAssemblyCompanySelectView,
    SupremeAssemblyTransferModal,
    SupremeAssemblyTransferTypeSelectionView,
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
    """Create a mock supreme assembly service."""
    service = MagicMock()
    service.transfer = AsyncMock()
    return service


@pytest.fixture
def mock_guild() -> MagicMock:
    """Create a mock Discord guild."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 12345
    guild.get_member = MagicMock(return_value=None)
    return guild


class TestSupremeAssemblyTransferTypeSelectionView:
    """Tests for SupremeAssemblyTransferTypeSelectionView."""

    async def test_init_creates_select_with_four_options(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test that initialization creates select with all transfer type options."""
        view = SupremeAssemblyTransferTypeSelectionView(service=mock_service, guild=mock_guild)

        # Check that view has a select menu
        assert len(view.children) == 1

        select = view.children[0]
        assert isinstance(select, discord.ui.Select)

        # Check options include user, council, department, and company
        option_values = [opt.value for opt in select.options]
        assert "user" in option_values
        assert "council" in option_values
        assert "department" in option_values
        assert "company" in option_values

    async def test_on_select_user_shows_user_select(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test selecting user type shows user select component."""
        view = SupremeAssemblyTransferTypeSelectionView(service=mock_service, guild=mock_guild)

        interaction = MockInteraction(user_id=100)
        interaction.data = {"values": ["user"]}

        with patch(
            "src.bot.commands.supreme_assembly.send_message_compat",
            new_callable=AsyncMock,
        ) as mock_send:
            await view._on_select(
                cast(discord.Interaction, interaction)
            )  # pyright: ignore[reportPrivateUsage]

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "選擇受款使用者" in call_args.kwargs.get("content", "")

    async def test_on_select_council_shows_modal(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test selecting council type shows transfer modal."""
        view = SupremeAssemblyTransferTypeSelectionView(service=mock_service, guild=mock_guild)

        interaction = MockInteraction(user_id=100)
        interaction.data = {"values": ["council"]}

        with patch(
            "src.bot.commands.supreme_assembly.send_modal_compat",
            new_callable=AsyncMock,
        ) as mock_send_modal:
            await view._on_select(
                cast(discord.Interaction, interaction)
            )  # pyright: ignore[reportPrivateUsage]

            mock_send_modal.assert_called_once()
            call_args = mock_send_modal.call_args
            modal = call_args.args[1]
            assert modal.target_type == "council"

    async def test_on_select_department_shows_department_select(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test selecting department type shows department select view."""
        view = SupremeAssemblyTransferTypeSelectionView(service=mock_service, guild=mock_guild)

        interaction = MockInteraction(user_id=100)
        interaction.data = {"values": ["department"]}

        with patch(
            "src.bot.commands.supreme_assembly.send_message_compat",
            new_callable=AsyncMock,
        ) as mock_send:
            await view._on_select(
                cast(discord.Interaction, interaction)
            )  # pyright: ignore[reportPrivateUsage]

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "選擇受款部門" in call_args.kwargs.get("content", "")

    async def test_on_select_company_shows_no_companies_message(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test selecting company type shows error when no companies available."""
        view = SupremeAssemblyTransferTypeSelectionView(service=mock_service, guild=mock_guild)

        interaction = MockInteraction(user_id=100)
        interaction.data = {"values": ["company"]}

        with (
            patch(
                "src.bot.commands.supreme_assembly.send_message_compat",
                new_callable=AsyncMock,
            ) as mock_send,
            patch(
                "src.bot.ui.company_select.get_active_companies",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await view._on_select(
                cast(discord.Interaction, interaction)
            )  # pyright: ignore[reportPrivateUsage]

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "沒有已登記的公司" in call_args.kwargs.get("content", "")

    async def test_on_select_company_shows_company_select(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test selecting company type shows company selection when companies exist."""
        view = SupremeAssemblyTransferTypeSelectionView(service=mock_service, guild=mock_guild)

        interaction = MockInteraction(user_id=100)
        interaction.data = {"values": ["company"]}

        mock_companies = [
            MockCompany(1, "公司 A", 9600000000000001),
            MockCompany(2, "公司 B", 9600000000000002),
        ]

        with (
            patch(
                "src.bot.commands.supreme_assembly.send_message_compat",
                new_callable=AsyncMock,
            ) as mock_send,
            patch(
                "src.bot.ui.company_select.get_active_companies",
                new_callable=AsyncMock,
                return_value=mock_companies,
            ),
        ):
            await view._on_select(
                cast(discord.Interaction, interaction)
            )  # pyright: ignore[reportPrivateUsage]

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "選擇受款公司" in call_args.kwargs.get("content", "")


class TestSupremeAssemblyCompanySelectView:
    """Tests for SupremeAssemblyCompanySelectView."""

    async def test_init(self, mock_service: MagicMock, mock_guild: MagicMock) -> None:
        """Test initialization."""
        view = SupremeAssemblyCompanySelectView(service=mock_service, guild=mock_guild)

        assert view.service == mock_service
        assert view.guild == mock_guild
        assert view._companies == {}  # pyright: ignore[reportPrivateUsage]

    async def test_setup_returns_false_when_no_companies(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test setup returns False when there are no active companies."""
        view = SupremeAssemblyCompanySelectView(service=mock_service, guild=mock_guild)

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
        view = SupremeAssemblyCompanySelectView(service=mock_service, guild=mock_guild)

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

    async def test_setup_creates_select_menu(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test setup creates a select menu with company options."""
        view = SupremeAssemblyCompanySelectView(service=mock_service, guild=mock_guild)

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
        """Test selecting a company shows the transfer modal."""
        view = SupremeAssemblyCompanySelectView(service=mock_service, guild=mock_guild)

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

        with patch(
            "src.bot.commands.supreme_assembly.send_modal_compat",
            new_callable=AsyncMock,
        ) as mock_send_modal:
            await view._on_select(
                cast(discord.Interaction, interaction)
            )  # pyright: ignore[reportPrivateUsage]

            mock_send_modal.assert_called_once()
            call_args = mock_send_modal.call_args
            modal = call_args.args[1]
            assert modal.target_type == "company"
            assert modal.target_company_name == "公司 A"

    async def test_on_select_handles_invalid_company(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test selecting an invalid company shows error."""
        view = SupremeAssemblyCompanySelectView(service=mock_service, guild=mock_guild)
        view._companies = {}  # Empty  # pyright: ignore[reportPrivateUsage]

        interaction = MockInteraction(user_id=100)
        interaction.data = {"values": ["999"]}  # Non-existent company

        with patch(
            "src.bot.commands.supreme_assembly.send_message_compat",
            new_callable=AsyncMock,
        ) as mock_send:
            await view._on_select(
                cast(discord.Interaction, interaction)
            )  # pyright: ignore[reportPrivateUsage]

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            content = call_args.kwargs.get("content", "")
            assert "找不到" in content


class TestSupremeAssemblyTransferModal:
    """Tests for SupremeAssemblyTransferModal."""

    async def test_init_with_company_target(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test initialization with company as target."""
        modal = SupremeAssemblyTransferModal(
            service=mock_service,
            guild=mock_guild,
            target_type="company",
            target_company_account_id=9600000000000001,
            target_company_name="測試公司",
        )

        assert modal.target_type == "company"
        assert modal.target_company_name == "測試公司"
        assert modal.target_company_account_id == 9600000000000001

        # Check target info shows company
        default = modal.target_info.default
        assert default is not None
        assert "測試公司" in default

    async def test_init_with_council_target(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test initialization with council as target."""
        modal = SupremeAssemblyTransferModal(
            service=mock_service,
            guild=mock_guild,
            target_type="council",
        )

        assert modal.target_type == "council"
        default = modal.target_info.default
        assert default is not None
        assert "常任理事會" in default

    async def test_init_with_user_target(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test initialization with user as target."""
        modal = SupremeAssemblyTransferModal(
            service=mock_service,
            guild=mock_guild,
            target_type="user",
            target_user_id=123456789,
            target_user_name="測試使用者",
        )

        assert modal.target_type == "user"
        assert modal.target_user_id == 123456789
        default = modal.target_info.default
        assert default is not None
        assert "測試使用者" in default

    async def test_init_with_department_target(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test initialization with department as target."""
        modal = SupremeAssemblyTransferModal(
            service=mock_service,
            guild=mock_guild,
            target_type="department",
            target_department_id="interior_affairs",
            target_department_name="內政部",
        )

        assert modal.target_type == "department"
        assert modal.target_department_id == "interior_affairs"
        default = modal.target_info.default
        assert default is not None
        assert "內政部" in default
