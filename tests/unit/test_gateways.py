"""Unit tests for low-coverage gateway modules."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import asyncpg
import pytest

from src.db.gateway.business_license import BusinessLicense, BusinessLicenseGateway
from src.db.gateway.company import Company, CompanyGateway
from src.db.gateway.council_governance import (
    CouncilConfig,
    CouncilGovernanceGateway,
    Proposal,
    Tally,
)
from src.db.gateway.economy_configuration import (
    CurrencyConfig,
    EconomyConfigurationGateway,
)
from src.db.gateway.justice_governance import JusticeGovernanceGateway, Suspect
from src.db.gateway.state_council_governance import (
    CurrencyIssuance,
    DepartmentConfig,
    GovernmentAccount,
    IdentityRecord,
    InterdepartmentTransfer,
    StateCouncilConfig,
    StateCouncilGovernanceGateway,
    TaxRecord,
    WelfareDisbursement,
)


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


# --- EconomyConfigurationGateway Tests ---


@pytest.mark.unit
class TestEconomyConfigurationGateway:
    """Test cases for EconomyConfigurationGateway."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def gateway(self) -> EconomyConfigurationGateway:
        """Create gateway instance."""
        return EconomyConfigurationGateway()

    @pytest.fixture
    def sample_currency_config(self) -> dict[str, Any]:
        """Sample currency configuration data."""
        return {
            "guild_id": _snowflake(),
            "currency_name": "金幣",
            "currency_icon": "💰",
        }

    @pytest.mark.asyncio
    async def test_get_currency_config_success(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
        sample_currency_config: dict[str, Any],
    ) -> None:
        """Test successful currency config retrieval."""
        mock_connection.fetchrow.return_value = sample_currency_config

        config = await gateway.get_currency_config(
            mock_connection, guild_id=sample_currency_config["guild_id"]
        )

        assert config is not None
        assert isinstance(config, CurrencyConfig)
        assert config.guild_id == sample_currency_config["guild_id"]
        assert config.currency_name == sample_currency_config["currency_name"]
        assert config.currency_icon == sample_currency_config["currency_icon"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_currency_config_not_found(
        self, gateway: EconomyConfigurationGateway, mock_connection: AsyncMock
    ) -> None:
        """Test currency config not found."""
        mock_connection.fetchrow.return_value = None

        config = await gateway.get_currency_config(mock_connection, guild_id=_snowflake())

        assert config is None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_currency_config_create_new(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
        sample_currency_config: dict[str, Any],
    ) -> None:
        """Test creating new currency config."""
        guild_id = sample_currency_config["guild_id"]
        mock_connection.fetchrow.side_effect = [
            None,  # get_currency_config returns None (doesn't exist)
            sample_currency_config,  # INSERT returns new config
        ]

        config = await gateway.update_currency_config(
            mock_connection,
            guild_id=guild_id,
            currency_name="金幣",
            currency_icon="💰",
        )

        assert isinstance(config, CurrencyConfig)
        assert config.guild_id == guild_id
        assert mock_connection.fetchrow.call_count == 2

    @pytest.mark.asyncio
    async def test_update_currency_config_update_existing(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
        sample_currency_config: dict[str, Any],
    ) -> None:
        """Test updating existing currency config."""
        guild_id = sample_currency_config["guild_id"]
        existing_config = sample_currency_config.copy()
        updated_config = sample_currency_config.copy()
        updated_config["currency_name"] = "新幣"

        mock_connection.fetchrow.side_effect = [
            existing_config,  # get_currency_config returns existing
            updated_config,  # UPDATE returns updated config
        ]

        config = await gateway.update_currency_config(
            mock_connection,
            guild_id=guild_id,
            currency_name="新幣",
        )

        assert isinstance(config, CurrencyConfig)
        assert config.currency_name == "新幣"
        assert mock_connection.fetchrow.call_count == 2

    @pytest.mark.asyncio
    async def test_update_currency_config_no_changes(
        self,
        gateway: EconomyConfigurationGateway,
        mock_connection: AsyncMock,
        sample_currency_config: dict[str, Any],
    ) -> None:
        """Test update with no changes returns existing."""
        existing = CurrencyConfig(
            guild_id=sample_currency_config["guild_id"],
            currency_name=sample_currency_config["currency_name"],
            currency_icon=sample_currency_config["currency_icon"],
        )
        mock_connection.fetchrow.return_value = sample_currency_config

        config = await gateway.update_currency_config(
            mock_connection,
            guild_id=existing.guild_id,
            currency_name=None,
            currency_icon=None,
        )

        assert config == existing
        # Only called once for get_currency_config
        mock_connection.fetchrow.assert_called_once()


# --- JusticeGovernanceGateway Tests ---


@pytest.mark.unit
class TestJusticeGovernanceGateway:
    """Test cases for JusticeGovernanceGateway."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def gateway(self) -> JusticeGovernanceGateway:
        """Create gateway instance."""
        return JusticeGovernanceGateway()

    @pytest.fixture
    def sample_suspect(self) -> dict[str, Any]:
        """Sample suspect data."""
        return {
            "suspect_id": 1,
            "guild_id": _snowflake(),
            "member_id": _snowflake(),
            "arrested_by": _snowflake(),
            "arrest_reason": "測試拘捕",
            "status": "detained",
            "arrested_at": datetime.now(timezone.utc),
            "charged_at": None,
            "released_at": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    @pytest.mark.asyncio
    async def test_create_suspect(
        self,
        gateway: JusticeGovernanceGateway,
        mock_connection: AsyncMock,
        sample_suspect: dict[str, Any],
    ) -> None:
        """Test creating suspect record."""
        mock_connection.fetchrow.return_value = sample_suspect

        suspect = await gateway.create_suspect(
            mock_connection,
            guild_id=sample_suspect["guild_id"],
            member_id=sample_suspect["member_id"],
            arrested_by=sample_suspect["arrested_by"],
            arrest_reason=sample_suspect["arrest_reason"],
        )

        assert isinstance(suspect, Suspect)
        assert suspect.guild_id == sample_suspect["guild_id"]
        assert suspect.member_id == sample_suspect["member_id"]
        assert suspect.status == "detained"
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_suspects(
        self,
        gateway: JusticeGovernanceGateway,
        mock_connection: AsyncMock,
        sample_suspect: dict[str, Any],
    ) -> None:
        """Test getting active suspects with pagination."""
        mock_connection.fetch.return_value = [sample_suspect]

        suspects = await gateway.get_active_suspects(
            mock_connection, guild_id=sample_suspect["guild_id"], limit=10, offset=0
        )

        assert len(suspects) == 1
        assert isinstance(suspects[0], Suspect)
        assert suspects[0].status == "detained"
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_suspect_by_member(
        self,
        gateway: JusticeGovernanceGateway,
        mock_connection: AsyncMock,
        sample_suspect: dict[str, Any],
    ) -> None:
        """Test getting suspect by member ID."""
        mock_connection.fetchrow.return_value = sample_suspect

        suspect = await gateway.get_suspect_by_member(
            mock_connection,
            guild_id=sample_suspect["guild_id"],
            member_id=sample_suspect["member_id"],
        )

        assert suspect is not None
        assert isinstance(suspect, Suspect)
        assert suspect.member_id == sample_suspect["member_id"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_suspect_by_member_not_found(
        self, gateway: JusticeGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test suspect not found by member ID."""
        mock_connection.fetchrow.return_value = None

        suspect = await gateway.get_suspect_by_member(
            mock_connection, guild_id=_snowflake(), member_id=_snowflake()
        )

        assert suspect is None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_charge_suspect(
        self,
        gateway: JusticeGovernanceGateway,
        mock_connection: AsyncMock,
        sample_suspect: dict[str, Any],
    ) -> None:
        """Test charging a suspect."""
        charged = sample_suspect.copy()
        charged["status"] = "charged"
        charged["charged_at"] = datetime.now(timezone.utc)
        mock_connection.fetchrow.return_value = charged

        suspect = await gateway.charge_suspect(mock_connection, suspect_id=1)

        assert isinstance(suspect, Suspect)
        assert suspect.status == "charged"
        assert suspect.charged_at is not None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_charge_suspect_not_found(
        self, gateway: JusticeGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test charging non-existent suspect raises error."""
        mock_connection.fetchrow.return_value = None

        with pytest.raises(ValueError, match="not found or already charged"):
            await gateway.charge_suspect(mock_connection, suspect_id=999)

    @pytest.mark.asyncio
    async def test_revoke_charge(
        self,
        gateway: JusticeGovernanceGateway,
        mock_connection: AsyncMock,
        sample_suspect: dict[str, Any],
    ) -> None:
        """Test revoking a charge."""
        revoked = sample_suspect.copy()
        revoked["status"] = "detained"
        revoked["charged_at"] = None
        mock_connection.fetchrow.return_value = revoked

        suspect = await gateway.revoke_charge(mock_connection, suspect_id=1)

        assert isinstance(suspect, Suspect)
        assert suspect.status == "detained"
        assert suspect.charged_at is None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_suspect(
        self,
        gateway: JusticeGovernanceGateway,
        mock_connection: AsyncMock,
        sample_suspect: dict[str, Any],
    ) -> None:
        """Test releasing a suspect."""
        released = sample_suspect.copy()
        released["status"] = "released"
        released["released_at"] = datetime.now(timezone.utc)
        mock_connection.fetchrow.return_value = released

        suspect = await gateway.release_suspect(mock_connection, suspect_id=1)

        assert isinstance(suspect, Suspect)
        assert suspect.status == "released"
        assert suspect.released_at is not None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_suspect_record(
        self,
        gateway: JusticeGovernanceGateway,
        mock_connection: AsyncMock,
        sample_suspect: dict[str, Any],
    ) -> None:
        """Test getting latest suspect record."""
        mock_connection.fetchrow.return_value = sample_suspect

        suspect = await gateway.get_latest_suspect_record(
            mock_connection,
            guild_id=sample_suspect["guild_id"],
            member_id=sample_suspect["member_id"],
        )

        assert suspect is not None
        assert isinstance(suspect, Suspect)
        mock_connection.fetchrow.assert_called_once()


# --- StateCouncilGovernanceGateway Tests ---


@pytest.mark.unit
class TestStateCouncilGovernanceGateway:
    """Test cases for StateCouncilGovernanceGateway."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def gateway(self) -> StateCouncilGovernanceGateway:
        """Create gateway instance."""
        return StateCouncilGovernanceGateway()

    @pytest.fixture
    def sample_config(self) -> dict[str, Any]:
        """Sample state council config data."""
        return {
            "guild_id": _snowflake(),
            "leader_id": _snowflake(),
            "leader_role_id": _snowflake(),
            "internal_affairs_account_id": _snowflake(),
            "finance_account_id": _snowflake(),
            "security_account_id": _snowflake(),
            "central_bank_account_id": _snowflake(),
            "treasury_account_id": _snowflake(),
            "welfare_account_id": _snowflake(),
            "auto_release_hours": 24,
            "citizen_role_id": _snowflake(),
            "suspect_role_id": _snowflake(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    @pytest.mark.asyncio
    async def test_upsert_state_council_config(
        self,
        gateway: StateCouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_config: dict[str, Any],
    ) -> None:
        """Test upserting state council config."""
        mock_connection.fetchrow.return_value = sample_config

        config = await gateway.upsert_state_council_config(
            mock_connection,
            guild_id=sample_config["guild_id"],
            leader_id=sample_config["leader_id"],
            leader_role_id=sample_config["leader_role_id"],
            internal_affairs_account_id=sample_config["internal_affairs_account_id"],
            finance_account_id=sample_config["finance_account_id"],
            security_account_id=sample_config["security_account_id"],
            central_bank_account_id=sample_config["central_bank_account_id"],
        )

        assert isinstance(config, StateCouncilConfig)
        assert config.guild_id == sample_config["guild_id"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_state_council_config(
        self,
        gateway: StateCouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_config: dict[str, Any],
    ) -> None:
        """Test fetching state council config."""
        mock_connection.fetchrow.return_value = sample_config

        config = await gateway.fetch_state_council_config(
            mock_connection, guild_id=sample_config["guild_id"]
        )

        assert config is not None
        assert isinstance(config, StateCouncilConfig)
        assert config.guild_id == sample_config["guild_id"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_state_council_config_not_found(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching non-existent config."""
        mock_connection.fetchrow.return_value = None

        config = await gateway.fetch_state_council_config(mock_connection, guild_id=_snowflake())

        assert config is None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_department_config(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test upserting department config."""
        dept_config = {
            "id": 1,
            "guild_id": _snowflake(),
            "department": "內政部",
            "role_id": _snowflake(),
            "welfare_amount": 100,
            "welfare_interval_hours": 24,
            "tax_rate_basis": 1000,
            "tax_rate_percent": 10,
            "max_issuance_per_month": 10000,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        mock_connection.fetchrow.return_value = dept_config

        config = await gateway.upsert_department_config(
            mock_connection,
            guild_id=dept_config["guild_id"],
            department="內政部",
            role_id=dept_config["role_id"],
        )

        assert isinstance(config, DepartmentConfig)
        assert config.department == "內政部"
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_department_configs(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching department configs."""
        dept_config = {
            "id": 1,
            "guild_id": _snowflake(),
            "department": "內政部",
            "role_id": _snowflake(),
            "welfare_amount": 100,
            "welfare_interval_hours": 24,
            "tax_rate_basis": 1000,
            "tax_rate_percent": 10,
            "max_issuance_per_month": 10000,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        mock_connection.fetch.return_value = [dept_config]

        configs = await gateway.fetch_department_configs(
            mock_connection, guild_id=dept_config["guild_id"]
        )

        assert len(configs) == 1
        assert isinstance(configs[0], DepartmentConfig)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_welfare_disbursement(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test creating welfare disbursement."""
        disbursement = {
            "disbursement_id": 1,
            "guild_id": _snowflake(),
            "recipient_id": _snowflake(),
            "amount": 100,
            "disbursement_type": "定期福利",
            "reference_id": None,
            "disbursed_at": datetime.now(timezone.utc),
        }
        mock_connection.fetchrow.return_value = disbursement

        result = await gateway.create_welfare_disbursement(
            mock_connection,
            guild_id=disbursement["guild_id"],
            recipient_id=disbursement["recipient_id"],
            amount=100,
        )

        assert isinstance(result, WelfareDisbursement)
        assert result.amount == 100
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_tax_record(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test creating tax record."""
        tax_record = {
            "tax_id": 1,
            "guild_id": _snowflake(),
            "taxpayer_id": _snowflake(),
            "taxable_amount": 1000,
            "tax_rate_percent": 10,
            "tax_amount": 100,
            "tax_type": "所得稅",
            "assessment_period": "2024-01",
            "collected_at": datetime.now(timezone.utc),
        }
        mock_connection.fetchrow.return_value = tax_record

        result = await gateway.create_tax_record(
            mock_connection,
            guild_id=tax_record["guild_id"],
            taxpayer_id=tax_record["taxpayer_id"],
            taxable_amount=1000,
            tax_rate_percent=10,
            tax_amount=100,
            assessment_period="2024-01",
        )

        assert isinstance(result, TaxRecord)
        assert result.tax_amount == 100
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_currency_issuance(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test creating currency issuance."""
        issuance = {
            "issuance_id": 1,
            "guild_id": _snowflake(),
            "amount": 5000,
            "reason": "測試發行",
            "performed_by": _snowflake(),
            "month_period": "2024-01",
            "issued_at": datetime.now(timezone.utc),
        }
        mock_connection.fetchrow.return_value = issuance

        result = await gateway.create_currency_issuance(
            mock_connection,
            guild_id=issuance["guild_id"],
            amount=5000,
            reason="測試發行",
            performed_by=issuance["performed_by"],
            month_period="2024-01",
        )

        assert isinstance(result, CurrencyIssuance)
        assert result.amount == 5000
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_interdepartment_transfer(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test creating interdepartment transfer."""
        transfer = {
            "transfer_id": 1,
            "guild_id": _snowflake(),
            "from_department": "財政部",
            "to_department": "內政部",
            "amount": 1000,
            "reason": "測試轉帳",
            "performed_by": _snowflake(),
            "transferred_at": datetime.now(timezone.utc),
        }
        mock_connection.fetchrow.return_value = transfer

        result = await gateway.create_interdepartment_transfer(
            mock_connection,
            guild_id=transfer["guild_id"],
            from_department="財政部",
            to_department="內政部",
            amount=1000,
            reason="測試轉帳",
            performed_by=transfer["performed_by"],
        )

        assert isinstance(result, InterdepartmentTransfer)
        assert result.amount == 1000
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_department_permission(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test checking department permission."""
        dept_config = {
            "id": 1,
            "guild_id": _snowflake(),
            "department": "內政部",
            "role_id": 123456,
            "welfare_amount": 100,
            "welfare_interval_hours": 24,
            "tax_rate_basis": 1000,
            "tax_rate_percent": 10,
            "max_issuance_per_month": 10000,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        mock_connection.fetchrow.return_value = dept_config

        has_permission = await gateway.check_department_permission(
            mock_connection,
            guild_id=dept_config["guild_id"],
            department="內政部",
            user_roles=[123456, 789012],
        )

        assert has_permission is True
        mock_connection.fetchrow.assert_called_once()


# --- CompanyGateway Tests ---


@pytest.mark.unit
class TestCompanyGateway:
    """Test cases for CompanyGateway."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def gateway(self) -> CompanyGateway:
        """Create gateway instance."""
        return CompanyGateway()

    @pytest.fixture
    def sample_company(self) -> dict[str, Any]:
        """Sample company data."""
        return {
            "id": 1,
            "guild_id": _snowflake(),
            "owner_id": _snowflake(),
            "license_id": UUID(int=123),
            "name": "測試公司",
            "account_id": _snowflake(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "license_type": "一般商業",
            "license_status": "active",
        }

    @pytest.mark.asyncio
    async def test_create_company(
        self,
        gateway: CompanyGateway,
        mock_connection: AsyncMock,
        sample_company: dict[str, Any],
    ) -> None:
        """Test creating company."""
        mock_connection.fetchrow.return_value = sample_company

        result = await gateway.create_company(
            mock_connection,
            guild_id=sample_company["guild_id"],
            owner_id=sample_company["owner_id"],
            license_id=sample_company["license_id"],
            name=sample_company["name"],
            account_id=sample_company["account_id"],
        )

        assert result.is_ok()
        company = result.unwrap()
        assert isinstance(company, Company)
        assert company.name == sample_company["name"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_company(
        self,
        gateway: CompanyGateway,
        mock_connection: AsyncMock,
        sample_company: dict[str, Any],
    ) -> None:
        """Test getting company by ID."""
        mock_connection.fetchrow.return_value = sample_company

        result = await gateway.get_company(mock_connection, company_id=1)

        assert result.is_ok()
        company = result.unwrap()
        assert company is not None
        assert isinstance(company, Company)
        assert company.id == 1
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_company_by_account(
        self,
        gateway: CompanyGateway,
        mock_connection: AsyncMock,
        sample_company: dict[str, Any],
    ) -> None:
        """Test getting company by account ID."""
        mock_connection.fetchrow.return_value = sample_company

        result = await gateway.get_company_by_account(
            mock_connection, account_id=sample_company["account_id"]
        )

        assert result.is_ok()
        company = result.unwrap()
        assert company is not None
        assert isinstance(company, Company)
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_user_companies(
        self,
        gateway: CompanyGateway,
        mock_connection: AsyncMock,
        sample_company: dict[str, Any],
    ) -> None:
        """Test listing user companies."""
        mock_connection.fetch.return_value = [sample_company]

        result = await gateway.list_user_companies(
            mock_connection,
            guild_id=sample_company["guild_id"],
            owner_id=sample_company["owner_id"],
        )

        assert result.is_ok()
        companies = result.unwrap()
        assert len(companies) == 1
        assert isinstance(companies[0], Company)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_ownership_true(
        self, gateway: CompanyGateway, mock_connection: AsyncMock
    ) -> None:
        """Test checking company ownership returns true."""
        mock_connection.fetchrow.return_value = [True]

        result = await gateway.check_ownership(mock_connection, company_id=1, user_id=_snowflake())

        assert result.is_ok()
        assert result.unwrap() is True
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_license_valid(
        self, gateway: CompanyGateway, mock_connection: AsyncMock
    ) -> None:
        """Test checking license validity."""
        mock_connection.fetchrow.return_value = [True]

        result = await gateway.check_license_valid(mock_connection, company_id=1)

        assert result.is_ok()
        assert result.unwrap() is True
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_derive_account_id(self, gateway: CompanyGateway) -> None:
        """Test deriving account ID."""
        guild_id = _snowflake()
        company_id = 123

        account_id = gateway.derive_account_id(guild_id, company_id)

        # Should be base + company_id
        expected = 9_600_000_000_000_000 + company_id
        assert account_id == expected


# --- CouncilGovernanceGateway Tests ---


@pytest.mark.unit
class TestCouncilGovernanceGateway:
    """Test cases for CouncilGovernanceGateway."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def gateway(self) -> CouncilGovernanceGateway:
        """Create gateway instance."""
        return CouncilGovernanceGateway()

    @pytest.fixture
    def sample_config(self) -> dict[str, Any]:
        """Sample council config data."""
        return {
            "guild_id": _snowflake(),
            "council_role_id": _snowflake(),
            "council_account_member_id": _snowflake(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    @pytest.fixture
    def sample_proposal(self) -> dict[str, Any]:
        """Sample proposal data."""
        return {
            "proposal_id": UUID(int=123),
            "guild_id": _snowflake(),
            "proposer_id": _snowflake(),
            "target_id": _snowflake(),
            "amount": 1000,
            "description": "測試提案",
            "attachment_url": None,
            "snapshot_n": 5,
            "threshold_t": 3,
            "deadline_at": datetime.now(timezone.utc),
            "status": "進行中",
            "reminder_sent": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "target_department_id": None,
        }

    @pytest.mark.asyncio
    async def test_upsert_config(
        self,
        gateway: CouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_config: dict[str, Any],
    ) -> None:
        """Test upserting council config."""
        mock_connection.fetchrow.return_value = sample_config

        config = await gateway.upsert_config(
            mock_connection,
            guild_id=sample_config["guild_id"],
            council_role_id=sample_config["council_role_id"],
            council_account_member_id=sample_config["council_account_member_id"],
        )

        assert isinstance(config, CouncilConfig)
        assert config.guild_id == sample_config["guild_id"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_config(
        self,
        gateway: CouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_config: dict[str, Any],
    ) -> None:
        """Test fetching council config."""
        mock_connection.fetchrow.return_value = sample_config

        config = await gateway.fetch_config(mock_connection, guild_id=sample_config["guild_id"])

        assert config is not None
        assert isinstance(config, CouncilConfig)
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_config_not_found(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching non-existent config."""
        mock_connection.fetchrow.return_value = None

        config = await gateway.fetch_config(mock_connection, guild_id=_snowflake())

        assert config is None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_proposal(
        self,
        gateway: CouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_proposal: dict[str, Any],
    ) -> None:
        """Test creating proposal."""
        mock_connection.fetchrow.return_value = sample_proposal

        proposal = await gateway.create_proposal(
            mock_connection,
            guild_id=sample_proposal["guild_id"],
            proposer_id=sample_proposal["proposer_id"],
            target_id=sample_proposal["target_id"],
            amount=1000,
            description="測試提案",
            attachment_url=None,
            snapshot_member_ids=[1, 2, 3, 4, 5],
        )

        assert isinstance(proposal, Proposal)
        assert proposal.amount == 1000
        mock_connection.fetchrow.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_proposal(
        self,
        gateway: CouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_proposal: dict[str, Any],
    ) -> None:
        """Test fetching proposal."""
        mock_connection.fetchrow.return_value = sample_proposal

        proposal = await gateway.fetch_proposal(
            mock_connection, proposal_id=sample_proposal["proposal_id"]
        )

        assert proposal is not None
        assert isinstance(proposal, Proposal)
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_tally(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching vote tally."""
        tally_data = {
            "approve": 3,
            "reject": 1,
            "abstain": 1,
            "total_voted": 5,
        }
        mock_connection.fetchrow.return_value = tally_data

        tally = await gateway.fetch_tally(mock_connection, proposal_id=UUID(int=123))

        assert isinstance(tally, Tally)
        assert tally.approve == 3
        assert tally.total_voted == 5
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_vote(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test upserting vote."""
        await gateway.upsert_vote(
            mock_connection,
            proposal_id=UUID(int=123),
            voter_id=_snowflake(),
            choice="approve",
        )

        mock_connection.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_proposal(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test canceling proposal."""
        mock_connection.fetchval.return_value = True

        result = await gateway.cancel_proposal(mock_connection, proposal_id=UUID(int=123))

        assert result is True
        mock_connection.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_council_role(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test adding council role."""
        mock_connection.fetchval.return_value = True

        result = await gateway.add_council_role(
            mock_connection, guild_id=_snowflake(), role_id=_snowflake()
        )

        assert result is True
        mock_connection.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_council_role(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test removing council role."""
        mock_connection.fetchval.return_value = True

        result = await gateway.remove_council_role(
            mock_connection, guild_id=_snowflake(), role_id=_snowflake()
        )

        assert result is True
        mock_connection.fetchval.assert_called_once()


# --- BusinessLicenseGateway Tests ---


@pytest.mark.unit
class TestBusinessLicenseGateway:
    """Test cases for BusinessLicenseGateway."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def gateway(self) -> BusinessLicenseGateway:
        """Create gateway instance."""
        return BusinessLicenseGateway()

    @pytest.fixture
    def sample_license(self) -> dict[str, Any]:
        """Sample business license data."""
        return {
            "license_id": UUID(int=123),
            "guild_id": _snowflake(),
            "user_id": _snowflake(),
            "license_type": "一般商業",
            "issued_by": _snowflake(),
            "issued_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc),
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "revoked_by": None,
            "revoked_at": None,
            "revoke_reason": None,
        }

    @pytest.mark.asyncio
    async def test_issue_license(
        self,
        gateway: BusinessLicenseGateway,
        mock_connection: AsyncMock,
        sample_license: dict[str, Any],
    ) -> None:
        """Test issuing business license."""
        mock_connection.fetchrow.return_value = sample_license

        result = await gateway.issue_license(
            mock_connection,
            guild_id=sample_license["guild_id"],
            user_id=sample_license["user_id"],
            license_type="一般商業",
            issued_by=sample_license["issued_by"],
            expires_at=sample_license["expires_at"],
        )

        assert result.is_ok()
        license = result.unwrap()
        assert isinstance(license, BusinessLicense)
        assert license.status == "active"
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_license(
        self,
        gateway: BusinessLicenseGateway,
        mock_connection: AsyncMock,
        sample_license: dict[str, Any],
    ) -> None:
        """Test revoking business license."""
        revoked = sample_license.copy()
        revoked["status"] = "revoked"
        revoked["revoked_by"] = _snowflake()
        revoked["revoke_reason"] = "測試撤銷"
        mock_connection.fetchrow.return_value = revoked

        result = await gateway.revoke_license(
            mock_connection,
            license_id=sample_license["license_id"],
            revoked_by=revoked["revoked_by"],
            revoke_reason="測試撤銷",
        )

        assert result.is_ok()
        license = result.unwrap()
        assert isinstance(license, BusinessLicense)
        assert license.status == "revoked"
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_license(
        self,
        gateway: BusinessLicenseGateway,
        mock_connection: AsyncMock,
        sample_license: dict[str, Any],
    ) -> None:
        """Test getting license by ID."""
        mock_connection.fetchrow.return_value = sample_license

        result = await gateway.get_license(mock_connection, license_id=sample_license["license_id"])

        assert result.is_ok()
        license = result.unwrap()
        assert license is not None
        assert isinstance(license, BusinessLicense)
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_licenses(
        self,
        gateway: BusinessLicenseGateway,
        mock_connection: AsyncMock,
        sample_license: dict[str, Any],
    ) -> None:
        """Test getting user licenses."""
        mock_connection.fetch.return_value = [sample_license]

        result = await gateway.get_user_licenses(
            mock_connection,
            guild_id=sample_license["guild_id"],
            user_id=sample_license["user_id"],
        )

        assert result.is_ok()
        licenses = result.unwrap()
        assert len(licenses) == 1
        assert isinstance(licenses[0], BusinessLicense)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_active_license_true(
        self, gateway: BusinessLicenseGateway, mock_connection: AsyncMock
    ) -> None:
        """Test checking active license returns true."""
        mock_connection.fetchrow.return_value = [True]

        result = await gateway.check_active_license(
            mock_connection,
            guild_id=_snowflake(),
            user_id=_snowflake(),
            license_type="一般商業",
        )

        assert result.is_ok()
        assert result.unwrap() is True
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_active_license_false(
        self, gateway: BusinessLicenseGateway, mock_connection: AsyncMock
    ) -> None:
        """Test checking active license returns false."""
        mock_connection.fetchrow.return_value = [False]

        result = await gateway.check_active_license(
            mock_connection,
            guild_id=_snowflake(),
            user_id=_snowflake(),
            license_type="一般商業",
        )

        assert result.is_ok()
        assert result.unwrap() is False
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_expire_licenses(
        self, gateway: BusinessLicenseGateway, mock_connection: AsyncMock
    ) -> None:
        """Test expiring licenses."""
        mock_connection.fetchrow.return_value = [5]

        result = await gateway.expire_licenses(mock_connection)

        assert result.is_ok()
        count = result.unwrap()
        assert count == 5
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_by_status(
        self, gateway: BusinessLicenseGateway, mock_connection: AsyncMock
    ) -> None:
        """Test counting licenses by status."""
        mock_connection.fetch.return_value = [
            {"status": "active", "count": 10},
            {"status": "expired", "count": 3},
            {"status": "revoked", "count": 2},
        ]

        result = await gateway.count_by_status(mock_connection, guild_id=_snowflake())

        assert result.is_ok()
        counts = result.unwrap()
        assert counts["active"] == 10
        assert counts["expired"] == 3
        assert counts["revoked"] == 2
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_licenses(
        self,
        gateway: BusinessLicenseGateway,
        mock_connection: AsyncMock,
        sample_license: dict[str, Any],
    ) -> None:
        """Test listing licenses with pagination."""
        # Add total_count to sample data
        license_with_count = sample_license.copy()
        license_with_count["total_count"] = 5
        mock_connection.fetch.return_value = [license_with_count] * 3

        result = await gateway.list_licenses(
            mock_connection,
            guild_id=sample_license["guild_id"],
            status="active",
            page=1,
            page_size=10,
        )

        assert result.is_ok()
        list_result = result.unwrap()
        assert len(list_result.licenses) == 3
        assert list_result.total_count == 5
        assert list_result.page == 1
        mock_connection.fetch.assert_called_once()


# --- Additional StateCouncilGovernanceGateway Tests ---


@pytest.mark.unit
class TestStateCouncilGovernanceGatewayExtra:
    """Additional test cases for StateCouncilGovernanceGateway."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def gateway(self) -> StateCouncilGovernanceGateway:
        """Create gateway instance."""
        return StateCouncilGovernanceGateway()

    @pytest.mark.asyncio
    async def test_fetch_department_config(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching single department config."""
        dept_config = {
            "id": 1,
            "guild_id": _snowflake(),
            "department": "內政部",
            "role_id": _snowflake(),
            "welfare_amount": 100,
            "welfare_interval_hours": 24,
            "tax_rate_basis": 1000,
            "tax_rate_percent": 10,
            "max_issuance_per_month": 10000,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        mock_connection.fetchrow.return_value = dept_config

        config = await gateway.fetch_department_config(
            mock_connection, guild_id=dept_config["guild_id"], department="內政部"
        )

        assert config is not None
        assert isinstance(config, DepartmentConfig)
        assert config.department == "內政部"
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_department_config_not_found(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching non-existent department config."""
        mock_connection.fetchrow.return_value = None

        config = await gateway.fetch_department_config(
            mock_connection, guild_id=_snowflake(), department="不存在部門"
        )

        assert config is None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_government_account(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test upserting government account."""
        account_data = {
            "account_id": _snowflake(),
            "guild_id": _snowflake(),
            "department": "財政部",
            "balance": 10000,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        mock_connection.fetchrow.return_value = account_data

        account = await gateway.upsert_government_account(
            mock_connection,
            guild_id=account_data["guild_id"],
            department="財政部",
            account_id=account_data["account_id"],
            balance=10000,
        )

        assert isinstance(account, GovernmentAccount)
        assert account.balance == 10000
        assert account.department == "財政部"
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_government_accounts(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching all government accounts."""
        account_data = {
            "account_id": _snowflake(),
            "guild_id": _snowflake(),
            "department": "財政部",
            "balance": 10000,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        mock_connection.fetch.return_value = [account_data]

        accounts = await gateway.fetch_government_accounts(
            mock_connection, guild_id=account_data["guild_id"]
        )

        assert len(accounts) == 1
        assert isinstance(accounts[0], GovernmentAccount)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_identity_record(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test creating identity record."""
        identity_data = {
            "record_id": 1,
            "guild_id": _snowflake(),
            "target_id": _snowflake(),
            "action": "grant_citizenship",
            "reason": "測試授予",
            "performed_by": _snowflake(),
            "performed_at": datetime.now(timezone.utc),
        }
        mock_connection.fetchrow.return_value = identity_data

        record = await gateway.create_identity_record(
            mock_connection,
            guild_id=identity_data["guild_id"],
            target_id=identity_data["target_id"],
            action="grant_citizenship",
            reason="測試授予",
            performed_by=identity_data["performed_by"],
        )

        assert isinstance(record, IdentityRecord)
        assert record.action == "grant_citizenship"
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_welfare_disbursements(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching welfare disbursements."""
        disbursement = {
            "disbursement_id": 1,
            "guild_id": _snowflake(),
            "recipient_id": _snowflake(),
            "amount": 100,
            "disbursement_type": "定期福利",
            "reference_id": None,
            "disbursed_at": datetime.now(timezone.utc),
        }
        mock_connection.fetch.return_value = [disbursement]

        disbursements = await gateway.fetch_welfare_disbursements(
            mock_connection, guild_id=disbursement["guild_id"], limit=100, offset=0
        )

        assert len(disbursements) == 1
        assert isinstance(disbursements[0], WelfareDisbursement)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_tax_records(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching tax records."""
        tax_record = {
            "tax_id": 1,
            "guild_id": _snowflake(),
            "taxpayer_id": _snowflake(),
            "taxable_amount": 1000,
            "tax_rate_percent": 10,
            "tax_amount": 100,
            "tax_type": "所得稅",
            "assessment_period": "2024-01",
            "collected_at": datetime.now(timezone.utc),
        }
        mock_connection.fetch.return_value = [tax_record]

        records = await gateway.fetch_tax_records(
            mock_connection, guild_id=tax_record["guild_id"], limit=100, offset=0
        )

        assert len(records) == 1
        assert isinstance(records[0], TaxRecord)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_identity_records(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching identity records."""
        identity_data = {
            "record_id": 1,
            "guild_id": _snowflake(),
            "target_id": _snowflake(),
            "action": "grant_citizenship",
            "reason": "測試授予",
            "performed_by": _snowflake(),
            "performed_at": datetime.now(timezone.utc),
        }
        mock_connection.fetch.return_value = [identity_data]

        records = await gateway.fetch_identity_records(
            mock_connection, guild_id=identity_data["guild_id"], limit=100, offset=0
        )

        assert len(records) == 1
        assert isinstance(records[0], IdentityRecord)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_currency_issuances(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching currency issuances."""
        issuance = {
            "issuance_id": 1,
            "guild_id": _snowflake(),
            "amount": 5000,
            "reason": "測試發行",
            "performed_by": _snowflake(),
            "month_period": "2024-01",
            "issued_at": datetime.now(timezone.utc),
        }
        mock_connection.fetch.return_value = [issuance]

        issuances = await gateway.fetch_currency_issuances(
            mock_connection,
            guild_id=issuance["guild_id"],
            month_period="2024-01",
            limit=100,
            offset=0,
        )

        assert len(issuances) == 1
        assert isinstance(issuances[0], CurrencyIssuance)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_sum_monthly_issuance(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test summing monthly issuance."""
        mock_connection.fetchval.return_value = 15000

        total = await gateway.sum_monthly_issuance(
            mock_connection, guild_id=_snowflake(), month_period="2024-01"
        )

        assert total == 15000
        mock_connection.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_interdepartment_transfers(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching interdepartment transfers."""
        transfer = {
            "transfer_id": 1,
            "guild_id": _snowflake(),
            "from_department": "財政部",
            "to_department": "內政部",
            "amount": 1000,
            "reason": "測試轉帳",
            "performed_by": _snowflake(),
            "transferred_at": datetime.now(timezone.utc),
        }
        mock_connection.fetch.return_value = [transfer]

        transfers = await gateway.fetch_interdepartment_transfers(
            mock_connection, guild_id=transfer["guild_id"], limit=100, offset=0
        )

        assert len(transfers) == 1
        assert isinstance(transfers[0], InterdepartmentTransfer)
        mock_connection.fetch.assert_called_once()


# --- Additional CouncilGovernanceGateway Tests ---


@pytest.mark.unit
class TestCouncilGovernanceGatewayExtra:
    """Additional test cases for CouncilGovernanceGateway."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def gateway(self) -> CouncilGovernanceGateway:
        """Create gateway instance."""
        return CouncilGovernanceGateway()

    @pytest.mark.asyncio
    async def test_fetch_snapshot(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching proposal snapshot."""
        proposal_id = UUID(int=123)
        member_ids = [1, 2, 3, 4, 5]
        mock_connection.fetch.return_value = [{"member_id": mid} for mid in member_ids]

        snapshot = await gateway.fetch_snapshot(mock_connection, proposal_id=proposal_id)

        assert len(snapshot) == 5
        assert snapshot == member_ids
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_active_by_guild(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test counting active proposals."""
        guild_id = _snowflake()
        mock_connection.fetchval.return_value = 3

        count = await gateway.count_active_by_guild(mock_connection, guild_id=guild_id)

        assert count == 3
        mock_connection.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_status(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test marking proposal status."""
        proposal_id = UUID(int=123)

        await gateway.mark_status(
            mock_connection, proposal_id=proposal_id, status="已通過", execution_tx_id=None
        )

        mock_connection.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_votes_detail(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching vote details."""
        proposal_id = UUID(int=123)
        mock_connection.fetch.return_value = [
            {"voter_id": 1, "choice": "approve"},
            {"voter_id": 2, "choice": "reject"},
        ]

        votes = await gateway.fetch_votes_detail(mock_connection, proposal_id=proposal_id)

        assert len(votes) == 2
        assert votes[0] == (1, "approve")
        assert votes[1] == (2, "reject")
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_due_proposals(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test listing due proposals."""
        proposal_data = {
            "proposal_id": UUID(int=123),
            "guild_id": _snowflake(),
            "proposer_id": _snowflake(),
            "target_id": _snowflake(),
            "amount": 1000,
            "description": "測試提案",
            "attachment_url": None,
            "snapshot_n": 5,
            "threshold_t": 3,
            "deadline_at": datetime.now(timezone.utc),
            "status": "進行中",
            "reminder_sent": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "target_department_id": None,
        }
        mock_connection.fetch.return_value = [proposal_data]

        proposals = await gateway.list_due_proposals(mock_connection)

        assert len(proposals) == 1
        assert isinstance(proposals[0], Proposal)
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_council_role_ids(
        self, gateway: CouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test getting council role IDs."""
        mock_connection.fetchval.return_value = [123, 456, 789]

        role_ids = await gateway.get_council_role_ids(mock_connection, guild_id=_snowflake())

        assert len(role_ids) == 3
        assert 123 in role_ids
        mock_connection.fetchval.assert_called_once()


# --- Additional CompanyGateway Tests ---


@pytest.mark.unit
class TestCompanyGatewayExtra:
    """Additional test cases for CompanyGateway."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def gateway(self) -> CompanyGateway:
        """Create gateway instance."""
        return CompanyGateway()

    @pytest.mark.asyncio
    async def test_list_guild_companies(
        self, gateway: CompanyGateway, mock_connection: AsyncMock
    ) -> None:
        """Test listing guild companies with pagination."""
        company_data = {
            "id": 1,
            "guild_id": _snowflake(),
            "owner_id": _snowflake(),
            "license_id": UUID(int=123),
            "name": "測試公司",
            "account_id": _snowflake(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "license_type": "一般商業",
            "license_status": "active",
            "total_count": 5,
        }
        mock_connection.fetch.return_value = [company_data] * 3

        result = await gateway.list_guild_companies(
            mock_connection, guild_id=company_data["guild_id"], page=1, page_size=20
        )

        assert result.is_ok()
        list_result = result.unwrap()
        assert len(list_result.companies) == 3
        assert list_result.total_count == 5
        assert list_result.page == 1
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_available_licenses(
        self, gateway: CompanyGateway, mock_connection: AsyncMock
    ) -> None:
        """Test getting available licenses."""
        license_data = {
            "license_id": UUID(int=123),
            "license_type": "一般商業",
            "issued_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc),
        }
        mock_connection.fetch.return_value = [license_data]

        result = await gateway.get_available_licenses(
            mock_connection, guild_id=_snowflake(), user_id=_snowflake()
        )

        assert result.is_ok()
        licenses = result.unwrap()
        assert len(licenses) == 1
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_next_company_id(
        self, gateway: CompanyGateway, mock_connection: AsyncMock
    ) -> None:
        """Test getting next company ID."""
        mock_connection.fetchrow.return_value = [123]

        result = await gateway.next_company_id(mock_connection)

        assert result.is_ok()
        company_id = result.unwrap()
        assert company_id == 123
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_company_sequence(
        self, gateway: CompanyGateway, mock_connection: AsyncMock
    ) -> None:
        """Test resetting company sequence."""
        result = await gateway.reset_company_sequence(mock_connection, value=100)

        assert result.is_ok()
        assert result.unwrap() is True
        mock_connection.execute.assert_called_once()
