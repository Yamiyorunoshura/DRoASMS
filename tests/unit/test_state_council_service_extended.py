"""Extended tests for StateCouncilService to boost coverage to 80%+.

This file contains additional tests that can be merged into test_state_council_service.py
"""

from datetime import datetime, timezone
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.services.state_council_service import StateCouncilService
from src.cython_ext.state_council_models import (
    GovernmentAccount,
    IdentityRecord,
)


def _snowflake() -> int:
    """Generate a fake snowflake ID."""
    import random

    return random.randint(100000000000000000, 999999999999999999)


class TestStateCouncilServiceExtended:
    """Extended tests for StateCouncilService."""

    @pytest.fixture
    def service(self) -> StateCouncilService:
        """Create a service instance with mocked dependencies."""
        from src.bot.services.department_registry import DepartmentRegistry

        registry = DepartmentRegistry()

        service = StateCouncilService(department_registry=registry)
        service._gateway = AsyncMock()
        service._economy = AsyncMock()
        service._justice_gateway = AsyncMock()
        service._license_gateway = AsyncMock()
        return service

    # --- Reconciliation Tests ---

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reconcile_government_balances_non_strict(
        self, service: StateCouncilService
    ) -> None:
        """Test reconcile balances in non-strict mode."""
        guild_id = _snowflake()
        admin_id = _snowflake()

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            account_id = _snowflake()
            accounts = [
                GovernmentAccount(
                    account_id,
                    guild_id,
                    "內政部",
                    1000,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
            ]

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_government_accounts.return_value = accounts

            econ = AsyncMock()
            econ.fetch_balance_snapshot.return_value = MagicMock(spec=["balance"], balance=500)
            service._economy = econ

            adj_service = AsyncMock()
            adj_service.adjust_balance = AsyncMock()

            with patch.object(service, "_ensure_adjust", return_value=adj_service):
                changes = await service.reconcile_government_balances(
                    guild_id=guild_id, admin_id=admin_id, strict=False
                )

                assert "內政部" in changes
                assert changes["內政部"] == 500

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_latest_suspect_markers_success(self, service: StateCouncilService) -> None:
        """Test fetching latest suspect markers."""
        guild_id = _snowflake()
        target_id = _snowflake()

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            records = [
                IdentityRecord(
                    record_id=1,
                    guild_id=guild_id,
                    target_id=target_id,
                    action="標記疑犯",
                    reason="測試",
                    operator_id=_snowflake(),
                    created_at=datetime.now(tz=timezone.utc),
                ),
            ]

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_identity_records.return_value = records

            result = await service.fetch_latest_suspect_markers(
                guild_id=guild_id, target_ids=[target_id]
            )

            assert len(result) == 1
            assert target_id in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_latest_suspect_markers_empty(self, service: StateCouncilService) -> None:
        """Test fetching suspect markers with empty target_ids."""
        result = await service.fetch_latest_suspect_markers(guild_id=_snowflake(), target_ids=[])
        assert result == {}

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_monthly_issuance_not_configured(self, service: StateCouncilService) -> None:
        """Test getting monthly issuance when not configured."""
        guild_id = _snowflake()

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = None

            result = await service.get_monthly_issuance(guild_id=guild_id)

            assert result == (0, 0)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_can_issue_not_configured(self, service: StateCouncilService) -> None:
        """Test checking issuance ability when not configured."""
        guild_id = _snowflake()

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = None

            result = await service.check_can_issue(guild_id=guild_id, amount=1000)

            assert result.is_err()
            assert "國務院未配置" in result.error

    @pytest.mark.unit
    def test_derive_department_account_id_consistency(self, service: StateCouncilService) -> None:
        """Test that derive_department_account_id is consistent."""
        guild_id = _snowflake()
        department = "財政部"

        id1 = service.derive_department_account_id(guild_id=guild_id, department=department)
        id2 = service.derive_department_account_id(guild_id=guild_id, department=department)

        assert id1 == id2  # Should be deterministic
        assert id1 > 0  # Should be positive

    @pytest.mark.unit
    def test_derive_department_account_id_different_guilds(
        self, service: StateCouncilService
    ) -> None:
        """Test that different guilds get different account IDs."""
        guild_id_1 = _snowflake()
        guild_id_2 = _snowflake()
        department = "財政部"

        id1 = service.derive_department_account_id(guild_id=guild_id_1, department=department)
        id2 = service.derive_department_account_id(guild_id=guild_id_2, department=department)

        assert id1 != id2  # Different guilds should get different IDs

    @pytest.mark.unit
    def test_derive_department_account_id_different_departments(
        self, service: StateCouncilService
    ) -> None:
        """Test that different departments get different account IDs."""
        guild_id = _snowflake()

        id1 = service.derive_department_account_id(guild_id=guild_id, department="財政部")
        id2 = service.derive_department_account_id(guild_id=guild_id, department="內政部")

        assert id1 != id2  # Different departments should get different IDs
