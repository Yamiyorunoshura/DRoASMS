"""Unit tests for ApplicationService.

Tests welfare and license application workflows with mocked gateways.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.services.application_service import (
    AlreadyHasActiveLicenseError,
    ApplicationNotFoundError,
    ApplicationNotPendingError,
    ApplicationService,
    DuplicatePendingApplicationError,
)
from src.cython_ext.state_council_models import (
    LicenseApplication,
    WelfareApplication,
)
from src.db.gateway.business_license import BusinessLicenseGateway
from src.db.gateway.government_applications import (
    LicenseApplicationGateway,
    WelfareApplicationGateway,
)
from src.infra.result import BusinessLogicError, DatabaseError, Err, Ok, ValidationError


def _snowflake() -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return secrets.randbits(63)


def _mock_welfare_app(
    id: int = 1,
    guild_id: int | None = None,
    applicant_id: int | None = None,
    amount: int = 1000,
    reason: str = "測試",
    status: str = "pending",
) -> WelfareApplication:
    """Create a mock WelfareApplication."""
    return WelfareApplication(
        id=id,
        guild_id=guild_id or _snowflake(),
        applicant_id=applicant_id or _snowflake(),
        amount=amount,
        reason=reason,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def _mock_license_app(
    id: int = 1,
    guild_id: int | None = None,
    applicant_id: int | None = None,
    license_type: str = "餐飲業",
    reason: str = "開店",
    status: str = "pending",
) -> LicenseApplication:
    """Create a mock LicenseApplication."""
    return LicenseApplication(
        id=id,
        guild_id=guild_id or _snowflake(),
        applicant_id=applicant_id or _snowflake(),
        license_type=license_type,
        reason=reason,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_pool() -> MagicMock:
    """Create a mock database pool."""
    pool = MagicMock()
    conn = AsyncMock()
    tx = AsyncMock()
    tx.__aenter__.return_value = tx
    tx.__aexit__.return_value = None
    conn.transaction = MagicMock(return_value=tx)
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool


@pytest.fixture
def mock_welfare_gateway() -> AsyncMock:
    """Create a mock WelfareApplicationGateway."""
    return AsyncMock(spec=WelfareApplicationGateway)


@pytest.fixture
def mock_license_gateway() -> AsyncMock:
    """Create a mock LicenseApplicationGateway."""
    return AsyncMock(spec=LicenseApplicationGateway)


@pytest.fixture
def mock_business_license_gateway() -> AsyncMock:
    """Create a mock BusinessLicenseGateway."""
    return AsyncMock(spec=BusinessLicenseGateway)


# ========== Welfare Application Service Tests ==========


@pytest.mark.unit
class TestWelfareApplicationService:
    """Test suite for welfare application service methods."""

    @pytest.mark.asyncio
    async def test_submit_welfare_application_success(
        self, mock_pool: MagicMock, mock_welfare_gateway: AsyncMock
    ) -> None:
        """Test successful welfare application submission."""
        guild_id = _snowflake()
        applicant_id = _snowflake()
        app = _mock_welfare_app(guild_id=guild_id, applicant_id=applicant_id)
        mock_welfare_gateway.create_application.return_value = Ok(app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)
            result = await service.submit_welfare_application(
                guild_id=guild_id,
                applicant_id=applicant_id,
                amount=1000,
                reason="經濟困難",
            )

        assert result.is_ok()
        assert result.unwrap().guild_id == guild_id

    @pytest.mark.asyncio
    async def test_submit_welfare_application_invalid_amount(
        self, mock_pool: MagicMock, mock_welfare_gateway: AsyncMock
    ) -> None:
        """Test welfare application with invalid amount returns ValidationError."""
        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)
            result = await service.submit_welfare_application(
                guild_id=_snowflake(),
                applicant_id=_snowflake(),
                amount=0,
                reason="測試",
            )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValidationError)

    @pytest.mark.asyncio
    async def test_submit_welfare_application_empty_reason(
        self, mock_pool: MagicMock, mock_welfare_gateway: AsyncMock
    ) -> None:
        """Test welfare application with empty reason returns ValidationError."""
        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)
            result = await service.submit_welfare_application(
                guild_id=_snowflake(),
                applicant_id=_snowflake(),
                amount=100,
                reason="   ",
            )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValidationError)

    @pytest.mark.asyncio
    async def test_approve_welfare_application_success(
        self, mock_pool: MagicMock, mock_welfare_gateway: AsyncMock
    ) -> None:
        """Test successful welfare application approval."""
        app_id = 10
        reviewer_id = _snowflake()
        pending_app = _mock_welfare_app(id=app_id, status="pending")
        approved_app = _mock_welfare_app(id=app_id, status="approved")

        mock_welfare_gateway.get_application.return_value = Ok(pending_app)
        mock_welfare_gateway.approve_application.return_value = Ok(approved_app)

        transfer_cb = AsyncMock(return_value=True)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)
            result = await service.approve_welfare_application(
                application_id=app_id,
                reviewer_id=reviewer_id,
                transfer_callback=transfer_cb,
            )

        assert result.is_ok()
        assert result.unwrap().status == "approved"
        transfer_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_approve_welfare_application_transfer_fails(
        self, mock_pool: MagicMock, mock_welfare_gateway: AsyncMock
    ) -> None:
        """Transfer callback失敗時應回傳 Err 並回滾。"""

        app_id = 11
        reviewer_id = _snowflake()
        pending_app = _mock_welfare_app(id=app_id, status="pending")
        approved_app = _mock_welfare_app(id=app_id, status="approved")

        mock_welfare_gateway.get_application.return_value = Ok(pending_app)
        mock_welfare_gateway.approve_application.return_value = Ok(approved_app)

        # callback 回傳 (False, message)
        transfer_cb = AsyncMock(return_value=(False, "insufficient funds"))

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)
            result = await service.approve_welfare_application(
                application_id=app_id,
                reviewer_id=reviewer_id,
                transfer_callback=transfer_cb,
            )

        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, BusinessLogicError)
        assert err.context.get("error_type") == "welfare_disburse_failed"
        transfer_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_approve_welfare_application_not_found(
        self, mock_pool: MagicMock, mock_welfare_gateway: AsyncMock
    ) -> None:
        """Test approving non-existent application returns error."""
        mock_welfare_gateway.get_application.return_value = Ok(None)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)
            result = await service.approve_welfare_application(
                application_id=999,
                reviewer_id=_snowflake(),
                transfer_callback=AsyncMock(),
            )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), ApplicationNotFoundError)

    @pytest.mark.asyncio
    async def test_approve_welfare_application_not_pending(
        self, mock_pool: MagicMock, mock_welfare_gateway: AsyncMock
    ) -> None:
        """Test approving non-pending application returns error."""
        app = _mock_welfare_app(status="approved")
        mock_welfare_gateway.get_application.return_value = Ok(app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)
            result = await service.approve_welfare_application(
                application_id=1,
                reviewer_id=_snowflake(),
                transfer_callback=AsyncMock(),
            )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), ApplicationNotPendingError)

    @pytest.mark.asyncio
    async def test_reject_welfare_application_success(
        self, mock_pool: MagicMock, mock_welfare_gateway: AsyncMock
    ) -> None:
        """Test successful welfare application rejection."""
        rejected_app = _mock_welfare_app(status="rejected")
        mock_welfare_gateway.reject_application.return_value = Ok(rejected_app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)
            result = await service.reject_welfare_application(
                application_id=1,
                reviewer_id=_snowflake(),
                rejection_reason="不符合資格",
            )

        assert result.is_ok()
        assert result.unwrap().status == "rejected"

    @pytest.mark.asyncio
    async def test_reject_welfare_application_empty_reason(
        self, mock_pool: MagicMock, mock_welfare_gateway: AsyncMock
    ) -> None:
        """Test rejecting with empty reason returns ValidationError."""
        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)
            result = await service.reject_welfare_application(
                application_id=1,
                reviewer_id=_snowflake(),
                rejection_reason="  ",
            )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValidationError)


# ========== License Application Service Tests ==========


@pytest.mark.unit
class TestLicenseApplicationService:
    """Test suite for license application service methods."""

    @pytest.mark.asyncio
    async def test_submit_license_application_success(
        self,
        mock_pool: MagicMock,
        mock_license_gateway: AsyncMock,
        mock_business_license_gateway: AsyncMock,
    ) -> None:
        """Test successful license application submission."""
        guild_id = _snowflake()
        applicant_id = _snowflake()
        app = _mock_license_app(guild_id=guild_id, applicant_id=applicant_id)

        mock_license_gateway.check_pending_application.return_value = Ok(False)
        mock_business_license_gateway.check_active_license.return_value = Ok(False)
        mock_license_gateway.create_application.return_value = Ok(app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(
                license_gateway=mock_license_gateway,
                business_license_gateway=mock_business_license_gateway,
            )
            result = await service.submit_license_application(
                guild_id=guild_id,
                applicant_id=applicant_id,
                license_type="餐飲業",
                reason="開設餐廳",
            )

        assert result.is_ok()
        assert result.unwrap().license_type == "餐飲業"

    @pytest.mark.asyncio
    async def test_submit_license_application_duplicate_pending(
        self,
        mock_pool: MagicMock,
        mock_license_gateway: AsyncMock,
        mock_business_license_gateway: AsyncMock,
    ) -> None:
        """Test submitting duplicate pending application returns error."""
        mock_license_gateway.check_pending_application.return_value = Ok(True)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(
                license_gateway=mock_license_gateway,
                business_license_gateway=mock_business_license_gateway,
            )
            result = await service.submit_license_application(
                guild_id=_snowflake(),
                applicant_id=_snowflake(),
                license_type="餐飲業",
                reason="開店",
            )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), DuplicatePendingApplicationError)

    @pytest.mark.asyncio
    async def test_submit_license_application_already_has_license(
        self,
        mock_pool: MagicMock,
        mock_license_gateway: AsyncMock,
        mock_business_license_gateway: AsyncMock,
    ) -> None:
        """Test submitting when already has active license returns error."""
        mock_license_gateway.check_pending_application.return_value = Ok(False)
        mock_business_license_gateway.check_active_license.return_value = Ok(True)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(
                license_gateway=mock_license_gateway,
                business_license_gateway=mock_business_license_gateway,
            )
            result = await service.submit_license_application(
                guild_id=_snowflake(),
                applicant_id=_snowflake(),
                license_type="餐飲業",
                reason="開店",
            )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), AlreadyHasActiveLicenseError)

    @pytest.mark.asyncio
    async def test_approve_license_application_success(
        self,
        mock_pool: MagicMock,
        mock_license_gateway: AsyncMock,
        mock_business_license_gateway: AsyncMock,
    ) -> None:
        """Test successful license application approval with license issuance."""
        pending_app = _mock_license_app(status="pending")
        approved_app = _mock_license_app(status="approved")

        mock_license_gateway.get_application.return_value = Ok(pending_app)
        mock_business_license_gateway.check_active_license.return_value = Ok(False)
        mock_business_license_gateway.issue_license.return_value = Ok(MagicMock())
        mock_license_gateway.approve_application.return_value = Ok(approved_app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(
                license_gateway=mock_license_gateway,
                business_license_gateway=mock_business_license_gateway,
            )
            result = await service.approve_license_application(
                application_id=1,
                reviewer_id=_snowflake(),
            )

        assert result.is_ok()
        assert result.unwrap().status == "approved"
        mock_business_license_gateway.issue_license.assert_called_once()

    @pytest.mark.asyncio
    async def test_reject_license_application_success(
        self, mock_pool: MagicMock, mock_license_gateway: AsyncMock
    ) -> None:
        """Test successful license application rejection."""
        rejected_app = _mock_license_app(status="rejected")
        mock_license_gateway.reject_application.return_value = Ok(rejected_app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(license_gateway=mock_license_gateway)
            result = await service.reject_license_application(
                application_id=1,
                reviewer_id=_snowflake(),
                rejection_reason="資料不完整",
            )

        assert result.is_ok()
        assert result.unwrap().status == "rejected"


# ========== Error Handling Tests ==========


@pytest.mark.unit
class TestApplicationServiceErrorHandling:
    """Test Result<T,E> error propagation in ApplicationService."""

    @pytest.mark.asyncio
    async def test_welfare_gateway_error_propagates(
        self, mock_pool: MagicMock, mock_welfare_gateway: AsyncMock
    ) -> None:
        """Test database errors from gateway are properly propagated."""
        mock_welfare_gateway.create_application.return_value = Err(
            DatabaseError("Connection failed")
        )

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)
            result = await service.submit_welfare_application(
                guild_id=_snowflake(),
                applicant_id=_snowflake(),
                amount=100,
                reason="test",
            )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), DatabaseError)

    @pytest.mark.asyncio
    async def test_license_gateway_error_propagates(
        self,
        mock_pool: MagicMock,
        mock_license_gateway: AsyncMock,
        mock_business_license_gateway: AsyncMock,
    ) -> None:
        """Test database errors from license gateway are properly propagated."""
        mock_license_gateway.check_pending_application.return_value = Err(
            DatabaseError("Query failed")
        )

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(
                license_gateway=mock_license_gateway,
                business_license_gateway=mock_business_license_gateway,
            )
            result = await service.submit_license_application(
                guild_id=_snowflake(),
                applicant_id=_snowflake(),
                license_type="test",
                reason="test",
            )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), DatabaseError)
