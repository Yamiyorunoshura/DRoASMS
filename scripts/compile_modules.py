#!/usr/bin/env python3
"""
統一模組編譯腳本

此腳本提供統一的介面來編譯不同類型的模組（經濟模組使用 mypyc，治理模組使用 mypc），
支援並行編譯、性能監控、自動回滾等功能。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    import tomllib as tomllib_module
except ImportError:
    # Python < 3.11 fallback
    try:
        import tomli as tomllib_module
    except ImportError:
        import subprocess
        import sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "tomli"])
        import tomli as tomllib_module

try:
    import resource
except ImportError:  # pragma: no cover - Windows 平台沒 resource 模組
    resource = None  # type: ignore


_RUNTIME_SYNCED_DIRS: Set[Path] = set()


def _set_compiler_option(options: Any, attr_names: Iterable[str], value: Any, desc: str) -> None:
    """嘗試設定 CompilerOptions 的屬性，兼容不同 mypyc 版本。"""

    for attr in attr_names:
        if hasattr(options, attr):
            setattr(options, attr, value)
            return

    print(f"警告: 當前 CompilerOptions 不支援 {desc} 設定，已忽略。")


def _ensure_mypyc_runtime_files(target_dir: Path) -> None:
    """確保 mypyc 執行期輔助檔案存在於輸出目錄。"""

    resolved = target_dir.resolve()
    if resolved in _RUNTIME_SYNCED_DIRS:
        return

    try:
        from importlib import resources

        rt_root = resources.files("mypyc") / "lib-rt"
    except Exception as exc:  # pragma: no cover - fallback 訊息
        print(f"警告: 無法同步 mypyc runtime 檔案: {exc}")
        return

    for entry in rt_root.iterdir():
        if entry.is_file():
            shutil.copy2(entry, resolved / entry.name)

    _RUNTIME_SYNCED_DIRS.add(resolved)


class CompilationBackend(ABC):
    """編譯後端抽象基類"""

    def __init__(self, config: Dict[str, Any], project_root: Path):
        self.config = config
        self.project_root = project_root

    @abstractmethod
    def compile_module(self, module_path: str, build_dir: Path) -> bool:
        """編譯單個模組

        Args:
            module_path: 模組路徑（點分隔格式）
            build_dir: 編譯輸出目錄

        Returns:
            編譯是否成功
        """
        pass

    @abstractmethod
    def get_backend_name(self) -> str:
        """獲取後端名稱"""
        pass


class MypycBackend(CompilationBackend):
    """Mypyc 編譯後端"""

    def get_backend_name(self) -> str:
        return "mypyc"

    def compile_module(self, module_path: str, build_dir: Path) -> bool:
        """使用 mypyc 編譯模組"""
        try:
            # 導入 mypyc 編譯器
            from mypyc.build import CompilerOptions, mypyc_build

            src_file = self.project_root / (module_path.replace(".", "/") + ".py")
            if not src_file.exists():
                print(f"錯誤: 模組文件不存在: {src_file}")
                return False

            _ensure_mypyc_runtime_files(build_dir)

            # 創建編譯選項
            options = CompilerOptions()
            options.target_dir = str(build_dir)
            options.verbose = self.config.get("show_warnings", False)
            options.include_runtime_files = True

            # 設置優化級別
            opt_level = self.config.get("opt_level", 3)
            if opt_level == 0:
                options.strip_asserts = False
            elif opt_level >= 1:
                options.strip_asserts = True

            # 設置調試級別
            debug_level = self.config.get("debug_level", 1)
            _set_compiler_option(options, ("debug", "log_trace"), debug_level > 0, "debug")

            # 執行編譯
            print(f"使用 mypyc 編譯器編譯: {module_path}")
            result = mypyc_build([str(src_file)], options)

            # 編譯 C 擴展
            return self._compile_c_extension(module_path, result, build_dir)

        except ImportError as e:
            print(f"錯誤: 無法導入 mypyc: {e}")
            print("請確保已安裝 mypyc: pip install mypy")
            return False
        except Exception as e:
            print(f"錯誤: mypyc 編譯過程發生錯誤: {e}")
            import traceback

            print(traceback.format_exc())
            return False

    def _compile_c_extension(self, module_path: str, mypyc_result: Any, build_dir: Path) -> bool:
        """編譯 C 擴展"""
        try:
            # 提取 C 文件
            c_files = []
            for group in mypyc_result[1]:
                for c_file in group[0]:
                    if c_file.endswith(".c"):
                        c_files.append(c_file)

            if not c_files:
                print(f"警告: 沒有生成 C 文件: {module_path}")
                return True

            # 編譯 C 擴展
            include_dir = str(build_dir)

            compile_cmd = [
                sys.executable,
                "-c",
                f"""
import setuptools
from setuptools import setup, Extension
import sys

extension = Extension(
    'native_{module_path.replace(".", "_")}',
    sources={c_files},
    include_dirs=['{include_dir}'],
    extra_compile_args=['-O3', '-march=native']
)

setup(
    name='native_{module_path.replace(".", "_")}',
    version='1.0.0',
    ext_modules=[extension],
    script_args=['build_ext', '--inplace']
)
""",
            ]

            compile_result = subprocess.run(
                compile_cmd, cwd=build_dir, capture_output=True, text=True, timeout=300
            )

            if compile_result.returncode != 0:
                print(f"警告: C 擴展編譯失敗: {compile_result.stderr}")
                return False
            else:
                print(f"成功: C 擴展編譯成功: {module_path}")
                return True

        except Exception as e:
            print(f"錯誤: C 擴展編譯失敗: {e}")
            return False


class MypcBackend(CompilationBackend):
    """Mypc 編譯後端（基於現有的治理模組編譯邏輯）"""

    def get_backend_name(self) -> str:
        return "mypc"

    def compile_module(self, module_path: str, build_dir: Path) -> bool:
        """使用 mypc 編譯模組（實際上使用 mypyc，但應用 mypc 配置）"""
        try:
            # 導入 mypyc 編譯器
            from mypyc.build import CompilerOptions, mypyc_build

            src_file = self.project_root / (module_path.replace(".", "/") + ".py")
            if not src_file.exists():
                print(f"錯誤: 模組文件不存在: {src_file}")
                return False

            _ensure_mypyc_runtime_files(build_dir)

            # 創建編譯選項（使用 mypc 配置）
            options = CompilerOptions()
            options.target_dir = str(build_dir)
            options.verbose = self.config.get("show_warnings", False)
            options.include_runtime_files = True

            # 設置優化級別（mypc 配置）
            opt_level = self.config.get("opt_level", 2)
            if opt_level == 0:
                options.strip_asserts = False
            elif opt_level >= 1:
                options.strip_asserts = True

            # 設置調試級別
            debug_level = self.config.get("debug_level", 0)
            _set_compiler_option(options, ("debug", "log_trace"), debug_level > 0, "debug")

            # 設置嚴格的 dunder typing（治理模組特有）
            if self.config.get("strict_dunder_typing", False):
                _set_compiler_option(
                    options,
                    ("strict_dunder", "strict_dunders_typing"),
                    True,
                    "strict dunder typing",
                )

            # 執行編譯
            print(f"使用 mypc 配置編譯模組: {module_path}")
            result = mypyc_build([str(src_file)], options)

            # 編譯 C 擴展
            return self._compile_c_extension(module_path, result, build_dir)

        except ImportError as e:
            print(f"錯誤: 無法導入 mypyc: {e}")
            print("請確保已安裝 mypyc: pip install mypy")
            return False
        except Exception as e:
            print(f"錯誤: mypc 編譯過程發生錯誤: {e}")
            import traceback

            print(traceback.format_exc())
            return False

    def _compile_c_extension(self, module_path: str, mypyc_result: Any, build_dir: Path) -> bool:
        """編譯 C 擴展（mypc 版本）"""
        try:
            # 提取 C 文件
            c_files = []
            for group in mypyc_result[1]:
                for c_file in group[0]:
                    if c_file.endswith(".c"):
                        c_files.append(c_file)

            if not c_files:
                print(f"警告: 沒有生成 C 文件: {module_path}")
                return True

            # 編譯 C 擴展（使用治理模組特定的編譯選項）
            include_dir = str(build_dir)

            compile_cmd = [
                sys.executable,
                "-c",
                f"""
import setuptools
from setuptools import setup, Extension
import sys

extension = Extension(
    'native_{module_path.replace(".", "_")}',
    sources={c_files},
    include_dirs=['{include_dir}'],
    extra_compile_args=['-O3', '-march=native']
)

setup(
    name='native_{module_path.replace(".", "_")}',
    version='1.0.0',
    ext_modules=[extension],
    script_args=['build_ext', '--inplace']
)
""",
            ]

            compile_result = subprocess.run(
                compile_cmd, cwd=build_dir, capture_output=True, text=True, timeout=300
            )

            if compile_result.returncode != 0:
                print(f"警告: C 擴展編譯失敗: {compile_result.stderr}")
                return False
            else:
                print(f"成功: C 擴展編譯成功: {module_path}")
                return True

        except Exception as e:
            print(f"錯誤: C 擴展編譯失敗: {e}")
            return False


class PerformanceMonitor:
    """Performance baseline/監控邏輯"""

    LOWER_IS_BETTER: Set[str] = {"compile_time_seconds", "peak_memory_mb"}

    def __init__(self, config: Dict[str, Any], build_dir: Path, project_root: Path):
        self.enabled = config.get("enable_monitoring", False)
        baseline_path = config.get("baseline_file")
        resolved_baseline = (
            Path(baseline_path) if baseline_path else build_dir / "perf_baseline.json"
        )
        if not resolved_baseline.is_absolute():
            resolved_baseline = (project_root / resolved_baseline).resolve()
        self.baseline_path = resolved_baseline
        self.threshold_percent = float(config.get("regression_threshold_percent", 5.0))
        self.metrics = config.get(
            "metrics",
            ["compile_time_seconds", "success_rate", "peak_memory_mb"],
        )
        thresholds = config.get("alert_thresholds", {})
        self.percent_thresholds = {
            key[:-8]: float(value)
            for key, value in thresholds.items()
            if key.endswith("_percent") and len(key) > 8
        }
        self.absolute_thresholds = {
            key: float(value) for key, value in thresholds.items() if not key.endswith("_percent")
        }

    def build_snapshot(
        self,
        compile_time: float,
        compile_results: Dict[str, bool],
        parallel_jobs: int,
    ) -> Dict[str, Any]:
        """建立一次編譯的性能快照"""
        total_count = len(compile_results)
        success_count = sum(compile_results.values())
        success_rate = (success_count / total_count) if total_count else 0.0
        failed_modules = [module for module, status in compile_results.items() if not status]

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "compile_time_seconds": round(compile_time, 3),
                "success_rate": round(success_rate, 4),
                "peak_memory_mb": self._get_peak_memory_mb(),
            },
            "context": {
                "total_modules": total_count,
                "failed_modules": failed_modules,
                "parallel_jobs": parallel_jobs if parallel_jobs else 1,
            },
        }
        return snapshot

    def evaluate(self, snapshot: Dict[str, Any], allow_refresh: bool = False) -> Dict[str, Any]:
        """比較基線並回報回歸/警示"""
        result: Dict[str, Any] = {
            "baseline_created": False,
            "baseline_refreshed": False,
            "regressions": [],
            "alerts": [],
            "baseline_path": str(self.baseline_path),
        }

        if not self.enabled:
            return result

        baseline = self._load_baseline()
        if baseline is None:
            self._write_baseline(snapshot)
            result["baseline_created"] = True
        else:
            regressions = self._find_regressions(baseline, snapshot)
            result["regressions"] = regressions
            if not regressions and allow_refresh:
                self._write_baseline(snapshot)
                result["baseline_refreshed"] = True

        result["alerts"] = self._detect_alerts(snapshot)
        return result

    def _get_peak_memory_mb(self) -> float:
        """取得 ru_maxrss 轉換後的 MB"""
        if resource is None:  # pragma: no cover - Windows 不支援
            return 0.0
        usage = resource.getrusage(resource.RUSAGE_SELF)
        peak_kb = usage.ru_maxrss
        if sys.platform == "darwin":
            peak_bytes = peak_kb
        else:
            peak_bytes = peak_kb * 1024
        return round(peak_bytes / (1024 * 1024), 3)

    def _load_baseline(self) -> Optional[Dict[str, Any]]:
        if not self.baseline_path.exists():
            return None
        try:
            with open(self.baseline_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            return None

    def _write_baseline(self, snapshot: Dict[str, Any]) -> None:
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.baseline_path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, indent=2, ensure_ascii=False)

    def _find_regressions(
        self,
        baseline: Dict[str, Any],
        snapshot: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        regressions: List[Dict[str, Any]] = []
        baseline_metrics = baseline.get("metrics", {})
        current_metrics = snapshot.get("metrics", {})

        for metric in self.metrics:
            baseline_value = baseline_metrics.get(metric)
            current_value = current_metrics.get(metric)
            if baseline_value in (None, 0) or current_value is None:
                continue

            change_percent = ((current_value - baseline_value) / baseline_value) * 100
            threshold = self.percent_thresholds.get(metric, self.threshold_percent)

            if metric in self.LOWER_IS_BETTER:
                degraded = change_percent > threshold
            else:
                degraded = (-change_percent) > threshold

            if degraded:
                regressions.append(
                    {
                        "metric": metric,
                        "baseline": baseline_value,
                        "current": current_value,
                        "change_percent": round(change_percent, 2),
                        "threshold_percent": threshold,
                    }
                )

        return regressions

    def _detect_alerts(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        metrics = snapshot.get("metrics", {})

        for metric, limit in self.absolute_thresholds.items():
            current_value = metrics.get(metric)
            if current_value is None:
                continue

            if metric in self.LOWER_IS_BETTER:
                breach = current_value > limit
            else:
                breach = current_value < limit

            if breach:
                alerts.append(
                    {
                        "metric": metric,
                        "current": current_value,
                        "limit": limit,
                        "type": "absolute",
                    }
                )

        return alerts


class UnifiedCompiler:
    """統一編譯器"""

    def __init__(self, project_root: Optional[str] = None, refresh_baseline: bool = False):
        """初始化編譯器

        Args:
            project_root: 專案根目錄路徑
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.pyproject_path = self.project_root / "pyproject.toml"
        self.config = self._load_config()
        self.build_dir = self.project_root / self.config["output"]["build_dir"]
        self.backup_dir = self.project_root / "backup/python_modules"
        self.refresh_baseline = refresh_baseline

        # 初始化編譯後端
        self.backends = self._init_backends()
        self.monitor = PerformanceMonitor(
            self.config.get("monitoring", {}),
            self.build_dir,
            self.project_root,
        )

        # 確保目錄存在
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        """載入統一配置文件"""
        try:
            with open(self.pyproject_path, "r", encoding="utf-8") as f:
                config = tomllib_module.loads(f.read())

            unified_config = config.get("tool", {}).get("unified-compiler", {})
            if not unified_config:
                raise ValueError("pyproject.toml 中沒有找到 [tool.unified-compiler] 配置")

            print("成功載入統一編譯器配置")
            return unified_config

        except FileNotFoundError as e:
            raise FileNotFoundError(f"配置文件不存在: {self.pyproject_path}") from e
        except Exception as e:
            raise ValueError(f"配置文件格式錯誤: {e}") from e

    def _init_backends(self) -> Dict[str, CompilationBackend]:
        """初始化編譯後端"""
        backends = {}
        backends_config = self.config.get("backends", {})

        # 初始化 mypyc 後端
        mypc_config = backends_config.get("mypyc", {})
        backends["mypyc"] = MypycBackend(mypc_config, self.project_root)

        # 初始化 mypc 後端
        mypc_config = backends_config.get("mypc", {})
        backends["mypc"] = MypcBackend(mypc_config, self.project_root)

        print(f"已初始化編譯後端: {list(backends.keys())}")
        return backends

    def _detect_module_type(self, module_path: str) -> str:
        """檢測模組類型"""
        modules_config = self.config.get("modules", {})

        if module_path in modules_config.get("economy_modules", []):
            return "mypyc"
        elif module_path in modules_config.get("governance_modules", []):
            return "mypc"
        else:
            # 自動檢測：根據模組路徑判斷
            if "bot.services" in module_path or "economy" in module_path:
                return "mypyc"
            elif (
                "governance" in module_path or "council" in module_path or "assembly" in module_path
            ):
                return "mypc"
            else:
                # 使用預設後端
                return self.config.get("default_backend", "mypyc")

    def _log(self, level: str, message: str) -> None:
        """記錄日誌"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def _backup_modules(self, module_paths: List[str]) -> None:
        """備份原始 Python 模組"""
        self._log("INFO", "備份原始 Python 模組...")

        for module_path in module_paths:
            src_path = self.project_root / (module_path.replace(".", "/") + ".py")
            if src_path.exists():
                # 保留目錄結構備份
                rel_path = src_path.relative_to(self.project_root)
                backup_path = self.backup_dir / rel_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, backup_path)
                self._log("DEBUG", f"已備份: {rel_path}")

    def _compile_single_module(self, module_path: str) -> Tuple[str, bool]:
        """編譯單個模組（用於並行編譯）

        Args:
            module_path: 模組路徑

        Returns:
            (模組路徑, 編譯是否成功)
        """
        try:
            # 檢測模組類型
            backend_name = self._detect_module_type(module_path)
            backend = self.backends[backend_name]

            self._log("INFO", f"編譯模組: {module_path} (使用 {backend_name} 後端)")

            # 編譯模組
            success = backend.compile_module(module_path, self.build_dir)

            if success:
                self._log("SUCCESS", f"模組編譯成功: {module_path}")
            else:
                self._log("ERROR", f"模組編譯失敗: {module_path}")

            return module_path, success

        except Exception as e:
            self._log("ERROR", f"編譯模組 {module_path} 時發生錯誤: {e}")
            return module_path, False

    def _run_tests(self) -> bool:
        """運行測試套件"""
        if not self.config.get("testing", {}).get("auto_test", True):
            return True

        self._log("INFO", "運行編譯後測試...")

        testing_config = self.config.get("testing", {})

        # 運行兼容性測試
        compatibility_tests = testing_config.get("compatibility_tests", [])
        for test_path in compatibility_tests:
            full_test_path = self.project_root / test_path
            if full_test_path.exists():
                self._log("DEBUG", f"運行兼容性測試: {test_path}")
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", test_path, "-v"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self._log("ERROR", f"兼容性測試失敗: {test_path}")
                    self._log("ERROR", result.stderr)
                    return False

        # 運行性能基準測試
        benchmark_tests = testing_config.get("benchmark_tests", [])
        for test_path in benchmark_tests:
            full_test_path = self.project_root / test_path
            if full_test_path.exists():
                self._log("DEBUG", f"運行性能基準測試: {test_path}")
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", test_path, "-v", "-s"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self._log("WARNING", f"性能測試失敗: {test_path}")
                    # 性能測試失敗不應該阻止部署，但需要警告
                    self._log("WARNING", result.stderr)

        self._log("SUCCESS", "所有測試通過")
        return True

    def _generate_report(
        self,
        compile_results: Dict[str, bool],
        compile_time: float,
        performance_snapshot: Dict[str, Any],
        monitor_result: Dict[str, Any],
    ) -> None:
        """生成編譯報告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "config": self.config,
            "compile_results": compile_results,
            "compile_time_seconds": compile_time,
            "success_rate": (
                sum(compile_results.values()) / len(compile_results) if compile_results else 0
            ),
            "output_directory": str(self.build_dir),
            "backends_used": list(self.backends.keys()),
            "performance": performance_snapshot,
            "monitoring": monitor_result,
        }

        report_path = self.build_dir / "compile_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self._log("INFO", f"編譯報告已生成: {report_path}")

    def compile_all(self) -> bool:
        """編譯所有配置的模組"""
        start_time = time.time()

        self._log("INFO", "開始統一模組編譯...")
        self._log("INFO", f"專案根目錄: {self.project_root}")
        self._log("INFO", f"輸出目錄: {self.build_dir}")

        # 收集所有模組
        modules_config = self.config.get("modules", {})
        all_modules = []

        # 添加經濟模組
        all_modules.extend(modules_config.get("economy_modules", []))

        # 添加治理模組
        all_modules.extend(modules_config.get("governance_modules", []))

        if not all_modules:
            self._log("WARNING", "沒有找到要編譯的模組")
            return True

        # 排除指定模組
        exclude_modules = modules_config.get("exclude_modules", [])
        all_modules = [m for m in all_modules if m not in exclude_modules]

        self._log("INFO", f"找到 {len(all_modules)} 個模組需要編譯")

        # 備份原始模組
        if self.config.get("deployment", {}).get("keep_python_fallback", True):
            self._backup_modules(all_modules)

        # 並行編譯模組
        parallel_jobs = self.config.get("parallel_jobs", 0)
        compile_results = {}

        if parallel_jobs and parallel_jobs > 1:
            self._log("INFO", f"使用 {parallel_jobs} 條工作線程進行並行編譯")
            with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
                future_to_module = {
                    executor.submit(self._compile_single_module, module_path): module_path
                    for module_path in all_modules
                }

                for future in as_completed(future_to_module):
                    module_path, success = future.result()
                    compile_results[module_path] = success
        else:
            if parallel_jobs != 0:
                self._log("INFO", "強制改為單線程編譯以避免 mypyc 執行緒安全問題")
            for module_path in all_modules:
                module_path, success = self._compile_single_module(module_path)
                compile_results[module_path] = success

        # 運行測試
        if not self._run_tests():
            self._log("ERROR", "測試失敗，編譯過程中止")
            return False

        # 生成報告與性能監控
        compile_time = time.time() - start_time
        success_count = sum(compile_results.values())
        total_count = len(compile_results)

        performance_snapshot = self.monitor.build_snapshot(
            compile_time, compile_results, parallel_jobs
        )
        monitor_result = self.monitor.evaluate(
            performance_snapshot,
            allow_refresh=self.refresh_baseline and success_count == total_count,
        )

        self._generate_report(compile_results, compile_time, performance_snapshot, monitor_result)

        success_rate_pct = (success_count / total_count * 100) if total_count else 0.0

        self._log("INFO", f"編譯完成: {success_count}/{total_count} 模組成功")
        self._log("INFO", f"編譯耗時: {compile_time:.2f} 秒")
        self._log("INFO", f"成功率: {success_rate_pct:.1f}%")

        if monitor_result.get("baseline_created"):
            self._log("INFO", f"首次建立性能基線: {monitor_result['baseline_path']}")
        if monitor_result.get("baseline_refreshed"):
            self._log("INFO", f"已刷新性能基線: {monitor_result['baseline_path']}")

        for alert in monitor_result.get("alerts", []):
            self._log(
                "WARNING",
                f"性能警示 - {alert['metric']}: 目前 {alert['current']} (閾值 {alert['limit']})",
            )

        for regression in monitor_result.get("regressions", []):
            self._log(
                "ERROR",
                (
                    f"性能回歸 - {regression['metric']}: "
                    f"基線 {regression['baseline']}, "
                    f"目前 {regression['current']} "
                    f"(變動 {regression['change_percent']}% / 閾值 "
                    f"{regression['threshold_percent']}%)"
                ),
            )

        success = success_count == total_count and not monitor_result.get("regressions")
        if not success and monitor_result.get("regressions"):
            self._log("ERROR", "偵測到性能回歸，請檢查 build/unified/compile_report.json")

        return success


def main() -> None:
    """主函數"""
    parser = argparse.ArgumentParser(description="統一模組編譯工具")
    parser.add_argument("command", choices=["compile", "test", "clean"], help="要執行的命令")
    parser.add_argument("--project-root", help="專案根目錄路徑 (預設: 當前目錄)")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細輸出")
    parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="編譯成功後刷新性能監控基線",
    )

    args = parser.parse_args()

    try:
        compiler = UnifiedCompiler(
            project_root=args.project_root, refresh_baseline=args.refresh_baseline
        )

        if args.command == "compile":
            success = compiler.compile_all()
            sys.exit(0 if success else 1)

        elif args.command == "test":
            success = compiler._run_tests()
            sys.exit(0 if success else 1)

        elif args.command == "clean":
            # 清理編譯文件
            if compiler.build_dir.exists():
                shutil.rmtree(compiler.build_dir)
                compiler.build_dir.mkdir(parents=True, exist_ok=True)
            print("清理完成")
            sys.exit(0)

    except Exception as e:
        print(f"錯誤: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
