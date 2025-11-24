"""Unit tests for CouncilGovernanceGateway snapshot helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest

from src.db.gateway.council_governance import CouncilGovernanceGateway


@pytest.mark.unit
class TestCouncilGovernanceGateway:
    """Test cases for snapshot- and vote-related helpers."""

    @pytest.fixture
    def gateway(self) -> CouncilGovernanceGateway:
        return CouncilGovernanceGateway()

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.mark.asyncio
    async def test_fetch_snapshot_returns_member_ids(
        self,
        gateway: CouncilGovernanceGateway,
        mock_connection: AsyncMock,
    ) -> None:
        proposal_id = uuid4()
        mock_connection.fetch.return_value = [
            {"member_id": 111111111111111111},
            {"member_id": 222222222222222222},
        ]

        members = await gateway.fetch_snapshot(mock_connection, proposal_id=proposal_id)

        assert members == [111111111111111111, 222222222222222222]
        mock_connection.fetch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_unvoted_members_returns_member_ids(
        self,
        gateway: CouncilGovernanceGateway,
        mock_connection: AsyncMock,
    ) -> None:
        proposal_id = uuid4()
        mock_connection.fetch.return_value = [
            {"member_id": 333333333333333333},
            {"member_id": 444444444444444444},
        ]

        members = await gateway.list_unvoted_members(mock_connection, proposal_id=proposal_id)

        assert members == [333333333333333333, 444444444444444444]
        mock_connection.fetch.assert_awaited_once()
