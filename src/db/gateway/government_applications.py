"""Government Applications Gateway.

Provides CRUD operations for welfare and business license applications
with Result<T,E> pattern.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Sequence

from src.cython_ext.state_council_models import (
    LicenseApplication,
    LicenseApplicationListResult,
    WelfareApplication,
    WelfareApplicationListResult,
)
from src.infra.result import DatabaseError, Err, Error, Ok, Result, async_returns_result
from src.infra.types.db import ConnectionProtocol

ApplicationStatus = Literal["pending", "approved", "rejected"]


def _row_to_welfare_application(row: dict[str, Any]) -> WelfareApplication:
    """將資料庫 row 轉換為 WelfareApplication 資料模型。"""
    return WelfareApplication(
        id=row["id"],
        guild_id=row["guild_id"],
        applicant_id=row["applicant_id"],
        amount=row["amount"],
        reason=row["reason"],
        status=row["status"],
        created_at=row["created_at"],
        reviewer_id=row.get("reviewer_id"),
        reviewed_at=row.get("reviewed_at"),
        rejection_reason=row.get("rejection_reason"),
    )


def _row_to_license_application(row: dict[str, Any]) -> LicenseApplication:
    """將資料庫 row 轉換為 LicenseApplication 資料模型。"""
    return LicenseApplication(
        id=row["id"],
        guild_id=row["guild_id"],
        applicant_id=row["applicant_id"],
        license_type=row["license_type"],
        reason=row["reason"],
        status=row["status"],
        created_at=row["created_at"],
        reviewer_id=row.get("reviewer_id"),
        reviewed_at=row.get("reviewed_at"),
        rejection_reason=row.get("rejection_reason"),
    )


class WelfareApplicationGateway:
    """福利申請 Gateway，提供 CRUD 操作。"""

    def __init__(self, *, schema: str = "governance") -> None:
        self._schema = schema

    @async_returns_result(DatabaseError)
    async def create_application(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        applicant_id: int,
        amount: int,
        reason: str,
    ) -> Result[WelfareApplication, Error]:
        """建立福利申請。

        Args:
            connection: 資料庫連線
            guild_id: Discord 伺服器 ID
            applicant_id: 申請人 ID
            amount: 申請金額
            reason: 申請原因

        Returns:
            Result[WelfareApplication, Error]: 成功返回申請記錄
        """
        sql = f"""
            INSERT INTO {self._schema}.welfare_applications
                (guild_id, applicant_id, amount, reason)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """
        row = await connection.fetchrow(sql, guild_id, applicant_id, amount, reason)
        if row is None:
            return Err(DatabaseError("Failed to create welfare application"))
        return Ok(_row_to_welfare_application(dict(row)))

    @async_returns_result(DatabaseError)
    async def get_application(
        self,
        connection: ConnectionProtocol,
        *,
        application_id: int,
    ) -> Result[WelfareApplication | None, Error]:
        """取得單一申請詳情。"""
        sql = f"""
            SELECT * FROM {self._schema}.welfare_applications
            WHERE id = $1
        """
        row = await connection.fetchrow(sql, application_id)
        if row is None:
            return Ok(None)
        return Ok(_row_to_welfare_application(dict(row)))

    @async_returns_result(DatabaseError)
    async def list_applications(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        status: ApplicationStatus | None = None,
        applicant_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Result[WelfareApplicationListResult, Error]:
        """列出申請（支援篩選與分頁）。"""
        offset = (page - 1) * page_size
        conditions = ["guild_id = $1"]
        params: list[Any] = [guild_id]
        param_idx = 2

        if status is not None:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if applicant_id is not None:
            conditions.append(f"applicant_id = ${param_idx}")
            params.append(applicant_id)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # Get total count
        count_sql = f"""
            SELECT COUNT(*) FROM {self._schema}.welfare_applications
            WHERE {where_clause}
        """
        count_row = await connection.fetchrow(count_sql, *params)
        total_count = count_row[0] if count_row else 0

        # Get paginated results
        params.extend([page_size, offset])
        sql = f"""
            SELECT * FROM {self._schema}.welfare_applications
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        rows = await connection.fetch(sql, *params)

        applications = [_row_to_welfare_application(dict(row)) for row in rows]
        return Ok(
            WelfareApplicationListResult(
                applications=applications,
                total_count=total_count,
                page=page,
                page_size=page_size,
            )
        )

    @async_returns_result(DatabaseError)
    async def approve_application(
        self,
        connection: ConnectionProtocol,
        *,
        application_id: int,
        reviewer_id: int,
    ) -> Result[WelfareApplication, Error]:
        """批准申請。"""
        sql = f"""
            UPDATE {self._schema}.welfare_applications
            SET status = 'approved',
                reviewer_id = $2,
                reviewed_at = $3
            WHERE id = $1 AND status = 'pending'
            RETURNING *
        """
        now = datetime.now(timezone.utc)
        row = await connection.fetchrow(sql, application_id, reviewer_id, now)
        if row is None:
            return Err(DatabaseError("Application not found or not pending"))
        return Ok(_row_to_welfare_application(dict(row)))

    @async_returns_result(DatabaseError)
    async def reject_application(
        self,
        connection: ConnectionProtocol,
        *,
        application_id: int,
        reviewer_id: int,
        rejection_reason: str,
    ) -> Result[WelfareApplication, Error]:
        """拒絕申請。"""
        sql = f"""
            UPDATE {self._schema}.welfare_applications
            SET status = 'rejected',
                reviewer_id = $2,
                reviewed_at = $3,
                rejection_reason = $4
            WHERE id = $1 AND status = 'pending'
            RETURNING *
        """
        now = datetime.now(timezone.utc)
        row = await connection.fetchrow(sql, application_id, reviewer_id, now, rejection_reason)
        if row is None:
            return Err(DatabaseError("Application not found or not pending"))
        return Ok(_row_to_welfare_application(dict(row)))

    @async_returns_result(DatabaseError)
    async def get_user_applications(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        applicant_id: int,
        limit: int = 20,
    ) -> Result[Sequence[WelfareApplication], Error]:
        """取得用戶的申請記錄。"""
        sql = f"""
            SELECT * FROM {self._schema}.welfare_applications
            WHERE guild_id = $1 AND applicant_id = $2
            ORDER BY created_at DESC
            LIMIT $3
        """
        rows = await connection.fetch(sql, guild_id, applicant_id, limit)
        return Ok([_row_to_welfare_application(dict(row)) for row in rows])


class LicenseApplicationGateway:
    """商業許可申請 Gateway，提供 CRUD 操作。"""

    def __init__(self, *, schema: str = "governance") -> None:
        self._schema = schema

    @async_returns_result(DatabaseError)
    async def create_application(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        applicant_id: int,
        license_type: str,
        reason: str,
    ) -> Result[LicenseApplication, Error]:
        """建立商業許可申請。"""
        sql = f"""
            INSERT INTO {self._schema}.license_applications
                (guild_id, applicant_id, license_type, reason)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """
        row = await connection.fetchrow(sql, guild_id, applicant_id, license_type, reason)
        if row is None:
            return Err(DatabaseError("Failed to create license application"))
        return Ok(_row_to_license_application(dict(row)))

    @async_returns_result(DatabaseError)
    async def get_application(
        self,
        connection: ConnectionProtocol,
        *,
        application_id: int,
    ) -> Result[LicenseApplication | None, Error]:
        """取得單一申請詳情。"""
        sql = f"""
            SELECT * FROM {self._schema}.license_applications
            WHERE id = $1
        """
        row = await connection.fetchrow(sql, application_id)
        if row is None:
            return Ok(None)
        return Ok(_row_to_license_application(dict(row)))

    @async_returns_result(DatabaseError)
    async def list_applications(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        status: ApplicationStatus | None = None,
        applicant_id: int | None = None,
        license_type: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Result[LicenseApplicationListResult, Error]:
        """列出申請（支援篩選與分頁）。"""
        offset = (page - 1) * page_size
        conditions = ["guild_id = $1"]
        params: list[Any] = [guild_id]
        param_idx = 2

        if status is not None:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if applicant_id is not None:
            conditions.append(f"applicant_id = ${param_idx}")
            params.append(applicant_id)
            param_idx += 1

        if license_type is not None:
            conditions.append(f"license_type = ${param_idx}")
            params.append(license_type)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # Get total count
        count_sql = f"""
            SELECT COUNT(*) FROM {self._schema}.license_applications
            WHERE {where_clause}
        """
        count_row = await connection.fetchrow(count_sql, *params)
        total_count = count_row[0] if count_row else 0

        # Get paginated results
        params.extend([page_size, offset])
        sql = f"""
            SELECT * FROM {self._schema}.license_applications
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        rows = await connection.fetch(sql, *params)

        applications = [_row_to_license_application(dict(row)) for row in rows]
        return Ok(
            LicenseApplicationListResult(
                applications=applications,
                total_count=total_count,
                page=page,
                page_size=page_size,
            )
        )

    @async_returns_result(DatabaseError)
    async def approve_application(
        self,
        connection: ConnectionProtocol,
        *,
        application_id: int,
        reviewer_id: int,
    ) -> Result[LicenseApplication, Error]:
        """批准申請。"""
        sql = f"""
            UPDATE {self._schema}.license_applications
            SET status = 'approved',
                reviewer_id = $2,
                reviewed_at = $3
            WHERE id = $1 AND status = 'pending'
            RETURNING *
        """
        now = datetime.now(timezone.utc)
        row = await connection.fetchrow(sql, application_id, reviewer_id, now)
        if row is None:
            return Err(DatabaseError("Application not found or not pending"))
        return Ok(_row_to_license_application(dict(row)))

    @async_returns_result(DatabaseError)
    async def reject_application(
        self,
        connection: ConnectionProtocol,
        *,
        application_id: int,
        reviewer_id: int,
        rejection_reason: str,
    ) -> Result[LicenseApplication, Error]:
        """拒絕申請。"""
        sql = f"""
            UPDATE {self._schema}.license_applications
            SET status = 'rejected',
                reviewer_id = $2,
                reviewed_at = $3,
                rejection_reason = $4
            WHERE id = $1 AND status = 'pending'
            RETURNING *
        """
        now = datetime.now(timezone.utc)
        row = await connection.fetchrow(sql, application_id, reviewer_id, now, rejection_reason)
        if row is None:
            return Err(DatabaseError("Application not found or not pending"))
        return Ok(_row_to_license_application(dict(row)))

    @async_returns_result(DatabaseError)
    async def check_pending_application(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        applicant_id: int,
        license_type: str,
    ) -> Result[bool, Error]:
        """檢查用戶是否有相同類型的待審批申請。"""
        sql = f"""
            SELECT EXISTS(
                SELECT 1 FROM {self._schema}.license_applications
                WHERE guild_id = $1 AND applicant_id = $2
                  AND license_type = $3 AND status = 'pending'
            )
        """
        row = await connection.fetchrow(sql, guild_id, applicant_id, license_type)
        return Ok(row[0] if row else False)

    @async_returns_result(DatabaseError)
    async def get_user_applications(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        applicant_id: int,
        limit: int = 20,
    ) -> Result[Sequence[LicenseApplication], Error]:
        """取得用戶的申請記錄。"""
        sql = f"""
            SELECT * FROM {self._schema}.license_applications
            WHERE guild_id = $1 AND applicant_id = $2
            ORDER BY created_at DESC
            LIMIT $3
        """
        rows = await connection.fetch(sql, guild_id, applicant_id, limit)
        return Ok([_row_to_license_application(dict(row)) for row in rows])


__all__ = [
    "WelfareApplicationGateway",
    "LicenseApplicationGateway",
]
