"""Integration tests for cross-panel transfer UI functionality.

Tests that the unified transfer type selection pattern works consistently
across all governance panels (enhance-transfer-target-selection change).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.company_select import (
    CompanySelectView,
    build_company_select_options,
    derive_company_account_id,
    get_active_companies,
)

pytestmark = pytest.mark.asyncio


class MockCompany:
    """Mock company object."""

    def __init__(
        self, company_id: int, name: str, account_id: int, license_status: str = "active"
    ) -> None:
        self.id = company_id
        self.name = name
        self.account_id = account_id
        self.license_status = license_status


class MockCompanyList:
    """Mock company list result."""

    def __init__(self, companies: list[MockCompany]) -> None:
        self.companies = companies


class MockUser:
    """Mock Discord user."""

    def __init__(self, user_id: int) -> None:
        self.id = user_id


class MockInteraction:
    """Mock Discord interaction."""

    def __init__(self, user_id: int, guild_id: int = 12345) -> None:
        self.user = MockUser(user_id)
        self.guild_id = guild_id
        self.data: dict[str, Any] | None = None


@pytest.mark.integration
class TestCompanySelectSharedComponent:
    """Tests for shared company selection component used across panels."""

    async def test_get_active_companies_returns_only_active(self) -> None:
        """Test that only active companies are returned."""
        mock_companies = MockCompanyList(
            [
                MockCompany(1, "Active Co", 9600000000000001, "active"),
                MockCompany(2, "Suspended Co", 9600000000000002, "suspended"),
                MockCompany(3, "Another Active", 9600000000000003, "active"),
            ]
        )

        from src.infra.result import Ok

        with (
            patch(
                "src.bot.ui.company_select.get_pool",
                return_value=MagicMock(),
            ),
            patch(
                "src.bot.services.company_service.CompanyService.list_guild_companies",
                new_callable=AsyncMock,
                return_value=Ok(mock_companies),
            ),
        ):
            companies = await get_active_companies(12345)

        # Should only return active companies
        assert len(companies) == 2
        assert all(c.license_status == "active" for c in companies)

    async def test_build_company_select_options_limits_to_25(self) -> None:
        """Test that company options are limited to 25 (Discord limit)."""
        mock_companies = [MockCompany(i, f"Company {i}", 9600000000000000 + i) for i in range(30)]

        options = build_company_select_options(mock_companies)

        assert len(options) == 25
        assert all(isinstance(opt, discord.SelectOption) for opt in options)

    async def test_build_company_select_options_includes_account_id(self) -> None:
        """Test that options include account ID in description."""
        mock_companies = [
            MockCompany(1, "Test Corp", 9600000000000001),
        ]

        options = build_company_select_options(mock_companies)

        assert len(options) == 1
        assert options[0].label == "Test Corp"
        assert options[0].value == "1"
        assert "9600000000000001" in (options[0].description or "")

    async def test_derive_company_account_id_formula(self) -> None:
        """Test company account ID derivation formula."""
        # Account ID = 9_600_000_000_000_000 + company_id
        assert derive_company_account_id(1) == 9_600_000_000_000_001
        assert derive_company_account_id(100) == 9_600_000_000_000_100
        assert derive_company_account_id(999) == 9_600_000_000_000_999

    async def test_company_select_view_setup_success(self) -> None:
        """Test CompanySelectView setup with available companies."""
        mock_companies = [
            MockCompany(1, "Corp A", 9600000000000001),
            MockCompany(2, "Corp B", 9600000000000002),
        ]

        on_selected = AsyncMock()
        view = CompanySelectView(guild_id=12345, on_company_selected=on_selected)

        with patch(
            "src.bot.ui.company_select.get_active_companies",
            new_callable=AsyncMock,
            return_value=mock_companies,
        ):
            result = await view.setup()

        assert result is True
        assert len(view.children) == 1
        assert isinstance(view.children[0], discord.ui.Select)

    async def test_company_select_view_setup_no_companies(self) -> None:
        """Test CompanySelectView setup with no companies."""
        on_selected = AsyncMock()
        view = CompanySelectView(guild_id=12345, on_company_selected=on_selected)

        with patch(
            "src.bot.ui.company_select.get_active_companies",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await view.setup()

        assert result is False


@pytest.mark.integration
class TestTransferTypeConsistency:
    """Tests for consistent transfer type selection across panels."""

    async def test_all_panels_support_company_transfer(self) -> None:
        """Test that all panels have company transfer option."""
        # Import all transfer type selection views
        from src.bot.commands.council import TransferTypeSelectionView
        from src.bot.commands.state_council import StateCouncilTransferTypeSelectionView
        from src.bot.commands.supreme_assembly import (
            SupremeAssemblyTransferTypeSelectionView,
        )
        from src.bot.ui.personal_panel_paginator import PersonalTransferTypeSelectionView

        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = 12345
        mock_service = MagicMock()

        # Personal Panel - has company button
        personal_view = PersonalTransferTypeSelectionView(
            guild_id=12345,
            author_id=100,
            balance=10000,
            currency_display="測試幣",
            transfer_callback=AsyncMock(),
            refresh_callback=AsyncMock(),
        )
        personal_labels = [getattr(c, "label", "") for c in personal_view.children]
        assert any("公司" in label for label in personal_labels)

        # State Council - has company button
        state_council_view = StateCouncilTransferTypeSelectionView(
            service=mock_service,
            guild_id=12345,
            guild=mock_guild,
            author_id=100,
            user_roles=[200],
            source_department="內政部",
            departments=["內政部", "財政部"],
        )
        sc_labels = [getattr(c, "label", "") for c in state_council_view.children]
        assert any("公司" in label for label in sc_labels)

        # Council - has company button (via decorator)
        council_view = TransferTypeSelectionView(service=mock_service, guild=mock_guild)
        council_labels = [getattr(c, "label", "") for c in council_view.children]
        assert any("公司" in label for label in council_labels)

        # Supreme Assembly - has company option in select
        supreme_view = SupremeAssemblyTransferTypeSelectionView(
            service=mock_service, guild=mock_guild
        )
        assert len(supreme_view.children) == 1
        select = supreme_view.children[0]
        assert isinstance(select, discord.ui.Select)
        option_values = [opt.value for opt in select.options]
        assert "company" in option_values


@pytest.mark.integration
class TestAccountIdConsistency:
    """Tests for consistent account ID derivation across panels."""

    async def test_company_account_id_matches_gateway(self) -> None:
        """Test that UI company account ID matches gateway derivation."""
        from src.bot.ui.company_select import derive_company_account_id
        from src.db.gateway.company import CompanyGateway

        # The UI derive function should match the gateway's formula
        company_id = 42
        ui_account_id = derive_company_account_id(company_id)
        gateway_account_id = CompanyGateway.derive_account_id(0, company_id)

        assert ui_account_id == gateway_account_id

    async def test_department_account_id_formula(self) -> None:
        """Test department account ID formula consistency."""
        from src.bot.services.department_registry import get_registry

        registry = get_registry()
        dept = registry.get_by_id("interior_affairs")
        assert dept is not None

        guild_id = 12345
        # Formula: 9_500_000_000_000_000 + guild_id + dept.code
        expected = 9_500_000_000_000_000 + guild_id + dept.code
        assert expected == 9_500_000_000_012_346  # guild_id=12345, code=1

    async def test_council_account_id_formula(self) -> None:
        """Test council account ID formula consistency."""
        from src.bot.services.council_service import CouncilServiceResult

        guild_id = 12345
        council_account_id = CouncilServiceResult.derive_council_account_id(guild_id)

        # Formula: 9_000_000_000_000_000 + guild_id (dedicated council range)
        expected = 9_000_000_000_000_000 + guild_id
        assert council_account_id == expected


@pytest.mark.integration
class TestTransferFlowIntegration:
    """End-to-end integration tests for transfer flows."""

    async def test_personal_to_company_flow(self) -> None:
        """Test personal panel to company transfer flow."""
        from src.bot.ui.personal_panel_paginator import PersonalTransferTypeSelectionView

        transfer_callback = AsyncMock(return_value=(True, "Success"))
        refresh_callback = AsyncMock()

        view = PersonalTransferTypeSelectionView(
            guild_id=12345,
            author_id=100,
            balance=10000,
            currency_display="測試幣",
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        mock_companies = [MockCompany(1, "Target Corp", 9600000000000001)]

        with (
            patch(
                "src.bot.ui.company_select.get_active_companies",
                new_callable=AsyncMock,
                return_value=mock_companies,
            ),
            patch(
                "src.bot.ui.personal_panel_paginator.send_message_compat",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            # Simulate company type selection
            interaction = MockInteraction(user_id=100)
            await view._on_company_type(interaction)  # type: ignore[arg-type]

            # Verify company select view was shown
            mock_send.assert_called()
            call_kwargs = mock_send.call_args.kwargs
            assert call_kwargs.get("view") is not None

    async def test_state_council_to_company_flow(self) -> None:
        """Test state council to company transfer flow."""
        from src.bot.commands.state_council import StateCouncilTransferTypeSelectionView

        mock_service = MagicMock()
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = 12345

        view = StateCouncilTransferTypeSelectionView(
            service=mock_service,
            guild_id=12345,
            guild=mock_guild,
            author_id=100,
            user_roles=[200],
            source_department="財政部",
            departments=["內政部", "財政部"],
        )

        mock_companies = [MockCompany(1, "Target Corp", 9600000000000001)]

        with (
            patch(
                "src.bot.ui.company_select.get_active_companies",
                new_callable=AsyncMock,
                return_value=mock_companies,
            ),
            patch(
                "src.bot.commands.state_council.send_message_compat",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            # Simulate company type selection
            interaction = MockInteraction(user_id=100)
            await view._on_company_type(interaction)  # type: ignore[arg-type]

            # Verify company transfer panel was shown
            mock_send.assert_called()
