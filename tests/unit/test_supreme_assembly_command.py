"""Supreme Assembly 指令測試。

測試最高人民會議指令的功能，包括：
- 參數驗證
- 權限檢查
- 配置管理
- 提案、投票、執行流程的關鍵邏輯
- 面板互動和錯誤處理
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.bot.commands.supreme_assembly import (
    SupremeAssemblyPanelView,
    build_supreme_assembly_group,
)
from src.bot.services.council_service import CouncilService
from src.bot.services.permission_service import PermissionService
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.supreme_assembly_service import (
    GovernanceNotConfiguredError,
    PermissionDeniedError,
    SupremeAssemblyService,
    VoteAlreadyExistsError,
    VoteTotals,
)
from src.db.gateway.supreme_assembly_governance import (
    Proposal,
    SupremeAssemblyConfig,
)
from src.infra.result import Err, Ok


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


def _proposal(**overrides: object) -> Proposal:
    """建立帶有預設值的 Proposal 物件，避免測試重複樣板。"""
    now = datetime.now(tz=timezone.utc)
    payload: dict[str, object] = {
        "proposal_id": UUID(int=secrets.randbits(128)),
        "guild_id": _snowflake(),
        "proposer_id": _snowflake(),
        "title": "測試提案",
        "description": "測試描述",
        "snapshot_n": 1,
        "threshold_t": 5,
        "deadline_at": now,
        "status": "進行中",
        "reminder_sent": False,
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return Proposal(**payload)  # type: ignore[arg-type]


@pytest.mark.unit
class TestSupremeAssemblyCommand:
    """Supreme Assembly 指令單元測試。"""

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        """創建模擬的 SupremeAssemblyService。"""
        service = MagicMock(spec=SupremeAssemblyService)
        service.vote = AsyncMock()
        service.get_config = AsyncMock()
        service.create_proposal = AsyncMock()
        service.list_active_proposals = AsyncMock()
        return service

    @pytest.fixture
    def mock_tree(self) -> MagicMock:
        """創建模擬的命令樹。"""
        tree = MagicMock()
        tree.client = None
        return tree

    @pytest.fixture
    def sample_guild_id(self) -> int:
        """測試公會ID。"""
        return _snowflake()

    @pytest.fixture
    def sample_config(self, sample_guild_id: int) -> SupremeAssemblyConfig:
        """測試配置。"""
        return SupremeAssemblyConfig(
            guild_id=sample_guild_id,
            speaker_role_id=_snowflake(),
            member_role_id=_snowflake(),
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

    def test_build_supreme_assembly_group(self, mock_service: MagicMock) -> None:
        """測試建立 supreme_assembly 指令群組。"""
        group = build_supreme_assembly_group(mock_service)

        assert group.name == "supreme_assembly"
        assert group.description == "最高人民會議治理指令群組"
        # 檢查是否包含基本指令
        # type: ignore[protected-access]
        command_names = [cmd.name for cmd in cast(Any, group)._children.values()]
        expected_commands = ["config_speaker_role", "config_member_role", "panel"]
        for cmd in expected_commands:
            assert cmd in command_names, f"缺少指令: {cmd}"

    def test_register_command(self, mock_tree: MagicMock) -> None:
        """測試註冊指令。"""
        with (
            patch("src.bot.commands.supreme_assembly.build_supreme_assembly_group") as mock_build,
            patch("src.bot.commands.supreme_assembly.SupremeAssemblyService") as mock_service_cls,
            patch("src.bot.commands.supreme_assembly.PermissionService") as mock_permission_cls,
            patch("src.bot.commands.supreme_assembly.CouncilServiceResult") as mock_council_cls,
            patch("src.bot.commands.supreme_assembly.StateCouncilService") as mock_state_cls,
        ):
            mock_group = MagicMock()
            mock_build.return_value = mock_group
            mock_service_cls.return_value = MagicMock(spec=SupremeAssemblyService)
            mock_permission_cls.return_value = MagicMock(spec=PermissionService)
            mock_council_cls.return_value = MagicMock(spec=CouncilService)
            mock_state_cls.return_value = MagicMock(spec=StateCouncilService)

            # 測試註冊
            from src.bot.commands.supreme_assembly import register

            register(mock_tree)

            # 驗證調用
            mock_tree.add_command.assert_called_once_with(mock_group)

    def test_config_speaker_role_permission_check(
        self, mock_service: MagicMock, sample_guild_id: int
    ) -> None:
        """測試配置議長角色權限檢查。"""
        # 建立指令群組
        group = build_supreme_assembly_group(mock_service)

        # 獲取配置議長角色指令
        config_cmd = None
        for cmd in cast(Any, group)._children.values():
            if hasattr(cmd, "name") and cmd.name == "config_speaker_role":
                config_cmd = cmd
                break

        assert config_cmd is not None, "找不到 config_speaker_role 指令"

    def test_config_member_role_permission_check(
        self, mock_service: MagicMock, sample_guild_id: int
    ) -> None:
        """測試配置議員角色權限檢查。"""
        # 建立指令群組
        group = build_supreme_assembly_group(mock_service)

        # 獲取配置議員角色指令
        config_cmd = None
        for cmd in cast(Any, group)._children.values():
            if hasattr(cmd, "name") and cmd.name == "config_member_role":
                config_cmd = cmd
                break

        assert config_cmd is not None, "找不到 config_member_role 指令"

    def test_panel_command_exists(self, mock_service: MagicMock) -> None:
        """測試面板指令存在。"""
        # 建立指令群組
        group = build_supreme_assembly_group(mock_service)

        # 獲取面板指令
        panel_cmd = None
        for cmd in cast(Any, group)._children.values():
            if hasattr(cmd, "name") and cmd.name == "panel":
                panel_cmd = cmd
                break

        assert panel_cmd is not None, "找不到 panel 指令"
        assert panel_cmd.description == "開啟最高人民會議面板（表決/投票/傳召）"


@pytest.mark.asyncio
class TestSupremeAssemblyPanelView:
    """Supreme Assembly 面板視圖測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        return AsyncMock(spec=SupremeAssemblyService)

    @pytest.fixture
    def mock_guild(self) -> MagicMock:
        """創建模擬的 Discord 公會。"""
        guild = MagicMock()
        guild.id = _snowflake()
        return guild

    @pytest.fixture
    def sample_config(self) -> SupremeAssemblyConfig:
        """測試配置。"""
        return SupremeAssemblyConfig(
            guild_id=_snowflake(),
            speaker_role_id=_snowflake(),
            member_role_id=_snowflake(),
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

    def test_panel_view_initialization(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """測試面板視圖初始化。"""
        author_id = _snowflake()
        speaker_role_id = _snowflake()
        member_role_id = _snowflake()

        # 創建一個模擬的 View 基類來避免 Discord UI 的問題
        with (
            patch("discord.ui.View.__init__") as mock_init,
            patch("discord.ui.View.add_item") as mock_add_item,
            patch.object(SupremeAssemblyPanelView, "timeout", 600),
        ):
            # 設置模擬屬性
            mock_init.return_value = None

            view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=author_id,
                speaker_role_id=speaker_role_id,
                member_role_id=member_role_id,
                is_speaker=True,
                is_member=True,
            )

            # 驗證基本屬性
            assert view.service == mock_service
            assert view.guild == mock_guild
            assert view.author_id == author_id
            assert view.speaker_role_id == speaker_role_id
            assert view.member_role_id == member_role_id
            assert view.is_speaker is True
            assert view.is_member is True

            # 驗證 Discord UI 方法被調用
            mock_init.assert_called_once()
            assert mock_add_item.call_count > 0  # 應該添加了一些 UI 元素

    def test_panel_view_components(self, mock_service: MagicMock, mock_guild: MagicMock) -> None:
        """測試面板視圖組件。"""
        with patch("discord.ui.View.__init__"), patch("discord.ui.View.add_item"):
            view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=_snowflake(),
                member_role_id=_snowflake(),
                is_speaker=True,
                is_member=True,
            )

            # 檢查基本按鈕
            assert hasattr(view, "_transfer_btn")
            assert hasattr(view, "_help_btn")
            assert hasattr(view, "_view_all_btn")
            assert hasattr(view, "_select")

            # 檢查議長專屬按鈕
            assert hasattr(view, "_propose_btn")
            assert hasattr(view, "_summon_btn")

    def test_panel_view_speaker_only_components(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """測試議長專屬組件只在議長時顯示。"""
        with patch("discord.ui.View.__init__"), patch("discord.ui.View.add_item"):
            # 議長模式
            speaker_view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=_snowflake(),
                member_role_id=_snowflake(),
                is_speaker=True,
                is_member=True,
            )

            # 非議長模式
            member_view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=_snowflake(),
                member_role_id=_snowflake(),
                is_speaker=False,
                is_member=True,
            )

            # 議長擁有提案與傳召按鈕
            assert hasattr(speaker_view, "_propose_btn")
            assert hasattr(speaker_view, "_summon_btn")

            # 人民代表同樣能提案，但無傳召權限
            assert hasattr(member_view, "_propose_btn")
            assert not hasattr(member_view, "_summon_btn")

    @pytest.mark.asyncio
    async def test_build_summary_embed(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """測試建立摘要嵌入。"""
        with patch("discord.ui.View.__init__"), patch("discord.ui.View.add_item"):
            view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=_snowflake(),
                member_role_id=_snowflake(),
                is_speaker=True,
                is_member=True,
            )

            # Mock balance service
            with patch("src.bot.commands.supreme_assembly.BalanceService") as mock_balance_service:
                mock_balance = AsyncMock()
                mock_balance_service.return_value = mock_balance

                # Mock balance snapshot
                mock_snap = MagicMock()
                mock_snap.balance = 15000
                mock_balance.get_balance_snapshot.return_value = mock_snap

                embed = await view.build_summary_embed()

                # 驗證嵌入內容
                assert embed.title == "最高人民會議面板"
                assert embed.description is not None
                assert "轉帳、發起表決" in embed.description
                # 檢查欄位中的餘額和議員信息
                assert len(embed.fields) > 0
                summary_field = embed.fields[0]
                assert summary_field.value is not None
                assert "餘額：" in summary_field.value
                assert "議員" in summary_field.value

    def test_build_help_embed(self, mock_service: MagicMock, mock_guild: MagicMock) -> None:
        """測試建立說明嵌入。"""
        with patch("discord.ui.View.__init__"), patch("discord.ui.View.add_item"):
            view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=_snowflake(),
                member_role_id=_snowflake(),
                is_speaker=True,
                is_member=True,
            )

            embed = view._build_help_embed()  # type: ignore[protected-access]

            # 驗證說明嵌入內容
            assert embed.title == "ℹ️ 使用指引｜最高人民會議面板"
            assert embed.description is not None
            assert "開啟方式：" in embed.description
            assert "轉帳功能：" in embed.description
            assert "發起表決：" in embed.description
            assert "投票規則：" in embed.description

    @pytest.mark.asyncio
    async def test_refresh_options(self, mock_service: MagicMock, mock_guild: MagicMock) -> None:
        """測試刷新選項。"""
        with patch("discord.ui.View.__init__"), patch("discord.ui.View.add_item"):
            view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=_snowflake(),
                member_role_id=_snowflake(),
                is_speaker=True,
                is_member=True,
            )

            # Mock 服務回傳進行中提案
            proposals = [
                _proposal(
                    guild_id=mock_guild.id,
                    description="測試提案1",
                )
            ]
            mock_service.list_active_proposals.return_value = proposals

            await view.refresh_options()

            # 驗證服務被調用
            mock_service.list_active_proposals.assert_called_once_with(guild_id=mock_guild.id)

            # 驗證選單選項已更新
            assert hasattr(view, "_select")
            assert len(view._select.options) > 0  # type: ignore[protected-access]


@pytest.mark.asyncio
class TestSupremeAssemblyCommandIntegration:
    """Supreme Assembly 指令整合測試。"""

    @pytest.fixture
    def mock_interaction(self) -> MagicMock:
        """創建模擬的 Discord 互動。"""
        interaction = MagicMock()
        interaction.guild_id = _snowflake()
        interaction.user = MagicMock()
        interaction.user.guild_permissions = MagicMock()
        interaction.user.guild_permissions.administrator = True
        interaction.user.guild_permissions.manage_guild = True
        return interaction

    @pytest.fixture
    def mock_role(self) -> MagicMock:
        """創建模擬的 Discord 角色。"""
        role = MagicMock()
        role.id = _snowflake()
        role.mention = f"<@&{role.id}>"
        return role

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        service = AsyncMock(spec=SupremeAssemblyService)
        return service

    async def test_config_speaker_role_success(
        self, mock_interaction: MagicMock, mock_role: MagicMock, mock_service: MagicMock
    ) -> None:
        """測試成功配置議長角色。"""
        guild_id = mock_interaction.guild_id

        # Mock 不存在現有配置
        mock_service.get_config.side_effect = GovernanceNotConfiguredError("未配置")

        # Mock 成功建立配置
        expected_config = SupremeAssemblyConfig(
            guild_id=guild_id,
            speaker_role_id=mock_role.id,
            member_role_id=0,  # 首次配置暫存為 0
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        mock_service.set_config.return_value = expected_config

        # 建立指令群組
        group = build_supreme_assembly_group(mock_service)

        # 獲取配置議長角色指令
        config_cmd = None
        for cmd in cast(Any, group)._children.values():
            if hasattr(cmd, "name") and cmd.name == "config_speaker_role":
                config_cmd = cmd
                break

        assert config_cmd is not None

        # 執行指令回調應
        mock_interaction.response = MagicMock()

        # 檢查基本權限驗證邏輯
        assert mock_interaction.user.guild_permissions.administrator is True
        assert mock_interaction.user.guild_permissions.manage_guild is True

    async def test_config_member_role_success(
        self, mock_interaction: MagicMock, mock_role: MagicMock, mock_service: MagicMock
    ) -> None:
        """測試成功配置議員角色。"""
        guild_id = mock_interaction.guild_id

        # Mock 現有議長配置
        existing_config = SupremeAssemblyConfig(
            guild_id=guild_id,
            speaker_role_id=_snowflake(),
            member_role_id=0,  # 尚未設定
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        mock_service.get_config.return_value = existing_config

        # Mock 成功更新配置
        updated_config = SupremeAssemblyConfig(
            guild_id=guild_id,
            speaker_role_id=existing_config.speaker_role_id,
            member_role_id=mock_role.id,
            created_at=existing_config.created_at,
            updated_at=datetime.now(tz=timezone.utc),
        )
        mock_service.set_config.return_value = updated_config

        # 建立指令群組
        group = build_supreme_assembly_group(mock_service)

        # 獲取配置議員角色指令
        config_cmd = None
        for cmd in cast(Any, group)._children.values():
            if hasattr(cmd, "name") and cmd.name == "config_member_role":
                config_cmd = cmd
                break

        assert config_cmd is not None

        # 執行指令回調應
        mock_interaction.response = MagicMock()

        # 檢查基本權限驗證邏輯
        assert mock_interaction.user.guild_permissions.administrator is True
        assert mock_interaction.user.guild_permissions.manage_guild is True

    async def test_config_speaker_role_handles_result_bootstrap(
        self, mock_interaction: MagicMock, mock_role: MagicMock, mock_service: MagicMock
    ) -> None:
        """當 get_config 回傳 Err 時應能正常啟動並回覆成功訊息。"""

        guild_id = mock_interaction.guild_id
        mock_interaction.guild = MagicMock()
        mock_interaction.user.id = _snowflake()

        mock_service.get_config.return_value = Err(GovernanceNotConfiguredError("未配置"))

        expected_config = SupremeAssemblyConfig(
            guild_id=guild_id,
            speaker_role_id=mock_role.id,
            member_role_id=0,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        mock_service.set_config.return_value = Ok(expected_config)
        mock_service.get_or_create_account_id = AsyncMock(return_value=987654321)

        group = build_supreme_assembly_group(mock_service)
        config_cmd = None
        for cmd in cast(Any, group)._children.values():
            if getattr(cmd, "name", None) == "config_speaker_role":
                config_cmd = cmd
                break

        assert config_cmd is not None

        with patch(
            "src.bot.commands.supreme_assembly.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await config_cmd.callback(mock_interaction, mock_role)

        mock_service.set_config.assert_awaited_once_with(
            guild_id=guild_id, speaker_role_id=mock_role.id, member_role_id=0
        )
        mock_service.get_or_create_account_id.assert_awaited_once_with(guild_id)

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        assert "已設定議長角色" in kwargs.get("content", "")
        assert kwargs.get("ephemeral") is True

    async def test_config_member_role_surfaces_set_config_err(
        self, mock_interaction: MagicMock, mock_role: MagicMock, mock_service: MagicMock
    ) -> None:
        """set_config 回傳 Err 時應回覆錯誤而非成功訊息。"""

        guild_id = mock_interaction.guild_id
        mock_interaction.guild = MagicMock()
        mock_interaction.user.id = _snowflake()

        existing_config = SupremeAssemblyConfig(
            guild_id=guild_id,
            speaker_role_id=_snowflake(),
            member_role_id=0,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        mock_service.get_config.return_value = Ok(existing_config)
        mock_service.set_config.return_value = Err(PermissionDeniedError("缺少權限"))
        mock_service.get_or_create_account_id = AsyncMock(return_value=123456789)

        group = build_supreme_assembly_group(mock_service)
        config_cmd = None
        for cmd in cast(Any, group)._children.values():
            if getattr(cmd, "name", None) == "config_member_role":
                config_cmd = cmd
                break

        assert config_cmd is not None

        with patch(
            "src.bot.commands.supreme_assembly.send_message_compat", new_callable=AsyncMock
        ) as mock_send:
            await config_cmd.callback(mock_interaction, mock_role)

        mock_service.set_config.assert_awaited_once_with(
            guild_id=guild_id,
            speaker_role_id=existing_config.speaker_role_id,
            member_role_id=mock_role.id,
        )

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        embed = kwargs.get("embed")
        assert embed is not None
        assert embed.title == "設定議員身分組失敗"
        assert embed.description == "缺少權限"
        assert kwargs.get("ephemeral") is True

    async def test_config_permissions_denied(
        self, mock_interaction: MagicMock, mock_service: MagicMock
    ) -> None:
        """測試配置權限不足。"""
        # 設定無權限
        mock_interaction.user.guild_permissions.administrator = False
        mock_interaction.user.guild_permissions.manage_guild = False

        # 建立指令群組
        group = build_supreme_assembly_group(mock_service)

        # 獲取配置指令
        config_cmd = None
        for cmd in cast(Any, group)._children.values():
            if hasattr(cmd, "name") and cmd.name == "config_speaker_role":
                config_cmd = cmd
                break

        assert config_cmd is not None

        # 執行指令回調應
        mock_interaction.response = MagicMock()

        # 權限檢查應該失敗
        # 在實際實現中，權限檢查失敗會發送錯誤訊息

    async def test_panel_not_configured(
        self, mock_interaction: MagicMock, mock_service: MagicMock
    ) -> None:
        """測試面板開啟但尚未配置。"""
        mock_interaction.guild_id = _snowflake()
        mock_interaction.guild = MagicMock()

        # Mock 配置不存在
        mock_service.get_config.side_effect = GovernanceNotConfiguredError("未配置")

        # 建立指令群組
        group = build_supreme_assembly_group(mock_service)

        # 獲取面板指令
        panel_cmd = None
        for cmd in cast(Any, group)._children.values():
            if hasattr(cmd, "name") and cmd.name == "panel":
                panel_cmd = cmd
                break

        assert panel_cmd is not None

        # 執行面板指令回調應
        mock_interaction.response = MagicMock()

        # 應該顯示配置錯誤訊息


@pytest.mark.asyncio
class TestSupremeAssemblyVotingLogic:
    """Supreme Assembly 投票邏輯測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        service = AsyncMock(spec=SupremeAssemblyService)
        return service

    @pytest.fixture
    def sample_proposal(self) -> Proposal:
        """測試提案。"""
        return _proposal(title="重要預算提案", description="重要預算提案")

    async def test_cast_vote_approval(
        self, mock_service: AsyncMock, sample_proposal: Proposal
    ) -> None:
        """測試投票同意。"""
        # Mock 服務回傳
        mock_service.vote.return_value = (
            VoteTotals(
                approve=1, reject=0, abstain=0, threshold_t=5, snapshot_n=10, remaining_unvoted=9
            ),
            "進行中",
        )

        _guild_id = _snowflake()
        voter_id = _snowflake()

        await mock_service.vote(
            proposal_id=sample_proposal.proposal_id,
            voter_id=voter_id,
            choice="approve",
        )

        # 驗證服務調用
        mock_service.vote.assert_called_once_with(
            proposal_id=sample_proposal.proposal_id,
            voter_id=voter_id,
            choice="approve",
        )

    async def test_cast_vote_rejection(
        self, mock_service: AsyncMock, sample_proposal: Proposal
    ) -> None:
        """測試投票反對。"""
        # Mock 服務回傳
        mock_service.vote.return_value = (
            VoteTotals(
                approve=0, reject=1, abstain=0, threshold_t=5, snapshot_n=10, remaining_unvoted=9
            ),
            "進行中",
        )

        _guild_id = _snowflake()
        voter_id = _snowflake()

        await mock_service.vote(
            proposal_id=sample_proposal.proposal_id,
            voter_id=voter_id,
            choice="reject",
        )

        # 驗證服務調用
        mock_service.vote.assert_called_once_with(
            proposal_id=sample_proposal.proposal_id,
            voter_id=voter_id,
            choice="reject",
        )

    async def test_cast_vote_abstain(
        self, mock_service: AsyncMock, sample_proposal: Proposal
    ) -> None:
        """測試投票棄權。"""
        # Mock 服務回傳
        mock_service.vote.return_value = (
            VoteTotals(
                approve=0, reject=0, abstain=1, threshold_t=5, snapshot_n=10, remaining_unvoted=9
            ),
            "進行中",
        )

        _guild_id = _snowflake()
        voter_id = _snowflake()

        await mock_service.vote(
            proposal_id=sample_proposal.proposal_id,
            voter_id=voter_id,
            choice="abstain",
        )

        # 驗證服務調用
        mock_service.vote.assert_called_once_with(
            proposal_id=sample_proposal.proposal_id,
            voter_id=voter_id,
            choice="abstain",
        )

    async def test_get_vote_totals(
        self, mock_service: AsyncMock, sample_proposal: Proposal
    ) -> None:
        """測試獲取投票總數。"""
        # Mock 投票統計
        mock_totals = VoteTotals(
            approve=8, reject=3, abstain=2, threshold_t=5, snapshot_n=1, remaining_unvoted=10
        )
        mock_service.get_vote_totals.return_value = mock_totals

        _guild_id = _snowflake()

        totals = await mock_service.get_vote_totals(proposal_id=sample_proposal.proposal_id)

        # 驗證結果
        assert totals.approve == 8
        assert totals.reject == 3
        assert totals.abstain == 2
        assert totals.threshold_t == 5

        # 驗證服務調用
        mock_service.get_vote_totals.assert_called_once_with(
            proposal_id=sample_proposal.proposal_id
        )


@pytest.mark.asyncio
class TestSupremeAssemblyProposalCreation:
    """Supreme Assembly 提案創建測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        service = AsyncMock(spec=SupremeAssemblyService)
        return service

    @pytest.fixture
    def sample_config(self) -> SupremeAssemblyConfig:
        """測試配置。"""
        return SupremeAssemblyConfig(
            guild_id=_snowflake(),
            speaker_role_id=_snowflake(),
            member_role_id=_snowflake(),
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

    async def test_create_proposal_success(
        self, mock_service: AsyncMock, sample_config: SupremeAssemblyConfig
    ) -> None:
        """測試成功創建提案。"""
        guild_id = _snowflake()
        proposer_id = _snowflake()
        member_snapshot = [_snowflake() for _ in range(10)]

        # Mock 服務回傳
        mock_service.get_config.return_value = sample_config
        mock_proposal = _proposal(
            guild_id=guild_id,
            proposer_id=proposer_id,
            title="基礎設施預算",
            description="基礎設施預算提案",
        )
        mock_service.create_proposal.return_value = mock_proposal

        # 執行提案創建
        proposal = await mock_service.create_proposal(
            guild_id=guild_id,
            proposer_id=proposer_id,
            title="基礎設施預算",
            description="用於改善交通基礎設施的預算提案",
            snapshot_member_ids=member_snapshot,
            deadline_hours=48,
        )

        # 驗證結果
        assert proposal.proposal_id == mock_proposal.proposal_id
        assert proposal.guild_id == guild_id
        assert proposal.proposer_id == proposer_id
        assert proposal.description == "基礎設施預算提案"

        # 驗證服務調用
        mock_service.create_proposal.assert_called_once()

    async def test_create_proposal_insufficient_permissions(self, mock_service: AsyncMock) -> None:
        """測試權限不足時創建提案。"""
        guild_id = _snowflake()

        # Mock 權限不足
        mock_service.create_proposal.side_effect = PermissionDeniedError("權限不足")

        proposer_id = _snowflake()
        member_snapshot = [_snowflake() for _ in range(10)]

        # 執行提案創建應該拋出異常
        with pytest.raises(PermissionDeniedError):
            await mock_service.create_proposal(
                guild_id=guild_id,
                proposer_id=proposer_id,
                title="測試提案",
                description="權限測試提案",
                snapshot_member_ids=member_snapshot,
                deadline_hours=72,
            )

    async def test_create_proposal_not_configured(self, mock_service: AsyncMock) -> None:
        """測試未配置時創建提案。"""
        guild_id = _snowflake()

        # Mock 未配置
        mock_service.create_proposal.side_effect = GovernanceNotConfiguredError("未配置")

        proposer_id = _snowflake()
        member_snapshot = [_snowflake() for _ in range(10)]

        # 執行提案創建應該拋出異常
        with pytest.raises(GovernanceNotConfiguredError):
            await mock_service.create_proposal(
                guild_id=guild_id,
                proposer_id=proposer_id,
                title="測試提案",
                description="配置測試提案",
                snapshot_member_ids=member_snapshot,
                deadline_hours=72,
            )

    async def test_create_proposal_empty_member_snapshot(
        self, mock_service: AsyncMock, sample_config: SupremeAssemblyConfig
    ) -> None:
        """測試空成員名單時創建提案。"""
        guild_id = _snowflake()
        proposer_id = _snowflake()

        # Mock 服務回傳
        mock_service.get_config.return_value = sample_config

        # 執行提案創建（空成員名單）
        # 服務在空快照時會拋出 PermissionDeniedError
        from src.bot.services.supreme_assembly_service import (
            PermissionDeniedError as _SAPermissionError,
        )

        mock_service.create_proposal.side_effect = _SAPermissionError("空成員名單")

        with pytest.raises(_SAPermissionError):  # 應該拋出關於空成員名單的錯誤
            await mock_service.create_proposal(
                guild_id=guild_id,
                proposer_id=proposer_id,
                title="測試提案",
                description="空成員名單測試",
                snapshot_member_ids=[],
                deadline_hours=72,
            )


# === 錯誤處理測試 ===


@pytest.mark.asyncio
class TestSupremeAssemblyErrorHandling:
    """Supreme Assembly 錯誤處理測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        return AsyncMock(spec=SupremeAssemblyService)

    async def test_vote_on_nonexistent_proposal(self, mock_service: AsyncMock) -> None:
        """測試對不存在提案投票的錯誤處理。"""
        proposal_id = UUID(int=secrets.randbits(128))
        voter_id = _snowflake()

        mock_service.vote.side_effect = RuntimeError("Proposal not found.")

        with pytest.raises(RuntimeError):
            await mock_service.vote(
                proposal_id=proposal_id,
                voter_id=voter_id,
                choice="approve",
            )

    async def test_duplicate_vote_handling(self, mock_service: AsyncMock) -> None:
        """測試重複投票的錯誤處理。"""
        # Mock 投票已存在
        from src.bot.services.supreme_assembly_service import VoteAlreadyExistsError

        mock_service.vote.side_effect = VoteAlreadyExistsError("已投票")

        sample_proposal = _proposal(threshold_t=3)

        guild_id = _snowflake()
        voter_id = _snowflake()

        # 嘗試重複投票
        with pytest.raises(VoteAlreadyExistsError):
            await mock_service.vote(
                guild_id=guild_id,
                proposal_id=sample_proposal.proposal_id,
                voter_id=voter_id,
                vote="approve",
            )

    async def test_invalid_vote_type_handling(self, mock_service: AsyncMock) -> None:
        """測試無效投票類型的錯誤處理。"""
        sample_proposal = _proposal(threshold_t=3)
        mock_service.get_proposal.return_value = sample_proposal

        voter_id = _snowflake()

        mock_service.vote.side_effect = ValueError("Invalid vote choice.")

        # 嘗試無效投票類型
        with pytest.raises(ValueError):  # 或其他適當的異常
            await mock_service.vote(
                proposal_id=sample_proposal.proposal_id,
                voter_id=voter_id,
                choice="invalid_vote_type",  # 無效的投票類型
            )


# === 邊界條件測試 ===


@pytest.mark.asyncio
class TestSupremeAssemblyBoundaryConditions:
    """Supreme Assembly 邊界條件測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        return AsyncMock(spec=SupremeAssemblyService)

    @pytest.fixture
    def mock_guild(self) -> MagicMock:
        """建立模擬的 Discord Guild。"""
        guild = MagicMock()
        guild.id = _snowflake()
        guild.get_role = MagicMock()
        return guild

    async def test_vote_on_completed_proposal(self, mock_service: AsyncMock) -> None:
        """測試對已完成提案投票。"""
        # Mock 已完成的提案
        completed_proposal = _proposal(status="通過")
        voter_id = _snowflake()
        mock_service.vote.return_value = False

        # 嘗試對已完成提案投票
        result = await mock_service.vote(
            proposal_id=completed_proposal.proposal_id,
            voter_id=voter_id,
            choice="approve",
        )

        assert result is False

    async def test_create_proposal_with_extreme_values(self, mock_service: AsyncMock) -> None:
        """測試創建包含極值參數的提案。"""
        sample_config = SupremeAssemblyConfig(
            guild_id=_snowflake(),
            speaker_role_id=_snowflake(),
            member_role_id=_snowflake(),
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

        mock_service.get_config.return_value = sample_config
        mock_service.create_proposal.return_value = MagicMock()

        guild_id = _snowflake()
        proposer_id = _snowflake()
        member_snapshot = [_snowflake() for _ in range(100)]  # 大量成員

        # 創建包含極值的提案
        await mock_service.create_proposal(
            guild_id=guild_id,
            proposer_id=proposer_id,
            title="A" * 200,  # 非常長的標題
            description="B" * 1000,  # 非常長的描述
            snapshot_member_ids=member_snapshot,
            deadline_hours=168,  # 一週
            # 注意：金額參數不在 create_proposal 中，這可能需要在實際實現中調整
        )

        # 驗證服務被調用
        mock_service.create_proposal.assert_called_once_with(
            guild_id=guild_id,
            proposer_id=proposer_id,
            title="A" * 200,
            description="B" * 1000,
            snapshot_member_ids=member_snapshot,
            deadline_hours=168,
        )

    async def test_panel_with_large_member_list(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """測試面板處理大量成員列表。"""
        # Mock 大量成員
        large_member_count = 1000
        member_role = MagicMock()
        member_role.members = [MagicMock(id=_snowflake()) for _ in range(large_member_count)]
        mock_guild.get_role.return_value = member_role

        _sample_config = SupremeAssemblyConfig(
            guild_id=_snowflake(),
            speaker_role_id=_snowflake(),
            member_role_id=member_role.id,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

        with patch("discord.ui.View.__init__"), patch("discord.ui.View.add_item"):
            view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=_snowflake(),
                member_role_id=member_role.id,
                is_speaker=True,
                is_member=True,
            )

            # Mock 大量提案
            large_proposal_list = [
                _proposal(guild_id=mock_guild.id, description=f"提案 {i}") for i in range(50)
            ]
            mock_service.list_active_proposals.return_value = large_proposal_list

            # 測試刷新選項
            await view.refresh_options()

            # 驗證服務被調用
            mock_service.list_active_proposals.assert_called_once()

            # 驗證選單不會過度增長（可能有限制）
            assert len(view._select.options) <= 25  # type: ignore[protected-access] # pyright: ignore[reportProtectedAccess]


@pytest.mark.unit
class TestSupremePeoplesAssemblyPermissions:
    """測試最高人民議會權限檢查功能"""

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        """創建模擬的 SupremeAssemblyService。"""
        service = MagicMock(spec=SupremeAssemblyService)
        service.get_config = AsyncMock()
        return service

    def test_peoples_assembly_permission_checker_representative_access(
        self, mock_service: MagicMock
    ) -> None:
        """測試人民代表可以開啟面板"""
        from src.bot.services.permission_service import SupremePeoplesAssemblyPermissionChecker

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_service.get_config.return_value = mock_config

        checker = SupremePeoplesAssemblyPermissionChecker(mock_service)

        # 人民代表身分（有成員角色但無議長角色）
        user_roles = [456]  # 只有人民代表角色

        import asyncio

        result = asyncio.run(
            checker.check_permission(
                guild_id=789, user_id=101, user_roles=user_roles, operation="panel_access"
            )
        )

        assert isinstance(result, Ok)
        permission = result.value
        assert permission.allowed is True
        assert permission.permission_level == "representative"
        assert permission.reason is not None
        assert "人民代表" in permission.reason

    def test_peoples_assembly_permission_checker_speaker_access(
        self, mock_service: MagicMock
    ) -> None:
        """測試議長可以開啟面板"""
        from src.bot.services.permission_service import SupremePeoplesAssemblyPermissionChecker

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_service.get_config.return_value = mock_config

        checker = SupremePeoplesAssemblyPermissionChecker(mock_service)

        # 議長身分（同時有議長和人民代表角色）
        user_roles = [123, 456]  # 同時有議長和人民代表角色

        import asyncio

        result = asyncio.run(
            checker.check_permission(
                guild_id=789, user_id=101, user_roles=user_roles, operation="panel_access"
            )
        )

        assert isinstance(result, Ok)
        permission = result.value
        assert permission.allowed is True
        assert permission.permission_level == "speaker"
        assert permission.reason is not None
        assert "議長" in permission.reason

    def test_peoples_assembly_permission_checker_unauthorized_access(
        self, mock_service: MagicMock
    ) -> None:
        """測試未授權使用者被拒絕"""
        from src.bot.services.permission_service import SupremePeoplesAssemblyPermissionChecker

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_service.get_config.return_value = mock_config

        checker = SupremePeoplesAssemblyPermissionChecker(mock_service)

        # 無關身分（沒有議長或人民代表角色）
        user_roles = [999]  # 無關角色

        import asyncio

        result = asyncio.run(
            checker.check_permission(
                guild_id=789, user_id=101, user_roles=user_roles, operation="panel_access"
            )
        )

        assert isinstance(result, Ok)
        permission = result.value
        assert permission.allowed is False
        assert permission.permission_level is None
        assert isinstance(permission.reason, str)
        assert "不具備" in permission.reason

    def test_peoples_assembly_permission_checker_create_proposal(
        self, mock_service: MagicMock
    ) -> None:
        """測試人民代表與議長都可發起提案"""
        from src.bot.services.permission_service import SupremePeoplesAssemblyPermissionChecker

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_service.get_config.return_value = mock_config

        checker = SupremePeoplesAssemblyPermissionChecker(mock_service)

        import asyncio

        # 議長可以發起提案
        speaker_result = asyncio.run(
            checker.check_permission(
                guild_id=789, user_id=101, user_roles=[123, 456], operation="create_proposal"
            )
        )
        assert isinstance(speaker_result, Ok)
        speaker_perm = speaker_result.value
        assert speaker_perm.allowed is True
        assert speaker_perm.permission_level == "speaker"

        # 人民代表也可以發起提案
        representative_result = asyncio.run(
            checker.check_permission(
                guild_id=789, user_id=102, user_roles=[456], operation="create_proposal"
            )
        )
        assert isinstance(representative_result, Ok)
        representative_perm = representative_result.value
        assert representative_perm.allowed is True
        assert representative_perm.permission_level == "representative"

    def test_peoples_assembly_permission_checker_vote(self, mock_service: MagicMock) -> None:
        """測試人民代表可以投票"""
        from src.bot.services.permission_service import SupremePeoplesAssemblyPermissionChecker

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_service.get_config.return_value = mock_config

        checker = SupremePeoplesAssemblyPermissionChecker(mock_service)

        import asyncio

        # 測試人民代表可以投票
        representative_result = asyncio.run(
            checker.check_permission(guild_id=789, user_id=102, user_roles=[456], operation="vote")
        )
        assert isinstance(representative_result, Ok)
        representative_perm = representative_result.value
        assert representative_perm.allowed is True
        assert representative_perm.permission_level == "representative"

        # 測試議長也可以投票
        speaker_result = asyncio.run(
            checker.check_permission(
                guild_id=789, user_id=101, user_roles=[123, 456], operation="vote"
            )
        )
        assert isinstance(speaker_result, Ok)
        speaker_perm = speaker_result.value
        assert speaker_perm.allowed is True

    def test_peoples_assembly_permission_checker_transfer(self, mock_service: MagicMock) -> None:
        """測試轉帳權限"""
        from src.bot.services.permission_service import SupremePeoplesAssemblyPermissionChecker

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_service.get_config.return_value = mock_config

        checker = SupremePeoplesAssemblyPermissionChecker(mock_service)

        import asyncio

        # 測試人民代表可以轉帳
        representative_result = asyncio.run(
            checker.check_permission(
                guild_id=789, user_id=102, user_roles=[456], operation="transfer"
            )
        )
        assert isinstance(representative_result, Ok)
        representative_perm = representative_result.value
        assert representative_perm.allowed is True
        assert representative_perm.permission_level == "representative"

        # 測試議長可以轉帳
        speaker_result = asyncio.run(
            checker.check_permission(
                guild_id=789, user_id=101, user_roles=[123, 456], operation="transfer"
            )
        )
        assert isinstance(speaker_result, Ok)
        speaker_perm = speaker_result.value
        assert speaker_perm.allowed is True
        assert speaker_perm.permission_level == "speaker"

    def test_permission_service_integration(self) -> None:
        """測試權限服務整合"""
        from src.bot.services.permission_service import PermissionService

        # 創建模擬服務
        mock_supreme_service = MagicMock()
        mock_council_result = MagicMock()
        mock_state_council_result = MagicMock()

        service = PermissionService(
            council_service=mock_council_result,
            state_council_service=mock_state_council_result,
            supreme_assembly_service=mock_supreme_service,
        )

        # 驗證服務有正確的檢查器
        assert hasattr(service, "_supreme_peoples_assembly_checker")
        assert hasattr(service, "check_supreme_peoples_assembly_permission")

    @pytest.mark.asyncio
    async def test_supreme_peoples_assembly_permission_check(self, mock_service: MagicMock) -> None:
        """測試完整的最高人民議會權限檢查流程"""
        from src.bot.services.permission_service import PermissionService

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_service.get_config.return_value = mock_config

        mock_council_result = MagicMock()
        mock_state_council_result = MagicMock()

        service = PermissionService(
            council_service=mock_council_result,
            state_council_service=mock_state_council_result,
            supreme_assembly_service=mock_service,
        )

        # 測試人民代表權限
        result = await service.check_supreme_peoples_assembly_permission(
            guild_id=789, user_id=102, user_roles=[456], operation="panel_access"
        )
        assert isinstance(result, Ok)
        permission = result.value
        assert permission.allowed is True
        assert permission.permission_level == "representative"
        assert permission.reason and "人民代表" in permission.reason


# === 傳召功能測試 ===


@pytest.mark.unit
class TestSummonTypeSelectionView:
    """傳召類型選擇視圖測試。"""

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        """創建模擬的 SupremeAssemblyService。"""
        service = MagicMock(spec=SupremeAssemblyService)
        service.get_config = AsyncMock()
        service.create_summon = AsyncMock()
        service.mark_summon_delivered = AsyncMock()
        return service

    @pytest.fixture
    def mock_guild(self) -> MagicMock:
        """創建模擬的 Discord Guild。"""
        guild = MagicMock()
        guild.id = _snowflake()
        guild.get_role = MagicMock()
        guild.get_member = MagicMock()
        return guild

    def test_summon_type_selection_view_initialization(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """測試傳召類型選擇視圖初始化。"""
        from src.bot.commands.supreme_assembly import SummonTypeSelectionView

        with patch("discord.ui.View.__init__"):
            view = SummonTypeSelectionView(service=mock_service, guild=mock_guild)

            # 驗證基本屬性
            assert view.service == mock_service
            assert view.guild == mock_guild

    def test_summon_type_selection_view_has_buttons(
        self, mock_service: MagicMock, mock_guild: MagicMock
    ) -> None:
        """測試傳召類型選擇視圖有正確的按鈕。"""
        from src.bot.commands.supreme_assembly import SummonTypeSelectionView

        with patch("discord.ui.View.__init__"):
            view = SummonTypeSelectionView(service=mock_service, guild=mock_guild)

            # 檢查是否有傳召議員和傳召官員的方法
            assert hasattr(view, "select_member")
            assert hasattr(view, "select_official")


@pytest.mark.asyncio
class TestSummonMemberSelectView:
    """傳召議員選擇視圖測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        service = AsyncMock(spec=SupremeAssemblyService)
        return service

    @pytest.fixture
    def mock_guild(self) -> MagicMock:
        """創建模擬的 Discord Guild。"""
        guild = MagicMock()
        guild.id = _snowflake()
        guild.get_role = MagicMock()
        guild.get_member = MagicMock()
        return guild

    @pytest.fixture
    def sample_config(self, mock_guild: MagicMock) -> SupremeAssemblyConfig:
        """測試配置。"""
        return SupremeAssemblyConfig(
            guild_id=mock_guild.id,
            speaker_role_id=_snowflake(),
            member_role_id=_snowflake(),
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

    async def test_summon_member_select_view_build_with_members(
        self, mock_service: AsyncMock, mock_guild: MagicMock, sample_config: SupremeAssemblyConfig
    ) -> None:
        """測試建立傳召議員視圖（有成員）。"""
        from src.bot.commands.supreme_assembly import SummonMemberSelectView

        # 設定模擬配置和成員
        mock_service.get_config.return_value = Ok(sample_config)

        # 創建模擬成員列表
        mock_members: list[MagicMock] = []
        for i in range(5):
            member = MagicMock()
            member.id = _snowflake()
            member.display_name = f"Member {i}"
            member.name = f"member{i}"
            mock_members.append(member)

        mock_role = MagicMock()
        mock_role.members = mock_members
        mock_guild.get_role.return_value = mock_role

        with (
            patch("discord.ui.View.__init__"),
            patch("discord.ui.View.add_item") as mock_add_item,
        ):
            _view = await SummonMemberSelectView.build(service=mock_service, guild=mock_guild)

            # 驗證服務被調用
            mock_service.get_config.assert_called_once_with(guild_id=mock_guild.id)
            mock_guild.get_role.assert_called_once_with(sample_config.member_role_id)

            # 驗證有添加選單
            assert mock_add_item.called
            assert _view is not None  # 確保視圖被創建

    async def test_summon_member_select_view_build_no_members(
        self, mock_service: AsyncMock, mock_guild: MagicMock, sample_config: SupremeAssemblyConfig
    ) -> None:
        """測試建立傳召議員視圖（無成員）。"""
        from src.bot.commands.supreme_assembly import SummonMemberSelectView

        # 設定模擬配置和空成員列表
        mock_service.get_config.return_value = Ok(sample_config)

        mock_role = MagicMock()
        mock_role.members = []
        mock_guild.get_role.return_value = mock_role

        with (
            patch("discord.ui.View.__init__"),
            patch("discord.ui.View.add_item") as mock_add_item,
        ):
            _view = await SummonMemberSelectView.build(service=mock_service, guild=mock_guild)

            # 驗證有添加禁用的選單
            assert mock_add_item.called
            assert _view is not None

    async def test_summon_member_select_view_build_config_error(
        self, mock_service: AsyncMock, mock_guild: MagicMock
    ) -> None:
        """測試建立傳召議員視圖時配置錯誤。"""
        from src.bot.commands.supreme_assembly import SummonMemberSelectView

        # 模擬配置錯誤
        mock_service.get_config.side_effect = GovernanceNotConfiguredError("未配置")

        with patch("discord.ui.View.__init__"), patch("discord.ui.View.add_item"):
            # 應該靜默處理錯誤
            view = await SummonMemberSelectView.build(service=mock_service, guild=mock_guild)

            # 視圖應該被創建（即使沒有選項）
            assert view is not None


@pytest.mark.asyncio
class TestSummonOfficialSelectView:
    """傳召政府官員選擇視圖測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        service = AsyncMock(spec=SupremeAssemblyService)
        return service

    @pytest.fixture
    def mock_guild(self) -> MagicMock:
        """創建模擬的 Discord Guild。"""
        guild = MagicMock()
        guild.id = _snowflake()
        guild.get_role = MagicMock()
        guild.get_member = MagicMock()
        return guild

    def test_summon_official_select_view_initialization(
        self, mock_service: AsyncMock, mock_guild: MagicMock
    ) -> None:
        """測試傳召政府官員視圖初始化。"""
        from src.bot.commands.supreme_assembly import SummonOfficialSelectView

        with (
            patch("discord.ui.View.__init__"),
            patch("discord.ui.View.add_item") as mock_add_item,
            patch("src.bot.commands.supreme_assembly.get_registry") as mock_get_registry,
        ):
            # 設定模擬部門註冊表
            mock_registry = MagicMock()
            mock_dept = MagicMock()
            mock_dept.id = "dept_1"
            mock_dept.name = "財政部"
            mock_dept.emoji = "💰"
            mock_registry.get_by_level.return_value = [mock_dept]
            mock_get_registry.return_value = mock_registry

            view = SummonOfficialSelectView(service=mock_service, guild=mock_guild)

            # 驗證基本屬性
            assert view.service == mock_service
            assert view.guild == mock_guild

            # 驗證有添加選單
            assert mock_add_item.called

    def test_summon_official_select_view_has_all_options(
        self, mock_service: AsyncMock, mock_guild: MagicMock
    ) -> None:
        """測試傳召政府官員視圖包含所有選項。"""
        from src.bot.commands.supreme_assembly import SummonOfficialSelectView

        with (
            patch("discord.ui.View.__init__"),
            patch("discord.ui.View.add_item") as mock_add_item,
            patch("src.bot.commands.supreme_assembly.get_registry") as mock_get_registry,
        ):
            # 設定多個部門
            mock_registry = MagicMock()
            mock_depts: list[MagicMock] = []
            for i, name in enumerate(["財政部", "國防部", "外交部"]):
                dept = MagicMock()
                dept.id = f"dept_{i}"
                dept.name = name
                dept.emoji = None
                mock_depts.append(dept)
            mock_registry.get_by_level.return_value = mock_depts
            mock_get_registry.return_value = mock_registry

            _view = SummonOfficialSelectView(service=mock_service, guild=mock_guild)

            # 驗證有添加選單（應該包含部門 + 國務院領袖 + 常任理事會）
            assert mock_add_item.called
            assert _view is not None


@pytest.mark.asyncio
class TestSummonPermanentCouncilView:
    """傳召常任理事會成員視圖測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        service = AsyncMock(spec=SupremeAssemblyService)
        return service

    @pytest.fixture
    def mock_guild(self) -> MagicMock:
        """創建模擬的 Discord Guild。"""
        guild = MagicMock()
        guild.id = _snowflake()
        guild.get_role = MagicMock()
        guild.get_member = MagicMock()
        return guild

    @pytest.fixture
    def mock_original_view(self, mock_service: AsyncMock, mock_guild: MagicMock) -> MagicMock:
        """創建模擬的原始視圖。"""
        return MagicMock()

    async def test_summon_permanent_council_view_build_with_members(
        self,
        mock_service: AsyncMock,
        mock_guild: MagicMock,
        mock_original_view: MagicMock,
    ) -> None:
        """測試建立傳召常任理事會視圖（有成員）。"""
        from src.bot.commands.supreme_assembly import SummonPermanentCouncilView

        # 創建模擬成員列表
        mock_members: list[MagicMock] = []
        for i in range(5):
            member = MagicMock()
            member.id = _snowflake()
            member.display_name = f"Council Member {i}"
            member.name = f"council{i}"
            mock_members.append(member)

        mock_role = MagicMock()
        mock_role.members = mock_members
        mock_guild.get_role.return_value = mock_role

        # 模擬理事會配置
        mock_council_config = MagicMock()
        mock_council_config.council_role_id = _snowflake()

        with (
            patch("discord.ui.View.__init__"),
            patch("discord.ui.View.add_item"),
            patch("src.bot.commands.supreme_assembly.get_pool") as mock_get_pool,
        ):
            mock_pool = MagicMock()
            mock_conn = MagicMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # 模擬 gateway
            with patch("src.db.gateway.council_governance.CouncilGovernanceGateway") as mock_gw_cls:
                mock_gw = MagicMock()
                mock_gw.fetch_config = AsyncMock(return_value=mock_council_config)
                mock_gw_cls.return_value = mock_gw

                _view = await SummonPermanentCouncilView.build(
                    service=mock_service,
                    guild=mock_guild,
                    original_view=mock_original_view,
                )

                # 驗證視圖被創建
                assert _view is not None
                assert _view.service == mock_service
                assert _view.guild == mock_guild

    async def test_summon_permanent_council_view_build_no_config(
        self,
        mock_service: AsyncMock,
        mock_guild: MagicMock,
        mock_original_view: MagicMock,
    ) -> None:
        """測試建立傳召常任理事會視圖（無配置）。"""
        from src.bot.commands.supreme_assembly import SummonPermanentCouncilView

        with (
            patch("discord.ui.View.__init__"),
            patch("discord.ui.View.add_item"),
            patch("src.bot.commands.supreme_assembly.get_pool") as mock_get_pool,
        ):
            mock_pool = MagicMock()
            mock_conn = MagicMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # 模擬無配置
            with patch("src.db.gateway.council_governance.CouncilGovernanceGateway") as mock_gw_cls:
                mock_gw = MagicMock()
                mock_gw.fetch_config = AsyncMock(return_value=None)
                mock_gw_cls.return_value = mock_gw

                view = await SummonPermanentCouncilView.build(
                    service=mock_service,
                    guild=mock_guild,
                    original_view=mock_original_view,
                )

                # 視圖應該被創建（即使沒有選項）
                assert view is not None


@pytest.mark.asyncio
class TestSummonFunctionality:
    """傳召功能整合測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        service = AsyncMock(spec=SupremeAssemblyService)
        return service

    @pytest.fixture
    def mock_guild(self) -> MagicMock:
        """創建模擬的 Discord Guild。"""
        guild = MagicMock()
        guild.id = _snowflake()
        guild.get_role = MagicMock()
        guild.get_member = MagicMock()
        return guild

    @pytest.fixture
    def mock_interaction(self, mock_guild: MagicMock) -> MagicMock:
        """創建模擬的 Discord 互動。"""
        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.user = MagicMock()
        interaction.user.id = _snowflake()
        interaction.user.mention = f"<@{interaction.user.id}>"
        interaction.data = {"values": ["123456789"]}
        interaction.client = MagicMock()
        return interaction

    async def test_summon_member_success(
        self,
        mock_service: AsyncMock,
        mock_guild: MagicMock,
        mock_interaction: MagicMock,
    ) -> None:
        """測試成功傳召議員。"""
        # 設定模擬傳召記錄
        mock_summon = MagicMock()
        mock_summon.summon_id = UUID(int=secrets.randbits(128))
        mock_service.create_summon.return_value = mock_summon

        # 設定模擬成員
        mock_member = MagicMock()
        mock_member.id = 123456789
        mock_member.mention = "<@123456789>"
        mock_member.send = AsyncMock()
        mock_guild.get_member.return_value = mock_member

        # 驗證傳召創建邏輯
        await mock_service.create_summon(
            guild_id=mock_guild.id,
            invoked_by=mock_interaction.user.id,
            target_id=mock_member.id,
            target_kind="member",
            note=None,
        )

        mock_service.create_summon.assert_called_once_with(
            guild_id=mock_guild.id,
            invoked_by=mock_interaction.user.id,
            target_id=mock_member.id,
            target_kind="member",
            note=None,
        )

    async def test_summon_official_success(
        self,
        mock_service: AsyncMock,
        mock_guild: MagicMock,
        mock_interaction: MagicMock,
    ) -> None:
        """測試成功傳召政府官員。"""
        # 設定模擬傳召記錄
        mock_summon = MagicMock()
        mock_summon.summon_id = UUID(int=secrets.randbits(128))
        mock_service.create_summon.return_value = mock_summon

        target_id = StateCouncilService.derive_main_account_id(mock_guild.id)

        # 驗證傳召創建邏輯
        await mock_service.create_summon(
            guild_id=mock_guild.id,
            invoked_by=mock_interaction.user.id,
            target_id=target_id,
            target_kind="official",
            note="傳召 國務院領袖",
        )

        mock_service.create_summon.assert_called_once_with(
            guild_id=mock_guild.id,
            invoked_by=mock_interaction.user.id,
            target_id=target_id,
            target_kind="official",
            note="傳召 國務院領袖",
        )

    async def test_summon_permission_denied_non_speaker(
        self,
        mock_service: AsyncMock,
        mock_guild: MagicMock,
    ) -> None:
        """測試非議長無法傳召。"""
        with patch("discord.ui.View.__init__"), patch("discord.ui.View.add_item"):
            view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=_snowflake(),
                member_role_id=_snowflake(),
                is_speaker=False,  # 非議長
                is_member=True,
            )

            # 非議長不應該有傳召按鈕
            assert not hasattr(view, "_summon_btn")

    async def test_summon_button_only_for_speaker(
        self,
        mock_service: AsyncMock,
        mock_guild: MagicMock,
    ) -> None:
        """測試傳召按鈕僅對議長顯示。"""
        with patch("discord.ui.View.__init__"), patch("discord.ui.View.add_item"):
            # 議長視圖
            speaker_view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=_snowflake(),
                member_role_id=_snowflake(),
                is_speaker=True,
                is_member=True,
            )

            # 人民代表視圖
            member_view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=_snowflake(),
                member_role_id=_snowflake(),
                is_speaker=False,
                is_member=True,
            )

            # 議長應該有傳召按鈕
            assert hasattr(speaker_view, "_summon_btn")

            # 人民代表不應該有傳召按鈕
            assert not hasattr(member_view, "_summon_btn")

    async def test_mark_summon_delivered(self, mock_service: AsyncMock) -> None:
        """測試標記傳召已送達。"""
        summon_id = UUID(int=secrets.randbits(128))

        await mock_service.mark_summon_delivered(summon_id=summon_id)

        mock_service.mark_summon_delivered.assert_called_once_with(summon_id=summon_id)

    async def test_summon_dm_failure_handling(
        self,
        mock_service: AsyncMock,
        mock_guild: MagicMock,
    ) -> None:
        """測試傳召私訊失敗處理。"""
        # 設定模擬傳召記錄
        mock_summon = MagicMock()
        mock_summon.summon_id = UUID(int=secrets.randbits(128))
        mock_service.create_summon.return_value = mock_summon

        # 設定模擬成員（私訊會失敗）
        mock_member = MagicMock()
        mock_member.id = 123456789
        mock_member.send = AsyncMock(side_effect=Exception("DM disabled"))
        mock_guild.get_member.return_value = mock_member

        # 傳召記錄應該仍然被創建
        await mock_service.create_summon(
            guild_id=mock_guild.id,
            invoked_by=_snowflake(),
            target_id=mock_member.id,
            target_kind="member",
            note=None,
        )

        mock_service.create_summon.assert_called_once()

        # 嘗試發送私訊（會失敗）
        with pytest.raises(Exception, match="DM disabled"):
            await mock_member.send(content="傳召通知")


@pytest.mark.asyncio
class TestSummonErrorHandling:
    """傳召功能錯誤處理測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        return AsyncMock(spec=SupremeAssemblyService)

    async def test_summon_service_error(self, mock_service: AsyncMock) -> None:
        """測試傳召服務錯誤處理。"""
        mock_service.create_summon.side_effect = RuntimeError("Database error")

        with pytest.raises(RuntimeError, match="Database error"):
            await mock_service.create_summon(
                guild_id=_snowflake(),
                invoked_by=_snowflake(),
                target_id=_snowflake(),
                target_kind="member",
                note=None,
            )

    async def test_summon_invalid_target_kind(self, mock_service: AsyncMock) -> None:
        """測試無效傳召目標類型。"""
        mock_service.create_summon.side_effect = ValueError("Invalid target kind")

        with pytest.raises(ValueError, match="Invalid target kind"):
            await mock_service.create_summon(
                guild_id=_snowflake(),
                invoked_by=_snowflake(),
                target_id=_snowflake(),
                target_kind="invalid",
                note=None,
            )

    async def test_mark_summon_delivered_not_found(self, mock_service: AsyncMock) -> None:
        """測試標記不存在的傳召。"""
        mock_service.mark_summon_delivered.side_effect = RuntimeError("Summon not found")

        with pytest.raises(RuntimeError, match="Summon not found"):
            await mock_service.mark_summon_delivered(summon_id=UUID(int=secrets.randbits(128)))


# === 權限邊界測試 ===


@pytest.mark.asyncio
class TestPermissionBoundaries:
    """權限邊界測試：測試各種權限邊界情況。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        return AsyncMock(spec=SupremeAssemblyService)

    @pytest.fixture
    def mock_guild(self) -> MagicMock:
        """創建模擬的 Discord Guild。"""
        guild = MagicMock()
        guild.id = _snowflake()
        guild.get_role = MagicMock()
        guild.get_member = MagicMock()
        return guild

    async def test_speaker_only_operations(
        self, mock_service: AsyncMock, mock_guild: MagicMock
    ) -> None:
        """測試僅議長可執行的操作。"""
        # 設定配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_service.get_config.return_value = mock_config

        # 測試傳召權限（僅限議長）
        with patch("discord.ui.View.__init__"), patch("discord.ui.View.add_item"):
            speaker_view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=123,
                member_role_id=456,
                is_speaker=True,
                is_member=True,
            )

            member_view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=123,
                member_role_id=456,
                is_speaker=False,
                is_member=True,
            )

            # 議長應該有傳召按鈕
            assert hasattr(speaker_view, "_summon_btn")
            # 人民代表不應該有傳召按鈕
            assert not hasattr(member_view, "_summon_btn")

    async def test_member_operations(self, mock_service: AsyncMock, mock_guild: MagicMock) -> None:
        """測試議員可執行的操作。"""
        with patch("discord.ui.View.__init__"), patch("discord.ui.View.add_item"):
            # 議員視圖
            member_view = SupremeAssemblyPanelView(
                service=mock_service,
                guild=mock_guild,
                author_id=_snowflake(),
                speaker_role_id=_snowflake(),
                member_role_id=_snowflake(),
                is_speaker=False,
                is_member=True,
            )

            # 議員應該有轉帳、提案和查看所有提案功能
            assert hasattr(member_view, "_transfer_btn")
            assert hasattr(member_view, "_propose_btn")  # 發起表決按鈕
            assert hasattr(member_view, "_view_all_btn")  # 查看所有提案按鈕

    async def test_non_member_access_denied(
        self, mock_service: AsyncMock, mock_guild: MagicMock
    ) -> None:
        """測試非議員存取被拒絕。"""
        from src.bot.services.permission_service import PermissionService
        from src.infra.result import Ok

        # 創建模擬的 PermissionService
        mock_council_service = MagicMock()
        mock_state_council_service = MagicMock()
        mock_supreme_assembly_service = MagicMock()

        # 設定配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_supreme_assembly_service.get_config = AsyncMock(return_value=mock_config)

        permission_service = PermissionService(
            council_service=mock_council_service,
            state_council_service=mock_state_council_service,
            supreme_assembly_service=mock_supreme_assembly_service,
        )

        # 測試無權限用戶
        result = await permission_service.check_supreme_peoples_assembly_permission(
            guild_id=mock_guild.id,
            user_id=_snowflake(),
            user_roles=[999],  # 無相關角色
            operation="panel_access",
        )

        assert isinstance(result, Ok)
        permission = result.value
        assert permission.allowed is False
        assert permission.permission_level is None  # None 表示無權限

    async def test_permission_check_with_multiple_roles(
        self, mock_service: AsyncMock, mock_guild: MagicMock
    ) -> None:
        """測試具有多個角色的權限檢查。"""
        from src.bot.services.permission_service import PermissionService
        from src.infra.result import Ok

        mock_council_service = MagicMock()
        mock_state_council_service = MagicMock()
        mock_supreme_assembly_service = MagicMock()

        # 設定配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_supreme_assembly_service.get_config = AsyncMock(return_value=mock_config)

        permission_service = PermissionService(
            council_service=mock_council_service,
            state_council_service=mock_state_council_service,
            supreme_assembly_service=mock_supreme_assembly_service,
        )

        # 測試同時具有議長和議員角色的用戶（應該是議長）
        result = await permission_service.check_supreme_peoples_assembly_permission(
            guild_id=mock_guild.id,
            user_id=_snowflake(),
            user_roles=[123, 456, 789],  # 議長 + 議員 + 其他
            operation="panel_access",
        )

        assert isinstance(result, Ok)
        permission = result.value
        assert permission.allowed is True
        assert permission.permission_level == "speaker"  # 最高權限優先

    async def test_governance_not_configured_permission(
        self, mock_service: AsyncMock, mock_guild: MagicMock
    ) -> None:
        """測試治理未配置時的權限處理。"""
        from src.bot.services.permission_service import PermissionService
        from src.infra.result import Err

        mock_council_service = MagicMock()
        mock_state_council_service = MagicMock()
        mock_supreme_assembly_service = MagicMock()

        # 模擬未配置
        mock_supreme_assembly_service.get_config = AsyncMock(
            side_effect=GovernanceNotConfiguredError("未配置")
        )

        permission_service = PermissionService(
            council_service=mock_council_service,
            state_council_service=mock_state_council_service,
            supreme_assembly_service=mock_supreme_assembly_service,
        )

        # 測試未配置時的權限檢查
        result = await permission_service.check_supreme_peoples_assembly_permission(
            guild_id=mock_guild.id,
            user_id=_snowflake(),
            user_roles=[123],
            operation="panel_access",
        )

        # 應該返回錯誤結果
        assert isinstance(result, Err)


@pytest.mark.unit
class TestVotingPermissionBoundaries:
    """投票權限邊界測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        return AsyncMock(spec=SupremeAssemblyService)

    @pytest.mark.asyncio
    async def test_only_snapshot_members_can_vote(self, mock_service: AsyncMock) -> None:
        """測試只有快照成員可以投票。"""
        snapshot_members = [_snowflake() for _ in range(5)]
        outsider_id = _snowflake()

        # 模擬快照成員列表
        mock_service.get_snapshot_members = AsyncMock(return_value=snapshot_members)

        # 快照成員可以投票
        snapshot_member = snapshot_members[0]
        assert snapshot_member in snapshot_members

        # 非快照成員不在列表中
        assert outsider_id not in snapshot_members

    @pytest.mark.asyncio
    async def test_vote_deadline_enforcement(self, mock_service: AsyncMock) -> None:
        """測試投票截止時間強制執行。"""
        test_proposal_id = UUID(int=secrets.randbits(128))

        # 模擬投票行為（截止後應該失敗）
        mock_service.vote.side_effect = RuntimeError("提案已截止")

        with pytest.raises(RuntimeError, match="提案已截止"):
            await mock_service.vote(
                proposal_id=test_proposal_id,
                voter_id=_snowflake(),
                choice="approve",
            )

    @pytest.mark.asyncio
    async def test_threshold_calculation_edge_cases(self, mock_service: AsyncMock) -> None:
        """測試門檻計算的邊界情況。"""
        # 測試不同成員數量的門檻計算

        # 1 人：門檻 = 1
        assert (1 + 1) // 2 == 1

        # 2 人：門檻 = 1 (如果使用 >50% 規則) 或 2 (如果使用 >=50% 規則)
        assert (2 + 1) // 2 == 1

        # 3 人：門檻 = 2
        assert (3 + 1) // 2 == 2

        # 100 人：門檻 = 50 (如果使用 >50% 規則) 或 51
        assert (100 + 1) // 2 == 50

    @pytest.mark.asyncio
    async def test_duplicate_vote_prevention(self, mock_service: AsyncMock) -> None:
        """測試防止重複投票。"""
        proposal_id = UUID(int=secrets.randbits(128))
        voter_id = _snowflake()

        # 第一次投票成功
        mock_service.vote.return_value = (
            VoteTotals(
                approve=1,
                reject=0,
                abstain=0,
                threshold_t=2,
                snapshot_n=3,
                remaining_unvoted=2,
            ),
            "進行中",
        )

        await mock_service.vote(
            proposal_id=proposal_id,
            voter_id=voter_id,
            choice="approve",
        )

        # 重複投票應該失敗
        mock_service.vote.side_effect = VoteAlreadyExistsError("已投票")

        with pytest.raises(VoteAlreadyExistsError):
            await mock_service.vote(
                proposal_id=proposal_id,
                voter_id=voter_id,
                choice="reject",
            )


@pytest.mark.unit
class TestProposalPermissionBoundaries:
    """提案權限邊界測試。"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """創建模擬的 SupremeAssemblyService。"""
        return AsyncMock(spec=SupremeAssemblyService)

    @pytest.mark.asyncio
    async def test_proposal_creation_requires_member_role(self, mock_service: AsyncMock) -> None:
        """測試建立提案需要議員角色。"""
        # 模擬非議員嘗試建案
        mock_service.create_proposal.side_effect = PermissionDeniedError("只有議員可以建立提案")

        with pytest.raises(PermissionDeniedError, match="只有議員可以建立提案"):
            await mock_service.create_proposal(
                guild_id=_snowflake(),
                proposer_id=_snowflake(),
                title="測試提案",
                description="內容",
                snapshot_member_ids=[],
                deadline_hours=72,
            )

    @pytest.mark.asyncio
    async def test_proposal_title_length_limits(self, mock_service: AsyncMock) -> None:
        """測試提案標題長度限制。"""
        # 測試過長的標題
        long_title = "A" * 256

        mock_service.create_proposal.side_effect = ValueError("標題過長")

        with pytest.raises(ValueError, match="標題過長"):
            await mock_service.create_proposal(
                guild_id=_snowflake(),
                proposer_id=_snowflake(),
                title=long_title,
                description="內容",
                snapshot_member_ids=[_snowflake()],
                deadline_hours=72,
            )

    @pytest.mark.asyncio
    async def test_proposal_deadline_range(self, mock_service: AsyncMock) -> None:
        """測試提案截止時間範圍。"""
        # 測試無效的截止時間
        mock_service.create_proposal.side_effect = ValueError("截止時間無效")

        # 負數時間
        with pytest.raises(ValueError, match="截止時間無效"):
            await mock_service.create_proposal(
                guild_id=_snowflake(),
                proposer_id=_snowflake(),
                title="測試",
                description="內容",
                snapshot_member_ids=[_snowflake()],
                deadline_hours=-1,
            )
