import json
from pathlib import Path

from scripts.compile_modules import PerformanceMonitor


def _build_monitor(tmp_path, extra_config=None):
    cfg = {
        "enable_monitoring": True,
        "baseline_file": str(tmp_path / "baseline.json"),
        "alert_thresholds": {
            "compile_time_percent": 5.0,
            "success_rate_percent": 2.0,
            "peak_memory_mb": 256.0,
        },
    }
    if extra_config:
        cfg.update(extra_config)
    return PerformanceMonitor(cfg, tmp_path, tmp_path)


def test_performance_monitor_creates_baseline(tmp_path):
    monitor = _build_monitor(tmp_path)
    monitor._get_peak_memory_mb = lambda: 128.0  # type: ignore[attr-defined]

    snapshot = monitor.build_snapshot(
        compile_time=4.2,
        compile_results={"module_a": True, "module_b": True},
        parallel_jobs=2,
    )

    result = monitor.evaluate(snapshot)

    assert result["baseline_created"] is True
    assert Path(tmp_path / "baseline.json").exists()
    stored = json.loads(Path(tmp_path / "baseline.json").read_text(encoding="utf-8"))
    assert stored["metrics"]["compile_time_seconds"] == snapshot["metrics"]["compile_time_seconds"]


def test_performance_monitor_detects_regressions_and_alerts(tmp_path):
    monitor = _build_monitor(tmp_path)
    baseline = {
        "timestamp": "2024-12-01T00:00:00",
        "metrics": {
            "compile_time_seconds": 5.0,
            "success_rate": 1.0,
            "peak_memory_mb": 100.0,
        },
        "context": {},
    }
    monitor._write_baseline(baseline)  # type: ignore[attr-defined]
    monitor._get_peak_memory_mb = lambda: 600.0  # type: ignore[attr-defined]

    snapshot = monitor.build_snapshot(
        compile_time=6.5,
        compile_results={"module_a": True, "module_b": False},
        parallel_jobs=1,
    )
    snapshot["metrics"]["success_rate"] = 0.5

    result = monitor.evaluate(snapshot)

    regression_metrics = {entry["metric"] for entry in result["regressions"]}
    assert "compile_time_seconds" in regression_metrics
    assert "success_rate" in regression_metrics

    alert_metrics = {entry["metric"] for entry in result["alerts"]}
    assert "peak_memory_mb" in alert_metrics


def test_performance_monitor_refreshes_baseline(tmp_path):
    monitor = _build_monitor(tmp_path)
    initial = {
        "timestamp": "2024-12-01T00:00:00",
        "metrics": {
            "compile_time_seconds": 8.0,
            "success_rate": 0.9,
            "peak_memory_mb": 300.0,
        },
        "context": {},
    }
    monitor._write_baseline(initial)  # type: ignore[attr-defined]
    monitor._get_peak_memory_mb = lambda: 150.0  # type: ignore[attr-defined]

    snapshot = monitor.build_snapshot(
        compile_time=5.5,
        compile_results={"module_a": True, "module_b": True},
        parallel_jobs=4,
    )
    snapshot["metrics"]["success_rate"] = 0.95

    result = monitor.evaluate(snapshot, allow_refresh=True)

    assert result["baseline_refreshed"] is True
    stored = json.loads(Path(tmp_path / "baseline.json").read_text(encoding="utf-8"))
    assert stored["metrics"]["compile_time_seconds"] == snapshot["metrics"]["compile_time_seconds"]
