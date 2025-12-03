"""測試公司管理指令模組 (company.py)。

涵蓋範圍：
- 面板開啟/空清單/有清單顯示
- 成立公司與轉帳流程的驗證與權限訊息
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import discord
import pytest

from src.bot.commands.company import (
    CompanyNameModal,
    CompanyPanelView,
    CompanyTransferModal,
    _format_currency_display,
    build_company_group,
    get_help_data,
)
from src.bot.services.company_service import (
    CompanyLicenseInvalidError,
    CompanyService,
    InvalidCompanyNameError,
    LicenseAlreadyUsedError,
    NoAvailableLicenseError,
)
from src.bot.services.currency_config_service import CurrencyConfigResult, CurrencyConfigService
from src.infra.result import Err, Ok

# --- Mock Objects ---


class MockCompany:
    """模擬公司對象。"""

    def __init__(
        self,
        id: int,
        name: str,
        account_id: int,
        license_type: str | None = "商業許可",
        license_status: str = "active",
        created_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.account_id = account_id
        self.license_type = license_type
        self.license_status = license_status
        self.created_at = created_at or datetime.now(timezone.utc)


class MockLicense:
    """模擬許可證對象。"""

    def __init__(
        self,
        license_id: UUID,
        license_type: str,
        expires_at: datetime,
    ) -> None:
        self.license_id = license_id
        self.license_type = license_type
        self.expires_at = expires_at


@pytest.fixture
def mock_currency_config() -> MagicMock:
    """創建假貨幣配置。"""
    config = MagicMock(spec=CurrencyConfigResult)
    config.currency_name = "金幣"
    config.currency_icon = "💰"
    config.decimal_places = 0
    return config


@pytest.fixture
def mock_company_service() -> MagicMock:
    """創建假 CompanyService。"""
    service = MagicMock(spec=CompanyService)
    service.list_user_companies = AsyncMock(return_value=Ok([]))
    service.get_available_licenses = AsyncMock(return_value=Ok([]))
    service.create_company = AsyncMock()
    service.get_company_balance = AsyncMock(return_value=Ok(10000))
    service.validate_company_operation = AsyncMock(return_value=Ok(True))
    return service


@pytest.fixture
def mock_currency_service() -> MagicMock:
    """創建假 CurrencyConfigService。"""
    service = MagicMock(spec=CurrencyConfigService)
    config = MagicMock(spec=CurrencyConfigResult)
    config.currency_name = "金幣"
    config.currency_icon = "💰"
    config.decimal_places = 0
    service.get_currency_config = AsyncMock(return_value=config)
    return service


@pytest.fixture
def fake_guild() -> MagicMock:
    """創建假 Discord Guild。"""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 12345
    guild.name = "Test Guild"
    return guild


@pytest.fixture
def fake_interaction(fake_guild: MagicMock) -> MagicMock:
    """創建假 Discord Interaction。"""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = fake_guild.id
    interaction.guild = fake_guild
    interaction.user = MagicMock()
    interaction.user.id = 67890
    interaction.user.display_name = "TestUser"
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.original_response = AsyncMock()
    return interaction


# --- Test Helper Functions ---


class TestFormatCurrencyDisplay:
    """測試 _format_currency_display 函數。"""

    def test_with_name_and_icon(self, mock_currency_config: MagicMock) -> None:
        """測試有名稱和圖標的貨幣顯示。"""
        result = _format_currency_display(mock_currency_config, 5000)
        assert result == "5,000 💰 金幣"

    def test_with_name_only(self, mock_currency_config: MagicMock) -> None:
        """測試只有名稱的貨幣顯示。"""
        mock_currency_config.currency_icon = None
        result = _format_currency_display(mock_currency_config, 3000)
        assert result == "3,000 金幣"

    def test_with_icon_only(self, mock_currency_config: MagicMock) -> None:
        """測試只有圖標的貨幣顯示。"""
        mock_currency_config.currency_name = None
        result = _format_currency_display(mock_currency_config, 2000)
        assert result == "2,000 💰"

    def test_zero_amount(self, mock_currency_config: MagicMock) -> None:
        """測試零金額。"""
        result = _format_currency_display(mock_currency_config, 0)
        assert result == "0 💰 金幣"


class TestGetHelpData:
    """測試 get_help_data 函數。"""

    def test_returns_dict(self) -> None:
        """測試返回字典。"""
        help_data = get_help_data()
        assert isinstance(help_data, dict)
        assert "company" in help_data
        assert "company panel" in help_data

    def test_help_data_structure(self) -> None:
        """測試幫助數據結構。"""
        help_data = get_help_data()
        company_help = help_data["company"]

        assert company_help["name"] == "company"
        assert company_help["description"] == "公司管理指令群組"
        assert company_help["category"] == "economy"

    def test_panel_help_structure(self) -> None:
        """測試 panel 指令的幫助數據結構。"""
        help_data = get_help_data()
        panel_help = help_data["company panel"]

        assert panel_help["name"] == "company panel"
        assert "開啟公司面板" in panel_help["description"]


class TestBuildCompanyGroup:
    """測試 build_company_group 函數。"""

    def test_returns_group(
        self, mock_company_service: MagicMock, mock_currency_service: MagicMock
    ) -> None:
        """測試返回群組。"""
        group = build_company_group(mock_company_service, mock_currency_service)
        assert isinstance(group, discord.app_commands.Group)
        assert group.name == "company"
        assert group.description == "公司管理指令"

    def test_group_has_panel_command(
        self, mock_company_service: MagicMock, mock_currency_service: MagicMock
    ) -> None:
        """測試群組有 panel 指令。"""
        group = build_company_group(mock_company_service, mock_currency_service)
        command_names = [cmd.name for cmd in group.commands]
        assert "panel" in command_names


# --- Test CompanyPanelView ---


class TestCompanyPanelViewInit:
    """測試 CompanyPanelView 初始化。"""

    @pytest.mark.asyncio
    async def test_init_basic(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試基本初始化。"""
        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )

        assert view.guild_id == 12345
        assert view.author_id == 67890
        assert view.current_page == "home"
        assert view.current_company is None


class TestCompanyPanelViewHomeEmbed:
    """測試 CompanyPanelView 首頁 Embed。"""

    @pytest.mark.asyncio
    async def test_build_home_embed_empty_companies(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試空公司列表的首頁 Embed。"""
        mock_company_service.list_user_companies = AsyncMock(return_value=Ok([]))

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )

        embed = await view.build_home_embed()

        assert embed.title == "🏢 公司面板"
        assert "您目前沒有任何公司" in embed.description
        assert len(embed.fields) == 0

    @pytest.mark.asyncio
    async def test_build_home_embed_with_companies(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試有公司列表的首頁 Embed。"""
        companies = [
            MockCompany(id=1, name="測試公司一", account_id=111),
            MockCompany(id=2, name="測試公司二", account_id=222, license_status="expired"),
        ]
        mock_company_service.list_user_companies = AsyncMock(return_value=Ok(companies))
        mock_company_service.get_company_balance = AsyncMock(return_value=Ok(5000))

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )

        embed = await view.build_home_embed()

        assert embed.title == "🏢 公司面板"
        assert "以下是您擁有的公司列表" in embed.description
        assert len(embed.fields) == 2
        assert "測試公司一" in embed.fields[0].name
        assert "測試公司二" in embed.fields[1].name

    @pytest.mark.asyncio
    async def test_build_home_embed_error_fetching_companies(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試取得公司列表失敗。"""
        mock_company_service.list_user_companies = AsyncMock(
            return_value=Err(Exception("Database error"))
        )

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )

        embed = await view.build_home_embed()

        # 應該顯示空列表
        assert "您目前沒有任何公司" in embed.description


class TestCompanyPanelViewDetailEmbed:
    """測試 CompanyPanelView 詳情頁 Embed。"""

    @pytest.mark.asyncio
    async def test_build_detail_embed_no_company(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試無選中公司時返回首頁。"""
        mock_company_service.list_user_companies = AsyncMock(return_value=Ok([]))

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.current_company = None

        embed = await view.build_detail_embed()

        # 應該返回首頁
        assert embed.title == "🏢 公司面板"

    @pytest.mark.asyncio
    async def test_build_detail_embed_with_company(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試有選中公司時的詳情頁。"""
        company = MockCompany(id=1, name="測試公司", account_id=111)
        mock_company_service.get_company_balance = AsyncMock(return_value=Ok(25000))

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.current_company = company

        embed = await view.build_detail_embed()

        assert embed.title == "🏢 測試公司"
        assert len(embed.fields) >= 2
        # 檢查公司資訊和餘額
        field_names = [f.name for f in embed.fields]
        assert "📋 公司資訊" in field_names
        assert "💰 帳戶餘額" in field_names


class TestCompanyPanelViewPermissions:
    """測試 CompanyPanelView 權限檢查。"""

    @pytest.mark.asyncio
    async def test_on_create_company_author_only(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試只有作者可以創建公司。"""
        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )

        mock_interaction = MagicMock()
        mock_interaction.user.id = 99999  # 非作者

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await view._on_create_company(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "僅限面板開啟者操作" in kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_on_transfer_author_only(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試只有作者可以轉帳。"""
        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )

        mock_interaction = MagicMock()
        mock_interaction.user.id = 99999  # 非作者

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await view._on_transfer(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "僅限面板開啟者操作" in kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_on_back_author_only(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試只有作者可以返回。"""
        mock_company_service.list_user_companies = AsyncMock(return_value=Ok([]))

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )

        mock_interaction = MagicMock()
        mock_interaction.user.id = 99999  # 非作者

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await view._on_back(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "僅限面板開啟者操作" in kwargs.get("content", "")


class TestCompanyPanelViewCreateCompany:
    """測試公司創建流程。"""

    @pytest.mark.asyncio
    async def test_on_create_company_no_licenses(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試無可用許可證時的提示。"""
        mock_company_service.get_available_licenses = AsyncMock(return_value=Ok([]))

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )

        mock_interaction = MagicMock()
        mock_interaction.user.id = 67890  # 作者

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await view._on_create_company(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "沒有可用的商業許可" in kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_on_create_company_get_licenses_error(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試取得許可證列表失敗。"""
        mock_company_service.get_available_licenses = AsyncMock(
            return_value=Err(Exception("Database error"))
        )

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )

        mock_interaction = MagicMock()
        mock_interaction.user.id = 67890

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await view._on_create_company(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "無法取得許可證列表" in kwargs.get("content", "")


class TestCompanyPanelViewTransfer:
    """測試公司轉帳流程。"""

    @pytest.mark.asyncio
    async def test_on_transfer_no_company_selected(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試未選擇公司時的提示。"""
        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.current_company = None

        mock_interaction = MagicMock()
        mock_interaction.user.id = 67890

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await view._on_transfer(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "請先選擇一家公司" in kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_on_transfer_license_invalid(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試許可證失效時的提示。"""
        company = MockCompany(id=1, name="測試公司", account_id=111)
        mock_company_service.validate_company_operation = AsyncMock(
            return_value=Err(CompanyLicenseInvalidError("License expired"))
        )

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.current_company = company

        mock_interaction = MagicMock()
        mock_interaction.user.id = 67890

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await view._on_transfer(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "商業許可已失效" in kwargs.get("content", "")


class TestCompanyNameModal:
    """測試公司名稱模態框。"""

    @pytest.mark.asyncio
    async def test_on_submit_no_pending_license(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試無待定許可證時的提示。"""
        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.pending_license_id = None

        modal = CompanyNameModal(view)
        modal.name_input._value = "新公司"

        mock_interaction = MagicMock()
        mock_interaction.user.id = 67890

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await modal.on_submit(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "請重新選擇許可證" in kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_on_submit_create_success(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試成功創建公司。"""
        new_company = MockCompany(id=99, name="新公司", account_id=999)
        mock_company_service.create_company = AsyncMock(return_value=Ok(new_company))

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.pending_license_id = UUID("12345678-1234-5678-1234-567812345678")

        modal = CompanyNameModal(view)
        modal.name_input._value = "新公司"

        mock_interaction = MagicMock()
        mock_interaction.user.id = 67890

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await modal.on_submit(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "公司成立成功" in kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_on_submit_no_available_license_error(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試無可用許可證錯誤。"""
        mock_company_service.create_company = AsyncMock(
            return_value=Err(NoAvailableLicenseError("No license"))
        )

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.pending_license_id = UUID("12345678-1234-5678-1234-567812345678")

        modal = CompanyNameModal(view)
        modal.name_input._value = "新公司"

        mock_interaction = MagicMock()

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await modal.on_submit(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "沒有可用的商業許可" in kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_on_submit_license_already_used_error(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試許可證已使用錯誤。"""
        mock_company_service.create_company = AsyncMock(
            return_value=Err(LicenseAlreadyUsedError("License used"))
        )

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.pending_license_id = UUID("12345678-1234-5678-1234-567812345678")

        modal = CompanyNameModal(view)
        modal.name_input._value = "新公司"

        mock_interaction = MagicMock()

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await modal.on_submit(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "已關聯一家公司" in kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_on_submit_invalid_name_error(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試無效公司名稱錯誤。"""
        mock_company_service.create_company = AsyncMock(
            return_value=Err(InvalidCompanyNameError("Invalid name"))
        )

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.pending_license_id = UUID("12345678-1234-5678-1234-567812345678")

        modal = CompanyNameModal(view)
        modal.name_input._value = ""

        mock_interaction = MagicMock()

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await modal.on_submit(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "1-100 個字元" in kwargs.get("content", "")


class TestCompanyTransferModal:
    """測試公司轉帳模態框。"""

    @pytest.mark.asyncio
    async def test_on_submit_no_company_selected(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試無選中公司時的提示。"""
        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.current_company = None

        modal = CompanyTransferModal(
            view,
            target_id=99999,
            target_name="接收者",
            target_type="user",
        )
        modal.amount_input._value = "1000"

        mock_interaction = MagicMock()

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await modal.on_submit(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "請先選擇一家公司" in kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_on_submit_invalid_amount(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試無效金額。"""
        company = MockCompany(id=1, name="測試公司", account_id=111)

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.current_company = company

        modal = CompanyTransferModal(
            view,
            target_id=99999,
            target_name="接收者",
            target_type="user",
        )
        modal.amount_input._value = "abc"

        mock_interaction = MagicMock()

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await modal.on_submit(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "金額必須為整數" in kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_on_submit_negative_amount(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試負金額。"""
        company = MockCompany(id=1, name="測試公司", account_id=111)

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.current_company = company

        modal = CompanyTransferModal(
            view,
            target_id=99999,
            target_name="接收者",
            target_type="user",
        )
        modal.amount_input._value = "-100"

        mock_interaction = MagicMock()

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await modal.on_submit(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "轉帳金額必須為正整數" in kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_on_submit_insufficient_balance(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試餘額不足。"""
        company = MockCompany(id=1, name="測試公司", account_id=111)
        mock_company_service.get_company_balance = AsyncMock(return_value=Ok(500))

        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.current_company = company

        modal = CompanyTransferModal(
            view,
            target_id=99999,
            target_name="接收者",
            target_type="user",
        )
        modal.amount_input._value = "1000"

        mock_interaction = MagicMock()

        with patch(
            "src.bot.commands.company.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await modal.on_submit(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "餘額不足" in kwargs.get("content", "")


class TestCompanyViewItems:
    """測試 View 項目更新。"""

    @pytest.mark.asyncio
    async def test_update_view_items_home(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試首頁項目更新。"""
        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.current_page = "home"
        view.companies = []

        view.update_view_items()

        # 應該有創建公司按鈕
        has_create_btn = any(
            hasattr(item, "custom_id") and item.custom_id == "create_company"
            for item in view.children
        )
        assert has_create_btn

    @pytest.mark.asyncio
    async def test_update_view_items_detail(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試詳情頁項目更新。"""
        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.current_page = "detail"

        view.update_view_items()

        # 應該有轉帳和返回按鈕
        custom_ids = [item.custom_id for item in view.children if hasattr(item, "custom_id")]
        assert "transfer" in custom_ids
        assert "back" in custom_ids

    @pytest.mark.asyncio
    async def test_update_view_items_transfer(
        self,
        mock_company_service: MagicMock,
        mock_currency_service: MagicMock,
        mock_currency_config: MagicMock,
    ) -> None:
        """測試轉帳頁項目更新。"""
        view = CompanyPanelView(
            company_service=mock_company_service,
            currency_service=mock_currency_service,
            guild_id=12345,
            author_id=67890,
            currency_config=mock_currency_config,
        )
        view.current_page = "transfer"

        view.update_view_items()

        # 應該有轉帳給用戶、轉帳給部門和返回按鈕
        custom_ids = [item.custom_id for item in view.children if hasattr(item, "custom_id")]
        assert "transfer_user" in custom_ids
        assert "transfer_gov" in custom_ids
        assert "back_detail" in custom_ids


if __name__ == "__main__":
    pytest.main([__file__])
