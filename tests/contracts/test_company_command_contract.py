"""Contract tests for company panel command."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.bot.commands.company import build_company_group
from src.bot.services.company_service import CompanyService
from src.bot.services.currency_config_service import (
    CurrencyConfigResult,
    CurrencyConfigService,
)
from src.cython_ext.state_council_models import AvailableLicense, Company
from src.infra.result import Ok


def _snowflake() -> int:
    return secrets.randbits(63)


@pytest.mark.contract
def test_company_command_group_structure() -> None:
    """Verify /company command group has correct structure."""
    company_service = SimpleNamespace(
        list_user_companies=AsyncMock(return_value=Ok([])),
        get_available_licenses=AsyncMock(return_value=Ok([])),
        create_company=AsyncMock(),
    )
    currency_service = SimpleNamespace(
        get_currency_config=AsyncMock(
            return_value=Ok(CurrencyConfigResult(currency_name="點", currency_icon=""))
        )
    )

    group = build_company_group(
        cast(CompanyService, company_service),
        cast(CurrencyConfigService, currency_service),
    )

    assert group.name == "company"
    assert "公司" in group.description or "company" in group.description.lower()

    # Check subcommands
    command_names = [c.name for c in group.commands]
    assert "panel" in command_names


@pytest.mark.contract
def test_company_panel_subcommand_signature() -> None:
    """Verify /company panel subcommand has correct signature."""
    company_service = SimpleNamespace(
        list_user_companies=AsyncMock(return_value=Ok([])),
    )
    currency_service = SimpleNamespace(
        get_currency_config=AsyncMock(
            return_value=Ok(CurrencyConfigResult(currency_name="點", currency_icon=""))
        )
    )

    group = build_company_group(
        cast(CompanyService, company_service),
        cast(CurrencyConfigService, currency_service),
    )

    # Find panel command
    panel_cmd = None
    for cmd in group.commands:
        if cmd.name == "panel":
            panel_cmd = cmd
            break

    assert panel_cmd is not None
    assert "面板" in panel_cmd.description or "panel" in panel_cmd.description.lower()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_company_panel_view_initialization() -> None:
    """Verify CompanyPanelView initializes correctly."""
    from src.bot.commands.company import CompanyPanelView
    from src.bot.services.currency_config_service import CurrencyConfigResult

    guild_id = _snowflake()
    user_id = _snowflake()

    company_service = SimpleNamespace(
        list_user_companies=AsyncMock(return_value=Ok([])),
        get_company_balance=AsyncMock(return_value=Ok(0)),
    )
    currency_service = SimpleNamespace(
        get_currency_config=AsyncMock(
            return_value=Ok(CurrencyConfigResult(currency_name="點", currency_icon=""))
        )
    )
    currency_config = CurrencyConfigResult(currency_name="點", currency_icon="")

    view = CompanyPanelView(
        company_service=cast(Any, company_service),
        currency_service=cast(Any, currency_service),
        guild_id=guild_id,
        author_id=user_id,
        currency_config=currency_config,
    )

    assert view.guild_id == guild_id
    assert view.author_id == user_id
    assert view.current_page == "home"
    assert view.panel_type == "company"


@pytest.mark.contract
def test_company_model_structure() -> None:
    """Verify Company model has required fields."""
    company = Company(
        id=1,
        guild_id=_snowflake(),
        owner_id=_snowflake(),
        license_id=uuid4(),
        name="Test Company",
        account_id=9_600_000_000_000_001,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        license_type="商業許可",
        license_status="active",
    )

    assert company.id == 1
    assert company.name == "Test Company"
    assert company.account_id == 9_600_000_000_000_001
    assert company.license_type == "商業許可"
    assert company.license_status == "active"


@pytest.mark.contract
def test_company_account_id_derivation() -> None:
    """Verify company account ID derivation formula."""
    from src.db.gateway.company import CompanyGateway

    guild_id = 123456789
    company_id = 1

    expected = 9_600_000_000_000_000 + company_id
    actual = CompanyGateway.derive_account_id(guild_id, company_id)

    assert actual == expected


@pytest.mark.contract
def test_available_license_model_structure() -> None:
    """Verify AvailableLicense model has required fields."""
    license = AvailableLicense(
        license_id=uuid4(),
        license_type="商業許可",
        issued_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )

    assert license.license_id is not None
    assert license.license_type == "商業許可"
    assert license.issued_at is not None
    assert license.expires_at is not None
