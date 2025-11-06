"""效能測試：State Council 部門操作的效能（P95 延遲 < 2s）。"""

from __future__ import annotations

import os
import secrets
import statistics
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.transfer_service import TransferService
from src.db.gateway.state_council_governance import (
    CurrencyIssuance,
    DepartmentConfig,
    StateCouncilConfig,
    StateCouncilGovernanceGateway,
    TaxRecord,
    WelfareDisbursement,
)


def _snowflake() -> int:
    """生成 Discord snowflake ID。"""
    return secrets.randbits(63)


@pytest.mark.performance
@pytest.mark.asyncio
async def test_state_council_welfare_disbursement_latency_p95_under_2s() -> None:
    """效能測試：State Council 福利發放 P95 延遲應小於 2 秒。"""
    total_ops = int(os.getenv("PERF_STATE_COUNCIL_WELFARE_COUNT", "100"))

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

    mock_welfare = WelfareDisbursement(
        id=1,
        guild_id=100,
        recipient_id=20,
        amount=100,
        period="2025-01",
        reason="performance test",
        disbursed_by=10,
        created_at=datetime.now(timezone.utc),
    )
    gateway.create_welfare_disbursement.return_value = mock_welfare

    latencies: list[float] = []

    with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        for i in range(total_ops):
            t0 = time.perf_counter()
            await svc.disburse_welfare(
                guild_id=100,
                department="內政部",
                user_id=10,
                user_roles=[200, 300],
                recipient_id=_snowflake(),
                amount=100 + i,
                reason=f"performance test {i}",
                period="2025-01",
            )
            latencies.append(time.perf_counter() - t0)

    # 計算 P95 延遲
    if latencies:
        latencies_sorted = sorted(latencies)
        p95_index = int(len(latencies_sorted) * 0.95)
        p95_latency = (
            latencies_sorted[p95_index]
            if p95_index < len(latencies_sorted)
            else latencies_sorted[-1]
        )

        assert (
            p95_latency < 2.0
        ), f"P95 welfare latency {p95_latency:.3f}s exceeds 2s budget. Max: {max(latencies):.3f}s, Mean: {statistics.mean(latencies):.3f}s"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_state_council_tax_collection_latency_p95_under_2s() -> None:
    """效能測試：State Council 稅收操作 P95 延遲應小於 2 秒。"""
    total_ops = int(os.getenv("PERF_STATE_COUNCIL_TAX_COUNT", "100"))

    gateway = AsyncMock(spec=StateCouncilGovernanceGateway)
    transfer_service = AsyncMock(spec=TransferService)
    svc = StateCouncilService(gateway=gateway, transfer_service=transfer_service)

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

    mock_dept_config = DepartmentConfig(
        id=1,
        guild_id=100,
        department="財政部",
        role_id=400,
        welfare_amount=0,
        welfare_interval_hours=24,
        tax_rate_basis=0,
        tax_rate_percent=10,
        max_issuance_per_month=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    gateway.fetch_department_config.return_value = mock_dept_config
    gateway.check_department_permission.return_value = True

    mock_tax = TaxRecord(
        id=1,
        guild_id=100,
        taxpayer_id=30,
        taxable_amount=1000,
        tax_rate_percent=10,
        tax_amount=100,
        tax_type="所得稅",
        assessment_period="2025-01",
        created_at=datetime.now(timezone.utc),
    )
    gateway.create_tax_record.return_value = mock_tax
    transfer_service.transfer_currency = AsyncMock()

    latencies: list[float] = []

    with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        for i in range(total_ops):
            t0 = time.perf_counter()
            await svc.collect_tax(
                guild_id=100,
                department="財政部",
                user_id=10,
                user_roles=[200, 400],
                taxpayer_id=_snowflake(),
                taxable_amount=1000 + i * 10,
                tax_rate_percent=10,
                tax_type="所得稅",
                assessment_period="2025-01",
            )
            latencies.append(time.perf_counter() - t0)

    if latencies:
        latencies_sorted = sorted(latencies)
        p95_index = int(len(latencies_sorted) * 0.95)
        p95_latency = (
            latencies_sorted[p95_index]
            if p95_index < len(latencies_sorted)
            else latencies_sorted[-1]
        )

        assert (
            p95_latency < 2.0
        ), f"P95 tax collection latency {p95_latency:.3f}s exceeds 2s budget. Max: {max(latencies):.3f}s, Mean: {statistics.mean(latencies):.3f}s"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_state_council_currency_issuance_latency_p95_under_2s() -> None:
    """效能測試：State Council 貨幣增發 P95 延遲應小於 2 秒。"""
    total_ops = int(os.getenv("PERF_STATE_COUNCIL_ISSUANCE_COUNT", "50"))

    gateway = AsyncMock(spec=StateCouncilGovernanceGateway)
    transfer_service = AsyncMock(spec=TransferService)
    svc = StateCouncilService(gateway=gateway, transfer_service=transfer_service)

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

    mock_dept_config = DepartmentConfig(
        id=1,
        guild_id=100,
        department="中央銀行",
        role_id=600,
        welfare_amount=0,
        welfare_interval_hours=24,
        tax_rate_basis=0,
        tax_rate_percent=0,
        max_issuance_per_month=100000,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    gateway.fetch_department_config.return_value = mock_dept_config
    gateway.check_department_permission.return_value = True
    gateway.sum_monthly_issuance.return_value = 0

    mock_issuance = CurrencyIssuance(
        id=1,
        guild_id=100,
        amount=1000,
        reason="performance test",
        month_period="2025-01",
        issued_by=10,
        created_at=datetime.now(timezone.utc),
    )
    gateway.create_currency_issuance.return_value = mock_issuance
    transfer_service.transfer_currency = AsyncMock()

    latencies: list[float] = []

    with patch("src.bot.services.state_council_service.get_pool") as mock_get_pool:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        for i in range(total_ops):
            t0 = time.perf_counter()
            await svc.issue_currency(
                guild_id=100,
                department="中央銀行",
                user_id=10,
                user_roles=[200, 600],
                amount=1000 + i * 10,
                reason=f"performance test {i}",
                month_period="2025-01",
            )
            latencies.append(time.perf_counter() - t0)

    if latencies:
        latencies_sorted = sorted(latencies)
        p95_index = int(len(latencies_sorted) * 0.95)
        p95_latency = (
            latencies_sorted[p95_index]
            if p95_index < len(latencies_sorted)
            else latencies_sorted[-1]
        )

        assert (
            p95_latency < 2.0
        ), f"P95 currency issuance latency {p95_latency:.3f}s exceeds 2s budget. Max: {max(latencies):.3f}s, Mean: {statistics.mean(latencies):.3f}s"
