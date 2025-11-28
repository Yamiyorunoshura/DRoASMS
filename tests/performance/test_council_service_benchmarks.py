#!/usr/bin/env python3
"""
Council Service Performance Benchmarks

Performance benchmarks for critical council service operations:
- Vote operations (approve/reject/abstain)
- Proposal creation and lifecycle management
- Result pattern vs exception handling overhead
"""

from __future__ import annotations

import gc
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# Import services for benchmarking - will skip entire file if imports fail
pytest.importorskip("src.bot.services.council_service")
pytest.importorskip("src.db.gateway.council_governance")
pytest.importorskip("src.infra.result")

# ruff: noqa: E402 - imports after importorskip are intentional
from src.bot.services.council_service import CouncilService, CouncilServiceResult, VoteTotals
from src.db.gateway.council_governance import (
    Proposal,
)
from src.infra.result import Err, Error, Ok

COUNCIL_AVAILABLE = True


@pytest.mark.skipif(not COUNCIL_AVAILABLE, reason="Council service not available")
class TestCouncilServicePerformanceBenchmarks:
    """Performance benchmarks for council service operations."""

    @pytest.fixture(autouse=True)
    def mock_pool(self) -> Any:
        """Mock get_pool() to avoid database dependency in benchmarks."""
        mock_pool = MagicMock()
        with patch("src.bot.services.council_service.get_pool", return_value=mock_pool):
            yield mock_pool

    @pytest.fixture
    def sample_data(self) -> dict[str, Any]:
        """Prepare sample data for benchmarks."""
        now = datetime.now(timezone.utc)
        proposal_id = uuid4()

        return {
            "now": now,
            "proposal_id": proposal_id,
            "guild_id": 12345,
            "voter_id": 67890,
            "proposer_id": 11111,
            "target_id": 22222,
            "amount": 5000,
            "description": "性能測試提案",
            "threshold_t": 6,
            "deadline_at": now + timedelta(days=7),
        }

    def test_service_initialization_performance(self, sample_data: dict[str, Any]) -> None:
        """Benchmark service initialization overhead."""
        iterations = 10000

        # Test legacy CouncilService initialization
        start_time = time.perf_counter()
        for _ in range(iterations):
            _service = CouncilService()
        legacy_time = time.perf_counter() - start_time

        # Test CouncilServiceResult initialization
        start_time = time.perf_counter()
        for _ in range(iterations):
            _service = CouncilServiceResult()
        result_time = time.perf_counter() - start_time

        print(f"\nService Initialization Performance ({iterations} iterations):")
        print(f"CouncilService: {legacy_time:.4f}s ({iterations/legacy_time:.0f} ops/sec)")
        print(f"CouncilServiceResult: {result_time:.4f}s ({iterations/result_time:.0f} ops/sec)")
        print(f"Overhead ratio: {result_time/legacy_time:.2f}x")

        # Both should be very fast (< 1ms per initialization)
        assert legacy_time < 1.0, "Legacy service initialization should be fast"
        assert result_time < 1.0, "Result service initialization should be fast"

    def test_static_method_performance(self, sample_data: dict[str, Any]) -> None:
        """Benchmark static method calls (account ID derivation)."""
        iterations = 100000
        guild_id = sample_data["guild_id"]

        # Test legacy service static method
        start_time = time.perf_counter()
        for _ in range(iterations):
            _account_id = CouncilService.derive_council_account_id(guild_id)
        legacy_time = time.perf_counter() - start_time

        # Test result service static method
        start_time = time.perf_counter()
        for _ in range(iterations):
            _account_id = CouncilServiceResult.derive_council_account_id(guild_id)
        result_time = time.perf_counter() - start_time

        print(f"\nStatic Method Performance ({iterations} calls):")
        print(
            f"CouncilService.derive_council_account_id: {legacy_time:.4f}s ({iterations/legacy_time:.0f} ops/sec)"
        )
        print(
            f"CouncilServiceResult.derive_council_account_id: {result_time:.4f}s ({iterations/result_time:.0f} ops/sec)"
        )
        print(f"Overhead ratio: {result_time/legacy_time:.2f}x")

        # Static methods should be extremely fast
        assert legacy_time < 0.1, "Legacy static method should be very fast"
        assert result_time < 0.1, "Result static method should be very fast"

    def test_result_pattern_overhead(self, sample_data: dict[str, Any]) -> None:
        """Benchmark Result pattern vs exception handling overhead."""
        iterations = 10000

        # Simulate Result pattern overhead
        def simulate_result_success() -> Ok[str, Error]:
            return Ok("success")

        def simulate_result_error() -> Err[str, Error]:
            return Err(Error("test error"))

        # Test Result success path
        start_time = time.perf_counter()
        for _ in range(iterations):
            result_obj = simulate_result_success()
            if hasattr(result_obj, "value"):
                _value = result_obj.value
        result_success_time = time.perf_counter() - start_time

        # Test Result error path
        start_time = time.perf_counter()
        for _ in range(iterations):
            result_obj = simulate_result_error()
            if hasattr(result_obj, "error"):
                _error = result_obj.error
        result_error_time = time.perf_counter() - start_time

        # Test exception success path (no exception)
        def simulate_exception_success() -> str:
            return "success"

        start_time = time.perf_counter()
        for _ in range(iterations):
            try:
                _value = simulate_exception_success()
            except Exception:
                pass
        exception_success_time = time.perf_counter() - start_time

        # Test exception error path
        def simulate_exception_error() -> str:
            raise Exception("test error")

        start_time = time.perf_counter()
        for _ in range(iterations):
            try:
                simulate_exception_error()
            except Exception:
                pass
        exception_error_time = time.perf_counter() - start_time

        print(f"\nError Handling Pattern Performance ({iterations} operations):")
        print(
            f"Result success: {result_success_time:.4f}s ({iterations/result_success_time:.0f} ops/sec)"
        )
        print(
            f"Result error: {result_error_time:.4f}s ({iterations/result_error_time:.0f} ops/sec)"
        )
        print(
            f"Exception success: {exception_success_time:.4f}s ({iterations/exception_success_time:.0f} ops/sec)"
        )
        print(
            f"Exception error: {exception_error_time:.4f}s ({iterations/exception_error_time:.0f} ops/sec)"
        )
        print(f"Result vs Exception (success): {result_success_time/exception_success_time:.2f}x")
        print(f"Result vs Exception (error): {result_error_time/exception_error_time:.2f}x")

        # Result pattern should have reasonable overhead
        assert (
            result_success_time < exception_error_time * 2
        ), "Result success should be faster than exception error"

    def test_vote_totals_creation_performance(self, sample_data: dict[str, Any]) -> None:
        """Benchmark VoteTotals creation and manipulation."""
        iterations = 10000

        # Test VoteTotals creation with correct signature
        start_time = time.perf_counter()
        for _ in range(iterations):
            _vote_totals = VoteTotals(
                approve=5, reject=2, abstain=1, threshold_t=6, snapshot_n=10, remaining_unvoted=3
            )
        creation_time = time.perf_counter() - start_time

        # Test VoteTotals with larger numbers
        start_time = time.perf_counter()
        for _ in range(iterations):
            _vote_totals = VoteTotals(
                approve=100,
                reject=50,
                abstain=25,
                threshold_t=100,
                snapshot_n=200,
                remaining_unvoted=25,
            )
        large_creation_time = time.perf_counter() - start_time

        print(f"\nVoteTotals Creation Performance ({iterations} operations):")
        print(f"Small VoteTotals: {creation_time:.4f}s ({iterations/creation_time:.0f} ops/sec)")
        print(
            f"Large VoteTotals: {large_creation_time:.4f}s ({iterations/large_creation_time:.0f} ops/sec)"
        )

        assert creation_time < 0.5, "VoteTotals creation should be fast"
        assert large_creation_time < 0.5, "Large VoteTotals creation should be fast"

    def test_proposal_data_performance(self, sample_data: dict[str, Any]) -> None:
        """Benchmark Proposal data creation and access."""
        iterations = 1000

        # Test Proposal creation
        start_time = time.perf_counter()
        proposals: list[Proposal] = []
        for i in range(iterations):
            proposal = Proposal(
                proposal_id=uuid4(),
                guild_id=sample_data["guild_id"],
                proposer_id=sample_data["proposer_id"],
                target_id=sample_data["target_id"],
                amount=sample_data["amount"],
                description=f"性能測試提案 {i}",
                attachment_url=None,
                snapshot_n=10,
                threshold_t=sample_data["threshold_t"],
                deadline_at=sample_data["deadline_at"],
                status="進行中",
                reminder_sent=False,
                created_at=sample_data["now"],
                updated_at=sample_data["now"],
            )
            proposals.append(proposal)
        creation_time = time.perf_counter() - start_time

        # Test Proposal access
        start_time = time.perf_counter()
        for proposal in proposals:
            # Access proposal attributes to benchmark attribute access performance
            _ = proposal.proposal_id
            _ = proposal.amount
            _ = proposal.status
            _ = proposal.description
        access_time = time.perf_counter() - start_time

        print(f"\nProposal Data Performance ({iterations} proposals):")
        print(f"Creation: {creation_time:.4f}s ({iterations/creation_time:.0f} ops/sec)")
        print(f"Access (4 fields): {access_time:.4f}s ({iterations*4/access_time:.0f} ops/sec)")

        assert creation_time < 1.0, "Proposal creation should be fast"
        assert access_time < 0.5, "Proposal access should be very fast"

    def test_memory_usage_comparison(self, sample_data: dict[str, Any]) -> None:
        """Compare memory usage between legacy and Result services."""

        objects_count = 1000

        # Test legacy service memory usage
        gc.collect()
        legacy_services: list[CouncilService] = []
        for _ in range(objects_count):
            service = CouncilService()
            legacy_services.append(service)

        legacy_memory = sum(sys.getsizeof(service) for service in legacy_services)

        # Test result service memory usage
        gc.collect()
        result_services: list[CouncilServiceResult] = []
        for _ in range(objects_count):
            service = CouncilServiceResult()
            result_services.append(service)

        result_memory = sum(sys.getsizeof(service) for service in result_services)

        # Test VoteTotals memory usage
        gc.collect()
        vote_totals: list[VoteTotals] = []
        for i in range(objects_count):
            totals = VoteTotals(
                approve=i % 10,
                reject=i % 5,
                abstain=i % 3,
                threshold_t=10,
                snapshot_n=20,
                remaining_unvoted=5,
            )
            vote_totals.append(totals)

        vote_totals_memory = sum(sys.getsizeof(totals) for totals in vote_totals)

        print(f"\nMemory Usage ({objects_count} objects):")
        print(
            f"CouncilService: {legacy_memory / 1024:.2f} KB total, {legacy_memory / objects_count:.1f} bytes per object"
        )
        print(
            f"CouncilServiceResult: {result_memory / 1024:.2f} KB total, {result_memory / objects_count:.1f} bytes per object"
        )
        print(
            f"VoteTotals: {vote_totals_memory / 1024:.2f} KB total, {vote_totals_memory / objects_count:.1f} bytes per object"
        )
        print(f"Service overhead ratio: {result_memory/legacy_memory:.2f}x")

        # Memory usage should be reasonable
        assert legacy_memory / objects_count < 1000, "Legacy service should be memory efficient"
        assert result_memory / objects_count < 1000, "Result service should be memory efficient"
        assert vote_totals_memory / objects_count < 200, "VoteTotals should be memory efficient"

    def test_concurrent_access_simulation(self, sample_data: dict[str, Any]) -> None:
        """Simulate concurrent access patterns for voting operations."""
        iterations = 1000

        # Simulate multiple voters accessing the same proposal

        # Test VoteTotals creation for concurrent updates
        start_time = time.perf_counter()
        for i in range(iterations):
            # Simulate vote processing
            vote_totals = VoteTotals(
                approve=50 + (i % 20),
                reject=25 + (i % 10),
                abstain=10 + (i % 5),
                threshold_t=100,
                snapshot_n=200,
                remaining_unvoted=100 - (i % 30),
            )
            # Simulate status calculation
            total_voted = vote_totals.approve + vote_totals.reject + vote_totals.abstain
            _status = "進行中" if total_voted < vote_totals.threshold_t else "已結束"
        concurrent_time = time.perf_counter() - start_time

        print(f"\nConcurrent Access Simulation ({iterations} operations):")
        print(f"Vote processing: {concurrent_time:.4f}s ({iterations/concurrent_time:.0f} ops/sec)")

        assert concurrent_time < 1.0, "Concurrent vote processing should be fast"


@pytest.mark.skipif(not COUNCIL_AVAILABLE, reason="Council service not available")
class TestCouncilServiceIntegrationBenchmarks:
    """Integration benchmarks for council service with realistic data patterns."""

    def test_proposal_lifecycle_performance(self) -> None:
        """Benchmark complete proposal lifecycle from creation to completion."""
        iterations = 100

        # Simulate proposal lifecycle
        start_time = time.perf_counter()
        for i in range(iterations):
            # 1. Create proposal
            proposal_id = uuid4()
            now = datetime.now(timezone.utc)

            proposal = Proposal(
                proposal_id=proposal_id,
                guild_id=12345,
                proposer_id=11111,
                target_id=22222,
                amount=5000,
                description=f"測試提案 {i}",
                attachment_url=None,
                snapshot_n=10,
                threshold_t=6,
                deadline_at=now + timedelta(days=7),
                status="進行中",
                reminder_sent=False,
                created_at=now,
                updated_at=now,
            )

            # 2. Simulate voting process
            vote_totals = VoteTotals(
                approve=0, reject=0, abstain=0, threshold_t=6, snapshot_n=10, remaining_unvoted=10
            )

            # Simulate 10 votes
            for voter in range(10):
                if voter < 7:  # 7 approve votes
                    vote_totals = VoteTotals(
                        approve=vote_totals.approve + 1,
                        reject=vote_totals.reject,
                        abstain=vote_totals.abstain,
                        threshold_t=vote_totals.threshold_t,
                        snapshot_n=vote_totals.snapshot_n,
                        remaining_unvoted=vote_totals.remaining_unvoted - 1,
                    )
                elif voter < 9:  # 2 reject votes
                    vote_totals = VoteTotals(
                        approve=vote_totals.approve,
                        reject=vote_totals.reject + 1,
                        abstain=vote_totals.abstain,
                        threshold_t=vote_totals.threshold_t,
                        snapshot_n=vote_totals.snapshot_n,
                        remaining_unvoted=vote_totals.remaining_unvoted - 1,
                    )
                else:  # 1 abstain
                    vote_totals = VoteTotals(
                        approve=vote_totals.approve,
                        reject=vote_totals.reject,
                        abstain=vote_totals.abstain + 1,
                        threshold_t=vote_totals.threshold_t,
                        snapshot_n=vote_totals.snapshot_n,
                        remaining_unvoted=vote_totals.remaining_unvoted - 1,
                    )

            # 3. Determine final status
            total_voted = vote_totals.approve + vote_totals.reject + vote_totals.abstain
            if total_voted >= vote_totals.threshold_t:
                if vote_totals.approve > vote_totals.reject:
                    final_status = "已執行"
                else:
                    final_status = "已否決"
            else:
                final_status = "已逾時"

            # Update proposal status
            updated_proposal = Proposal(
                proposal_id=proposal.proposal_id,
                guild_id=proposal.guild_id,
                proposer_id=proposal.proposer_id,
                target_id=proposal.target_id,
                amount=proposal.amount,
                description=proposal.description,
                attachment_url=proposal.attachment_url,
                snapshot_n=proposal.snapshot_n,
                threshold_t=proposal.threshold_t,
                deadline_at=proposal.deadline_at,
                status=final_status,
                reminder_sent=proposal.reminder_sent,
                created_at=proposal.created_at,
                updated_at=datetime.now(timezone.utc),
            )

            # Verify final state
            assert updated_proposal.status in ["已執行", "已否決", "已逾時"]

        lifecycle_time = time.perf_counter() - start_time

        print(f"\nProposal Lifecycle Performance ({iterations} proposals):")
        print(
            f"Complete lifecycle: {lifecycle_time:.4f}s ({iterations/lifecycle_time:.0f} proposals/sec)"
        )
        print(f"Average per proposal: {lifecycle_time/iterations*1000:.2f}ms")

        assert lifecycle_time < 5.0, "Proposal lifecycle should complete in reasonable time"


if __name__ == "__main__":
    # Run benchmarks
    pytest.main([__file__, "-v", "-s"])
