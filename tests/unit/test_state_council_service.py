"""Unit tests for State Council service business logic."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.bot.services.state_council_service import (
    InsufficientFundsError,
    MonthlyIssuanceLimitExceededError,
    PermissionDeniedError,
    StateCouncilNotConfiguredError,
    StateCouncilService,
    StateCouncilSummary,
)
from src.bot.services.transfer_service import InsufficientBalanceError
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


class TestStateCouncilService:
    """Test cases for StateCouncilService."""

    @pytest.fixture
    def mock_gateway(self) -> AsyncMock:
        """Create a mock gateway."""
        return AsyncMock(spec=StateCouncilGovernanceGateway)

    @pytest.fixture
    def mock_transfer_service(self) -> AsyncMock:
        """Create a mock transfer service."""
        return AsyncMock()

    @pytest.fixture
    def service(
        self, mock_gateway: AsyncMock, mock_transfer_service: AsyncMock
    ) -> StateCouncilService:
        """Create service with mocked dependencies."""
        return StateCouncilService(gateway=mock_gateway, transfer_service=mock_transfer_service)

    @pytest.fixture
    def sample_config(self) -> StateCouncilConfig:
        """Sample state council configuration."""
        return StateCouncilConfig(
            guild_id=_snowflake(),
            leader_id=_snowflake(),
            leader_role_id=_snowflake(),
            internal_affairs_account_id=_snowflake(),
            finance_account_id=_snowflake(),
            security_account_id=_snowflake(),
            central_bank_account_id=_snowflake(),
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

    @pytest.fixture
    def sample_department_config(self) -> DepartmentConfig:
        """Sample department configuration."""
        return DepartmentConfig(
            id=_snowflake(),
            guild_id=_snowflake(),
            department="內政部",
            role_id=_snowflake(),
            welfare_amount=1000,
            welfare_interval_hours=24,
            tax_rate_basis=0,
            tax_rate_percent=0,
            max_issuance_per_month=0,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

    @pytest.fixture
    def sample_account(self) -> GovernmentAccount:
        """Sample government account."""
        return GovernmentAccount(
            account_id=_snowflake(),
            guild_id=_snowflake(),
            department="內政部",
            balance=5000,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

    # --- Configuration Tests ---

    @pytest.mark.asyncio
    async def test_derive_department_account_id(self, service: StateCouncilService) -> None:
        """Test department account ID derivation."""
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

    @pytest.mark.asyncio
    async def test_set_config(self, service: StateCouncilService, mock_gateway: MagicMock) -> None:
        """Test state council configuration setup."""
        guild_id = _snowflake()
        leader_id = _snowflake()
        leader_role_id = _snowflake()

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            # Mock gateway methods
            mock_gateway.fetch_government_accounts.return_value = []  # 無既有帳戶時應建立 4 筆
            mock_gateway.upsert_state_council_config.return_value = StateCouncilConfig(
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

            config = await service.set_config(
                guild_id=guild_id,
                leader_id=leader_id,
                leader_role_id=leader_role_id,
            )

            # Verify gateway calls
            assert mock_gateway.upsert_state_council_config.called
            assert mock_gateway.upsert_department_config.call_count == 4  # 4 departments
            assert mock_gateway.upsert_government_account.call_count == 4  # 4 accounts

            # Verify returned config
            assert config.guild_id == guild_id
            assert config.leader_id == leader_id
        assert config.leader_role_id == leader_role_id

    @pytest.mark.asyncio
    async def test_set_config_preserves_existing_accounts(
        self, service: StateCouncilService
    ) -> None:
        """切換領袖時應沿用既有政府帳戶的 account_id 與餘額，不得重建。"""
        from src.db.gateway.state_council_governance import GovernmentAccount, StateCouncilConfig

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)

            guild_id = _snowflake()
            # 預設四個既有部門帳戶（具備餘額）
            existing = [
                GovernmentAccount(
                    _snowflake(),
                    guild_id,
                    "內政部",
                    100,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
                GovernmentAccount(
                    _snowflake(),
                    guild_id,
                    "財政部",
                    200,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
                GovernmentAccount(
                    _snowflake(),
                    guild_id,
                    "國土安全部",
                    300,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
                GovernmentAccount(
                    _snowflake(),
                    guild_id,
                    "中央銀行",
                    400,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
            ]
            gw.fetch_government_accounts.return_value = existing

            leader_id = _snowflake()
            leader_role_id = _snowflake()

            # upsert_state_council_config 回傳值應包含傳入的 account_id（此處用既有值）
            gw.upsert_state_council_config.return_value = StateCouncilConfig(
                guild_id=guild_id,
                leader_id=leader_id,
                leader_role_id=leader_role_id,
                internal_affairs_account_id=existing[0].account_id,
                finance_account_id=existing[1].account_id,
                security_account_id=existing[2].account_id,
                central_bank_account_id=existing[3].account_id,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )

            config = await service.set_config(
                guild_id=guild_id, leader_id=leader_id, leader_role_id=leader_role_id
            )

            # 不應重新建立任何政府帳戶（避免餘額被覆寫/重置）
            gw.upsert_government_account.assert_not_called()
            # 仍會確保部門設定存在
            assert gw.upsert_department_config.call_count == 4

            # 回傳的組態應沿用既有帳戶 ID
            assert config.internal_affairs_account_id == existing[0].account_id
            assert config.finance_account_id == existing[1].account_id
            assert config.security_account_id == existing[2].account_id
            assert config.central_bank_account_id == existing[3].account_id

    @pytest.mark.asyncio
    async def test_get_config_success(
        self, service: StateCouncilService, sample_config: StateCouncilConfig
    ) -> None:
        """Test successful config retrieval."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = sample_config

            config = await service.get_config(guild_id=sample_config.guild_id)
            assert config == sample_config

    @pytest.mark.asyncio
    async def test_get_config_not_found(self, service: StateCouncilService) -> None:
        """Test config retrieval when not configured."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = None

            with pytest.raises(StateCouncilNotConfiguredError):
                await service.get_config(guild_id=_snowflake())

    # --- Permission Tests ---

    @pytest.mark.asyncio
    async def test_check_leader_permission_user_based(
        self, service: StateCouncilService, sample_config: StateCouncilConfig
    ) -> None:
        """Test leader permission check with user-based leadership."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = sample_config

            # Test leader access
            assert sample_config.leader_id is not None
            assert await service.check_leader_permission(
                guild_id=sample_config.guild_id,
                user_id=sample_config.leader_id,
                user_roles=[],
            )

            # Test non-leader access denied
            assert not await service.check_leader_permission(
                guild_id=sample_config.guild_id,
                user_id=_snowflake(),
                user_roles=[],
            )

    @pytest.mark.asyncio
    async def test_check_leader_permission_role_based(
        self, service: StateCouncilService, sample_config: StateCouncilConfig
    ) -> None:
        """Test leader permission check with role-based leadership."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = sample_config

            # Test role-based leader access
            assert sample_config.leader_role_id is not None
            assert await service.check_leader_permission(
                guild_id=sample_config.guild_id,
                user_id=_snowflake(),
                user_roles=[sample_config.leader_role_id],
            )

            # Test wrong role denied
            assert not await service.check_leader_permission(
                guild_id=sample_config.guild_id,
                user_id=_snowflake(),
                user_roles=[_snowflake()],
            )

    @pytest.mark.asyncio
    async def test_check_department_permission_success(
        self, service: StateCouncilService, sample_department_config: DepartmentConfig
    ) -> None:
        """Test successful department permission check."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_department_config.return_value = sample_department_config

            # Test authorized role
            assert sample_department_config.role_id is not None
            assert await service.check_department_permission(
                guild_id=sample_department_config.guild_id,
                user_id=_snowflake(),
                department=sample_department_config.department,
                user_roles=[sample_department_config.role_id],
            )

    @pytest.mark.asyncio
    async def test_check_department_permission_denied(
        self, service: StateCouncilService, sample_department_config: DepartmentConfig
    ) -> None:
        """Test department permission check when denied."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_department_config.return_value = sample_department_config

            # Test unauthorized role
            assert not await service.check_department_permission(
                guild_id=sample_department_config.guild_id,
                user_id=_snowflake(),
                department=sample_department_config.department,
                user_roles=[_snowflake()],
            )

            # Test non-existent department
            gw.fetch_department_config.return_value = None
            assert not await service.check_department_permission(
                guild_id=sample_department_config.guild_id,
                user_id=_snowflake(),
                department="不存在的部門",
                user_roles=[_snowflake()],
            )

    # --- Department Balance Tests ---

    @pytest.mark.asyncio
    async def test_get_department_balance(
        self, service: StateCouncilService, sample_account: GovernmentAccount
    ) -> None:
        """Test getting department balance."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_government_accounts.return_value = [sample_account]

            balance = await service.get_department_balance(
                guild_id=sample_account.guild_id,
                department=sample_account.department,
            )
            assert balance == sample_account.balance

    @pytest.mark.asyncio
    async def test_get_department_balance_not_found(
        self, service: StateCouncilService, sample_account: GovernmentAccount
    ) -> None:
        """Test getting balance for non-existent department."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_government_accounts.return_value = [sample_account]

            balance = await service.get_department_balance(
                guild_id=sample_account.guild_id,
                department="不存在的部門",
            )
            assert balance == 0

    # --- Welfare Disbursement Tests ---

    @pytest.mark.asyncio
    async def test_disburse_welfare_success(
        self, service: StateCouncilService, sample_account: GovernmentAccount
    ) -> None:
        """Test successful welfare disbursement."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup mocks
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_government_accounts.return_value = [sample_account]
            gw.update_account_balance.return_value = None
            gw.create_welfare_disbursement.return_value = WelfareDisbursement(
                disbursement_id=UUID(int=123),
                guild_id=sample_account.guild_id,
                recipient_id=_snowflake(),
                amount=1000,
                disbursement_type="定期福利",
                reference_id=None,
                disbursed_at=datetime.now(tz=timezone.utc),
            )

            with patch.object(service, "check_department_permission", return_value=True):
                result = await service.disburse_welfare(
                    guild_id=sample_account.guild_id,
                    department="內政部",
                    user_id=_snowflake(),
                    user_roles=[_snowflake()],
                    recipient_id=_snowflake(),
                    amount=1000,
                    disbursement_type="定期福利",
                )

            # Verify transfer was called
            cast(AsyncMock, service._transfer.transfer_currency).assert_called_once()
            # Verify balance was updated
            gw.update_account_balance.assert_called_once()
            # Verify disbursement record was created
            gw.create_welfare_disbursement.assert_called_once()

            assert result.amount == 1000

    @pytest.mark.asyncio
    async def test_disburse_welfare_insufficient_funds(
        self, service: StateCouncilService, sample_account: GovernmentAccount
    ) -> None:
        """Test welfare disbursement with insufficient funds."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup account with low balance
            low_balance_account = GovernmentAccount(
                account_id=sample_account.account_id,
                guild_id=sample_account.guild_id,
                department=sample_account.department,
                balance=500,  # Less than amount to disburse
                created_at=sample_account.created_at,
                updated_at=sample_account.updated_at,
            )
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_government_accounts.return_value = [low_balance_account]

            with pytest.raises(InsufficientFundsError):
                await service.disburse_welfare(
                    guild_id=sample_account.guild_id,
                    department="內政部",
                    user_id=_snowflake(),
                    user_roles=[_snowflake()],
                    recipient_id=_snowflake(),
                    amount=1000,  # More than balance
                    disbursement_type="定期福利",
                )

    @pytest.mark.asyncio
    async def test_disburse_welfare_reconciles_when_governance_has_funds(
        self, service: StateCouncilService
    ) -> None:
        """當經濟餘額不足但治理層顯示足夠時，應先對齊再發放成功。"""
        guild_id = _snowflake()
        dept_account = GovernmentAccount(
            account_id=_snowflake(),
            guild_id=guild_id,
            department="內政部",
            balance=2000,  # 治理層顯示 2000
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # 綁定 gateway 回傳帳戶
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_government_accounts.return_value = [dept_account]
            gw.update_account_balance.return_value = None
            gw.create_welfare_disbursement.return_value = WelfareDisbursement(
                disbursement_id=UUID(int=456),
                guild_id=guild_id,
                recipient_id=_snowflake(),
                amount=1000,
                disbursement_type="定期福利",
                reference_id=None,
                disbursed_at=datetime.now(tz=timezone.utc),
            )

            # 模擬經濟帳本餘額只有 100（不足 1000）
            econ = AsyncMock()
            econ.fetch_balance.return_value = MagicMock(balance=100)
            service._economy = econ

            # 注入可觀察的 adjustment 物件
            adjust = AsyncMock()
            service._adjust = adjust

            # 轉帳會被呼叫並回傳新的 initiator_balance
            tx = MagicMock()
            tx.initiator_balance = 1000
            cast(AsyncMock, service._transfer.transfer_currency).return_value = tx

            with patch.object(service, "check_department_permission", return_value=True):
                result = await service.disburse_welfare(
                    guild_id=guild_id,
                    department="內政部",
                    user_id=_snowflake(),
                    user_roles=[_snowflake()],
                    recipient_id=_snowflake(),
                    amount=1000,
                )

            # 應先對齊（從 100 拉到 2000，delta=1900），再成功發放
            adjust.adjust_balance.assert_called_once()
            args, kwargs = adjust.adjust_balance.call_args
            assert kwargs["amount"] == 1900
            cast(AsyncMock, service._transfer.transfer_currency).assert_called_once()
            assert result.amount == 1000

    @pytest.mark.asyncio
    async def test_disburse_welfare_permission_denied(
        self, service: StateCouncilService, sample_account: GovernmentAccount
    ) -> None:
        """Test welfare disbursement with permission denied."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            with patch.object(service, "check_department_permission", return_value=False):
                with pytest.raises(PermissionDeniedError):
                    await service.disburse_welfare(
                        guild_id=sample_account.guild_id,
                        department="內政部",
                        user_id=_snowflake(),
                        user_roles=[_snowflake()],
                        recipient_id=_snowflake(),
                        amount=1000,
                        disbursement_type="定期福利",
                    )

    # --- Tax Collection Tests ---

    @pytest.mark.asyncio
    async def test_collect_tax_success(
        self, service: StateCouncilService, sample_account: GovernmentAccount
    ) -> None:
        """Test successful tax collection."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup mocks
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_government_accounts.return_value = [sample_account]
            gw.update_account_balance.return_value = None
            gw.create_tax_record.return_value = TaxRecord(
                tax_id=UUID(int=123),
                guild_id=sample_account.guild_id,
                taxpayer_id=_snowflake(),
                taxable_amount=10000,
                tax_rate_percent=10,
                tax_amount=1000,
                tax_type="所得稅",
                assessment_period="2024-01",
                collected_at=datetime.now(tz=timezone.utc),
            )

            with patch.object(service, "check_department_permission", return_value=True):
                result = await service.collect_tax(
                    guild_id=sample_account.guild_id,
                    department="財政部",
                    user_id=_snowflake(),
                    user_roles=[_snowflake()],
                    taxpayer_id=_snowflake(),
                    taxable_amount=10000,
                    tax_rate_percent=10,
                    assessment_period="2024-01",
                )

            # Verify transfer was called
            cast(AsyncMock, service._transfer.transfer_currency).assert_called_once()
            # Verify balance was updated
            gw.update_account_balance.assert_called_once()
            # Verify tax record was created
            gw.create_tax_record.assert_called_once()

            assert result.tax_amount == 1000

    # --- Currency Issuance Tests ---

    @pytest.mark.asyncio
    async def test_issue_currency_success(
        self, service: StateCouncilService, sample_account: GovernmentAccount
    ) -> None:
        """Test successful currency issuance."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup mocks
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_department_config.return_value = DepartmentConfig(
                id=_snowflake(),
                guild_id=sample_account.guild_id,
                department="中央銀行",
                role_id=_snowflake(),
                welfare_amount=0,
                welfare_interval_hours=24,
                tax_rate_basis=0,
                tax_rate_percent=0,
                max_issuance_per_month=10000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )
            gw.fetch_government_accounts.return_value = [sample_account]
            gw.sum_monthly_issuance.return_value = 2000  # Already issued this month
            gw.update_account_balance.return_value = None
            gw.create_currency_issuance.return_value = CurrencyIssuance(
                issuance_id=UUID(int=123),
                guild_id=sample_account.guild_id,
                amount=3000,
                reason="經濟刺激",
                performed_by=_snowflake(),
                month_period="2024-01",
                issued_at=datetime.now(tz=timezone.utc),
            )

            with patch.object(service, "check_department_permission", return_value=True):
                result = await service.issue_currency(
                    guild_id=sample_account.guild_id,
                    department="中央銀行",
                    user_id=_snowflake(),
                    user_roles=[_snowflake()],
                    amount=3000,
                    reason="經濟刺激",
                    month_period="2024-01",
                )

            # Verify monthly limit check
            gw.sum_monthly_issuance.assert_called_once()
            # Verify balance was updated
            gw.update_account_balance.assert_called_once()
            # Verify issuance record was created
            gw.create_currency_issuance.assert_called_once()

        assert result.amount == 3000

    # --- Department → User Transfer Tests ---

    @pytest.mark.asyncio
    async def test_transfer_department_to_user_success(self, service: StateCouncilService) -> None:
        guild_id = _snowflake()
        dept_account = GovernmentAccount(
            account_id=_snowflake(),
            guild_id=guild_id,
            department="內政部",
            balance=5000,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_government_accounts.return_value = [dept_account]
            gw.update_account_balance.return_value = None

            # 模擬 DB 成功轉帳並回傳 initiator_balance
            tx_result = MagicMock()
            tx_result.initiator_balance = 4000
            cast(AsyncMock, service._transfer.transfer_currency).return_value = tx_result

            econ = AsyncMock()
            econ.fetch_balance.return_value = MagicMock(balance=5000)
            service._economy = econ

            with patch.object(service, "check_department_permission", return_value=True):
                await service.transfer_department_to_user(
                    guild_id=guild_id,
                    user_id=_snowflake(),
                    user_roles=[_snowflake()],
                    from_department="內政部",
                    recipient_id=_snowflake(),
                    amount=1000,
                    reason="測試",
                )

            # 應更新治理層餘額為 DB 回傳的 initiator_balance
            gw.update_account_balance.assert_called_once()
            _, kwargs = gw.update_account_balance.call_args
            assert kwargs["new_balance"] == 4000

    @pytest.mark.asyncio
    async def test_transfer_department_to_user_insufficient(
        self, service: StateCouncilService
    ) -> None:
        guild_id = _snowflake()
        dept_account = GovernmentAccount(
            account_id=_snowflake(),
            guild_id=guild_id,
            department="內政部",
            balance=500,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_government_accounts.return_value = [dept_account]

            # 模擬 DB 層不足錯誤 → 服務層應轉換為 InsufficientFundsError
            cast(AsyncMock, service._transfer.transfer_currency).side_effect = (
                InsufficientBalanceError("Transfer denied: insufficient funds")
            )

            with patch.object(service, "check_department_permission", return_value=True):
                with pytest.raises(InsufficientFundsError):
                    await service.transfer_department_to_user(
                        guild_id=guild_id,
                        user_id=_snowflake(),
                        user_roles=[_snowflake()],
                        from_department="內政部",
                        recipient_id=_snowflake(),
                        amount=1000,
                        reason="測試",
                    )

    @pytest.mark.asyncio
    async def test_transfer_department_to_user_reconciles_when_governance_has_funds(
        self, service: StateCouncilService
    ) -> None:
        guild_id = _snowflake()
        dept_account = GovernmentAccount(
            account_id=_snowflake(),
            guild_id=guild_id,
            department="內政部",
            balance=1500,  # 治理層足夠
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_government_accounts.return_value = [dept_account]
            gw.update_account_balance.return_value = None

            # 經濟帳本只有 200，不足 1000
            econ = AsyncMock()
            econ.fetch_balance.return_value = MagicMock(balance=200)
            service._economy = econ

            # 注入調整器以觀察被呼叫
            adjust = AsyncMock()
            service._adjust = adjust

            tx = MagicMock()
            tx.initiator_balance = 500
            cast(AsyncMock, service._transfer.transfer_currency).return_value = tx

            with patch.object(service, "check_department_permission", return_value=True):
                await service.transfer_department_to_user(
                    guild_id=guild_id,
                    user_id=_snowflake(),
                    user_roles=[_snowflake()],
                    from_department="內政部",
                    recipient_id=_snowflake(),
                    amount=1000,
                    reason="測試",
                )

            # 會先進行對齊（1500-200=1300）後再轉帳
            adjust.adjust_balance.assert_called_once()
            _, kwargs = adjust.adjust_balance.call_args
            assert kwargs["amount"] == 1300
            cast(AsyncMock, service._transfer.transfer_currency).assert_called_once()

    @pytest.mark.asyncio
    async def test_issue_currency_exceeds_monthly_limit(
        self, service: StateCouncilService, sample_account: GovernmentAccount
    ) -> None:
        """Test currency issuance exceeding monthly limit."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup mocks
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_department_config.return_value = DepartmentConfig(
                id=_snowflake(),
                guild_id=sample_account.guild_id,
                department="中央銀行",
                role_id=_snowflake(),
                welfare_amount=0,
                welfare_interval_hours=24,
                tax_rate_basis=0,
                tax_rate_percent=0,
                max_issuance_per_month=5000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )
            gw.sum_monthly_issuance.return_value = 4000  # Already issued this month

            with pytest.raises(MonthlyIssuanceLimitExceededError):
                await service.issue_currency(
                    guild_id=sample_account.guild_id,
                    department="中央銀行",
                    user_id=_snowflake(),
                    user_roles=[_snowflake()],
                    amount=2000,  # Would exceed 5000 limit
                    reason="經濟刺激",
                    month_period="2024-01",
                )

    # --- Interdepartment Transfer Tests ---

    @pytest.mark.asyncio
    async def test_transfer_between_departments_success(self, service: StateCouncilService) -> None:
        """Test successful interdepartment transfer."""
        guild_id = _snowflake()

        from_account = GovernmentAccount(
            account_id=_snowflake(),
            guild_id=guild_id,
            department="內政部",
            balance=5000,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

        to_account = GovernmentAccount(
            account_id=_snowflake(),
            guild_id=guild_id,
            department="財政部",
            balance=3000,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup mocks
            with patch.object(service, "check_department_permission", return_value=True):
                gw = cast(AsyncMock, service._gateway)
                gw.fetch_government_accounts.return_value = [from_account, to_account]
                gw.update_account_balance.return_value = None
                gw.create_interdepartment_transfer.return_value = InterdepartmentTransfer(
                    transfer_id=UUID(int=123),
                    guild_id=guild_id,
                    from_department="內政部",
                    to_department="財政部",
                    amount=1000,
                    reason="預算調整",
                    performed_by=_snowflake(),
                    transferred_at=datetime.now(tz=timezone.utc),
                )

                result = await service.transfer_between_departments(
                    guild_id=guild_id,
                    user_id=_snowflake(),
                    user_roles=[_snowflake()],
                    from_department="內政部",
                    to_department="財政部",
                    amount=1000,
                    reason="預算調整",
                )

                # Verify transfer was called
                cast(AsyncMock, service._transfer.transfer_currency).assert_called_once()
                # Verify both account balances were updated
                assert gw.update_account_balance.call_count == 2
                # Verify transfer record was created
                gw.create_interdepartment_transfer.assert_called_once()

                assert result.amount == 1000

    @pytest.mark.asyncio
    async def test_transfer_between_departments_insufficient_funds(
        self, service: StateCouncilService
    ) -> None:
        """Test interdepartment transfer with insufficient funds."""
        guild_id = _snowflake()

        from_account = GovernmentAccount(
            account_id=_snowflake(),
            guild_id=guild_id,
            department="內政部",
            balance=500,  # Low balance
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

        to_account = GovernmentAccount(
            account_id=_snowflake(),
            guild_id=guild_id,
            department="財政部",
            balance=3000,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            with patch.object(service, "check_department_permission", return_value=True):
                gw = cast(AsyncMock, service._gateway)
                gw.fetch_government_accounts.return_value = [from_account, to_account]

                with pytest.raises(InsufficientFundsError):
                    await service.transfer_between_departments(
                        guild_id=guild_id,
                        user_id=_snowflake(),
                        user_roles=[_snowflake()],
                        from_department="內政部",
                        to_department="財政部",
                        amount=1000,  # More than balance
                        reason="預算調整",
                    )

    # --- Summary Tests ---

    @pytest.mark.asyncio
    async def test_get_council_summary(
        self, service: StateCouncilService, sample_config: StateCouncilConfig
    ) -> None:
        """Test getting council summary."""
        guild_id = _snowflake()

        accounts = [
            GovernmentAccount(
                account_id=_snowflake(),
                guild_id=guild_id,
                department="內政部",
                balance=5000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            ),
            GovernmentAccount(
                account_id=_snowflake(),
                guild_id=guild_id,
                department="財政部",
                balance=3000,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            ),
        ]

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            # Setup mocks
            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = sample_config
            gw.fetch_government_accounts.return_value = accounts
            gw.fetch_interdepartment_transfers.return_value = []
            gw.fetch_welfare_disbursements.return_value = []
            gw.fetch_tax_records.return_value = []
            gw.fetch_identity_records.return_value = []
            gw.fetch_currency_issuances.return_value = []

            summary = await service.get_council_summary(guild_id=guild_id)

            assert isinstance(summary, StateCouncilSummary)
            assert summary.leader_id == sample_config.leader_id
            assert summary.leader_role_id == sample_config.leader_role_id
            assert summary.total_balance == 8000  # Sum of account balances
            assert len(summary.department_stats) == 2
            assert "內政部" in summary.department_stats
            assert "財政部" in summary.department_stats

    @pytest.mark.asyncio
    async def test_get_council_summary_not_configured(self, service: StateCouncilService) -> None:
        """Test getting council summary when not configured."""
        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = None

            with pytest.raises(StateCouncilNotConfiguredError):
                await service.get_council_summary(guild_id=_snowflake())

    # --- Account Synchronization Tests ---

    @pytest.mark.asyncio
    async def test_ensure_government_accounts_all_exist(
        self, service: StateCouncilService, sample_config: StateCouncilConfig
    ) -> None:
        """測試所有帳戶存在時不執行建立。"""
        guild_id = sample_config.guild_id
        admin_id = _snowflake()

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_tx = AsyncMock()
            mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
            mock_tx.__aexit__ = AsyncMock(return_value=None)
            mock_conn.transaction.return_value = mock_tx
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = sample_config

            # 所有四個部門帳戶都存在
            existing_accounts = [
                GovernmentAccount(
                    sample_config.internal_affairs_account_id,
                    guild_id,
                    "內政部",
                    1000,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
                GovernmentAccount(
                    sample_config.finance_account_id,
                    guild_id,
                    "財政部",
                    2000,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
                GovernmentAccount(
                    sample_config.security_account_id,
                    guild_id,
                    "國土安全部",
                    3000,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
                GovernmentAccount(
                    sample_config.central_bank_account_id,
                    guild_id,
                    "中央銀行",
                    4000,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
            ]
            gw.fetch_government_accounts.return_value = existing_accounts

            # Mock 經濟系統查詢
            econ = AsyncMock()
            econ.fetch_balance.return_value = MagicMock(balance=1000)
            service._economy = econ

            await service.ensure_government_accounts(guild_id=guild_id, admin_id=admin_id)

            # 不應建立新帳戶
            gw.upsert_government_account.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_government_accounts_partial_missing(
        self, service: StateCouncilService, sample_config: StateCouncilConfig
    ) -> None:
        """測試部分帳戶缺失時僅建立缺失者。"""
        guild_id = sample_config.guild_id
        admin_id = _snowflake()

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_tx = AsyncMock()
            mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
            mock_tx.__aexit__ = AsyncMock(return_value=None)
            mock_conn.transaction.return_value = mock_tx
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = sample_config

            # 只有兩個部門帳戶存在（缺少財政部和中央銀行）
            existing_accounts = [
                GovernmentAccount(
                    sample_config.internal_affairs_account_id,
                    guild_id,
                    "內政部",
                    1000,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
                GovernmentAccount(
                    sample_config.security_account_id,
                    guild_id,
                    "國土安全部",
                    3000,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
            ]
            gw.fetch_government_accounts.return_value = existing_accounts

            # Mock 經濟系統查詢（為缺失的帳戶返回餘額）
            econ = AsyncMock()
            econ.fetch_balance.side_effect = [
                MagicMock(balance=1000),  # 內政部（已存在，檢查餘額同步）
                MagicMock(balance=2500),  # 財政部（缺失，建立時使用）
                MagicMock(balance=3000),  # 國土安全部（已存在，檢查餘額同步）
                MagicMock(balance=4500),  # 中央銀行（缺失，建立時使用）
            ]
            service._economy = econ

            # Mock upsert_government_account 回傳值
            gw.upsert_government_account.side_effect = [
                GovernmentAccount(
                    sample_config.finance_account_id,
                    guild_id,
                    "財政部",
                    2500,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
                GovernmentAccount(
                    sample_config.central_bank_account_id,
                    guild_id,
                    "中央銀行",
                    4500,
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
            ]

            await service.ensure_government_accounts(guild_id=guild_id, admin_id=admin_id)

            # 應建立兩個缺失的帳戶
            assert gw.upsert_government_account.call_count == 2

            # 驗證建立的帳戶使用配置中的 account_id
            calls = gw.upsert_government_account.call_args_list
            created_depts = {call.kwargs["department"] for call in calls}
            assert "財政部" in created_depts
            assert "中央銀行" in created_depts

            # 驗證使用配置中的 account_id
            finance_call = next(c for c in calls if c.kwargs["department"] == "財政部")
            assert finance_call.kwargs["account_id"] == sample_config.finance_account_id
            assert finance_call.kwargs["balance"] == 2500

            central_bank_call = next(c for c in calls if c.kwargs["department"] == "中央銀行")
            assert central_bank_call.kwargs["account_id"] == sample_config.central_bank_account_id
            assert central_bank_call.kwargs["balance"] == 4500

    @pytest.mark.asyncio
    async def test_ensure_government_accounts_syncs_balance(
        self, service: StateCouncilService, sample_config: StateCouncilConfig
    ) -> None:
        """測試餘額同步邏輯正確。"""
        guild_id = sample_config.guild_id
        admin_id = _snowflake()

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_tx = AsyncMock()
            mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
            mock_tx.__aexit__ = AsyncMock(return_value=None)
            mock_conn.transaction.return_value = mock_tx
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = sample_config

            # 帳戶存在但餘額不一致（治理層 1000，經濟系統 1500）
            existing_accounts = [
                GovernmentAccount(
                    sample_config.internal_affairs_account_id,
                    guild_id,
                    "內政部",
                    1000,  # 治理層餘額
                    datetime.now(tz=timezone.utc),
                    datetime.now(tz=timezone.utc),
                ),
            ]
            gw.fetch_government_accounts.return_value = existing_accounts

            # Mock 經濟系統查詢返回更高的餘額
            econ = AsyncMock()
            econ.fetch_balance.return_value = MagicMock(balance=1500)  # 經濟系統餘額
            service._economy = econ

            await service.ensure_government_accounts(guild_id=guild_id, admin_id=admin_id)

            # 應更新治理層餘額以匹配經濟系統
            gw.update_account_balance.assert_called_once()
            call = gw.update_account_balance.call_args
            assert call.kwargs["account_id"] == sample_config.internal_affairs_account_id
            assert call.kwargs["new_balance"] == 1500

    @pytest.mark.asyncio
    async def test_ensure_government_accounts_not_configured(
        self, service: StateCouncilService
    ) -> None:
        """測試未配置時拋出錯誤。"""
        guild_id = _snowflake()
        admin_id = _snowflake()

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = None  # 未配置

            with pytest.raises(StateCouncilNotConfiguredError):
                await service.ensure_government_accounts(guild_id=guild_id, admin_id=admin_id)

    @pytest.mark.asyncio
    async def test_ensure_government_accounts_economy_query_failure(
        self, service: StateCouncilService, sample_config: StateCouncilConfig
    ) -> None:
        """測試經濟系統查詢失敗時使用 0 作為初始餘額。"""
        guild_id = sample_config.guild_id
        admin_id = _snowflake()

        with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_tx = AsyncMock()
            mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
            mock_tx.__aexit__ = AsyncMock(return_value=None)
            mock_conn.transaction.return_value = mock_tx
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_get_pool.return_value = mock_pool

            gw = cast(AsyncMock, service._gateway)
            gw.fetch_state_council_config.return_value = sample_config
            gw.fetch_government_accounts.return_value = []  # 無現有帳戶

            # Mock 經濟系統查詢失敗
            econ = AsyncMock()
            econ.fetch_balance.side_effect = Exception("Database error")
            service._economy = econ

            # Mock upsert_government_account 回傳值
            gw.upsert_government_account.return_value = GovernmentAccount(
                sample_config.internal_affairs_account_id,
                guild_id,
                "內政部",
                0,
                datetime.now(tz=timezone.utc),
                datetime.now(tz=timezone.utc),
            )

            await service.ensure_government_accounts(guild_id=guild_id, admin_id=admin_id)

            # 應建立四個帳戶，每個餘額為 0（因為經濟系統查詢失敗）
            assert gw.upsert_government_account.call_count == 4
            for call in gw.upsert_government_account.call_args_list:
                assert call.kwargs["balance"] == 0
