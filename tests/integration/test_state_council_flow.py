"""Integration tests for State Council workflow."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import cast
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from src.bot.services.state_council_service import (
    InsufficientFundsError,
    MonthlyIssuanceLimitExceededError,
    PermissionDeniedError,
    StateCouncilNotConfiguredError,
    StateCouncilService,
)
from src.bot.services.transfer_service import TransferService
from src.db.gateway.state_council_governance import (
    CurrencyIssuance,
    DepartmentConfig,
    GovernmentAccount,
    InterdepartmentTransfer,
    StateCouncilConfig,
    StateCouncilGovernanceGateway,
    TaxRecord,
    WelfareDisbursement,
)


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


@pytest.mark.integration
@pytest.mark.timeout(60)
class TestStateCouncilFlow:
    """Integration tests for State Council complete workflows."""

    @pytest.fixture
    async def test_db_pool(self) -> AsyncMock:
        """Create test database pool mock."""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        return mock_pool

    @pytest.fixture
    def guild_id(self) -> int:
        """Test guild ID."""
        return _snowflake()

    @pytest.fixture
    def leader_id(self) -> int:
        """Test leader ID."""
        return _snowflake()

    @pytest.fixture
    def leader_role_id(self) -> int:
        """Test leader role ID."""
        return _snowflake()

    @pytest.fixture
    def department_role_id(self) -> int:
        """Test department role ID."""
        return _snowflake()

    @pytest.fixture
    def service(self) -> StateCouncilService:
        """Create State Council service instance."""
        gateway = AsyncMock(spec=StateCouncilGovernanceGateway)
        transfer_service = AsyncMock(spec=TransferService)
        return StateCouncilService(gateway=gateway, transfer_service=transfer_service)

    @pytest.fixture
    def mock_user_id(self) -> int:
        """Test user ID."""
        return _snowflake()

    @pytest.fixture
    def mock_recipient_id(self) -> int:
        """Test recipient ID."""
        return _snowflake()

    @pytest.mark.asyncio
    async def test_complete_state_council_setup_flow(
        self, service: StateCouncilService, guild_id: int, leader_id: int, leader_role_id: int
    ) -> None:
        """Test complete State Council setup workflow."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Mock successful config creation
            expected_config = StateCouncilConfig(
                guild_id=guild_id,
                leader_id=leader_id,
                leader_role_id=leader_role_id,
                internal_affairs_account_id=9500000000000001,
                finance_account_id=9500000000000002,
                security_account_id=9500000000000003,
                central_bank_account_id=9500000000000004,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )
            gw = cast(AsyncMock, service._gateway)
            gw.upsert_state_council_config.return_value = expected_config

            # Setup State Council
            config = await service.set_config(
                guild_id=guild_id,
                leader_id=leader_id,
                leader_role_id=leader_role_id,
            )

            # Verify setup
            assert config.guild_id == guild_id
            assert config.leader_id == leader_id
            assert config.leader_role_id == leader_role_id

            # Verify all components are set up
            assert gw.upsert_state_council_config.called
            assert gw.upsert_department_config.call_count == 4
            assert gw.upsert_government_account.call_count == 4

    @pytest.mark.asyncio
    async def test_welfare_disbursement_workflow(
        self,
        service: StateCouncilService,
        guild_id: int,
        mock_user_id: int,
        department_role_id: int,
        mock_recipient_id: int,
    ) -> None:
        """Test complete welfare disbursement workflow."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup mock data
            config = StateCouncilConfig(
                guild_id=guild_id,
                leader_id=_snowflake(),
                leader_role_id=_snowflake(),
                internal_affairs_account_id=9500000000000001,
                finance_account_id=9500000000000002,
                security_account_id=9500000000000003,
                central_bank_account_id=9500000000000004,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            department_config = DepartmentConfig(
                id=_snowflake(),
                guild_id=guild_id,
                department="內政部",
                role_id=department_role_id,
                welfare_amount=1000,
                welfare_interval_hours=24,
                tax_rate_basis=0,
                tax_rate_percent=0,
                max_issuance_per_month=0,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            government_account = GovernmentAccount(
                account_id=config.internal_affairs_account_id,
                guild_id=guild_id,
                department="內政部",
                balance=10000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            expected_disbursement = WelfareDisbursement(
                disbursement_id=UUID(int=123),
                guild_id=guild_id,
                recipient_id=mock_recipient_id,
                amount=1500,
                disbursement_type="特殊福利",
                reference_id="REF123",
                disbursed_at=datetime.now(tz=timezone.utc),
            )

            # Mock gateway responses
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = config
            gw.fetch_department_config.return_value = department_config
            gw.fetch_government_accounts.return_value = [government_account]
            gw.update_account_balance.return_value = None
            gw.create_welfare_disbursement.return_value = expected_disbursement

            # Mock successful transfer
            cast(AsyncMock, service._transfer.transfer_currency).return_value = None

            # Perform welfare disbursement
            disbursement = await service.disburse_welfare(
                guild_id=guild_id,
                department="內政部",
                user_id=mock_user_id,
                user_roles=[department_role_id],
                recipient_id=mock_recipient_id,
                amount=1500,
                disbursement_type="特殊福利",
            )

            # Verify result
            assert disbursement.recipient_id == mock_recipient_id
            assert disbursement.amount == 1500
            assert disbursement.disbursement_type == "特殊福利"
            assert disbursement.reference_id == "REF123"

            # Verify workflow steps（允許傳入 connection 以保證同交易原子性）
            _xfer = cast(AsyncMock, service._transfer.transfer_currency)
            _xfer.assert_called_once()
            _, _kwargs = _xfer.call_args
            assert _kwargs["guild_id"] == guild_id
            assert _kwargs["initiator_id"] == government_account.account_id
            assert _kwargs["target_id"] == mock_recipient_id
            assert _kwargs["amount"] == 1500
            assert _kwargs["reason"] == "福利發放 - 特殊福利"
            assert "connection" in _kwargs and _kwargs["connection"] is mock_conn
            gw.update_account_balance.assert_called_once_with(
                mock_conn, account_id=government_account.account_id, new_balance=8500
            )
            gw.create_welfare_disbursement.assert_called_once()

    @pytest.mark.asyncio
    async def test_tax_collection_workflow(
        self,
        service: StateCouncilService,
        guild_id: int,
        mock_user_id: int,
        department_role_id: int,
        mock_recipient_id: int,
    ) -> None:
        """Test complete tax collection workflow."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup mock data
            config = StateCouncilConfig(
                guild_id=guild_id,
                leader_id=_snowflake(),
                leader_role_id=_snowflake(),
                internal_affairs_account_id=9500000000000001,
                finance_account_id=9500000000000002,
                security_account_id=9500000000000003,
                central_bank_account_id=9500000000000004,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            department_config = DepartmentConfig(
                id=_snowflake(),
                guild_id=guild_id,
                department="財政部",
                role_id=department_role_id,
                welfare_amount=0,
                welfare_interval_hours=24,
                tax_rate_basis=0,
                tax_rate_percent=0,
                max_issuance_per_month=0,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            government_account = GovernmentAccount(
                account_id=config.finance_account_id,
                guild_id=guild_id,
                department="財政部",
                balance=5000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            expected_tax = TaxRecord(
                tax_id=UUID(int=456),
                guild_id=guild_id,
                taxpayer_id=mock_recipient_id,
                taxable_amount=20000,
                tax_rate_percent=15,
                tax_amount=3000,
                tax_type="所得稅",
                assessment_period="2024-01",
                collected_at=datetime.now(tz=timezone.utc),
            )

            # Mock gateway responses
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_department_config.return_value = department_config
            gw.fetch_government_accounts.return_value = [government_account]
            gw.update_account_balance.return_value = None
            gw.create_tax_record.return_value = expected_tax

            # Mock successful transfer
            cast(AsyncMock, service._transfer.transfer_currency).return_value = None

            # Perform tax collection
            tax_record = await service.collect_tax(
                guild_id=guild_id,
                department="財政部",
                user_id=mock_user_id,
                user_roles=[department_role_id],
                taxpayer_id=mock_recipient_id,
                taxable_amount=20000,
                tax_rate_percent=15,
                assessment_period="2024-01",
            )

            # Verify result
            assert tax_record.taxpayer_id == mock_recipient_id
            assert tax_record.taxable_amount == 20000
            assert tax_record.tax_amount == 3000
            assert tax_record.assessment_period == "2024-01"

            # Verify workflow steps
            cast(AsyncMock, service._transfer.transfer_currency).assert_called_once_with(
                guild_id=guild_id,
                initiator_id=mock_recipient_id,
                target_id=government_account.account_id,
                amount=3000,
                reason="稅收 - 所得稅",
            )
            gw.update_account_balance.assert_called_once_with(
                mock_conn, account_id=government_account.account_id, new_balance=8000
            )
            gw.create_tax_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_currency_issuance_workflow(
        self,
        service: StateCouncilService,
        guild_id: int,
        mock_user_id: int,
        department_role_id: int,
    ) -> None:
        """Test complete currency issuance workflow."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup mock data
            config = StateCouncilConfig(
                guild_id=guild_id,
                leader_id=_snowflake(),
                leader_role_id=_snowflake(),
                internal_affairs_account_id=9500000000000001,
                finance_account_id=9500000000000002,
                security_account_id=9500000000000003,
                central_bank_account_id=9500000000000004,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            department_config = DepartmentConfig(
                id=_snowflake(),
                guild_id=guild_id,
                department="中央銀行",
                role_id=department_role_id,
                welfare_amount=0,
                welfare_interval_hours=24,
                tax_rate_basis=0,
                tax_rate_percent=0,
                max_issuance_per_month=10000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            government_account = GovernmentAccount(
                account_id=config.central_bank_account_id,
                guild_id=guild_id,
                department="中央銀行",
                balance=5000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            expected_issuance = CurrencyIssuance(
                issuance_id=UUID(int=789),
                guild_id=guild_id,
                amount=5000,
                reason="經濟刺激方案",
                performed_by=mock_user_id,
                month_period="2024-01",
                issued_at=datetime.now(tz=timezone.utc),
            )

            # Mock gateway responses
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_department_config.return_value = department_config
            gw.fetch_government_accounts.return_value = [government_account]
            gw.sum_monthly_issuance.return_value = 3000  # Already issued this month
            gw.update_account_balance.return_value = None
            gw.create_currency_issuance.return_value = expected_issuance

            # Perform currency issuance
            issuance = await service.issue_currency(
                guild_id=guild_id,
                department="中央銀行",
                user_id=mock_user_id,
                user_roles=[department_role_id],
                amount=5000,
                reason="經濟刺激方案",
                month_period="2024-01",
            )

            # Verify result
            assert issuance.amount == 5000
            assert issuance.reason == "經濟刺激方案"
            assert issuance.performed_by == mock_user_id
            assert issuance.month_period == "2024-01"

            # Verify workflow steps
            gw.sum_monthly_issuance.assert_called_once_with(
                mock_conn, guild_id=guild_id, month_period="2024-01"
            )
            gw.update_account_balance.assert_called_once_with(
                mock_conn, account_id=government_account.account_id, new_balance=10000
            )
            gw.create_currency_issuance.assert_called_once()

    @pytest.mark.asyncio
    async def test_interdepartment_transfer_workflow(
        self,
        service: StateCouncilService,
        guild_id: int,
        mock_user_id: int,
        department_role_id: int,
    ) -> None:
        """Test complete interdepartment transfer workflow."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup mock data
            from_account = GovernmentAccount(
                account_id=9500000000000001,
                guild_id=guild_id,
                department="內政部",
                balance=10000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            to_account = GovernmentAccount(
                account_id=9500000000000002,
                guild_id=guild_id,
                department="財政部",
                balance=5000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            expected_transfer = InterdepartmentTransfer(
                transfer_id=UUID(int=101),
                guild_id=guild_id,
                from_department="內政部",
                to_department="財政部",
                amount=3000,
                reason="預算重新分配",
                performed_by=mock_user_id,
                transferred_at=datetime.now(tz=timezone.utc),
            )

            # Mock gateway responses and permissions
            with patch.object(service, "check_department_permission", return_value=True):
                gw = cast(AsyncMock, service._gateway)
                gw.fetch_government_accounts.return_value = [from_account, to_account]
                gw.update_account_balance.return_value = None
                gw.create_interdepartment_transfer.return_value = expected_transfer

                # Mock successful transfer
                cast(AsyncMock, service._transfer.transfer_currency).return_value = None

                # Perform interdepartment transfer
                transfer = await service.transfer_between_departments(
                    guild_id=guild_id,
                    user_id=mock_user_id,
                    user_roles=[department_role_id],
                    from_department="內政部",
                    to_department="財政部",
                    amount=3000,
                    reason="預算重新分配",
                )

                # Verify result
                assert transfer.from_department == "內政部"
                assert transfer.to_department == "財政部"
                assert transfer.amount == 3000
                assert transfer.reason == "預算重新分配"
                assert transfer.performed_by == mock_user_id

                # Verify workflow steps
                cast(AsyncMock, service.check_department_permission).assert_called_once_with(
                    guild_id=guild_id,
                    user_id=mock_user_id,
                    department="內政部",
                    user_roles=[department_role_id],
                )
                cast(AsyncMock, service._transfer.transfer_currency).assert_called_once_with(
                    guild_id=guild_id,
                    initiator_id=from_account.account_id,
                    target_id=to_account.account_id,
                    amount=3000,
                    reason="部門轉帳 - 預算重新分配",
                )
                assert gw.update_account_balance.call_count == 2
                gw.create_interdepartment_transfer.assert_called_once()

    @pytest.mark.asyncio
    async def test_permission_denied_scenarios(
        self, service: StateCouncilService, guild_id: int, mock_user_id: int
    ) -> None:
        """Test various permission denied scenarios."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Mock config exists
            config = StateCouncilConfig(
                guild_id=guild_id,
                leader_id=_snowflake(),
                leader_role_id=_snowflake(),
                internal_affairs_account_id=9500000000000001,
                finance_account_id=9500000000000002,
                security_account_id=9500000000000003,
                central_bank_account_id=9500000000000004,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = config

            # Test welfare disbursement permission denied
            with patch.object(service, "check_department_permission", return_value=False):
                with pytest.raises(PermissionDeniedError):
                    await service.disburse_welfare(
                        guild_id=guild_id,
                        department="內政部",
                        user_id=mock_user_id,
                        user_roles=[],
                        recipient_id=_snowflake(),
                        amount=1000,
                        disbursement_type="定期福利",
                    )

            # Test tax collection permission denied
            with patch.object(service, "check_department_permission", return_value=False):
                with pytest.raises(PermissionDeniedError):
                    await service.collect_tax(
                        guild_id=guild_id,
                        department="財政部",
                        user_id=mock_user_id,
                        user_roles=[],
                        taxpayer_id=_snowflake(),
                        taxable_amount=10000,
                        tax_rate_percent=10,
                        assessment_period="2024-01",
                    )

            # Test currency issuance permission denied
            with patch.object(service, "check_department_permission", return_value=False):
                with pytest.raises(PermissionDeniedError):
                    await service.issue_currency(
                        guild_id=guild_id,
                        department="中央銀行",
                        user_id=mock_user_id,
                        user_roles=[],
                        amount=5000,
                        reason="經濟刺激",
                        month_period="2024-01",
                    )

    @pytest.mark.asyncio
    async def test_insufficient_funds_scenarios(
        self,
        service: StateCouncilService,
        guild_id: int,
        mock_user_id: int,
        department_role_id: int,
    ) -> None:
        """Test insufficient funds scenarios."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup account with insufficient balance
            low_balance_account = GovernmentAccount(
                account_id=9500000000000001,
                guild_id=guild_id,
                department="內政部",
                balance=500,  # Low balance
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            department_config = DepartmentConfig(
                id=_snowflake(),
                guild_id=guild_id,
                department="內政部",
                role_id=department_role_id,
                welfare_amount=1000,
                welfare_interval_hours=24,
                tax_rate_basis=0,
                tax_rate_percent=0,
                max_issuance_per_month=0,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_department_config.return_value = department_config
            gw.fetch_government_accounts.return_value = [low_balance_account]

            # Test welfare disbursement insufficient funds
            with pytest.raises(InsufficientFundsError):
                await service.disburse_welfare(
                    guild_id=guild_id,
                    department="內政部",
                    user_id=mock_user_id,
                    user_roles=[department_role_id],
                    recipient_id=_snowflake(),
                    amount=1000,  # More than balance
                    disbursement_type="定期福利",
                )

    @pytest.mark.asyncio
    async def test_monthly_issuance_limit_scenario(
        self,
        service: StateCouncilService,
        guild_id: int,
        mock_user_id: int,
        department_role_id: int,
    ) -> None:
        """Test monthly issuance limit exceeded scenario."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup department config with monthly limit
            department_config = DepartmentConfig(
                id=_snowflake(),
                guild_id=guild_id,
                department="中央銀行",
                role_id=department_role_id,
                welfare_amount=0,
                welfare_interval_hours=24,
                tax_rate_basis=0,
                tax_rate_percent=0,
                max_issuance_per_month=5000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            government_account = GovernmentAccount(
                account_id=9500000000000004,
                guild_id=guild_id,
                department="中央銀行",
                balance=10000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_department_config.return_value = department_config
            gw.fetch_government_accounts.return_value = [government_account]
            gw.sum_monthly_issuance.return_value = 4000  # Close to limit

            # Test issuance limit exceeded
            with pytest.raises(MonthlyIssuanceLimitExceededError):
                await service.issue_currency(
                    guild_id=guild_id,
                    department="中央銀行",
                    user_id=mock_user_id,
                    user_roles=[department_role_id],
                    amount=2000,  # Would exceed 5000 limit
                    reason="經濟刺激",
                    month_period="2024-01",
                )

    @pytest.mark.asyncio
    async def test_council_summary_workflow(
        self, service: StateCouncilService, guild_id: int
    ) -> None:
        """Test council summary generation workflow."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup mock data
            config = StateCouncilConfig(
                guild_id=guild_id,
                leader_id=_snowflake(),
                leader_role_id=_snowflake(),
                internal_affairs_account_id=9500000000000001,
                finance_account_id=9500000000000002,
                security_account_id=9500000000000003,
                central_bank_account_id=9500000000000004,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            accounts = [
                GovernmentAccount(
                    account_id=9500000000000001,
                    guild_id=guild_id,
                    department="內政部",
                    balance=8000,
                    created_at=datetime.now(tz=timezone.utc),
                    updated_at=datetime.now(tz=timezone.utc),
                ),
                GovernmentAccount(
                    account_id=9500000000000002,
                    guild_id=guild_id,
                    department="財政部",
                    balance=6000,
                    created_at=datetime.now(tz=timezone.utc),
                    updated_at=datetime.now(tz=timezone.utc),
                ),
                GovernmentAccount(
                    account_id=9500000000000003,
                    guild_id=guild_id,
                    department="國土安全部",
                    balance=4000,
                    created_at=datetime.now(tz=timezone.utc),
                    updated_at=datetime.now(tz=timezone.utc),
                ),
                GovernmentAccount(
                    account_id=9500000000000004,
                    guild_id=guild_id,
                    department="中央銀行",
                    balance=12000,
                    created_at=datetime.now(tz=timezone.utc),
                    updated_at=datetime.now(tz=timezone.utc),
                ),
            ]

            # Mock gateway responses
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = config
            gw.fetch_government_accounts.return_value = accounts
            gw.fetch_interdepartment_transfers.return_value = []
            gw.fetch_welfare_disbursements.return_value = []
            gw.fetch_tax_records.return_value = []
            gw.fetch_identity_records.return_value = []
            gw.fetch_currency_issuances.return_value = []

            # Generate council summary
            summary = await service.get_council_summary(guild_id=guild_id)

            # Verify result
            assert summary.leader_id == config.leader_id
            assert summary.leader_role_id == config.leader_role_id
            assert summary.total_balance == 30000  # Sum of all account balances
            assert len(summary.department_stats) == 4

            # Verify department stats
            for dept_name in ["內政部", "財政部", "國土安全部", "中央銀行"]:
                assert dept_name in summary.department_stats
                dept_stats = summary.department_stats[dept_name]
                assert dept_stats.department == dept_name
                assert dept_stats.balance > 0

    @pytest.mark.asyncio
    async def test_not_configured_scenarios(
        self, service: StateCouncilService, guild_id: int
    ) -> None:
        """Test operations when State Council is not configured."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Mock config not found
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = None

            # Test council summary fails when not configured
            with pytest.raises(StateCouncilNotConfiguredError):
                await service.get_council_summary(guild_id=guild_id)

            # Test permission checks return False when not configured
            result = await service.check_leader_permission(
                guild_id=guild_id, user_id=_snowflake(), user_roles=[]
            )
            assert result is False

            result = await service.check_department_permission(
                guild_id=guild_id, user_id=_snowflake(), department="內政部", user_roles=[]
            )
            assert result is False
