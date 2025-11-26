"""Unit tests for Government Applications Gateway.

Tests WelfareApplicationGateway and LicenseApplicationGateway CRUD operations
with mocked database connections using Result<T,E> pattern.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.cython_ext.state_council_models import (
    LicenseApplication,
    LicenseApplicationListResult,
    WelfareApplication,
    WelfareApplicationListResult,
)
from src.db.gateway.government_applications import (
    LicenseApplicationGateway,
    WelfareApplicationGateway,
)
from src.infra.result import DatabaseError


def _snowflake() -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return secrets.randbits(63)


def _create_welfare_mock_record(
    application_id: int,
    guild_id: int,
    applicant_id: int,
    amount: int,
    reason: str,
    status: str = "pending",
    reviewer_id: int | None = None,
    reviewed_at: datetime | None = None,
    rejection_reason: str | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a mock asyncpg.Record as dict for welfare application."""
    now = datetime.now(timezone.utc)
    return {
        "id": application_id,
        "guild_id": guild_id,
        "applicant_id": applicant_id,
        "amount": amount,
        "reason": reason,
        "status": status,
        "created_at": created_at or now,
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at,
        "rejection_reason": rejection_reason,
    }


def _create_license_mock_record(
    application_id: int,
    guild_id: int,
    applicant_id: int,
    license_type: str,
    reason: str,
    status: str = "pending",
    reviewer_id: int | None = None,
    reviewed_at: datetime | None = None,
    rejection_reason: str | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a mock asyncpg.Record as dict for license application."""
    now = datetime.now(timezone.utc)
    return {
        "id": application_id,
        "guild_id": guild_id,
        "applicant_id": applicant_id,
        "license_type": license_type,
        "reason": reason,
        "status": status,
        "created_at": created_at or now,
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at,
        "rejection_reason": rejection_reason,
    }


# ========== Welfare Application Gateway Tests ==========


@pytest.mark.unit
class TestWelfareApplicationGateway:
    """Test suite for WelfareApplicationGateway."""

    @pytest.mark.asyncio
    async def test_create_application_success(self) -> None:
        """Test creating a welfare application returns Ok with application data."""
        gateway = WelfareApplicationGateway()
        mock_conn = AsyncMock()
        guild_id = _snowflake()
        applicant_id = _snowflake()
        application_id = 1

        mock_record = _create_welfare_mock_record(
            application_id=application_id,
            guild_id=guild_id,
            applicant_id=applicant_id,
            amount=1000,
            reason="經濟困難",
        )
        mock_conn.fetchrow = AsyncMock(return_value=mock_record)

        result = await gateway.create_application(
            mock_conn,
            guild_id=guild_id,
            applicant_id=applicant_id,
            amount=1000,
            reason="經濟困難",
        )

        assert result.is_ok()
        app = result.unwrap()
        assert isinstance(app, WelfareApplication)
        assert app.id == application_id
        assert app.guild_id == guild_id
        assert app.applicant_id == applicant_id
        assert app.amount == 1000
        assert app.reason == "經濟困難"
        assert app.status == "pending"

    @pytest.mark.asyncio
    async def test_create_application_failure(self) -> None:
        """Test creating welfare application returns Err on DB failure."""
        gateway = WelfareApplicationGateway()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await gateway.create_application(
            mock_conn,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            amount=1000,
            reason="test",
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, DatabaseError)

    @pytest.mark.asyncio
    async def test_get_application_found(self) -> None:
        """Test getting an existing welfare application."""
        gateway = WelfareApplicationGateway()
        mock_conn = AsyncMock()
        application_id = 42

        mock_record = _create_welfare_mock_record(
            application_id=application_id,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            amount=500,
            reason="測試",
        )
        mock_conn.fetchrow = AsyncMock(return_value=mock_record)

        result = await gateway.get_application(mock_conn, application_id=application_id)

        assert result.is_ok()
        app = result.unwrap()
        assert app is not None
        assert app.id == application_id
        assert app.amount == 500

    @pytest.mark.asyncio
    async def test_get_application_not_found(self) -> None:
        """Test getting a non-existent welfare application returns None."""
        gateway = WelfareApplicationGateway()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await gateway.get_application(mock_conn, application_id=999)

        assert result.is_ok()
        assert result.unwrap() is None

    @pytest.mark.asyncio
    async def test_list_applications_with_pagination(self) -> None:
        """Test listing welfare applications with pagination."""
        gateway = WelfareApplicationGateway()
        mock_conn = AsyncMock()
        guild_id = _snowflake()

        # Mock count query
        mock_count = MagicMock()
        mock_count.__getitem__ = lambda self, idx: 25  # total count

        mock_records = [
            _create_welfare_mock_record(
                application_id=i,
                guild_id=guild_id,
                applicant_id=_snowflake(),
                amount=100 * i,
                reason=f"原因{i}",
            )
            for i in range(1, 11)
        ]

        mock_conn.fetchrow = AsyncMock(return_value=mock_count)
        mock_conn.fetch = AsyncMock(return_value=mock_records)

        result = await gateway.list_applications(
            mock_conn,
            guild_id=guild_id,
            page=1,
            page_size=10,
        )

        assert result.is_ok()
        list_result = result.unwrap()
        assert isinstance(list_result, WelfareApplicationListResult)
        assert len(list_result.applications) == 10
        assert list_result.total_count == 25
        assert list_result.page == 1
        assert list_result.page_size == 10

    @pytest.mark.asyncio
    async def test_list_applications_with_status_filter(self) -> None:
        """Test filtering welfare applications by status."""
        gateway = WelfareApplicationGateway()
        mock_conn = AsyncMock()
        guild_id = _snowflake()

        mock_count = MagicMock()
        mock_count.__getitem__ = lambda self, idx: 5

        pending_records = [
            _create_welfare_mock_record(
                application_id=i,
                guild_id=guild_id,
                applicant_id=_snowflake(),
                amount=100,
                reason="待審",
                status="pending",
            )
            for i in range(1, 6)
        ]

        mock_conn.fetchrow = AsyncMock(return_value=mock_count)
        mock_conn.fetch = AsyncMock(return_value=pending_records)

        result = await gateway.list_applications(
            mock_conn,
            guild_id=guild_id,
            status="pending",
        )

        assert result.is_ok()
        list_result = result.unwrap()
        assert all(app.status == "pending" for app in list_result.applications)

    @pytest.mark.asyncio
    async def test_approve_application_success(self) -> None:
        """Test approving a welfare application."""
        gateway = WelfareApplicationGateway()
        mock_conn = AsyncMock()
        application_id = 10
        reviewer_id = _snowflake()

        mock_record = _create_welfare_mock_record(
            application_id=application_id,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            amount=1000,
            reason="測試",
            status="approved",
            reviewer_id=reviewer_id,
            reviewed_at=datetime.now(timezone.utc),
        )
        mock_conn.fetchrow = AsyncMock(return_value=mock_record)

        result = await gateway.approve_application(
            mock_conn,
            application_id=application_id,
            reviewer_id=reviewer_id,
        )

        assert result.is_ok()
        app = result.unwrap()
        assert app.status == "approved"
        assert app.reviewer_id == reviewer_id
        assert app.reviewed_at is not None

    @pytest.mark.asyncio
    async def test_approve_application_not_pending(self) -> None:
        """Test approving non-pending application returns error."""
        gateway = WelfareApplicationGateway()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await gateway.approve_application(
            mock_conn,
            application_id=10,
            reviewer_id=_snowflake(),
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, DatabaseError)

    @pytest.mark.asyncio
    async def test_reject_application_success(self) -> None:
        """Test rejecting a welfare application."""
        gateway = WelfareApplicationGateway()
        mock_conn = AsyncMock()
        application_id = 20
        reviewer_id = _snowflake()
        rejection_reason = "不符合資格"

        mock_record = _create_welfare_mock_record(
            application_id=application_id,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            amount=1000,
            reason="測試",
            status="rejected",
            reviewer_id=reviewer_id,
            reviewed_at=datetime.now(timezone.utc),
            rejection_reason=rejection_reason,
        )
        mock_conn.fetchrow = AsyncMock(return_value=mock_record)

        result = await gateway.reject_application(
            mock_conn,
            application_id=application_id,
            reviewer_id=reviewer_id,
            rejection_reason=rejection_reason,
        )

        assert result.is_ok()
        app = result.unwrap()
        assert app.status == "rejected"
        assert app.rejection_reason == rejection_reason

    @pytest.mark.asyncio
    async def test_get_user_applications(self) -> None:
        """Test getting applications for a specific user."""
        gateway = WelfareApplicationGateway()
        mock_conn = AsyncMock()
        guild_id = _snowflake()
        applicant_id = _snowflake()

        mock_records = [
            _create_welfare_mock_record(
                application_id=i,
                guild_id=guild_id,
                applicant_id=applicant_id,
                amount=100 * i,
                reason=f"原因{i}",
            )
            for i in range(1, 4)
        ]
        mock_conn.fetch = AsyncMock(return_value=mock_records)

        result = await gateway.get_user_applications(
            mock_conn,
            guild_id=guild_id,
            applicant_id=applicant_id,
            limit=20,
        )

        assert result.is_ok()
        apps = result.unwrap()
        assert len(apps) == 3
        assert all(app.applicant_id == applicant_id for app in apps)


# ========== License Application Gateway Tests ==========


@pytest.mark.unit
class TestLicenseApplicationGateway:
    """Test suite for LicenseApplicationGateway."""

    @pytest.mark.asyncio
    async def test_create_application_success(self) -> None:
        """Test creating a license application returns Ok with application data."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()
        guild_id = _snowflake()
        applicant_id = _snowflake()
        application_id = 1

        mock_record = _create_license_mock_record(
            application_id=application_id,
            guild_id=guild_id,
            applicant_id=applicant_id,
            license_type="餐飲業",
            reason="開設餐廳",
        )
        mock_conn.fetchrow = AsyncMock(return_value=mock_record)

        result = await gateway.create_application(
            mock_conn,
            guild_id=guild_id,
            applicant_id=applicant_id,
            license_type="餐飲業",
            reason="開設餐廳",
        )

        assert result.is_ok()
        app = result.unwrap()
        assert isinstance(app, LicenseApplication)
        assert app.id == application_id
        assert app.license_type == "餐飲業"
        assert app.reason == "開設餐廳"
        assert app.status == "pending"

    @pytest.mark.asyncio
    async def test_create_application_failure(self) -> None:
        """Test creating license application returns Err on DB failure."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await gateway.create_application(
            mock_conn,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            license_type="test",
            reason="test",
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, DatabaseError)

    @pytest.mark.asyncio
    async def test_get_application_found(self) -> None:
        """Test getting an existing license application."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()
        application_id = 42

        mock_record = _create_license_mock_record(
            application_id=application_id,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            license_type="零售業",
            reason="開店",
        )
        mock_conn.fetchrow = AsyncMock(return_value=mock_record)

        result = await gateway.get_application(mock_conn, application_id=application_id)

        assert result.is_ok()
        app = result.unwrap()
        assert app is not None
        assert app.id == application_id
        assert app.license_type == "零售業"

    @pytest.mark.asyncio
    async def test_get_application_not_found(self) -> None:
        """Test getting a non-existent license application returns None."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await gateway.get_application(mock_conn, application_id=999)

        assert result.is_ok()
        assert result.unwrap() is None

    @pytest.mark.asyncio
    async def test_list_applications_with_pagination(self) -> None:
        """Test listing license applications with pagination."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()
        guild_id = _snowflake()

        mock_count = MagicMock()
        mock_count.__getitem__ = lambda self, idx: 15

        mock_records = [
            _create_license_mock_record(
                application_id=i,
                guild_id=guild_id,
                applicant_id=_snowflake(),
                license_type="服務業",
                reason=f"原因{i}",
            )
            for i in range(1, 11)
        ]

        mock_conn.fetchrow = AsyncMock(return_value=mock_count)
        mock_conn.fetch = AsyncMock(return_value=mock_records)

        result = await gateway.list_applications(
            mock_conn,
            guild_id=guild_id,
            page=1,
            page_size=10,
        )

        assert result.is_ok()
        list_result = result.unwrap()
        assert isinstance(list_result, LicenseApplicationListResult)
        assert len(list_result.applications) == 10
        assert list_result.total_count == 15

    @pytest.mark.asyncio
    async def test_list_applications_with_license_type_filter(self) -> None:
        """Test filtering license applications by license type."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()
        guild_id = _snowflake()

        mock_count = MagicMock()
        mock_count.__getitem__ = lambda self, idx: 3

        mock_records = [
            _create_license_mock_record(
                application_id=i,
                guild_id=guild_id,
                applicant_id=_snowflake(),
                license_type="餐飲業",
                reason="開店",
            )
            for i in range(1, 4)
        ]

        mock_conn.fetchrow = AsyncMock(return_value=mock_count)
        mock_conn.fetch = AsyncMock(return_value=mock_records)

        result = await gateway.list_applications(
            mock_conn,
            guild_id=guild_id,
            license_type="餐飲業",
        )

        assert result.is_ok()
        list_result = result.unwrap()
        assert all(app.license_type == "餐飲業" for app in list_result.applications)

    @pytest.mark.asyncio
    async def test_approve_application_success(self) -> None:
        """Test approving a license application."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()
        application_id = 10
        reviewer_id = _snowflake()

        mock_record = _create_license_mock_record(
            application_id=application_id,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            license_type="製造業",
            reason="建廠",
            status="approved",
            reviewer_id=reviewer_id,
            reviewed_at=datetime.now(timezone.utc),
        )
        mock_conn.fetchrow = AsyncMock(return_value=mock_record)

        result = await gateway.approve_application(
            mock_conn,
            application_id=application_id,
            reviewer_id=reviewer_id,
        )

        assert result.is_ok()
        app = result.unwrap()
        assert app.status == "approved"
        assert app.reviewer_id == reviewer_id

    @pytest.mark.asyncio
    async def test_reject_application_success(self) -> None:
        """Test rejecting a license application."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()
        application_id = 20
        reviewer_id = _snowflake()
        rejection_reason = "資料不完整"

        mock_record = _create_license_mock_record(
            application_id=application_id,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            license_type="服務業",
            reason="經營",
            status="rejected",
            reviewer_id=reviewer_id,
            reviewed_at=datetime.now(timezone.utc),
            rejection_reason=rejection_reason,
        )
        mock_conn.fetchrow = AsyncMock(return_value=mock_record)

        result = await gateway.reject_application(
            mock_conn,
            application_id=application_id,
            reviewer_id=reviewer_id,
            rejection_reason=rejection_reason,
        )

        assert result.is_ok()
        app = result.unwrap()
        assert app.status == "rejected"
        assert app.rejection_reason == rejection_reason

    @pytest.mark.asyncio
    async def test_check_pending_application_exists(self) -> None:
        """Test checking for existing pending application."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()
        guild_id = _snowflake()
        applicant_id = _snowflake()

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, idx: True
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await gateway.check_pending_application(
            mock_conn,
            guild_id=guild_id,
            applicant_id=applicant_id,
            license_type="餐飲業",
        )

        assert result.is_ok()
        assert result.unwrap() is True

    @pytest.mark.asyncio
    async def test_check_pending_application_not_exists(self) -> None:
        """Test checking for non-existing pending application."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, idx: False
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await gateway.check_pending_application(
            mock_conn,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            license_type="餐飲業",
        )

        assert result.is_ok()
        assert result.unwrap() is False

    @pytest.mark.asyncio
    async def test_get_user_applications(self) -> None:
        """Test getting license applications for a specific user."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()
        guild_id = _snowflake()
        applicant_id = _snowflake()

        mock_records = [
            _create_license_mock_record(
                application_id=i,
                guild_id=guild_id,
                applicant_id=applicant_id,
                license_type=f"類型{i}",
                reason=f"原因{i}",
            )
            for i in range(1, 5)
        ]
        mock_conn.fetch = AsyncMock(return_value=mock_records)

        result = await gateway.get_user_applications(
            mock_conn,
            guild_id=guild_id,
            applicant_id=applicant_id,
            limit=20,
        )

        assert result.is_ok()
        apps = result.unwrap()
        assert len(apps) == 4
        assert all(app.applicant_id == applicant_id for app in apps)


# ========== Error Handling Tests ==========


@pytest.mark.unit
class TestGatewayErrorHandling:
    """Test Result<T,E> error handling for gateways."""

    @pytest.mark.asyncio
    async def test_welfare_gateway_handles_database_exception(self) -> None:
        """Test that database exceptions are wrapped in DatabaseError."""
        gateway = WelfareApplicationGateway()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=RuntimeError("DB connection failed"))

        result = await gateway.create_application(
            mock_conn,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            amount=100,
            reason="test",
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, DatabaseError)

    @pytest.mark.asyncio
    async def test_license_gateway_handles_database_exception(self) -> None:
        """Test that database exceptions are wrapped in DatabaseError."""
        gateway = LicenseApplicationGateway()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=RuntimeError("DB connection failed"))

        result = await gateway.create_application(
            mock_conn,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            license_type="test",
            reason="test",
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, DatabaseError)
