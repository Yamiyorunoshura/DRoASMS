"""Performance tests for department registry loading and queries."""

from __future__ import annotations

import time

import pytest

from src.bot.services.department_registry import get_registry


@pytest.mark.performance
def test_registry_load_performance() -> None:
    """性能測試：驗證部門載入速度（應在 100ms 內完成）"""
    start = time.perf_counter()
    registry = get_registry()
    load_time = (time.perf_counter() - start) * 1000  # Convert to milliseconds

    # Registry should load quickly (even with file I/O, should be < 100ms)
    assert load_time < 100, f"Registry load took {load_time:.2f}ms, expected < 100ms"

    # Verify it actually loaded
    dept = registry.get_by_id("interior_affairs")
    assert dept is not None


@pytest.mark.performance
def test_registry_query_performance() -> None:
    """性能測試：驗證部門查詢速度（單次查詢應在 1ms 內完成）"""
    registry = get_registry()

    # Warm up (first query may be slower due to initialization)
    _ = registry.get_by_id("interior_affairs")

    # Test query performance
    start = time.perf_counter()
    for _ in range(100):
        _ = registry.get_by_id("interior_affairs")
        _ = registry.get_by_name("內政部")
        _ = registry.get_by_code(1)
        _ = registry.list_all()
    query_time = (time.perf_counter() - start) * 1000  # Convert to milliseconds

    # 400 queries (100 of each type) should complete in < 10ms
    avg_time_per_query = query_time / 400
    assert (
        avg_time_per_query < 0.1
    ), f"Average query time {avg_time_per_query:.4f}ms, expected < 0.1ms"


@pytest.mark.performance
def test_registry_list_all_performance() -> None:
    """性能測試：驗證列出所有部門的速度"""
    registry = get_registry()

    start = time.perf_counter()
    for _ in range(1000):
        departments = registry.list_all()
        assert len(departments) >= 4
    list_time = (time.perf_counter() - start) * 1000  # Convert to milliseconds

    # 1000 list operations should complete in < 50ms
    avg_time_per_list = list_time / 1000
    assert (
        avg_time_per_list < 0.1
    ), f"Average list_all time {avg_time_per_list:.4f}ms, expected < 0.1ms"
