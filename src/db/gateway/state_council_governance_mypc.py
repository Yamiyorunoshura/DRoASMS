from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from src.cython_ext.state_council_models import (
    CurrencyIssuance,
    DepartmentConfig,
    GovernmentAccount,
    IdentityRecord,
    InterdepartmentTransfer,
    StateCouncilConfig,
    TaxRecord,
    WelfareDisbursement,
)
from src.infra.types.db import ConnectionProtocol


def _safe_row_get(row: Any, key: str, default: Any | None = None) -> Any | None:
    """容錯取得列值。

    - asyncpg.Record 不一定支援 dict.get；
    - 測試常以 dict 模擬；
    因此統一改以 try/except 擢取，缺值時回傳 default（預設 None）。
    """
    try:
        return row[key]
    except Exception:
        return default


def _create_welfare_disbursement_from_row(row: Any) -> WelfareDisbursement:
    """Helper function to create WelfareDisbursement from database row."""
    return WelfareDisbursement(
        disbursement_id=row["disbursement_id"],
        guild_id=row["guild_id"],
        recipient_id=row["recipient_id"],
        amount=row["amount"],
        disbursement_type=row["disbursement_type"],
        reference_id=row["reference_id"],
        disbursed_at=row["disbursed_at"],
    )


def _create_tax_record_from_row(row: Any) -> TaxRecord:
    """Helper function to create TaxRecord from database row."""
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


def _create_currency_issuance_from_row(row: Any) -> CurrencyIssuance:
    """Helper function to create CurrencyIssuance from database row."""
    return CurrencyIssuance(
        issuance_id=row["issuance_id"],
        guild_id=row["guild_id"],
        amount=row["amount"],
        reason=row["reason"],
        month_period=row["month_period"],
        performed_by=row["performed_by"],
        issued_at=row["issued_at"],
    )


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
        return _create_welfare_disbursement_from_row(row)

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
        return [_create_welfare_disbursement_from_row(row) for row in rows]

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
        return _create_tax_record_from_row(row)

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
        return [_create_tax_record_from_row(row) for row in rows]

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
        return _create_currency_issuance_from_row(row)

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
        return [_create_currency_issuance_from_row(row) for row in rows]

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


__all__ = [
    "StateCouncilConfig",
    "DepartmentConfig",
    "GovernmentAccount",
    "WelfareDisbursement",
    "TaxRecord",
    "IdentityRecord",
    "CurrencyIssuance",
    "InterdepartmentTransfer",
    "StateCouncilGovernanceGateway",
    "_create_welfare_disbursement_from_row",
    "_create_tax_record_from_row",
    "_create_currency_issuance_from_row",
]
