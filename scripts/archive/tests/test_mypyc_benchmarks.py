"""性能基準測試：為 Mypc 編譯準備的治理模組性能基準測試框架。

此測試套件提供治理模組的性能基準測量，用於：
1. 建立 mypc 編譯前的性能基準
2. 驗證 mypc 編譯後的性能提升（目標：5-10倍）
3. 監控性能回歸
4. 提供持續性能監控
"""

from __future__ import annotations

import os
import secrets
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Sequence
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.bot.services.council_service import CouncilService
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.supreme_assembly_service import SupremeAssemblyService
from src.db.gateway.council_governance import (
    CouncilConfig,
    CouncilGovernanceGateway,
)
from src.db.gateway.council_governance import (
    Proposal as CouncilProposal,
)
from src.db.gateway.state_council_governance import (
    CurrencyIssuance,
    DepartmentConfig,
    GovernmentAccount,
    StateCouncilConfig,
    StateCouncilGovernanceGateway,
    WelfareDisbursement,
)
from src.db.gateway.supreme_assembly_governance import (
    Proposal as SupremeAssemblyProposal,
)
from src.db.gateway.supreme_assembly_governance import (
    SupremeAssemblyConfig,
    SupremeAssemblyGovernanceGateway,
)
from src.db.gateway.supreme_assembly_governance import (
    Tally as SupremeAssemblyTally,
)


def _snowflake() -> int:
    """生成 Discord snowflake ID。"""
    return secrets.randbits(63)


class PerformanceMetrics:
    """性能測量工具類。"""

    def __init__(self, operation_name: str) -> None:
        self.operation_name = operation_name
        self.latencies: list[float] = []
        self.start_time: float | None = None
        self.end_time: float | None = None

    def start_measurement(self) -> None:
        """開始測量。"""
        self.start_time = time.perf_counter()

    def end_measurement(self) -> None:
        """結束測量並記錄延遲。"""
        if self.start_time is not None:
            latency = time.perf_counter() - self.start_time
            self.latencies.append(latency)
            self.end_time = time.perf_counter()

    def get_stats(self) -> dict[str, Any]:
        """獲取性能統計。"""
        if not self.latencies:
            return {}

        sorted_latencies = sorted(self.latencies)
        return {
            "operation": self.operation_name,
            "count": len(self.latencies),
            "mean_latency_ms": statistics.mean(self.latencies) * 1000,
            "median_latency_ms": statistics.median(self.latencies) * 1000,
            "p95_latency_ms": sorted_latencies[int(len(sorted_latencies) * 0.95)] * 1000,
            "p99_latency_ms": sorted_latencies[int(len(sorted_latencies) * 0.99)] * 1000,
            "min_latency_ms": min(self.latencies) * 1000,
            "max_latency_ms": max(self.latencies) * 1000,
            "total_duration_ms": sum(self.latencies) * 1000,
        }


class MockDataFactory:
    """模擬數據工廠，用於創建測試數據。"""

    @staticmethod
    def create_council_config(guild_id: int) -> CouncilConfig:
        """創建議會配置。"""
        return CouncilConfig(
            guild_id=guild_id,
            council_role_id=_snowflake(),
            council_account_member_id=_snowflake(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def create_state_council_config(guild_id: int) -> StateCouncilConfig:
        """創建國務院配置。"""
        return StateCouncilConfig(
            guild_id=guild_id,
            leader_id=_snowflake(),
            leader_role_id=_snowflake(),
            internal_affairs_account_id=9500000000000001,
            finance_account_id=9500000000000002,
            security_account_id=9500000000000003,
            central_bank_account_id=9500000000000004,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def create_department_config(guild_id: int, department: str) -> DepartmentConfig:
        """創建部會配置。"""
        now = datetime.now(timezone.utc)
        return DepartmentConfig(
            id=secrets.randbits(31),
            guild_id=guild_id,
            department=department,
            role_id=_snowflake(),
            welfare_amount=1_000,
            welfare_interval_hours=24,
            tax_rate_basis=100,
            tax_rate_percent=10,
            max_issuance_per_month=1_000_000,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def create_government_account(
        guild_id: int, department: str, *, balance: int = 2_000_000
    ) -> GovernmentAccount:
        """創建政府帳戶。"""
        now = datetime.now(timezone.utc)
        return GovernmentAccount(
            account_id=_snowflake(),
            guild_id=guild_id,
            department=department,
            balance=balance,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def create_supreme_assembly_config(guild_id: int) -> SupremeAssemblyConfig:
        """創建最高人民會議配置。"""
        return SupremeAssemblyConfig(
            guild_id=guild_id,
            speaker_role_id=_snowflake(),
            member_role_id=_snowflake(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def create_proposal(guild_id: int) -> CouncilProposal:
        """創建提案。"""
        return CouncilProposal(
            proposal_id=secrets.randbits(63),
            guild_id=guild_id,
            proposer_id=_snowflake(),
            target_id=_snowflake(),
            amount=1000,
            description="這是一個性能測試提案",
            attachment_url=None,
            snapshot_n=1,
            threshold_t=3,
            deadline_at=datetime.now(timezone.utc),
            status="進行中",
            reminder_sent=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            target_department_id=None,
        )

    @staticmethod
    def create_supreme_assembly_proposal(
        guild_id: int, member_snapshot: Sequence[int]
    ) -> SupremeAssemblyProposal:
        """創建最高人民會議提案。"""
        snapshot = list(dict.fromkeys(int(x) for x in member_snapshot))
        snapshot_n = len(snapshot) or 1
        threshold_t = snapshot_n // 2 + 1
        now = datetime.now(timezone.utc)
        return SupremeAssemblyProposal(
            proposal_id=uuid4(),
            guild_id=guild_id,
            proposer_id=_snowflake(),
            title="最高人民會議性能測試提案",
            description="這是一個最高人民會議性能測試提案",
            snapshot_n=snapshot_n,
            threshold_t=threshold_t,
            deadline_at=now,
            status="進行中",
            reminder_sent=False,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def create_supreme_assembly_tally(
        *, approve: int, reject: int, abstain: int
    ) -> SupremeAssemblyTally:
        """創建最高人民會議投票統計。"""
        return SupremeAssemblyTally(
            approve=approve,
            reject=reject,
            abstain=abstain,
            total_voted=approve + reject + abstain,
        )


class _DummyTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _DummyAcquire:
    def __init__(self, connection: object) -> None:
        self._connection = connection

    async def __aenter__(self) -> object:
        return self._connection

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _DummyConnection:
    def transaction(self) -> _DummyTransaction:
        return _DummyTransaction()


class _DummyPool:
    def __init__(self) -> None:
        self._connection = _DummyConnection()

    def acquire(self) -> _DummyAcquire:
        return _DummyAcquire(self._connection)


def _make_mock_pool() -> _DummyPool:
    """建立支援 acquire/transaction 的簡易 pool 物件。"""
    return _DummyPool()

    @staticmethod
    def create_department_config(guild_id: int, department: str) -> DepartmentConfig:
        """創建部門配置。"""
        return DepartmentConfig(
            id=_snowflake(),
            guild_id=guild_id,
            department=department,
            role_id=_snowflake(),
            welfare_amount=1000,
            welfare_interval_hours=24,
            tax_rate_basis=10000,
            tax_rate_percent=10,
            max_issuance_per_month=10000,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def create_government_account(guild_id: int, department: str) -> GovernmentAccount:
        """創建政府帳戶。"""
        return GovernmentAccount(
            account_id=_snowflake(),
            guild_id=guild_id,
            department=department,
            balance=10000,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )


# === 議會治理模組性能測試 ===


@pytest.mark.performance
@pytest.mark.asyncio
async def test_council_config_fetch_latency() -> None:
    """測試議會配置獲取延遲。"""
    total_ops = int(os.getenv("PERF_COUNCIL_CONFIG_COUNT", "50"))
    metrics = PerformanceMetrics("council_config_fetch")
    guild_id = _snowflake()

    # 創建服務實例
    gateway = AsyncMock(spec=CouncilGovernanceGateway)
    transfer_service = AsyncMock()
    council_service = CouncilService(gateway=gateway, transfer_service=transfer_service)

    # 設定 mock
    config = MockDataFactory.create_council_config(guild_id)
    council_service._gateway.fetch_config.return_value = config

    with patch("src.bot.services.council_service.get_pool"):
        for _i in range(total_ops):
            metrics.start_measurement()
            await council_service.get_config(guild_id=guild_id)
            metrics.end_measurement()

    stats = metrics.get_stats()
    print(f"議會配置獲取性能統計: {stats}")

    # 性能基準：平均延遲應小於 50ms，P95 應小於 100ms
    assert stats["mean_latency_ms"] < 50, f"平均延遲 {stats['mean_latency_ms']:.2f}ms 超過基準 50ms"
    assert stats["p95_latency_ms"] < 100, f"P95 延遲 {stats['p95_latency_ms']:.2f}ms 超過基準 100ms"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_council_config_set_latency() -> None:
    """測試議會配置設定延遲。"""
    total_ops = int(os.getenv("PERF_COUNCIL_CONFIG_SET_COUNT", "30"))
    metrics = PerformanceMetrics("council_config_set")
    guild_id = _snowflake()

    # 創建服務實例
    gateway = AsyncMock(spec=CouncilGovernanceGateway)
    transfer_service = AsyncMock()
    council_service = CouncilService(gateway=gateway, transfer_service=transfer_service)

    # 設定 mock
    config = MockDataFactory.create_council_config(guild_id)
    council_service._gateway.upsert_config.return_value = config

    with patch("src.bot.services.council_service.get_pool"):
        for i in range(total_ops):
            metrics.start_measurement()
            await council_service.set_config(
                guild_id=guild_id,
                council_role_id=_snowflake() + i,
            )
            metrics.end_measurement()

    stats = metrics.get_stats()
    print(f"議會配置設定性能統計: {stats}")

    # 性能基準：平均延遲應小於 80ms，P95 應小於 150ms
    assert stats["mean_latency_ms"] < 80, f"平均延遲 {stats['mean_latency_ms']:.2f}ms 超過基準 80ms"
    assert stats["p95_latency_ms"] < 150, f"P95 延遲 {stats['p95_latency_ms']:.2f}ms 超過基準 150ms"


# === 國務院治理模組性能測試 ===


@pytest.mark.performance
@pytest.mark.asyncio
async def test_welfare_disbursement_latency() -> None:
    """測試福利發放延遲。"""
    total_ops = int(os.getenv("PERF_WELFARE_COUNT", "30"))
    metrics = PerformanceMetrics("welfare_disbursement")
    guild_id = _snowflake()

    # 創建服務實例
    gateway = AsyncMock(spec=StateCouncilGovernanceGateway)
    transfer_service = AsyncMock()
    state_council_service = StateCouncilService(gateway=gateway, transfer_service=transfer_service)

    # 設定 mock
    config = MockDataFactory.create_state_council_config(guild_id)
    dept_config = MockDataFactory.create_department_config(guild_id, "內政部")
    account = MockDataFactory.create_government_account(guild_id, "內政部")
    welfare = WelfareDisbursement(
        disbursement_id=secrets.randbits(63),
        guild_id=guild_id,
        recipient_id=_snowflake(),
        amount=1000,
        disbursement_type="定期福利",
        reference_id=None,
        disbursed_at=datetime.now(timezone.utc),
    )

    state_council_service._gateway.fetch_config.return_value = config
    state_council_service._gateway.fetch_department_config.return_value = dept_config
    state_council_service._gateway.fetch_government_accounts.return_value = [account]
    state_council_service._gateway.create_welfare_disbursement.return_value = welfare

    with patch("src.bot.services.state_council_service.get_pool"):
        with patch.object(state_council_service, "check_department_permission", return_value=True):
            for i in range(total_ops):
                metrics.start_measurement()
                await state_council_service.disburse_welfare(
                    guild_id=guild_id,
                    department="內政部",
                    user_id=_snowflake(),
                    user_roles=[_snowflake()],
                    recipient_id=_snowflake(),
                    amount=1000 + i * 10,
                    disbursement_type="定期福利",
                )
                metrics.end_measurement()

    stats = metrics.get_stats()
    print(f"福利發放性能統計: {stats}")

    # 性能基準：平均延遲應小於 200ms，P95 應小於 500ms
    assert (
        stats["mean_latency_ms"] < 200
    ), f"平均延遲 {stats['mean_latency_ms']:.2f}ms 超過基準 200ms"
    assert stats["p95_latency_ms"] < 500, f"P95 延遲 {stats['p95_latency_ms']:.2f}ms 超過基準 500ms"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_currency_issuance_latency() -> None:
    """測試貨幣增發延遲。"""
    total_ops = int(os.getenv("PERF_ISSUANCE_COUNT", "20"))
    metrics = PerformanceMetrics("currency_issuance")
    guild_id = _snowflake()

    # 創建服務實例
    gateway = AsyncMock(spec=StateCouncilGovernanceGateway)
    transfer_service = AsyncMock()
    state_council_service = StateCouncilService(gateway=gateway, transfer_service=transfer_service)

    # 設定 mock
    dept_config = MockDataFactory.create_department_config(guild_id, "中央銀行")
    account = MockDataFactory.create_government_account(guild_id, "中央銀行")
    issuance = CurrencyIssuance(
        issuance_id=secrets.randbits(63),
        guild_id=guild_id,
        amount=5000,
        reason="性能測試增發",
        performed_by=_snowflake(),
        month_period="2025-01",
        issued_at=datetime.now(timezone.utc),
    )

    state_council_service._gateway.fetch_department_config.return_value = dept_config
    state_council_service._gateway.fetch_government_accounts.return_value = [account]
    state_council_service._gateway.sum_monthly_issuance.return_value = 0
    state_council_service._gateway.create_currency_issuance.return_value = issuance

    with patch("src.bot.services.state_council_service.get_pool"):
        with patch.object(state_council_service, "check_department_permission", return_value=True):
            for i in range(total_ops):
                metrics.start_measurement()
                await state_council_service.issue_currency(
                    guild_id=guild_id,
                    department="中央銀行",
                    user_id=_snowflake(),
                    user_roles=[_snowflake()],
                    amount=5000 + i * 100,
                    reason=f"性能測試增發 {i}",
                    month_period="2025-01",
                )
                metrics.end_measurement()

    stats = metrics.get_stats()
    print(f"貨幣增發性能統計: {stats}")

    # 性能基準：平均延遲應小於 150ms，P95 應小於 300ms
    assert (
        stats["mean_latency_ms"] < 150
    ), f"平均延遲 {stats['mean_latency_ms']:.2f}ms 超過基準 150ms"
    assert stats["p95_latency_ms"] < 300, f"P95 延遲 {stats['p95_latency_ms']:.2f}ms 超過基準 300ms"


# === 最高人民會議治理模組性能測試 ===


@pytest.mark.performance
@pytest.mark.asyncio
async def test_supreme_assembly_proposal_creation_latency() -> None:
    """測試最高人民會議提案創建延遲。"""
    total_ops = int(os.getenv("PERF_SA_PROPOSAL_COUNT", "30"))
    metrics = PerformanceMetrics("supreme_assembly_proposal_creation")
    guild_id = _snowflake()

    # 創建服務實例
    gateway = AsyncMock(spec=SupremeAssemblyGovernanceGateway)
    transfer_service = AsyncMock()
    supreme_assembly_service = SupremeAssemblyService(
        gateway=gateway, transfer_service=transfer_service
    )

    # 準備成員名單快照與 mock
    member_snapshot = [_snowflake() for _ in range(10)]
    config = MockDataFactory.create_supreme_assembly_config(guild_id)
    proposal = MockDataFactory.create_supreme_assembly_proposal(guild_id, member_snapshot)

    supreme_assembly_service._gateway.fetch_config.return_value = config
    supreme_assembly_service._gateway.create_proposal.return_value = proposal
    supreme_assembly_service._gateway.count_active_by_guild.return_value = 0

    with patch(
        "src.bot.services.supreme_assembly_service.get_pool", return_value=_make_mock_pool()
    ):
        for i in range(total_ops):
            metrics.start_measurement()
            await supreme_assembly_service.create_proposal(
                guild_id=guild_id,
                proposer_id=_snowflake(),
                title=f"最高人民會議性能測試提案 {i}",
                description=f"第 {i} 個最高人民會議性能測試提案",
                snapshot_member_ids=member_snapshot,
                deadline_hours=72,
            )
            metrics.end_measurement()

    stats = metrics.get_stats()
    print(f"最高人民會議提案創建性能統計: {stats}")

    # 性能基準：平均延遲應小於 120ms，P95 應小於 250ms
    assert (
        stats["mean_latency_ms"] < 120
    ), f"平均延遲 {stats['mean_latency_ms']:.2f}ms 超過基準 120ms"
    assert stats["p95_latency_ms"] < 250, f"P95 延遲 {stats['p95_latency_ms']:.2f}ms 超過基準 250ms"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_supreme_assembly_voting_latency() -> None:
    """測試最高人民會議投票延遲。"""
    total_ops = int(os.getenv("PERF_SA_VOTING_COUNT", "50"))
    metrics = PerformanceMetrics("supreme_assembly_voting")
    guild_id = _snowflake()

    # 創建服務實例
    gateway = AsyncMock(spec=SupremeAssemblyGovernanceGateway)
    transfer_service = AsyncMock()
    supreme_assembly_service = SupremeAssemblyService(
        gateway=gateway, transfer_service=transfer_service
    )

    # 準備 mock
    member_snapshot = [_snowflake() for _ in range(10)]
    config = MockDataFactory.create_supreme_assembly_config(guild_id)
    proposal = MockDataFactory.create_supreme_assembly_proposal(guild_id, member_snapshot)
    tally = MockDataFactory.create_supreme_assembly_tally(
        approve=len(member_snapshot) // 2,
        reject=0,
        abstain=0,
    )

    supreme_assembly_service._gateway.fetch_config.return_value = config
    supreme_assembly_service._gateway.fetch_proposal.return_value = proposal
    supreme_assembly_service._gateway.fetch_snapshot.return_value = member_snapshot
    supreme_assembly_service._gateway.upsert_vote.return_value = None
    supreme_assembly_service._gateway.fetch_tally.return_value = tally
    supreme_assembly_service._gateway.mark_status.return_value = None

    with patch(
        "src.bot.services.supreme_assembly_service.get_pool", return_value=_make_mock_pool()
    ):
        for i in range(total_ops):
            metrics.start_measurement()
            voter_id = member_snapshot[i % len(member_snapshot)]
            await supreme_assembly_service.vote(
                proposal_id=proposal.proposal_id,
                voter_id=voter_id,
                choice="approve",
            )
            metrics.end_measurement()

    stats = metrics.get_stats()
    print(f"最高人民會議投票性能統計: {stats}")

    # 性能基準：平均延遲應小於 60ms，P95 應小於 120ms
    assert stats["mean_latency_ms"] < 60, f"平均延遲 {stats['mean_latency_ms']:.2f}ms 超過基準 60ms"
    assert stats["p95_latency_ms"] < 120, f"P95 延遲 {stats['p95_latency_ms']:.2f}ms 超過基準 120ms"


# === 綜合性能測試 ===


@pytest.mark.performance
@pytest.mark.asyncio
async def test_governance_modules_comprehensive_performance() -> None:
    """綜合性能測試：同時測試多個治理模組的性能。"""

    # 準備服務實例
    council_gateway = AsyncMock(spec=CouncilGovernanceGateway)
    state_council_gateway = AsyncMock(spec=StateCouncilGovernanceGateway)
    supreme_assembly_gateway = AsyncMock(spec=SupremeAssemblyGovernanceGateway)

    transfer_service = AsyncMock()

    council_service = CouncilService(gateway=council_gateway, transfer_service=transfer_service)
    state_council_service = StateCouncilService(
        gateway=state_council_gateway, transfer_service=transfer_service
    )
    supreme_assembly_service = SupremeAssemblyService(
        gateway=supreme_assembly_gateway, transfer_service=transfer_service
    )

    guild_id = _snowflake()

    # 準備 mock 數據
    council_config = MockDataFactory.create_council_config(guild_id)
    state_council_config = MockDataFactory.create_state_council_config(guild_id)
    supreme_assembly_config = MockDataFactory.create_supreme_assembly_config(guild_id)
    member_snapshot = [_snowflake() for _ in range(10)]
    sa_proposal = MockDataFactory.create_supreme_assembly_proposal(guild_id, member_snapshot)

    # 設定 mocks
    council_service._gateway.fetch_config.return_value = council_config
    council_service._gateway.upsert_config.return_value = council_config

    state_council_service._gateway.fetch_config.return_value = state_council_config
    state_council_service._gateway.fetch_department_config.return_value = (
        MockDataFactory.create_department_config(guild_id, "內政部")
    )
    state_council_service._gateway.fetch_government_accounts.return_value = [
        MockDataFactory.create_government_account(guild_id, "內政部")
    ]
    state_council_service._gateway.create_welfare_disbursement.return_value = MagicMock()

    supreme_assembly_service._gateway.fetch_config.return_value = supreme_assembly_config
    supreme_assembly_service._gateway.create_proposal.return_value = sa_proposal
    supreme_assembly_service._gateway.count_active_by_guild.return_value = 0

    # 性能測量
    metrics = {
        "council_config": PerformanceMetrics("council_config_concurrent"),
        "welfare": PerformanceMetrics("welfare_concurrent"),
        "sa_proposal": PerformanceMetrics("sa_proposal_concurrent"),
    }

    ops_per_module = 10

    with patch("src.bot.services.council_service.get_pool", return_value=_make_mock_pool()):
        with patch(
            "src.bot.services.state_council_service.get_pool", return_value=_make_mock_pool()
        ):
            with patch(
                "src.bot.services.supreme_assembly_service.get_pool",
                return_value=_make_mock_pool(),
            ):
                with patch.object(
                    state_council_service, "check_department_permission", return_value=True
                ):
                    for i in range(ops_per_module):
                        # 議會配置獲取
                        metrics["council_config"].start_measurement()
                        await council_service.get_config(guild_id=guild_id)
                        metrics["council_config"].end_measurement()

                        # 國務院福利發放
                        metrics["welfare"].start_measurement()
                        await state_council_service.disburse_welfare(
                            guild_id=guild_id,
                            department="內政部",
                            user_id=_snowflake(),
                            user_roles=[_snowflake()],
                            recipient_id=_snowflake(),
                            amount=1000,
                            disbursement_type="定期福利",
                        )
                        metrics["welfare"].end_measurement()

                        # 最高人民會議提案
                        metrics["sa_proposal"].start_measurement()
                        await supreme_assembly_service.create_proposal(
                            guild_id=guild_id,
                            proposer_id=_snowflake(),
                            title=f"綜合測試SA提案 {i}",
                            description="綜合性能測試SA提案",
                            snapshot_member_ids=member_snapshot,
                            deadline_hours=72,
                        )
                        metrics["sa_proposal"].end_measurement()

    # 輸出性能報告
    print("\n=== 綜合性能測試報告 ===")
    for name, metric in metrics.items():
        stats = metric.get_stats()
        if stats:
            print(
                f"{name}: 平均延遲 {stats['mean_latency_ms']:.2f}ms, "
                f"P95延遲 {stats['p95_latency_ms']:.2f}ms"
            )

    # 綜合性能基準驗證
    for name, metric in metrics.items():
        stats = metric.get_stats()
        if stats:
            assert (
                stats["mean_latency_ms"] < 300
            ), f"{name} 平均延遲 {stats['mean_latency_ms']:.2f}ms 超過綜合基準 300ms"
            assert (
                stats["p95_latency_ms"] < 600
            ), f"{name} P95延遲 {stats['p95_latency_ms']:.2f}ms 超過綜合基準 600ms"


# === 性能基準驗證工具 ===


def generate_performance_report() -> dict[str, Any]:
    """生成性能測試報告模板。"""
    return {
        "test_suite": "mypc_benchmarks",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python_version": os.sys.version,
            "platform": os.name,
        },
        "baseline_metrics": {
            "council_config_fetch": {"target_mean_ms": 50, "target_p95_ms": 100},
            "council_config_set": {"target_mean_ms": 80, "target_p95_ms": 150},
            "welfare_disbursement": {"target_mean_ms": 200, "target_p95_ms": 500},
            "currency_issuance": {"target_mean_ms": 150, "target_p95_ms": 300},
            "supreme_assembly_proposal_creation": {"target_mean_ms": 120, "target_p95_ms": 250},
            "supreme_assembly_voting": {"target_mean_ms": 60, "target_p95_ms": 120},
        },
        "mypc_targets": {
            "expected_speedup": "5-10x",
            "performance_improvement_goal": "至少5倍性能提升",
        },
    }


if __name__ == "__main__":
    """運行性能報告生成。"""
    report = generate_performance_report()
    print("性能基準測試報告模板：")
    import json

    print(json.dumps(report, indent=2, ensure_ascii=False))
