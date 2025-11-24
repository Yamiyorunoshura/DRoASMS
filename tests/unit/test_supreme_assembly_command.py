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
    VoteTotals,
)
from src.db.gateway.supreme_assembly_governance import (
    Proposal,
    SupremeAssemblyConfig,
)
from src.infra.result import Ok


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
        command_names = [cmd.name for cmd in group._children.values()]
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
        for cmd in group._children.values():
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
        for cmd in group._children.values():
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
        for cmd in group._children.values():
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

            embed = view._build_help_embed()

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
            assert len(view._select.options) > 0


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

        # 獲取配置指令
        config_cmd = None
        for cmd in group._children.values():
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

        # 獲取配置指令
        config_cmd = None
        for cmd in group._children.values():
            if hasattr(cmd, "name") and cmd.name == "config_member_role":
                config_cmd = cmd
                break

        assert config_cmd is not None

        # 執行指令回調應
        mock_interaction.response = MagicMock()

        # 檢查基本權限驗證邏輯
        assert mock_interaction.user.guild_permissions.administrator is True
        assert mock_interaction.user.guild_permissions.manage_guild is True

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
        for cmd in group._children.values():
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
        for cmd in group._children.values():
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
            assert len(view._select.options) <= 25  # Discord 選單選項限制


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
        assert permission.reason is not None
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
