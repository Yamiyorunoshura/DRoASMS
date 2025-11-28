"""測試個人面板元件。"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from src.bot.services.currency_config_service import CurrencyConfigResult
from src.bot.services.department_registry import Department, get_registry
from src.bot.services.state_council_service import StateCouncilNotConfiguredError
from src.bot.ui.personal_panel_paginator import PersonalPanelView, TransferModal

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


class MockBalanceSnapshot:
    """模擬餘額快照。"""

    def __init__(
        self,
        balance: int = 10000,
        is_throttled: bool = False,
        throttled_until: datetime | None = None,
        last_modified_at: datetime | None = None,
    ) -> None:
        self.balance = balance
        self.is_throttled = is_throttled
        self.throttled_until = throttled_until
        self.last_modified_at = last_modified_at or datetime.now(timezone.utc)


class MockHistoryEntry:
    """模擬交易歷史記錄。"""

    def __init__(
        self,
        amount: int = 100,
        is_credit: bool = True,
        is_debit: bool = False,
        initiator_id: int | None = 123456789,
        target_id: int | None = 987654321,
        reason: str | None = "測試交易",
        created_at: datetime | None = None,
        direction: str = "in",
    ) -> None:
        self.amount = amount
        self.is_credit = is_credit
        self.is_debit = is_debit
        self.initiator_id = initiator_id
        self.target_id = target_id
        self.reason = reason
        self.created_at = created_at or datetime.now(timezone.utc)
        self.direction = direction


class MockCurrencyConfig:
    """模擬貨幣配置。"""

    def __init__(
        self,
        currency_name: str = "測試幣",
        currency_icon: str = "💰",
    ) -> None:
        self.currency_name = currency_name
        self.currency_icon = currency_icon


@pytest.fixture
def sample_balance_snapshot() -> MockBalanceSnapshot:
    """提供範例餘額快照。"""
    return MockBalanceSnapshot(
        balance=10000,
        is_throttled=False,
        last_modified_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_history_entries() -> list[MockHistoryEntry]:
    """提供範例交易歷史。"""
    return [
        MockHistoryEntry(
            amount=100,
            is_credit=True,
            is_debit=False,
            initiator_id=111111111,
            target_id=222222222,
            reason="轉帳收入",
        ),
        MockHistoryEntry(
            amount=50,
            is_credit=False,
            is_debit=True,
            initiator_id=222222222,
            target_id=333333333,
            reason="轉帳支出",
        ),
        MockHistoryEntry(
            amount=200,
            is_credit=True,
            is_debit=False,
            initiator_id=444444444,
            target_id=None,
            reason="系統獎勵",
        ),
    ]


@pytest.fixture
def sample_currency_config() -> CurrencyConfigResult:
    """提供範例貨幣配置。"""
    return CurrencyConfigResult(
        currency_name="測試幣",
        currency_icon="💰",
    )


@pytest.fixture
def transfer_callback() -> AsyncMock:
    """提供模擬轉帳回調。"""
    callback = AsyncMock()
    callback.return_value = (True, "轉帳成功")
    return callback


@pytest.fixture
def refresh_callback(
    sample_balance_snapshot: MockBalanceSnapshot,
    sample_history_entries: list[MockHistoryEntry],
) -> AsyncMock:
    """提供模擬刷新回調。"""
    callback = AsyncMock()
    callback.return_value = (sample_balance_snapshot, sample_history_entries)
    return callback


class TestPersonalPanelView:
    """測試 PersonalPanelView 元件。"""

    async def test_init(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試初始化。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        assert view.author_id == 123456789
        assert view.guild_id == 111111111
        assert view.current_tab == "home"
        assert view.balance_snapshot == sample_balance_snapshot
        assert view.history_entries == sample_history_entries

    async def test_create_home_embed(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試首頁嵌入訊息創建。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        embed = view.create_home_embed()

        assert embed.title == "👤 個人面板"
        assert embed.color is not None
        # Check balance field
        fields = {f.name: f.value for f in embed.fields}
        assert "💰 目前餘額" in fields
        balance_field = fields["💰 目前餘額"]
        assert balance_field is not None and "10,000" in balance_field

    async def test_create_home_embed_with_throttle(
        self,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試冷卻中狀態的首頁嵌入訊息。"""
        throttled_snapshot = MockBalanceSnapshot(
            balance=5000,
            is_throttled=True,
            throttled_until=datetime.now(timezone.utc),
        )

        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=throttled_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        embed = view.create_home_embed()

        fields = {f.name: f.value for f in embed.fields}
        assert "⏳ 轉帳冷卻中" in fields

    async def test_create_property_embed_empty(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試空交易歷史的財產頁面。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=[],
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        embed = view.create_property_embed([], 1, 1)

        assert embed.title == "📊 財產 - 交易歷史"
        fields = {f.name: f.value for f in embed.fields}
        assert "📭 無交易記錄" in fields

    async def test_create_property_embed_with_entries(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試有交易歷史的財產頁面。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        embed = view.create_property_embed(sample_history_entries, 1, 1)

        assert embed.title == "📊 財產 - 交易歷史"
        assert any("交易記錄" in (f.name or "") for f in embed.fields)

    async def test_create_transfer_embed(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試轉帳頁面嵌入訊息。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        embed = view.create_transfer_embed()

        assert embed.title == "💸 轉帳"
        fields = {f.name: f.value for f in embed.fields}
        assert "💰 可用餘額" in fields
        assert "📋 操作說明" in fields

    async def test_get_currency_display(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試貨幣顯示字串。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        currency_display = view._get_currency_display()  # pyright: ignore[reportPrivateUsage]

        assert "測試幣" in currency_display
        assert "💰" in currency_display

    async def test_get_currency_display_no_icon(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試無圖示的貨幣顯示。"""
        config_no_icon = CurrencyConfigResult(
            currency_name="金幣",
            currency_icon="",
        )

        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=config_no_icon,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        currency_display = view._get_currency_display()  # pyright: ignore[reportPrivateUsage]

        assert currency_display == "金幣"

    async def test_derive_department_account_id(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試部門帳戶 ID 計算。"""
        from src.bot.services.department_registry import Department

        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        dept = Department(
            id="test_dept",
            name="測試部門",
            code=5,
        )

        account_id = view._derive_department_account_id(
            111111111, dept
        )  # pyright: ignore[reportPrivateUsage]

        # Should be 9_500_000_000_000_000 + guild_id + dept_code
        expected = 9_500_000_000_000_000 + 111111111 + 5
        assert account_id == expected

    async def test_resolve_department_account_id_uses_service(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """當提供 StateCouncilService 時應優先使用其帳戶 ID。"""
        mock_service = SimpleNamespace(
            get_department_account_id=AsyncMock(return_value=42_000_000_000_000_001)
        )

        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
            state_council_service=mock_service,  # type: ignore[arg-type]
        )

        dept = Department(id="finance", name="財政部", code=2)

        account_id = (
            await view._resolve_department_account_id(  # pyright: ignore[reportPrivateUsage]
                111111111,
                dept,
            )
        )

        assert account_id == 42_000_000_000_000_001
        mock_service.get_department_account_id.assert_awaited_once_with(  # type: ignore[attr-defined]
            guild_id=111111111,
            department="財政部",
        )

    async def test_resolve_department_account_id_fallback_on_error(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """當服務丟出錯誤時應回退至推導算法。"""
        mock_service = SimpleNamespace(
            get_department_account_id=AsyncMock(
                side_effect=StateCouncilNotConfiguredError("not configured")
            )
        )

        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
            state_council_service=mock_service,  # type: ignore[arg-type]
        )

        dept = Department(id="finance", name="財政部", code=2)

        account_id = (
            await view._resolve_department_account_id(  # pyright: ignore[reportPrivateUsage]
                111111111,
                dept,
            )
        )

        expected = 9_500_000_000_000_000 + 111111111 + dept.code
        assert account_id == expected

    async def test_derive_institution_account_id_permanent_council(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試常任理事會帳戶 ID 計算。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        account_id = view._derive_institution_account_id(
            111111111, "permanent_council"
        )  # pyright: ignore[reportPrivateUsage]

        # Should be 9_000_000_000_000_000 + guild_id (council dedicated range)
        expected = 9_000_000_000_000_000 + 111111111
        assert account_id == expected

    async def test_derive_institution_account_id_supreme_assembly(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試最高人民會議帳戶 ID 計算。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        account_id = view._derive_institution_account_id(
            111111111, "supreme_assembly"
        )  # pyright: ignore[reportPrivateUsage]

        # Should be 9_500_000_000_000_000 + guild_id + code(200)
        expected = 9_500_000_000_000_000 + 111111111 + 200
        assert account_id == expected

    async def test_derive_institution_account_id_state_council(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試國務院主帳戶 ID 計算。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        account_id = view._derive_institution_account_id(
            111111111, "state_council"
        )  # pyright: ignore[reportPrivateUsage]

        # State council transfers route to finance dept (dept_code=2)
        # Formula: 9_500_000_000_000_000 + guild_id + finance_dept_code
        expected = 9_500_000_000_000_000 + 111111111 + 2
        assert account_id == expected

    async def test_derive_institution_account_id_invalid(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試無效機構 ID 返回 None。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        account_id = view._derive_institution_account_id(
            111111111, "invalid_institution"
        )  # pyright: ignore[reportPrivateUsage]

        assert account_id is None

    async def test_view_has_tab_buttons(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試視圖包含分頁按鈕。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        # Check that view has items
        assert len(view.children) > 0

        # Find buttons by custom_id
        button_ids = [
            getattr(item, "custom_id", None) for item in view.children if hasattr(item, "custom_id")
        ]
        assert "personal_panel_home" in button_ids
        assert "personal_panel_property" in button_ids
        assert "personal_panel_transfer" in button_ids
        assert "personal_panel_refresh" in button_ids


class TestTransferModal:
    """測試 TransferModal 元件。"""

    async def test_init(self) -> None:
        """測試初始化。"""

        async def mock_submit(
            interaction: discord.Interaction, amount: int, reason: str | None
        ) -> None:
            pass

        modal = TransferModal(
            target_name="測試使用者",
            currency_display="測試幣 💰",
            available_balance=10000,
            on_submit=mock_submit,
        )

        assert modal.title == "轉帳給 測試使用者"
        placeholder = modal.amount_input.placeholder
        assert placeholder is not None and "10,000" in placeholder

    async def test_modal_fields(self) -> None:
        """測試 Modal 包含必要欄位。"""

        async def mock_submit(
            interaction: discord.Interaction, amount: int, reason: str | None
        ) -> None:
            pass

        modal = TransferModal(
            target_name="測試使用者",
            currency_display="測試幣 💰",
            available_balance=5000,
            on_submit=mock_submit,
        )

        # Check amount input field
        assert modal.amount_input.label == "轉帳金額"
        assert modal.amount_input.required is True

        # Check reason input field
        assert modal.reason_input.label == "備註（選填）"
        assert modal.reason_input.required is False


class TestPersonalPanelViewCallbacks:
    """測試 PersonalPanelView 回調函數。"""

    async def test_check_author_reject_non_owner(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試非擁有者操作被拒絕。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        # Create mock interaction with different user
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 999999999  # Different from author_id
        mock_interaction.response.send_message = AsyncMock()

        result = await view._check_author(mock_interaction)  # pyright: ignore[reportPrivateUsage]

        assert result is False

    async def test_check_author_accept_owner(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
    ) -> None:
        """測試擁有者操作被接受。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        # Create mock interaction with same user as author
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456789  # Same as author_id

        result = await view._check_author(mock_interaction)  # pyright: ignore[reportPrivateUsage]

        assert result is True

    async def test_on_user_select_handles_dict_values(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """確保從 interaction.data 字典讀取值時可以正常處理。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456789
        mock_interaction.guild = None
        mock_interaction.data = {"values": ["987654321"]}

        mock_send_modal = AsyncMock()
        monkeypatch.setattr(
            "src.bot.ui.personal_panel_paginator.send_modal_compat",
            mock_send_modal,
        )

        await view._on_user_select(mock_interaction)  # pyright: ignore[reportPrivateUsage]

        assert view._pending_transfer_target_id == 987654321  # pyright: ignore[reportPrivateUsage]
        assert (
            view._pending_transfer_target_name == "<@987654321>"
        )  # pyright: ignore[reportPrivateUsage]
        mock_send_modal.assert_awaited_once()

    async def test_on_govt_select_handles_department(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """確保政府機構選擇器讀取部門型資料時可以成功開啟 Modal。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        registry = get_registry()
        dept = registry.get_by_id("finance")
        assert dept is not None

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456789
        mock_interaction.guild = None
        mock_interaction.data = {"values": [f"department:{dept.id}"]}

        mock_send_modal = AsyncMock()
        monkeypatch.setattr(
            "src.bot.ui.personal_panel_paginator.send_modal_compat",
            mock_send_modal,
        )

        await view._on_govt_select(mock_interaction)  # pyright: ignore[reportPrivateUsage]

        expected_target_id = 9_500_000_000_000_000 + view.guild_id + dept.code
        assert (
            view._pending_transfer_target_id == expected_target_id
        )  # pyright: ignore[reportPrivateUsage]
        expected_name = f"{dept.emoji} {dept.name}" if dept.emoji else dept.name
        assert (
            view._pending_transfer_target_name == expected_name
        )  # pyright: ignore[reportPrivateUsage]
        mock_send_modal.assert_awaited_once()

    async def test_on_govt_select_handles_institution(
        self,
        sample_balance_snapshot: MockBalanceSnapshot,
        sample_history_entries: list[MockHistoryEntry],
        sample_currency_config: CurrencyConfigResult,
        transfer_callback: AsyncMock,
        refresh_callback: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """確保政府機構選擇器讀取機構型資料時可以成功開啟 Modal。"""
        view = PersonalPanelView(
            author_id=123456789,
            guild_id=111111111,
            balance_snapshot=sample_balance_snapshot,  # type: ignore[arg-type]
            history_entries=sample_history_entries,  # type: ignore[arg-type]
            currency_config=sample_currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
        )

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123456789
        mock_interaction.guild = None
        mock_interaction.data = {"values": ["institution:permanent_council"]}

        mock_send_modal = AsyncMock()
        monkeypatch.setattr(
            "src.bot.ui.personal_panel_paginator.send_modal_compat",
            mock_send_modal,
        )

        await view._on_govt_select(mock_interaction)  # pyright: ignore[reportPrivateUsage]

        expected_target_id = 9_000_000_000_000_000 + view.guild_id
        assert (
            view._pending_transfer_target_id == expected_target_id
        )  # pyright: ignore[reportPrivateUsage]
        mock_send_modal.assert_awaited_once()
