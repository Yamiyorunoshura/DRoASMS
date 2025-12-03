from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from faker import Faker

from src.bot.services.company_service import (
    CompanyLicenseInvalidError,
    CompanyNotFoundError,
    CompanyOwnershipError,
    CompanyService,
    InvalidCompanyNameError,
    LicenseAlreadyUsedError,
    NoAvailableLicenseError,
)
from src.cython_ext.economy_query_models import BalanceRecord
from src.cython_ext.state_council_models import (
    AvailableLicense,
    Company,
    CompanyListResult,
)
from src.infra.result import DatabaseError, Err, Ok


def _snowflake(faker: Faker) -> int:
    """產生隨機 Discord snowflake ID 供隔離測試使用。"""
    return faker.random_int(min=1, max=9223372036854775807)


class FakeAcquire:
    """假的資料庫連線取得上下文管理器。"""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    async def __aenter__(self) -> Any:
        return self._connection

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class FakePool:
    """假的資料庫連線池。"""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self._connection)


class FakeConnection:
    """假的資料庫連線。"""

    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, sql: str, *args: object) -> None:
        self.executed.append((sql, args))


def _create_company(
    *,
    company_id: int,
    guild_id: int,
    owner_id: int,
    name: str = "測試公司",
    account_id: int | None = None,
) -> Company:
    """建立測試用公司實體。"""
    return Company(
        id=company_id,
        guild_id=guild_id,
        owner_id=owner_id,
        license_id=uuid4(),
        name=name,
        account_id=account_id or 1000000 + company_id,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )


def _create_available_license() -> AvailableLicense:
    """建立測試用可用許可證。"""
    now = datetime.now(timezone.utc)
    return AvailableLicense(
        license_id=uuid4(),
        license_type="business",
        issued_at=now,
        expires_at=None,
    )


# =============================================================================
# Test: create_company success path
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_company_success(faker: Faker) -> None:
    """測試成功創建公司。"""
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)
    license_id = uuid4()
    company_name = faker.company()

    company = _create_company(
        company_id=1,
        guild_id=guild_id,
        owner_id=owner_id,
        name=company_name,
    )

    mock_gateway = AsyncMock()
    mock_gateway.next_company_id.return_value = Ok(company.id)
    mock_gateway.create_company.return_value = Ok(company)

    # Mock EconomyQueryGateway
    mock_econ_gateway = AsyncMock()
    mock_econ_gateway.ensure_balance_record = AsyncMock()

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    # Patch EconomyQueryGateway
    import src.bot.services.company_service as company_service_module

    original_econ_gateway = company_service_module.EconomyQueryGateway
    company_service_module.EconomyQueryGateway = lambda: mock_econ_gateway

    try:
        result = await service.create_company(
            guild_id=guild_id,
            owner_id=owner_id,
            license_id=license_id,
            name=company_name,
        )

        assert isinstance(result, Ok)
        assert result.value == company
        mock_gateway.next_company_id.assert_awaited_once()
        mock_gateway.create_company.assert_awaited_once()
        mock_econ_gateway.ensure_balance_record.assert_awaited_once()
    finally:
        company_service_module.EconomyQueryGateway = original_econ_gateway


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_company_does_not_rewind_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_company 不應重置序列為未呼叫狀態，避免產生重複 ID。"""

    connection = FakeConnection()
    pool = FakePool(connection)

    company = Company(
        id=42,
        guild_id=1,
        owner_id=2,
        license_id=uuid4(),
        name="Test Corp",
        account_id=999,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )

    gateway = SimpleNamespace(
        next_company_id=AsyncMock(return_value=Ok(company.id)),
        create_company=AsyncMock(return_value=Ok(company)),
        reset_company_sequence=AsyncMock(return_value=Ok(True)),
    )

    service = CompanyService(pool, gateway=gateway)  # type: ignore[arg-type]

    # Mock EconomyQueryGateway
    mock_econ_gateway = AsyncMock()
    mock_econ_gateway.ensure_balance_record = AsyncMock()

    import src.bot.services.company_service as company_service_module

    original_econ_gateway = company_service_module.EconomyQueryGateway
    company_service_module.EconomyQueryGateway = lambda: mock_econ_gateway

    try:
        result = await service.create_company(
            guild_id=company.guild_id,
            owner_id=company.owner_id,
            license_id=company.license_id,
            name=company.name,
        )

        assert isinstance(result, Ok)
        assert result.value == company

        # 不應呼叫 reset_company_sequence，避免下一個 nextval 重複上一個 ID。
        gateway.reset_company_sequence.assert_not_awaited()
    finally:
        company_service_module.EconomyQueryGateway = original_econ_gateway


# =============================================================================
# Test: create_company validation errors
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_company_empty_name(faker: Faker) -> None:
    """測試空白公司名稱應返回錯誤。"""
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)
    license_id = uuid4()

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool)  # type: ignore[arg-type]

    result = await service.create_company(
        guild_id=guild_id,
        owner_id=owner_id,
        license_id=license_id,
        name="   ",  # Empty after strip
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, InvalidCompanyNameError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_company_name_too_long(faker: Faker) -> None:
    """測試過長的公司名稱應返回錯誤。"""
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)
    license_id = uuid4()

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool)  # type: ignore[arg-type]

    result = await service.create_company(
        guild_id=guild_id,
        owner_id=owner_id,
        license_id=license_id,
        name="A" * 101,  # 101 characters
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, InvalidCompanyNameError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_company_name_boundary_valid(faker: Faker) -> None:
    """測試邊界長度（1 和 100 字元）的公司名稱應成功。"""
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)
    license_id = uuid4()

    company = _create_company(
        company_id=1,
        guild_id=guild_id,
        owner_id=owner_id,
        name="A" * 100,
    )

    mock_gateway = AsyncMock()
    mock_gateway.next_company_id.return_value = Ok(company.id)
    mock_gateway.create_company.return_value = Ok(company)

    mock_econ_gateway = AsyncMock()
    mock_econ_gateway.ensure_balance_record = AsyncMock()

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    import src.bot.services.company_service as company_service_module

    original_econ_gateway = company_service_module.EconomyQueryGateway
    company_service_module.EconomyQueryGateway = lambda: mock_econ_gateway

    try:
        # Test 100 characters
        result = await service.create_company(
            guild_id=guild_id,
            owner_id=owner_id,
            license_id=license_id,
            name="A" * 100,
        )
        assert isinstance(result, Ok)

        # Test 1 character
        mock_gateway.create_company.return_value = Ok(company)
        result = await service.create_company(
            guild_id=guild_id,
            owner_id=owner_id,
            license_id=license_id,
            name="B",
        )
        assert isinstance(result, Ok)
    finally:
        company_service_module.EconomyQueryGateway = original_econ_gateway


# =============================================================================
# Test: create_company license errors
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_company_no_available_license(faker: Faker) -> None:
    """測試無可用許可證時應返回錯誤。"""
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)
    license_id = uuid4()

    mock_gateway = AsyncMock()
    mock_gateway.next_company_id.return_value = Ok(1)
    mock_gateway.create_company.return_value = Err(DatabaseError("Invalid or inactive license"))

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.create_company(
        guild_id=guild_id,
        owner_id=owner_id,
        license_id=license_id,
        name="Test Company",
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, NoAvailableLicenseError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_company_license_already_used(faker: Faker) -> None:
    """測試許可證已被使用時應返回錯誤。"""
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)
    license_id = uuid4()

    mock_gateway = AsyncMock()
    mock_gateway.next_company_id.return_value = Ok(1)
    mock_gateway.create_company.return_value = Err(
        DatabaseError("already has an associated company")
    )

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.create_company(
        guild_id=guild_id,
        owner_id=owner_id,
        license_id=license_id,
        name="Test Company",
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, LicenseAlreadyUsedError)


# =============================================================================
# Test: create_company database errors
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_company_next_id_fails(faker: Faker) -> None:
    """測試取得下一個 ID 失敗時應返回錯誤。"""
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)
    license_id = uuid4()

    mock_gateway = AsyncMock()
    mock_gateway.next_company_id.return_value = Err(DatabaseError("Sequence error"))

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.create_company(
        guild_id=guild_id,
        owner_id=owner_id,
        license_id=license_id,
        name="Test Company",
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, DatabaseError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_company_exception_handling(faker: Faker) -> None:
    """測試創建公司時異常處理。"""
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)
    license_id = uuid4()

    mock_gateway = AsyncMock()
    mock_gateway.next_company_id.return_value = Ok(1)
    mock_gateway.create_company.side_effect = RuntimeError("Unexpected error")

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.create_company(
        guild_id=guild_id,
        owner_id=owner_id,
        license_id=license_id,
        name="Test Company",
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, DatabaseError)
    assert "Unexpected error" in str(result.error)


# =============================================================================
# Test: get_company
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_company_found(faker: Faker) -> None:
    """測試成功取得公司。"""
    company_id = faker.random_int(min=1, max=1000)
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)

    company = _create_company(
        company_id=company_id,
        guild_id=guild_id,
        owner_id=owner_id,
    )

    mock_gateway = AsyncMock()
    mock_gateway.get_company.return_value = Ok(company)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.get_company(company_id=company_id)

    assert isinstance(result, Ok)
    assert result.value == company
    mock_gateway.get_company.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_company_not_found(faker: Faker) -> None:
    """測試公司不存在時應返回 None。"""
    company_id = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    mock_gateway.get_company.return_value = Ok(None)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.get_company(company_id=company_id)

    assert isinstance(result, Ok)
    assert result.value is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_company_database_error(faker: Faker) -> None:
    """測試查詢公司時資料庫錯誤。"""
    company_id = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    mock_gateway.get_company.return_value = Err(DatabaseError("Connection failed"))

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.get_company(company_id=company_id)

    assert isinstance(result, Err)
    assert isinstance(result.error, DatabaseError)


# =============================================================================
# Test: get_company_by_account
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_company_by_account_found(faker: Faker) -> None:
    """測試根據帳戶 ID 成功取得公司。"""
    account_id = faker.random_int(min=1000000, max=9999999)
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)

    company = _create_company(
        company_id=1,
        guild_id=guild_id,
        owner_id=owner_id,
        account_id=account_id,
    )

    mock_gateway = AsyncMock()
    mock_gateway.get_company_by_account.return_value = Ok(company)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.get_company_by_account(account_id=account_id)

    assert isinstance(result, Ok)
    assert result.value == company
    assert result.value.account_id == account_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_company_by_account_not_found(faker: Faker) -> None:
    """測試帳戶 ID 對應的公司不存在。"""
    account_id = faker.random_int(min=1000000, max=9999999)

    mock_gateway = AsyncMock()
    mock_gateway.get_company_by_account.return_value = Ok(None)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.get_company_by_account(account_id=account_id)

    assert isinstance(result, Ok)
    assert result.value is None


# =============================================================================
# Test: list_user_companies
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_user_companies_multiple(faker: Faker) -> None:
    """測試列出用戶擁有的多家公司。"""
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)

    companies = [
        _create_company(company_id=1, guild_id=guild_id, owner_id=owner_id, name="公司 A"),
        _create_company(company_id=2, guild_id=guild_id, owner_id=owner_id, name="公司 B"),
        _create_company(company_id=3, guild_id=guild_id, owner_id=owner_id, name="公司 C"),
    ]

    mock_gateway = AsyncMock()
    mock_gateway.list_user_companies.return_value = Ok(companies)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.list_user_companies(guild_id=guild_id, owner_id=owner_id)

    assert isinstance(result, Ok)
    assert len(result.value) == 3
    assert all(c.owner_id == owner_id for c in result.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_user_companies_empty(faker: Faker) -> None:
    """測試用戶沒有公司時應返回空列表。"""
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)

    mock_gateway = AsyncMock()
    mock_gateway.list_user_companies.return_value = Ok([])

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.list_user_companies(guild_id=guild_id, owner_id=owner_id)

    assert isinstance(result, Ok)
    assert len(result.value) == 0


# =============================================================================
# Test: list_guild_companies
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_guild_companies_paginated(faker: Faker) -> None:
    """測試列出伺服器內的公司（支援分頁）。"""
    guild_id = _snowflake(faker)

    companies = [
        _create_company(company_id=i, guild_id=guild_id, owner_id=_snowflake(faker))
        for i in range(1, 21)
    ]

    list_result = CompanyListResult(
        companies=companies,
        total_count=50,
        page=1,
        page_size=20,
    )

    mock_gateway = AsyncMock()
    mock_gateway.list_guild_companies.return_value = Ok(list_result)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.list_guild_companies(guild_id=guild_id, page=1, page_size=20)

    assert isinstance(result, Ok)
    assert result.value.total_count == 50
    assert len(result.value.companies) == 20
    assert result.value.page == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_guild_companies_empty(faker: Faker) -> None:
    """測試伺服器沒有公司時應返回空結果。"""
    guild_id = _snowflake(faker)

    list_result = CompanyListResult(
        companies=[],
        total_count=0,
        page=1,
        page_size=20,
    )

    mock_gateway = AsyncMock()
    mock_gateway.list_guild_companies.return_value = Ok(list_result)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.list_guild_companies(guild_id=guild_id)

    assert isinstance(result, Ok)
    assert result.value.total_count == 0
    assert len(result.value.companies) == 0


# =============================================================================
# Test: get_available_licenses
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_available_licenses_multiple(faker: Faker) -> None:
    """測試取得多個可用許可證。"""
    guild_id = _snowflake(faker)
    user_id = _snowflake(faker)

    licenses = [_create_available_license() for _ in range(3)]

    mock_gateway = AsyncMock()
    mock_gateway.get_available_licenses.return_value = Ok(licenses)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.get_available_licenses(guild_id=guild_id, user_id=user_id)

    assert isinstance(result, Ok)
    assert len(result.value) == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_available_licenses_empty(faker: Faker) -> None:
    """測試沒有可用許可證時應返回空列表。"""
    guild_id = _snowflake(faker)
    user_id = _snowflake(faker)

    mock_gateway = AsyncMock()
    mock_gateway.get_available_licenses.return_value = Ok([])

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.get_available_licenses(guild_id=guild_id, user_id=user_id)

    assert isinstance(result, Ok)
    assert len(result.value) == 0


# =============================================================================
# Test: check_ownership
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_ownership_true(faker: Faker) -> None:
    """測試驗證擁有權成功。"""
    company_id = faker.random_int(min=1, max=1000)
    user_id = _snowflake(faker)

    mock_gateway = AsyncMock()
    mock_gateway.check_ownership.return_value = Ok(True)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.check_ownership(company_id=company_id, user_id=user_id)

    assert isinstance(result, Ok)
    assert result.value is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_ownership_false(faker: Faker) -> None:
    """測試驗證擁有權失敗。"""
    company_id = faker.random_int(min=1, max=1000)
    user_id = _snowflake(faker)

    mock_gateway = AsyncMock()
    mock_gateway.check_ownership.return_value = Ok(False)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.check_ownership(company_id=company_id, user_id=user_id)

    assert isinstance(result, Ok)
    assert result.value is False


# =============================================================================
# Test: check_license_valid
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_license_valid_true(faker: Faker) -> None:
    """測試許可證有效。"""
    company_id = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    mock_gateway.check_license_valid.return_value = Ok(True)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.check_license_valid(company_id=company_id)

    assert isinstance(result, Ok)
    assert result.value is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_license_valid_false(faker: Faker) -> None:
    """測試許可證無效。"""
    company_id = faker.random_int(min=1, max=1000)

    mock_gateway = AsyncMock()
    mock_gateway.check_license_valid.return_value = Ok(False)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.check_license_valid(company_id=company_id)

    assert isinstance(result, Ok)
    assert result.value is False


# =============================================================================
# Test: validate_company_operation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_company_operation_success(faker: Faker) -> None:
    """測試公司操作驗證成功（擁有權 + 許可證有效）。"""
    company_id = faker.random_int(min=1, max=1000)
    guild_id = _snowflake(faker)
    user_id = _snowflake(faker)

    company = _create_company(
        company_id=company_id,
        guild_id=guild_id,
        owner_id=user_id,
    )

    mock_gateway = AsyncMock()
    mock_gateway.get_company.return_value = Ok(company)
    mock_gateway.check_license_valid.return_value = Ok(True)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.validate_company_operation(
        company_id=company_id,
        user_id=user_id,
    )

    assert isinstance(result, Ok)
    assert result.value == company


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_company_operation_not_found(faker: Faker) -> None:
    """測試公司不存在時應返回錯誤。"""
    company_id = faker.random_int(min=1, max=1000)
    user_id = _snowflake(faker)

    mock_gateway = AsyncMock()
    mock_gateway.get_company.return_value = Ok(None)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.validate_company_operation(
        company_id=company_id,
        user_id=user_id,
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, CompanyNotFoundError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_company_operation_not_owner(faker: Faker) -> None:
    """測試非擁有者時應返回錯誤。"""
    company_id = faker.random_int(min=1, max=1000)
    guild_id = _snowflake(faker)
    owner_id = _snowflake(faker)
    user_id = _snowflake(faker)  # Different user

    company = _create_company(
        company_id=company_id,
        guild_id=guild_id,
        owner_id=owner_id,
    )

    mock_gateway = AsyncMock()
    mock_gateway.get_company.return_value = Ok(company)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.validate_company_operation(
        company_id=company_id,
        user_id=user_id,
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, CompanyOwnershipError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_company_operation_invalid_license(faker: Faker) -> None:
    """測試許可證無效時應返回錯誤。"""
    company_id = faker.random_int(min=1, max=1000)
    guild_id = _snowflake(faker)
    user_id = _snowflake(faker)

    company = _create_company(
        company_id=company_id,
        guild_id=guild_id,
        owner_id=user_id,
    )

    mock_gateway = AsyncMock()
    mock_gateway.get_company.return_value = Ok(company)
    mock_gateway.check_license_valid.return_value = Ok(False)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.validate_company_operation(
        company_id=company_id,
        user_id=user_id,
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, CompanyLicenseInvalidError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_company_operation_database_error(faker: Faker) -> None:
    """測試資料庫錯誤時應返回錯誤。"""
    company_id = faker.random_int(min=1, max=1000)
    user_id = _snowflake(faker)

    mock_gateway = AsyncMock()
    mock_gateway.get_company.return_value = Err(DatabaseError("Connection failed"))

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool, gateway=mock_gateway)  # type: ignore[arg-type]

    result = await service.validate_company_operation(
        company_id=company_id,
        user_id=user_id,
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, DatabaseError)


# =============================================================================
# Test: get_company_balance
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_company_balance_success(faker: Faker) -> None:
    """測試成功取得公司餘額。"""
    guild_id = _snowflake(faker)
    account_id = faker.random_int(min=1000000, max=9999999)
    balance = faker.random_int(min=0, max=1000000)

    balance_record = BalanceRecord(
        guild_id=guild_id,
        member_id=account_id,
        balance=balance,
        last_modified_at=datetime.now(timezone.utc),
        throttled_until=None,
    )

    mock_econ_gateway = AsyncMock()
    mock_econ_gateway.fetch_balance_snapshot.return_value = Ok(balance_record)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool)  # type: ignore[arg-type]

    import src.bot.services.company_service as company_service_module

    original_econ_gateway = company_service_module.EconomyQueryGateway
    company_service_module.EconomyQueryGateway = lambda: mock_econ_gateway

    try:
        result = await service.get_company_balance(
            guild_id=guild_id,
            account_id=account_id,
        )

        assert isinstance(result, Ok)
        assert result.value == balance
    finally:
        company_service_module.EconomyQueryGateway = original_econ_gateway


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_company_balance_no_record(faker: Faker) -> None:
    """測試公司帳戶沒有餘額記錄時應返回 0。"""
    guild_id = _snowflake(faker)
    account_id = faker.random_int(min=1000000, max=9999999)

    mock_econ_gateway = AsyncMock()
    mock_econ_gateway.fetch_balance_snapshot.return_value = Ok(None)

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool)  # type: ignore[arg-type]

    import src.bot.services.company_service as company_service_module

    original_econ_gateway = company_service_module.EconomyQueryGateway
    company_service_module.EconomyQueryGateway = lambda: mock_econ_gateway

    try:
        result = await service.get_company_balance(
            guild_id=guild_id,
            account_id=account_id,
        )

        assert isinstance(result, Ok)
        assert result.value == 0
    finally:
        company_service_module.EconomyQueryGateway = original_econ_gateway


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_company_balance_database_error(faker: Faker) -> None:
    """測試查詢餘額時資料庫錯誤。"""
    guild_id = _snowflake(faker)
    account_id = faker.random_int(min=1000000, max=9999999)

    mock_econ_gateway = AsyncMock()
    mock_econ_gateway.fetch_balance_snapshot.return_value = Err(DatabaseError("Connection failed"))

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool)  # type: ignore[arg-type]

    import src.bot.services.company_service as company_service_module

    original_econ_gateway = company_service_module.EconomyQueryGateway
    company_service_module.EconomyQueryGateway = lambda: mock_econ_gateway

    try:
        result = await service.get_company_balance(
            guild_id=guild_id,
            account_id=account_id,
        )

        assert isinstance(result, Err)
        assert isinstance(result.error, DatabaseError)
    finally:
        company_service_module.EconomyQueryGateway = original_econ_gateway


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_company_balance_exception(faker: Faker) -> None:
    """測試查詢餘額時異常處理。"""
    guild_id = _snowflake(faker)
    account_id = faker.random_int(min=1000000, max=9999999)

    mock_econ_gateway = AsyncMock()
    mock_econ_gateway.fetch_balance_snapshot.side_effect = RuntimeError("Unexpected error")

    fake_conn = FakeConnection()
    fake_pool = FakePool(fake_conn)

    service = CompanyService(pool=fake_pool)  # type: ignore[arg-type]

    import src.bot.services.company_service as company_service_module

    original_econ_gateway = company_service_module.EconomyQueryGateway
    company_service_module.EconomyQueryGateway = lambda: mock_econ_gateway

    try:
        result = await service.get_company_balance(
            guild_id=guild_id,
            account_id=account_id,
        )

        assert isinstance(result, Err)
        assert isinstance(result.error, DatabaseError)
        assert "Unexpected error" in str(result.error)
    finally:
        company_service_module.EconomyQueryGateway = original_econ_gateway
