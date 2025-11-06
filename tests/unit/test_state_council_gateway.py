"""Unit tests for State Council gateway database operations."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import asyncpg
import pytest

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
        """Sample state council configuration data."""
        return {
            "guild_id": _snowflake(),
            "leader_id": _snowflake(),
            "leader_role_id": _snowflake(),
            "internal_affairs_account_id": _snowflake(),
            "finance_account_id": _snowflake(),
            "security_account_id": _snowflake(),
            "central_bank_account_id": _snowflake(),
            "created_at": datetime.now(tz=timezone.utc),
            "updated_at": datetime.now(tz=timezone.utc),
        }

    @pytest.fixture
    def sample_department_config(self) -> dict[str, Any]:
        """Sample department configuration data."""
        return {
            "id": _snowflake(),
            "guild_id": _snowflake(),
            "department": "內政部",
            "role_id": _snowflake(),
            "welfare_amount": 1000,
            "welfare_interval_hours": 24,
            "tax_rate_basis": 0,
            "tax_rate_percent": 0,
            "max_issuance_per_month": 0,
            "created_at": datetime.now(tz=timezone.utc),
            "updated_at": datetime.now(tz=timezone.utc),
        }

    @pytest.fixture
    def sample_account(self) -> dict[str, Any]:
        """Sample government account data."""
        return {
            "account_id": _snowflake(),
            "guild_id": _snowflake(),
            "department": "內政部",
            "balance": 5000,
            "created_at": datetime.now(tz=timezone.utc),
            "updated_at": datetime.now(tz=timezone.utc),
        }

    # --- State Council Config Tests ---

    @pytest.mark.asyncio
    async def test_upsert_state_council_config_insert(
        self,
        gateway: StateCouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_config: dict[str, Any],
    ) -> None:
        """Test inserting new state council config."""
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
        assert config.leader_id == sample_config["leader_id"]
        assert config.leader_role_id == sample_config["leader_role_id"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_state_council_config_update(
        self,
        gateway: StateCouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_config: dict[str, Any],
    ) -> None:
        """Test updating existing state council config."""
        updated_config = sample_config.copy()
        updated_config["leader_id"] = _snowflake()
        mock_connection.fetchrow.return_value = updated_config

        config = await gateway.upsert_state_council_config(
            mock_connection,
            guild_id=sample_config["guild_id"],
            leader_id=updated_config["leader_id"],
            leader_role_id=sample_config["leader_role_id"],
            internal_affairs_account_id=sample_config["internal_affairs_account_id"],
            finance_account_id=sample_config["finance_account_id"],
            security_account_id=sample_config["security_account_id"],
            central_bank_account_id=sample_config["central_bank_account_id"],
        )

        assert config.leader_id == updated_config["leader_id"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_state_council_config_success(
        self,
        gateway: StateCouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_config: dict[str, Any],
    ) -> None:
        """Test successful state council config fetch."""
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
        """Test fetching non-existent state council config."""
        mock_connection.fetchrow.return_value = None

        config = await gateway.fetch_state_council_config(mock_connection, guild_id=_snowflake())

        assert config is None
        mock_connection.fetchrow.assert_called_once()

    # --- Department Config Tests ---

    @pytest.mark.asyncio
    async def test_upsert_department_config(
        self,
        gateway: StateCouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_department_config: dict[str, Any],
    ) -> None:
        """Test upserting department config."""
        mock_connection.fetchrow.return_value = sample_department_config

        config = await gateway.upsert_department_config(
            mock_connection,
            guild_id=sample_department_config["guild_id"],
            department=sample_department_config["department"],
            role_id=sample_department_config["role_id"],
            welfare_amount=sample_department_config["welfare_amount"],
            welfare_interval_hours=sample_department_config["welfare_interval_hours"],
            tax_rate_basis=sample_department_config["tax_rate_basis"],
            tax_rate_percent=sample_department_config["tax_rate_percent"],
            max_issuance_per_month=sample_department_config["max_issuance_per_month"],
        )

        assert isinstance(config, DepartmentConfig)
        assert config.guild_id == sample_department_config["guild_id"]
        assert config.department == sample_department_config["department"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_department_configs(
        self,
        gateway: StateCouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_department_config: dict[str, Any],
    ) -> None:
        """Test fetching all department configs for a guild."""
        mock_connection.fetch.return_value = [sample_department_config]

        configs = await gateway.fetch_department_configs(
            mock_connection, guild_id=sample_department_config["guild_id"]
        )

        assert len(configs) == 1
        assert isinstance(configs[0], DepartmentConfig)
        assert configs[0].department == sample_department_config["department"]
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_department_config_success(
        self,
        gateway: StateCouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_department_config: dict[str, Any],
    ) -> None:
        """Test successful department config fetch."""
        mock_connection.fetchrow.return_value = sample_department_config

        config = await gateway.fetch_department_config(
            mock_connection,
            guild_id=sample_department_config["guild_id"],
            department=sample_department_config["department"],
        )

        assert config is not None
        assert isinstance(config, DepartmentConfig)
        assert config.department == sample_department_config["department"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_department_config_not_found(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching non-existent department config."""
        mock_connection.fetchrow.return_value = None

        config = await gateway.fetch_department_config(
            mock_connection, guild_id=_snowflake(), department="不存在的部門"
        )

        assert config is None
        mock_connection.fetchrow.assert_called_once()

    # --- Government Account Tests ---

    @pytest.mark.asyncio
    async def test_upsert_government_account(
        self,
        gateway: StateCouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_account: dict[str, Any],
    ) -> None:
        """Test upserting government account."""
        mock_connection.fetchrow.return_value = sample_account

        account = await gateway.upsert_government_account(
            mock_connection,
            guild_id=sample_account["guild_id"],
            department=sample_account["department"],
            account_id=sample_account["account_id"],
            balance=sample_account["balance"],
        )

        assert isinstance(account, GovernmentAccount)
        assert account.account_id == sample_account["account_id"]
        assert account.department == sample_account["department"]
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_government_accounts(
        self,
        gateway: StateCouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_account: dict[str, Any],
    ) -> None:
        """Test fetching all government accounts for a guild."""
        mock_connection.fetch.return_value = [sample_account]

        accounts = await gateway.fetch_government_accounts(
            mock_connection, guild_id=sample_account["guild_id"]
        )

        assert len(accounts) == 1
        assert isinstance(accounts[0], GovernmentAccount)
        assert accounts[0].department == sample_account["department"]
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_account_balance(
        self,
        gateway: StateCouncilGovernanceGateway,
        mock_connection: AsyncMock,
        sample_account: dict[str, Any],
    ) -> None:
        """Test updating account balance."""
        new_balance = 10000

        await gateway.update_account_balance(
            mock_connection,
            account_id=sample_account["account_id"],
            new_balance=new_balance,
        )

        mock_connection.execute.assert_called_once()

    # --- Welfare Disbursement Tests ---

    @pytest.mark.asyncio
    async def test_create_welfare_disbursement(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test creating welfare disbursement record."""
        guild_id = _snowflake()
        recipient_id = _snowflake()
        amount = 1000
        disbursement_type = "定期福利"
        reference_id = "REF123"

        sample_disbursement = {
            "disbursement_id": UUID(int=123),
            "guild_id": guild_id,
            "recipient_id": recipient_id,
            "amount": amount,
            "disbursement_type": disbursement_type,
            "reference_id": reference_id,
            "disbursed_at": datetime.now(tz=timezone.utc),
        }

        mock_connection.fetchrow.return_value = sample_disbursement

        disbursement = await gateway.create_welfare_disbursement(
            mock_connection,
            guild_id=guild_id,
            recipient_id=recipient_id,
            amount=amount,
            disbursement_type=disbursement_type,
            reference_id=reference_id,
        )

        assert isinstance(disbursement, WelfareDisbursement)
        assert disbursement.guild_id == guild_id
        assert disbursement.recipient_id == recipient_id
        assert disbursement.amount == amount
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_welfare_disbursements(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching welfare disbursements."""
        guild_id = _snowflake()
        limit = 100
        offset = 0

        sample_disbursement = {
            "disbursement_id": UUID(int=123),
            "guild_id": guild_id,
            "recipient_id": _snowflake(),
            "amount": 1000,
            "disbursement_type": "定期福利",
            "reference_id": None,
            "disbursed_at": datetime.now(tz=timezone.utc),
        }

        mock_connection.fetch.return_value = [sample_disbursement]

        disbursements = await gateway.fetch_welfare_disbursements(
            mock_connection, guild_id=guild_id, limit=limit, offset=offset
        )

        assert len(disbursements) == 1
        assert isinstance(disbursements[0], WelfareDisbursement)
        assert disbursements[0].guild_id == guild_id
        mock_connection.fetch.assert_called_once()

    # --- Tax Record Tests ---

    @pytest.mark.asyncio
    async def test_create_tax_record(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test creating tax record."""
        guild_id = _snowflake()
        taxpayer_id = _snowflake()
        taxable_amount = 10000
        tax_rate_percent = 10
        tax_amount = 1000
        tax_type = "所得稅"
        assessment_period = "2024-01"

        sample_tax = {
            "tax_id": UUID(int=123),
            "guild_id": guild_id,
            "taxpayer_id": taxpayer_id,
            "taxable_amount": taxable_amount,
            "tax_rate_percent": tax_rate_percent,
            "tax_amount": tax_amount,
            "tax_type": tax_type,
            "assessment_period": assessment_period,
            "collected_at": datetime.now(tz=timezone.utc),
        }

        mock_connection.fetchrow.return_value = sample_tax

        tax_record = await gateway.create_tax_record(
            mock_connection,
            guild_id=guild_id,
            taxpayer_id=taxpayer_id,
            taxable_amount=taxable_amount,
            tax_rate_percent=tax_rate_percent,
            tax_amount=tax_amount,
            tax_type=tax_type,
            assessment_period=assessment_period,
        )

        assert isinstance(tax_record, TaxRecord)
        assert tax_record.guild_id == guild_id
        assert tax_record.taxpayer_id == taxpayer_id
        assert tax_record.tax_amount == tax_amount
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_tax_records(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching tax records."""
        guild_id = _snowflake()
        limit = 100
        offset = 0

        sample_tax = {
            "tax_id": UUID(int=123),
            "guild_id": guild_id,
            "taxpayer_id": _snowflake(),
            "taxable_amount": 10000,
            "tax_rate_percent": 10,
            "tax_amount": 1000,
            "tax_type": "所得稅",
            "assessment_period": "2024-01",
            "collected_at": datetime.now(tz=timezone.utc),
        }

        mock_connection.fetch.return_value = [sample_tax]

        tax_records = await gateway.fetch_tax_records(
            mock_connection, guild_id=guild_id, limit=limit, offset=offset
        )

        assert len(tax_records) == 1
        assert isinstance(tax_records[0], TaxRecord)
        assert tax_records[0].guild_id == guild_id
        mock_connection.fetch.assert_called_once()

    # --- Identity Record Tests ---

    @pytest.mark.asyncio
    async def test_create_identity_record(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test creating identity record."""
        guild_id = _snowflake()
        target_id = _snowflake()
        action = "移除公民身分"
        reason = "違反規定"
        performed_by = _snowflake()

        sample_identity = {
            "record_id": UUID(int=123),
            "guild_id": guild_id,
            "target_id": target_id,
            "action": action,
            "reason": reason,
            "performed_by": performed_by,
            "performed_at": datetime.now(tz=timezone.utc),
        }

        mock_connection.fetchrow.return_value = sample_identity

        identity_record = await gateway.create_identity_record(
            mock_connection,
            guild_id=guild_id,
            target_id=target_id,
            action=action,
            reason=reason,
            performed_by=performed_by,
        )

        assert isinstance(identity_record, IdentityRecord)
        assert identity_record.guild_id == guild_id
        assert identity_record.target_id == target_id
        assert identity_record.action == action
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_identity_records(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching identity records."""
        guild_id = _snowflake()
        limit = 100
        offset = 0

        sample_identity = {
            "record_id": UUID(int=123),
            "guild_id": guild_id,
            "target_id": _snowflake(),
            "action": "移除公民身分",
            "reason": None,
            "performed_by": _snowflake(),
            "performed_at": datetime.now(tz=timezone.utc),
        }

        mock_connection.fetch.return_value = [sample_identity]

        identity_records = await gateway.fetch_identity_records(
            mock_connection, guild_id=guild_id, limit=limit, offset=offset
        )

        assert len(identity_records) == 1
        assert isinstance(identity_records[0], IdentityRecord)
        assert identity_records[0].guild_id == guild_id
        mock_connection.fetch.assert_called_once()

    # --- Currency Issuance Tests ---

    @pytest.mark.asyncio
    async def test_create_currency_issuance(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test creating currency issuance record."""
        guild_id = _snowflake()
        amount = 5000
        reason = "經濟刺激"
        performed_by = _snowflake()
        month_period = "2024-01"

        sample_issuance = {
            "issuance_id": UUID(int=123),
            "guild_id": guild_id,
            "amount": amount,
            "reason": reason,
            "performed_by": performed_by,
            "month_period": month_period,
            "issued_at": datetime.now(tz=timezone.utc),
        }

        mock_connection.fetchrow.return_value = sample_issuance

        currency_issuance = await gateway.create_currency_issuance(
            mock_connection,
            guild_id=guild_id,
            amount=amount,
            reason=reason,
            performed_by=performed_by,
            month_period=month_period,
        )

        assert isinstance(currency_issuance, CurrencyIssuance)
        assert currency_issuance.guild_id == guild_id
        assert currency_issuance.amount == amount
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_currency_issuances(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching currency issuances."""
        guild_id = _snowflake()
        month_period = "2024-01"
        limit = 100
        offset = 0

        sample_issuance = {
            "issuance_id": UUID(int=123),
            "guild_id": guild_id,
            "amount": 5000,
            "reason": "經濟刺激",
            "performed_by": _snowflake(),
            "month_period": month_period,
            "issued_at": datetime.now(tz=timezone.utc),
        }

        mock_connection.fetch.return_value = [sample_issuance]

        issuances = await gateway.fetch_currency_issuances(
            mock_connection,
            guild_id=guild_id,
            month_period=month_period,
            limit=limit,
            offset=offset,
        )

        assert len(issuances) == 1
        assert isinstance(issuances[0], CurrencyIssuance)
        assert issuances[0].guild_id == guild_id
        assert issuances[0].month_period == month_period
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_sum_monthly_issuance(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test summing monthly currency issuance."""
        guild_id = _snowflake()
        month_period = "2024-01"
        expected_total = 10000

        mock_connection.fetchval.return_value = expected_total

        total = await gateway.sum_monthly_issuance(
            mock_connection, guild_id=guild_id, month_period=month_period
        )

        assert total == expected_total
        mock_connection.fetchval.assert_called_once()

    # --- Interdepartment Transfer Tests ---

    @pytest.mark.asyncio
    async def test_create_interdepartment_transfer(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test creating interdepartment transfer record."""
        guild_id = _snowflake()
        from_department = "內政部"
        to_department = "財政部"
        amount = 2000
        reason = "預算調整"
        performed_by = _snowflake()

        sample_transfer = {
            "transfer_id": UUID(int=123),
            "guild_id": guild_id,
            "from_department": from_department,
            "to_department": to_department,
            "amount": amount,
            "reason": reason,
            "performed_by": performed_by,
            "transferred_at": datetime.now(tz=timezone.utc),
        }

        mock_connection.fetchrow.return_value = sample_transfer

        transfer = await gateway.create_interdepartment_transfer(
            mock_connection,
            guild_id=guild_id,
            from_department=from_department,
            to_department=to_department,
            amount=amount,
            reason=reason,
            performed_by=performed_by,
        )

        assert isinstance(transfer, InterdepartmentTransfer)
        assert transfer.guild_id == guild_id
        assert transfer.from_department == from_department
        assert transfer.to_department == to_department
        assert transfer.amount == amount
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_interdepartment_transfers(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching interdepartment transfers."""
        guild_id = _snowflake()
        limit = 100
        offset = 0

        sample_transfer = {
            "transfer_id": UUID(int=123),
            "guild_id": guild_id,
            "from_department": "內政部",
            "to_department": "財政部",
            "amount": 2000,
            "reason": "預算調整",
            "performed_by": _snowflake(),
            "transferred_at": datetime.now(tz=timezone.utc),
        }

        mock_connection.fetch.return_value = [sample_transfer]

        transfers = await gateway.fetch_interdepartment_transfers(
            mock_connection, guild_id=guild_id, limit=limit, offset=offset
        )

        assert len(transfers) == 1
        assert isinstance(transfers[0], InterdepartmentTransfer)
        assert transfers[0].guild_id == guild_id
        mock_connection.fetch.assert_called_once()

    # --- Scheduler Helper Tests ---

    @pytest.mark.asyncio
    async def test_fetch_all_department_configs_with_welfare(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching department configs with welfare settings."""
        sample_config = {
            "guild_id": _snowflake(),
            "department": "內政部",
            "welfare_amount": 1000,
            "welfare_interval_hours": 24,
        }

        mock_connection.fetch.return_value = [sample_config]

        configs = await gateway.fetch_all_department_configs_with_welfare(mock_connection)

        assert len(configs) == 1
        assert configs[0]["guild_id"] == sample_config["guild_id"]
        assert configs[0]["welfare_amount"] == 1000
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_all_department_configs_for_issuance(
        self, gateway: StateCouncilGovernanceGateway, mock_connection: AsyncMock
    ) -> None:
        """Test fetching department configs with issuance limits."""
        sample_config = {
            "guild_id": _snowflake(),
            "department": "中央銀行",
            "max_issuance_per_month": 10000,
        }

        mock_connection.fetch.return_value = [sample_config]

        configs = await gateway.fetch_all_department_configs_for_issuance(mock_connection)

        assert len(configs) == 1
        assert configs[0]["guild_id"] == sample_config["guild_id"]
        assert configs[0]["max_issuance_per_month"] == 10000
        mock_connection.fetch.assert_called_once()
