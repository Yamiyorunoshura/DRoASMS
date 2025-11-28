from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import discord
import pytest

from src.bot.commands.council import (
    CouncilPanelView,
    ExportModal,
    ProposalActionView,
    TransferProposalModal,
    _broadcast_result,
    _extract_select_values,
    _format_proposal_desc,
    _format_proposal_title,
    _handle_vote,
    _register_persistent_views,
    _safe_fetch_user,
    build_council_group,
    get_help_data,
    register,
)
from src.bot.services.council_service import (
    CouncilService,
    CouncilServiceResult,
    GovernanceNotConfiguredError,
    PermissionDeniedError,
)
from src.bot.services.permission_service import PermissionResult, PermissionService
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.supreme_assembly_service import SupremeAssemblyService
from src.infra.di.container import DependencyContainer
from src.infra.result import Ok

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
    role.name = "Council Role"
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
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send_message = AsyncMock()
    interaction.client = MagicMock()
    interaction.data = {}
    return interaction


@pytest.fixture
def mock_council_service() -> MagicMock:
    """創建一個假的 CouncilService"""
    service = MagicMock(spec=CouncilService)
    service.set_config = AsyncMock(return_value=MagicMock())
    service.get_config = AsyncMock()
    service.create_transfer_proposal = AsyncMock()
    service.vote = AsyncMock()
    service.cancel_proposal = AsyncMock()
    service.get_proposal = AsyncMock()
    service.list_active_proposals = AsyncMock(return_value=[])
    service.export_interval = AsyncMock(return_value=[])
    service.expire_due_proposals = AsyncMock(return_value=0)
    service.add_council_role = AsyncMock(return_value=True)
    service.remove_council_role = AsyncMock(return_value=True)
    service.get_council_role_ids = AsyncMock(return_value=[])
    service.check_council_permission = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_container(mock_council_service: MagicMock) -> MagicMock:
    """創建一個假的依賴注入容器"""
    container = MagicMock(spec=DependencyContainer)
    permission_service = MagicMock(spec=PermissionService)
    permission_service.check_council_permission.return_value = Ok(
        PermissionResult(allowed=True, permission_level="council_member")
    )
    result_service = MagicMock(spec=CouncilServiceResult)

    def _resolve(service_type: type[Any]) -> Any:
        if service_type is CouncilService:
            return mock_council_service
        if service_type is CouncilServiceResult:
            return result_service
        if service_type is PermissionService:
            return permission_service
        return MagicMock()

    container.resolve = MagicMock(side_effect=_resolve)
    return container


@pytest.fixture
def mock_command_tree() -> MagicMock:
    """創建一個假的 CommandTree"""
    tree = MagicMock(spec=discord.app_commands.CommandTree)
    tree.client = MagicMock()
    tree.add_command = MagicMock()
    return tree


# --- Test Helper Functions ---


class TestExtractSelectValues:
    """測試 _extract_select_values 函數"""

    def test_empty_data(self) -> None:
        """測試空數據"""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.data = {}
        assert _extract_select_values(interaction) == []

    def test_no_values_field(self) -> None:
        """測試沒有 values 欄位"""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.data = {"other": "data"}
        assert _extract_select_values(interaction) == []

    def test_values_not_list(self) -> None:
        """測試 values 不是列表"""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.data = {"values": "not_a_list"}
        assert _extract_select_values(interaction) == []

    def test_empty_list(self) -> None:
        """測試空列表"""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.data = {"values": []}
        assert _extract_select_values(interaction) == []

    def test_mixed_types(self) -> None:
        """測試混合類型列表"""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.data = {"values": ["string", 123, None, "another_string"]}
        assert _extract_select_values(interaction) == ["string", "another_string"]


class TestFormatProposalTitle:
    """測試 _format_proposal_title 函數"""

    def test_user_target(self) -> None:
        """測試使用者目標"""
        proposal = MagicMock()
        proposal.proposal_id = UUID("12345678-1234-5678-9abc-123456789012")
        proposal.target_id = 67890
        proposal.amount = 1000
        proposal.target_department_id = None

        result = _format_proposal_title(proposal)
        assert result == "#12345678 → <@67890> 1000"

    def test_department_target(self) -> None:
        """測試部門目標"""
        proposal = MagicMock()
        proposal.proposal_id = UUID("12345678-1234-5678-9abc-123456789012")
        proposal.target_id = 67890
        proposal.amount = 1000
        proposal.target_department_id = "DEPT_001"

        # Mock registry
        from src.bot.services.department_registry import get_registry

        registry = get_registry()
        registry.get_by_id = MagicMock(return_value=MagicMock(name="財政部"))

        result = _format_proposal_title(proposal)
        assert "財政部" in result


class TestFormatProposalDesc:
    """測試 _format_proposal_desc 函數"""

    def test_full_description(self) -> None:
        """測試完整描述"""
        proposal = MagicMock()
        proposal.deadline_at = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)
        proposal.description = "This is a test proposal for testing purposes"
        proposal.threshold_t = 5

        result = _format_proposal_desc(proposal)
        expected = "截止 2025-01-15 10:30 UTC｜T=5｜This is a test proposal for testing purposes"
        assert result == expected

    def test_no_description(self) -> None:
        """測試沒有描述"""
        proposal = MagicMock()
        proposal.deadline_at = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)
        proposal.description = ""
        proposal.threshold_t = 3

        result = _format_proposal_desc(proposal)
        expected = "截止 2025-01-15 10:30 UTC｜T=3｜無描述"
        assert result == expected

    def test_long_description_truncated(self) -> None:
        """測試長描述被截斷"""
        long_desc = "x" * 100  # 長度超過60字元
        proposal = MagicMock()
        proposal.deadline_at = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)
        proposal.description = long_desc
        proposal.threshold_t = 4

        result = _format_proposal_desc(proposal)
        assert len(result) <= 100  # 確保不會太長
        assert "xxxxx" in result  # 確保有描述內容


class TestGetHelpData:
    """測試 get_help_data 函數"""

    def test_returns_dict(self) -> None:
        """測試返回字典"""
        help_data = get_help_data()
        assert isinstance(help_data, dict)
        assert "council" in help_data
        assert "council config_role" in help_data
        assert "council add_role" in help_data
        assert "council remove_role" in help_data
        assert "council list_roles" in help_data
        assert "council panel" in help_data

    def test_help_data_structure(self) -> None:
        """測試幫助數據結構"""
        help_data = get_help_data()
        council_help = help_data["council"]

        assert council_help["name"] == "council"
        assert council_help["description"] == "理事會治理指令群組"
        assert council_help["category"] == "governance"
        assert isinstance(council_help["parameters"], list)
        assert isinstance(council_help["permissions"], list)
        assert isinstance(council_help["examples"], list)
        assert isinstance(council_help["tags"], list)


class TestBuildCouncilGroup:
    """測試 build_council_group 函數"""

    def test_returns_group(self, mock_council_service: MagicMock) -> None:
        """測試返回群組"""
        mock_result_service = MagicMock(spec=CouncilServiceResult)
        group = build_council_group(mock_council_service, mock_result_service)
        assert isinstance(group, discord.app_commands.Group)
        assert group.name == "council"
        assert group.description == "理事會治理指令群組"

    def test_group_has_commands(self, mock_council_service: MagicMock) -> None:
        """測試群組有指令"""
        mock_result_service = MagicMock(spec=CouncilServiceResult)
        group = build_council_group(mock_council_service, mock_result_service)
        # 檢查是否有 config_role 和 panel 指令
        command_names = [cmd.name for cmd in group._children.values()]
        assert "config_role" in command_names
        assert "add_role" in command_names
        assert "remove_role" in command_names
        assert "list_roles" in command_names
        assert "panel" in command_names


class TestRegister:
    """測試 register 函數"""

    def test_register_with_container(
        self, mock_command_tree: MagicMock, mock_container: MagicMock
    ) -> None:
        """測試使用容器註冊"""
        with patch("src.bot.commands.council._install_background_scheduler"):
            register(mock_command_tree, container=mock_container)
        mock_command_tree.add_command.assert_called_once()

    def test_register_without_container(self, mock_command_tree: MagicMock) -> None:
        """測試不使用容器註冊"""
        with (
            patch("src.bot.commands.council._install_background_scheduler"),
            patch("src.bot.commands.council.CouncilService") as mock_service_cls,
            patch("src.bot.commands.council.CouncilServiceResult") as mock_result_service_cls,
            patch("src.bot.commands.council.StateCouncilService") as mock_state_cls,
            patch("src.bot.commands.council.SupremeAssemblyService") as mock_supreme_cls,
            patch("src.bot.commands.council.PermissionService") as mock_permission_cls,
        ):
            service_instance = MagicMock(spec=CouncilService)
            mock_service_cls.return_value = service_instance
            mock_result_service_cls.return_value = MagicMock(spec=CouncilServiceResult)
            mock_state_cls.return_value = MagicMock(spec=StateCouncilService)
            mock_supreme_cls.return_value = MagicMock(spec=SupremeAssemblyService)
            mock_permission_cls.return_value = MagicMock(spec=PermissionService)
            register(mock_command_tree, container=None)
            mock_service_cls.assert_called_once_with()
        mock_command_tree.add_command.assert_called_once()


class TestHandleVote:
    """測試 _handle_vote 函數"""

    @pytest.mark.asyncio
    async def test_successful_vote(self, mock_council_service: MagicMock) -> None:
        """測試成功投票"""
        # 設置 mock
        mock_council_service.vote.return_value = (
            MagicMock(approve=5, reject=2, abstain=1, threshold_t=6),
            "進行中",
        )

        interaction = MagicMock()
        interaction.user.id = 67890
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send_message = AsyncMock()

        await _handle_vote(interaction, mock_council_service, uuid4(), "approve")

        mock_council_service.vote.assert_called_once_with(
            proposal_id=mock_council_service.vote.call_args[1]["proposal_id"],
            voter_id=67890,
            choice="approve",
        )
        interaction.response.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_permission_denied(self, mock_council_service: MagicMock) -> None:
        """測試權限被拒絕"""
        mock_council_service.vote.side_effect = PermissionDeniedError("沒有投票權")

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        await _handle_vote(interaction, mock_council_service, uuid4(), "approve")

        interaction.response.send_message.assert_called_with("沒有投票權", ephemeral=True)

    @pytest.mark.asyncio
    async def test_vote_error(self, mock_council_service: MagicMock) -> None:
        """測試投票錯誤"""
        mock_council_service.vote.side_effect = Exception("資料庫錯誤")

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        await _handle_vote(interaction, mock_council_service, uuid4(), "approve")

        interaction.response.send_message.assert_called_with("投票失敗。", ephemeral=True)


class TestSafeFetchUser:
    """測試 _safe_fetch_user 函數"""

    @pytest.mark.asyncio
    async def test_successful_fetch(self) -> None:
        """測試成功獲取使用者"""
        client = MagicMock(spec=discord.Client)
        user = MagicMock(spec=discord.User)
        client.fetch_user = AsyncMock(return_value=user)

        result = await _safe_fetch_user(client, 12345)
        assert result == user
        client.fetch_user.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_fetch_failure(self) -> None:
        """測試獲取使用者失敗"""
        client = MagicMock(spec=discord.Client)
        client.fetch_user = AsyncMock(side_effect=discord.NotFound(MagicMock(), "User not found"))

        result = await _safe_fetch_user(client, 12345)
        assert result is None


class TestCouncilPanelView:
    """測試 CouncilPanelView 類別"""

    @pytest.mark.asyncio
    async def test_init(self, mock_council_service: MagicMock, fake_guild: MagicMock) -> None:
        """測試初始化"""
        with (
            patch("discord.ui.View.__init__", return_value=None),
            patch("discord.ui.View.add_item"),
        ):
            view = CouncilPanelView(
                service=mock_council_service,
                guild=fake_guild,
                author_id=67890,
                council_role_id=11111,
            )

        assert view.service == mock_council_service
        assert view.guild == fake_guild
        assert view.author_id == 67890
        assert view.council_role_id == 11111

    @pytest.mark.asyncio
    async def test_build_summary_embed_success(
        self, mock_council_service: MagicMock, fake_guild: MagicMock
    ) -> None:
        """測試成功建立摘要嵌入"""
        with (
            patch("discord.ui.View.__init__", return_value=None),
            patch("discord.ui.View.add_item"),
        ):
            view = CouncilPanelView(
                service=mock_council_service,
                guild=fake_guild,
                author_id=67890,
                council_role_id=11111,
            )

        embed = await view.build_summary_embed()

        assert isinstance(embed, discord.Embed)
        assert embed.title == "常任理事會面板"
        assert "Council 摘要" in embed.fields[0].name

    @pytest.mark.asyncio
    async def test_refresh_options_error(
        self, mock_council_service: MagicMock, fake_guild: MagicMock
    ) -> None:
        """測試刷新選項時發生錯誤"""
        mock_council_service.list_active_proposals.side_effect = Exception("資料庫錯誤")

        with (
            patch("discord.ui.View.__init__", return_value=None),
            patch("discord.ui.View.add_item"),
        ):
            view = CouncilPanelView(
                service=mock_council_service,
                guild=fake_guild,
                author_id=67890,
                council_role_id=11111,
            )

        # 應該不會拋出異常
        await view.refresh_options()

        mock_council_service.list_active_proposals.assert_called_once()

    def test_build_help_embed(self, mock_council_service: MagicMock, fake_guild: MagicMock) -> None:
        """測試建立幫助嵌入"""
        with (
            patch("discord.ui.View.__init__", return_value=None),
            patch("discord.ui.View.add_item"),
        ):
            view = CouncilPanelView(
                service=mock_council_service,
                guild=fake_guild,
                author_id=67890,
                council_role_id=11111,
            )

        embed = view._build_help_embed()

        assert isinstance(embed, discord.Embed)
        assert "使用指引｜常任理事會面板" in embed.title
        assert "開啟方式" in (embed.description or "")


class TestTransferProposalModal:
    """測試 TransferProposalModal 類別"""

    @pytest.mark.asyncio
    async def test_init_user_target(
        self, mock_council_service: MagicMock, fake_guild: MagicMock
    ) -> None:
        """測試使用者目標初始化"""
        modal = TransferProposalModal(
            service=mock_council_service,
            guild=fake_guild,
            target_user_id=67890,
            target_user_name="TestUser",
        )

        assert modal.service == mock_council_service
        assert modal.guild == fake_guild
        assert modal.target_user_id == 67890
        assert modal.target_user_name == "TestUser"
        assert modal.target_department_id is None
        assert modal.target_department_name is None

    @pytest.mark.asyncio
    async def test_init_department_target(
        self, mock_council_service: MagicMock, fake_guild: MagicMock
    ) -> None:
        """測試部門目標初始化"""
        modal = TransferProposalModal(
            service=mock_council_service,
            guild=fake_guild,
            target_department_id="DEPT_001",
            target_department_name="財政部",
        )

        assert modal.service == mock_council_service
        assert modal.guild == fake_guild
        assert modal.target_user_id is None
        assert modal.target_user_name is None
        assert modal.target_department_id == "DEPT_001"
        assert modal.target_department_name == "財政部"

    @pytest.mark.asyncio
    async def test_submit_no_target(
        self, mock_council_service: MagicMock, fake_guild: MagicMock, fake_interaction: MagicMock
    ) -> None:
        """測試提交時沒有目標"""
        modal = TransferProposalModal(
            service=mock_council_service,
            guild=fake_guild,
        )

        await modal.on_submit(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "錯誤：未選擇受款人。",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_submit_invalid_amount(
        self, mock_council_service: MagicMock, fake_guild: MagicMock, fake_interaction: MagicMock
    ) -> None:
        """測試提交時金額無效"""
        modal = TransferProposalModal(
            service=mock_council_service,
            guild=fake_guild,
            target_user_id=67890,
        )
        modal.amount = MagicMock()
        modal.amount.value = "not_a_number"

        await modal.on_submit(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "金額需為正整數。",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_submit_zero_amount(
        self, mock_council_service: MagicMock, fake_guild: MagicMock, fake_interaction: MagicMock
    ) -> None:
        """測試提交時金額為零"""
        modal = TransferProposalModal(
            service=mock_council_service,
            guild=fake_guild,
            target_user_id=67890,
        )
        modal.amount = MagicMock()
        modal.amount.value = "0"

        await modal.on_submit(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "金額需 > 0。",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_submit_governance_not_configured(
        self, mock_council_service: MagicMock, fake_guild: MagicMock, fake_interaction: MagicMock
    ) -> None:
        """測試提交時治理未配置"""
        mock_council_service.get_config.side_effect = GovernanceNotConfiguredError("未配置")

        modal = TransferProposalModal(
            service=mock_council_service,
            guild=fake_guild,
            target_user_id=67890,
        )
        modal.amount = MagicMock()
        modal.amount.value = "100"

        await modal.on_submit(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "尚未完成治理設定。",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_submit_empty_role_members(
        self,
        mock_council_service: MagicMock,
        fake_guild: MagicMock,
        fake_interaction: MagicMock,
        fake_role: MagicMock,
    ) -> None:
        """測試提交時角色成員為空"""
        mock_council_service.get_config.return_value = MagicMock()
        fake_role.members = []
        fake_guild.get_role.return_value = fake_role

        modal = TransferProposalModal(
            service=mock_council_service,
            guild=fake_guild,
            target_user_id=67890,
        )
        modal.amount = MagicMock()
        modal.amount.value = "100"

        await modal.on_submit(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "理事名冊為空，請先確認角色有成員。",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_submit_success(
        self,
        mock_council_service: MagicMock,
        fake_guild: MagicMock,
        fake_interaction: MagicMock,
        fake_role: MagicMock,
    ) -> None:
        """測試成功提交"""
        # Mock config
        mock_config = MagicMock()
        mock_council_service.get_config.return_value = mock_config

        # Mock role with members
        fake_member = MagicMock()
        fake_member.id = 11111
        fake_role.members = [fake_member]
        fake_guild.get_role.return_value = fake_role

        # Mock proposal creation
        mock_proposal = MagicMock()
        mock_proposal.proposal_id = uuid4()
        mock_council_service.create_transfer_proposal.return_value = mock_proposal

        modal = TransferProposalModal(
            service=mock_council_service,
            guild=fake_guild,
            target_user_id=67890,
        )
        modal.amount = MagicMock()
        modal.amount.value = "100"
        modal.description = MagicMock()
        modal.description.value = "Test description"
        modal.attachment_url = MagicMock()
        modal.attachment_url.value = "http://example.com"

        await modal.on_submit(fake_interaction)

        mock_council_service.create_transfer_proposal.assert_called_once()
        fake_interaction.response.send_message.assert_called()


class TestExportModal:
    """測試 ExportModal 類別"""

    @pytest.mark.asyncio
    async def test_init(self, mock_council_service: MagicMock, fake_guild: MagicMock) -> None:
        """測試初始化"""
        modal = ExportModal(service=mock_council_service, guild=fake_guild)

        assert modal.service == mock_council_service
        assert modal.guild == fake_guild

    @pytest.mark.asyncio
    async def test_submit_no_permissions(
        self,
        mock_council_service: MagicMock,
        fake_guild: MagicMock,
        fake_interaction: MagicMock,
        fake_member: MagicMock,
    ) -> None:
        """測試提交時沒有權限"""
        fake_member.guild_permissions.administrator = False
        fake_member.guild_permissions.manage_guild = False
        fake_interaction.user = fake_member

        modal = ExportModal(service=mock_council_service, guild=fake_guild)
        modal.start = MagicMock()
        modal.start.value = "2025-01-01T00:00:00Z"
        modal.end = MagicMock()
        modal.end.value = "2025-01-31T23:59:59Z"
        modal.format = MagicMock()
        modal.format.value = "json"

        await modal.on_submit(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "需要管理員或管理伺服器權限。",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_submit_invalid_time_format(
        self,
        mock_council_service: MagicMock,
        fake_guild: MagicMock,
        fake_interaction: MagicMock,
        fake_member: MagicMock,
    ) -> None:
        """測試提交時時間格式無效"""
        fake_member.guild_permissions.administrator = True
        fake_interaction.user = fake_member

        modal = ExportModal(service=mock_council_service, guild=fake_guild)
        modal.start = MagicMock()
        modal.start.value = "invalid_time"
        modal.end = MagicMock()
        modal.end.value = "2025-01-31T23:59:59Z"
        modal.format = MagicMock()
        modal.format.value = "json"

        await modal.on_submit(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "時間格式錯誤，請使用 ISO 8601（例如 2025-01-01T00:00:00Z）",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_submit_start_after_end(
        self,
        mock_council_service: MagicMock,
        fake_guild: MagicMock,
        fake_interaction: MagicMock,
        fake_member: MagicMock,
    ) -> None:
        """測試提交時開始時間晚於結束時間"""
        fake_member.guild_permissions.administrator = True
        fake_interaction.user = fake_member

        modal = ExportModal(service=mock_council_service, guild=fake_guild)
        modal.start = MagicMock()
        modal.start.value = "2025-02-01T00:00:00Z"
        modal.end = MagicMock()
        modal.end.value = "2025-01-31T23:59:59Z"
        modal.format = MagicMock()
        modal.format.value = "json"

        await modal.on_submit(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "起始時間不可晚於結束時間。",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_submit_invalid_format(
        self,
        mock_council_service: MagicMock,
        fake_guild: MagicMock,
        fake_interaction: MagicMock,
        fake_member: MagicMock,
    ) -> None:
        """測試提交時格式無效"""
        fake_member.guild_permissions.administrator = True
        fake_interaction.user = fake_member

        modal = ExportModal(service=mock_council_service, guild=fake_guild)
        modal.start = MagicMock()
        modal.start.value = "2025-01-01T00:00:00Z"
        modal.end = MagicMock()
        modal.end.value = "2025-01-31T23:59:59Z"
        modal.format = MagicMock()
        modal.format.value = "xml"  # 不支持的格式

        await modal.on_submit(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "格式必須是 json 或 csv。",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_export_json_success(
        self,
        mock_council_service: MagicMock,
        fake_guild: MagicMock,
        fake_interaction: MagicMock,
        fake_member: MagicMock,
    ) -> None:
        """測試 JSON 導出成功"""
        fake_member.guild_permissions.administrator = True
        fake_interaction.user = fake_member
        fake_interaction.guild_id = fake_guild.id

        # Mock export data
        mock_data = [{"proposal_id": str(uuid4()), "amount": 1000}]
        mock_council_service.export_interval.return_value = mock_data

        modal = ExportModal(service=mock_council_service, guild=fake_guild)
        modal.start = MagicMock()
        modal.start.value = "2025-01-01T00:00:00Z"
        modal.end = MagicMock()
        modal.end.value = "2025-01-31T23:59:59Z"
        modal.format = MagicMock()
        modal.format.value = "json"

        await modal.on_submit(fake_interaction)

        mock_council_service.export_interval.assert_called_once()
        fake_interaction.response.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_export_csv_success(
        self,
        mock_council_service: MagicMock,
        fake_guild: MagicMock,
        fake_interaction: MagicMock,
        fake_member: MagicMock,
    ) -> None:
        """測試 CSV 導出成功"""
        fake_member.guild_permissions.administrator = True
        fake_interaction.user = fake_member
        fake_interaction.guild_id = fake_guild.id

        # Mock export data
        mock_data = [{"proposal_id": str(uuid4()), "amount": 1000}]
        mock_council_service.export_interval.return_value = mock_data

        modal = ExportModal(service=mock_council_service, guild=fake_guild)
        modal.start = MagicMock()
        modal.start.value = "2025-01-01T00:00:00Z"
        modal.end = MagicMock()
        modal.end.value = "2025-01-31T23:59:59Z"
        modal.format = MagicMock()
        modal.format.value = "csv"

        await modal.on_submit(fake_interaction)

        mock_council_service.export_interval.assert_called_once()
        fake_interaction.response.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_export_service_error(
        self,
        mock_council_service: MagicMock,
        fake_guild: MagicMock,
        fake_interaction: MagicMock,
        fake_member: MagicMock,
    ) -> None:
        """測試導出時服務錯誤"""
        fake_member.guild_permissions.administrator = True
        fake_interaction.user = fake_member
        fake_interaction.guild_id = fake_guild.id

        mock_council_service.export_interval.side_effect = Exception("資料庫錯誤")

        modal = ExportModal(service=mock_council_service, guild=fake_guild)
        modal.start = MagicMock()
        modal.start.value = "2025-01-01T00:00:00Z"
        modal.end = MagicMock()
        modal.end.value = "2025-01-31T23:59:59Z"
        modal.format = MagicMock()
        modal.format.value = "json"

        await modal.on_submit(fake_interaction)

        fake_interaction.response.send_message.assert_called_with(
            "匯出失敗：資料庫錯誤",
            ephemeral=True,
        )


class TestProposalActionView:
    """測試 ProposalActionView 類別"""

    def test_init_with_cancel_permission(self, mock_council_service: MagicMock) -> None:
        """測試有撤案權限的初始化"""
        proposal_id = uuid4()
        with (
            patch("discord.ui.View.__init__", return_value=None),
            patch("discord.ui.View.add_item"),
        ):
            view = ProposalActionView(
                service=mock_council_service,
                proposal_id=proposal_id,
                can_cancel=True,
            )

        assert view.service == mock_council_service
        assert view.proposal_id == proposal_id
        assert view._can_cancel is True

    def test_init_without_cancel_permission(self, mock_council_service: MagicMock) -> None:
        """測試沒有撤案權限的初始化"""
        proposal_id = uuid4()
        with (
            patch("discord.ui.View.__init__", return_value=None),
            patch("discord.ui.View.add_item"),
        ):
            view = ProposalActionView(
                service=mock_council_service,
                proposal_id=proposal_id,
                can_cancel=False,
            )

        assert view._can_cancel is False

    @pytest.mark.asyncio
    async def test_cancel_without_permission(self, mock_council_service: MagicMock) -> None:
        """測試沒有權限時嘗試撤案"""
        proposal_id = uuid4()
        with (
            patch("discord.ui.View.__init__", return_value=None),
            patch("discord.ui.View.add_item"),
        ):
            view = ProposalActionView(
                service=mock_council_service,
                proposal_id=proposal_id,
                can_cancel=False,
            )

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        # Create a proper button mock
        button = MagicMock()
        button.custom_id = "panel_cancel_btn"

        await view.cancel(interaction, button)

        interaction.response.send_message.assert_called_with(
            "你不是此提案的提案人。",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_cancel_success(self, mock_council_service: MagicMock) -> None:
        """測試成功撤案"""
        proposal_id = uuid4()
        with (
            patch("discord.ui.View.__init__", return_value=None),
            patch("discord.ui.View.add_item"),
        ):
            view = ProposalActionView(
                service=mock_council_service,
                proposal_id=proposal_id,
                can_cancel=True,
            )

        mock_council_service.cancel_proposal.return_value = True

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        # Create a proper button mock
        button = MagicMock()
        button.custom_id = "panel_cancel_btn"

        await view.cancel(interaction, button)

        mock_council_service.cancel_proposal.assert_called_once_with(proposal_id=proposal_id)
        interaction.response.send_message.assert_called_with("已撤案。", ephemeral=True)

    @pytest.mark.asyncio
    async def test_cancel_failure(self, mock_council_service: MagicMock) -> None:
        """測試撤案失敗"""
        proposal_id = uuid4()
        with (
            patch("discord.ui.View.__init__", return_value=None),
            patch("discord.ui.View.add_item"),
        ):
            view = ProposalActionView(
                service=mock_council_service,
                proposal_id=proposal_id,
                can_cancel=True,
            )

        mock_council_service.cancel_proposal.return_value = False

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        # Create a proper button mock
        button = MagicMock()
        button.custom_id = "panel_cancel_btn"

        await view.cancel(interaction, button)

        mock_council_service.cancel_proposal.assert_called_once_with(proposal_id=proposal_id)
        interaction.response.send_message.assert_called_with(
            "撤案失敗：可能已有人投票或狀態非進行中。",
            ephemeral=True,
        )


class TestRegisterPersistentViews:
    """測試 _register_persistent_views 函數"""

    @pytest.mark.asyncio
    async def test_register_views_success(self) -> None:
        """測試成功註冊視圖"""
        client = MagicMock(spec=discord.Client)

        # Mock pool and connection
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_pool.acquire.return_value.__aexit__.return_value = None

        # Mock gateway and active proposals
        mock_proposal = MagicMock()
        mock_proposal.proposal_id = uuid4()

        with pytest.MonkeyPatch().context() as m:
            m.setattr("src.bot.commands.council.get_pool", lambda: mock_pool)

            # Mock the gateway
            mock_gateway = MagicMock()
            mock_gateway.list_active_proposals = AsyncMock(return_value=[mock_proposal])

            with pytest.MonkeyPatch().context() as m2:
                m2.setattr(
                    "src.db.gateway.council_governance.CouncilGovernanceGateway",
                    lambda: mock_gateway,
                )

                await _register_persistent_views(client, MagicMock())

                client.add_view.assert_called()


class TestBroadcastResult:
    """測試 _broadcast_result 函數"""

    @pytest.mark.asyncio
    async def test_broadcast_success(self) -> None:
        """測試成功廣播結果"""
        client = MagicMock(spec=discord.Client)
        guild = MagicMock(spec=discord.Guild)
        guild.id = 12345

        service = MagicMock(spec=CouncilService)
        proposal_id = uuid4()

        # Mock data
        snapshot = [11111, 22222, 33333]
        votes = [(11111, "approve"), (22222, "reject"), (33333, "abstain")]

        service.get_snapshot = AsyncMock(return_value=snapshot)
        service.get_votes_detail = AsyncMock(return_value=votes)
        service.get_config = AsyncMock(return_value=MagicMock(council_role_id=44444))
        service.get_proposal = AsyncMock(return_value=MagicMock(proposer_id=11111))

        # Mock role and members
        role = MagicMock()
        member1 = MagicMock()
        member1.id = 11111
        member1.send = AsyncMock()
        member2 = MagicMock()
        member2.id = 22222
        member2.send = AsyncMock()
        member3 = MagicMock()
        member3.id = 33333
        member3.send = AsyncMock()

        role.members = [member1, member2, member3]
        guild.get_role = MagicMock(return_value=role)
        guild.get_member = MagicMock(return_value=member1)

        await _broadcast_result(client, guild, service, proposal_id, "已執行")

        # Verify each member received a message
        member1.send.assert_called_once()
        member2.send.assert_called_once()
        member3.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_with_send_failure(self) -> None:
        """測試廣播時發送失敗"""
        client = MagicMock(spec=discord.Client)
        guild = MagicMock(spec=discord.Guild)
        guild.id = 12345

        service = MagicMock(spec=CouncilService)
        proposal_id = uuid4()

        # Mock data
        snapshot = [11111]
        votes = [(11111, "approve")]

        service.get_snapshot = AsyncMock(return_value=snapshot)
        service.get_votes_detail = AsyncMock(return_value=votes)
        service.get_config = AsyncMock(return_value=MagicMock(council_role_id=44444))
        service.get_proposal = AsyncMock(return_value=MagicMock(proposer_id=11111))

        # Mock role and member with send failure
        role = MagicMock()
        member = MagicMock()
        member.id = 11111
        member.send = AsyncMock(side_effect=Exception("Send failed"))

        role.members = [member]
        guild.get_role = MagicMock(return_value=role)
        guild.get_member = MagicMock(return_value=member)

        # Should not raise exception
        await _broadcast_result(client, guild, service, proposal_id, "已執行")

        member.send.assert_called_once()


# --- Integration Tests ---


class TestCouncilCommandsIntegration:
    """理事會指令整合測試"""

    @pytest.mark.asyncio
    async def test_config_role_command_success(
        self,
        mock_council_service: MagicMock,
        fake_guild: MagicMock,
        fake_member: MagicMock,
        fake_role: MagicMock,
    ) -> None:
        """測試 config_role 指令成功"""
        # Set up permissions
        fake_member.guild_permissions.administrator = True

        # Create interaction
        interaction = MagicMock()
        interaction.guild_id = fake_guild.id
        interaction.guild = fake_guild
        interaction.user = fake_member
        interaction.response = MagicMock()

        # Mock service response
        mock_config = MagicMock()
        mock_config.council_account_member_id = 99999
        mock_council_service.set_config.return_value = mock_config

        # Create command
        group = build_council_group(mock_council_service)

        # Get config_role command
        config_role_cmd = None
        for child in group._children.values():
            if child.name == "config_role":
                config_role_cmd = child
                break

        assert config_role_cmd is not None

        # Execute command
        await config_role_cmd.callback(interaction, fake_role)

        mock_council_service.set_config.assert_called_once_with(
            guild_id=fake_guild.id, council_role_id=fake_role.id
        )
        interaction.response.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_config_role_command_no_permissions(
        self, mock_council_service: MagicMock, fake_guild: MagicMock, fake_member: MagicMock
    ) -> None:
        """測試 config_role 指令沒有權限"""
        # Set up no permissions
        fake_member.guild_permissions.administrator = False
        fake_member.guild_permissions.manage_guild = False

        # Create interaction
        interaction = MagicMock()
        interaction.guild_id = fake_guild.id
        interaction.guild = fake_guild
        interaction.user = fake_member
        interaction.response = MagicMock()

        # Create command
        group = build_council_group(mock_council_service)

        # Get config_role command
        config_role_cmd = None
        for child in group._children.values():
            if child.name == "config_role":
                config_role_cmd = child
                break

        assert config_role_cmd is not None

        # Execute command
        await config_role_cmd.callback(interaction, MagicMock())

        interaction.response.send_message.assert_called_with(
            "需要管理員或管理伺服器權限。", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_panel_command_not_configured(
        self, mock_council_service: MagicMock, fake_guild: MagicMock, fake_member: MagicMock
    ) -> None:
        """測試 panel 指令未配置"""
        # Mock governance not configured
        mock_council_service.get_config.side_effect = GovernanceNotConfiguredError("未配置")

        # Create interaction
        interaction = MagicMock()
        interaction.guild_id = fake_guild.id
        interaction.guild = fake_guild
        interaction.user = fake_member
        interaction.response = MagicMock()

        # Create command
        group = build_council_group(mock_council_service)

        # Get panel command
        panel_cmd = None
        for child in group._children.values():
            if child.name == "panel":
                panel_cmd = child
                break

        assert panel_cmd is not None

        # Execute command
        await panel_cmd.callback(interaction)

        interaction.response.send_message.assert_called_with(
            "尚未完成治理設定，請先執行 /council config_role。", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_panel_command_not_council_member(
        self,
        mock_council_service: MagicMock,
        fake_guild: MagicMock,
        fake_member: MagicMock,
        fake_role: MagicMock,
    ) -> None:
        """測試 panel 指令不是理事會成員"""
        # Mock config
        mock_config = MagicMock()
        mock_config.council_role_id = fake_role.id
        mock_council_service.get_config.return_value = mock_config

        # Mock user not having role
        fake_guild.get_role.return_value = fake_role
        fake_member.roles = []  # No council role

        # Create interaction
        interaction = MagicMock()
        interaction.guild_id = fake_guild.id
        interaction.guild = fake_guild
        interaction.user = fake_member
        interaction.response = MagicMock()

        # Create command
        group = build_council_group(mock_council_service)

        # Get panel command
        panel_cmd = None
        for child in group._children.values():
            if child.name == "panel":
                panel_cmd = child
                break

        assert panel_cmd is not None

        mock_council_service.check_council_permission.return_value = False

        # Execute command
        await panel_cmd.callback(interaction)

        interaction.response.send_message.assert_called_with(
            "僅限具備常任理事身分組的人員可開啟面板。", ephemeral=True
        )
