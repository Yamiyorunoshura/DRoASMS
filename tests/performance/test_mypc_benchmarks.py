#!/usr/bin/env python3
"""
Mypc 編譯基準測試

此文件用於測試治理模組的 mypyc 編譯相容性和性能基準。
驗證模組能否正確編譯並提供性能提升的基準數據。
"""

from __future__ import annotations

import gc
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

# Import the original and mypyc-compatible versions
try:
    from src.db.gateway.council_governance import (
        CouncilConfig,
        CouncilGovernanceGateway,
        Proposal,
        Tally,
    )

    COUNCIL_AVAILABLE = True
except ImportError:
    COUNCIL_AVAILABLE = False

try:
    from src.db.gateway.supreme_assembly_governance import (
        Proposal as SAProposal,
    )
    from src.db.gateway.supreme_assembly_governance import (
        Summon,
        SupremeAssemblyConfig,
        SupremeAssemblyGovernanceGateway,
    )

    # 移除未使用的 SATally 以符合 lint 規範

    SUPREME_ASSEMBLY_AVAILABLE = True
except ImportError:
    SUPREME_ASSEMBLY_AVAILABLE = False

try:
    from src.db.gateway.state_council_governance_mypc import (
        CurrencyIssuance,
        DepartmentConfig,
        IdentityRecord,
        InterdepartmentTransfer,
        StateCouncilConfig,
        TaxRecord,
        WelfareDisbursement,
    )
    from src.db.gateway.state_council_governance_mypc import (
        StateCouncilGovernanceGateway as MypcStateCouncilGateway,
    )

    MYPYC_STATE_COUNCIL_AVAILABLE = True
except ImportError:
    MYPYC_STATE_COUNCIL_AVAILABLE = False

try:
    from src.cython_ext.economy_balance_models import BalanceSnapshot
    from src.cython_ext.economy_transfer_models import TransferResult
    from src.cython_ext.transfer_pool_core import TransferCheckStateStore

    CYTHON_MODELS_AVAILABLE = True
except ImportError:
    CYTHON_MODELS_AVAILABLE = False


@pytest.mark.skipif(not COUNCIL_AVAILABLE, reason="Council governance module not available")
class TestCouncilGovernanceMypcCompatibility:
    """測試 Council Governance 的 mypyc 相容性"""

    def test_council_config_dataclass_creation(self) -> None:
        """測試 CouncilConfig dataclass 創建"""
        from datetime import datetime

        now = datetime.now()
        config = CouncilConfig(
            guild_id=12345,
            council_role_id=67890,
            council_account_member_id=11111,
            created_at=now,
            updated_at=now,
        )

        assert config.guild_id == 12345
        assert config.council_role_id == 67890
        assert config.council_account_member_id == 11111
        assert config.created_at == now
        assert config.updated_at == now

    def test_proposal_dataclass_creation(self) -> None:
        """測試 Proposal dataclass 創建"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        proposal_id = uuid4()

        proposal = Proposal(
            proposal_id=proposal_id,
            guild_id=12345,
            proposer_id=67890,
            target_id=11111,
            amount=5000,
            description="測試提案",
            attachment_url=None,
            snapshot_n=10,
            threshold_t=6,
            deadline_at=now,
            status="進行中",
            reminder_sent=False,
            created_at=now,
            updated_at=now,
        )

        assert proposal.proposal_id == proposal_id
        assert proposal.guild_id == 12345
        assert proposal.amount == 5000
        assert proposal.description == "測試提案"
        assert proposal.status == "進行中"

    def test_council_gateway_initialization(self) -> None:
        """測試 CouncilGovernanceGateway 初始化"""
        gateway = CouncilGovernanceGateway()
        assert gateway._schema == "governance"

        custom_schema_gateway = CouncilGovernanceGateway(schema="custom_gov")
        assert custom_schema_gateway._schema == "custom_gov"

    def test_tally_dataclass_creation(self) -> None:
        """測試 Tally dataclass 創建"""
        tally = Tally(approve=5, reject=2, abstain=1, total_voted=8)
        assert tally.approve == 5
        assert tally.reject == 2
        assert tally.abstain == 1
        assert tally.total_voted == 8


@pytest.mark.skipif(
    not SUPREME_ASSEMBLY_AVAILABLE, reason="Supreme Assembly governance module not available"
)
class TestSupremeAssemblyMypcCompatibility:
    """測試 Supreme Assembly Governance 的 mypyc 相容性"""

    def test_supreme_assembly_config_dataclass_creation(self) -> None:
        """測試 SupremeAssemblyConfig dataclass 創建"""
        from datetime import datetime

        now = datetime.now()
        config = SupremeAssemblyConfig(
            guild_id=12345,
            speaker_role_id=67890,
            member_role_id=11111,
            created_at=now,
            updated_at=now,
        )

        assert config.guild_id == 12345
        assert config.speaker_role_id == 67890
        assert config.member_role_id == 11111

    def test_supreme_assembly_proposal_dataclass_creation(self) -> None:
        """測試 Supreme Assembly Proposal dataclass 創建"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        proposal_id = uuid4()

        proposal = SAProposal(
            proposal_id=proposal_id,
            guild_id=12345,
            proposer_id=67890,
            title="測試議案",
            description="測試議案描述",
            snapshot_n=10,
            threshold_t=6,
            deadline_at=now,
            status="進行中",
            reminder_sent=False,
            created_at=now,
            updated_at=now,
        )

        assert proposal.proposal_id == proposal_id
        assert proposal.title == "測試議案"
        assert proposal.description == "測試議案描述"

    def test_summon_dataclass_creation(self) -> None:
        """測試 Summon dataclass 創建"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        summon_id = uuid4()

        summon = Summon(
            summon_id=summon_id,
            guild_id=12345,
            invoked_by=67890,
            target_id=11111,
            target_kind="member",
            note="測試傳喚",
            delivered=False,
            delivered_at=None,
            created_at=now,
        )

        assert summon.summon_id == summon_id
        assert summon.target_kind == "member"
        assert summon.delivered is False

    def test_supreme_assembly_gateway_initialization(self) -> None:
        """測試 SupremeAssemblyGovernanceGateway 初始化"""
        gateway = SupremeAssemblyGovernanceGateway()
        assert gateway._schema == "governance"


@pytest.mark.skipif(
    not MYPYC_STATE_COUNCIL_AVAILABLE, reason="Mypc State Council governance module not available"
)
class TestStateCouncilMypcCompatibility:
    """測試 State Council Governance mypc 版本的相容性"""

    def test_state_council_config_dataclass_creation(self) -> None:
        """測試 StateCouncilConfig dataclass 創建"""
        from datetime import datetime

        now = datetime.now()
        config = StateCouncilConfig(
            guild_id=12345,
            leader_id=67890,
            leader_role_id=11111,
            internal_affairs_account_id=22222,
            finance_account_id=33333,
            security_account_id=44444,
            central_bank_account_id=55555,
            created_at=now,
            updated_at=now,
            citizen_role_id=66666,
            suspect_role_id=77777,
        )

        assert config.guild_id == 12345
        assert config.leader_id == 67890
        assert config.citizen_role_id == 66666
        assert config.suspect_role_id == 77777

    def test_department_config_dataclass_creation(self) -> None:
        """測試 DepartmentConfig dataclass 創建"""
        from datetime import datetime

        now = datetime.now()
        config = DepartmentConfig(
            id=1,
            guild_id=12345,
            department="財政部",
            role_id=67890,
            welfare_amount=1000,
            welfare_interval_hours=24,
            tax_rate_basis=50000,
            tax_rate_percent=10,
            max_issuance_per_month=100000,
            created_at=now,
            updated_at=now,
        )

        assert config.id == 1
        assert config.department == "財政部"
        assert config.welfare_amount == 1000

    def test_welfare_disbursement_dataclass_creation(self) -> None:
        """測試 WelfareDisbursement dataclass 創建 (mypc 相容版本)"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        disbursement_id = uuid4()

        disbursement = WelfareDisbursement(
            disbursement_id=disbursement_id,
            guild_id=12345,
            recipient_id=67890,
            amount=5000,
            disbursement_type="定期福利",
            reference_id="REF-001",
            disbursed_at=now,
        )

        assert disbursement.disbursement_id == disbursement_id
        assert disbursement.amount == 5000
        assert disbursement.disbursement_type == "定期福利"

    def test_tax_record_dataclass_creation(self) -> None:
        """測試 TaxRecord dataclass 創建 (mypc 相容版本)"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        tax_id = uuid4()

        tax_record = TaxRecord(
            tax_id=tax_id,
            guild_id=12345,
            taxpayer_id=67890,
            tax_amount=500,
            tax_type="所得稅",
            assessment_period="2024-01",
            taxable_amount=50000,
            tax_rate_percent=10,
            collected_at=now,
            collected_by=11111,
        )

        assert tax_record.tax_id == tax_id
        assert tax_record.tax_amount == 500
        assert tax_record.tax_type == "所得稅"
        assert tax_record.assessment_period == "2024-01"

    def test_currency_issuance_dataclass_creation(self) -> None:
        """測試 CurrencyIssuance dataclass 創建 (mypc 相容版本)"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        issuance_id = uuid4()

        issuance = CurrencyIssuance(
            issuance_id=issuance_id,
            guild_id=12345,
            amount=100000,
            reason="月度發行",
            month_period="2024-01",
            performed_by=67890,
            issued_at=now,
        )

        assert issuance.issuance_id == issuance_id
        assert issuance.amount == 100000
        assert issuance.reason == "月度發行"

    def test_identity_record_dataclass_creation(self) -> None:
        """測試 IdentityRecord dataclass 創建"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        record_id = uuid4()

        record = IdentityRecord(
            record_id=record_id,
            guild_id=12345,
            target_id=67890,
            action="身份認證",
            reason="首次註冊",
            performed_by=11111,
            performed_at=now,
        )

        assert record.record_id == record_id
        assert record.action == "身份認證"

    def test_interdepartment_transfer_dataclass_creation(self) -> None:
        """測試 InterdepartmentTransfer dataclass 創建"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        transfer_id = uuid4()

        transfer = InterdepartmentTransfer(
            transfer_id=transfer_id,
            guild_id=12345,
            from_department="財政部",
            to_department="內政部",
            amount=50000,
            reason="部門間調度",
            performed_by=67890,
            transferred_at=now,
        )

        assert transfer.transfer_id == transfer_id
        assert transfer.from_department == "財政部"
        assert transfer.to_department == "內政部"

    def test_mypc_state_council_gateway_initialization(self) -> None:
        """測試 Mypc StateCouncilGovernanceGateway 初始化"""
        gateway = MypcStateCouncilGateway()
        assert gateway._schema == "governance"

        custom_schema_gateway = MypcStateCouncilGateway(schema="custom_gov")
        assert custom_schema_gateway._schema == "custom_gov"


@pytest.mark.skipif(
    not (COUNCIL_AVAILABLE and SUPREME_ASSEMBLY_AVAILABLE and MYPYC_STATE_COUNCIL_AVAILABLE),
    reason="Not all governance modules available",
)
class TestGovernanceModulesPerformanceBenchmark:
    """治理模組性能基準測試"""

    @pytest.fixture
    def sample_data(self) -> dict[str, Any]:
        """準備測試數據"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        proposal_id = uuid4()

        return {
            "now": now,
            "proposal_id": proposal_id,
            "guild_id": 12345,
            "user_id": 67890,
            "amount": 5000,
            "description": "性能測試提案",
        }

    def test_dataclass_creation_performance(self, sample_data: dict[str, Any]) -> None:
        """測試 dataclass 創建性能"""
        iterations = 10000

        # 測試 CouncilConfig 創建性能
        start_time = time.perf_counter()
        for _ in range(iterations):
            _config = CouncilConfig(
                guild_id=sample_data["guild_id"],
                council_role_id=11111,
                council_account_member_id=22222,
                created_at=sample_data["now"],
                updated_at=sample_data["now"],
            )
        council_time = time.perf_counter() - start_time

        # 測試 StateCouncilConfig 創建性能
        start_time = time.perf_counter()
        for _ in range(iterations):
            _config = StateCouncilConfig(
                guild_id=sample_data["guild_id"],
                leader_id=11111,
                leader_role_id=22222,
                internal_affairs_account_id=33333,
                finance_account_id=44444,
                security_account_id=55555,
                central_bank_account_id=66666,
                created_at=sample_data["now"],
                updated_at=sample_data["now"],
            )
        state_council_time = time.perf_counter() - start_time

        # 輸出性能結果
        print(f"\nDataclass Creation Performance ({iterations} iterations):")
        print(f"CouncilConfig: {council_time:.4f}s ({iterations/council_time:.0f} ops/sec)")
        print(
            f"StateCouncilConfig: {state_council_time:.4f}s ({iterations/state_council_time:.0f} ops/sec)"
        )

        # 基本性能斷言 - 每個操作應該在合理時間內完成
        assert council_time < 1.0, "CouncilConfig creation should be fast"
        assert state_council_time < 1.0, "StateCouncilConfig creation should be fast"

    def test_dataclass_access_performance(self, sample_data: dict[str, Any]) -> None:
        """測試 dataclass 屬性存取性能"""
        iterations = 100000

        # 創建測試對象
        council_config = CouncilConfig(
            guild_id=sample_data["guild_id"],
            council_role_id=11111,
            council_account_member_id=22222,
            created_at=sample_data["now"],
            updated_at=sample_data["now"],
        )

        state_council_config = StateCouncilConfig(
            guild_id=sample_data["guild_id"],
            leader_id=11111,
            leader_role_id=22222,
            internal_affairs_account_id=33333,
            finance_account_id=44444,
            security_account_id=55555,
            central_bank_account_id=66666,
            created_at=sample_data["now"],
            updated_at=sample_data["now"],
        )

        # 測試 CouncilConfig 屬性存取性能
        start_time = time.perf_counter()
        for _ in range(iterations):
            _ = council_config.guild_id
            _ = council_config.council_role_id
            _ = council_config.council_account_member_id
        council_access_time = time.perf_counter() - start_time

        # 測試 StateCouncilConfig 屬性存取性能
        start_time = time.perf_counter()
        for _ in range(iterations):
            _ = state_council_config.guild_id
            _ = state_council_config.leader_id
            _ = state_council_config.finance_account_id
        state_council_access_time = time.perf_counter() - start_time

        # 輸出性能結果
        print(f"\nDataclass Access Performance ({iterations * 3} accesses):")
        print(
            f"CouncilConfig: {council_access_time:.4f}s ({iterations * 3 / council_access_time:.0f} ops/sec)"
        )
        print(
            f"StateCouncilConfig: {state_council_access_time:.4f}s ({iterations * 3 / state_council_access_time:.0f} ops/sec)"
        )

        # 基本性能斷言
        assert council_access_time < 0.5, "CouncilConfig access should be very fast"
        assert state_council_access_time < 0.5, "StateCouncilConfig access should be very fast"

    def test_memory_usage(self) -> None:
        """測試記憶體使用情況"""
        import sys

        # 創建大量對象測試記憶體使用
        objects_count = 1000

        # 測試 CouncilConfig 記憶體使用
        gc.collect()
        _initial_memory = sys.getsizeof([])  # 基準記憶體（未使用，只作基準示意）

        council_configs = []
        for i in range(objects_count):
            from datetime import datetime

            now = datetime.now()
            config = CouncilConfig(
                guild_id=i,
                council_role_id=i + 1,
                council_account_member_id=i + 2,
                created_at=now,
                updated_at=now,
            )
            council_configs.append(config)

        council_memory = sum(sys.getsizeof(config) for config in council_configs)

        # 測試 StateCouncilConfig 記憶體使用
        gc.collect()
        state_council_configs = []
        for i in range(objects_count):
            from datetime import datetime

            now = datetime.now()
            config = StateCouncilConfig(
                guild_id=i,
                leader_id=i + 1,
                leader_role_id=i + 2,
                internal_affairs_account_id=i + 3,
                finance_account_id=i + 4,
                security_account_id=i + 5,
                central_bank_account_id=i + 6,
                created_at=now,
                updated_at=now,
            )
            state_council_configs.append(config)

        state_council_memory = sum(sys.getsizeof(config) for config in state_council_configs)

        # 輸出記憶體使用結果
        print(f"\nMemory Usage ({objects_count} objects):")
        print(
            f"CouncilConfig: {council_memory / 1024:.2f} KB total, {council_memory / objects_count:.1f} bytes per object"
        )
        print(
            f"StateCouncilConfig: {state_council_memory / 1024:.2f} KB total, {state_council_memory / objects_count:.1f} bytes per object"
        )

        # 驗證記憶體使用在合理範圍內
        assert council_memory / objects_count < 200, "CouncilConfig should be memory efficient"
        assert (
            state_council_memory / objects_count < 300
        ), "StateCouncilConfig should be memory efficient"


@pytest.mark.skipif(not CYTHON_MODELS_AVAILABLE, reason="Cython economy models not available")
class TestCythonEconomyModels:
    """Basic smoke tests for the new Cython-backed economy modules."""

    def test_balance_snapshot_reacts_to_throttle(self) -> None:
        future = datetime.now(timezone.utc)
        snapshot = BalanceSnapshot(
            guild_id=1,
            member_id=2,
            balance=500,
            throttled_until=future,
        )
        assert snapshot.guild_id == 1
        assert snapshot.member_id == 2
        assert isinstance(snapshot.is_throttled, bool)

    def test_transfer_result_protects_metadata(self) -> None:
        data = {"note": "original"}
        result = TransferResult(
            transaction_id=uuid4(),
            guild_id=1,
            initiator_id=10,
            target_id=20,
            amount=100,
            initiator_balance=900,
            target_balance=100,
            metadata=data,
        )
        data["note"] = "mutated"
        assert result.metadata["note"] == "original"

    def test_transfer_check_state_store_flow(self) -> None:
        store = TransferCheckStateStore()
        transfer_id = uuid4()
        assert store.record(transfer_id, "balance", 1) is False
        assert store.record(transfer_id, "cooldown", 1) is False
        assert store.record(transfer_id, "daily_limit", 1) is True
        assert store.all_passed(transfer_id) is True
        assert store.remove(transfer_id) is True


if __name__ == "__main__":
    # 運行基準測試
    pytest.main([__file__, "-v", "-s"])
