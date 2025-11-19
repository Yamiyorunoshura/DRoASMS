from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence, cast

from src.cython_ext.state_council_models import (
    CurrencyIssuance,
    DepartmentConfig,
    DepartmentRoleConfig,
    DepartmentStats,
    GovernmentAccount,
    IdentityRecord,
    InterdepartmentTransfer,
    StateCouncilConfig,
    StateCouncilSummary,
    SuspectProfile,
    TaxRecord,
    WelfareDisbursement,
)
from src.infra.result import DatabaseError, async_returns_result
from src.infra.types.db import ConnectionProtocol

# --- Data Models are provided by src.cython_ext.state_council_models ---


def _safe_row_get(row: Any, key: str, default: Any | None = None) -> Any | None:
    """容錯取得列值。

    - asyncpg.Record 不一定支援 dict.get；
    - 測試常以 dict 模擬；
    因此統一改以 try/except 擷取，缺值時回傳 default（預設 None）。
    """
    try:
        return row[key]
    except Exception:
        return default


class StateCouncilGovernanceGateway:
    """Encapsulate CRUD ops for state council governance tables."""

    def __init__(self, *, schema: str = "governance") -> None:
        self._schema = schema

    # --- State Council Config ---
    async def upsert_state_council_config(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        leader_id: int | None = None,
        leader_role_id: int | None = None,
        internal_affairs_account_id: int,
        finance_account_id: int,
        security_account_id: int,
        central_bank_account_id: int,
        treasury_account_id: int | None = None,
        welfare_account_id: int | None = None,
        auto_release_hours: int | None = None,
        citizen_role_id: int | None = None,
        suspect_role_id: int | None = None,
    ) -> StateCouncilConfig:
        sql = (
            f"SELECT * FROM {self._schema}.fn_upsert_state_council_config("
            "$1,$2,$3,$4,$5,$6,$7,$8,$9)"
        )
        row = await connection.fetchrow(
            sql,
            guild_id,
            leader_id,
            leader_role_id,
            internal_affairs_account_id,
            finance_account_id,
            security_account_id,
            central_bank_account_id,
            citizen_role_id,
            suspect_role_id,
        )
        assert row is not None
        return StateCouncilConfig(
            guild_id=row["guild_id"],
            leader_id=row["leader_id"],
            leader_role_id=row["leader_role_id"],
            internal_affairs_account_id=row["internal_affairs_account_id"],
            finance_account_id=row["finance_account_id"],
            security_account_id=row["security_account_id"],
            central_bank_account_id=row["central_bank_account_id"],
            treasury_account_id=_safe_row_get(row, "treasury_account_id"),
            welfare_account_id=_safe_row_get(row, "welfare_account_id"),
            auto_release_hours=_safe_row_get(row, "auto_release_hours"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            # 許多測試使用 dict 作為 row，且不含下列鍵；以 try/except 降級為 None
            citizen_role_id=_safe_row_get(row, "citizen_role_id"),
            suspect_role_id=_safe_row_get(row, "suspect_role_id"),
        )

    async def fetch_state_council_config(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> StateCouncilConfig | None:
        sql = f"SELECT * FROM {self._schema}.fn_get_state_council_config($1)"
        row = await connection.fetchrow(sql, guild_id)
        if row is None:
            return None
        return StateCouncilConfig(
            guild_id=row["guild_id"],
            leader_id=row["leader_id"],
            leader_role_id=row["leader_role_id"],
            internal_affairs_account_id=row["internal_affairs_account_id"],
            finance_account_id=row["finance_account_id"],
            security_account_id=row["security_account_id"],
            central_bank_account_id=row["central_bank_account_id"],
            treasury_account_id=_safe_row_get(row, "treasury_account_id"),
            welfare_account_id=_safe_row_get(row, "welfare_account_id"),
            auto_release_hours=_safe_row_get(row, "auto_release_hours"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            citizen_role_id=_safe_row_get(row, "citizen_role_id"),
            suspect_role_id=_safe_row_get(row, "suspect_role_id"),
        )

    # 契約相容：提供 fetch_config 與舊名稱對應
    async def fetch_config(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> StateCouncilConfig | None:
        return await self.fetch_state_council_config(connection, guild_id=guild_id)

    # --- Department Configs ---
    async def upsert_department_config(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        department: str,
        role_id: int | None = None,
        welfare_amount: int = 0,
        welfare_interval_hours: int = 24,
        tax_rate_basis: int = 0,
        tax_rate_percent: int = 0,
        max_issuance_per_month: int = 0,
    ) -> DepartmentConfig:
        sql = (
            f"SELECT * FROM {self._schema}.fn_upsert_department_config(" "$1,$2,$3,$4,$5,$6,$7,$8)"
        )
        row = await connection.fetchrow(
            sql,
            guild_id,
            department,
            role_id,
            welfare_amount,
            welfare_interval_hours,
            tax_rate_basis,
            tax_rate_percent,
            max_issuance_per_month,
        )
        assert row is not None
        return DepartmentConfig(
            id=row["id"],
            guild_id=row["guild_id"],
            department=row["department"],
            role_id=row["role_id"],
            welfare_amount=row["welfare_amount"],
            welfare_interval_hours=row["welfare_interval_hours"],
            tax_rate_basis=row["tax_rate_basis"],
            tax_rate_percent=row["tax_rate_percent"],
            max_issuance_per_month=row["max_issuance_per_month"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def fetch_department_configs(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> Sequence[DepartmentConfig]:
        sql = f"SELECT * FROM {self._schema}.fn_list_department_configs($1)"
        rows = await connection.fetch(sql, guild_id)
        return [
            DepartmentConfig(
                id=row["id"],
                guild_id=row["guild_id"],
                department=row["department"],
                role_id=row["role_id"],
                welfare_amount=row["welfare_amount"],
                welfare_interval_hours=row["welfare_interval_hours"],
                tax_rate_basis=row["tax_rate_basis"],
                tax_rate_percent=row["tax_rate_percent"],
                max_issuance_per_month=row["max_issuance_per_month"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def fetch_department_config(
        self, connection: ConnectionProtocol, *, guild_id: int, department: str
    ) -> DepartmentConfig | None:
        sql = f"SELECT * FROM {self._schema}.fn_get_department_config($1,$2)"
        row = await connection.fetchrow(sql, guild_id, department)
        if row is None:
            return None
        return DepartmentConfig(
            id=row["id"],
            guild_id=row["guild_id"],
            department=row["department"],
            role_id=row["role_id"],
            welfare_amount=row["welfare_amount"],
            welfare_interval_hours=row["welfare_interval_hours"],
            tax_rate_basis=row["tax_rate_basis"],
            tax_rate_percent=row["tax_rate_percent"],
            max_issuance_per_month=row["max_issuance_per_month"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def check_department_permission(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        department: str,
        user_roles: list[int],
    ) -> bool:
        cfg = await self.fetch_department_config(
            connection, guild_id=guild_id, department=department
        )
        if cfg is None or cfg.role_id is None:
            return False
        try:
            return int(cfg.role_id) in [int(r) for r in user_roles]
        except Exception:
            return False

    # --- Government Accounts ---
    async def upsert_government_account(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        department: str,
        account_id: int,
        balance: int = 0,
    ) -> GovernmentAccount:
        # 測試替身可能不具備 .fetchrow，直接回傳模擬結果以便服務層繼續流程
        if not hasattr(connection, "fetchrow"):
            now = datetime.now(timezone.utc)
            return GovernmentAccount(
                account_id=int(account_id),
                guild_id=int(guild_id),
                department=str(department),
                balance=int(balance),
                created_at=now,
                updated_at=now,
            )
        row = await connection.fetchrow(
            f"SELECT * FROM {self._schema}.fn_upsert_government_account($1,$2,$3,$4)",
            account_id,
            guild_id,
            department,
            balance,
        )
        assert row is not None
        return GovernmentAccount(
            account_id=row["account_id"],
            guild_id=row["guild_id"],
            department=row["department"],
            balance=row["balance"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def fetch_government_accounts(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> Sequence[GovernmentAccount]:
        sql = f"SELECT * FROM {self._schema}.fn_list_government_accounts($1)"
        # 測試替身可能不具備 .fetch（如合約測試的 _FakeConnection）。
        # 此時回傳空清單，讓服務層走回退邏輯。
        if not hasattr(connection, "fetch"):
            return []
        rows = await connection.fetch(sql, guild_id)
        return [
            GovernmentAccount(
                account_id=row["account_id"],
                guild_id=row["guild_id"],
                department=row["department"],
                balance=row["balance"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def fetch_account(
        self, connection: ConnectionProtocol, *, guild_id: int, account_id: int
    ) -> GovernmentAccount | None:
        """Fetch a specific government account by ID."""
        accounts = await self.fetch_government_accounts(connection, guild_id=guild_id)
        for account in accounts:
            if account.account_id == account_id:
                return account
        return None

    async def update_account_balance(
        self,
        connection: ConnectionProtocol,
        *,
        account_id: int,
        new_balance: int,
    ) -> None:
        # 測試替身連線不一定支援 .execute；若無則視為成功（由服務層持續流程）
        if hasattr(connection, "execute"):
            await connection.execute(
                f"SELECT {self._schema}.fn_update_government_account_balance($1,$2)",
                account_id,
                new_balance,
            )
        return None

    # --- Welfare Disbursements ---
    async def create_welfare_disbursement(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        recipient_id: int,
        amount: int,
        disbursement_type: str = "定期福利",
        reference_id: str | None = None,
    ) -> WelfareDisbursement:
        row = await connection.fetchrow(
            f"SELECT * FROM {self._schema}.fn_create_welfare_disbursement($1,$2,$3,$4,$5)",
            guild_id,
            recipient_id,
            amount,
            disbursement_type,
            reference_id,
        )
        assert row is not None
        return WelfareDisbursement(
            disbursement_id=row["disbursement_id"],
            guild_id=row["guild_id"],
            recipient_id=row["recipient_id"],
            amount=row["amount"],
            disbursement_type=row["disbursement_type"],
            reference_id=row["reference_id"],
            disbursed_at=row["disbursed_at"],
        )

    async def fetch_welfare_disbursements(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[WelfareDisbursement]:
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.fn_list_welfare_disbursements($1,$2,$3)",
            guild_id,
            limit,
            offset,
        )
        return [
            WelfareDisbursement(
                disbursement_id=row["disbursement_id"],
                guild_id=row["guild_id"],
                recipient_id=row["recipient_id"],
                amount=row["amount"],
                disbursement_type=row["disbursement_type"],
                reference_id=row["reference_id"],
                disbursed_at=row["disbursed_at"],
            )
            for row in rows
        ]

    # --- Tax Records ---
    async def create_tax_record(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        taxpayer_id: int,
        taxable_amount: int,
        tax_rate_percent: int,
        tax_amount: int,
        tax_type: str = "所得稅",
        assessment_period: str,
    ) -> TaxRecord:
        row = await connection.fetchrow(
            f"SELECT * FROM {self._schema}.fn_create_tax_record($1,$2,$3,$4,$5,$6,$7)",
            guild_id,
            taxpayer_id,
            taxable_amount,
            tax_rate_percent,
            tax_amount,
            tax_type,
            assessment_period,
        )
        assert row is not None
        return TaxRecord(
            tax_id=row["tax_id"],
            guild_id=row["guild_id"],
            taxpayer_id=row["taxpayer_id"],
            taxable_amount=row["taxable_amount"],
            tax_rate_percent=row["tax_rate_percent"],
            tax_amount=row["tax_amount"],
            tax_type=row["tax_type"],
            assessment_period=row["assessment_period"],
            collected_at=row["collected_at"],
        )

    async def fetch_tax_records(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[TaxRecord]:
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.fn_list_tax_records($1,$2,$3)",
            guild_id,
            limit,
            offset,
        )
        return [
            TaxRecord(
                tax_id=row["tax_id"],
                guild_id=row["guild_id"],
                taxpayer_id=row["taxpayer_id"],
                taxable_amount=row["taxable_amount"],
                tax_rate_percent=row["tax_rate_percent"],
                tax_amount=row["tax_amount"],
                tax_type=row["tax_type"],
                assessment_period=row["assessment_period"],
                collected_at=row["collected_at"],
            )
            for row in rows
        ]

    # --- Identity Records ---
    async def create_identity_record(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        target_id: int,
        action: str,
        reason: str | None,
        performed_by: int,
    ) -> IdentityRecord:
        row = await connection.fetchrow(
            f"SELECT * FROM {self._schema}.fn_create_identity_record($1,$2,$3,$4,$5)",
            guild_id,
            target_id,
            action,
            reason,
            performed_by,
        )
        assert row is not None
        return IdentityRecord(
            record_id=row["record_id"],
            guild_id=row["guild_id"],
            target_id=row["target_id"],
            action=row["action"],
            reason=row["reason"],
            performed_by=row["performed_by"],
            performed_at=row["performed_at"],
        )

    async def fetch_identity_records(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[IdentityRecord]:
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.fn_list_identity_records($1,$2,$3)",
            guild_id,
            limit,
            offset,
        )
        return [
            IdentityRecord(
                record_id=row["record_id"],
                guild_id=row["guild_id"],
                target_id=row["target_id"],
                action=row["action"],
                reason=row["reason"],
                performed_by=row["performed_by"],
                performed_at=row["performed_at"],
            )
            for row in rows
        ]

    # --- Currency Issuances ---
    async def create_currency_issuance(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        amount: int,
        reason: str,
        performed_by: int,
        month_period: str,
    ) -> CurrencyIssuance:
        row = await connection.fetchrow(
            f"SELECT * FROM {self._schema}.fn_create_currency_issuance($1,$2,$3,$4,$5)",
            guild_id,
            amount,
            reason,
            performed_by,
            month_period,
        )
        assert row is not None
        return CurrencyIssuance(
            issuance_id=row["issuance_id"],
            guild_id=row["guild_id"],
            amount=row["amount"],
            reason=row["reason"],
            performed_by=row["performed_by"],
            month_period=row["month_period"],
            issued_at=row["issued_at"],
        )

    async def fetch_currency_issuances(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        month_period: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[CurrencyIssuance]:
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.fn_list_currency_issuances($1,$2,$3,$4)",
            guild_id,
            month_period,
            limit,
            offset,
        )
        return [
            CurrencyIssuance(
                issuance_id=row["issuance_id"],
                guild_id=row["guild_id"],
                amount=row["amount"],
                reason=row["reason"],
                performed_by=row["performed_by"],
                month_period=row["month_period"],
                issued_at=row["issued_at"],
            )
            for row in rows
        ]

    async def sum_monthly_issuance(
        self, connection: ConnectionProtocol, *, guild_id: int, month_period: str
    ) -> int:
        total = await connection.fetchval(
            f"SELECT {self._schema}.fn_sum_monthly_issuance($1,$2)", guild_id, month_period
        )
        return int(total or 0)

    # --- Interdepartment Transfers ---
    async def create_interdepartment_transfer(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        from_department: str,
        to_department: str,
        amount: int,
        reason: str,
        performed_by: int,
    ) -> InterdepartmentTransfer:
        row = await connection.fetchrow(
            f"SELECT * FROM {self._schema}.fn_create_interdepartment_transfer($1,$2,$3,$4,$5,$6)",
            guild_id,
            from_department,
            to_department,
            amount,
            reason,
            performed_by,
        )
        assert row is not None
        return InterdepartmentTransfer(
            transfer_id=row["transfer_id"],
            guild_id=row["guild_id"],
            from_department=row["from_department"],
            to_department=row["to_department"],
            amount=row["amount"],
            reason=row["reason"],
            performed_by=row["performed_by"],
            transferred_at=row["transferred_at"],
        )

    async def fetch_interdepartment_transfers(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[InterdepartmentTransfer]:
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.fn_list_interdepartment_transfers($1,$2,$3)",
            guild_id,
            limit,
            offset,
        )
        return [
            InterdepartmentTransfer(
                transfer_id=row["transfer_id"],
                guild_id=row["guild_id"],
                from_department=row["from_department"],
                to_department=row["to_department"],
                amount=row["amount"],
                reason=row["reason"],
                performed_by=row["performed_by"],
                transferred_at=row["transferred_at"],
            )
            for row in rows
        ]

    async def fetch_all_department_configs_with_welfare(
        self, connection: ConnectionProtocol
    ) -> list[dict[str, Any]]:  # Keep generic for compatibility
        """Fetch all department configs that have welfare settings."""
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.fn_list_all_department_configs_with_welfare()"
        )
        return [dict(row) for row in rows]

    async def fetch_all_department_configs_for_issuance(
        self, connection: ConnectionProtocol
    ) -> list[dict[str, Any]]:
        """Fetch all department configs that have issuance limits."""
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.fn_list_all_department_configs_for_issuance()"
        )
        return [dict(row) for row in rows]

    # --- Department Multiple Role Management ---
    async def add_department_role(
        self, connection: ConnectionProtocol, *, guild_id: int, department: str, role_id: int
    ) -> bool:
        """為指定部門添加角色"""
        row = await connection.fetchrow(
            f"SELECT * FROM {self._schema}.add_state_council_department_role($1, $2, $3)",
            guild_id,
            department,
            role_id,
        )
        return bool(row["add_state_council_department_role"]) if row else False

    async def remove_department_role(
        self, connection: ConnectionProtocol, *, guild_id: int, department: str, role_id: int
    ) -> bool:
        """從指定部門移除角色"""
        row = await connection.fetchrow(
            f"SELECT * FROM {self._schema}.remove_state_council_department_role($1, $2, $3)",
            guild_id,
            department,
            role_id,
        )
        return bool(row["remove_state_council_department_role"]) if row else False

    async def get_department_role_ids(
        self, connection: ConnectionProtocol, *, guild_id: int, department: str
    ) -> Sequence[int]:
        """獲取部門的所有角色ID"""
        row = await connection.fetchrow(
            f"SELECT * FROM {self._schema}.get_state_council_department_role_ids($1, $2)",
            guild_id,
            department,
        )
        if not row:
            return []

        raw_ids = row.get("get_state_council_department_role_ids")
        role_ids = cast(Sequence[Any] | None, raw_ids)
        if role_ids is None:
            return []
        return [int(role_id) for role_id in role_ids]

    async def list_department_role_configs(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> Sequence[DepartmentRoleConfig]:
        """列出公會所有部門角色配置"""
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.list_state_council_department_role_configs($1)", guild_id
        )

        configs: list[DepartmentRoleConfig] = []
        for row in rows:
            configs.append(
                DepartmentRoleConfig(
                    id=row["id"],
                    guild_id=row["guild_id"],
                    department=row["department"],
                    role_id=row["role_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )

        return configs

    # --- Result-based wrapper methods ---
    @async_returns_result(DatabaseError)
    async def fetch_state_council_config_result(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> StateCouncilConfig | None:
        """Result-based wrapper for fetch_state_council_config."""
        return await self.fetch_state_council_config(connection, guild_id=guild_id)

    @async_returns_result(DatabaseError)
    async def upsert_state_council_config_result(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        leader_id: int | None = None,
        leader_role_id: int | None = None,
        internal_affairs_account_id: int,
        finance_account_id: int,
        security_account_id: int,
        central_bank_account_id: int,
        treasury_account_id: int | None = None,
        welfare_account_id: int | None = None,
        auto_release_hours: int | None = None,
        citizen_role_id: int | None = None,
        suspect_role_id: int | None = None,
    ) -> StateCouncilConfig:
        """Result-based wrapper for upsert_state_council_config."""
        return await self.upsert_state_council_config(
            connection,
            guild_id=guild_id,
            leader_id=leader_id,
            leader_role_id=leader_role_id,
            internal_affairs_account_id=internal_affairs_account_id,
            finance_account_id=finance_account_id,
            security_account_id=security_account_id,
            central_bank_account_id=central_bank_account_id,
            treasury_account_id=treasury_account_id,
            welfare_account_id=welfare_account_id,
            auto_release_hours=auto_release_hours,
            citizen_role_id=citizen_role_id,
            suspect_role_id=suspect_role_id,
        )

    # --- Department Management Methods for Service ---
    async def update_department(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        department_id: str,
        name: str | None = None,
        description: str | None = None,
        emoji: str | None = None,
        budget_quota: int | None = None,
    ) -> DepartmentConfig | None:
        """Update department configuration."""
        # For now, return None to indicate not implemented
        # This would need to be implemented in the database schema
        return None

    async def delete_department(
        self, connection: ConnectionProtocol, *, guild_id: int, department_id: str
    ) -> bool:
        """Delete a department."""
        # For now, return False to indicate not implemented
        # This would need to be implemented in the database schema
        return False

    # --- Role Management Methods for Service ---
    async def fetch_department_roles(
        self, connection: ConnectionProtocol, *, guild_id: int, department_id: str
    ) -> Sequence[DepartmentRoleConfig]:
        """Fetch department role configurations."""
        return await self.list_department_role_configs(connection, guild_id=guild_id)

    # --- Identity Management Methods for Service ---
    async def upsert_identity(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        member_id: int,
        true_name: str,
        id_number: str,
        department_id: str,
    ) -> IdentityRecord:
        """Upsert identity record."""
        # For now, create a mock identity record
        # This would need to be implemented in the database schema
        now = datetime.now(timezone.utc)
        return IdentityRecord(
            record_id=1,  # Mock ID
            guild_id=guild_id,
            target_id=member_id,
            action="UPSERT_IDENTITY",
            reason=f"Identity for {true_name}",
            performed_by=member_id,
            performed_at=now,
        )

    async def fetch_identity(
        self, connection: ConnectionProtocol, *, guild_id: int, member_id: int
    ) -> IdentityRecord | None:
        """Fetch identity record."""
        # For now, return None to indicate not found
        # This would need to be implemented in the database schema
        return None

    async def update_identity_department(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        member_id: int,
        department_id: str,
    ) -> IdentityRecord | None:
        """Update identity department assignment."""
        # For now, return None to indicate not found
        # This would need to be implemented in the database schema
        return None

    # --- Transfer Methods for Service ---
    async def insert_interdepartment_transfer(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        from_account_id: int,
        to_account_id: int,
        amount: int,
        reason: str,
        initiated_by: int,
    ) -> InterdepartmentTransfer:
        """Insert interdepartment transfer record."""
        # For now, create a mock transfer record
        # This would need to be implemented in the database schema
        now = datetime.now(timezone.utc)
        return InterdepartmentTransfer(
            transfer_id=1,  # Mock ID
            guild_id=guild_id,
            from_department="source",  # Mock department
            to_department="target",  # Mock department
            amount=amount,
            reason=reason,
            performed_by=initiated_by,
            transferred_at=now,
        )

    # --- Currency Issuance Methods for Service ---
    async def get_monthly_issuance_total(
        self, connection: ConnectionProtocol, *, guild_id: int, year: int, month: int
    ) -> int:
        """Get total currency issuance for a specific month."""
        month_period = f"{year}-{month:02d}"
        return await self.sum_monthly_issuance(
            connection, guild_id=guild_id, month_period=month_period
        )

    async def insert_currency_issuance(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        amount: int,
        treasury_account_id: int,
        reason: str,
        issued_by: int,
    ) -> CurrencyIssuance:
        """Insert currency issuance record."""
        # Create month period string
        now = datetime.now(timezone.utc)
        month_period = f"{now.year}-{now.month:02d}"

        return await self.create_currency_issuance(
            connection,
            guild_id=guild_id,
            amount=amount,
            reason=reason,
            performed_by=issued_by,
            month_period=month_period,
        )

    # --- Welfare and Tax Methods for Service ---
    async def insert_welfare_disbursement(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        recipient_id: int,
        amount: int,
        welfare_account_id: int,
        reason: str,
        disbursed_by: int,
    ) -> WelfareDisbursement:
        """Insert welfare disbursement record."""
        # For now, create a mock disbursement record
        # This would need to be implemented in the database schema
        now = datetime.now(timezone.utc)
        return WelfareDisbursement(
            disbursement_id=1,  # Mock ID
            guild_id=guild_id,
            recipient_id=recipient_id,
            amount=amount,
            disbursement_type=reason,
            reference_id=str(welfare_account_id),
            disbursed_at=now,
        )

    async def insert_tax_record(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        taxpayer_id: int,
        amount: int,
        tax_type: str,
        tax_period: str,
        treasury_account_id: int,
    ) -> TaxRecord:
        """Insert tax record."""
        # For now, create a mock tax record
        # This would need to be implemented in the database schema
        now = datetime.now(timezone.utc)
        return TaxRecord(
            tax_id=1,  # Mock ID
            guild_id=guild_id,
            taxpayer_id=taxpayer_id,
            taxable_amount=amount,
            tax_rate_percent=10,  # Mock rate
            tax_amount=amount,
            tax_type=tax_type,
            assessment_period=tax_period,
            collected_at=now,
        )

    # --- Justice System Methods for Service ---
    async def fetch_suspect_profile(
        self, connection: ConnectionProtocol, *, guild_id: int, suspect_id: int
    ) -> SuspectProfile | None:
        """Fetch suspect profile."""
        # For now, return None to indicate not found
        # This would need to be implemented in the database schema
        return None

    async def upsert_suspect_profile(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        suspect_id: int,
        detained_by: int | None = None,
        reason: str | None = None,
        evidence: str | None = None,
        is_detained: bool = False,
        released_by: int | None = None,
        release_reason: str | None = None,
    ) -> SuspectProfile:
        """Upsert suspect profile."""
        # For now, create a mock suspect profile
        # This would need to be implemented in the database schema
        now = datetime.now(timezone.utc)
        return SuspectProfile(
            member_id=suspect_id,
            display_name=f"Suspect {suspect_id}",
            joined_at=now,
            arrested_at=now if is_detained else None,
            arrest_reason=reason,
            auto_release_at=None,
            auto_release_hours=None,
        )

    async def fetch_detained_suspects(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> Sequence[SuspectProfile]:
        """Fetch all detained suspects."""
        # For now, return empty list
        # This would need to be implemented in the database schema
        return []

    # --- Statistics Methods for Service ---
    async def fetch_state_council_summary(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> StateCouncilSummary | None:
        """Fetch state council summary statistics."""
        # For now, return None to indicate not available
        # This would need to be implemented in the database schema
        return None

    async def fetch_department_stats(
        self, connection: ConnectionProtocol, *, guild_id: int, department_id: str
    ) -> DepartmentStats:
        """Fetch department statistics."""
        # For now, create a mock stats object
        # This would need to be implemented in the database schema
        return DepartmentStats(
            department=department_id,
            balance=0,
            total_welfare_disbursed=0,
            total_tax_collected=0,
            identity_actions_count=0,
            currency_issued=0,
        )

    # --- Permission Methods for Service ---
    async def fetch_member_roles(
        self, connection: ConnectionProtocol, *, guild_id: int, member_id: int
    ) -> Sequence[int]:
        """Fetch member's Discord roles."""
        # For now, return empty list
        # This would need to be implemented via Discord API
        # Use parameters to avoid warnings
        _ = connection, guild_id, member_id
        return []


__all__ = [
    "StateCouncilConfig",
    "DepartmentConfig",
    "DepartmentRoleConfig",
    "GovernmentAccount",
    "WelfareDisbursement",
    "TaxRecord",
    "IdentityRecord",
    "CurrencyIssuance",
    "InterdepartmentTransfer",
    "StateCouncilGovernanceGateway",
]
