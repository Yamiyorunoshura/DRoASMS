"""Unit tests for Supreme Assembly gateway database operations."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import asyncpg
import pytest

from src.db.gateway.supreme_assembly_governance import (
    Proposal,
    Summon,
    SupremeAssemblyConfig,
    SupremeAssemblyGovernanceGateway,
    Tally,
)
from src.infra.result import DatabaseError


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


@pytest.mark.unit
class TestSupremeAssemblyGovernanceGateway:
    """Test cases for SupremeAssemblyGovernanceGateway."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def gateway(self) -> SupremeAssemblyGovernanceGateway:
        """Create gateway instance."""
        return SupremeAssemblyGovernanceGateway()

    @pytest.fixture
    def sample_config(self) -> dict[str, Any]:
        """Sample supreme assembly configuration data."""
        return {
            "guild_id": _snowflake(),
            "speaker_role_id": _snowflake(),
            "member_role_id": _snowflake(),
            "created_at": datetime.now(tz=timezone.utc),
            "updated_at": datetime.now(tz=timezone.utc),
        }

    @pytest.fixture
    def sample_proposal(self) -> dict[str, Any]:
        """Sample proposal data."""
        return {
            "proposal_id": UUID(int=123),
            "guild_id": _snowflake(),
            "proposer_id": _snowflake(),
            "title": "測試提案",
            "description": "這是測試",
            "snapshot_n": 5,
            "threshold_t": 3,
            "deadline_at": datetime.now(tz=timezone.utc),
            "status": "進行中",
            "reminder_sent": False,
            "created_at": datetime.now(tz=timezone.utc),
            "updated_at": datetime.now(tz=timezone.utc),
        }

    @pytest.fixture
    def sample_summon(self) -> dict[str, Any]:
        """Sample summon data."""
        return {
            "summon_id": UUID(int=456),
            "guild_id": _snowflake(),
            "invoked_by": _snowflake(),
            "target_id": _snowflake(),
            "target_kind": "member",
            "note": "測試傳召",
            "delivered": False,
            "delivered_at": None,
            "created_at": datetime.now(tz=timezone.utc),
        }

    # --- Config Tests ---

    @pytest.mark.asyncio
    async def test_upsert_config_insert(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
        sample_config: dict[str, Any],
    ) -> None:
        """Test inserting new config."""
        mock_connection.fetchrow.return_value = sample_config

        config = await gateway.upsert_config(
            mock_connection,
            guild_id=sample_config["guild_id"],
            speaker_role_id=sample_config["speaker_role_id"],
            member_role_id=sample_config["member_role_id"],
        )

        assert isinstance(config, SupremeAssemblyConfig)
        assert config.guild_id == sample_config["guild_id"]
        assert config.speaker_role_id == sample_config["speaker_role_id"]
        assert config.member_role_id == sample_config["member_role_id"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_config_success(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
        sample_config: dict[str, Any],
    ) -> None:
        """Test successful config fetch."""
        mock_connection.fetchrow.return_value = sample_config

        config = await gateway.fetch_config(mock_connection, guild_id=sample_config["guild_id"])

        assert config is not None
        assert isinstance(config, SupremeAssemblyConfig)
        assert config.guild_id == sample_config["guild_id"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_config_not_found(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching non-existent config."""
        mock_connection.fetchrow.return_value = None

        config = await gateway.fetch_config(mock_connection, guild_id=_snowflake())

        assert config is None
        mock_connection.fetchrow.assert_called_once()

    # --- Account Tests ---

    @pytest.mark.asyncio
    async def test_fetch_account_success(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test successful account fetch."""
        guild_id = _snowflake()
        account_id = _snowflake()
        balance = 5000
        mock_connection.fetchrow.return_value = {
            "account_id": account_id,
            "balance": balance,
        }

        result = await gateway.fetch_account(mock_connection, guild_id=guild_id)

        assert result is not None
        assert result[0] == account_id
        assert result[1] == balance
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_account_not_found(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching non-existent account."""
        mock_connection.fetchrow.return_value = None

        result = await gateway.fetch_account(mock_connection, guild_id=_snowflake())

        assert result is None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_account(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test ensuring account exists."""
        guild_id = _snowflake()
        account_id = _snowflake()

        await gateway.ensure_account(mock_connection, guild_id=guild_id, account_id=account_id)

        mock_connection.execute.assert_called_once()

    # --- Proposal Tests ---

    @pytest.mark.asyncio
    async def test_create_proposal(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
        sample_proposal: dict[str, Any],
    ) -> None:
        """Test creating proposal."""
        mock_connection.fetchval.return_value = 0  # active count
        mock_connection.fetchrow.return_value = sample_proposal

        proposal = await gateway.create_proposal(
            mock_connection,
            guild_id=sample_proposal["guild_id"],
            proposer_id=sample_proposal["proposer_id"],
            title=sample_proposal["title"],
            description=sample_proposal["description"],
            snapshot_member_ids=[1, 2, 3, 4, 5],
        )

        assert isinstance(proposal, Proposal)
        assert proposal.proposal_id == sample_proposal["proposal_id"]
        assert proposal.title == sample_proposal["title"]
        mock_connection.fetchrow.assert_called()

    @pytest.mark.asyncio
    async def test_create_proposal_concurrency_limit(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
    ) -> None:
        """Test proposal creation fails when concurrency limit reached."""
        mock_connection.fetchval.return_value = 5  # already 5 active proposals

        with pytest.raises(RuntimeError, match="Active proposal limit"):
            await gateway.create_proposal(
                mock_connection,
                guild_id=_snowflake(),
                proposer_id=_snowflake(),
                title="測試",
                description=None,
                snapshot_member_ids=[1, 2, 3],
            )

    @pytest.mark.asyncio
    async def test_fetch_proposal_success(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
        sample_proposal: dict[str, Any],
    ) -> None:
        """Test successful proposal fetch."""
        mock_connection.fetchrow.return_value = sample_proposal

        proposal = await gateway.fetch_proposal(
            mock_connection, proposal_id=sample_proposal["proposal_id"]
        )

        assert proposal is not None
        assert isinstance(proposal, Proposal)
        assert proposal.proposal_id == sample_proposal["proposal_id"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_proposal_not_found(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching non-existent proposal."""
        mock_connection.fetchrow.return_value = None

        proposal = await gateway.fetch_proposal(mock_connection, proposal_id=UUID(int=999))

        assert proposal is None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_snapshot(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching proposal snapshot."""
        proposal_id = UUID(int=123)
        member_ids = [1, 2, 3]
        mock_connection.fetch.return_value = [{"member_id": mid} for mid in member_ids]

        snapshot = await gateway.fetch_snapshot(mock_connection, proposal_id=proposal_id)

        assert len(snapshot) == 3
        assert snapshot == member_ids
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_active_by_guild(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test counting active proposals by guild."""
        guild_id = _snowflake()
        mock_connection.fetchval.return_value = 3

        count = await gateway.count_active_by_guild(mock_connection, guild_id=guild_id)

        assert count == 3
        mock_connection.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_proposal_no_votes(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test canceling proposal with no votes."""
        proposal_id = UUID(int=123)
        mock_connection.fetchval.return_value = 0  # no votes
        mock_connection.execute.return_value = "UPDATE 1"

        result = await gateway.cancel_proposal(mock_connection, proposal_id=proposal_id)

        assert result is True
        mock_connection.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_proposal_with_votes(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test canceling proposal with votes fails."""
        proposal_id = UUID(int=123)
        mock_connection.fetchval.return_value = 1  # has votes

        result = await gateway.cancel_proposal(mock_connection, proposal_id=proposal_id)

        assert result is False
        mock_connection.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_mark_status(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test marking proposal status."""
        proposal_id = UUID(int=123)
        status = "已通過"

        await gateway.mark_status(mock_connection, proposal_id=proposal_id, status=status)

        mock_connection.execute.assert_called_once()

    # --- Voting Tests ---

    @pytest.mark.asyncio
    async def test_upsert_vote_success(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test successful vote insertion."""
        proposal_id = UUID(int=123)
        voter_id = _snowflake()
        choice = "approve"
        mock_connection.fetchval.return_value = None  # vote doesn't exist

        await gateway.upsert_vote(
            mock_connection,
            proposal_id=proposal_id,
            voter_id=voter_id,
            choice=choice,
        )

        mock_connection.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_vote_already_exists(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test vote insertion fails when vote already exists."""
        proposal_id = UUID(int=123)
        voter_id = _snowflake()
        mock_connection.fetchval.return_value = 1  # vote exists

        with pytest.raises(RuntimeError, match="already exists"):
            await gateway.upsert_vote(
                mock_connection,
                proposal_id=proposal_id,
                voter_id=voter_id,
                choice="approve",
            )

    @pytest.mark.asyncio
    async def test_fetch_tally(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching vote tally."""
        proposal_id = UUID(int=123)
        mock_connection.fetchrow.return_value = {
            "approve": 3,
            "reject": 1,
            "abstain": 1,
            "total_voted": 5,
        }

        tally = await gateway.fetch_tally(mock_connection, proposal_id=proposal_id)

        assert isinstance(tally, Tally)
        assert tally.approve == 3
        assert tally.reject == 1
        assert tally.abstain == 1
        assert tally.total_voted == 5
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_votes_detail(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching vote details."""
        proposal_id = UUID(int=123)
        mock_connection.fetch.return_value = [
            {"voter_id": 1, "choice": "approve"},
            {"voter_id": 2, "choice": "reject"},
            {"voter_id": 3, "choice": "abstain"},
        ]

        votes = await gateway.fetch_votes_detail(mock_connection, proposal_id=proposal_id)

        assert len(votes) == 3
        assert votes[0] == (1, "approve")
        assert votes[1] == (2, "reject")
        assert votes[2] == (3, "abstain")
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_unvoted_members(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test listing unvoted members."""
        proposal_id = UUID(int=123)
        mock_connection.fetch.return_value = [
            {"member_id": 1},
            {"member_id": 3},
        ]

        unvoted = await gateway.list_unvoted_members(mock_connection, proposal_id=proposal_id)

        assert len(unvoted) == 2
        assert unvoted == [1, 3]
        mock_connection.fetch.assert_called_once()

    # --- Scheduler Tests ---

    @pytest.mark.asyncio
    async def test_list_due_proposals(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
        sample_proposal: dict[str, Any],
    ) -> None:
        """Test listing due proposals."""
        mock_connection.fetch.return_value = [sample_proposal]

        proposals = await gateway.list_due_proposals(mock_connection)

        assert len(proposals) == 1
        assert isinstance(proposals[0], Proposal)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_active_proposals(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
        sample_proposal: dict[str, Any],
    ) -> None:
        """Test listing active proposals."""
        mock_connection.fetch.return_value = [sample_proposal]

        proposals = await gateway.list_active_proposals(mock_connection)

        assert len(proposals) == 1
        assert isinstance(proposals[0], Proposal)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_reminded(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test marking proposal as reminded."""
        proposal_id = UUID(int=123)

        await gateway.mark_reminded(mock_connection, proposal_id=proposal_id)

        mock_connection.execute.assert_called_once()

    # --- Summon Tests ---

    @pytest.mark.asyncio
    async def test_create_summon(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
        sample_summon: dict[str, Any],
    ) -> None:
        """Test creating summon record."""
        mock_connection.fetchrow.return_value = sample_summon

        summon = await gateway.create_summon(
            mock_connection,
            guild_id=sample_summon["guild_id"],
            invoked_by=sample_summon["invoked_by"],
            target_id=sample_summon["target_id"],
            target_kind=sample_summon["target_kind"],
            note=sample_summon["note"],
        )

        assert isinstance(summon, Summon)
        assert summon.guild_id == sample_summon["guild_id"]
        assert summon.target_id == sample_summon["target_id"]
        assert summon.target_kind == sample_summon["target_kind"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_summon_delivered(
        self, gateway: SupremeAssemblyGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test marking summon as delivered."""
        summon_id = UUID(int=456)

        await gateway.mark_summon_delivered(mock_connection, summon_id=summon_id)

        mock_connection.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_summons(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
        sample_summon: dict[str, Any],
    ) -> None:
        """Test listing summons."""
        guild_id = sample_summon["guild_id"]
        mock_connection.fetch.return_value = [sample_summon]

        summons = await gateway.list_summons(mock_connection, guild_id=guild_id, limit=50)

        assert len(summons) == 1
        assert isinstance(summons[0], Summon)
        assert summons[0].guild_id == guild_id
        mock_connection.fetch.assert_called_once()

    # --- Export Tests ---

    @pytest.mark.asyncio
    async def test_export_interval(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
    ) -> None:
        """Test exporting proposals in interval."""
        guild_id = _snowflake()
        start = datetime.now(tz=timezone.utc)
        end = datetime.now(tz=timezone.utc)
        mock_connection.fetch.return_value = [
            {
                "proposal_id": UUID(int=123),
                "guild_id": guild_id,
                "votes": [],
                "snapshot": [],
            }
        ]

        result = await gateway.export_interval(
            mock_connection, guild_id=guild_id, start=start, end=end
        )

        assert len(result) == 1
        assert isinstance(result[0], dict)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_config_result_success(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
        sample_config: dict[str, Any],
    ) -> None:
        mock_connection.fetchrow.return_value = sample_config

        result = await gateway.fetch_config_result(
            mock_connection, guild_id=sample_config["guild_id"]
        )

        assert result.is_ok()
        config = result.unwrap()
        assert isinstance(config, SupremeAssemblyConfig)

    @pytest.mark.asyncio
    async def test_fetch_config_result_failure(
        self,
        gateway: SupremeAssemblyGovernanceGateway,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.fetchrow.side_effect = RuntimeError("db error")

        result = await gateway.fetch_config_result(mock_connection, guild_id=_snowflake())

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, DatabaseError)
