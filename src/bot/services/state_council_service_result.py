"""Result-based StateCouncilService implementation."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Sequence, cast

import structlog

from src.bot.services.adjustment_service import AdjustmentService
from src.bot.services.department_registry import DepartmentRegistry
from src.bot.services.state_council_errors import (
    AccountNotFoundError,
    BusinessLicenseNotFoundError,
    DepartmentNotFoundError,
    DuplicateLicenseError,
    IdentityNotFoundError,
    InsufficientFundsError,
    InvalidLicenseStatusError,
    InvalidTransferError,
    MonthlyIssuanceLimitExceededError,
    StateCouncilError,
    StateCouncilNotConfiguredError,
    StateCouncilPermissionDeniedError,
    StateCouncilValidationError,
)
from src.bot.services.transfer_service import TransferService
from src.cython_ext.state_council_models import (
    BusinessLicense,
    BusinessLicenseListResult,
    DepartmentStats,
    StateCouncilSummary,
    SuspectProfile,
    SuspectReleaseResult,
)
from src.db.gateway.business_license import BusinessLicenseGateway
from src.db.gateway.economy_queries import EconomyQueryGateway
from src.db.gateway.state_council_governance import (
    CurrencyIssuance,
    DepartmentConfig,
    DepartmentRoleConfig,
    GovernmentAccount,
    IdentityRecord,
    InterdepartmentTransfer,
    StateCouncilConfig,
    StateCouncilGovernanceGateway,
    TaxRecord,
    WelfareDisbursement,
)
from src.db.pool import get_pool
from src.infra.result import (
    DatabaseError,
    Err,
    Error,
    Ok,
    Result,
    async_returns_result,
)
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)


class _AcquireConnectionContext:
    """Async context manager wrapper for pool.acquire() results."""

    def __init__(self, pool_obj: Any, acq_obj: Any) -> None:
        self._pool = pool_obj
        self._acq = acq_obj
        self._conn: Any | None = None

    async def __aenter__(self) -> Any:
        aenter = getattr(self._acq, "__aenter__", None)
        if aenter is not None:
            try:
                LOGGER.debug(
                    "acquire_cm_aenter",
                    aenter_type=type(aenter).__name__,
                    has_rv=hasattr(aenter, "return_value"),
                )
            except Exception:
                pass
            rv = getattr(aenter, "return_value", None)
            if rv is not None:
                try:
                    LOGGER.debug(
                        "acquire_cm_aenter_rv",
                        rv_type=type(rv).__name__,
                    )
                except Exception:
                    pass
                self._conn = rv
                return rv
            self._conn = await aenter()
            return self._conn
        conn = self._acq
        if inspect.isawaitable(conn):
            conn = await conn
        self._conn = conn
        return conn

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        aexit = getattr(self._acq, "__aexit__", None)
        if aexit is not None:
            await aexit(exc_type, exc, tb)
            return None
        if self._conn is not None:
            release = getattr(self._pool, "release", None)
            if release is not None:
                try:
                    if inspect.iscoroutinefunction(release):
                        await release(self._conn)
                    else:
                        release(self._conn)
                except Exception:
                    LOGGER.debug("acquire_cm_release_failed", exc_info=True)
        return None


class StateCouncilServiceResult:
    """Coordinates state council governance operations using Result pattern."""

    def __init__(
        self,
        *,
        gateway: StateCouncilGovernanceGateway | None = None,
        transfer_service: TransferService | None = None,
        adjustment_service: AdjustmentService | None = None,
        department_registry: DepartmentRegistry | None = None,
        business_license_gateway: BusinessLicenseGateway | None = None,
    ) -> None:
        # 注意：不要在建構子中即刻觸發資料庫事件圈（event loop）相依物件建立，
        # 以便單元測試能在無 event loop 的情況下建構 service。
        self._gateway = gateway or StateCouncilGovernanceGateway()
        # TransferService 可於建構時立即建立（若未注入），
        # 測試會以 patch(get_pool) 提供替身，因此不會觸發真實 event loop。
        # _transfer 在建構時即建立，避免 Optional 帶來的型態歧義
        self._transfer: TransferService = transfer_service or TransferService(get_pool())
        self._adjust: AdjustmentService | None = adjustment_service
        # 以經濟系統為唯一真實來源查詢餘額
        self._economy = EconomyQueryGateway()
        # 政府註冊表
        self._department_registry = department_registry or DepartmentRegistry()
        # 商業許可 Gateway
        self._license_gateway = business_license_gateway or BusinessLicenseGateway()

    def _get_auto_release_jobs(self, guild_id: int) -> dict[int, Any]:
        """Fetch in-memory auto-release metadata without importing at module load."""

        try:
            from src.bot.services.state_council_scheduler import (
                get_auto_release_jobs_for_guild,
            )

            return get_auto_release_jobs_for_guild(guild_id)
        except Exception:
            return {}

    def _cancel_auto_release_job(self, guild_id: int, suspect_id: int) -> None:
        try:
            from src.bot.services.state_council_scheduler import cancel_auto_release

            cancel_auto_release(guild_id, suspect_id)
        except Exception:
            LOGGER.warning(
                "state_council.auto_release.cancel_failed",
                guild_id=guild_id,
                suspect_id=suspect_id,
            )

    def _schedule_auto_release_job(
        self, guild_id: int, suspect_id: int, hours: int, scheduled_by: int
    ) -> Any | None:
        try:
            from src.bot.services.state_council_scheduler import set_auto_release

            return set_auto_release(guild_id, suspect_id, hours, scheduled_by=scheduled_by)
        except Exception:
            LOGGER.warning(
                "state_council.auto_release.schedule_failed",
                guild_id=guild_id,
                suspect_id=suspect_id,
                hours=hours,
            )
            return None

    def _ensure_transfer(self) -> TransferService:
        """取得 TransferService（非 Optional）。"""
        return self._transfer

    def _ensure_adjust(self) -> AdjustmentService:
        """取得 AdjustmentService，必要時以目前事件圈的連線池延遲建立。"""
        if self._adjust is None:
            self._adjust = AdjustmentService(get_pool())
        return self._adjust

    # --- Internal safe wrappers / adapters ---
    async def _safe_fetch_accounts(
        self, conn: Any, *, guild_id: int
    ) -> Result[Sequence[GovernmentAccount], StateCouncilError]:
        """Fetch government accounts with error handling."""
        try:
            accounts = await self._gateway.fetch_government_accounts(conn, guild_id=guild_id)
            return Ok(accounts)
        except Exception as exc:
            return Err(StateCouncilError(f"Failed to fetch accounts: {exc}"))

    def _acquire_connection(self) -> _AcquireConnectionContext:
        """Acquire a database connection with proper error handling."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        acq = pool.acquire()
        return _AcquireConnectionContext(pool, acq)

    # --- Configuration ---
    @staticmethod
    def derive_department_account_id(guild_id: int, dept_name: str) -> int:
        """Derive a deterministic account ID for a department."""
        # Use a large offset to avoid collisions with user IDs
        base = 8_000_000_000_000_000
        # Hash department name to get a stable integer
        dept_hash = hash(dept_name) % 1_000_000
        return base + int(guild_id) * 1_000_000 + dept_hash

    @async_returns_result(
        StateCouncilError,
        exception_map={
            RuntimeError: StateCouncilNotConfiguredError,
            Exception: DatabaseError,
        },
    )
    async def set_config(
        self,
        *,
        guild_id: int,
        leader_id: int | None = None,
        leader_role_id: int | None = None,
        internal_affairs_account_id: int,
        treasury_account_id: int,
        welfare_account_id: int,
    ) -> Result[StateCouncilConfig, StateCouncilError]:
        """Set state council configuration."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            config = await self._gateway.upsert_state_council_config(
                c,
                guild_id=guild_id,
                leader_id=leader_id,
                leader_role_id=leader_role_id,
                internal_affairs_account_id=internal_affairs_account_id,
                finance_account_id=internal_affairs_account_id,  # 暫時使用相同的值
                security_account_id=internal_affairs_account_id,  # 暫時使用相同的值
                central_bank_account_id=internal_affairs_account_id,  # 暫時使用相同的值
                treasury_account_id=treasury_account_id,
                welfare_account_id=welfare_account_id,
            )
            return Ok(config)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            RuntimeError: StateCouncilNotConfiguredError,
            Exception: DatabaseError,
        },
    )
    async def get_config(self, *, guild_id: int) -> Result[StateCouncilConfig, StateCouncilError]:
        """Get state council configuration."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            config = await self._gateway.fetch_state_council_config(c, guild_id=guild_id)
            if config is None:
                return Err(
                    StateCouncilNotConfiguredError(
                        "State council governance is not configured for this guild.",
                        context={"guild_id": guild_id},
                    )
                )
            return Ok(config)

    # --- Department Management ---
    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def list_departments(
        self, *, guild_id: int
    ) -> Result[Sequence[DepartmentConfig], StateCouncilError]:
        """List all departments for a guild."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            departments = await self._gateway.fetch_department_configs(c, guild_id=guild_id)
            return Ok(departments)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def get_department(
        self, *, guild_id: int, department_id: str
    ) -> Result[DepartmentConfig | None, StateCouncilError]:
        """Get a specific department by ID."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            department = await self._gateway.fetch_department_config(
                c, guild_id=guild_id, department=department_id
            )
            return Ok(department)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            StateCouncilValidationError: StateCouncilValidationError,
            Exception: DatabaseError,
        },
    )
    async def create_department(
        self,
        *,
        guild_id: int,
        department_id: str,
        name: str,
        description: str | None = None,
        emoji: str | None = None,
        budget_quota: int | None = None,
    ) -> Result[DepartmentConfig, StateCouncilError]:
        """Create a new department."""
        # Validation
        if not department_id or not department_id.strip():
            return Err(
                StateCouncilValidationError(
                    "Department ID cannot be empty.",
                    context={"department_id": department_id},
                )
            )
        if not name or not name.strip():
            return Err(
                StateCouncilValidationError(
                    "Department name cannot be empty.",
                    context={"name": name},
                )
            )
        if budget_quota is not None and budget_quota < 0:
            return Err(
                StateCouncilValidationError(
                    "Budget quota cannot be negative.",
                    context={"budget_quota": budget_quota},
                )
            )

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            department = await self._gateway.upsert_department_config(
                c,
                guild_id=guild_id,
                department=department_id,
                role_id=None,
                welfare_amount=budget_quota or 0,
                welfare_interval_hours=24,
                tax_rate_basis=100,
                tax_rate_percent=10,
                max_issuance_per_month=100000,
            )
            return Ok(department)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            DepartmentNotFoundError: DepartmentNotFoundError,
            Exception: DatabaseError,
        },
    )
    async def update_department(
        self,
        *,
        guild_id: int,
        department_id: str,
        name: str | None = None,
        description: str | None = None,
        emoji: str | None = None,
        budget_quota: int | None = None,
    ) -> Result[DepartmentConfig, StateCouncilError]:
        """Update department configuration."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            department = await self._gateway.update_department(
                c,
                guild_id=guild_id,
                department_id=department_id,
                name=name,
                description=description,
                emoji=emoji,
                budget_quota=budget_quota,
            )
            if department is None:
                return Err(
                    DepartmentNotFoundError(
                        f"Department {department_id} not found.",
                        context={"guild_id": guild_id, "department_id": department_id},
                    )
                )
            return Ok(department)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def delete_department(
        self, *, guild_id: int, department_id: str
    ) -> Result[bool, StateCouncilError]:
        """Delete a department."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            success = await self._gateway.delete_department(
                c, guild_id=guild_id, department_id=department_id
            )
            return Ok(success)

    # --- Department Role Management ---
    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def add_department_role(
        self, *, guild_id: int, department_id: str, role_id: int
    ) -> Result[bool, StateCouncilError]:
        """Add a role to a department."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            result = await self._gateway.add_department_role(
                c, guild_id=guild_id, department=department_id, role_id=role_id
            )
            return Ok(result)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def remove_department_role(
        self, *, guild_id: int, department_id: str, role_id: int
    ) -> Result[bool, StateCouncilError]:
        """Remove a role from a department."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            result = await self._gateway.remove_department_role(
                c, guild_id=guild_id, department=department_id, role_id=role_id
            )
            return Ok(result)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def list_department_roles(
        self, *, guild_id: int, department_id: str
    ) -> Result[Sequence[DepartmentRoleConfig], StateCouncilError]:
        """List all roles for a department."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            roles = await self._gateway.fetch_department_roles(
                c, guild_id=guild_id, department_id=department_id
            )
            return Ok(roles)

    # --- Account Management ---
    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def get_accounts(
        self, *, guild_id: int
    ) -> Result[Sequence[GovernmentAccount], StateCouncilError]:
        """Get all government accounts for a guild."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            accounts = await self._gateway.fetch_government_accounts(c, guild_id=guild_id)
            return Ok(accounts)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def get_account(
        self, *, guild_id: int, account_id: int
    ) -> Result[GovernmentAccount | None, StateCouncilError]:
        """Get a specific government account."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            account = await self._gateway.fetch_account(c, guild_id=guild_id, account_id=account_id)
            return Ok(account)

    # --- Identity Management ---
    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def register_identity(
        self,
        *,
        guild_id: int,
        member_id: int,
        true_name: str,
        id_number: str,
        department_id: str,
    ) -> Result[IdentityRecord, StateCouncilError]:
        """Register a member's identity."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            identity = await self._gateway.upsert_identity(
                c,
                guild_id=guild_id,
                member_id=member_id,
                true_name=true_name,
                id_number=id_number,
                department_id=department_id,
            )
            return Ok(identity)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            IdentityNotFoundError: IdentityNotFoundError,
            Exception: DatabaseError,
        },
    )
    async def get_identity(
        self, *, guild_id: int, member_id: int
    ) -> Result[IdentityRecord, StateCouncilError]:
        """Get a member's identity record."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            identity = await self._gateway.fetch_identity(c, guild_id=guild_id, member_id=member_id)
            if identity is None:
                return Err(
                    IdentityNotFoundError(
                        f"Identity not found for member {member_id}.",
                        context={"guild_id": guild_id, "member_id": member_id},
                    )
                )
            return Ok(identity)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def update_identity_department(
        self, *, guild_id: int, member_id: int, department_id: str
    ) -> Result[IdentityRecord, StateCouncilError]:
        """Update a member's department assignment."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            identity = await self._gateway.update_identity_department(
                c, guild_id=guild_id, member_id=member_id, department_id=department_id
            )
            if identity is None:
                return Err(
                    IdentityNotFoundError(
                        f"Identity not found for member {member_id}.",
                        context={"guild_id": guild_id, "member_id": member_id},
                    )
                )
            return Ok(identity)

    # --- Financial Operations ---
    @async_returns_result(
        StateCouncilError,
        exception_map={
            InsufficientFundsError: InsufficientFundsError,
            InvalidTransferError: InvalidTransferError,
            Exception: DatabaseError,
        },
    )
    async def transfer_between_accounts(
        self,
        *,
        guild_id: int,
        from_account_id: int,
        to_account_id: int,
        amount: int,
        reason: str,
        initiated_by: int,
    ) -> Result[InterdepartmentTransfer, StateCouncilError]:
        """Transfer funds between government accounts."""
        # Validation
        if amount <= 0:
            return Err(
                StateCouncilValidationError(
                    "Transfer amount must be positive.",
                    context={"amount": amount},
                )
            )
        if from_account_id == to_account_id:
            return Err(
                StateCouncilValidationError(
                    "Source and destination accounts must be different.",
                    context={"account_id": from_account_id},
                )
            )

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn

            # Check source account balance
            from_account = await self._gateway.fetch_account(
                c, guild_id=guild_id, account_id=from_account_id
            )
            if from_account is None:
                return Err(
                    AccountNotFoundError(
                        f"Source account {from_account_id} not found.",
                        context={"guild_id": guild_id, "account_id": from_account_id},
                    )
                )
            if from_account.balance < amount:
                return Err(
                    InsufficientFundsError(
                        f"Insufficient funds in account {from_account_id}. "
                        f"Required: {amount}, Available: {from_account.balance}",
                        context={
                            "account_id": from_account_id,
                            "required": amount,
                            "available": from_account.balance,
                        },
                    )
                )

            # Check destination account exists
            to_account = await self._gateway.fetch_account(
                c, guild_id=guild_id, account_id=to_account_id
            )
            if to_account is None:
                return Err(
                    AccountNotFoundError(
                        f"Destination account {to_account_id} not found.",
                        context={"guild_id": guild_id, "account_id": to_account_id},
                    )
                )

            # Perform the transfer
            transfer = await self._gateway.insert_interdepartment_transfer(
                c,
                guild_id=guild_id,
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                amount=amount,
                reason=reason,
                initiated_by=initiated_by,
            )
            return Ok(transfer)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            MonthlyIssuanceLimitExceededError: MonthlyIssuanceLimitExceededError,
            StateCouncilValidationError: StateCouncilValidationError,
            Exception: DatabaseError,
        },
    )
    async def issue_currency(
        self,
        *,
        guild_id: int,
        amount: int,
        reason: str,
        issued_by: int,
    ) -> Result[CurrencyIssuance, StateCouncilError]:
        """Issue new currency into the treasury account."""
        # Validation
        if amount <= 0:
            return Err(
                StateCouncilValidationError(
                    "Issuance amount must be positive.",
                    context={"amount": amount},
                )
            )

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn

            # Get config to find treasury account
            config_result = await self.get_config(guild_id=guild_id)
            if isinstance(config_result, Err):
                # 將設定錯誤轉換為當前服務的錯誤型別
                err_value = config_result.error
                if isinstance(err_value, StateCouncilError):
                    return Err(err_value)
                return Err(StateCouncilError(str(err_value)))
            # 在 Ok 路徑下，型別系統無法精確推斷內部值，這裡以 cast 協助推論
            config = cast(StateCouncilConfig, getattr(config_result, "value", None))

            # Check monthly issuance limit
            current_month_total = await self._gateway.get_monthly_issuance_total(
                c, guild_id=guild_id, year=datetime.now().year, month=datetime.now().month
            )
            monthly_limit = 1_000_000  # TODO: Make configurable
            if current_month_total + amount > monthly_limit:
                return Err(
                    MonthlyIssuanceLimitExceededError(
                        (
                            "Monthly issuance limit exceeded. "
                            f"Current: {current_month_total}, "
                            f"Requested: {amount}, "
                            f"Limit: {monthly_limit}"
                        ),
                        context={
                            "current_total": current_month_total,
                            "requested": amount,
                            "limit": monthly_limit,
                        },
                    )
                )

            # Create the issuance record
            issuance = await self._gateway.insert_currency_issuance(
                c,
                guild_id=guild_id,
                amount=amount,
                treasury_account_id=config.treasury_account_id or 0,
                reason=reason,
                issued_by=issued_by,
            )
            return Ok(issuance)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            InsufficientFundsError: InsufficientFundsError,
            Exception: DatabaseError,
        },
    )
    async def disburse_welfare(
        self,
        *,
        guild_id: int,
        recipient_id: int,
        amount: int,
        reason: str,
        disbursed_by: int,
    ) -> Result[WelfareDisbursement, StateCouncilError]:
        """Disburse welfare funds to a member."""
        # Validation
        if amount <= 0:
            return Err(
                StateCouncilValidationError(
                    "Welfare amount must be positive.",
                    context={"amount": amount},
                )
            )

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn

            # Get config to find welfare account
            config_result = await self.get_config(guild_id=guild_id)
            if isinstance(config_result, Err):
                err_value = config_result.error
                if isinstance(err_value, StateCouncilError):
                    return Err(err_value)
                return Err(StateCouncilError(str(err_value)))
            config = cast(StateCouncilConfig, getattr(config_result, "value", None))

            # Check welfare account balance
            if config.welfare_account_id is None:
                return Err(
                    AccountNotFoundError(
                        "Welfare account is not configured.",
                        context={"guild_id": guild_id},
                    )
                )
            welfare_account = await self._gateway.fetch_account(
                c, guild_id=guild_id, account_id=config.welfare_account_id
            )
            if welfare_account is None:
                return Err(
                    AccountNotFoundError(
                        f"Welfare account {config.welfare_account_id or 0} not found.",
                        context={"guild_id": guild_id, "account_id": config.welfare_account_id},
                    )
                )
            if welfare_account.balance < amount:
                return Err(
                    InsufficientFundsError(
                        f"Insufficient funds in welfare account. "
                        f"Required: {amount}, Available: {welfare_account.balance}",
                        context={
                            "account_id": config.welfare_account_id or 0,
                            "required": amount,
                            "available": welfare_account.balance,
                        },
                    )
                )

            # Create the disbursement record
            disbursement = await self._gateway.insert_welfare_disbursement(
                c,
                guild_id=guild_id,
                recipient_id=recipient_id,
                amount=amount,
                welfare_account_id=config.welfare_account_id or 0,
                reason=reason,
                disbursed_by=disbursed_by,
            )
            return Ok(disbursement)

    # --- Tax Collection ---
    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def record_tax_payment(
        self,
        *,
        guild_id: int,
        taxpayer_id: int,
        amount: int,
        tax_type: str,
        tax_period: str,
    ) -> Result[TaxRecord, StateCouncilError]:
        """Record a tax payment."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn

            # Get config to find treasury account
            config_result = await self.get_config(guild_id=guild_id)
            if isinstance(config_result, Err):
                err_value = config_result.error
                if isinstance(err_value, StateCouncilError):
                    return Err(err_value)
                return Err(StateCouncilError(str(err_value)))
            config = cast(StateCouncilConfig, getattr(config_result, "value", None))

            # Record the tax payment
            tax_record = await self._gateway.insert_tax_record(
                c,
                guild_id=guild_id,
                taxpayer_id=taxpayer_id,
                amount=amount,
                tax_type=tax_type,
                tax_period=tax_period,
                treasury_account_id=config.treasury_account_id or 0,
            )
            return Ok(tax_record)

    # --- Justice System Integration ---
    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def detain_suspect(
        self,
        *,
        guild_id: int,
        suspect_id: int,
        detained_by: int,
        reason: str,
        evidence: str | None = None,
    ) -> Result[SuspectProfile, StateCouncilError]:
        """Detain a suspect."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn

            # Check if already detained
            existing = await self._gateway.fetch_suspect_profile(
                c, guild_id=guild_id, suspect_id=suspect_id
            )
            if existing is not None and existing.is_detained:
                return Err(
                    StateCouncilValidationError(
                        f"Suspect {suspect_id} is already detained.",
                        context={"guild_id": guild_id, "suspect_id": suspect_id},
                    )
                )

            # Create or update suspect profile
            suspect = await self._gateway.upsert_suspect_profile(
                c,
                guild_id=guild_id,
                suspect_id=suspect_id,
                detained_by=detained_by,
                reason=reason,
                evidence=evidence,
                is_detained=True,
            )

            # Schedule auto-release if configured
            config_result = await self.get_config(guild_id=guild_id)
            if isinstance(config_result, Ok):
                config = cast(StateCouncilConfig, config_result.unwrap())
                if config.auto_release_hours and config.auto_release_hours > 0:
                    self._schedule_auto_release_job(
                        guild_id=guild_id,
                        suspect_id=suspect_id,
                        hours=config.auto_release_hours,
                        scheduled_by=detained_by,
                    )

            return Ok(suspect)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            IdentityNotFoundError: IdentityNotFoundError,
            Exception: DatabaseError,
        },
    )
    async def release_suspect(
        self,
        *,
        guild_id: int,
        suspect_id: int,
        released_by: int,
        release_reason: str,
    ) -> Result[SuspectReleaseResult, StateCouncilError]:
        """Release a detained suspect."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn

            # Get suspect profile
            suspect = await self._gateway.fetch_suspect_profile(
                c, guild_id=guild_id, suspect_id=suspect_id
            )
            if suspect is None:
                return Err(
                    IdentityNotFoundError(
                        f"Suspect profile not found for {suspect_id}.",
                        context={"guild_id": guild_id, "suspect_id": suspect_id},
                    )
                )

            if not suspect.is_detained:
                return Err(
                    StateCouncilValidationError(
                        f"Suspect {suspect_id} is not currently detained.",
                        context={"guild_id": guild_id, "suspect_id": suspect_id},
                    )
                )

            # Update suspect status
            await self._gateway.upsert_suspect_profile(
                c,
                guild_id=guild_id,
                suspect_id=suspect_id,
                is_detained=False,
                released_by=released_by,
                release_reason=release_reason,
            )

            # Cancel auto-release job
            self._cancel_auto_release_job(guild_id=guild_id, suspect_id=suspect_id)

            # Create release result
            detention_duration = None
            if suspect.arrested_at:
                detention_duration = int(
                    (datetime.now(timezone.utc) - suspect.arrested_at).total_seconds() / 3600
                )

            result = SuspectReleaseResult(
                suspect_id=suspect_id,
                display_name=suspect.display_name,
                released=True,
                was_detained=True,
                released_by=released_by,
                release_reason=release_reason,
                detention_duration_hours=detention_duration,
            )

            return Ok(result)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def get_suspect_profile(
        self, *, guild_id: int, suspect_id: int
    ) -> Result[SuspectProfile | None, StateCouncilError]:
        """Get a suspect's profile."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            profile = await self._gateway.fetch_suspect_profile(
                c, guild_id=guild_id, suspect_id=suspect_id
            )
            return Ok(profile)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def list_detained_suspects(
        self, *, guild_id: int
    ) -> Result[Sequence[SuspectProfile], StateCouncilError]:
        """List all currently detained suspects."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            suspects = await self._gateway.fetch_detained_suspects(c, guild_id=guild_id)
            return Ok(suspects)

    # --- Statistics ---
    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def get_summary(self, *, guild_id: int) -> Result[StateCouncilSummary, StateCouncilError]:
        """Get state council summary statistics."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            summary = await self._gateway.fetch_state_council_summary(c, guild_id=guild_id)
            if summary is None:
                return Err(
                    StateCouncilNotConfiguredError(
                        "State council summary not available.",
                        context={"guild_id": guild_id},
                    )
                )
            return Ok(summary)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def get_department_stats(
        self, *, guild_id: int, department_id: str
    ) -> Result[DepartmentStats, StateCouncilError]:
        """Get statistics for a specific department."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            stats = await self._gateway.fetch_department_stats(
                c, guild_id=guild_id, department_id=department_id
            )
            return Ok(stats)

    # --- Permission Checks ---
    @async_returns_result(
        StateCouncilError,
        exception_map={
            StateCouncilNotConfiguredError: StateCouncilNotConfiguredError,
            Exception: StateCouncilError,
        },
    )
    async def check_leader_permission(
        self, *, guild_id: int, user_id: int, user_roles: Sequence[int]
    ) -> Result[bool, StateCouncilError]:
        """Check if user has leader permission."""
        config_result = await self.get_config(guild_id=guild_id)
        if isinstance(config_result, Err):
            err_value = config_result.error
            if isinstance(err_value, StateCouncilError):
                return Err(err_value)
            return Err(StateCouncilError(str(err_value)))

        config = cast(StateCouncilConfig, getattr(config_result, "value", None))

        # Check by user ID
        if config.leader_id is not None and config.leader_id == user_id:
            return Ok(True)

        # Check by role
        if config.leader_role_id is not None and config.leader_role_id in user_roles:
            return Ok(True)

        return Ok(False)

    @async_returns_result(
        StateCouncilError,
        exception_map={
            DepartmentNotFoundError: DepartmentNotFoundError,
            StateCouncilPermissionDeniedError: StateCouncilPermissionDeniedError,
            Exception: StateCouncilError,
        },
    )
    async def check_department_permission(
        self, *, guild_id: int, user_id: int, department_id: str
    ) -> Result[bool, StateCouncilError]:
        """Check if user has permission for a department."""
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn

            # Check if department exists
            department = await self._gateway.fetch_department_config(
                c, guild_id=guild_id, department=department_id
            )
            if department is None:
                return Err(
                    DepartmentNotFoundError(
                        f"Department {department_id} not found.",
                        context={"guild_id": guild_id, "department_id": department_id},
                    )
                )

            # Check if user has department role
            user_roles = await self._gateway.fetch_member_roles(
                c, guild_id=guild_id, member_id=user_id
            )
            department_roles = await self._gateway.fetch_department_roles(
                c, guild_id=guild_id, department_id=department_id
            )

            has_permission = bool(set(user_roles) & {r.role_id for r in department_roles})
            return Ok(has_permission)

    # --- Business License Management ---
    @async_returns_result(
        StateCouncilError,
        exception_map={
            DuplicateLicenseError: DuplicateLicenseError,
            StateCouncilValidationError: StateCouncilValidationError,
            Exception: DatabaseError,
        },
    )
    async def issue_business_license(
        self,
        *,
        guild_id: int,
        user_id: int,
        license_type: str,
        issued_by: int,
        expires_at: datetime,
    ) -> Result[BusinessLicense, Error]:
        """發放商業許可給指定用戶。

        Args:
            guild_id: Discord 伺服器 ID
            user_id: 目標用戶 ID
            license_type: 許可類型
            issued_by: 核發人員 ID
            expires_at: 到期時間

        Returns:
            Result[BusinessLicense, StateCouncilError]: 成功返回許可記錄
        """
        # Validation
        if not license_type or not license_type.strip():
            return Err(
                StateCouncilValidationError(
                    "License type cannot be empty.",
                    context={"license_type": license_type},
                )
            )
        if expires_at <= datetime.now(timezone.utc):
            return Err(
                StateCouncilValidationError(
                    "Expiration date must be in the future.",
                    context={"expires_at": str(expires_at)},
                )
            )

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            result = await self._license_gateway.issue_license(
                c,
                guild_id=guild_id,
                user_id=user_id,
                license_type=license_type,
                issued_by=issued_by,
                expires_at=expires_at,
            )
            if isinstance(result, Err):
                err = result.unwrap_err()
                # Check for duplicate license error
                if "already has an active license" in str(err):
                    return Err(
                        DuplicateLicenseError(
                            f"User already has an active {license_type} license.",
                            context={
                                "guild_id": guild_id,
                                "user_id": user_id,
                                "license_type": license_type,
                            },
                        )
                    )
                return Err(StateCouncilError(str(err)))
            return result.value

    @async_returns_result(
        StateCouncilError,
        exception_map={
            BusinessLicenseNotFoundError: BusinessLicenseNotFoundError,
            InvalidLicenseStatusError: InvalidLicenseStatusError,
            Exception: DatabaseError,
        },
    )
    async def revoke_business_license(
        self,
        *,
        license_id: str,
        revoked_by: int,
        revoke_reason: str,
    ) -> Result[BusinessLicense, Error]:
        """撤銷商業許可。

        Args:
            license_id: 許可 ID (UUID 字串)
            revoked_by: 撤銷人員 ID
            revoke_reason: 撤銷原因

        Returns:
            Result[BusinessLicense, StateCouncilError]: 成功返回更新後的許可記錄
        """
        from uuid import UUID

        # Validation
        if not revoke_reason or not revoke_reason.strip():
            return Err(
                StateCouncilValidationError(
                    "Revoke reason cannot be empty.",
                    context={"revoke_reason": revoke_reason},
                )
            )

        try:
            uuid_id = UUID(license_id)
        except (ValueError, TypeError):
            return Err(
                StateCouncilValidationError(
                    "Invalid license ID format.",
                    context={"license_id": license_id},
                )
            )

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            result = await self._license_gateway.revoke_license(
                c,
                license_id=uuid_id,
                revoked_by=revoked_by,
                revoke_reason=revoke_reason,
            )
            if isinstance(result, Err):
                err = result.unwrap_err()
                err_msg = str(err)
                if "not found" in err_msg.lower():
                    return Err(
                        BusinessLicenseNotFoundError(
                            f"License {license_id} not found.",
                            context={"license_id": license_id},
                        )
                    )
                if "cannot revoke" in err_msg.lower():
                    return Err(
                        InvalidLicenseStatusError(
                            "Cannot revoke license with non-active status.",
                            context={"license_id": license_id},
                        )
                    )
                return Err(StateCouncilError(err_msg))
            return result.value

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def list_business_licenses(
        self,
        *,
        guild_id: int,
        status: str | None = None,
        license_type: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Result[BusinessLicenseListResult, Error]:
        """列出商業許可（支援篩選與分頁）。

        Args:
            guild_id: Discord 伺服器 ID
            status: 篩選狀態（active/expired/revoked）
            license_type: 篩選許可類型
            page: 頁碼（從 1 開始）
            page_size: 每頁筆數

        Returns:
            Result[BusinessLicenseListResult, StateCouncilError]: 許可列表與分頁資訊
        """
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            result = await self._license_gateway.list_licenses(
                c,
                guild_id=guild_id,
                status=status,
                license_type=license_type,
                page=page,
                page_size=page_size,
            )
            if isinstance(result, Err):
                return Err(StateCouncilError(str(result.unwrap_err())))
            return result.value

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def get_user_business_licenses(
        self,
        *,
        guild_id: int,
        user_id: int,
    ) -> Result[Sequence[BusinessLicense], Error]:
        """取得特定用戶的所有商業許可。

        Args:
            guild_id: Discord 伺服器 ID
            user_id: 用戶 ID

        Returns:
            Result[Sequence[BusinessLicense], StateCouncilError]: 用戶的許可列表
        """
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            result = await self._license_gateway.get_user_licenses(
                c,
                guild_id=guild_id,
                user_id=user_id,
            )
            if isinstance(result, Err):
                return Err(StateCouncilError(str(result.unwrap_err())))
            return result.value

    @async_returns_result(
        StateCouncilError,
        exception_map={
            Exception: DatabaseError,
        },
    )
    async def check_user_has_license(
        self,
        *,
        guild_id: int,
        user_id: int,
        license_type: str,
    ) -> Result[bool, Error]:
        """檢查用戶是否擁有特定類型的有效許可。

        Args:
            guild_id: Discord 伺服器 ID
            user_id: 用戶 ID
            license_type: 許可類型

        Returns:
            Result[bool, StateCouncilError]: True 表示擁有有效許可
        """
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            result = await self._license_gateway.check_active_license(
                c,
                guild_id=guild_id,
                user_id=user_id,
                license_type=license_type,
            )
            if isinstance(result, Err):
                return Err(StateCouncilError(str(result.unwrap_err())))
            return result.value

    @async_returns_result(
        StateCouncilError,
        exception_map={
            StateCouncilNotConfiguredError: StateCouncilNotConfiguredError,
            StateCouncilPermissionDeniedError: StateCouncilPermissionDeniedError,
            Exception: StateCouncilError,
        },
    )
    async def check_interior_affairs_permission(
        self, *, guild_id: int, user_id: int, user_roles: Sequence[int]
    ) -> Result[bool, StateCouncilError]:
        """檢查用戶是否具備內政部權限（內政部領導人或國務院領袖）。

        Args:
            guild_id: Discord 伺服器 ID
            user_id: 用戶 ID
            user_roles: 用戶的身分組列表

        Returns:
            Result[bool, StateCouncilError]: True 表示具備權限
        """
        # First check if user is state council leader
        leader_result = await self.check_leader_permission(
            guild_id=guild_id, user_id=user_id, user_roles=user_roles
        )
        if leader_result.is_ok() and leader_result.unwrap():
            return Ok(True)

        # Check department permission for interior affairs
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn

            # Get department roles for interior affairs
            department_roles = await self._gateway.fetch_department_roles(
                c, guild_id=guild_id, department_id="interior_affairs"
            )

            # Check if user has any of the department roles
            has_permission = bool(set(user_roles) & {r.role_id for r in department_roles})
            return Ok(has_permission)


__all__ = [
    "StateCouncilServiceResult",
]
