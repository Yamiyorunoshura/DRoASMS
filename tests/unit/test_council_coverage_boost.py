"""補齊 council.py 測試覆蓋率 - 目標從 49% 提升至 70%+

此測試文件專注於覆蓋以下未測試的代碼路徑：
1. add_role, remove_role, list_roles 指令的各種場景
2. TransferTypeSelectionView, DepartmentSelectView, UserSelectView, CouncilCompanySelectView 互動
3. ProposeTransferModal 的各種提交場景
4. CouncilPanelView 的更多互動場景
5. _unwrap_result 函數的各種 Result 型別處理
6. _dm_council_for_voting 和相關的 VotingView
7. _broadcast_result 的邊界情況
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.bot.commands.council import (
    CouncilPanelView,
    DepartmentSelectView,
    ProposeTransferModal,
    TransferTypeSelectionView,
    UserSelectView,
    VotingView,
    _dm_council_for_voting,
    _unwrap_result,
    build_council_group,
)
from src.bot.services.council_service import (
    CouncilService,
    CouncilServiceResult,
    GovernanceNotConfiguredError,
)
from src.infra.result import Err, Ok

# === 測試 _unwrap_result 函數 ===


@pytest.mark.unit
class TestUnwrapResult:
    """測試 _unwrap_result 函數處理各種 Result 型別"""

    def test_unwrap_ok_value(self) -> None:
        """測試展開 Ok(value)"""
        result = Ok("test_value")
        value, error = _unwrap_result(result)
        assert value == "test_value"
        assert error is None

    def test_unwrap_err_value(self) -> None:
        """測試展開 Err(error)"""
        test_error = Exception("test error")
        result = Err(test_error)
        value, error = _unwrap_result(result)
        assert value is None
        assert error == test_error

    def test_unwrap_nested_ok_ok(self) -> None:
        """測試展開 Ok(Ok(value))"""
        result = Ok(Ok("nested_value"))
        value, error = _unwrap_result(result)
        assert value == "nested_value"
        assert error is None

    def test_unwrap_ok_err(self) -> None:
        """測試展開 Ok(Err(error))"""
        test_error = Exception("nested error")
        result = Ok(Err(test_error))
        value, error = _unwrap_result(result)
        assert value is None
        assert error == test_error

    def test_unwrap_non_result(self) -> None:
        """測試展開非 Result 型別的值"""
        plain_value = "plain_string"
        value, error = _unwrap_result(plain_value)
        assert value == "plain_string"
        assert error is None


# === 測試 add_role 指令 ===


@pytest.mark.unit
class TestAddRoleCommand:
    """測試 /council add_role 指令的各種場景"""

    @pytest.mark.asyncio
    async def test_add_role_success(self) -> None:
        """測試成功新增理事身分組"""
        mock_service = MagicMock(spec=CouncilService)
        mock_result_service = MagicMock(spec=CouncilServiceResult)
        mock_result_service.add_council_role = AsyncMock(return_value=Ok(True))

        # Setup guild, role, and member with admin permission
        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role = MagicMock()
        mock_role.id = 11111
        mock_role.mention = "<@&11111>"

        mock_member = MagicMock()
        mock_member.guild_permissions.administrator = True

        # Setup interaction
        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.user = mock_member
        interaction.response = AsyncMock()

        # Build group and get command
        group = build_council_group(mock_service, mock_result_service)
        add_role_cmd = None
        for child in group._children.values():
            if child.name == "add_role":
                add_role_cmd = child
                break

        assert add_role_cmd is not None

        # Execute command
        await add_role_cmd.callback(interaction, mock_role)

        # Verify
        mock_result_service.add_council_role.assert_called_once_with(
            guild_id=mock_guild.id, role_id=mock_role.id
        )
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        # Check both positional and keyword arguments
        content = call_args[0][0] if call_args[0] else call_args[1].get("content", "")
        assert "已新增" in content or mock_role.mention in str(content)

    @pytest.mark.asyncio
    async def test_add_role_already_exists(self) -> None:
        """測試新增已存在的理事身分組"""
        mock_service = MagicMock(spec=CouncilService)
        mock_result_service = MagicMock(spec=CouncilServiceResult)
        mock_result_service.add_council_role = AsyncMock(return_value=Ok(False))

        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role = MagicMock()
        mock_role.id = 11111
        mock_role.mention = "<@&11111>"

        mock_member = MagicMock()
        mock_member.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.user = mock_member
        interaction.response = AsyncMock()

        group = build_council_group(mock_service, mock_result_service)
        add_role_cmd = [cmd for cmd in group._children.values() if cmd.name == "add_role"][0]

        await add_role_cmd.callback(interaction, mock_role)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        content = call_args[0][0] if call_args[0] else call_args[1].get("content", "")
        assert "已存在" in content or "exist" in content.lower()

    @pytest.mark.asyncio
    async def test_add_role_no_permission(self) -> None:
        """測試沒有權限新增理事身分組"""
        mock_service = MagicMock(spec=CouncilService)
        mock_result_service = MagicMock(spec=CouncilServiceResult)

        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role = MagicMock()

        mock_member = MagicMock()
        mock_member.guild_permissions.administrator = False
        mock_member.guild_permissions.manage_guild = False

        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.user = mock_member
        interaction.response = AsyncMock()

        group = build_council_group(mock_service, mock_result_service)
        add_role_cmd = [cmd for cmd in group._children.values() if cmd.name == "add_role"][0]

        await add_role_cmd.callback(interaction, mock_role)

        interaction.response.send_message.assert_called_once_with(
            "需要管理員或管理伺服器權限。", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_add_role_service_error(self) -> None:
        """測試服務錯誤"""
        mock_service = MagicMock(spec=CouncilService)
        mock_result_service = MagicMock(spec=CouncilServiceResult)
        mock_result_service.add_council_role = AsyncMock(side_effect=Exception("Database error"))

        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role = MagicMock()
        mock_role.id = 11111

        mock_member = MagicMock()
        mock_member.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.user = mock_member
        interaction.response = AsyncMock()

        group = build_council_group(mock_service, mock_result_service)
        add_role_cmd = [cmd for cmd in group._children.values() if cmd.name == "add_role"][0]

        await add_role_cmd.callback(interaction, mock_role)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        content = call_args[0][0] if call_args[0] else call_args[1].get("content", "")
        assert "失敗" in content or "error" in content.lower()


# === 測試 remove_role 指令 ===


@pytest.mark.unit
class TestRemoveRoleCommand:
    """測試 /council remove_role 指令的各種場景"""

    @pytest.mark.asyncio
    async def test_remove_role_success(self) -> None:
        """測試成功移除理事身分組"""
        mock_service = MagicMock(spec=CouncilService)
        mock_result_service = MagicMock(spec=CouncilServiceResult)
        mock_result_service.remove_council_role = AsyncMock(return_value=Ok(True))

        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role = MagicMock()
        mock_role.id = 11111
        mock_role.mention = "<@&11111>"

        mock_member = MagicMock()
        mock_member.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.user = mock_member
        interaction.response = AsyncMock()

        group = build_council_group(mock_service, mock_result_service)
        remove_role_cmd = [cmd for cmd in group._children.values() if cmd.name == "remove_role"][0]

        await remove_role_cmd.callback(interaction, mock_role)

        mock_result_service.remove_council_role.assert_called_once_with(
            guild_id=mock_guild.id, role_id=mock_role.id
        )
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        content = call_args[0][0] if call_args[0] else call_args[1].get("content", "")
        assert "移除" in content or mock_role.mention in str(content)

    @pytest.mark.asyncio
    async def test_remove_role_not_exists(self) -> None:
        """測試移除不存在的理事身分組"""
        mock_service = MagicMock(spec=CouncilService)
        mock_result_service = MagicMock(spec=CouncilServiceResult)
        mock_result_service.remove_council_role = AsyncMock(return_value=Ok(False))

        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role = MagicMock()
        mock_role.id = 11111
        mock_role.mention = "<@&11111>"

        mock_member = MagicMock()
        mock_member.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.user = mock_member
        interaction.response = AsyncMock()

        group = build_council_group(mock_service, mock_result_service)
        remove_role_cmd = [cmd for cmd in group._children.values() if cmd.name == "remove_role"][0]

        await remove_role_cmd.callback(interaction, mock_role)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        content = call_args[0][0] if call_args[0] else call_args[1].get("content", "")
        assert "不在" in content or mock_role.mention in str(content)


# === 測試 list_roles 指令 ===


@pytest.mark.unit
class TestListRolesCommand:
    """測試 /council list_roles 指令的各種場景"""

    @pytest.mark.asyncio
    async def test_list_roles_success(self) -> None:
        """測試成功列出理事身分組"""
        mock_service = MagicMock(spec=CouncilService)
        mock_result_service = MagicMock(spec=CouncilServiceResult)
        mock_result_service.get_council_role_ids = AsyncMock(return_value=Ok([11111, 22222]))
        mock_config = MagicMock()
        mock_config.council_role_id = 33333
        mock_result_service.get_config = AsyncMock(return_value=Ok(mock_config))

        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role1 = MagicMock()
        mock_role1.mention = "<@&11111>"
        mock_role2 = MagicMock()
        mock_role2.mention = "<@&22222>"
        mock_guild.get_role = lambda role_id: (
            mock_role1 if role_id == 11111 else mock_role2 if role_id == 22222 else None
        )

        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.response = AsyncMock()

        group = build_council_group(mock_service, mock_result_service)
        list_roles_cmd = [cmd for cmd in group._children.values() if cmd.name == "list_roles"][0]

        await list_roles_cmd.callback(interaction)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        content = call_args[0][0] if call_args[0] else call_args[1].get("content", "")
        # 檢查是否包含身分組相關資訊
        assert (
            "11111" in content
            or "22222" in content
            or "<@&11111>" in content
            or "身分組" in content
        )

    @pytest.mark.asyncio
    async def test_list_roles_not_configured(self) -> None:
        """測試未配置時列出理事身分組"""
        mock_service = MagicMock(spec=CouncilService)
        mock_result_service = MagicMock(spec=CouncilServiceResult)
        mock_result_service.get_council_role_ids = AsyncMock(
            side_effect=GovernanceNotConfiguredError("未配置")
        )

        mock_guild = MagicMock()
        mock_guild.id = 12345

        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.response = AsyncMock()

        group = build_council_group(mock_service, mock_result_service)
        list_roles_cmd = [cmd for cmd in group._children.values() if cmd.name == "list_roles"][0]

        await list_roles_cmd.callback(interaction)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        content = call_args[0][0] if call_args[0] else call_args[1].get("content", "")
        assert "尚未" in content or "設定" in content or "未完成" in content

    @pytest.mark.asyncio
    async def test_list_roles_empty(self) -> None:
        """測試沒有理事身分組"""
        mock_service = MagicMock(spec=CouncilService)
        mock_result_service = MagicMock(spec=CouncilServiceResult)
        mock_result_service.get_council_role_ids = AsyncMock(return_value=Ok([]))
        mock_config = MagicMock()
        mock_config.council_role_id = None
        mock_result_service.get_config = AsyncMock(return_value=Ok(mock_config))

        mock_guild = MagicMock()
        mock_guild.id = 12345

        interaction = MagicMock()
        interaction.guild_id = mock_guild.id
        interaction.guild = mock_guild
        interaction.response = AsyncMock()

        group = build_council_group(mock_service, mock_result_service)
        list_roles_cmd = [cmd for cmd in group._children.values() if cmd.name == "list_roles"][0]

        await list_roles_cmd.callback(interaction)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        content = call_args[0][0] if call_args[0] else call_args[1].get("content", "")
        assert "沒有" in content or "目前" in content or "身分組" in content


# === 測試 TransferTypeSelectionView ===


@pytest.mark.unit
class TestTransferTypeSelectionView:
    """測試轉帳類型選擇視圖"""

    @pytest.mark.asyncio
    async def test_select_user_button(self) -> None:
        """測試選擇使用者按鈕"""
        mock_service = MagicMock(spec=CouncilService)
        mock_guild = MagicMock()

        with patch.object(TransferTypeSelectionView, "__init__", return_value=None):
            view = TransferTypeSelectionView(service=mock_service, guild=mock_guild)
            view.service = mock_service
            view.guild = mock_guild

        interaction = MagicMock()
        interaction.response = AsyncMock()
        button = MagicMock()

        await view.select_user(interaction, button)

        interaction.response.send_message.assert_called_once()
        # 應該會顯示 UserSelectView
        assert interaction.response.send_message.called

    @pytest.mark.asyncio
    async def test_select_department_button(self) -> None:
        """測試選擇部門按鈕"""
        mock_service = MagicMock(spec=CouncilService)
        mock_guild = MagicMock()

        with patch.object(TransferTypeSelectionView, "__init__", return_value=None):
            view = TransferTypeSelectionView(service=mock_service, guild=mock_guild)
            view.service = mock_service
            view.guild = mock_guild

        interaction = MagicMock()
        interaction.response = AsyncMock()
        button = MagicMock()

        await view.select_department(interaction, button)

        interaction.response.send_message.assert_called_once()


# === 測試 DepartmentSelectView ===


@pytest.mark.unit
class TestDepartmentSelectView:
    """測試部門選擇視圖"""

    @pytest.mark.asyncio
    async def test_on_select_valid_department(self) -> None:
        """測試選擇有效部門"""
        mock_service = MagicMock(spec=CouncilService)
        mock_guild = MagicMock()
        mock_guild.id = 12345

        with (
            patch.object(DepartmentSelectView, "__init__", return_value=None),
            patch("src.bot.commands.council.get_registry") as mock_get_registry,
        ):
            view = DepartmentSelectView(service=mock_service, guild=mock_guild)
            view.service = mock_service
            view.guild = mock_guild

            # Mock registry
            mock_dept = MagicMock()
            mock_dept.name = "財政部"
            mock_registry = MagicMock()
            mock_registry.get_by_id.return_value = mock_dept
            mock_get_registry.return_value = mock_registry

            # Mock interaction with department selection
            interaction = MagicMock()
            interaction.data = {"values": ["DEPT_001"]}
            interaction.response = AsyncMock()

            await view._on_select(interaction)

            interaction.response.send_modal.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_select_no_values(self) -> None:
        """測試沒有選擇部門"""
        mock_service = MagicMock(spec=CouncilService)
        mock_guild = MagicMock()

        with patch.object(DepartmentSelectView, "__init__", return_value=None):
            view = DepartmentSelectView(service=mock_service, guild=mock_guild)
            view.service = mock_service
            view.guild = mock_guild

            interaction = MagicMock()
            interaction.data = None
            interaction.response = AsyncMock()

            await view._on_select(interaction)

            interaction.response.send_message.assert_called_once_with(
                "請選擇一個部門。", ephemeral=True
            )


# === 測試 UserSelectView ===


@pytest.mark.unit
class TestUserSelectView:
    """測試使用者選擇視圖"""

    @pytest.mark.asyncio
    async def test_on_select_valid_user(self) -> None:
        """測試選擇有效使用者"""
        mock_service = MagicMock(spec=CouncilService)
        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_member = MagicMock()
        mock_member.display_name = "Test User"
        mock_guild.get_member.return_value = mock_member

        with patch.object(UserSelectView, "__init__", return_value=None):
            view = UserSelectView(service=mock_service, guild=mock_guild)
            view.service = mock_service
            view.guild = mock_guild

            interaction = MagicMock()
            interaction.data = {"values": ["67890"]}
            interaction.response = AsyncMock()

            await view._on_select(interaction)

            interaction.response.send_modal.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_select_no_values(self) -> None:
        """測試沒有選擇使用者"""
        mock_service = MagicMock(spec=CouncilService)
        mock_guild = MagicMock()

        with patch.object(UserSelectView, "__init__", return_value=None):
            view = UserSelectView(service=mock_service, guild=mock_guild)
            view.service = mock_service
            view.guild = mock_guild

            interaction = MagicMock()
            interaction.data = {"values": []}
            interaction.response = AsyncMock()

            await view._on_select(interaction)

            interaction.response.send_message.assert_called_once_with(
                "請選擇一個使用者。", ephemeral=True
            )


# === 測試 ProposeTransferModal ===


@pytest.mark.unit
class TestProposeTransferModal:
    """測試舊版建立轉帳提案 Modal"""

    @pytest.mark.asyncio
    async def test_on_submit_invalid_user_input(self) -> None:
        """測試無效的使用者輸入"""
        mock_service = MagicMock(spec=CouncilService)
        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_guild.get_member.return_value = None

        with patch.object(ProposeTransferModal, "__init__", return_value=None):
            modal = ProposeTransferModal(service=mock_service, guild=mock_guild)
            modal.service = mock_service
            modal.guild = mock_guild
            modal.target = MagicMock()
            modal.target.value = "invalid_user_id"
            modal.amount = MagicMock()
            modal.amount.value = "100"
            modal.description = MagicMock()
            modal.description.value = ""
            modal.attachment_url = MagicMock()
            modal.attachment_url.value = ""

            interaction = MagicMock()
            interaction.client = MagicMock()
            interaction.client.get_user.return_value = None
            interaction.client.fetch_user = AsyncMock(side_effect=Exception("User not found"))
            interaction.response = AsyncMock()

            await modal.on_submit(interaction)

            interaction.response.send_message.assert_called_once()
            call_args = interaction.response.send_message.call_args
            content = call_args[0][0] if call_args[0] else call_args[1].get("content", "")
            assert "無法辨識" in content or "受款人" in content or "錯誤" in content

    @pytest.mark.asyncio
    async def test_on_submit_valid_mention(self) -> None:
        """測試有效的使用者 mention"""
        mock_service = MagicMock(spec=CouncilService)
        mock_service.get_config = AsyncMock(return_value=Ok(MagicMock(council_role_id=11111)))
        mock_proposal = MagicMock()
        mock_proposal.proposal_id = uuid4()
        mock_service.create_transfer_proposal = AsyncMock(return_value=Ok(mock_proposal))

        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_member = MagicMock()
        mock_member.id = 67890
        mock_member2 = MagicMock()
        mock_member2.id = 11111
        mock_role = MagicMock()
        mock_role.members = [mock_member2]
        mock_guild.get_role.return_value = mock_role
        mock_guild.get_member.return_value = mock_member

        with (
            patch.object(ProposeTransferModal, "__init__", return_value=None),
            patch("src.bot.commands.council._dm_council_for_voting", new_callable=AsyncMock),
        ):
            modal = ProposeTransferModal(service=mock_service, guild=mock_guild)
            modal.service = mock_service
            modal.guild = mock_guild
            modal.target = MagicMock()
            modal.target.value = "<@67890>"
            modal.amount = MagicMock()
            modal.amount.value = "100"
            modal.description = MagicMock()
            modal.description.value = "Test description"
            modal.attachment_url = MagicMock()
            modal.attachment_url.value = "http://example.com"

            interaction = MagicMock()
            interaction.user = MagicMock()
            interaction.user.id = 99999
            interaction.client = MagicMock()
            interaction.response = AsyncMock()

            await modal.on_submit(interaction)

            mock_service.create_transfer_proposal.assert_called_once()
            interaction.response.send_message.assert_called_once()


# === 測試 VotingView 按鈕 ===


@pytest.mark.unit
class TestVotingView:
    """測試投票視圖按鈕"""

    @pytest.mark.asyncio
    async def test_approve_button(self) -> None:
        """測試同意按鈕"""
        mock_service = MagicMock(spec=CouncilService)
        mock_service.vote = AsyncMock(
            return_value=(MagicMock(approve=5, reject=0, abstain=0, threshold_t=4), "進行中")
        )
        proposal_id = uuid4()

        with patch.object(VotingView, "__init__", return_value=None):
            view = VotingView(proposal_id=proposal_id, service=mock_service)
            view.proposal_id = proposal_id
            view.service = mock_service

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 67890
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.guild_id = 12345
        interaction.guild = None
        interaction.client = MagicMock()
        button = MagicMock()

        await view.approve(interaction, button)

        mock_service.vote.assert_called_once()

    @pytest.mark.asyncio
    async def test_reject_button(self) -> None:
        """測試反對按鈕"""
        mock_service = MagicMock(spec=CouncilService)
        mock_service.vote = AsyncMock(
            return_value=(MagicMock(approve=0, reject=5, abstain=0, threshold_t=4), "已否決")
        )
        proposal_id = uuid4()

        with patch.object(VotingView, "__init__", return_value=None):
            view = VotingView(proposal_id=proposal_id, service=mock_service)
            view.proposal_id = proposal_id
            view.service = mock_service

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 67890
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.guild_id = 12345
        interaction.guild = None
        interaction.client = MagicMock()
        button = MagicMock()

        await view.reject(interaction, button)

        mock_service.vote.assert_called_once()

    @pytest.mark.asyncio
    async def test_abstain_button(self) -> None:
        """測試棄權按鈕"""
        mock_service = MagicMock(spec=CouncilService)
        mock_service.vote = AsyncMock(
            return_value=(MagicMock(approve=2, reject=2, abstain=1, threshold_t=4), "進行中")
        )
        proposal_id = uuid4()

        with patch.object(VotingView, "__init__", return_value=None):
            view = VotingView(proposal_id=proposal_id, service=mock_service)
            view.proposal_id = proposal_id
            view.service = mock_service

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 67890
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.guild_id = 12345
        interaction.guild = None
        interaction.client = MagicMock()
        button = MagicMock()

        await view.abstain(interaction, button)

        mock_service.vote.assert_called_once()


# === 測試 _dm_council_for_voting ===


@pytest.mark.unit
class TestDMCouncilForVoting:
    """測試 DM 通知理事投票"""

    @pytest.mark.asyncio
    async def test_dm_council_success(self) -> None:
        """測試成功發送 DM 通知"""
        client = MagicMock()
        guild = MagicMock()
        guild.id = 12345
        service = MagicMock(spec=CouncilService)
        service.get_council_role_ids = AsyncMock(return_value=Ok([11111]))
        service.get_config = AsyncMock(return_value=Ok(MagicMock(council_role_id=11111)))

        proposal = MagicMock()
        proposal.proposal_id = uuid4()
        proposal.target_id = 67890
        proposal.amount = 1000
        proposal.description = "Test proposal"
        proposal.attachment_url = None
        proposal.threshold_t = 3
        proposal.deadline_at = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)
        proposal.target_department_id = None

        # Mock role and members
        mock_member = MagicMock()
        mock_member.id = 11111
        mock_member.send = AsyncMock()
        mock_role = MagicMock()
        mock_role.members = [mock_member]
        guild.get_role.return_value = mock_role

        await _dm_council_for_voting(client, guild, service, proposal)

        # Verify member received DM
        mock_member.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_dm_council_with_department_target(self) -> None:
        """測試部門目標的 DM 通知"""
        client = MagicMock()
        guild = MagicMock()
        guild.id = 12345
        service = MagicMock(spec=CouncilService)
        service.get_council_role_ids = AsyncMock(return_value=Ok([11111]))

        proposal = MagicMock()
        proposal.proposal_id = uuid4()
        proposal.target_id = 67890
        proposal.target_department_id = "DEPT_001"
        proposal.amount = 5000
        proposal.description = "Department funding"
        proposal.attachment_url = None
        proposal.threshold_t = 4
        proposal.deadline_at = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)

        # Mock role and members
        mock_member = MagicMock()
        mock_member.send = AsyncMock()
        mock_role = MagicMock()
        mock_role.members = [mock_member]
        guild.get_role.return_value = mock_role

        with patch("src.bot.commands.council.get_registry") as mock_get_registry:
            mock_dept = MagicMock()
            mock_dept.name = "財政部"
            mock_registry = MagicMock()
            mock_registry.get_by_id.return_value = mock_dept
            mock_get_registry.return_value = mock_registry

            await _dm_council_for_voting(client, guild, service, proposal)

            mock_member.send.assert_called_once()


# === 測試 CouncilPanelView 額外場景 ===


@pytest.mark.unit
class TestCouncilPanelViewExtended:
    """測試 CouncilPanelView 的更多場景"""

    @pytest.mark.asyncio
    async def test_on_click_help(self) -> None:
        """測試點擊幫助按鈕"""
        mock_service = MagicMock(spec=CouncilService)
        mock_guild = MagicMock()
        mock_guild.id = 12345

        with (
            patch.object(CouncilPanelView, "__init__", return_value=None),
            patch.object(CouncilPanelView, "_build_help_embed") as mock_build_help,
        ):
            view = CouncilPanelView(
                service=mock_service, guild=mock_guild, author_id=67890, council_role_id=11111
            )
            view.service = mock_service
            view.guild = mock_guild
            view.author_id = 67890

            mock_embed = MagicMock()
            mock_build_help.return_value = mock_embed

            interaction = MagicMock()
            interaction.user = MagicMock()
            interaction.user.id = 67890
            interaction.response = AsyncMock()

            await view._on_click_help(interaction)

            interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_click_help_wrong_user(self) -> None:
        """測試非面板開啟者點擊幫助按鈕"""
        mock_service = MagicMock(spec=CouncilService)
        mock_guild = MagicMock()

        with patch.object(CouncilPanelView, "__init__", return_value=None):
            view = CouncilPanelView(
                service=mock_service, guild=mock_guild, author_id=67890, council_role_id=11111
            )
            view.author_id = 67890

            interaction = MagicMock()
            interaction.user = MagicMock()
            interaction.user.id = 99999  # Different user
            interaction.response = AsyncMock()

            await view._on_click_help(interaction)

            interaction.response.send_message.assert_called_once_with(
                "僅限面板開啟者操作。", ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_on_select_proposal_invalid_id(self) -> None:
        """測試選擇無效的提案 ID"""
        mock_service = MagicMock(spec=CouncilService)
        mock_guild = MagicMock()
        mock_guild.id = 12345

        with patch.object(CouncilPanelView, "__init__", return_value=None):
            view = CouncilPanelView(
                service=mock_service, guild=mock_guild, author_id=67890, council_role_id=11111
            )
            view.service = mock_service
            view.guild = mock_guild
            view._select = MagicMock()
            view._select.values = ["invalid_uuid"]

            interaction = MagicMock()
            interaction.response = AsyncMock()

            await view._on_select_proposal(interaction)

            interaction.response.send_message.assert_called_once()
            call_args = interaction.response.send_message.call_args
            content = call_args[0][0] if call_args[0] else call_args[1].get("content", "")
            assert "格式錯誤" in content or "錯誤" in content or "選項" in content

    @pytest.mark.asyncio
    async def test_on_select_proposal_none_selected(self) -> None:
        """測試選擇 none 選項"""
        mock_service = MagicMock(spec=CouncilService)
        mock_guild = MagicMock()

        with patch.object(CouncilPanelView, "__init__", return_value=None):
            view = CouncilPanelView(
                service=mock_service, guild=mock_guild, author_id=67890, council_role_id=11111
            )
            view._select = MagicMock()
            view._select.values = ["none"]

            interaction = MagicMock()
            interaction.response = AsyncMock()

            await view._on_select_proposal(interaction)

            interaction.response.send_message.assert_called_once_with(
                "沒有可操作的提案。", ephemeral=True
            )
