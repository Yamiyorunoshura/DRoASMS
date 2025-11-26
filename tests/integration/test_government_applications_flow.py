"""Integration tests for Government Applications flow.

Tests the end-to-end flow of welfare and license applications:
- User submits application via personal panel
- Internal affairs reviews and approves/rejects
- Upon approval, welfare is disbursed or license is issued
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
from src.infra.result import Ok


def _snowflake() -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return secrets.randbits(63)


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
    return AsyncMock()


@pytest.fixture
def mock_license_gateway() -> AsyncMock:
    """Create a mock LicenseApplicationGateway."""
    return AsyncMock()


@pytest.fixture
def mock_business_license_gateway() -> AsyncMock:
    """Create a mock BusinessLicenseGateway."""
    return AsyncMock()


# ========== End-to-End Flow Tests ==========


@pytest.mark.integration
class TestWelfareApplicationFlow:
    """Test end-to-end welfare application workflow."""

    @pytest.mark.asyncio
    async def test_complete_welfare_approval_flow(
        self,
        mock_pool: MagicMock,
        mock_welfare_gateway: AsyncMock,
    ) -> None:
        """Test: User submits → Admin approves → Welfare disbursed."""
        guild_id = _snowflake()
        applicant_id = _snowflake()
        reviewer_id = _snowflake()
        app_id = 1

        # Step 1: User submits application
        pending_app = WelfareApplication(
            id=app_id,
            guild_id=guild_id,
            applicant_id=applicant_id,
            amount=5000,
            reason="生活困難，需要補助",
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        mock_welfare_gateway.create_application.return_value = Ok(pending_app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)

            submit_result = await service.submit_welfare_application(
                guild_id=guild_id,
                applicant_id=applicant_id,
                amount=5000,
                reason="生活困難，需要補助",
            )

        assert submit_result.is_ok()
        submitted = submit_result.unwrap()
        assert submitted.status == "pending"
        assert submitted.amount == 5000

        # Step 2: Admin retrieves and approves application
        approved_app = WelfareApplication(
            id=app_id,
            guild_id=guild_id,
            applicant_id=applicant_id,
            amount=5000,
            reason="生活困難，需要補助",
            status="approved",
            created_at=datetime.now(timezone.utc),
            reviewer_id=reviewer_id,
            reviewed_at=datetime.now(timezone.utc),
        )
        mock_welfare_gateway.get_application.return_value = Ok(pending_app)
        mock_welfare_gateway.approve_application.return_value = Ok(approved_app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            approve_result = await service.approve_welfare_application(
                application_id=app_id,
                reviewer_id=reviewer_id,
                transfer_callback=AsyncMock(),
            )

        assert approve_result.is_ok()
        approved = approve_result.unwrap()
        assert approved.status == "approved"
        assert approved.reviewer_id == reviewer_id

    @pytest.mark.asyncio
    async def test_complete_welfare_rejection_flow(
        self,
        mock_pool: MagicMock,
        mock_welfare_gateway: AsyncMock,
    ) -> None:
        """Test: User submits → Admin rejects with reason."""
        guild_id = _snowflake()
        applicant_id = _snowflake()
        reviewer_id = _snowflake()
        app_id = 2

        # Submit application
        pending_app = WelfareApplication(
            id=app_id,
            guild_id=guild_id,
            applicant_id=applicant_id,
            amount=100000,
            reason="想要很多錢",
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        mock_welfare_gateway.create_application.return_value = Ok(pending_app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)
            await service.submit_welfare_application(
                guild_id=guild_id,
                applicant_id=applicant_id,
                amount=100000,
                reason="想要很多錢",
            )

        # Admin rejects
        rejected_app = WelfareApplication(
            id=app_id,
            guild_id=guild_id,
            applicant_id=applicant_id,
            amount=100000,
            reason="想要很多錢",
            status="rejected",
            created_at=datetime.now(timezone.utc),
            reviewer_id=reviewer_id,
            reviewed_at=datetime.now(timezone.utc),
            rejection_reason="申請金額過高，不符合福利標準",
        )
        mock_welfare_gateway.reject_application.return_value = Ok(rejected_app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            reject_result = await service.reject_welfare_application(
                application_id=app_id,
                reviewer_id=reviewer_id,
                rejection_reason="申請金額過高，不符合福利標準",
            )

        assert reject_result.is_ok()
        rejected = reject_result.unwrap()
        assert rejected.status == "rejected"
        assert rejected.rejection_reason == "申請金額過高，不符合福利標準"


@pytest.mark.integration
class TestLicenseApplicationFlow:
    """Test end-to-end license application workflow."""

    @pytest.mark.asyncio
    async def test_complete_license_approval_flow(
        self,
        mock_pool: MagicMock,
        mock_license_gateway: AsyncMock,
        mock_business_license_gateway: AsyncMock,
    ) -> None:
        """Test: User submits → Admin approves → License issued."""
        guild_id = _snowflake()
        applicant_id = _snowflake()
        reviewer_id = _snowflake()
        app_id = 1

        # Step 1: User submits application
        pending_app = LicenseApplication(
            id=app_id,
            guild_id=guild_id,
            applicant_id=applicant_id,
            license_type="餐飲業",
            reason="開設餐廳",
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        mock_license_gateway.check_pending_application.return_value = Ok(False)
        mock_business_license_gateway.check_active_license.return_value = Ok(False)
        mock_license_gateway.create_application.return_value = Ok(pending_app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(
                license_gateway=mock_license_gateway,
                business_license_gateway=mock_business_license_gateway,
            )

            submit_result = await service.submit_license_application(
                guild_id=guild_id,
                applicant_id=applicant_id,
                license_type="餐飲業",
                reason="開設餐廳",
            )

        assert submit_result.is_ok()
        submitted = submit_result.unwrap()
        assert submitted.license_type == "餐飲業"
        assert submitted.status == "pending"

        # Step 2: Admin approves and license is issued
        approved_app = LicenseApplication(
            id=app_id,
            guild_id=guild_id,
            applicant_id=applicant_id,
            license_type="餐飲業",
            reason="開設餐廳",
            status="approved",
            created_at=datetime.now(timezone.utc),
            reviewer_id=reviewer_id,
            reviewed_at=datetime.now(timezone.utc),
        )
        mock_license_gateway.get_application.return_value = Ok(pending_app)
        mock_business_license_gateway.check_active_license.return_value = Ok(False)
        mock_business_license_gateway.issue_license.return_value = Ok(MagicMock())
        mock_license_gateway.approve_application.return_value = Ok(approved_app)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            approve_result = await service.approve_license_application(
                application_id=app_id,
                reviewer_id=reviewer_id,
            )

        assert approve_result.is_ok()
        approved = approve_result.unwrap()
        assert approved.status == "approved"
        # Verify license was issued
        mock_business_license_gateway.issue_license.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_pending_application_blocked(
        self,
        mock_pool: MagicMock,
        mock_license_gateway: AsyncMock,
        mock_business_license_gateway: AsyncMock,
    ) -> None:
        """Test: User cannot submit duplicate pending application."""
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
    async def test_already_has_license_blocked(
        self,
        mock_pool: MagicMock,
        mock_license_gateway: AsyncMock,
        mock_business_license_gateway: AsyncMock,
    ) -> None:
        """Test: User cannot apply for license they already have."""
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


@pytest.mark.integration
class TestApplicationHistoryRetrieval:
    """Test application history retrieval for personal panel."""

    @pytest.mark.asyncio
    async def test_get_user_applications_combined(
        self,
        mock_pool: MagicMock,
        mock_welfare_gateway: AsyncMock,
        mock_license_gateway: AsyncMock,
    ) -> None:
        """Test retrieving both welfare and license applications for a user."""
        guild_id = _snowflake()
        user_id = _snowflake()

        welfare_apps = [
            WelfareApplication(
                id=1,
                guild_id=guild_id,
                applicant_id=user_id,
                amount=1000,
                reason="福利申請1",
                status="approved",
                created_at=datetime.now(timezone.utc),
            ),
            WelfareApplication(
                id=2,
                guild_id=guild_id,
                applicant_id=user_id,
                amount=2000,
                reason="福利申請2",
                status="pending",
                created_at=datetime.now(timezone.utc),
            ),
        ]
        license_apps = [
            LicenseApplication(
                id=1,
                guild_id=guild_id,
                applicant_id=user_id,
                license_type="餐飲業",
                reason="開店",
                status="approved",
                created_at=datetime.now(timezone.utc),
            ),
        ]

        mock_welfare_gateway.get_user_applications.return_value = Ok(welfare_apps)
        mock_license_gateway.get_user_applications.return_value = Ok(license_apps)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(
                welfare_gateway=mock_welfare_gateway,
                license_gateway=mock_license_gateway,
            )

            welfare_result = await service.get_user_welfare_applications(
                guild_id=guild_id,
                applicant_id=user_id,
            )
            license_result = await service.get_user_license_applications(
                guild_id=guild_id,
                applicant_id=user_id,
            )

        assert welfare_result.is_ok()
        assert license_result.is_ok()
        assert len(list(welfare_result.unwrap())) == 2
        assert len(list(license_result.unwrap())) == 1


@pytest.mark.integration
class TestConcurrentApplicationHandling:
    """Test edge cases with concurrent application handling."""

    @pytest.mark.asyncio
    async def test_approve_already_approved_application(
        self,
        mock_pool: MagicMock,
        mock_welfare_gateway: AsyncMock,
    ) -> None:
        """Test that approving an already approved application fails gracefully."""
        already_approved = WelfareApplication(
            id=1,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            amount=1000,
            reason="test",
            status="approved",
            created_at=datetime.now(timezone.utc),
        )
        mock_welfare_gateway.get_application.return_value = Ok(already_approved)

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
    async def test_reject_already_rejected_application(
        self,
        mock_pool: MagicMock,
        mock_license_gateway: AsyncMock,
    ) -> None:
        """Test that rejecting an already rejected application fails gracefully."""
        already_rejected = LicenseApplication(
            id=1,
            guild_id=_snowflake(),
            applicant_id=_snowflake(),
            license_type="餐飲業",
            reason="test",
            status="rejected",
            created_at=datetime.now(timezone.utc),
        )
        mock_license_gateway.get_application.return_value = Ok(already_rejected)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(license_gateway=mock_license_gateway)

            result = await service.approve_license_application(
                application_id=1,
                reviewer_id=_snowflake(),
            )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), ApplicationNotPendingError)

    @pytest.mark.asyncio
    async def test_approve_nonexistent_application(
        self,
        mock_pool: MagicMock,
        mock_welfare_gateway: AsyncMock,
    ) -> None:
        """Test that approving a non-existent application returns proper error."""
        mock_welfare_gateway.get_application.return_value = Ok(None)

        with patch("src.bot.services.application_service.get_pool", return_value=mock_pool):
            service = ApplicationService(welfare_gateway=mock_welfare_gateway)

            result = await service.approve_welfare_application(
                application_id=99999,
                reviewer_id=_snowflake(),
                transfer_callback=AsyncMock(),
            )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), ApplicationNotFoundError)
