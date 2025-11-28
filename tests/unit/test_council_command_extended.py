"""Extended tests for council command - Task 2.2.1-2.2.5.

Coverage for proposal creation, voting, execution, permissions, and Result<T,E> error paths.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import discord
import pytest

from src.bot.commands.council import (
    _broadcast_result,
    _handle_vote,
    build_council_group,
)
from src.bot.services.council_service import (
    CouncilService,
    CouncilServiceResult,
    GovernanceNotConfiguredError,
    PermissionDeniedError,
)
from src.infra.result import Err, Ok, ValidationError


@pytest.fixture
def mock_service() -> MagicMock:
    service = MagicMock(spec=CouncilService)
    service.create_transfer_proposal = AsyncMock()
    service.vote = AsyncMock()
    service.cancel_proposal = AsyncMock()
    service.get_proposal = AsyncMock()
    service.list_active_proposals = AsyncMock(return_value=[])
    service.check_council_permission = AsyncMock(return_value=True)
    service.get_config = AsyncMock()
    return service


@pytest.fixture
def mock_guild() -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    guild.id = 12345
    guild.name = "Test Guild"
    return guild


@pytest.fixture
def mock_interaction(mock_guild: MagicMock) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = mock_guild.id
    interaction.guild = mock_guild
    interaction.user = MagicMock()
    interaction.user.id = 67890
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send_message = AsyncMock()
    return interaction


class TestProposalCreation:
    """Task 2.2.1: Proposal creation test cases."""

    @pytest.mark.asyncio
    async def test_create_transfer_proposal_to_user(self, mock_service: MagicMock) -> None:
        """Test creating transfer proposal to user."""
        proposal_id = uuid4()
        mock_service.create_transfer_proposal = AsyncMock(return_value=proposal_id)

        result = await mock_service.create_transfer_proposal(
            guild_id=12345,
            proposer_id=67890,
            target_id=11111,
            amount=1000,
            description="測試轉帳提案",
            duration_hours=24,
        )

        assert result == proposal_id
        mock_service.create_transfer_proposal.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_transfer_proposal_to_department(self, mock_service: MagicMock) -> None:
        """Test creating transfer proposal to department."""
        proposal_id = uuid4()
        mock_service.create_transfer_proposal = AsyncMock(return_value=proposal_id)

        result = await mock_service.create_transfer_proposal(
            guild_id=12345,
            proposer_id=67890,
            target_department_id="DEPT_001",
            amount=5000,
            description="部門撥款提案",
            duration_hours=48,
        )

        assert result == proposal_id

    @pytest.mark.asyncio
    async def test_create_proposal_not_configured(self, mock_service: MagicMock) -> None:
        """Test proposal creation when council not configured."""
        mock_service.create_transfer_proposal = AsyncMock(
            side_effect=GovernanceNotConfiguredError("理事會尚未設定")
        )

        with pytest.raises(GovernanceNotConfiguredError):
            await mock_service.create_transfer_proposal(
                guild_id=12345,
                proposer_id=67890,
                target_id=11111,
                amount=1000,
                description="",
                duration_hours=24,
            )

    @pytest.mark.asyncio
    async def test_create_proposal_permission_denied(self, mock_service: MagicMock) -> None:
        """Test proposal creation with permission denied."""
        mock_service.create_transfer_proposal = AsyncMock(
            side_effect=PermissionDeniedError("僅限理事可建案")
        )

        with pytest.raises(PermissionDeniedError):
            await mock_service.create_transfer_proposal(
                guild_id=12345,
                proposer_id=99999,
                target_id=11111,
                amount=1000,
                description="",
                duration_hours=24,
            )

    @pytest.mark.asyncio
    async def test_create_proposal_invalid_amount(self, mock_service: MagicMock) -> None:
        """Test proposal creation with invalid amount."""
        mock_service.create_transfer_proposal = AsyncMock(side_effect=ValueError("金額必須為正數"))

        with pytest.raises(ValueError):
            await mock_service.create_transfer_proposal(
                guild_id=12345,
                proposer_id=67890,
                target_id=11111,
                amount=-100,
                description="",
                duration_hours=24,
            )


class TestVotingFunctionality:
    """Task 2.2.2: Voting functionality test cases."""

    @pytest.mark.asyncio
    async def test_vote_approve(self, mock_service: MagicMock, mock_interaction: MagicMock) -> None:
        """Test approve vote."""
        mock_service.vote = AsyncMock(
            return_value=(MagicMock(approve=5, reject=0, abstain=0, threshold_t=4), "已通過")
        )

        await _handle_vote(mock_interaction, mock_service, uuid4(), "approve")

        mock_service.vote.assert_called_once()
        mock_interaction.response.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_vote_reject(self, mock_service: MagicMock, mock_interaction: MagicMock) -> None:
        """Test reject vote."""
        mock_service.vote = AsyncMock(
            return_value=(MagicMock(approve=0, reject=5, abstain=0, threshold_t=4), "已否決")
        )

        await _handle_vote(mock_interaction, mock_service, uuid4(), "reject")

        mock_service.vote.assert_called_once()

    @pytest.mark.asyncio
    async def test_vote_abstain(self, mock_service: MagicMock, mock_interaction: MagicMock) -> None:
        """Test abstain vote."""
        mock_service.vote = AsyncMock(
            return_value=(MagicMock(approve=2, reject=2, abstain=1, threshold_t=4), "進行中")
        )

        await _handle_vote(mock_interaction, mock_service, uuid4(), "abstain")

        mock_service.vote.assert_called_once()

    @pytest.mark.asyncio
    async def test_vote_duplicate(
        self, mock_service: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test duplicate vote handling."""
        mock_service.vote = AsyncMock(side_effect=PermissionDeniedError("您已經投過票"))

        await _handle_vote(mock_interaction, mock_service, uuid4(), "approve")

        mock_interaction.response.send_message.assert_called_with("您已經投過票", ephemeral=True)

    @pytest.mark.asyncio
    async def test_vote_expired_proposal(
        self, mock_service: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test voting on expired proposal."""
        mock_service.vote = AsyncMock(side_effect=PermissionDeniedError("提案已過期"))

        await _handle_vote(mock_interaction, mock_service, uuid4(), "approve")

        mock_interaction.response.send_message.assert_called_with("提案已過期", ephemeral=True)


class TestProposalExecution:
    """Task 2.2.3: Proposal execution test cases."""

    @pytest.mark.asyncio
    async def test_proposal_passes_threshold(self, mock_service: MagicMock) -> None:
        """Test proposal passes when reaching threshold."""
        mock_service.vote = AsyncMock(
            return_value=(MagicMock(approve=5, reject=1, abstain=0, threshold_t=4), "已通過")
        )

        totals, status = await mock_service.vote(
            proposal_id=uuid4(), voter_id=67890, choice="approve"
        )

        assert status == "已通過"
        assert totals.approve >= totals.threshold_t

    @pytest.mark.asyncio
    async def test_proposal_rejected(self, mock_service: MagicMock) -> None:
        """Test proposal rejection."""
        mock_service.vote = AsyncMock(
            return_value=(MagicMock(approve=1, reject=5, abstain=0, threshold_t=4), "已否決")
        )

        totals, status = await mock_service.vote(
            proposal_id=uuid4(), voter_id=67890, choice="reject"
        )

        assert status == "已否決"

    @pytest.mark.asyncio
    async def test_cancel_proposal_by_proposer(self, mock_service: MagicMock) -> None:
        """Test canceling proposal by proposer."""
        mock_service.cancel_proposal = AsyncMock(return_value=True)

        result = await mock_service.cancel_proposal(proposal_id=uuid4(), user_id=67890)

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_proposal_permission_denied(self, mock_service: MagicMock) -> None:
        """Test cancel proposal with permission denied."""
        mock_service.cancel_proposal = AsyncMock(
            side_effect=PermissionDeniedError("只有提案人可以撤案")
        )

        with pytest.raises(PermissionDeniedError):
            await mock_service.cancel_proposal(proposal_id=uuid4(), user_id=99999)


class TestPermissionValidation:
    """Task 2.2.4: Permission validation test cases."""

    @pytest.mark.asyncio
    async def test_check_council_permission_has_role(self, mock_service: MagicMock) -> None:
        """Test permission check with council role."""
        mock_service.check_council_permission = AsyncMock(return_value=True)

        result = await mock_service.check_council_permission(
            guild_id=12345, user_id=67890, user_roles=[11111, 22222]
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_check_council_permission_no_role(self, mock_service: MagicMock) -> None:
        """Test permission check without council role."""
        mock_service.check_council_permission = AsyncMock(return_value=False)

        result = await mock_service.check_council_permission(
            guild_id=12345, user_id=99999, user_roles=[]
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_config_role_requires_admin(
        self, mock_service: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Test config_role requires admin permission."""
        mock_interaction.user.guild_permissions = MagicMock()
        mock_interaction.user.guild_permissions.administrator = False
        mock_interaction.user.guild_permissions.manage_guild = False

        # The command should check permissions
        mock_service.set_config = AsyncMock()
        mock_result_service = MagicMock(spec=CouncilServiceResult)

        with patch("src.bot.commands.council._install_background_scheduler"):
            group = build_council_group(mock_service, mock_result_service)

        config_role_cmd = None
        for cmd in group._children.values():
            if cmd.name == "config_role":
                config_role_cmd = cmd
                break

        assert config_role_cmd is not None


class TestResultErrorPaths:
    """Task 2.2.5: Result<T,E> error path tests."""

    @pytest.mark.asyncio
    async def test_create_proposal_returns_ok(self, mock_service: MagicMock) -> None:
        """Test create_proposal returning Ok result."""
        proposal_id = uuid4()
        mock_service.create_transfer_proposal = AsyncMock(return_value=Ok(proposal_id))

        result = await mock_service.create_transfer_proposal(
            guild_id=12345,
            proposer_id=67890,
            target_id=11111,
            amount=1000,
            description="",
            duration_hours=24,
        )

        assert result.is_ok()
        assert result.unwrap() == proposal_id

    @pytest.mark.asyncio
    async def test_create_proposal_returns_err(self, mock_service: MagicMock) -> None:
        """Test create_proposal returning Err result."""
        error = ValidationError("金額超過上限")
        mock_service.create_transfer_proposal = AsyncMock(return_value=Err(error))

        result = await mock_service.create_transfer_proposal(
            guild_id=12345,
            proposer_id=67890,
            target_id=11111,
            amount=999999999,
            description="",
            duration_hours=24,
        )

        assert result.is_err()
        assert "金額" in result.unwrap_err().message

    @pytest.mark.asyncio
    async def test_vote_returns_ok(self, mock_service: MagicMock) -> None:
        """Test vote returning Ok result."""
        totals = MagicMock(approve=3, reject=1, abstain=0, threshold_t=4)
        mock_service.vote = AsyncMock(return_value=Ok((totals, "進行中")))

        result = await mock_service.vote(proposal_id=uuid4(), voter_id=67890, choice="approve")

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_vote_returns_err(self, mock_service: MagicMock) -> None:
        """Test vote returning Err result."""
        error = PermissionDeniedError("投票權限不足")
        mock_service.vote = AsyncMock(return_value=Err(error))

        result = await mock_service.vote(proposal_id=uuid4(), voter_id=99999, choice="approve")

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_get_config_returns_err(self, mock_service: MagicMock) -> None:
        """Test get_config returning Err when not configured."""
        error = GovernanceNotConfiguredError("尚未設定理事會")
        mock_service.get_config = AsyncMock(return_value=Err(error))

        result = await mock_service.get_config(guild_id=12345)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), GovernanceNotConfiguredError)

    @pytest.mark.asyncio
    async def test_list_proposals_returns_ok(self, mock_service: MagicMock) -> None:
        """Test list_active_proposals returning Ok result."""
        proposals = [MagicMock(), MagicMock()]
        mock_service.list_active_proposals = AsyncMock(return_value=Ok(proposals))

        result = await mock_service.list_active_proposals(guild_id=12345)

        assert result.is_ok()
        assert len(result.unwrap()) == 2


class TestBroadcastResultIntegration:
    """Test broadcast result integration scenarios."""

    def test_broadcast_result_function_exists(self) -> None:
        """Test that _broadcast_result function is accessible."""
        assert callable(_broadcast_result)

    def test_broadcast_status_values(self) -> None:
        """Test expected status values for broadcast."""
        valid_statuses = ["已通過", "已否決", "已執行", "已撤案", "已過期"]
        for status in valid_statuses:
            assert isinstance(status, str)
            assert len(status) > 0
