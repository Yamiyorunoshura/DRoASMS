"""Company Gateway for Business Entity Management.

Provides CRUD operations for company management with Result<T,E> pattern.
"""

from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID

from src.cython_ext.state_council_models import (
    AvailableLicense,
    Company,
    CompanyListResult,
)
from src.infra.result import DatabaseError, Err, Error, Ok, Result, async_returns_result
from src.infra.types.db import ConnectionProtocol


def _row_to_company(row: dict[str, Any]) -> Company:
    """將資料庫 row 轉換為 Company 資料模型。"""
    return Company(
        id=row["id"],
        guild_id=row["guild_id"],
        owner_id=row["owner_id"],
        license_id=row["license_id"],
        name=row["name"],
        account_id=row["account_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        license_type=row.get("license_type"),
        license_status=row.get("license_status"),
    )


def _row_to_available_license(row: dict[str, Any]) -> AvailableLicense:
    """將資料庫 row 轉換為 AvailableLicense 資料模型。"""
    return AvailableLicense(
        license_id=row["license_id"],
        license_type=row["license_type"],
        issued_at=row["issued_at"],
        expires_at=row["expires_at"],
    )


class CompanyGateway:
    """Encapsulate CRUD ops for company tables."""

    def __init__(self, *, schema: str = "governance") -> None:
        self._schema = schema

    @async_returns_result(DatabaseError)
    async def next_company_id(self, connection: ConnectionProtocol) -> Result[int, Error]:
        """取得下一個公司 ID（使用序列）。"""
        sql = "SELECT nextval('governance.companies_id_seq'::regclass)"
        row = await connection.fetchrow(sql)
        if row is None:
            return Err(DatabaseError("Failed to get next company id"))
        return Ok(int(row[0]))

    @async_returns_result(DatabaseError)
    async def reset_company_sequence(
        self, connection: ConnectionProtocol, *, value: int
    ) -> Result[bool, Error]:
        """重置公司序列值以匹配剛產生的 ID。"""
        sql = "SELECT setval('governance.companies_id_seq'::regclass, $1, false)"
        await connection.execute(sql, value)
        return Ok(True)

    @async_returns_result(DatabaseError)
    async def create_company(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        owner_id: int,
        license_id: UUID,
        name: str,
        account_id: int,
    ) -> Result[Company, Error]:
        """創建公司。

        Args:
            connection: 資料庫連線
            guild_id: Discord 伺服器 ID
            owner_id: 擁有者 ID
            license_id: 關聯的商業許可 ID
            name: 公司名稱
            account_id: 公司帳戶 ID

        Returns:
            Result[Company, Error]: 成功返回公司記錄，失敗返回錯誤

        Raises:
            DatabaseError: 當許可證無效、已關聯公司或名稱無效時
        """
        sql = f"SELECT * FROM {self._schema}.fn_create_company($1, $2, $3, $4, $5)"
        row = await connection.fetchrow(
            sql,
            guild_id,
            owner_id,
            license_id,
            name,
            account_id,
        )
        if row is None:
            return Err(DatabaseError("Failed to create company"))
        return Ok(_row_to_company(dict(row)))

    @async_returns_result(DatabaseError)
    async def get_company(
        self,
        connection: ConnectionProtocol,
        *,
        company_id: int,
    ) -> Result[Company | None, Error]:
        """取得單一公司詳情。

        Args:
            connection: 資料庫連線
            company_id: 公司 ID

        Returns:
            Result[Company | None, Error]: 成功返回公司記錄，不存在返回 None
        """
        sql = f"SELECT * FROM {self._schema}.fn_get_company($1)"
        row = await connection.fetchrow(sql, company_id)
        if row is None:
            return Ok(None)
        return Ok(_row_to_company(dict(row)))

    @async_returns_result(DatabaseError)
    async def get_company_by_account(
        self,
        connection: ConnectionProtocol,
        *,
        account_id: int,
    ) -> Result[Company | None, Error]:
        """根據帳戶 ID 取得公司。

        Args:
            connection: 資料庫連線
            account_id: 公司帳戶 ID

        Returns:
            Result[Company | None, Error]: 成功返回公司記錄，不存在返回 None
        """
        sql = f"SELECT * FROM {self._schema}.fn_get_company_by_account($1)"
        row = await connection.fetchrow(sql, account_id)
        if row is None:
            return Ok(None)
        return Ok(_row_to_company(dict(row)))

    @async_returns_result(DatabaseError)
    async def list_user_companies(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        owner_id: int,
    ) -> Result[Sequence[Company], Error]:
        """列出用戶擁有的所有公司。

        Args:
            connection: 資料庫連線
            guild_id: Discord 伺服器 ID
            owner_id: 擁有者 ID

        Returns:
            Result[Sequence[Company], Error]: 公司列表
        """
        sql = f"SELECT * FROM {self._schema}.fn_list_user_companies($1, $2)"
        rows = await connection.fetch(sql, guild_id, owner_id)
        return Ok([_row_to_company(dict(row)) for row in rows])

    @async_returns_result(DatabaseError)
    async def list_guild_companies(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Result[CompanyListResult, Error]:
        """列出伺服器內所有公司（支援分頁）。

        Args:
            connection: 資料庫連線
            guild_id: Discord 伺服器 ID
            page: 頁碼（從 1 開始）
            page_size: 每頁筆數

        Returns:
            Result[CompanyListResult, Error]: 公司列表與分頁資訊
        """
        offset = (page - 1) * page_size
        sql = f"SELECT * FROM {self._schema}.fn_list_guild_companies($1, $2, $3)"
        rows = await connection.fetch(sql, guild_id, page_size, offset)

        companies: list[Company] = []
        total_count = 0

        for row in rows:
            row_dict = dict(row)
            total_count = row_dict.get("total_count", 0)
            companies.append(_row_to_company(row_dict))

        return Ok(
            CompanyListResult(
                companies=companies,
                total_count=total_count,
                page=page,
                page_size=page_size,
            )
        )

    @async_returns_result(DatabaseError)
    async def get_available_licenses(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        user_id: int,
    ) -> Result[Sequence[AvailableLicense], Error]:
        """取得用戶可用於建立公司的許可證。

        Args:
            connection: 資料庫連線
            guild_id: Discord 伺服器 ID
            user_id: 用戶 ID

        Returns:
            Result[Sequence[AvailableLicense], Error]: 可用許可證列表
        """
        sql = f"SELECT * FROM {self._schema}.fn_get_available_licenses_for_company($1, $2)"
        rows = await connection.fetch(sql, guild_id, user_id)
        return Ok([_row_to_available_license(dict(row)) for row in rows])

    @async_returns_result(DatabaseError)
    async def check_ownership(
        self,
        connection: ConnectionProtocol,
        *,
        company_id: int,
        user_id: int,
    ) -> Result[bool, Error]:
        """驗證公司擁有權。

        Args:
            connection: 資料庫連線
            company_id: 公司 ID
            user_id: 用戶 ID

        Returns:
            Result[bool, Error]: True 表示用戶擁有該公司
        """
        sql = f"SELECT {self._schema}.fn_check_company_ownership($1, $2)"
        row = await connection.fetchrow(sql, company_id, user_id)
        if row is None:
            return Ok(False)
        return Ok(row[0])

    @async_returns_result(DatabaseError)
    async def check_license_valid(
        self,
        connection: ConnectionProtocol,
        *,
        company_id: int,
    ) -> Result[bool, Error]:
        """驗證公司許可證是否有效。

        Args:
            connection: 資料庫連線
            company_id: 公司 ID

        Returns:
            Result[bool, Error]: True 表示許可證有效
        """
        sql = f"SELECT {self._schema}.fn_check_company_license_valid($1)"
        row = await connection.fetchrow(sql, company_id)
        if row is None:
            return Ok(False)
        return Ok(row[0])

    @staticmethod
    def derive_account_id(guild_id: int, company_id: int) -> int:
        """計算公司帳戶 ID。

        2025-11 修正：原本以 `guild_id * 1000` 拼接，在 Discord 雪花 ID
        約 1.3e18 的情況下會溢出 PostgreSQL BIGINT（上限 9.22e18），導致
        asyncpg 拋出 "value out of int64 range"。改為僅使用全域唯一的
        company_id 做偏移，維持可預測且避免碰撞，並保留 9.6e15 區段與
        其它治理帳戶（9.0e15~9.5e15）分隔。

        Args:
            guild_id: Discord 伺服器 ID
            company_id: 公司 ID

        Returns:
            int: 公司帳戶 ID
        """
        base = 9_600_000_000_000_000
        # guild_id 參數保留相容性，但不再參與計算以避免 int64 溢位
        _ = guild_id
        return int(base + int(company_id))
