"""Business License Gateway for Interior Affairs.

Provides CRUD operations for business license management with Result<T,E> pattern.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence
from uuid import UUID

from src.cython_ext.state_council_models import (
    BusinessLicense,
    BusinessLicenseListResult,
)
from src.infra.result import DatabaseError, Err, Error, Ok, Result, async_returns_result
from src.infra.types.db import ConnectionProtocol


def _row_to_license(row: dict[str, Any]) -> BusinessLicense:
    """將資料庫 row 轉換為 BusinessLicense 資料模型。"""
    return BusinessLicense(
        license_id=row["license_id"],
        guild_id=row["guild_id"],
        user_id=row["user_id"],
        license_type=row["license_type"],
        issued_by=row["issued_by"],
        issued_at=row["issued_at"],
        expires_at=row["expires_at"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        revoked_by=row.get("revoked_by"),
        revoked_at=row.get("revoked_at"),
        revoke_reason=row.get("revoke_reason"),
    )


class BusinessLicenseGateway:
    """Encapsulate CRUD ops for business license tables."""

    def __init__(self, *, schema: str = "governance") -> None:
        self._schema = schema

    @async_returns_result(DatabaseError)
    async def issue_license(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        user_id: int,
        license_type: str,
        issued_by: int,
        expires_at: datetime,
    ) -> Result[BusinessLicense, Error]:
        """發放商業許可給指定用戶。

        Args:
            connection: 資料庫連線
            guild_id: Discord 伺服器 ID
            user_id: 目標用戶 ID
            license_type: 許可類型
            issued_by: 核發人員 ID
            expires_at: 到期時間

        Returns:
            Result[BusinessLicense, Error]: 成功返回許可記錄，失敗返回錯誤

        Raises:
            DatabaseError: 當用戶已擁有相同類型有效許可時（unique_violation）
        """
        sql = f"SELECT * FROM {self._schema}.fn_issue_business_license(" "$1, $2, $3, $4, $5)"
        row = await connection.fetchrow(
            sql,
            guild_id,
            user_id,
            license_type,
            issued_by,
            expires_at,
        )
        if row is None:
            return Err(DatabaseError("Failed to issue license"))
        return Ok(_row_to_license(dict(row)))

    @async_returns_result(DatabaseError)
    async def revoke_license(
        self,
        connection: ConnectionProtocol,
        *,
        license_id: UUID,
        revoked_by: int,
        revoke_reason: str,
    ) -> Result[BusinessLicense, Error]:
        """撤銷商業許可。

        Args:
            connection: 資料庫連線
            license_id: 許可 ID
            revoked_by: 撤銷人員 ID
            revoke_reason: 撤銷原因

        Returns:
            Result[BusinessLicense, Error]: 成功返回更新後的許可記錄

        Raises:
            DatabaseError: 許可不存在或已非 active 狀態
        """
        sql = f"SELECT * FROM {self._schema}.fn_revoke_business_license(" "$1, $2, $3)"
        row = await connection.fetchrow(
            sql,
            license_id,
            revoked_by,
            revoke_reason,
        )
        if row is None:
            return Err(DatabaseError("Failed to revoke license"))
        return Ok(_row_to_license(dict(row)))

    @async_returns_result(DatabaseError)
    async def get_license(
        self,
        connection: ConnectionProtocol,
        *,
        license_id: UUID,
    ) -> Result[BusinessLicense | None, Error]:
        """取得單一許可詳情。

        Args:
            connection: 資料庫連線
            license_id: 許可 ID

        Returns:
            Result[BusinessLicense | None, Error]: 成功返回許可記錄，不存在返回 None
        """
        sql = f"SELECT * FROM {self._schema}.fn_get_business_license($1)"
        row = await connection.fetchrow(sql, license_id)
        if row is None:
            return Ok(None)
        return Ok(_row_to_license(dict(row)))

    @async_returns_result(DatabaseError)
    async def list_licenses(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        status: str | None = None,
        license_type: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Result[BusinessLicenseListResult, Error]:
        """列出許可（支援篩選與分頁）。

        Args:
            connection: 資料庫連線
            guild_id: Discord 伺服器 ID
            status: 篩選狀態（active/expired/revoked）
            license_type: 篩選許可類型
            page: 頁碼（從 1 開始）
            page_size: 每頁筆數

        Returns:
            Result[BusinessLicenseListResult, Error]: 許可列表與分頁資訊
        """
        offset = (page - 1) * page_size
        sql = f"SELECT * FROM {self._schema}.fn_list_business_licenses(" "$1, $2, $3, $4, $5)"
        rows = await connection.fetch(
            sql,
            guild_id,
            status,
            license_type,
            page_size,
            offset,
        )

        licenses: list[BusinessLicense] = []
        total_count = 0

        for row in rows:
            row_dict = dict(row)
            total_count = row_dict.get("total_count", 0)
            licenses.append(_row_to_license(row_dict))

        return Ok(
            BusinessLicenseListResult(
                licenses=licenses,
                total_count=total_count,
                page=page,
                page_size=page_size,
            )
        )

    @async_returns_result(DatabaseError)
    async def get_user_licenses(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        user_id: int,
    ) -> Result[Sequence[BusinessLicense], Error]:
        """取得特定用戶的所有許可。

        Args:
            connection: 資料庫連線
            guild_id: Discord 伺服器 ID
            user_id: 用戶 ID

        Returns:
            Result[Sequence[BusinessLicense], Error]: 用戶的許可列表
        """
        sql = f"SELECT * FROM {self._schema}.fn_get_user_licenses($1, $2)"
        rows = await connection.fetch(sql, guild_id, user_id)
        return Ok([_row_to_license(dict(row)) for row in rows])

    @async_returns_result(DatabaseError)
    async def check_active_license(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        user_id: int,
        license_type: str,
    ) -> Result[bool, Error]:
        """檢查用戶是否擁有特定類型的有效許可。

        Args:
            connection: 資料庫連線
            guild_id: Discord 伺服器 ID
            user_id: 用戶 ID
            license_type: 許可類型

        Returns:
            Result[bool, Error]: True 表示擁有有效許可
        """
        sql = f"SELECT {self._schema}.fn_check_active_license($1, $2, $3)"
        row = await connection.fetchrow(sql, guild_id, user_id, license_type)
        if row is None:
            return Ok(False)
        return Ok(row[0])

    @async_returns_result(DatabaseError)
    async def expire_licenses(
        self,
        connection: ConnectionProtocol,
    ) -> Result[int, Error]:
        """自動過期已到期的許可。

        Returns:
            Result[int, Error]: 過期的許可數量
        """
        sql = f"SELECT {self._schema}.fn_expire_business_licenses()"
        row = await connection.fetchrow(sql)
        if row is None:
            return Ok(0)
        return Ok(row[0])

    @async_returns_result(DatabaseError)
    async def count_by_status(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
    ) -> Result[dict[str, int], Error]:
        """統計各狀態的許可數量。

        Args:
            connection: 資料庫連線
            guild_id: Discord 伺服器 ID

        Returns:
            Result[dict[str, int], Error]: 狀態 -> 數量 的映射
        """
        sql = f"SELECT * FROM {self._schema}.fn_count_business_licenses_by_status($1)"
        rows = await connection.fetch(sql, guild_id)
        return Ok({row["status"]: row["count"] for row in rows})
