#!/usr/bin/env python3
"""
統一編譯器配置遷移腳本

此腳本將現有的分散配置（mypc.toml, pyproject.toml [tool.mypyc]）遷移到
統一的 [tool.unified-compiler] 配置格式。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
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
        # 如果都沒有，嘗試安裝
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "tomli"])
        import tomli as tomllib_module


class ConfigMigrator:
    """配置遷移器"""

    def __init__(self, project_root: Optional[str] = None):
        """初始化遷移器

        Args:
            project_root: 專案根目錄路徑
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.mypc_config_path = self.project_root / "mypc.toml"
        self.pyproject_path = self.project_root / "pyproject.toml"
        self.backup_dir = self.project_root / "backup/config_migration"

        # 確保備份目錄存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _log(self, level: str, message: str) -> None:
        """記錄日誌"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def _backup_files(self) -> None:
        """備份原始配置文件"""
        self._log("INFO", "備份原始配置文件...")

        backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 備份 mypc.toml
        if self.mypc_config_path.exists():
            backup_mypc = self.backup_dir / f"mypc_{backup_timestamp}.toml"
            shutil.copy2(self.mypc_config_path, backup_mypc)
            self._log("INFO", f"已備份 mypc.toml -> {backup_mypc}")

        # 備份 pyproject.toml
        if self.pyproject_path.exists():
            backup_pyproject = self.backup_dir / f"pyproject_{backup_timestamp}.toml"
            shutil.copy2(self.pyproject_path, backup_pyproject)
            self._log("INFO", f"已備份 pyproject.toml -> {backup_pyproject}")

    def _load_mypc_config(self) -> Dict[str, Any]:
        """載入 mypc.toml 配置"""
        if not self.mypc_config_path.exists():
            self._log("WARNING", "mypc.toml 不存在，跳過 mypc 配置遷移")
            return {}

        try:
            with open(self.mypc_config_path, "r", encoding="utf-8") as f:
                config = tomllib_module.loads(f.read())
                self._log("INFO", "成功載入 mypc.toml 配置")
                return config
        except Exception as e:
            self._log("ERROR", f"載入 mypc.toml 失敗: {e}")
            return {}

    def _load_pyproject_config(self) -> Dict[str, Any]:
        """載入 pyproject.toml 配置"""
        if not self.pyproject_path.exists():
            raise FileNotFoundError(f"pyproject.toml 不存在: {self.pyproject_path}")

        try:
            with open(self.pyproject_path, "r", encoding="utf-8") as f:
                config = tomllib_module.loads(f.read())
                self._log("INFO", "成功載入 pyproject.toml 配置")
                return config
        except Exception as e:
            self._log("ERROR", f"載入 pyproject.toml 失敗: {e}")
            raise

    def _merge_configurations(
        self, mypc_config: Dict[str, Any], pyproject_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """合併配置到統一格式"""
        self._log("INFO", "開始合併配置...")

        unified_config = {}

        # 從 mypc 配置提取基本設置
        if mypc_config:
            mypc_section = mypc_config.get("mypc", {})
            unified_config.update(
                {
                    "default_backend": "mypc",  # mypc.toml 存在時預設使用 mypc
                    "opt_level": mypc_section.get("opt_level", 2),
                    "debug": mypc_section.get("debug", False),
                    "show_warnings": mypc_section.get("show_warnings", True),
                    "cflags": mypc_section.get("cflags", ["-O3", "-march=native"]),
                    "parallel_jobs": 0,  # 新增配置，預設自動檢測
                }
            )

            # 模組配置
            modules_config = mypc_config.get("modules", {})
            unified_config["modules"] = {
                "governance_modules": modules_config.get("governance_modules", []),
                "exclude_modules": modules_config.get("exclude_modules", []),
            }

            # 性能配置
            perf_config = mypc_config.get("performance", {})
            unified_config["performance"] = {
                "target_speedup": perf_config.get("target_speedup", 5.0),
                "memory_efficiency": perf_config.get("memory_efficiency", 0.8),
                "startup_time_target": perf_config.get("startup_time_target", 100),
            }

            # 輸出配置
            output_config = mypc_config.get("output", {})
            unified_config["output"] = {
                "build_dir": output_config.get("build_dir", "build/unified"),
                "keep_intermediate": output_config.get("keep_intermediate", False),
                "generate_profile": output_config.get("generate_profile", True),
                "log_level": output_config.get("log_level", "INFO"),
            }

            # 測試配置
            testing_config = mypc_config.get("testing", {})
            unified_config["testing"] = {
                "auto_test": testing_config.get("auto_test", True),
                "benchmark_tests": testing_config.get("benchmark_tests", []),
                "compatibility_tests": testing_config.get("compatibility_tests", []),
            }

            # 部署配置
            deployment_config = mypc_config.get("deployment", {})
            unified_config["deployment"] = {
                "strategy": deployment_config.get("strategy", "gradual"),
                "keep_python_fallback": deployment_config.get("keep_python_fallback", True),
                "rollback_threshold": deployment_config.get("rollback_threshold", 20),
            }

            # 監控配置
            monitoring_config = mypc_config.get("monitoring", {}) or {}
            unified_config["monitoring"] = {
                "enable_monitoring": monitoring_config.get("enable_monitoring", True),
                "baseline_file": monitoring_config.get(
                    "baseline_file", "build/unified/perf_baseline.json"
                ),
                "regression_threshold_percent": monitoring_config.get(
                    "regression_threshold_percent", 5.0
                ),
                "metrics": monitoring_config.get(
                    "metrics",
                    ["compile_time_seconds", "success_rate", "peak_memory_mb"],
                ),
                "alert_thresholds": monitoring_config.get(
                    "alert_thresholds",
                    {
                        "compile_time_percent": 10.0,
                        "success_rate_percent": 2.0,
                        "peak_memory_mb": 2048.0,
                    },
                ),
            }

        # 從現有 pyproject.toml [tool.mypyc] 提取經濟模組配置
        mypc_config_section = pyproject_config.get("tool", {}).get("mypyc", {})
        if mypc_config_section:
            # 添加經濟模組到模組配置
            if "modules" not in unified_config:
                unified_config["modules"] = {}

            unified_config["modules"]["economy_modules"] = mypc_config_section.get("targets", [])

            # 更新後端配置
            backends_config = {
                "mypyc": {
                    "opt_level": mypc_config_section.get("opt_level", 3),
                    "debug_level": mypc_config_section.get("debug_level", 1),
                    "strict_dunder_typing": mypc_config_section.get("strict_dunder_typing", False),
                    "log_trace": mypc_config_section.get("log_trace", False),
                    "strip_asserts": mypc_config_section.get("opt_level", 3) > 0,
                }
            }

            # 如果有治理模組專用配置
            governance_config = mypc_config_section.get("governance", {})
            if governance_config:
                backends_config["mypc"] = {
                    "opt_level": governance_config.get("opt_level", 2),
                    "debug_level": governance_config.get("debug_level", 0),
                    "strict_dunder_typing": governance_config.get("strict_dunder_typing", True),
                    "log_trace": governance_config.get("log_trace", False),
                }

            unified_config["backends"] = backends_config

        self._log("INFO", "配置合併完成")
        return unified_config

    def _update_pyproject_toml(self, unified_config: Dict[str, Any]) -> None:
        """更新 pyproject.toml 文件"""
        self._log("INFO", "更新 pyproject.toml...")

        try:
            # 載入現有 pyproject.toml
            with open(self.pyproject_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 檢查是否已存在 unified-compiler 配置
            has_unified_config = False
            unified_start_line = None
            unified_end_line = None

            for i, line in enumerate(lines):
                if "[tool.unified-compiler]" in line:
                    has_unified_config = True
                    unified_start_line = i
                elif (
                    unified_start_line is not None
                    and line.startswith("[")
                    and "[tool.unified-compiler" not in line
                ):
                    unified_end_line = i
                    break

            if has_unified_config:
                self._log("WARNING", "pyproject.toml 中已存在 unified-compiler 配置，將覆蓋")
                # 移除現有配置
                if unified_end_line is None:
                    unified_end_line = len(lines)
                del lines[unified_start_line:unified_end_line]

            # 生成新的配置區塊
            config_lines = ["[tool.unified-compiler]\n"]

            # 添加基本配置
            basic_keys = ["default_backend", "opt_level", "debug", "show_warnings", "parallel_jobs"]
            for key in basic_keys:
                if key in unified_config:
                    value = unified_config[key]
                    if isinstance(value, str):
                        config_lines.append(f'{key} = "{value}"\n')
                    else:
                        config_lines.append(f"{key} = {value}\n")

            # 添加 cflags（列表）
            if "cflags" in unified_config:
                config_lines.append(f'cflags = {unified_config["cflags"]}\n')

            # 添加模組配置
            if "modules" in unified_config:
                config_lines.append("\n[tool.unified-compiler.modules]\n")
                modules = unified_config["modules"]

                for module_type in ["economy_modules", "governance_modules", "exclude_modules"]:
                    if module_type in modules and modules[module_type]:
                        config_lines.append(f"{module_type} = {modules[module_type]}\n")

            # 添加後端配置
            if "backends" in unified_config:
                backends = unified_config["backends"]
                for backend_name, backend_config in backends.items():
                    config_lines.append(f"\n[tool.unified-compiler.backends.{backend_name}]\n")
                    for key, value in backend_config.items():
                        if isinstance(value, str):
                            config_lines.append(f'{key} = "{value}"\n')
                        else:
                            config_lines.append(f"{key} = {value}\n")

            # 添加其他配置區塊
            other_sections = ["performance", "output", "testing", "deployment", "monitoring"]
            for section in other_sections:
                if section in unified_config:
                    config_lines.append(f"\n[tool.unified-compiler.{section}]\n")
                    section_config = unified_config[section]
                    for key, value in section_config.items():
                        if isinstance(value, str):
                            config_lines.append(f'{key} = "{value}"\n')
                        elif isinstance(value, dict):
                            # 處理嵌套字典（如 alert_thresholds）
                            config_lines.append(f"{key} = {{ ")
                            for k, v in value.items():
                                if isinstance(v, str):
                                    config_lines.append(f'{k} = "{v}", ')
                                else:
                                    config_lines.append(f"{k} = {v}, ")
                            config_lines.append("}\n")
                        elif isinstance(value, list):
                            config_lines.append(f"{key} = {value}\n")
                        else:
                            config_lines.append(f"{key} = {value}\n")

            # 添加配置到文件末尾
            config_lines.append("\n")

            # 找到插入位置（文件末尾或現有 [tool] 區塊之後）
            insert_position = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].startswith("[tool.") and "unified-compiler" not in lines[i]:
                    insert_position = i + 1
                    break

            # 插入新配置
            lines[insert_position:insert_position] = config_lines

            # 寫回文件
            with open(self.pyproject_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            self._log("SUCCESS", "pyproject.toml 更新完成")

        except Exception as e:
            self._log("ERROR", f"更新 pyproject.toml 失敗: {e}")
            raise

    def _generate_migration_report(
        self, original_configs: Dict[str, Any], unified_config: Dict[str, Any]
    ) -> None:
        """生成遷移報告"""
        self._log("INFO", "生成遷移報告...")

        report = {
            "timestamp": datetime.now().isoformat(),
            "migration_type": "unified-compiler",
            "original_configs": {
                "mypc_toml": bool(original_configs.get("mypc")),
                "pyproject_mypyc": bool(original_configs.get("pyproject_mypyc")),
            },
            "unified_config": unified_config,
            "changes_summary": {
                "total_modules_migrated": (
                    len(unified_config.get("modules", {}).get("economy_modules", []))
                    + len(unified_config.get("modules", {}).get("governance_modules", []))
                ),
                "backends_configured": list(unified_config.get("backends", {}).keys()),
                "configuration_sections": list(unified_config.keys()),
            },
        }

        report_path = self.backup_dir / (
            f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self._log("INFO", f"遷移報告已生成: {report_path}")

    def migrate(self, dry_run: bool = False) -> bool:
        """執行配置遷移

        Args:
            dry_run: 是否為試運行模式（不實際修改文件）

        Returns:
            遷移是否成功
        """
        try:
            self._log("INFO", f"開始{'試運行' if dry_run else ''}配置遷移...")

            # 載入原始配置
            mypc_config = self._load_mypc_config()
            pyproject_config = self._load_pyproject_config()

            original_configs = {
                "mypc": mypc_config,
                "pyproject_mypyc": pyproject_config.get("tool", {}).get("mypyc", {}),
            }

            # 合併配置
            unified_config = self._merge_configurations(mypc_config, pyproject_config)

            if not unified_config:
                self._log("ERROR", "沒有找到可遷移的配置")
                return False

            if dry_run:
                self._log("INFO", "試運行模式 - 以下配置將被遷移到 pyproject.toml:")
                print(json.dumps(unified_config, indent=2, ensure_ascii=False))
                return True

            # 備份文件
            self._backup_files()

            # 更新 pyproject.toml
            self._update_pyproject_toml(unified_config)

            # 生成報告
            self._generate_migration_report(original_configs, unified_config)

            self._log("SUCCESS", "配置遷移完成!")
            self._log("INFO", "建議: 1. 檢查新的 [tool.unified-compiler] 配置")
            self._log("INFO", "      2. 測試新的編譯腳本: python scripts/compile_modules.py test")
            self._log("INFO", "      3. 確認無誤後可刪除 mypc.toml")

            return True

        except Exception as e:
            self._log("ERROR", f"遷移過程發生錯誤: {e}")
            import traceback

            self._log("DEBUG", traceback.format_exc())
            return False


def main() -> None:
    """主函數"""
    parser = argparse.ArgumentParser(description="統一編譯器配置遷移工具")
    parser.add_argument("--dry-run", action="store_true", help="試運行模式，不實際修改文件")
    parser.add_argument("--project-root", help="專案根目錄路徑 (預設: 當前目錄)")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細輸出")

    args = parser.parse_args()

    try:
        migrator = ConfigMigrator(project_root=args.project_root)
        success = migrator.migrate(dry_run=args.dry_run)
        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"錯誤: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
