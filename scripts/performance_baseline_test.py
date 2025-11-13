#!/usr/bin/env python3
"""
性能基線測試工具

用於建立和監控統一編譯前後的性能基線比較
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class PerformanceBaselineTester:
    """性能基線測試器"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.results = []

    def measure_import_time(self, module_path: str) -> float:
        """測量模組導入時間"""
        start_time = time.time()
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"import {module_path}; print('Import successful')"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return time.time() - start_time
            else:
                return -1  # 導入失敗
        except Exception:
            return -1

    def measure_memory_usage(self, module_path: str) -> float:
        """測量模組記憶體使用量（MB）"""
        try:
            code = f"""
import {module_path}
import psutil
import os
process = psutil.Process(os.getpid())
mem_info = process.memory_info()
print(mem_info.rss / 1024 / 1024)  # MB
"""
            result = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                return -1
        except Exception:
            return -1

    def measure_startup_time(self, script_path: str) -> float:
        """測量腳本啟動時間"""
        start_time = time.time()
        try:
            subprocess.run(
                [sys.executable, str(script_path)], capture_output=True, text=True, timeout=30
            )
            return time.time() - start_time
        except Exception:
            return -1

    def run_baseline_test(self, modules: List[str]) -> Dict[str, Any]:
        """執行基線測試"""
        baseline_data = {
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version,
            "modules": {},
        }

        total_import_time = 0
        total_memory = 0
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

        # 計算總體統計
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

    def save_baseline(self, baseline_data: Dict[str, Any], output_path: Path):
        """保存基線數據"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(baseline_data, f, indent=2, ensure_ascii=False)

    def compare_baselines(
        self, baseline1: Dict[str, Any], baseline2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """比較兩個基線測試結果"""
        comparison = {
            "baseline1_timestamp": baseline1["timestamp"],
            "baseline2_timestamp": baseline2["timestamp"],
            "improvements": {},
            "regressions": {},
            "summary": {},
        }

        summary1 = baseline1.get("summary", {})
        summary2 = baseline2.get("summary", {})

        # 比較總體統計
        for metric in ["average_import_time", "total_memory_usage", "average_memory_usage"]:
            val1 = summary1.get(metric, 0)
            val2 = summary2.get(metric, 0)

            if val1 > 0 and val2 > 0:
                change_percent = ((val2 - val1) / val1) * 100
                comparison["summary"][metric] = {
                    "baseline1": val1,
                    "baseline2": val2,
                    "change_percent": change_percent,
                    "improvement": change_percent < 0,
                }

        return comparison


if __name__ == "__main__":
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent
    tester = PerformanceBaselineTester(project_root)

    # 測試模組列表
    test_modules = [
        "src.bot.services.adjustment_service",
        "src.bot.services.transfer_service",
        "src.db.gateway.economy_adjustments",
        "src.db.gateway.council_governance",
        "src.db.gateway.supreme_assembly_governance",
    ]

    print("開始性能基線測試...")
    baseline_data = tester.run_baseline_test(test_modules)

    # 保存基線數據
    output_path = project_root / "build" / "baseline_pre_unification.json"
    tester.save_baseline(baseline_data, output_path)

    print(f"基線測試完成，結果保存至: {output_path}")
    print(f"測試模組數: {len(test_modules)}")
    print(f"成功導入: {baseline_data['summary']['successful_imports']}")
    print(f"平均導入時間: {baseline_data['summary']['average_import_time']:.4f} 秒")
    print(f"總記憶體使用: {baseline_data['summary']['total_memory_usage']:.2f} MB")
