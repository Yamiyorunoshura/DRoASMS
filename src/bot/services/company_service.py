"""Company Service for Business Entity Management.

Provides business logic for company management with Result<T,E> pattern.
"""

from __future__ import annotations

from typing import Any, Sequence, cast
from uuid import UUID

import structlog

from src.cython_ext.state_council_models import (
    AvailableLicense,
    Company,
    CompanyListResult,
)
from src.db.gateway.company import CompanyGateway
from src.db.gateway.economy_queries import EconomyQueryGateway
from src.infra.result import (
    DatabaseError,
    Err,
    Error,
    Ok,
    Result,
)
from src.infra.types.db import PoolProtocol

LOGGER = structlog.get_logger(__name__)


class CompanyError(Error):
    """Base error for company-related failures."""


class CompanyNotFoundError(CompanyError):
    """Raised when a company is not found."""

    def __init__(self, message: str = "Company not found", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class CompanyOwnershipError(CompanyError):
    """Raised when user doesn't own the company."""

    def __init__(self, message: str = "您沒有權限管理此公司", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class CompanyLicenseInvalidError(CompanyError):
    """Raised when the company's license is invalid."""

    def __init__(self, message: str = "此公司的商業許可已失效", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class NoAvailableLicenseError(CompanyError):
    """Raised when user has no available licenses."""

    def __init__(
        self, message: str = "您沒有可用的商業許可，請先申請商業許可", **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)


class LicenseAlreadyUsedError(CompanyError):
    """Raised when the license is already associated with a company."""

    def __init__(self, message: str = "此許可證已關聯一家公司", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class InvalidCompanyNameError(CompanyError):
    """Raised when company name is invalid."""

    def __init__(self, message: str = "公司名稱必須為 1-100 個字元", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class CompanyService:
    """Business logic for company management."""

    def __init__(
        self,
        pool: PoolProtocol,
        *,
        gateway: CompanyGateway | None = None,
    ) -> None:
        self._pool = pool
        self._gateway = gateway or CompanyGateway()

    async def create_company(
        self,
        *,
        guild_id: int,
        owner_id: int,
        license_id: UUID,
        name: str,
    ) -> Result[Company, Error]:
        """創建公司。

        Args:
            guild_id: Discord 伺服器 ID
            owner_id: 擁有者 ID
            license_id: 關聯的商業許可 ID
            name: 公司名稱

        Returns:
            Result[Company, Error]: 成功返回公司記錄，失敗返回錯誤
        """
        # Validate name
        name_stripped = name.strip()
        if len(name_stripped) < 1 or len(name_stripped) > 100:
            return Err(InvalidCompanyNameError())

        async with self._pool.acquire() as connection:
            try:
                next_id_result = await self._gateway.next_company_id(connection)
                if isinstance(next_id_result, Err):
                    return Err(next_id_result.error)
                next_id = int(cast(Ok[int, Error], next_id_result).value)

                account_id = CompanyGateway.derive_account_id(guild_id, next_id)

                result = await self._gateway.create_company(
                    connection,
                    guild_id=guild_id,
                    owner_id=owner_id,
                    license_id=license_id,
                    name=name_stripped,
                    account_id=account_id,
                )

                if isinstance(result, Err):
                    error_msg = str(result.error)
                    if "Invalid or inactive license" in error_msg:
                        return Err(NoAvailableLicenseError())
                    if "already has an associated company" in error_msg:
                        return Err(LicenseAlreadyUsedError())
                    if "must be 1-100 characters" in error_msg:
                        return Err(InvalidCompanyNameError())
                    # Propagate gateway error
                    return Err(result.error)

                company = cast(Company, result.value)

                # Ensure balance record exists for the company account
                econ_q = EconomyQueryGateway()
                await econ_q.ensure_balance_record(
                    connection, guild_id=guild_id, member_id=account_id
                )

                LOGGER.info(
                    "company.created",
                    guild_id=guild_id,
                    owner_id=owner_id,
                    company_id=company.id,
                    account_id=account_id,
                )

                return Ok(company)

            except Exception as exc:
                LOGGER.exception(
                    "company.create.failed",
                    guild_id=guild_id,
                    owner_id=owner_id,
                    error=str(exc),
                )
                error_msg = str(exc)
                if "Invalid or inactive license" in error_msg:
                    return Err(NoAvailableLicenseError())
                if "already has an associated company" in error_msg:
                    return Err(LicenseAlreadyUsedError())
                if "must be 1-100 characters" in error_msg:
                    return Err(InvalidCompanyNameError())
                return Err(DatabaseError(f"Failed to create company: {exc}"))

    async def _ensure_balance_record(self, connection: Any, guild_id: int, account_id: int) -> None:
        econ_q = EconomyQueryGateway()
        try:
            await econ_q.ensure_balance_record(connection, guild_id=guild_id, member_id=account_id)
        except Exception as exc:
            LOGGER.warning(
                "company.ensure_balance.failed",
                guild_id=guild_id,
                account_id=account_id,
                error=str(exc),
            )

    async def get_company(
        self,
        *,
        company_id: int,
    ) -> Result[Company | None, Error]:
        """取得單一公司詳情。

        Args:
            company_id: 公司 ID

        Returns:
            Result[Company | None, Error]: 成功返回公司記錄，不存在返回 None
        """
        async with self._pool.acquire() as connection:
            result = await self._gateway.get_company(connection, company_id=company_id)
            return cast(Result[Company | None, Error], result)

    async def get_company_by_account(
        self,
        *,
        account_id: int,
    ) -> Result[Company | None, Error]:
        """根據帳戶 ID 取得公司。

        Args:
            account_id: 公司帳戶 ID

        Returns:
            Result[Company | None, Error]: 成功返回公司記錄，不存在返回 None
        """
        async with self._pool.acquire() as connection:
            result = await self._gateway.get_company_by_account(connection, account_id=account_id)
            return cast(Result[Company | None, Error], result)

    async def list_user_companies(
        self,
        *,
        guild_id: int,
        owner_id: int,
    ) -> Result[Sequence[Company], Error]:
        """列出用戶擁有的所有公司。

        Args:
            guild_id: Discord 伺服器 ID
            owner_id: 擁有者 ID

        Returns:
            Result[Sequence[Company], Error]: 公司列表
        """
        async with self._pool.acquire() as connection:
            result = await self._gateway.list_user_companies(
                connection, guild_id=guild_id, owner_id=owner_id
            )
            return cast(Result[Sequence[Company], Error], result)

    async def list_guild_companies(
        self,
        *,
        guild_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Result[CompanyListResult, Error]:
        """列出伺服器內所有公司（支援分頁）。

        Args:
            guild_id: Discord 伺服器 ID
            page: 頁碼（從 1 開始）
            page_size: 每頁筆數

        Returns:
            Result[CompanyListResult, Error]: 公司列表與分頁資訊
        """
        async with self._pool.acquire() as connection:
            result = await self._gateway.list_guild_companies(
                connection, guild_id=guild_id, page=page, page_size=page_size
            )
            return cast(Result[CompanyListResult, Error], result)

    async def get_available_licenses(
        self,
        *,
        guild_id: int,
        user_id: int,
    ) -> Result[Sequence[AvailableLicense], Error]:
        """取得用戶可用於建立公司的許可證。

        Args:
            guild_id: Discord 伺服器 ID
            user_id: 用戶 ID

        Returns:
            Result[Sequence[AvailableLicense], Error]: 可用許可證列表
        """
        async with self._pool.acquire() as connection:
            result = await self._gateway.get_available_licenses(
                connection, guild_id=guild_id, user_id=user_id
            )
            return cast(Result[Sequence[AvailableLicense], Error], result)

    async def check_ownership(
        self,
        *,
        company_id: int,
        user_id: int,
    ) -> Result[bool, Error]:
        """驗證公司擁有權。

        Args:
            company_id: 公司 ID
            user_id: 用戶 ID

        Returns:
            Result[bool, Error]: True 表示用戶擁有該公司
        """
        async with self._pool.acquire() as connection:
            result = await self._gateway.check_ownership(
                connection, company_id=company_id, user_id=user_id
            )
            return cast(Result[bool, Error], result)

    async def check_license_valid(
        self,
        *,
        company_id: int,
    ) -> Result[bool, Error]:
        """驗證公司許可證是否有效。

        Args:
            company_id: 公司 ID

        Returns:
            Result[bool, Error]: True 表示許可證有效
        """
        async with self._pool.acquire() as connection:
            result = await self._gateway.check_license_valid(connection, company_id=company_id)
            return cast(Result[bool, Error], result)

    async def validate_company_operation(
        self,
        *,
        company_id: int,
        user_id: int,
    ) -> Result[Company, Error]:
        """驗證用戶是否可以操作公司（擁有權 + 許可證有效）。

        Args:
            company_id: 公司 ID
            user_id: 用戶 ID

        Returns:
            Result[Company, Error]: 驗證通過返回公司記錄，否則返回錯誤
        """
        # Get company
        company_result = await self.get_company(company_id=company_id)
        if isinstance(company_result, Err):
            return Err(company_result.error)
        if company_result.value is None:
            return Err(CompanyNotFoundError())

        company = company_result.value

        # Check ownership
        if company.owner_id != user_id:
            return Err(CompanyOwnershipError())

        # Check license validity
        license_result = await self.check_license_valid(company_id=company_id)
        if isinstance(license_result, Err):
            return Err(license_result.error)
        if not license_result.value:
            return Err(CompanyLicenseInvalidError())

        return Ok(company)

    async def get_company_balance(
        self,
        *,
        guild_id: int,
        account_id: int,
    ) -> Result[int, Error]:
        """取得公司帳戶餘額。

        Args:
            guild_id: Discord 伺服器 ID
            account_id: 公司帳戶 ID

        Returns:
            Result[int, Error]: 餘額
        """
        async with self._pool.acquire() as connection:
            try:
                econ_q = EconomyQueryGateway()
                snapshot = await econ_q.fetch_balance_snapshot(
                    connection, guild_id=guild_id, member_id=account_id
                )
                if isinstance(snapshot, Err):
                    return Err(snapshot.error)
                record = snapshot.value
                return Ok(0 if record is None else int(record.balance))
            except Exception as exc:
                LOGGER.exception(
                    "company.get_balance.failed",
                    guild_id=guild_id,
                    account_id=account_id,
                    error=str(exc),
                )
                return Err(DatabaseError(f"Failed to get balance: {exc}"))
