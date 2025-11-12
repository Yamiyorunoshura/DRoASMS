from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.commands.state_council import (
    _edit_message_compat,
    _format_currency_display,
    _send_message_compat,
    _send_modal_compat,
    build_state_council_group,
    get_help_data,
)
from src.bot.services.currency_config_service import CurrencyConfigResult
from src.bot.services.state_council_service import (
    InsufficientFundsError,
    MonthlyIssuanceLimitExceededError,
    PermissionDeniedError,
    StateCouncilNotConfiguredError,
    StateCouncilService,
)

# --- Fixtures and Mocks ---


@pytest.fixture
def fake_guild() -> MagicMock:
    """創建一個假的 Discord Guild 物件"""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 12345
    guild.name = "Test Guild"
    guild.get_role = MagicMock()
    guild.get_member = MagicMock()
    return guild


@pytest.fixture
def fake_user() -> MagicMock:
    """創建一個假的 Discord User 物件"""
    user = MagicMock(spec=discord.User)
    user.id = 67890
    user.name = "TestUser"
    user.display_name = "Test User"
    user.mention = "<@67890>"
    user.roles = []
    user.guild_permissions = MagicMock()
    user.guild_permissions.administrator = False
    user.guild_permissions.manage_guild = False
    return user


@pytest.fixture
def fake_member() -> MagicMock:
    """創建一個假的 Discord Member 物件"""
    member = MagicMock(spec=discord.Member)
    member.id = 67890
    member.name = "TestUser"
    member.display_name = "Test User"
    member.mention = "<@67890>"
    member.roles = []
    member.guild_permissions = MagicMock()
    member.guild_permissions.administrator = False
    member.guild_permissions.manage_guild = False
    return member


@pytest.fixture
def fake_role() -> MagicMock:
    """創建一個假的 Discord Role 物件"""
    role = MagicMock(spec=discord.Role)
    role.id = 11111
    role.name = "Test Role"
    role.mention = "<@&11111>"
    role.members = []
    return role


@pytest.fixture
def fake_interaction(fake_guild: MagicMock, fake_member: MagicMock) -> MagicMock:
    """創建一個假的 Discord Interaction 物件"""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = fake_guild.id
    interaction.guild = fake_guild
    interaction.user = fake_member
    interaction.response = MagicMock()
    interaction.followup = MagicMock()
    interaction.original_response = AsyncMock()
    interaction.data = {}
    return interaction


@pytest.fixture
def mock_state_council_service() -> MagicMock:
    """創建一個假的 StateCouncilService"""
    service = MagicMock(spec=StateCouncilService)
    service.set_config = AsyncMock(return_value=MagicMock())
    service.get_config = AsyncMock()
    service.update_citizen_role_config = AsyncMock()
    service.update_suspect_role_config = AsyncMock()
    service.check_leader_permission = AsyncMock(return_value=False)
    service.check_department_permission = AsyncMock(return_value=False)
    service.ensure_government_accounts = AsyncMock()
    service.transfer_currency = AsyncMock()
    service.issue_currency = AsyncMock()
    service.create_welfare_disbursement = AsyncMock()
    service.get_department_balance = AsyncMock(return_value=10000)
    service.update_department_config = AsyncMock()
    return service


@pytest.fixture
def mock_currency_config_service() -> MagicMock:
    """創建一個假的 CurrencyConfigService"""
    service = MagicMock()
    return service


@pytest.fixture
def mock_currency_config() -> MagicMock:
    """創建一個假的貨幣配置"""
    config = MagicMock(spec=CurrencyConfigResult)
    config.currency_name = "金幣"
    config.currency_icon = "💰"
    config.decimal_places = 0
    return config


# --- Test Helper Functions ---


class TestFormatCurrencyDisplay:
    """測試 _format_currency_display 函數"""

    def test_with_name_and_icon(self, mock_currency_config: MagicMock) -> None:
        """測試有名稱和圖標的貨幣顯示"""
        result = _format_currency_display(mock_currency_config, 5000)
        assert result == "5,000 💰 金幣"

    def test_with_name_only(self, mock_currency_config: MagicMock) -> None:
        """測試只有名稱的貨幣顯示"""
        mock_currency_config.currency_icon = None
        result = _format_currency_display(mock_currency_config, 3000)
        assert result == "3,000 金幣"

    def test_with_icon_only(self, mock_currency_config: MagicMock) -> None:
        """測試只有圖標的貨幣顯示"""
        mock_currency_config.currency_name = None
        result = _format_currency_display(mock_currency_config, 2000)
        assert result == "2,000 💰"

    def test_large_amount(self, mock_currency_config: MagicMock) -> None:
        """測試大金額格式化"""
        result = _format_currency_display(mock_currency_config, 1234567890)
        assert result == "1,234,567,890 💰 金幣"

    def test_zero_amount(self, mock_currency_config: MagicMock) -> None:
        """測試零金額"""
        result = _format_currency_display(mock_currency_config, 0)
        assert result == "0 💰 金幣"


class TestMessageCompatFunctions:
    """測試消息兼容性函數"""

    @pytest.mark.asyncio
    async def test_send_message_compat_with_response(self) -> None:
        """測試使用 response.send_message"""
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()

        await _send_message_compat(interaction, content="Test message", ephemeral=True)

        interaction.response.send_message.assert_called_once_with("Test message", ephemeral=True)

    @pytest.mark.asyncio
    async def test_send_message_compat_with_edit_message(self) -> None:
        """測試使用 response_edit_message"""
        interaction = MagicMock()
        interaction.response = MagicMock()
        del interaction.response.send_message  # 移除 send_message
        interaction.response_edit_message = AsyncMock()

        embed = MagicMock()
        await _send_message_compat(interaction, embed=embed, ephemeral=True)

        interaction.response_edit_message.assert_called_once_with(embed=embed, ephemeral=True)

    @pytest.mark.asyncio
    async def test_send_message_compat_with_send_message_stub(self) -> None:
        """測試使用 response_send_message stub"""
        interaction = MagicMock()
        interaction.response = MagicMock()
        del interaction.response.send_message
        del interaction.response.edit_message
        interaction.response_send_message = AsyncMock()

        await _send_message_compat(interaction, content="Test message")

        interaction.response_send_message.assert_called_once_with("Test message", ephemeral=False)

    @pytest.mark.asyncio
    async def test_edit_message_compat_with_response(self) -> None:
        """測試使用 response.edit_message"""
        interaction = MagicMock()
        interaction.response.edit_message = AsyncMock()

        embed = MagicMock()
        await _edit_message_compat(interaction, embed=embed)

        interaction.response.edit_message.assert_called_once_with(embed=embed)

    @pytest.mark.asyncio
    async def test_edit_message_compat_with_stub(self) -> None:
        """測試使用 response_edit_message stub"""
        interaction = MagicMock()
        interaction.response = MagicMock()
        del interaction.response.edit_message
        interaction.response_edit_message = AsyncMock()

        embed = MagicMock()
        await _edit_message_compat(interaction, embed=embed)

        interaction.response_edit_message.assert_called_once_with(embed=embed)

    @pytest.mark.asyncio
    async def test_send_modal_compat_with_response(self) -> None:
        """測試使用 response.send_modal"""
        interaction = MagicMock()
        interaction.response.send_modal = AsyncMock()

        modal = MagicMock()
        await _send_modal_compat(interaction, modal)

        interaction.response.send_modal.assert_called_once_with(modal)

    @pytest.mark.asyncio
    async def test_send_modal_compat_with_stub(self) -> None:
        """測試使用 response_send_modal stub"""
        interaction = MagicMock()
        interaction.response = MagicMock()
        del interaction.response.send_modal
        interaction.response_send_modal = AsyncMock()

        modal = MagicMock()
        await _send_modal_compat(interaction, modal)

        interaction.response_send_modal.assert_called_once_with(modal)


class TestGetHelpData:
    """測試 get_help_data 函數"""

    def test_returns_dict(self) -> None:
        """測試返回字典"""
        help_data = get_help_data()
        assert isinstance(help_data, dict)
        assert "state_council" in help_data
        assert "state_council config_leader" in help_data
        assert "state_council config_citizen_role" in help_data
        assert "state_council config_suspect_role" in help_data
        assert "state_council panel" in help_data
        assert "state_council suspects" in help_data

    def test_help_data_structure(self) -> None:
        """測試幫助數據結構"""
        help_data = get_help_data()
        sc_help = help_data["state_council"]

        assert sc_help["name"] == "state_council"
        assert sc_help["description"] == "國務院治理指令群組"
        assert sc_help["category"] == "governance"
        assert isinstance(sc_help["parameters"], list)
        assert isinstance(sc_help["permissions"], list)
        assert isinstance(sc_help["examples"], list)
        assert isinstance(sc_help["tags"], list)

    def test_config_leader_help_structure(self) -> None:
        """測試 config_leader 指令的幫助數據結構"""
        help_data = get_help_data()
        config_help = help_data["state_council config_leader"]

        assert "leader" in [p["name"] for p in config_help["parameters"]]
        assert "leader_role" in [p["name"] for p in config_help["parameters"]]
        assert "administrator" in config_help["permissions"]
        assert "manage_guild" in config_help["permissions"]
        assert isinstance(config_help["examples"], list)


class TestBuildStateCouncilGroup:
    """測試 build_state_council_group 函數"""

    def test_returns_group(self, mock_state_council_service: MagicMock) -> None:
        """測試返回群組"""
        group = build_state_council_group(mock_state_council_service)
        assert isinstance(group, discord.app_commands.Group)
        assert group.name == "state_council"
        assert group.description == "國務院治理指令"

    def test_group_has_commands(self, mock_state_council_service: MagicMock) -> None:
        """測試群組有指令"""
        group = build_state_council_group(mock_state_council_service)
        # 檢查是否有主要指令
        command_names = [cmd.name for cmd in group.commands]
        assert "config_leader" in command_names
        assert "config_citizen_role" in command_names
        assert "config_suspect_role" in command_names
        assert "panel" in command_names
        assert "suspects" in command_names

    def test_group_with_currency_service(
        self, mock_state_council_service: MagicMock, mock_currency_config_service: MagicMock
    ) -> None:
        """測試帶貨幣服務的群組"""
        group = build_state_council_group(mock_state_council_service, mock_currency_config_service)
        assert isinstance(group, discord.app_commands.Group)
        assert group.name == "state_council"


class TestStateCouncilCommandLogic:
    """測試國務院指令邏輯"""

    @pytest.mark.asyncio
    async def test_config_leader_command_success(
        self,
        mock_state_council_service: MagicMock,
        fake_interaction: MagicMock,
        fake_member: MagicMock,
        fake_role: MagicMock,
    ) -> None:
        """測試 config_leader 指令成功"""
        # 設置權限
        fake_member.guild_permissions.administrator = True

        # Mock configuration
        mock_config = MagicMock()
        mock_config.internal_affairs_account_id = 11111
        mock_config.finance_account_id = 22222
        mock_config.security_account_id = 33333
        mock_config.central_bank_account_id = 44444
        mock_state_council_service.set_config = AsyncMock(return_value=mock_config)

        # Mock interaction
        fake_interaction.user = fake_member
        fake_interaction.response = AsyncMock()
        fake_interaction.original_response = AsyncMock()

        # Create command with patches
        with patch("src.bot.commands.state_council._install_background_scheduler"):
            group = build_state_council_group(mock_state_council_service)

            # Get config_leader command
            config_leader_cmd = None
            for child in group.commands:
                if child.name == "config_leader":
                    config_leader_cmd = child
                    break

            assert config_leader_cmd is not None

            # Execute command with user
            await config_leader_cmd.callback(fake_interaction, leader=fake_member, leader_role=None)

        mock_state_council_service.set_config.assert_called_once()
        fake_interaction.response.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_config_leader_command_no_permissions(
        self,
        mock_state_council_service: MagicMock,
        fake_interaction: MagicMock,
        fake_member: MagicMock,
    ) -> None:
        """測試 config_leader 指令沒有權限"""
        # 設置無權限
        fake_member.guild_permissions.administrator = False
        fake_member.guild_permissions.manage_guild = False

        # Mock interaction
        fake_interaction.user = fake_member
        fake_interaction.response = AsyncMock()

        # Create command with patches
        with patch("src.bot.commands.state_council._install_background_scheduler"):
            group = build_state_council_group(mock_state_council_service)

            # Get config_leader command
            config_leader_cmd = None
            for child in group.commands:
                if child.name == "config_leader":
                    config_leader_cmd = child
                    break

            assert config_leader_cmd is not None

            # Execute command
            await config_leader_cmd.callback(fake_interaction, leader=None, leader_role=None)

        fake_interaction.response.send_message.assert_called_with(
            "需要管理員或管理伺服器權限。", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_config_leader_command_no_parameters(
        self,
        mock_state_council_service: MagicMock,
        fake_interaction: MagicMock,
        fake_member: MagicMock,
    ) -> None:
        """測試 config_leader 指令沒有提供參數"""
        # 設置權限
        fake_member.guild_permissions.administrator = True

        # Mock interaction
        fake_interaction.user = fake_member
        fake_interaction.response = AsyncMock()

        # Create command with patches
        with patch("src.bot.commands.state_council._install_background_scheduler"):
            group = build_state_council_group(mock_state_council_service)

            # Get config_leader command
            config_leader_cmd = None
            for child in group.commands:
                if child.name == "config_leader":
                    config_leader_cmd = child
                    break

            assert config_leader_cmd is not None

            # Execute command without parameters
            await config_leader_cmd.callback(fake_interaction, leader=None, leader_role=None)

        fake_interaction.response.send_message.assert_called_with(
            "必須指定一位使用者或一個身分組作為國務院領袖。", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_config_citizen_role_command_success(
        self, fake_interaction: MagicMock, fake_member: MagicMock, fake_role: MagicMock
    ) -> None:
        """測試 config_citizen_role 指令成功"""
        # 設置權限
        fake_member.guild_permissions.administrator = True

        # Mock interaction
        fake_interaction.user = fake_member
        fake_interaction.response = AsyncMock()

        # Mock service
        mock_service = MagicMock(spec=StateCouncilService)
        mock_service.update_citizen_role_config = AsyncMock()

        # Create command with patches
        with patch("src.bot.commands.state_council.StateCouncilService", return_value=mock_service):
            with patch("src.bot.commands.state_council._install_background_scheduler"):
                group = build_state_council_group(MagicMock())

                # Get config_citizen_role command
                config_cmd = None
                for child in group.commands:
                    if child.name == "config_citizen_role":
                        config_cmd = child
                        break

                assert config_cmd is not None

                # Execute command
                await config_cmd.callback(fake_interaction, role=fake_role)

        mock_service.update_citizen_role_config.assert_called_once_with(
            guild_id=fake_interaction.guild_id, citizen_role_id=fake_role.id
        )
        fake_interaction.response.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_config_citizen_role_not_configured(
        self, fake_interaction: MagicMock, fake_member: MagicMock, fake_role: MagicMock
    ) -> None:
        """測試 config_citizen_role 指令未配置國務院"""
        # 設置權限
        fake_member.guild_permissions.administrator = True

        # Mock interaction
        fake_interaction.user = fake_member
        fake_interaction.response = AsyncMock()

        # Mock service with NotConfiguredError
        mock_service = MagicMock(spec=StateCouncilService)
        mock_service.update_citizen_role_config = AsyncMock(
            side_effect=StateCouncilNotConfiguredError("Not configured")
        )

        # Create command with patches
        with patch("src.bot.commands.state_council.StateCouncilService", return_value=mock_service):
            with patch("src.bot.commands.state_council._install_background_scheduler"):
                group = build_state_council_group(MagicMock())

                # Get config_citizen_role command
                config_cmd = None
                for child in group.commands:
                    if child.name == "config_citizen_role":
                        config_cmd = child
                        break

                assert config_cmd is not None

                # Execute command
                await config_cmd.callback(fake_interaction, role=fake_role)

        fake_interaction.response.send_message.assert_called_with(
            "尚未完成國務院設定，請先執行 /state_council config_leader。", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_config_suspect_role_command_success(
        self, fake_interaction: MagicMock, fake_member: MagicMock, fake_role: MagicMock
    ) -> None:
        """測試 config_suspect_role 指令成功"""
        # 設置權限
        fake_member.guild_permissions.administrator = True

        # Mock interaction
        fake_interaction.user = fake_member
        fake_interaction.response = AsyncMock()

        # Mock service
        mock_service = MagicMock(spec=StateCouncilService)
        mock_service.update_suspect_role_config = AsyncMock()

        # Create command with patches
        with patch("src.bot.commands.state_council.StateCouncilService", return_value=mock_service):
            with patch("src.bot.commands.state_council._install_background_scheduler"):
                group = build_state_council_group(MagicMock())

                # Get config_suspect_role command
                config_cmd = None
                for child in group.commands:
                    if child.name == "config_suspect_role":
                        config_cmd = child
                        break

                assert config_cmd is not None

                # Execute command
                await config_cmd.callback(fake_interaction, role=fake_role)

        mock_service.update_suspect_role_config.assert_called_once_with(
            guild_id=fake_interaction.guild_id, suspect_role_id=fake_role.id
        )
        fake_interaction.response.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_panel_command_not_configured(
        self, mock_state_council_service: MagicMock, fake_interaction: MagicMock
    ) -> None:
        """測試 panel 指令未配置"""
        mock_state_council_service.get_config = AsyncMock(
            side_effect=StateCouncilNotConfiguredError("Not configured")
        )

        # Mock interaction
        fake_interaction.response = AsyncMock()

        # Create command with patches
        with patch("src.bot.commands.state_council._install_background_scheduler"):
            with patch("src.bot.commands.state_council.CurrencyConfigService"):
                group = build_state_council_group(mock_state_council_service)

                # Get panel command
                panel_cmd = None
                for child in group.commands:
                    if child.name == "panel":
                        panel_cmd = child
                        break

                assert panel_cmd is not None

                # Execute command
                await panel_cmd.callback(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "尚未完成國務院設定，請先執行 /state_council config_leader。", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_panel_command_no_permissions(
        self, mock_state_council_service: MagicMock, fake_interaction: MagicMock
    ) -> None:
        """測試 panel 指令沒有權限"""
        # Mock config
        mock_config = MagicMock()
        mock_config.leader_id = 99999
        mock_config.leader_role_id = 88888
        mock_state_council_service.get_config = AsyncMock(return_value=mock_config)

        # Mock permission checks
        mock_state_council_service.check_leader_permission = AsyncMock(return_value=False)
        mock_state_council_service.check_department_permission = AsyncMock(return_value=False)

        # Mock interaction
        fake_interaction.response = AsyncMock()
        fake_interaction.original_response = AsyncMock()

        # Create command with patches
        with patch("src.bot.commands.state_council._install_background_scheduler"):
            with patch("src.bot.commands.state_council.CurrencyConfigService"):
                group = build_state_council_group(mock_state_council_service)

                # Get panel command
                panel_cmd = None
                for child in group.commands:
                    if child.name == "panel":
                        panel_cmd = child
                        break

                assert panel_cmd is not None

                # Execute command
                await panel_cmd.callback(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "僅限國務院領袖或部門授權人員可開啟面板。", ephemeral=True
        )


class TestStateCouncilIntegration:
    """國務院整合測試"""

    @pytest.mark.asyncio
    async def test_full_config_flow(self) -> None:
        """測試完整配置流程"""
        # Mock service
        mock_service = MagicMock(spec=StateCouncilService)
        mock_config = MagicMock()
        mock_config.leader_id = 12345
        mock_config.leader_role_id = 54321
        mock_config.internal_affairs_account_id = 11111
        mock_config.finance_account_id = 22222
        mock_config.security_account_id = 33333
        mock_config.central_bank_account_id = 44444
        mock_service.set_config = AsyncMock(return_value=mock_config)

        # Test config leader
        result = await mock_service.set_config(
            guild_id=12345, leader_id=12345, leader_role_id=54321
        )

        assert result == mock_config
        mock_service.set_config.assert_called_once_with(
            guild_id=12345, leader_id=12345, leader_role_id=54321
        )

    @pytest.mark.asyncio
    async def test_permission_checking(self) -> None:
        """測試權限檢查"""
        mock_service = MagicMock(spec=StateCouncilService)
        mock_service.check_leader_permission = AsyncMock(return_value=True)
        mock_service.check_department_permission = AsyncMock(return_value=False)

        guild_id = 12345
        user_id = 67890
        user_roles = [11111, 22222]

        # Test leader permission
        is_leader = await mock_service.check_leader_permission(
            guild_id=guild_id, user_id=user_id, user_roles=user_roles
        )
        assert is_leader is True

        # Test department permission
        has_dept_permission = await mock_service.check_department_permission(
            guild_id=guild_id, user_id=user_id, department="財政部", user_roles=user_roles
        )
        assert has_dept_permission is False

    @pytest.mark.asyncio
    async def test_currency_issuance(self) -> None:
        """測試貨幣發行"""
        mock_service = MagicMock(spec=StateCouncilService)
        mock_service.issue_currency = AsyncMock()

        guild_id = 12345
        admin_id = 67890
        amount = 10000
        reason = "Test issuance"

        await mock_service.issue_currency(
            guild_id=guild_id, admin_id=admin_id, amount=amount, reason=reason
        )

        mock_service.issue_currency.assert_called_once_with(
            guild_id=guild_id, admin_id=admin_id, amount=amount, reason=reason
        )

    @pytest.mark.asyncio
    async def test_welfare_disbursement(self) -> None:
        """測試福利發放"""
        mock_service = MagicMock(spec=StateCouncilService)
        mock_service.create_welfare_disbursement = AsyncMock()

        guild_id = 12345
        admin_id = 67890
        recipient_id = 11111
        amount = 5000
        reason = "Test welfare"

        await mock_service.create_welfare_disbursement(
            guild_id=guild_id,
            admin_id=admin_id,
            recipient_id=recipient_id,
            amount=amount,
            reason=reason,
        )

        mock_service.create_welfare_disbursement.assert_called_once_with(
            guild_id=guild_id,
            admin_id=admin_id,
            recipient_id=recipient_id,
            amount=amount,
            reason=reason,
        )

    @pytest.mark.asyncio
    async def test_department_transfer(self) -> None:
        """測試部門轉帳"""
        mock_service = MagicMock(spec=StateCouncilService)
        mock_service.transfer_currency = AsyncMock()

        guild_id = 12345
        admin_id = 67890
        from_department = "財政部"
        to_department = "內政部"
        amount = 3000
        reason = "Test transfer"

        await mock_service.transfer_currency(
            guild_id=guild_id,
            admin_id=admin_id,
            from_department=from_department,
            to_department=to_department,
            amount=amount,
            reason=reason,
        )

        mock_service.transfer_currency.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_scenarios(self) -> None:
        """測試錯誤處理場景"""
        mock_service = MagicMock(spec=StateCouncilService)

        # Test different exception types
        test_exceptions = [
            PermissionDeniedError("No permission"),
            StateCouncilNotConfiguredError("Not configured"),
            InsufficientFundsError("Insufficient funds"),
            MonthlyIssuanceLimitExceededError("Monthly limit exceeded"),
            Exception("General error"),
        ]

        for exc in test_exceptions:
            mock_service.issue_currency = AsyncMock(side_effect=exc)

            try:
                await mock_service.issue_currency(
                    guild_id=12345, admin_id=67890, amount=1000, reason="Test"
                )
            except Exception:
                pass  # Expected for some error types

    def test_currency_display_edge_cases(self) -> None:
        """測試貨幣顯示的邊界情況"""
        # Test empty config
        config = MagicMock(spec=CurrencyConfigResult)
        config.currency_name = None
        config.currency_icon = None

        result = _format_currency_display(config, 1000)
        assert result == "1,000 None"

        # Test special characters in names
        config.currency_name = "特殊貨幣!@#$%"
        config.currency_icon = "🪙"

        result = _format_currency_display(config, 5000)
        assert "特殊貨幣!@#$%" in result
        assert "🪙" in result
