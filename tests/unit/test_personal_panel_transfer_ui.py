"""Unit tests for Personal Panel transfer UI components.

Tests the unified transfer type selection flow for the Personal Panel
(enhance-transfer-target-selection change).
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.personal_panel_paginator import (
    PersonalTransferTypeSelectionView,
    TransferModal,
)

pytestmark = pytest.mark.asyncio


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
def transfer_callback() -> AsyncMock:
    """Create a mock transfer callback."""
    callback = AsyncMock()
    callback.return_value = (True, "轉帳成功")
    return callback


@pytest.fixture
def refresh_callback() -> AsyncMock:
    """Create a mock refresh callback."""
    callback = AsyncMock()
    callback.return_value = (MagicMock(), [])
    return callback


class TestPersonalTransferTypeSelectionView:
    """Tests for PersonalTransferTypeSelectionView."""

    async def test_init_creates_three_type_buttons(
        self, transfer_callback: AsyncMock, refresh_callback: AsyncMock
    ) -> None:
        """Test that initialization creates user, govt, and company buttons."""
        view = PersonalTransferTypeSelectionView(
            guild_id=12345,
            author_id=100,
            balance=10000,
            currency_display="測試幣 💰",
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        # Check that view has 3 buttons
        assert len(view.children) == 3

        # Check button labels
        button_labels = [getattr(child, "label", "") for child in view.children]
        assert "👤 使用者" in button_labels
        assert "🏛️ 政府部門" in button_labels
        assert "🏢 公司" in button_labels

    async def test_author_check_blocks_non_author(
        self, transfer_callback: AsyncMock, refresh_callback: AsyncMock
    ) -> None:
        """Test that non-author users are blocked from interacting."""
        view = PersonalTransferTypeSelectionView(
            guild_id=12345,
            author_id=100,
            balance=10000,
            currency_display="測試幣",
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        interaction = MockInteraction(user_id=999)  # Different from author_id=100

        with patch(
            "src.bot.ui.personal_panel_paginator.send_message_compat",
            new_callable=AsyncMock,
        ) as mock_send:
            result = await view._check_author(
                cast(discord.Interaction, interaction)
            )  # pyright: ignore[reportPrivateUsage]
            assert result is False
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "僅限面板開啟者操作" in call_args.kwargs.get("content", "")

    async def test_author_check_allows_author(
        self, transfer_callback: AsyncMock, refresh_callback: AsyncMock
    ) -> None:
        """Test that the author can interact."""
        view = PersonalTransferTypeSelectionView(
            guild_id=12345,
            author_id=100,
            balance=10000,
            currency_display="測試幣",
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        interaction = MockInteraction(user_id=100)

        result = await view._check_author(
            cast(discord.Interaction, interaction)
        )  # pyright: ignore[reportPrivateUsage]
        assert result is True

    async def test_on_company_type_shows_no_companies_message(
        self, transfer_callback: AsyncMock, refresh_callback: AsyncMock
    ) -> None:
        """Test company type selection shows error when no companies available."""
        view = PersonalTransferTypeSelectionView(
            guild_id=12345,
            author_id=100,
            balance=10000,
            currency_display="測試幣",
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        interaction = MockInteraction(user_id=100)

        with (
            patch(
                "src.bot.ui.personal_panel_paginator.send_message_compat",
                new_callable=AsyncMock,
            ) as mock_send,
            patch(
                "src.bot.ui.company_select.get_active_companies",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await view._on_company_type(
                cast(discord.Interaction, interaction)
            )  # pyright: ignore[reportPrivateUsage]

            # Should show no companies message
            mock_send.assert_called()
            call_args = mock_send.call_args
            content = call_args.kwargs.get("content", "")
            assert "沒有已登記的公司" in content

    async def test_on_company_type_shows_company_select(
        self, transfer_callback: AsyncMock, refresh_callback: AsyncMock
    ) -> None:
        """Test company type selection shows company selection view when companies exist."""
        view = PersonalTransferTypeSelectionView(
            guild_id=12345,
            author_id=100,
            balance=10000,
            currency_display="測試幣",
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        interaction = MockInteraction(user_id=100)

        mock_companies = [
            MockCompany(1, "公司 A", 9600000000000001),
            MockCompany(2, "公司 B", 9600000000000002),
        ]

        with (
            patch(
                "src.bot.ui.personal_panel_paginator.send_message_compat",
                new_callable=AsyncMock,
            ) as mock_send,
            patch(
                "src.bot.ui.company_select.get_active_companies",
                new_callable=AsyncMock,
                return_value=mock_companies,
            ),
        ):
            await view._on_company_type(
                cast(discord.Interaction, interaction)
            )  # pyright: ignore[reportPrivateUsage]

            # Should show company selection view
            mock_send.assert_called()
            call_args = mock_send.call_args
            assert call_args.kwargs.get("view") is not None
            assert "選擇要轉帳的公司" in call_args.kwargs.get("content", "")


class TestTransferModal:
    """Tests for TransferModal."""

    async def test_init_sets_title_with_target_name(self) -> None:
        """Test modal title includes target name."""
        on_submit = AsyncMock()
        modal = TransferModal(
            target_name="測試用戶",
            currency_display="測試幣 💰",
            available_balance=10000,
            on_submit=on_submit,
        )

        assert "測試用戶" in modal.title

    async def test_init_sets_balance_placeholder(self) -> None:
        """Test amount input placeholder shows available balance."""
        on_submit = AsyncMock()
        modal = TransferModal(
            target_name="測試用戶",
            currency_display="測試幣",
            available_balance=10000,
            on_submit=on_submit,
        )

        placeholder = modal.amount_input.placeholder
        assert placeholder is not None
        assert "10,000" in placeholder
        assert "測試幣" in placeholder

    async def test_on_submit_calls_callback_with_valid_amount(self) -> None:
        """Test on_submit calls callback with valid amount."""
        on_submit = AsyncMock()
        modal = TransferModal(
            target_name="測試用戶",
            currency_display="測試幣",
            available_balance=10000,
            on_submit=on_submit,
        )

        # Set input values
        modal.amount_input._value = "1000"  # pyright: ignore[reportPrivateUsage]
        modal.reason_input._value = "測試轉帳"  # pyright: ignore[reportPrivateUsage]

        interaction = MockInteraction(user_id=100)

        await modal.on_submit(cast(discord.Interaction, interaction))

        on_submit.assert_called_once_with(cast(discord.Interaction, interaction), 1000, "測試轉帳")

    async def test_on_submit_handles_invalid_amount(self) -> None:
        """Test on_submit shows error for invalid amount."""
        on_submit = AsyncMock()
        modal = TransferModal(
            target_name="測試用戶",
            currency_display="測試幣",
            available_balance=10000,
            on_submit=on_submit,
        )

        # Set invalid amount
        modal.amount_input._value = "invalid"  # pyright: ignore[reportPrivateUsage]
        modal.reason_input._value = ""  # pyright: ignore[reportPrivateUsage]

        interaction = MockInteraction(user_id=100)

        with patch(
            "src.bot.ui.personal_panel_paginator.send_message_compat",
            new_callable=AsyncMock,
        ) as mock_send:
            await modal.on_submit(cast(discord.Interaction, interaction))

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "正整數" in call_args.kwargs.get("content", "")

        # Callback should not be called
        on_submit.assert_not_called()

    async def test_on_submit_handles_empty_reason(self) -> None:
        """Test on_submit handles empty reason (optional field)."""
        on_submit = AsyncMock()
        modal = TransferModal(
            target_name="測試用戶",
            currency_display="測試幣",
            available_balance=10000,
            on_submit=on_submit,
        )

        # Set valid amount with empty reason
        modal.amount_input._value = "500"  # pyright: ignore[reportPrivateUsage]
        modal.reason_input._value = ""  # pyright: ignore[reportPrivateUsage]

        interaction = MockInteraction(user_id=100)

        await modal.on_submit(cast(discord.Interaction, interaction))

        # Should call with None for reason
        on_submit.assert_called_once_with(cast(discord.Interaction, interaction), 500, None)


class TestPersonalTransferCompanyIntegration:
    """Integration tests for personal panel company transfer."""

    async def test_handle_company_transfer_success(
        self, transfer_callback: AsyncMock, refresh_callback: AsyncMock
    ) -> None:
        """Test successful company transfer handling."""
        view = PersonalTransferTypeSelectionView(
            guild_id=12345,
            author_id=100,
            balance=10000,
            currency_display="測試幣",
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        interaction = MockInteraction(user_id=100)

        with patch(
            "src.bot.ui.personal_panel_paginator.send_message_compat",
            new_callable=AsyncMock,
        ) as mock_send:
            await view._handle_company_transfer(  # pyright: ignore[reportPrivateUsage]
                cast(discord.Interaction, interaction),
                amount=1000,
                reason="公司付款",
                account_id=9600000000000001,
                company_name="測試公司",
            )

            # Should call transfer callback
            transfer_callback.assert_called_once_with(
                12345,  # guild_id
                100,  # author_id
                9600000000000001,  # account_id
                "公司付款",  # reason
                1000,  # amount
            )

            # Should show success message
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "成功" in call_args.kwargs.get("content", "")

    async def test_handle_company_transfer_insufficient_balance(
        self, transfer_callback: AsyncMock, refresh_callback: AsyncMock
    ) -> None:
        """Test company transfer fails with insufficient balance."""
        view = PersonalTransferTypeSelectionView(
            guild_id=12345,
            author_id=100,
            balance=100,  # Low balance
            currency_display="測試幣",
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        interaction = MockInteraction(user_id=100)

        with patch(
            "src.bot.ui.personal_panel_paginator.send_message_compat",
            new_callable=AsyncMock,
        ) as mock_send:
            await view._handle_company_transfer(  # pyright: ignore[reportPrivateUsage]
                cast(discord.Interaction, interaction),
                amount=1000,  # More than balance
                reason="公司付款",
                account_id=9600000000000001,
                company_name="測試公司",
            )

            # Should show error message
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "餘額不足" in call_args.kwargs.get("content", "")

        # Transfer callback should not be called
        transfer_callback.assert_not_called()

    async def test_handle_company_transfer_zero_amount(
        self, transfer_callback: AsyncMock, refresh_callback: AsyncMock
    ) -> None:
        """Test company transfer fails with zero amount."""
        view = PersonalTransferTypeSelectionView(
            guild_id=12345,
            author_id=100,
            balance=10000,
            currency_display="測試幣",
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        interaction = MockInteraction(user_id=100)

        with patch(
            "src.bot.ui.personal_panel_paginator.send_message_compat",
            new_callable=AsyncMock,
        ) as mock_send:
            await view._handle_company_transfer(  # pyright: ignore[reportPrivateUsage]
                cast(discord.Interaction, interaction),
                amount=0,
                reason="公司付款",
                account_id=9600000000000001,
                company_name="測試公司",
            )

            # Should show error message
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "大於 0" in call_args.kwargs.get("content", "")

        # Transfer callback should not be called
        transfer_callback.assert_not_called()
