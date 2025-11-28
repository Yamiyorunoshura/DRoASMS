"""Unit tests for State Council transfer UI components.

Tests the transfer type selection view and company transfer flow
for the State Council panel (enhance-transfer-target-selection change).
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.commands.state_council import (
    DepartmentCompanyTransferPanelView,
    StateCouncilAccountTransferTypeView,
    StateCouncilToCompanyTransferView,
    StateCouncilToGovernmentDeptTransferView,
    StateCouncilToUserTransferView,
    StateCouncilTransferAmountModal,
    StateCouncilTransferTypeSelectionView,
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
        self.edit_message = AsyncMock()
        self.send_modal = AsyncMock()


class MockInteraction:
    """Mock Discord interaction."""

    def __init__(self, user_id: int, guild_id: int = 12345) -> None:
        self.user = MockUser(user_id)
        self.response = MockResponse()
        self.data: dict[str, Any] | None = None
        self.guild_id = guild_id
        self.original_response = AsyncMock(return_value=MagicMock())


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
    """Create a mock state council service."""
    service = MagicMock()
    service.transfer_to_user = AsyncMock(return_value={"success": True})
    service.transfer_to_company = AsyncMock(return_value={"success": True})
    return service


@pytest.fixture
def mock_guild() -> MagicMock:
    """Create a mock Discord guild."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 12345
    return guild


class TestStateCouncilTransferTypeSelectionView:
    """Tests for StateCouncilTransferTypeSelectionView."""

    async def test_init_creates_user_and_company_buttons(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test that initialization creates user and company transfer buttons."""
        view = StateCouncilTransferTypeSelectionView(
            service=mock_service,
            guild_id=12345,
            guild=mock_guild,
            author_id=100,
            user_roles=[200, 300],
            source_department="內政部",
            departments=["內政部", "財政部", "國土安全部"],
        )

        # Check that view has children (buttons)
        assert len(view.children) == 2

        # Check button labels
        button_labels = [getattr(child, "label", "") for child in view.children]
        assert "👤 使用者" in button_labels
        assert "🏢 公司" in button_labels

    async def test_author_check_blocks_non_author(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test that non-author users are blocked from interacting."""
        view = StateCouncilTransferTypeSelectionView(
            service=mock_service,
            guild_id=12345,
            guild=mock_guild,
            author_id=100,
            user_roles=[200],
            source_department="內政部",
            departments=["內政部", "財政部"],
        )

        # Create interaction from different user
        interaction = MockInteraction(user_id=999)  # Different from author_id=100

        # Test _check_author
        with patch(
            "src.bot.commands.state_council.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            result = await view._check_author(cast(discord.Interaction, interaction))
            assert result is False
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "僅限面板開啟者操作" in call_args.kwargs.get("content", "")

    async def test_author_check_allows_author(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test that the author can interact."""
        view = StateCouncilTransferTypeSelectionView(
            service=mock_service,
            guild_id=12345,
            guild=mock_guild,
            author_id=100,
            user_roles=[200],
            source_department="內政部",
            departments=["內政部", "財政部"],
        )

        interaction = MockInteraction(user_id=100)  # Same as author_id

        result = await view._check_author(cast(discord.Interaction, interaction))
        assert result is True


class TestDepartmentCompanyTransferPanelView:
    """Tests for DepartmentCompanyTransferPanelView."""

    async def test_init(self, mock_service: MagicMock) -> None:
        """Test initialization of company transfer panel."""
        view = DepartmentCompanyTransferPanelView(
            service=mock_service,
            guild_id=12345,
            author_id=100,
            user_roles=[200, 300],
            source_department="財政部",
            departments=["內政部", "財政部", "國土安全部"],
        )

        assert view.guild_id == 12345
        assert view.author_id == 100
        assert view.source_department == "財政部"
        assert view.company_id is None
        assert view.company_account_id is None

    async def test_build_embed_with_source_department(self, mock_service: MagicMock) -> None:
        """Test embed creation with source department set."""
        view = DepartmentCompanyTransferPanelView(
            service=mock_service,
            guild_id=12345,
            author_id=100,
            user_roles=[200],
            source_department="財政部",
            departments=["內政部", "財政部"],
        )

        embed = view.build_embed()

        assert "財政部" in embed.title
        assert embed.fields is not None

        # Check source department field
        field_values = {f.name: f.value for f in embed.fields}
        assert "來源部門" in field_values
        assert field_values["來源部門"] == "財政部"

    async def test_build_embed_without_source_department(self, mock_service: MagicMock) -> None:
        """Test embed creation without source department (overview mode)."""
        view = DepartmentCompanyTransferPanelView(
            service=mock_service,
            guild_id=12345,
            author_id=100,
            user_roles=[200],
            source_department=None,
            departments=["內政部", "財政部"],
        )

        embed = view.build_embed()

        field_values = {f.name: f.value for f in embed.fields}
        assert "來源部門" in field_values
        assert "總覽" in field_values["來源部門"]

    async def test_can_submit_returns_false_without_required_fields(
        self, mock_service: MagicMock
    ) -> None:
        """Test _can_submit returns False when required fields are missing."""
        view = DepartmentCompanyTransferPanelView(
            service=mock_service,
            guild_id=12345,
            author_id=100,
            user_roles=[200],
            source_department="財政部",
            departments=["內政部", "財政部"],
        )

        # All fields missing
        assert view._can_submit() is False

        # Only company set
        view.company_account_id = 9600000000000001
        assert view._can_submit() is False

        # Company and amount set
        view.amount = 100
        assert view._can_submit() is False

        # All except source_department
        view.reason = "測試轉帳"
        assert view._can_submit() is True  # source_department is already set

    async def test_can_submit_returns_true_with_all_fields(self, mock_service: MagicMock) -> None:
        """Test _can_submit returns True when all required fields are set."""
        view = DepartmentCompanyTransferPanelView(
            service=mock_service,
            guild_id=12345,
            author_id=100,
            user_roles=[200],
            source_department="財政部",
            departments=["內政部", "財政部"],
        )

        view.company_account_id = 9600000000000001
        view.company_name = "測試公司"
        view.amount = 1000
        view.reason = "測試轉帳給公司"

        assert view._can_submit() is True

    async def test_setup_returns_false_when_no_companies(self, mock_service: MagicMock) -> None:
        """Test setup returns False when there are no active companies."""
        view = DepartmentCompanyTransferPanelView(
            service=mock_service,
            guild_id=12345,
            author_id=100,
            user_roles=[200],
            source_department="財政部",
            departments=["內政部", "財政部"],
        )

        with patch(
            "src.bot.ui.company_select.get_active_companies",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await view.setup()
            assert result is False

    async def test_setup_returns_true_with_companies(self, mock_service: MagicMock) -> None:
        """Test setup returns True when companies are available."""
        view = DepartmentCompanyTransferPanelView(
            service=mock_service,
            guild_id=12345,
            author_id=100,
            user_roles=[200],
            source_department="財政部",
            departments=["內政部", "財政部"],
        )

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
            assert len(view._companies) == 2

    async def test_build_embed_shows_company_when_selected(self, mock_service: MagicMock) -> None:
        """Test embed shows company name when a company is selected."""
        view = DepartmentCompanyTransferPanelView(
            service=mock_service,
            guild_id=12345,
            author_id=100,
            user_roles=[200],
            source_department="財政部",
            departments=["內政部", "財政部"],
        )

        view.company_name = "測試公司 ABC"
        view.company_account_id = 9600000000000001

        embed = view.build_embed()

        field_values = {f.name: f.value for f in embed.fields}
        assert "受款公司" in field_values
        assert "測試公司 ABC" in field_values["受款公司"]


class TestStateCouncilAccountTransferTypeView:
    """Tests for StateCouncilAccountTransferTypeView (新增政府部門轉帳選項)."""

    async def test_init_creates_three_buttons(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test that initialization creates user, company, and department buttons."""
        view = StateCouncilAccountTransferTypeView(
            service=mock_service,
            guild_id=12345,
            guild=mock_guild,
            author_id=100,
            user_roles=[200, 300],
        )

        # Check that view has 3 children (buttons)
        assert len(view.children) == 3

        # Check button labels
        button_labels = [getattr(child, "label", "") for child in view.children]
        assert "👤 使用者" in button_labels
        assert "🏢 公司" in button_labels
        assert "🏛️ 政府部門" in button_labels

    async def test_author_check_blocks_non_author(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test that non-author users are blocked from interacting."""
        view = StateCouncilAccountTransferTypeView(
            service=mock_service,
            guild_id=12345,
            guild=mock_guild,
            author_id=100,
            user_roles=[200],
        )

        interaction = MockInteraction(user_id=999)  # Different from author_id=100

        with patch(
            "src.bot.commands.state_council.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            result = await view._check_author(cast(discord.Interaction, interaction))
            assert result is False
            mock_send.assert_called_once()

    async def test_author_check_allows_author(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test that the author can interact."""
        view = StateCouncilAccountTransferTypeView(
            service=mock_service,
            guild_id=12345,
            guild=mock_guild,
            author_id=100,
            user_roles=[200],
        )

        interaction = MockInteraction(user_id=100)  # Same as author_id

        result = await view._check_author(cast(discord.Interaction, interaction))
        assert result is True


class TestStateCouncilToUserTransferView:
    """Tests for StateCouncilToUserTransferView (國務院→使用者轉帳)."""

    async def test_init(self, mock_service: MagicMock, mock_guild: MagicMock) -> None:
        """Test initialization of State Council to user transfer panel."""
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            view = StateCouncilToUserTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200, 300],
            )

            assert view.guild_id == 12345
            assert view.author_id == 100
            assert view.recipient_id is None
            assert view.amount is None
            assert view.reason is None

    async def test_build_embed_shows_state_council_as_source(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test embed shows State Council account as source."""
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            view = StateCouncilToUserTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200],
            )

            embed = view.build_embed()

            assert "國務院帳戶" in embed.title
            field_values = {f.name: f.value for f in embed.fields}
            assert "來源" in field_values
            assert "國務院帳戶" in field_values["來源"]

    async def test_can_submit_returns_false_without_required_fields(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test _can_submit returns False when required fields are missing."""
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            view = StateCouncilToUserTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200],
            )

            assert view._can_submit() is False

            view.recipient_id = 999
            assert view._can_submit() is False

            view.amount = 100
            assert view._can_submit() is False

            view.reason = "測試轉帳"
            assert view._can_submit() is True


class TestStateCouncilToCompanyTransferView:
    """Tests for StateCouncilToCompanyTransferView (國務院→公司轉帳)."""

    async def test_init(self, mock_service: MagicMock, mock_guild: MagicMock) -> None:
        """Test initialization of State Council to company transfer panel."""
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            view = StateCouncilToCompanyTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200, 300],
            )

            assert view.guild_id == 12345
            assert view.author_id == 100
            assert view.company_id is None
            assert view.company_account_id is None

    async def test_build_embed_shows_state_council_as_source(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test embed shows State Council account as source."""
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            view = StateCouncilToCompanyTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200],
            )

            embed = view.build_embed()

            assert "國務院帳戶" in embed.title
            field_values = {f.name: f.value for f in embed.fields}
            assert "來源" in field_values
            assert "國務院帳戶" in field_values["來源"]

    async def test_setup_returns_false_when_no_companies(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test setup returns False when there are no active companies."""
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            view = StateCouncilToCompanyTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200],
            )

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
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            view = StateCouncilToCompanyTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200],
            )

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
                assert len(view._companies) == 2


class TestStateCouncilToGovernmentDeptTransferView:
    """Tests for StateCouncilToGovernmentDeptTransferView (國務院→政府部門轉帳)."""

    async def test_init(self, mock_service: MagicMock, mock_guild: MagicMock) -> None:
        """Test initialization of State Council to government dept transfer panel."""
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            view = StateCouncilToGovernmentDeptTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200, 300],
            )

            assert view.guild_id == 12345
            assert view.author_id == 100
            assert view.target_dept_id is None
            assert view.target_dept_name is None

    async def test_build_embed_shows_state_council_as_source(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test embed shows State Council account as source."""
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            view = StateCouncilToGovernmentDeptTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200],
            )

            embed = view.build_embed()

            assert "國務院帳戶" in embed.title
            field_values = {f.name: f.value for f in embed.fields}
            assert "來源" in field_values
            assert "國務院帳戶" in field_values["來源"]

    async def test_government_departments_list(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test that government departments list includes all expected departments."""
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            view = StateCouncilToGovernmentDeptTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200],
            )

            dept_names = [name for _, _, name in view.GOVERNMENT_DEPARTMENTS]
            assert "常任理事會" in dept_names
            assert "內政部" in dept_names
            assert "財政部" in dept_names
            assert "國土安全部" in dept_names
            assert "中央銀行" in dept_names
            assert "法務部" in dept_names
            assert "最高人民會議" in dept_names

    async def test_can_submit_returns_false_without_required_fields(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """Test _can_submit returns False when required fields are missing."""
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            view = StateCouncilToGovernmentDeptTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200],
            )

            assert view._can_submit() is False

            view.target_dept_id = "interior_affairs"
            assert view._can_submit() is False

            view.amount = 100
            assert view._can_submit() is False

            view.reason = "測試撥款"
            assert view._can_submit() is True


class TestStateCouncilTransferAmountModal:
    """Tests for StateCouncilTransferAmountModal (轉帳金額與理由輸入)."""

    async def test_init(self, mock_service: MagicMock, mock_guild: MagicMock) -> None:
        """Test modal initialization."""
        # Create a mock parent view
        with patch("src.bot.commands.state_council.get_pool", return_value=MagicMock()):
            parent_view = StateCouncilToUserTransferView(
                service=mock_service,
                guild_id=12345,
                guild=mock_guild,
                author_id=100,
                user_roles=[200],
            )

            modal = StateCouncilTransferAmountModal(parent_view)

            assert modal.parent_view == parent_view
            assert len(modal.children) == 2  # amount and reason inputs
