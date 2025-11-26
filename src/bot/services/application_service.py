"""Government Application Service.

Handles welfare and business license application workflows.
"""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportReturnType=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnnecessaryComparison=false
# Note: Type suppressions are needed due to:
# 1. asyncpg pool.acquire() returns partially typed connection
# 2. @async_returns_result decorator returns Result[T, Error] but Pyright
#    incorrectly infers Result[Result[T, Error], Error] when T is already a Result

from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Sequence

import structlog

from src.cython_ext.state_council_models import (
    LicenseApplication,
    LicenseApplicationListResult,
    WelfareApplication,
    WelfareApplicationListResult,
)
from src.db.gateway.business_license import BusinessLicenseGateway
from src.db.gateway.government_applications import (
    LicenseApplicationGateway,
    WelfareApplicationGateway,
)
from src.db.pool import get_pool
from src.infra.result import BusinessLogicError, Err, Error, Ok, Result, ValidationError

LOGGER = structlog.get_logger(__name__)


# Application-specific errors
class ApplicationNotFoundError(BusinessLogicError):
    """申請不存在。"""

    def __init__(self, application_id: int) -> None:
        super().__init__(
            f"Application {application_id} not found",
            context={"application_id": application_id, "error_type": "application_not_found"},
        )


class ApplicationNotPendingError(BusinessLogicError):
    """申請非待審批狀態。"""

    def __init__(self, application_id: int, status: str) -> None:
        super().__init__(
            f"Application {application_id} is not pending (current: {status})",
            context={
                "application_id": application_id,
                "status": status,
                "error_type": "application_not_pending",
            },
        )


class DuplicatePendingApplicationError(BusinessLogicError):
    """已有相同類型的待審批申請。"""

    def __init__(self, license_type: str) -> None:
        super().__init__(
            f"Already has a pending application for license type: {license_type}",
            context={"license_type": license_type, "error_type": "duplicate_pending_application"},
        )


class AlreadyHasActiveLicenseError(BusinessLogicError):
    """已持有相同類型的有效許可。"""

    def __init__(self, license_type: str) -> None:
        super().__init__(
            f"Already has an active license of type: {license_type}",
            context={"license_type": license_type, "error_type": "already_has_license"},
        )


class StateCouncilNotConfiguredError(BusinessLogicError):
    """國務院尚未設定。"""

    def __init__(self) -> None:
        super().__init__(
            "State council not configured for this guild",
            context={"error_type": "state_council_not_configured"},
        )


class InsufficientBalanceError(BusinessLogicError):
    """內政部餘額不足。"""

    def __init__(self, required: int, available: int) -> None:
        super().__init__(
            f"Insufficient balance: required {required}, available {available}",
            context={
                "required": required,
                "available": available,
                "error_type": "insufficient_balance",
            },
        )


@dataclass(frozen=True, slots=True)
class ApplicationSubmitResult:
    """申請提交結果。"""

    success: bool
    application_id: int | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ApplicationReviewResult:
    """申請審批結果。"""

    success: bool
    action: str  # 'approved' or 'rejected'
    application_id: int
    error_message: str | None = None


class ApplicationService:
    """政府服務申請處理服務。"""

    DEFAULT_LICENSE_DURATION_DAYS = 365

    def __init__(
        self,
        *,
        welfare_gateway: WelfareApplicationGateway | None = None,
        license_gateway: LicenseApplicationGateway | None = None,
        business_license_gateway: BusinessLicenseGateway | None = None,
    ) -> None:
        self._welfare_gateway = welfare_gateway or WelfareApplicationGateway()
        self._license_gateway = license_gateway or LicenseApplicationGateway()
        self._business_license_gateway = business_license_gateway or BusinessLicenseGateway()

    # ========== Welfare Application Methods ==========

    async def submit_welfare_application(
        self,
        *,
        guild_id: int,
        applicant_id: int,
        amount: int,
        reason: str,
    ) -> Result[WelfareApplication, Error]:
        """提交福利申請。

        Args:
            guild_id: Discord 伺服器 ID
            applicant_id: 申請人 ID
            amount: 申請金額
            reason: 申請原因

        Returns:
            Result[WelfareApplication, Error]: 成功返回申請記錄
        """
        # Validate amount
        if amount <= 0:
            return Err(
                ValidationError(
                    "Amount must be positive",
                    context={"amount": amount, "error_type": "invalid_amount"},
                )
            )

        if not reason.strip():
            return Err(
                ValidationError(
                    "Reason is required",
                    context={"error_type": "missing_reason"},
                )
            )

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await self._welfare_gateway.create_application(
                conn,
                guild_id=guild_id,
                applicant_id=applicant_id,
                amount=amount,
                reason=reason.strip(),
            )

        if result.is_err():
            LOGGER.error(
                "application.welfare.submit_failed",
                guild_id=guild_id,
                applicant_id=applicant_id,
                error=str(result.unwrap_err()),
            )
            return result

        application = result.unwrap()
        LOGGER.info(
            "application.welfare.submitted",
            guild_id=guild_id,
            applicant_id=applicant_id,
            application_id=application.id,
            amount=amount,
        )
        return Ok(application)

    async def get_welfare_application(
        self,
        *,
        application_id: int,
    ) -> Result[WelfareApplication | None, Error]:
        """取得福利申請詳情。"""
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._welfare_gateway.get_application(conn, application_id=application_id)

    async def list_welfare_applications(
        self,
        *,
        guild_id: int,
        status: str | None = None,
        applicant_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Result[WelfareApplicationListResult, Error]:
        """列出福利申請。"""
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._welfare_gateway.list_applications(
                conn,
                guild_id=guild_id,
                status=status,  # type: ignore[arg-type]
                applicant_id=applicant_id,
                page=page,
                page_size=page_size,
            )

    async def get_user_welfare_applications(
        self,
        *,
        guild_id: int,
        applicant_id: int,
        limit: int = 20,
    ) -> Result[Sequence[WelfareApplication], Error]:
        """取得用戶的福利申請記錄。"""
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._welfare_gateway.get_user_applications(
                conn,
                guild_id=guild_id,
                applicant_id=applicant_id,
                limit=limit,
            )

    async def approve_welfare_application(
        self,
        *,
        application_id: int,
        reviewer_id: int,
        transfer_callback: Callable[..., Any] | None,
    ) -> Result[WelfareApplication, Error]:
        """批准福利申請並（可選）立即執行福利發放。

        Args:
            application_id: 申請 ID
            reviewer_id: 審批人 ID
            transfer_callback: 可選的撥款回調；接受彈性參數集（application、guild_id、
                applicant_id、amount、reason 等），返回 truthy/Result/tuple[bool, str]

        行為：
            - 以交易包覆：狀態更新與撥款成功才提交；撥款失敗則回滾並回傳 Err。
        """
        pool = get_pool()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # 讀取申請
                    app_result = await self._welfare_gateway.get_application(
                        conn, application_id=application_id
                    )
                    if app_result.is_err():
                        return Err(app_result.unwrap_err())

                    application = app_result.unwrap()
                    if application is None:
                        return Err(ApplicationNotFoundError(application_id))

                    if application.status != "pending":
                        return Err(ApplicationNotPendingError(application_id, application.status))

                    # 更新狀態為核准
                    result = await self._welfare_gateway.approve_application(
                        conn,
                        application_id=application_id,
                        reviewer_id=reviewer_id,
                    )
                    if result.is_err():
                        return result

                    approved = result.unwrap()

                    # 若提供撥款回調，立即執行福利發放；失敗則回滾整筆交易。
                    if transfer_callback is not None:
                        try:
                            try:
                                sig = inspect.signature(transfer_callback)
                                param_names = set(sig.parameters.keys())
                                accepts_var_kwargs = any(
                                    p.kind == inspect.Parameter.VAR_KEYWORD
                                    for p in sig.parameters.values()
                                )
                            except Exception:
                                param_names = set()
                                accepts_var_kwargs = (
                                    True  # 寧可多給參數以避免 None 造成的 int() 失敗
                                )

                            payload: dict[str, Any] = {}
                            # 若回調接受 **kwargs，直接提供完整上下文；否則依照實際參數命名填入
                            if accepts_var_kwargs or "application" in param_names:
                                payload["application"] = approved
                            if accepts_var_kwargs or "guild_id" in param_names:
                                payload["guild_id"] = approved.guild_id
                            if accepts_var_kwargs or "applicant_id" in param_names:
                                payload["applicant_id"] = approved.applicant_id
                            if accepts_var_kwargs or "amount" in param_names:
                                payload["amount"] = approved.amount
                            if accepts_var_kwargs or "reason" in param_names:
                                payload["reason"] = approved.reason

                            transfer_result = await transfer_callback(**payload)

                            # 解讀回傳結果（支援 Result / (bool, msg) / truthy 判斷）
                            if isinstance(transfer_result, Err):
                                raise BusinessLogicError(
                                    str(transfer_result.unwrap_err()),
                                    context={"error_type": "welfare_disburse_failed"},
                                )
                            elif isinstance(transfer_result, Ok):
                                pass
                            elif isinstance(transfer_result, tuple):
                                success = bool(transfer_result[0])
                                message = transfer_result[1] if len(transfer_result) > 1 else ""
                                if not success:
                                    raise BusinessLogicError(
                                        message or "Welfare disbursement failed",
                                        context={"error_type": "welfare_disburse_failed"},
                                    )
                            elif transfer_result is False:
                                raise BusinessLogicError(
                                    "Welfare disbursement failed",
                                    context={"error_type": "welfare_disburse_failed"},
                                )
                            # 其他 truthy / None 視為成功，保持相容
                        except BusinessLogicError:
                            # 直接向外拋出以觸發交易回滾
                            raise
                        except Exception as exc:  # pragma: no cover - 防禦性包裝
                            raise BusinessLogicError(
                                f"Welfare disbursement failed: {exc}",
                                context={"error_type": "welfare_disburse_failed"},
                            ) from exc

                    LOGGER.info(
                        "application.welfare.approved",
                        application_id=application_id,
                        reviewer_id=reviewer_id,
                        amount=approved.amount,
                    )
                    return Ok(approved)
        # 交易區塊外捕捉：確保失敗時回傳 Err，並已回滾狀態變更
        except BusinessLogicError as exc:
            return Err(exc)

    async def reject_welfare_application(
        self,
        *,
        application_id: int,
        reviewer_id: int,
        rejection_reason: str,
    ) -> Result[WelfareApplication, Error]:
        """拒絕福利申請。"""
        if not rejection_reason.strip():
            return Err(
                ValidationError(
                    "Rejection reason is required",
                    context={"error_type": "missing_rejection_reason"},
                )
            )

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await self._welfare_gateway.reject_application(
                conn,
                application_id=application_id,
                reviewer_id=reviewer_id,
                rejection_reason=rejection_reason.strip(),
            )

        if result.is_err():
            return result

        rejected = result.unwrap()
        LOGGER.info(
            "application.welfare.rejected",
            application_id=application_id,
            reviewer_id=reviewer_id,
            reason=rejection_reason,
        )
        return Ok(rejected)

    # ========== License Application Methods ==========

    async def submit_license_application(
        self,
        *,
        guild_id: int,
        applicant_id: int,
        license_type: str,
        reason: str,
    ) -> Result[LicenseApplication, Error]:
        """提交商業許可申請。

        Args:
            guild_id: Discord 伺服器 ID
            applicant_id: 申請人 ID
            license_type: 許可類型
            reason: 申請原因

        Returns:
            Result[LicenseApplication, Error]: 成功返回申請記錄
        """
        if not license_type.strip():
            return Err(
                ValidationError(
                    "License type is required",
                    context={"error_type": "missing_license_type"},
                )
            )

        if not reason.strip():
            return Err(
                ValidationError(
                    "Reason is required",
                    context={"error_type": "missing_reason"},
                )
            )

        pool = get_pool()
        async with pool.acquire() as conn:
            # Check for duplicate pending application
            has_pending_result = await self._license_gateway.check_pending_application(
                conn,
                guild_id=guild_id,
                applicant_id=applicant_id,
                license_type=license_type.strip(),
            )
            if has_pending_result.is_err():
                return Err(has_pending_result.unwrap_err())

            if has_pending_result.unwrap():
                return Err(DuplicatePendingApplicationError(license_type))

            # Check for active license
            has_active_result = await self._business_license_gateway.check_active_license(
                conn,
                guild_id=guild_id,
                user_id=applicant_id,
                license_type=license_type.strip(),
            )
            if has_active_result.is_err():
                return Err(has_active_result.unwrap_err())

            if has_active_result.unwrap():
                return Err(AlreadyHasActiveLicenseError(license_type))

            # Create application
            result = await self._license_gateway.create_application(
                conn,
                guild_id=guild_id,
                applicant_id=applicant_id,
                license_type=license_type.strip(),
                reason=reason.strip(),
            )

        if result.is_err():
            LOGGER.error(
                "application.license.submit_failed",
                guild_id=guild_id,
                applicant_id=applicant_id,
                error=str(result.unwrap_err()),
            )
            return result

        application = result.unwrap()
        LOGGER.info(
            "application.license.submitted",
            guild_id=guild_id,
            applicant_id=applicant_id,
            application_id=application.id,
            license_type=license_type,
        )
        return Ok(application)

    async def get_license_application(
        self,
        *,
        application_id: int,
    ) -> Result[LicenseApplication | None, Error]:
        """取得商業許可申請詳情。"""
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._license_gateway.get_application(conn, application_id=application_id)

    async def list_license_applications(
        self,
        *,
        guild_id: int,
        status: str | None = None,
        applicant_id: int | None = None,
        license_type: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Result[LicenseApplicationListResult, Error]:
        """列出商業許可申請。"""
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._license_gateway.list_applications(
                conn,
                guild_id=guild_id,
                status=status,  # type: ignore[arg-type]
                applicant_id=applicant_id,
                license_type=license_type,
                page=page,
                page_size=page_size,
            )

    async def get_user_license_applications(
        self,
        *,
        guild_id: int,
        applicant_id: int,
        limit: int = 20,
    ) -> Result[Sequence[LicenseApplication], Error]:
        """取得用戶的商業許可申請記錄。"""
        pool = get_pool()
        async with pool.acquire() as conn:
            return await self._license_gateway.get_user_applications(
                conn,
                guild_id=guild_id,
                applicant_id=applicant_id,
                limit=limit,
            )

    async def approve_license_application(
        self,
        *,
        application_id: int,
        reviewer_id: int,
        license_duration_days: int | None = None,
    ) -> Result[LicenseApplication, Error]:
        """批准商業許可申請。

        Args:
            application_id: 申請 ID
            reviewer_id: 審批人 ID
            license_duration_days: 許可有效期（天）

        Returns:
            Result[LicenseApplication, Error]: 成功返回更新後的申請
        """
        duration = license_duration_days or self.DEFAULT_LICENSE_DURATION_DAYS

        pool = get_pool()
        async with pool.acquire() as conn:
            # Get application
            app_result = await self._license_gateway.get_application(
                conn, application_id=application_id
            )
            if app_result.is_err():
                return Err(app_result.unwrap_err())

            application = app_result.unwrap()
            if application is None:
                return Err(ApplicationNotFoundError(application_id))

            if application.status != "pending":
                return Err(ApplicationNotPendingError(application_id, application.status))

            # Check if user already has active license (race condition check)
            has_active_result = await self._business_license_gateway.check_active_license(
                conn,
                guild_id=application.guild_id,
                user_id=application.applicant_id,
                license_type=application.license_type,
            )
            if has_active_result.is_err():
                return Err(has_active_result.unwrap_err())

            if has_active_result.unwrap():
                return Err(AlreadyHasActiveLicenseError(application.license_type))

            # Issue license
            expires_at = datetime.now(timezone.utc) + timedelta(days=duration)
            issue_result = await self._business_license_gateway.issue_license(
                conn,
                guild_id=application.guild_id,
                user_id=application.applicant_id,
                license_type=application.license_type,
                issued_by=reviewer_id,
                expires_at=expires_at,
            )
            if issue_result.is_err():
                LOGGER.error(
                    "application.license.issue_failed",
                    application_id=application_id,
                    error=str(issue_result.unwrap_err()),
                )
                return Err(issue_result.unwrap_err())

            # Approve the application
            result = await self._license_gateway.approve_application(
                conn,
                application_id=application_id,
                reviewer_id=reviewer_id,
            )

        if result.is_err():
            return result

        approved = result.unwrap()
        LOGGER.info(
            "application.license.approved",
            application_id=application_id,
            reviewer_id=reviewer_id,
            license_type=approved.license_type,
        )
        return Ok(approved)

    async def reject_license_application(
        self,
        *,
        application_id: int,
        reviewer_id: int,
        rejection_reason: str,
    ) -> Result[LicenseApplication, Error]:
        """拒絕商業許可申請。"""
        if not rejection_reason.strip():
            return Err(
                ValidationError(
                    "Rejection reason is required",
                    context={"error_type": "missing_rejection_reason"},
                )
            )

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await self._license_gateway.reject_application(
                conn,
                application_id=application_id,
                reviewer_id=reviewer_id,
                rejection_reason=rejection_reason.strip(),
            )

        if result.is_err():
            return result

        rejected = result.unwrap()
        LOGGER.info(
            "application.license.rejected",
            application_id=application_id,
            reviewer_id=reviewer_id,
            reason=rejection_reason,
        )
        return Ok(rejected)


__all__ = [
    "ApplicationService",
    "ApplicationNotFoundError",
    "ApplicationNotPendingError",
    "DuplicatePendingApplicationError",
    "AlreadyHasActiveLicenseError",
    "StateCouncilNotConfiguredError",
    "InsufficientBalanceError",
    "ApplicationSubmitResult",
    "ApplicationReviewResult",
]
