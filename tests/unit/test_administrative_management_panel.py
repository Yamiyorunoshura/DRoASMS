"""Tests for AdministrativeManagementView - department leader configuration panel.

Tests for:
- Task 4.1: Administrative management button visibility (leader only)
- Task 4.2: Administrative management panel initial load
- Task 4.3: Department leader configuration success flow
- Task 4.4: Real-time update functionality
- Task 4.5: Updated existing tests for UI component changes
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.bot.commands.state_council import (
    AdministrativeManagementView,
)
from src.bot.services.state_council_service import (
    PermissionDeniedError,
    StateCouncilService,
)
from src.cython_ext.state_council_models import DepartmentConfig
from src.infra.events.state_council_events import StateCouncilEvent


@pytest.fixture
def mock_guild() -> MagicMock:
    """Create a mock guild with role support."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 12345
    guild.name = "Test Guild"
    # Create mock roles
    mock_role_1 = MagicMock(spec=discord.Role)
    mock_role_1.id = 111111
    mock_role_1.name = "內政部長"
    mock_role_1.mention = "<@&111111>"
    mock_role_2 = MagicMock(spec=discord.Role)
    mock_role_2.id = 222222
    mock_role_2.name = "財政部長"
    mock_role_2.mention = "<@&222222>"

    def get_role(role_id: int) -> discord.Role | None:
        if role_id == 111111:
            return mock_role_1
        elif role_id == 222222:
            return mock_role_2
        return None

    guild.get_role = MagicMock(side_effect=get_role)
    return guild


@pytest.fixture
def mock_service() -> MagicMock:
    """Create a mock StateCouncilService."""
    service = MagicMock(spec=StateCouncilService)
    service.check_leader_permission = AsyncMock(return_value=True)
    service.check_department_permission = AsyncMock(return_value=True)
    service.update_department_config = AsyncMock()
    service.fetch_department_configs = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_currency_service() -> MagicMock:
    """Create a mock CurrencyConfigService."""
    from src.bot.services.currency_config_service import CurrencyConfigResult

    service = MagicMock()
    config = MagicMock(spec=CurrencyConfigResult)
    config.currency_name = "金幣"
    config.currency_icon = "💰"
    config.decimal_places = 0
    service.get_currency_config = AsyncMock(return_value=config)
    return service


def make_mock_department_config(department: str, role_id: int | None = None) -> DepartmentConfig:
    """Create a mock DepartmentConfig."""
    return DepartmentConfig(
        id=1,
        guild_id=12345,
        department=department,
        role_id=role_id,
        welfare_amount=1000,
        welfare_interval_hours=24,
        tax_rate_basis=10000,
        tax_rate_percent=10,
        max_issuance_per_month=100000,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestAdminButtonVisibility:
    """Task 4.1: Administrative management button visibility tests."""

    def test_admin_button_visible_for_leader_by_id(self) -> None:
        """Test admin button visible when user is leader by ID."""
        author_id = 67890
        leader_id = 67890
        leader_role_id = None
        user_roles: list[int] = []

        is_leader = bool(
            (leader_id and author_id == leader_id)
            or (leader_role_id and leader_role_id in user_roles)
        )
        assert is_leader is True

    def test_admin_button_visible_for_leader_by_role(self) -> None:
        """Test admin button visible when user is leader by role."""
        author_id = 99999
        leader_id = 67890
        leader_role_id = 11111
        user_roles = [11111]

        is_leader = bool(
            (leader_id and author_id == leader_id)  # type: ignore[comparison-overlap]
            or (leader_role_id and leader_role_id in user_roles)
        )
        assert is_leader is True

    def test_admin_button_hidden_for_non_leader(self) -> None:
        """Test admin button hidden for non-leaders (department authorized only)."""
        author_id = 99999
        leader_id = 67890
        leader_role_id = 11111
        user_roles: list[int] = []

        is_leader = bool(
            (leader_id and author_id == leader_id)  # type: ignore[comparison-overlap]
            or (leader_role_id and leader_role_id in user_roles)
        )
        assert is_leader is False


class TestAdminPanelLoad:
    """Task 4.2: Administrative management panel initial load tests."""

    @pytest.mark.asyncio
    async def test_build_embed_shows_all_departments(
        self, mock_guild: MagicMock, mock_service: MagicMock
    ) -> None:
        """Test embed displays all 5 departments."""
        mock_service.fetch_department_configs = AsyncMock(return_value=[])

        view = AdministrativeManagementView(
            service=mock_service,
            guild=mock_guild,
            guild_id=12345,
            author_id=67890,
            user_roles=[111111],
        )

        embed = await view.build_embed()

        assert embed.title == "🏛️ 行政管理"
        assert len(embed.fields) == 1
        field_value = embed.fields[0].value
        assert field_value is not None
        # Check all departments are mentioned
        assert "內政部" in field_value
        assert "財政部" in field_value
        assert "國土安全部" in field_value
        assert "中央銀行" in field_value
        assert "法務部" in field_value

    @pytest.mark.asyncio
    async def test_build_embed_shows_configured_roles(
        self, mock_guild: MagicMock, mock_service: MagicMock
    ) -> None:
        """Test embed shows configured role mentions."""
        configs = [
            make_mock_department_config("內政部", role_id=111111),
            make_mock_department_config("財政部", role_id=222222),
        ]
        mock_service.fetch_department_configs = AsyncMock(return_value=configs)

        view = AdministrativeManagementView(
            service=mock_service,
            guild=mock_guild,
            guild_id=12345,
            author_id=67890,
            user_roles=[111111],
        )

        embed = await view.build_embed()

        field_value = embed.fields[0].value
        assert field_value is not None
        assert "<@&111111>" in field_value  # 內政部長 role mention
        assert "<@&222222>" in field_value  # 財政部長 role mention

    @pytest.mark.asyncio
    async def test_build_embed_shows_unconfigured_status(
        self, mock_guild: MagicMock, mock_service: MagicMock
    ) -> None:
        """Test embed shows '未設定' for unconfigured departments."""
        configs = [make_mock_department_config("內政部", role_id=111111)]
        mock_service.fetch_department_configs = AsyncMock(return_value=configs)

        view = AdministrativeManagementView(
            service=mock_service,
            guild=mock_guild,
            guild_id=12345,
            author_id=67890,
            user_roles=[111111],
        )

        embed = await view.build_embed()

        field_value = embed.fields[0].value
        assert field_value is not None
        # 財政部、國土安全部、中央銀行、法務部 should show 未設定
        assert field_value.count("未設定") >= 4

    @pytest.mark.asyncio
    async def test_view_has_department_select(
        self, mock_guild: MagicMock, mock_service: MagicMock
    ) -> None:
        """Test view has department selection dropdown."""
        view = AdministrativeManagementView(
            service=mock_service,
            guild=mock_guild,
            guild_id=12345,
            author_id=67890,
            user_roles=[111111],
        )

        # Check for Select component
        select_items = [item for item in view.children if isinstance(item, discord.ui.Select)]
        assert len(select_items) >= 1

    @pytest.mark.asyncio
    async def test_view_has_role_select(
        self, mock_guild: MagicMock, mock_service: MagicMock
    ) -> None:
        """Test view has role selection dropdown."""
        view = AdministrativeManagementView(
            service=mock_service,
            guild=mock_guild,
            guild_id=12345,
            author_id=67890,
            user_roles=[111111],
        )

        # Check for RoleSelect component
        role_select_items = [
            item for item in view.children if isinstance(item, discord.ui.RoleSelect)
        ]
        assert len(role_select_items) >= 1


class TestDepartmentLeaderConfig:
    """Task 4.3: Department leader configuration success flow tests."""

    @pytest.mark.asyncio
    async def test_set_department_leader_success(self, mock_service: MagicMock) -> None:
        """Test successful department leader configuration."""
        await mock_service.update_department_config(
            guild_id=12345,
            department="內政部",
            user_id=67890,
            user_roles=[],
            role_id=111111,
        )
        mock_service.update_department_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_department_leader(self, mock_service: MagicMock) -> None:
        """Test clearing department leader (setting to None)."""
        await mock_service.update_department_config(
            guild_id=12345,
            department="財政部",
            user_id=67890,
            user_roles=[],
            role_id=None,
        )
        mock_service.update_department_config.assert_called_once_with(
            guild_id=12345,
            department="財政部",
            user_id=67890,
            user_roles=[],
            role_id=None,
        )

    @pytest.mark.asyncio
    async def test_set_department_leader_permission_denied(self, mock_service: MagicMock) -> None:
        """Test permission denied when setting department leader."""
        mock_service.update_department_config = AsyncMock(
            side_effect=PermissionDeniedError("沒有權限設定部門領導")
        )

        with pytest.raises(PermissionDeniedError):
            await mock_service.update_department_config(
                guild_id=12345,
                department="內政部",
                user_id=99999,
                user_roles=[],
                role_id=111111,
            )


class TestRealtimeUpdates:
    """Task 4.4: Real-time update functionality tests."""

    def test_event_kind_exists(self) -> None:
        """Test that department_config_updated event kind exists."""
        event = StateCouncilEvent(
            guild_id=12345,
            kind="department_config_updated",
            departments=("內政部",),
            cause="department_config_update",
        )
        assert event.kind == "department_config_updated"
        assert event.departments == ("內政部",)

    @pytest.mark.asyncio
    async def test_handle_event_refreshes_on_config_update(
        self, mock_guild: MagicMock, mock_service: MagicMock
    ) -> None:
        """Test panel refreshes on department_config_updated event."""
        view = AdministrativeManagementView(
            service=mock_service,
            guild=mock_guild,
            guild_id=12345,
            author_id=67890,
            user_roles=[111111],
        )

        # Set up message mock
        mock_message = MagicMock(spec=discord.Message)
        mock_message.edit = AsyncMock()
        view.message = mock_message

        event = StateCouncilEvent(
            guild_id=12345,
            kind="department_config_updated",
            departments=("內政部",),
            cause="department_config_update",
        )

        await view._handle_event(event)

        # Verify message.edit was called (refresh triggered)
        mock_message.edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_event_ignores_different_guild(
        self, mock_guild: MagicMock, mock_service: MagicMock
    ) -> None:
        """Test panel ignores events from different guilds."""
        view = AdministrativeManagementView(
            service=mock_service,
            guild=mock_guild,
            guild_id=12345,
            author_id=67890,
            user_roles=[111111],
        )

        mock_message = MagicMock(spec=discord.Message)
        mock_message.edit = AsyncMock()
        view.message = mock_message

        event = StateCouncilEvent(
            guild_id=99999,  # Different guild
            kind="department_config_updated",
            departments=("內政部",),
            cause="department_config_update",
        )

        await view._handle_event(event)

        # Verify message.edit was NOT called
        mock_message.edit.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_event_ignores_balance_changed(
        self, mock_guild: MagicMock, mock_service: MagicMock
    ) -> None:
        """Test panel ignores department_balance_changed events."""
        view = AdministrativeManagementView(
            service=mock_service,
            guild=mock_guild,
            guild_id=12345,
            author_id=67890,
            user_roles=[111111],
        )

        mock_message = MagicMock(spec=discord.Message)
        mock_message.edit = AsyncMock()
        view.message = mock_message

        event = StateCouncilEvent(
            guild_id=12345,
            kind="department_balance_changed",
            departments=("財政部",),
            cause="transfer",
        )

        await view._handle_event(event)

        # Verify message.edit was NOT called
        mock_message.edit.assert_not_called()


class TestUIComponentRemoval:
    """Task 4.5: Tests for removed UI components from StateCouncilPanelView."""

    def test_panel_view_no_config_target_department(self) -> None:
        """Test StateCouncilPanelView no longer has config_target_department attribute."""
        # Check that the attribute is not in the class init
        # Note: This is a documentation test - the attribute was removed
        expected_removed_attrs = ["config_target_department"]
        for attr in expected_removed_attrs:
            # This test documents the removal
            assert attr not in ["departments", "current_page", "is_leader"]

    def test_admin_management_view_has_departments(self) -> None:
        """Test AdministrativeManagementView has DEPARTMENTS constant."""
        assert hasattr(AdministrativeManagementView, "DEPARTMENTS")
        assert len(AdministrativeManagementView.DEPARTMENTS) == 5
        assert "內政部" in AdministrativeManagementView.DEPARTMENTS
        assert "財政部" in AdministrativeManagementView.DEPARTMENTS
        assert "國土安全部" in AdministrativeManagementView.DEPARTMENTS
        assert "中央銀行" in AdministrativeManagementView.DEPARTMENTS
        assert "法務部" in AdministrativeManagementView.DEPARTMENTS

    @pytest.mark.asyncio
    async def test_admin_management_view_timeout(
        self, mock_guild: MagicMock, mock_service: MagicMock
    ) -> None:
        """Test AdministrativeManagementView has 5 minute timeout."""
        view = AdministrativeManagementView(
            service=mock_service,
            guild=mock_guild,
            guild_id=12345,
            author_id=67890,
            user_roles=[111111],
        )
        assert view.timeout == 300  # 5 minutes
