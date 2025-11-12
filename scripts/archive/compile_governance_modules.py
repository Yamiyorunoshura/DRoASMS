#!/usr/bin/env python3
"""
治理模組 Mypc 編譯腳本

此腳本用於編譯治理模組為 C 擴展，提升系統性能。
支援增量編譯、性能測試和回滾功能。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib as tomllib_module
except ImportError:
    # Python < 3.11 fallback
    try:
        import tomli as tomllib_module
    except ImportError:
        # 如果都沒有，嘗試使用內建的方法或安裝
        import subprocess
        import sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "tomli"])
        import tomli as tomllib_module


class MypcCompiler:
    """Mypc 編譯器管理類 - 向後兼容包裝器"""

    def __init__(self, config_path: str = "mypc.toml", project_root: Optional[str] = None):
        """初始化編譯器

        Args:
            config_path: 配置文件路徑（為向後兼容保留，實際使用統一配置）
            project_root: 專案根目錄路徑
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()

        # 嘗試載入統一配置，如果不存在則回退到舊配置
        try:
            self._load_unified_config()
            print("✅ 使用統一編譯器配置")
        except (ValueError, FileNotFoundError):
            # 回退到舊的 mypc.toml 配置
            self.config_path = self.project_root / config_path
            self.config = self._load_legacy_config()
            self.build_dir = self.project_root / self.config["output"]["build_dir"]
            print("⚠️  回退到舊版 mypc.toml 配置（建議遷移到統一配置）")

        self.backup_dir = self.project_root / "backup/python_modules"

        # 確保目錄存在
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _load_unified_config(self) -> None:
        """載入統一配置文件"""
        pyproject_path = self.project_root / "pyproject.toml"

        with open(pyproject_path, "r", encoding="utf-8") as f:
            config = tomllib_module.loads(f.read())

        unified_config = config.get("tool", {}).get("unified-compiler", {})
        if not unified_config:
            raise ValueError("pyproject.toml 中沒有找到 [tool.unified-compiler] 配置")

        # 將統一配置轉換為舊格式以保持兼容性
        self.config = {
            "mypc": {
                "opt_level": unified_config.get("backends", {}).get("mypc", {}).get("opt_level", 2),
                "debug": not unified_config.get("debug", False),
                "show_warnings": unified_config.get("show_warnings", True),
                "cflags": unified_config.get("cflags", ["-O3", "-march=native"]),
            },
            "modules": {
                "governance_modules": unified_config.get("modules", {}).get(
                    "governance_modules", []
                ),
                "exclude_modules": unified_config.get("modules", {}).get("exclude_modules", []),
            },
            "output": unified_config.get(
                "output",
                {
                    "build_dir": "build/unified",
                    "keep_intermediate": False,
                    "generate_profile": True,
                    "log_level": "INFO",
                },
            ),
            "testing": unified_config.get(
                "testing",
                {
                    "auto_test": True,
                    "benchmark_tests": [],
                    "compatibility_tests": [],
                },
            ),
            "deployment": unified_config.get(
                "deployment",
                {
                    "strategy": "gradual",
                    "keep_python_fallback": True,
                    "rollback_threshold": 20,
                },
            ),
            "monitoring": unified_config.get(
                "monitoring",
                {
                    "enable_monitoring": True,
                    "metrics": [],
                    "alert_thresholds": {},
                },
            ),
        }

        self.build_dir = self.project_root / self.config["output"]["build_dir"]

    def _load_legacy_config(self) -> Dict[str, Any]:
        """載入舊版配置文件"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return tomllib_module.loads(f.read())
        except FileNotFoundError as e:
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}") from e
        except Exception as e:
            raise ValueError(f"配置文件格式錯誤: {e}") from e

    def _log(self, level: str, message: str) -> None:
        """記錄日誌"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def _backup_modules(self) -> None:
        """備份原始 Python 模組"""
        self._log("INFO", "備份原始 Python 模組...")

        modules = self.config["modules"]["governance_modules"]
        for module_path in modules:
            src_path = self.project_root / (module_path.replace(".", "/") + ".py")
            if src_path.exists():
                # 保留目錄結構備份
                rel_path = src_path.relative_to(self.project_root)
                backup_path = self.backup_dir / rel_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, backup_path)
                self._log("DEBUG", f"已備份: {rel_path}")

    def _compile_module(self, module_path: str) -> bool:
        """編譯單個模組"""
        self._log("INFO", f"開始編譯模組: {module_path}")

        src_file = self.project_root / (module_path.replace(".", "/") + ".py")
        if not src_file.exists():
            self._log("ERROR", f"模組文件不存在: {src_file}")
            return False

        try:
            # 導入 mypyc 編譯器
            from mypyc.build import CompilerOptions, mypyc_build

            # 創建編譯選項
            options = CompilerOptions()
            options.target_dir = str(self.build_dir)
            options.verbose = self.config["mypc"].get("show_warnings", False)

            # 設置優化級別
            opt_level = self.config["mypc"]["opt_level"]
            if opt_level == 0:
                options.strip_asserts = False
            elif opt_level >= 1:
                options.strip_asserts = True

            # 執行編譯
            self._log("DEBUG", f"使用 mypyc 編譯器編譯: {module_path}")
            result = mypyc_build([str(src_file)], options)

            # 編譯 C 擴展
            import subprocess
            import sys

            # 切換到 build 目錄並編譯 C 擴展
            c_files = []
            for group in result[1]:
                for c_file in group[0]:
                    if c_file.endswith(".c"):
                        c_files.append(c_file)

            if c_files:
                # 編譯 C 擴展
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
                    compile_cmd, cwd=self.build_dir, capture_output=True, text=True, timeout=300
                )

                if compile_result.returncode != 0:
                    self._log("WARNING", f"C 擴展編譯失敗: {compile_result.stderr}")
                else:
                    self._log("SUCCESS", f"C 擴展編譯成功: {module_path}")

            self._log("SUCCESS", f"模組編譯成功: {module_path}")
            self._log("DEBUG", f"編譯結果: {result}")
            return True

        except ImportError as e:
            self._log("ERROR", f"無法導入 mypyc: {e}")
            self._log("ERROR", "請確保已安裝 mypyc: pip install mypy")
            return False
        except Exception as e:
            self._log("ERROR", f"編譯過程發生錯誤: {e}")
            import traceback

            self._log("DEBUG", traceback.format_exc())
            return False

    def _run_tests(self) -> bool:
        """運行測試套件"""
        self._log("INFO", "運行編譯後測試...")

        # 運行兼容性測試
        compatibility_tests = self.config["testing"]["compatibility_tests"]
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
        benchmark_tests = self.config["testing"]["benchmark_tests"]
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

    def _generate_report(self, compile_results: Dict[str, bool], compile_time: float) -> None:
        """生成編譯報告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "config": self.config,
            "compile_results": compile_results,
            "compile_time_seconds": compile_time,
            "success_rate": sum(compile_results.values()) / len(compile_results),
            "output_directory": str(self.build_dir),
        }

        report_path = self.build_dir / "compile_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self._log("INFO", f"編譯報告已生成: {report_path}")

    def compile_all(self) -> bool:
        """編譯所有配置的模組"""
        start_time = time.time()

        self._log("INFO", "開始編譯治理模組...")
        self._log("INFO", f"配置文件: {self.config_path}")
        self._log("INFO", f"專案根目錄: {self.project_root}")
        self._log("INFO", f"輸出目錄: {self.build_dir}")

        # 備份原始模組
        if self.config["deployment"]["keep_python_fallback"]:
            self._backup_modules()

        # 編譯模組
        modules = self.config["modules"]["governance_modules"]
        compile_results = {}

        for module_path in modules:
            success = self._compile_module(module_path)
            compile_results[module_path] = success

            if not success:
                self._log("WARNING", f"模組編譯失敗，將保留原始 Python 版本: {module_path}")

        # 運行測試
        if self.config["testing"]["auto_test"]:
            test_success = self._run_tests()
            if not test_success:
                self._log("ERROR", "測試失敗，編譯過程中止")
                return False

        # 生成報告
        compile_time = time.time() - start_time
        self._generate_report(compile_results, compile_time)

        success_count = sum(compile_results.values())
        total_count = len(compile_results)

        self._log("INFO", f"編譯完成: {success_count}/{total_count} 模組成功")
        self._log("INFO", f"編譯耗時: {compile_time:.2f} 秒")
        self._log("INFO", f"成功率: {success_count/total_count*100:.1f}%")

        return success_count > 0

    def rollback(self) -> bool:
        """回滾到原始 Python 版本"""
        self._log("INFO", "開始回滾到原始 Python 版本...")

        modules = self.config["modules"]["governance_modules"]
        success_count = 0

        for module_path in modules:
            src_path = self.project_root / (module_path.replace(".", "/") + ".py")
            backup_path = self.backup_dir / (module_path.replace(".", "/") + ".py")

            if backup_path.exists():
                try:
                    shutil.copy2(backup_path, src_path)
                    self._log("SUCCESS", f"已回滾: {module_path}")
                    success_count += 1
                except Exception as e:
                    self._log("ERROR", f"回滾失敗: {module_path}, 錯誤: {e}")
            else:
                self._log("WARNING", f"備份文件不存在: {module_path}")

        total_count = len(modules)
        self._log("INFO", f"回滾完成: {success_count}/{total_count} 模組成功")
        return success_count == total_count

    def clean(self) -> None:
        """清理編譯文件"""
        self._log("INFO", f"清理編譯目錄: {self.build_dir}")
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
            self.build_dir.mkdir(parents=True, exist_ok=True)
        self._log("INFO", "清理完成")


def main() -> None:
    """主函數"""
    parser = argparse.ArgumentParser(description="治理模組 Mypc 編譯工具")
    parser.add_argument(
        "command", choices=["compile", "rollback", "clean", "test"], help="要執行的命令"
    )
    parser.add_argument("--config", default="mypc.toml", help="配置文件路徑 (預設: mypc.toml)")
    parser.add_argument("--project-root", help="專案根目錄路徑 (預設: 當前目錄)")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細輸出")

    args = parser.parse_args()

    try:
        compiler = MypcCompiler(config_path=args.config, project_root=args.project_root)

        if args.command == "compile":
            success = compiler.compile_all()
            sys.exit(0 if success else 1)

        elif args.command == "rollback":
            success = compiler.rollback()
            sys.exit(0 if success else 1)

        elif args.command == "clean":
            compiler.clean()
            sys.exit(0)

        elif args.command == "test":
            success = compiler._run_tests()
            sys.exit(0 if success else 1)

    except Exception as e:
        print(f"錯誤: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
