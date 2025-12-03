from __future__ import annotations

import warnings
from typing import Any

import pytest

from src.infra import result_compat
from src.infra.result import DatabaseError, Err, Error, Ok, Result
from src.infra.result_compat import (
    CompatibilityWarning,
    CompatibilityZone,
    MigrationTracker,
    adapt_result_for_exception_code,
    example_compatibility_usage,
    get_migration_report,
    get_migration_state,
    mark_legacy,
    mark_migrated,
    migrate_step1,
    monitor_result_usage,
    result_to_exception,
    wrap_function,
)


@pytest.mark.unit
class TestWrapFunction:
    def test_wrap_function_success_passthrough(self) -> None:
        def add(a: int, b: int) -> int:
            return a + b

        wrapped = wrap_function(add)

        assert wrapped(1, 2) == 3

    def test_wrap_function_exception_raises_generic_exception(self) -> None:
        def boom() -> None:
            raise ValueError("boom")

        wrapped = wrap_function(boom, exceptions=(ValueError,))

        with pytest.raises(Exception) as exc_info:
            wrapped()

        # 透過 Result -> Error -> Exception 轉換後仍保留訊息
        assert "boom" in str(exc_info.value)

    def test_wrap_function_with_error_type_preserves_cause(self) -> None:
        class CausePreservingError(DatabaseError):
            def __init__(self, message: str) -> None:
                super().__init__(message, cause=RuntimeError("inner"))

        def boom() -> None:
            raise ValueError("boom")

        wrapped = wrap_function(boom, exceptions=(ValueError,), error_type=CausePreservingError)

        # error_type 會建立帶有 cause 的 Error，wrap_function 應還原為原始 cause
        with pytest.raises(RuntimeError) as exc_info:
            wrapped()

        assert "inner" in str(exc_info.value)

    def test_wrap_function_emits_warning_after_threshold(self) -> None:
        calls: list[int] = []

        def sometimes_ok(value: int) -> int:
            calls.append(value)
            if value < 0:
                raise ValueError("neg")
            return value

        wrapped = wrap_function(
            sometimes_ok,
            exceptions=(ValueError,),
            warn_after=1,  # 第一次錯誤不警告，第二次之後應警告
        )

        # 第一次錯誤：不應觸發 CompatibilityWarning
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", CompatibilityWarning)
            with pytest.raises(ValueError):
                wrapped(-1)
        assert not any(isinstance(w.message, CompatibilityWarning) for w in caught)

        # 第二次錯誤：應觸發 CompatibilityWarning
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", CompatibilityWarning)
            with pytest.raises(ValueError):
                wrapped(-2)
        assert any(isinstance(w.message, CompatibilityWarning) for w in caught)


@pytest.mark.unit
class TestAdaptResultForExceptionCode:
    def test_adapt_ok_result_returns_value(self) -> None:
        result: Result[int, Error] = Ok(42)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", CompatibilityWarning)
            value = adapt_result_for_exception_code(result)

        assert value == 42
        # 使用相容層時，即便是 Ok 也會發出 CompatibilityWarning，提醒盡快遷移
        assert any(isinstance(w.message, CompatibilityWarning) for w in caught)

    def test_adapt_err_result_raises_cause_if_present(self) -> None:
        err = DatabaseError("bad", cause=RuntimeError("root"))
        result: Result[int, Error] = Err(err)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", CompatibilityWarning)
            with pytest.raises(RuntimeError) as exc_info:
                adapt_result_for_exception_code(result)

        assert "root" in str(exc_info.value)
        assert any(isinstance(w.message, CompatibilityWarning) for w in caught)

    def test_adapt_err_result_raises_generic_exception_without_cause(self) -> None:
        err = DatabaseError("no-cause")
        result: Result[int, Error] = Err(err)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", CompatibilityWarning)
            with pytest.raises(Exception) as exc_info:
                adapt_result_for_exception_code(result)

        assert "no-cause" in str(exc_info.value)
        assert any(isinstance(w.message, CompatibilityWarning) for w in caught)

    def test_result_to_exception_delegates_to_adapter(self) -> None:
        # 確認薄包裝函式不改變語義
        err = DatabaseError("wrapped")
        result: Result[int, Error] = Err(err)

        with pytest.raises(DatabaseError):
            result_to_exception(result)


@pytest.mark.unit
class TestMonitorAndMigrationHelpers:
    def test_monitor_result_usage_increments_counter(self) -> None:
        calls: list[int] = []

        @monitor_result_usage
        def fn(x: int) -> Result[int, Error]:
            calls.append(x)
            return Ok(x * 2)

        first = fn(1)
        second = fn(2)

        assert first.unwrap() == 2
        assert second.unwrap() == 4
        assert calls == [1, 2]

    def test_migrate_step1_decorator_and_direct_call(self) -> None:
        @migrate_step1(exceptions=(ValueError,))
        def decorated(x: int) -> int:
            if x < 0:
                raise ValueError("neg")
            return x

        assert decorated(1) == 1
        with pytest.raises(ValueError):
            decorated(-1)

        # 直接呼叫 migrate_step1(fn) 的語法也應被支援
        def raw(x: int) -> int:
            if x == 0:
                raise ValueError("zero")
            return x * 10

        wrapped = migrate_step1(raw, exceptions=(ValueError,))
        assert wrapped(2) == 20
        with pytest.raises(ValueError):
            wrapped(0)

    def test_migration_tracker_helpers(self) -> None:
        # 先重設全域 migration tracker 狀態
        tracker: Any = result_compat._migration_tracker  # type: ignore[attr-defined]
        tracker.migrated_functions.clear()
        tracker.legacy_functions.clear()
        tracker.compatibility_warnings.clear()

        mark_migrated("foo")
        mark_legacy("bar")

        state = get_migration_state()
        assert state["migrated"] == ["foo"]
        assert state["legacy"] == ["bar"]

        report = get_migration_report()
        assert "Migrated Functions" in report
        assert "Legacy Functions" in report


@pytest.mark.unit
class TestCompatibilityZone:
    def test_compatibility_zone_emits_warning_on_enter(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", CompatibilityWarning)
            with CompatibilityZone("demo"):
                pass

        assert any(isinstance(w.message, CompatibilityWarning) for w in caught)

    def test_compatibility_zone_logs_on_exception(self) -> None:
        # 只需確保 context manager 能處理例外，不會吞掉例外
        with pytest.raises(RuntimeError):
            with CompatibilityZone("demo"):
                raise RuntimeError("boom")


@pytest.mark.unit
class TestMigrationTracker:
    def test_mark_migrated_adds_to_migrated_set(self) -> None:
        tracker = MigrationTracker()
        tracker.mark_migrated("func1")
        tracker.mark_migrated("func2")

        assert "func1" in tracker.migrated_functions
        assert "func2" in tracker.migrated_functions

    def test_mark_migrated_removes_from_legacy(self) -> None:
        tracker = MigrationTracker()
        tracker.mark_legacy("func1")
        assert "func1" in tracker.legacy_functions

        tracker.mark_migrated("func1")
        assert "func1" not in tracker.legacy_functions
        assert "func1" in tracker.migrated_functions

    def test_mark_legacy_adds_to_legacy_set(self) -> None:
        tracker = MigrationTracker()
        tracker.mark_legacy("legacy_func")

        assert "legacy_func" in tracker.legacy_functions

    def test_log_compatibility_warning_appends_to_list(self) -> None:
        tracker = MigrationTracker()
        tracker.log_compatibility_warning("warning1")
        tracker.log_compatibility_warning("warning2")

        assert "warning1" in tracker.compatibility_warnings
        assert "warning2" in tracker.compatibility_warnings

    def test_get_migration_report_no_functions(self) -> None:
        tracker = MigrationTracker()
        report = tracker.get_migration_report()

        assert "No functions tracked yet" in report

    def test_get_migration_report_with_functions(self) -> None:
        tracker = MigrationTracker()
        tracker.mark_migrated("func1")
        tracker.mark_migrated("func2")
        tracker.mark_legacy("legacy1")

        report = tracker.get_migration_report()

        assert "Result Pattern Migration Progress" in report
        assert "func1" in report
        assert "func2" in report
        assert "legacy1" in report
        assert "Migrated Functions" in report
        assert "Legacy Functions" in report
        # 驗證百分比計算（2/3 = 66.7%）
        assert "66.7%" in report

    def test_get_migration_report_with_warnings(self) -> None:
        tracker = MigrationTracker()
        tracker.mark_migrated("func1")
        tracker.mark_legacy("func2")

        # 添加超過10個警告，應該只顯示最後10個
        for i in range(15):
            tracker.log_compatibility_warning(f"warning{i}")

        report = tracker.get_migration_report()

        assert "Compatibility Warnings" in report
        # 最後10個警告應該在報告中
        assert "warning14" in report
        assert "warning5" in report
        # 最早的警告不應該在報告中
        assert "warning0" not in report

    def test_get_state_returns_structured_data(self) -> None:
        tracker = MigrationTracker()
        tracker.mark_migrated("m1")
        tracker.mark_migrated("m2")
        tracker.mark_legacy("l1")
        tracker.log_compatibility_warning("w1")

        state = tracker.get_state()

        assert state["migrated"] == ["m1", "m2"]
        assert state["legacy"] == ["l1"]
        assert state["compatibility_warnings"] == ["w1"]


@pytest.mark.unit
class TestGlobalTrackerHelpers:
    def test_mark_migrated_updates_global_tracker(self) -> None:
        # 重設全域 tracker
        tracker: Any = result_compat._migration_tracker  # type: ignore[attr-defined]
        tracker.migrated_functions.clear()
        tracker.legacy_functions.clear()

        mark_migrated("global_func")

        assert "global_func" in tracker.migrated_functions

    def test_mark_legacy_updates_global_tracker(self) -> None:
        # 重設全域 tracker
        tracker: Any = result_compat._migration_tracker  # type: ignore[attr-defined]
        tracker.migrated_functions.clear()
        tracker.legacy_functions.clear()

        mark_legacy("global_legacy")

        assert "global_legacy" in tracker.legacy_functions

    def test_get_migration_state_returns_global_state(self) -> None:
        # 重設全域 tracker
        tracker: Any = result_compat._migration_tracker  # type: ignore[attr-defined]
        tracker.migrated_functions.clear()
        tracker.legacy_functions.clear()
        tracker.compatibility_warnings.clear()

        mark_migrated("test_func")
        state = get_migration_state()

        assert "test_func" in state["migrated"]

    def test_get_migration_report_returns_global_report(self) -> None:
        # 重設全域 tracker
        tracker: Any = result_compat._migration_tracker  # type: ignore[attr-defined]
        tracker.migrated_functions.clear()
        tracker.legacy_functions.clear()
        tracker.compatibility_warnings.clear()

        mark_migrated("report_func")
        report = get_migration_report()

        assert "report_func" in report


@pytest.mark.unit
class TestCompatibilityWarningClass:
    def test_compatibility_warning_is_user_warning(self) -> None:
        # 確認 CompatibilityWarning 是 UserWarning 的子類
        assert issubclass(CompatibilityWarning, UserWarning)

    def test_compatibility_warning_can_be_raised(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", CompatibilityWarning)
            warnings.warn("test warning", CompatibilityWarning, stacklevel=2)

        assert len(caught) == 1
        assert issubclass(caught[0].category, CompatibilityWarning)


@pytest.mark.unit
class TestExampleUsage:
    def test_example_compatibility_usage_runs_without_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """測試示例函數能夠正確執行"""
        # 這個測試會覆蓋 example_compatibility_usage 函數
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", CompatibilityWarning)
            example_compatibility_usage()

        # 驗證輸出
        captured = capsys.readouterr()
        assert "Compatibility layer examples completed" in captured.out
