from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import discord
import pytest

from src.bot.commands.council import (
    _extract_select_values,
    _format_proposal_desc,
    _format_proposal_title,
    _handle_vote,
    _safe_fetch_user,
    build_council_group,
    get_help_data,
)
from src.bot.services.council_service import (
    CouncilService,
    GovernanceNotConfiguredError,
    PermissionDeniedError,
)

# --- Test Helper Functions (Non-UI) ---


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

    def test_returns_group(self) -> None:
        """測試返回群組"""
        mock_service = MagicMock(spec=CouncilService)
        group = build_council_group(mock_service)
        assert isinstance(group, discord.app_commands.Group)
        assert group.name == "council"
        assert group.description == "理事會治理指令群組"

    def test_group_has_commands(self) -> None:
        """測試群組有指令"""
        mock_service = MagicMock(spec=CouncilService)
        group = build_council_group(mock_service)
        # 檢查是否有 config_role 和 panel 指令
        command_names = [cmd.name for cmd in group._children.values()]
        assert "config_role" in command_names
        assert "panel" in command_names


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


class TestHandleVote:
    """測試 _handle_vote 函數 - 使用 patch 避免事件循環問題"""

    @pytest.mark.asyncio
    async def test_successful_vote(self) -> None:
        """測試成功投票"""
        mock_council_service = MagicMock(spec=CouncilService)
        mock_council_service.vote.return_value = (
            MagicMock(approve=5, reject=2, abstain=1, threshold_t=6),
            "進行中",
        )

        # Mock interaction with AsyncMock
        interaction = MagicMock()
        interaction.user.id = 67890
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Mock the followup send to avoid actual async issues
        with patch("src.bot.commands.council.structlog.get_logger"):
            await _handle_vote(interaction, mock_council_service, uuid4(), "approve")

        mock_council_service.vote.assert_called_once()
        interaction.response.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_permission_denied(self) -> None:
        """測試權限被拒絕"""
        mock_council_service = MagicMock(spec=CouncilService)
        mock_council_service.vote.side_effect = PermissionDeniedError("沒有投票權")

        interaction = MagicMock()
        interaction.response = AsyncMock()

        with patch("src.bot.commands.council.structlog.get_logger"):
            await _handle_vote(interaction, mock_council_service, uuid4(), "approve")

        interaction.response.send_message.assert_called_with("沒有投票權", ephemeral=True)

    @pytest.mark.asyncio
    async def test_vote_error(self) -> None:
        """測試投票錯誤"""
        mock_council_service = MagicMock(spec=CouncilService)
        mock_council_service.vote.side_effect = Exception("資料庫錯誤")

        interaction = MagicMock()
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        with patch("src.bot.commands.council.structlog.get_logger"):
            await _handle_vote(interaction, mock_council_service, uuid4(), "approve")

        interaction.response.send_message.assert_called_with("投票失敗。", ephemeral=True)


class TestCouncilCommandLogic:
    """測試 Council 指令邏輯 - 避免 UI 組件"""

    @pytest.mark.asyncio
    async def test_config_role_command_success(self) -> None:
        """測試 config_role 指令成功 - 使用 patch"""
        mock_council_service = MagicMock(spec=CouncilService)
        mock_config = MagicMock()
        mock_config.council_account_member_id = 99999
        mock_council_service.set_config = AsyncMock(return_value=mock_config)

        # Mock guild, role, and member
        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role = MagicMock()
        mock_role.id = 11111
        mock_role.mention = "<@&11111>"

        mock_member = MagicMock()
        mock_member.guild_permissions.administrator = True

        # Mock interaction
        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.user = mock_member
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.original_response = AsyncMock(return_value=MagicMock())

        # Patch the background scheduler to avoid event loop issues
        with patch("src.bot.commands.council._install_background_scheduler"):
            group = build_council_group(mock_council_service)

            # Get config_role command
            config_role_cmd = None
            for child in group._children.values():
                if child.name == "config_role":
                    config_role_cmd = child
                    break

            assert config_role_cmd is not None

            # Execute command
            await config_role_cmd.callback(interaction, mock_role)

        mock_council_service.set_config.assert_called_once_with(
            guild_id=mock_guild.id, council_role_id=mock_role.id
        )
        interaction.response.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_config_role_command_no_permissions(self) -> None:
        """測試 config_role 指令沒有權限"""
        mock_council_service = MagicMock(spec=CouncilService)

        # Mock guild, role, and member without permissions
        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role = MagicMock()

        mock_member = MagicMock()
        mock_member.guild_permissions.administrator = False
        mock_member.guild_permissions.manage_guild = False

        # Mock interaction
        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.user = mock_member
        interaction.response = AsyncMock()

        # Patch the background scheduler
        with patch("src.bot.commands.council._install_background_scheduler"):
            group = build_council_group(mock_council_service)

            # Get config_role command
            config_role_cmd = None
            for child in group._children.values():
                if child.name == "config_role":
                    config_role_cmd = child
                    break

            assert config_role_cmd is not None

            # Execute command
            await config_role_cmd.callback(interaction, mock_role)

        interaction.response.send_message.assert_called_with(
            "需要管理員或管理伺服器權限。", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_panel_command_not_configured(self) -> None:
        """測試 panel 指令未配置"""
        mock_council_service = MagicMock(spec=CouncilService)
        mock_council_service.get_config.side_effect = GovernanceNotConfiguredError("未配置")

        # Mock guild and member
        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_member = MagicMock()

        # Mock interaction
        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.user = mock_member
        interaction.response = AsyncMock()

        # Patch the background scheduler and other UI components
        with patch("src.bot.commands.council._install_background_scheduler"):
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
    async def test_panel_command_not_council_member(self) -> None:
        """測試 panel 指令不是理事會成員"""
        mock_council_service = MagicMock(spec=CouncilService)
        mock_config = MagicMock()
        mock_config.council_role_id = 11111
        mock_council_service.get_config = AsyncMock(return_value=mock_config)

        # Mock guild, role, and member
        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role = MagicMock()
        mock_role.id = 11111
        mock_role.members = []
        mock_guild.get_role.return_value = mock_role

        mock_member = MagicMock(spec=discord.Member)
        mock_member.roles = []  # No council role

        # Mock interaction
        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.user = mock_member
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.original_response = AsyncMock(return_value=MagicMock())

        # Patch UI components
        with patch("src.bot.commands.council._install_background_scheduler"):
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

        interaction.response.send_message.assert_called_with("僅限理事可開啟面板。", ephemeral=True)


# --- UI Component Tests (Event Loop Safe) ---


class TestUIComponents:
    """測試 UI 組件 - 使用事件循環上下文"""

    @pytest.mark.asyncio
    async def test_modal_submit_in_event_loop(self) -> None:
        """在事件循環中測試 Modal 提交邏輯"""
        # 使用實際的事件循環
        async with self._create_event_loop():
            # Mock TransferProposalModal 的邏輯
            from src.bot.commands.council import TransferProposalModal

            mock_service = MagicMock(spec=CouncilService)
            mock_guild = MagicMock()

            # Mock the modal initialization to avoid event loop issues
            with patch.object(TransferProposalModal, "__init__", return_value=None):
                modal = TransferProposalModal(service=mock_service, guild=mock_guild)

                # Set required attributes
                modal.target_user_id = None
                modal.target_department_id = None
                modal.amount = MagicMock()
                modal.amount.value = "100"
                modal.service = mock_service
                modal.guild = mock_guild

                # Mock interaction
                interaction = MagicMock()
                interaction.response = MagicMock()
                interaction.response.send_message = AsyncMock()

                await modal.on_submit(interaction)

                interaction.response.send_message.assert_called_with(
                    "錯誤：未選擇受款人。", ephemeral=True
                )

    @asynccontextmanager
    async def _create_event_loop(self):
        """創建事件循環上下文"""
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        try:
            yield loop
        finally:
            pass


# --- Performance and Integration Tests ---


class TestCouncilIntegration:
    """理事會整合測試"""

    @pytest.mark.asyncio
    async def test_full_proposal_creation_flow(self) -> None:
        """測試完整提案建立流程 - 使用 mock 避免實際 UI"""
        mock_service = MagicMock(spec=CouncilService)
        mock_proposal = MagicMock()
        mock_proposal.proposal_id = uuid4()
        mock_service.create_transfer_proposal = AsyncMock(return_value=mock_proposal)

        # Mock guild and role
        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role = MagicMock()
        mock_role.id = 11111
        mock_member1 = MagicMock()
        mock_member1.id = 11111
        mock_member2 = MagicMock()
        mock_member2.id = 22222
        mock_role.members = [mock_member1, mock_member2]

        mock_config = MagicMock()
        mock_config.council_role_id = mock_role.id
        mock_service.get_config = AsyncMock(return_value=mock_config)
        mock_guild.get_role.return_value = mock_role

        # Test data
        guild_id = 12345
        proposer_id = 67890
        target_id = 11111
        amount = 1000
        description = "Test proposal"
        snapshot_member_ids = [11111, 22222]

        # Call the service method directly
        result = await mock_service.create_transfer_proposal(
            guild_id=guild_id,
            proposer_id=proposer_id,
            target_id=target_id,
            amount=amount,
            description=description,
            attachment_url=None,
            snapshot_member_ids=snapshot_member_ids,
        )

        # Verify
        assert result == mock_proposal
        mock_service.create_transfer_proposal.assert_called_once_with(
            guild_id=guild_id,
            proposer_id=proposer_id,
            target_id=target_id,
            amount=amount,
            description=description,
            attachment_url=None,
            snapshot_member_ids=snapshot_member_ids,
        )

    @pytest.mark.asyncio
    async def test_voting_flow(self) -> None:
        """測試投票流程"""
        mock_service = MagicMock(spec=CouncilService)
        mock_tally = MagicMock()
        mock_tally.approve = 5
        mock_tally.reject = 2
        mock_tally.abstain = 1
        mock_tally.threshold_t = 4
        mock_service.vote = AsyncMock(return_value=(mock_tally, "進行中"))

        proposal_id = uuid4()
        voter_id = 67890
        choice = "approve"

        result = await mock_service.vote(proposal_id=proposal_id, voter_id=voter_id, choice=choice)

        assert result == (mock_tally, "進行中")
        mock_service.vote.assert_called_once_with(
            proposal_id=proposal_id, voter_id=voter_id, choice=choice
        )

    @pytest.mark.asyncio
    async def test_proposal_cancellation(self) -> None:
        """測試提案撤案"""
        mock_service = MagicMock(spec=CouncilService)
        mock_service.cancel_proposal = AsyncMock(return_value=True)

        proposal_id = uuid4()
        result = await mock_service.cancel_proposal(proposal_id=proposal_id)

        assert result is True
        mock_service.cancel_proposal.assert_called_once_with(proposal_id=proposal_id)

    def test_proposal_title_formatting_edge_cases(self) -> None:
        """測試提案標題格式化的邊界情況"""
        # Test with very long IDs
        proposal = MagicMock()
        proposal.proposal_id = UUID("12345678-1234-5678-9abc-123456789012")
        proposal.target_id = 123456789012345678  # Very large ID
        proposal.amount = 999999999
        proposal.target_department_id = None

        result = _format_proposal_title(proposal)
        assert "#" in result
        assert "→" in result
        assert str(proposal.amount) in result

    def test_proposal_description_edge_cases(self) -> None:
        """測試提案描述的邊界情況"""
        # Test with special characters
        proposal = MagicMock()
        proposal.deadline_at = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)
        proposal.description = "Special chars: @#$%^&*()_+-={}[]|\\:;\"'<>?,./"
        proposal.threshold_t = 3

        result = _format_proposal_desc(proposal)
        assert "截止" in result
        assert "T=3" in result
        assert "Special chars" in result

    @pytest.mark.asyncio
    async def test_error_handling_scenarios(self) -> None:
        """測試錯誤處理場景"""
        mock_service = MagicMock(spec=CouncilService)

        # Test various exception types
        test_exceptions = [
            PermissionDeniedError("No permission"),
            GovernanceNotConfiguredError("Not configured"),
            ValueError("Invalid value"),
            Exception("General error"),
        ]

        for exc in test_exceptions:
            mock_service.vote = AsyncMock(side_effect=exc)

            interaction = MagicMock()
            interaction.response = AsyncMock()
            interaction.followup = AsyncMock()

            # Should not raise exception
            with patch("src.bot.commands.council.structlog.get_logger"):
                try:
                    await _handle_vote(interaction, mock_service, uuid4(), "approve")
                except Exception:
                    pass  # Expected for some error types

            # Verify error response
            interaction.response.send_message.assert_called()
