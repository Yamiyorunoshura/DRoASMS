#!/usr/bin/env python3
"""性能基線測試工具。

此腳本會匯入 Cython 目標模組、量測匯入耗時與記憶體、並輸出基線檔案。
所有設定來自 `pyproject.toml` 的 `[tool.cython-compiler]` 區段，可透過 CLI 覆寫。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:  # pragma: no cover - psutil 可能無法在某些平台編譯
    import psutil  # type: ignore
except Exception:  # 錯誤時退回 resource
    psutil = None  # type: ignore

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib

try:  # pragma: no cover - resource 在 Windows 上不可用
    import resource
except ImportError:  # pragma: no cover
    resource = None  # type: ignore


@dataclass(slots=True)
class BaselineConfig:
    modules: List[str]
    output: Path
    pyproject: Path


class PerformanceBaselineTester:
    """性能基線測試器。"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.results: list[dict[str, Any]] = []

    def measure_import_time(self, module_path: str) -> float:
        """測量模組導入時間"""
        start_time = time.time()
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"import {module_path}; print('Import successful')"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return time.time() - start_time if result.returncode == 0 else -1
        except Exception:
            return -1

    def measure_memory_usage(self, module_path: str) -> float:
        """測量模組記憶體使用量（MB）"""
        if psutil is None:
            if resource is None:
                return -1
            usage = resource.getrusage(resource.RUSAGE_SELF)
            # macOS 以 bytes 回傳，Linux 為 KB，透過條件判斷
            rss = getattr(usage, "ru_maxrss", 0)
            if sys.platform == "darwin":
                return rss / 1024 / 1024
            return rss / 1024  # Linux: already KB

        try:
            code = f"""
import {module_path}
import psutil
import os
process = psutil.Process(os.getpid())
mem_info = process.memory_info()
print(mem_info.rss / 1024 / 1024)
"""
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return float(result.stdout.strip()) if result.returncode == 0 else -1
        except Exception:
            return -1

    def run_baseline_test(self, modules: List[str]) -> Dict[str, Any]:
        """執行基線測試"""
        baseline_data: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version,
            "modules": {},
        }

        total_import_time = 0.0
        total_memory = 0.0
        successful_imports = 0

        for module in modules:
            print(f"測試模組: {module}")

            import_time = self.measure_import_time(module)
            memory_usage = self.measure_memory_usage(module)

            module_data = {
                "import_time_seconds": import_time,
                "memory_usage_mb": memory_usage,
                "import_successful": import_time > 0,
            }

            if import_time > 0:
                total_import_time += import_time
                successful_imports += 1
            if memory_usage > 0:
                total_memory += memory_usage

            baseline_data["modules"][module] = module_data

        baseline_data["summary"] = {
            "total_modules": len(modules),
            "successful_imports": successful_imports,
            "average_import_time": (
                total_import_time / successful_imports if successful_imports > 0 else 0
            ),
            "total_memory_usage": total_memory,
            "average_memory_usage": (
                total_memory / successful_imports if successful_imports > 0 else 0
            ),
        }

        return baseline_data

    def save_baseline(self, baseline_data: Dict[str, Any], output_path: Path) -> None:
        """保存基線數據"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(baseline_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _load_modules_from_pyproject(pyproject: Path) -> List[str]:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    compiler = data.get("tool", {}).get("cython-compiler", {})
    targets: Iterable[dict[str, Any]] = compiler.get("targets", [])
    modules = [target["module"] for target in targets if "module" in target]
    if not modules:
        raise ValueError("pyproject.toml 缺少 [tool.cython-compiler.targets] 配置")
    return list(dict.fromkeys(modules))


def _parse_args() -> BaselineConfig:
    parser = argparse.ArgumentParser(description="建立或刷新 Cython 遷移基線")
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/cython/baseline_pre_migration.json"),
        help="輸出檔案路徑",
    )
    parser.add_argument(
        "--module",
        dest="modules",
        action="append",
        help="額外指定要量測的模組，可重複",
    )
    args = parser.parse_args()

    modules = _load_modules_from_pyproject(args.pyproject)
    if args.modules:
        modules.extend(args.modules)

    unique_modules = list(dict.fromkeys(modules))
    return BaselineConfig(modules=unique_modules, output=args.output, pyproject=args.pyproject)


def main() -> None:
    cfg = _parse_args()
    project_root = Path(__file__).parent.parent
    tester = PerformanceBaselineTester(project_root)

    print("開始性能基線測試…")
    baseline_data = tester.run_baseline_test(cfg.modules)
    baseline_data["meta"] = {
        "modules": cfg.modules,
        "pyproject": str(cfg.pyproject),
        "cwd": os.getcwd(),
    }
    tester.save_baseline(baseline_data, cfg.output)

    summary = baseline_data.get("summary", {})
    print(f"基線測試完成，結果保存至: {cfg.output}")
    print(f"測試模組數: {summary.get('total_modules', len(cfg.modules))}")
    print(f"成功導入: {summary.get('successful_imports', 0)}")
    print(f"平均導入時間: {summary.get('average_import_time', 0):.4f} 秒")
    print(f"總記憶體使用: {summary.get('total_memory_usage', 0):.2f} MB")


if __name__ == "__main__":
    main()
