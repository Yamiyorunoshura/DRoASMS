"""契約測試：State Council 面板操作流程（福利、稅收、身分、增發、轉帳）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.bot.services.state_council_service import (
    MonthlyIssuanceLimitExceededError,
    PermissionDeniedError,
    StateCouncilService,
)
from src.bot.services.transfer_service import TransferService
from src.db.gateway.state_council_governance import (
    CurrencyIssuance,
    DepartmentConfig,
    StateCouncilConfig,
    StateCouncilGovernanceGateway,
    TaxRecord,
    WelfareDisbursement,
)


class _FakeTxn:
    async def __aenter__(self) -> "_FakeTxn":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class _FakeConnection:
    def __init__(self, gw: "_FakeGateway") -> None:
        self._gw = gw

    def transaction(self) -> _FakeTxn:
        return _FakeTxn()


class _FakeAcquire:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConnection:
        return self._conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self._conn)


class _FakeGateway(StateCouncilGovernanceGateway):
    def __init__(self, *, schema: str = "governance") -> None:
        super().__init__(schema=schema)
        self._cfg: dict[int, StateCouncilConfig] = {}
        self._dept_configs: dict[tuple[int, str], DepartmentConfig] = {}
        self._welfares: dict[int, WelfareDisbursement] = {}
        self._taxes: dict[int, TaxRecord] = {}
        self._identities: dict[int, Any] = {}
        self._issuances: dict[int, CurrencyIssuance] = {}
        self._transfers: dict[int, Any] = {}
        self._next_id = 1

    async def upsert_state_council_config(
        self,
        connection: Any,
        *,
        guild_id: int,
        leader_id: int | None = None,
        leader_role_id: int | None = None,
        internal_affairs_account_id: int = 1001,
        finance_account_id: int = 1002,
        security_account_id: int = 1003,
        central_bank_account_id: int = 1004,
    ) -> StateCouncilConfig:
        cfg = StateCouncilConfig(
            guild_id=guild_id,
            leader_id=leader_id or 10,
            leader_role_id=leader_role_id or 200,
            internal_affairs_account_id=internal_affairs_account_id,
            finance_account_id=finance_account_id,
            security_account_id=security_account_id,
            central_bank_account_id=central_bank_account_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._cfg[guild_id] = cfg
        return cfg

    async def fetch_state_council_config(
        self, connection: Any, *, guild_id: int
    ) -> StateCouncilConfig | None:
        return self._cfg.get(guild_id)

    async def upsert_department_config(
        self,
        connection: Any,
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
        dept_id = self._next_id
        self._next_id += 1
        dept_cfg = DepartmentConfig(
            id=dept_id,
            guild_id=guild_id,
            department=department,
            role_id=role_id,
            welfare_amount=welfare_amount,
            welfare_interval_hours=welfare_interval_hours,
            tax_rate_basis=tax_rate_basis,
            tax_rate_percent=tax_rate_percent,
            max_issuance_per_month=max_issuance_per_month,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._dept_configs[(guild_id, department)] = dept_cfg
        return dept_cfg

    async def fetch_department_config(
        self, connection: Any, *, guild_id: int, department: str
    ) -> DepartmentConfig | None:
        return self._dept_configs.get((guild_id, department))

    async def check_department_permission(
        self, connection: Any, *, guild_id: int, department: str, user_roles: list[int]
    ) -> bool:
        dept_cfg = self._dept_configs.get((guild_id, department))
        if dept_cfg is None or dept_cfg.role_id is None:
            return False
        return dept_cfg.role_id in user_roles

    async def create_welfare_disbursement(
        self,
        connection: Any,
        *,
        guild_id: int,
        recipient_id: int,
        amount: int,
        period: str,
        reason: str,
        disbursed_by: int,
    ) -> WelfareDisbursement:
        welfare_id = self._next_id
        self._next_id += 1
        welfare = WelfareDisbursement(
            id=welfare_id,
            guild_id=guild_id,
            recipient_id=recipient_id,
            amount=amount,
            period=period,
            reason=reason,
            disbursed_by=disbursed_by,
            created_at=datetime.now(timezone.utc),
        )
        self._welfares[welfare_id] = welfare
        return welfare

    async def create_tax_record(
        self,
        connection: Any,
        *,
        guild_id: int,
        taxpayer_id: int,
        tax_amount: int,
        tax_type: str,
        assessment_period: str,
        collected_by: int,
    ) -> TaxRecord:
        tax_id = self._next_id
        self._next_id += 1
        tax = TaxRecord(
            id=tax_id,
            guild_id=guild_id,
            taxpayer_id=taxpayer_id,
            tax_amount=tax_amount,
            tax_type=tax_type,
            assessment_period=assessment_period,
            collected_by=collected_by,
            created_at=datetime.now(timezone.utc),
        )
        self._taxes[tax_id] = tax
        return tax

    async def create_identity_record(
        self,
        connection: Any,
        *,
        guild_id: int,
        target_id: int,
        action: str,
        reason: str,
        performed_by: int,
    ) -> Any:
        identity_id = self._next_id
        self._next_id += 1
        # 簡化的身份記錄
        identity = {
            "id": identity_id,
            "guild_id": guild_id,
            "target_id": target_id,
            "action": action,
            "reason": reason,
            "performed_by": performed_by,
            "created_at": datetime.now(timezone.utc),
        }
        self._identities[identity_id] = identity
        return identity

    async def create_currency_issuance(
        self,
        connection: Any,
        *,
        guild_id: int,
        amount: int,
        reason: str,
        month_period: str,
        issued_by: int,
    ) -> CurrencyIssuance:
        issuance_id = self._next_id
        self._next_id += 1
        issuance = CurrencyIssuance(
            id=issuance_id,
            guild_id=guild_id,
            amount=amount,
            reason=reason,
            month_period=month_period,
            issued_by=issued_by,
            created_at=datetime.now(timezone.utc),
        )
        self._issuances[issuance_id] = issuance
        return issuance

    async def sum_monthly_issuance(
        self, connection: Any, *, guild_id: int, department: str, month_period: str
    ) -> int:
        total = 0
        for issuance in self._issuances.values():
            if issuance.guild_id == guild_id and issuance.month_period == month_period:
                total += issuance.amount
        return total

    async def create_interdepartment_transfer(
        self,
        connection: Any,
        *,
        guild_id: int,
        from_department: str,
        to_department: str,
        amount: int,
        reason: str,
        transferred_by: int,
    ) -> Any:
        transfer_id = self._next_id
        self._next_id += 1
        transfer = {
            "id": transfer_id,
            "guild_id": guild_id,
            "from_department": from_department,
            "to_department": to_department,
            "amount": amount,
            "reason": reason,
            "transferred_by": transferred_by,
            "created_at": datetime.now(timezone.utc),
        }
        self._transfers[transfer_id] = transfer
        return transfer


@pytest.mark.contract
@pytest.mark.asyncio
async def test_state_council_panel_welfare_contract() -> None:
    """契約測試：面板福利發放操作。"""
    gateway = AsyncMock(spec=StateCouncilGovernanceGateway)
    transfer_service = AsyncMock(spec=TransferService)
    svc = StateCouncilService(gateway=gateway, transfer_service=transfer_service)

    # Mock config
    mock_config = StateCouncilConfig(
        guild_id=100,
        leader_id=10,
        leader_role_id=200,
        internal_affairs_account_id=1001,
        finance_account_id=1002,
        security_account_id=1003,
        central_bank_account_id=1004,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    gateway.fetch_config.return_value = mock_config

    # Mock department config
    mock_dept_config = DepartmentConfig(
        id=1,
        guild_id=100,
        department="內政部",
        role_id=300,
        welfare_amount=100,
        welfare_interval_hours=24,
        tax_rate_basis=0,
        tax_rate_percent=0,
        max_issuance_per_month=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    gateway.fetch_department_config.return_value = mock_dept_config
    gateway.check_department_permission.return_value = True

    # Mock welfare creation
    mock_welfare = WelfareDisbursement(
        id=1,
        guild_id=100,
        recipient_id=20,
        amount=100,
        period="2025-01",
        reason="測試福利",
        disbursed_by=10,
        created_at=datetime.now(timezone.utc),
    )
    gateway.create_welfare_disbursement.return_value = mock_welfare

    with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        # 福利發放
        result = await svc.disburse_welfare(
            guild_id=100,
            department="內政部",
            user_id=10,
            user_roles=[200, 300],
            recipient_id=20,
            amount=100,
            reason="測試福利",
            period="2025-01",
        )

        assert result.recipient_id == 20
        assert result.amount == 100
        assert result.period == "2025-01"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_state_council_panel_tax_collection_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """契約測試：面板稅收操作。"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)
    await svc.set_config(guild_id=100, leader_id=10, leader_role_id=200)

    # 設定財政部權限
    await svc.set_department_config(
        guild_id=100,
        department="財政部",
        department_role_id=400,
        max_welfare_per_month=0,
    )

    # 稅收（需要先有餘額）
    # 注意：此測試假設轉帳服務能正常工作
    result = await svc.collect_tax(
        guild_id=100,
        department="財政部",
        user_id=10,
        user_roles=[200, 400],
        taxpayer_id=30,
        taxable_amount=1000,
        tax_rate_percent=10,
        tax_type="所得稅",
        assessment_period="2025-01",
    )

    assert result.taxpayer_id == 30
    assert result.tax_amount == 100  # 1000 * 10%
    assert result.tax_type == "所得稅"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_state_council_panel_identity_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """契約測試：面板身分管理操作。"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)
    await svc.set_config(guild_id=100, leader_id=10, leader_role_id=200)

    # 設定國土安全部權限
    await svc.set_department_config(
        guild_id=100,
        department="國土安全部",
        department_role_id=500,
        max_welfare_per_month=0,
    )

    # 身分操作
    result = await svc.create_identity_record(
        guild_id=100,
        department="國土安全部",
        user_id=10,
        user_roles=[200, 500],
        target_id=40,
        action="移除公民身分",
        reason="測試",
    )

    assert result.target_id == 40
    assert result.action == "移除公民身分"
    assert result.performed_by == 10


@pytest.mark.contract
@pytest.mark.asyncio
async def test_state_council_panel_currency_issuance_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """契約測試：面板貨幣增發操作。"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)
    await svc.set_config(guild_id=100, leader_id=10, leader_role_id=200)

    # 設定中央銀行權限
    await svc.set_department_config(
        guild_id=100,
        department="中央銀行",
        department_role_id=600,
        max_welfare_per_month=0,
        max_issuance_per_month=50000,
    )

    # 貨幣增發
    result = await svc.issue_currency(
        guild_id=100,
        department="中央銀行",
        user_id=10,
        user_roles=[200, 600],
        amount=1000,
        reason="測試增發",
        month_period="2025-01",
    )

    assert result.amount == 1000
    assert result.month_period == "2025-01"
    assert result.reason == "測試增發"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_state_council_panel_transfer_between_departments_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """契約測試：面板部門間轉帳操作。"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)
    await svc.set_config(guild_id=100, leader_id=10, leader_role_id=200)

    # 設定兩個部門
    await svc.set_department_config(
        guild_id=100,
        department="內政部",
        department_role_id=300,
        max_welfare_per_month=0,
    )
    await svc.set_department_config(
        guild_id=100,
        department="財政部",
        department_role_id=400,
        max_welfare_per_month=0,
    )

    # 部門間轉帳
    result = await svc.transfer_between_departments(
        guild_id=100,
        department="內政部",
        user_id=10,
        user_roles=[200, 300],
        from_department="內政部",
        to_department="財政部",
        amount=500,
        reason="測試轉帳",
    )

    assert result.from_department == "內政部"
    assert result.to_department == "財政部"
    assert result.amount == 500


@pytest.mark.contract
@pytest.mark.asyncio
async def test_state_council_panel_transfer_department_to_user_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """契約測試：面板部門轉帳給用戶操作。"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)
    await svc.set_config(guild_id=100, leader_id=10, leader_role_id=200)

    # 設定部門
    await svc.set_department_config(
        guild_id=100,
        department="內政部",
        department_role_id=300,
        max_welfare_per_month=0,
    )

    # 部門轉帳給用戶
    result = await svc.transfer_department_to_user(
        guild_id=100,
        department="內政部",
        user_id=10,
        user_roles=[200, 300],
        recipient_id=50,
        amount=200,
        reason="測試部門轉帳",
    )

    assert result.recipient_id == 50
    assert result.amount == 200
    assert result.reason == "測試部門轉帳"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_state_council_panel_error_handling_permission_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """契約測試：面板錯誤處理（權限不足）。"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)
    await svc.set_config(guild_id=100, leader_id=10, leader_role_id=200)

    # 設定部門但用戶沒有對應權限
    await svc.set_department_config(
        guild_id=100,
        department="內政部",
        department_role_id=300,
        max_welfare_per_month=0,
    )

    # 嘗試執行操作但沒有權限
    with pytest.raises(PermissionDeniedError):
        await svc.disburse_welfare(
            guild_id=100,
            department="內政部",
            user_id=99,  # 沒有權限的用戶
            user_roles=[999],  # 沒有對應的 role
            recipient_id=20,
            amount=100,
            reason="測試",
            period="2025-01",
        )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_state_council_panel_error_handling_department_mismatch_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """契約測試：面板錯誤處理（部門不匹配）。"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)
    await svc.set_config(guild_id=100, leader_id=10, leader_role_id=200)

    # 設定內政部權限
    await svc.set_department_config(
        guild_id=100,
        department="內政部",
        department_role_id=300,
        max_welfare_per_month=0,
    )

    # 嘗試用內政部權限執行財政部操作
    with pytest.raises(PermissionDeniedError, match="Only Finance"):
        await svc.collect_tax(
            guild_id=100,
            department="內政部",  # 錯誤的部門
            user_id=10,
            user_roles=[200, 300],
            taxpayer_id=30,
            taxable_amount=1000,
            tax_rate_percent=10,
            tax_type="所得稅",
            assessment_period="2025-01",
        )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_state_council_panel_error_handling_issuance_limit_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """契約測試：面板錯誤處理（增發限額超標）。"""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)
    await svc.set_config(guild_id=100, leader_id=10, leader_role_id=200)

    # 設定中央銀行權限，限制月增發量
    await svc.set_department_config(
        guild_id=100,
        department="中央銀行",
        department_role_id=600,
        max_welfare_per_month=0,
        max_issuance_per_month=1000,  # 限制為 1000
    )

    # 嘗試增發超過限額
    with pytest.raises(MonthlyIssuanceLimitExceededError):
        await svc.issue_currency(
            guild_id=100,
            department="中央銀行",
            user_id=10,
            user_roles=[200, 600],
            amount=2000,  # 超過限額
            reason="測試",
            month_period="2025-01",
        )
