"""Basic unit tests for State Council functionality."""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock

import pytest

from src.bot.services.state_council_service import StateCouncilService


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


@pytest.mark.unit
class TestStateCouncilBasic:
    """Basic tests for State Council service."""

    def test_derive_department_account_id(self) -> None:
        """Test department account ID derivation."""
        mock_transfer = AsyncMock()
        service = StateCouncilService(transfer_service=mock_transfer)
        guild_id = 12345

        internal_affairs_id = service.derive_department_account_id(guild_id, "內政部")
        finance_id = service.derive_department_account_id(guild_id, "財政部")
        security_id = service.derive_department_account_id(guild_id, "國土安全部")
        central_bank_id = service.derive_department_account_id(guild_id, "中央銀行")

        # Verify different departments get different IDs
        assert internal_affairs_id != finance_id != security_id != central_bank_id

        # Verify deterministic (same guild + department = same ID)
        assert service.derive_department_account_id(guild_id, "內政部") == internal_affairs_id

        # Verify different guilds get different IDs
        assert service.derive_department_account_id(54321, "內政部") != internal_affairs_id

        # Verify expected pattern
        expected_base = 9_500_000_000_000_000
        expected_internal = expected_base + int(guild_id) + 1
        expected_finance = expected_base + int(guild_id) + 2
        expected_security = expected_base + int(guild_id) + 3
        expected_central = expected_base + int(guild_id) + 4

        assert internal_affairs_id == expected_internal
        assert finance_id == expected_finance
        assert security_id == expected_security
        assert central_bank_id == expected_central

    def test_derive_department_account_id_unknown_department(self) -> None:
        """Test department account ID derivation with unknown department."""
        mock_transfer = AsyncMock()
        service = StateCouncilService(transfer_service=mock_transfer)
        guild_id = 12345

        unknown_id = service.derive_department_account_id(guild_id, "不存在的部門")
        expected_base = 9_500_000_000_000_000
        expected_unknown = expected_base + int(guild_id) + 0  # Default to 0

        assert unknown_id == expected_unknown

    @pytest.mark.asyncio
    async def test_service_initialization(self) -> None:
        """Test service initialization with default dependencies."""
        from unittest.mock import patch

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_get_pool.return_value = AsyncMock()
            service = StateCouncilService()

        # Verify service has required attributes
        assert hasattr(service, "_gateway")
        assert hasattr(service, "_transfer")
        assert service._gateway is not None
        assert service._transfer is not None

    @pytest.mark.asyncio
    async def test_service_initialization_with_custom_dependencies(self) -> None:
        """Test service initialization with custom dependencies."""
        mock_gateway = AsyncMock()
        mock_transfer = AsyncMock()

        service = StateCouncilService(gateway=mock_gateway, transfer_service=mock_transfer)

        # Verify custom dependencies are set
        assert service._gateway == mock_gateway
        assert service._transfer == mock_transfer

    @pytest.mark.asyncio
    async def test_permission_check_methods_exist(self) -> None:
        """Test that permission check methods exist."""
        mock_transfer = AsyncMock()
        service = StateCouncilService(transfer_service=mock_transfer)

        # Verify methods exist
        assert hasattr(service, "check_leader_permission")
        assert hasattr(service, "check_department_permission")
        assert callable(service.check_leader_permission)
        assert callable(service.check_department_permission)

    @pytest.mark.asyncio
    async def test_core_business_methods_exist(self) -> None:
        """Test that core business methods exist."""
        mock_transfer = AsyncMock()
        service = StateCouncilService(transfer_service=mock_transfer)

        # Verify core methods exist
        core_methods = [
            "set_config",
            "get_config",
            "get_council_summary",
            "disburse_welfare",
            "collect_tax",
            "create_identity_record",
            "issue_currency",
            "transfer_between_departments",
            "get_department_balance",
            "get_all_accounts",
            "update_department_config",
        ]

        for method_name in core_methods:
            assert hasattr(service, method_name)
            assert callable(getattr(service, method_name))

    def test_department_codes_mapping(self) -> None:
        """Test department codes are correctly mapped."""
        mock_transfer = AsyncMock()
        service = StateCouncilService(transfer_service=mock_transfer)
        guild_id = 1000

        # Test all expected departments
        expected_codes = {
            "內政部": 1,
            "財政部": 2,
            "國土安全部": 3,
            "中央銀行": 4,
        }

        for department, expected_code in expected_codes.items():
            account_id = service.derive_department_account_id(guild_id, department)
            expected_base = 9_500_000_000_000_000
            expected_id = expected_base + int(guild_id) + expected_code
            assert account_id == expected_id

    def test_account_id_uniqueness_across_guilds(self) -> None:
        """Test account IDs are unique across different guilds."""
        mock_transfer = AsyncMock()
        service = StateCouncilService(transfer_service=mock_transfer)

        guild1 = 1000
        guild2 = 2000

        # Same department in different guilds should have different IDs
        dept1_guild1 = service.derive_department_account_id(guild1, "內政部")
        dept1_guild2 = service.derive_department_account_id(guild2, "內政部")

        assert dept1_guild1 != dept1_guild2

    def test_account_id_consistency_within_guild(self) -> None:
        """Test account IDs are consistent within the same guild."""
        mock_transfer = AsyncMock()
        service = StateCouncilService(transfer_service=mock_transfer)

        guild_id = 1000

        # Multiple calls for same guild+department should return same ID
        id1 = service.derive_department_account_id(guild_id, "內政部")
        id2 = service.derive_department_account_id(guild_id, "內政部")
        id3 = service.derive_department_account_id(guild_id, "內政部")

        assert id1 == id2 == id3

    def test_department_account_id_range(self) -> None:
        """Test department account IDs are in expected range."""
        mock_transfer = AsyncMock()
        service = StateCouncilService(transfer_service=mock_transfer)

        guild_id = 1
        base_id = 9_500_000_000_000_000

        # Test small guild ID
        for department in ["內政部", "財政部", "國土安全部", "中央銀行"]:
            account_id = service.derive_department_account_id(guild_id, department)
            assert base_id < account_id < base_id + 100  # +code 1..4

        # Test larger guild ID
        guild_id = 999999
        for department in ["內政部", "財政部", "國土安全部", "中央銀行"]:
            account_id = service.derive_department_account_id(guild_id, department)
            assert base_id < account_id < base_id + guild_id + 10

    def test_service_error_types(self) -> None:
        """Test service has proper error types."""
        from src.bot.services.state_council_service import (
            InsufficientFundsError,
            MonthlyIssuanceLimitExceededError,
            PermissionDeniedError,
            StateCouncilNotConfiguredError,
        )

        # Verify error classes exist and inherit from RuntimeError
        assert issubclass(StateCouncilNotConfiguredError, RuntimeError)
        assert issubclass(PermissionDeniedError, RuntimeError)
        assert issubclass(InsufficientFundsError, RuntimeError)
        assert issubclass(MonthlyIssuanceLimitExceededError, RuntimeError)

    def test_service_data_classes(self) -> None:
        """Test service has proper data classes."""
        from src.bot.services.state_council_service import (
            DepartmentStats,
            StateCouncilSummary,
        )

        # Test DepartmentStats can be instantiated
        dept_stats = DepartmentStats(
            department="內政部",
            balance=1000,
            total_welfare_disbursed=500,
            total_tax_collected=0,
            identity_actions_count=0,
            currency_issued=0,
        )

        assert dept_stats.department == "內政部"
        assert dept_stats.balance == 1000

        # Test StateCouncilSummary can be instantiated
        summary = StateCouncilSummary(
            leader_id=123,
            leader_role_id=456,
            total_balance=10000,
            department_stats={},
            recent_transfers=[],
        )

        assert summary.leader_id == 123
        assert summary.total_balance == 10000
