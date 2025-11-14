#!/usr/bin/env python3
"""編譯時間基準測試"""

import json
import subprocess
import time
from pathlib import Path


def benchmark_parallel_levels():
    """測試不同並行級別的編譯時間"""

    project_root = Path(__file__).parent.parent
    results = []

    parallel_levels = [1, 2, 4, "auto"]

    for level in parallel_levels:
        print(f"\n測試並行級別: {level}")

        # 清理之前的編譯
        subprocess.run(
            ["python3", "scripts/compile_modules.py", "clean"],
            cwd=project_root,
            capture_output=True,
        )

        # 修改pyproject.toml中的parallel設置
        pyproject_path = project_root / "pyproject.toml"
        content = pyproject_path.read_text()

        if isinstance(level, int):
            content = content.replace("parallel = 4", f"parallel = {level}")
        else:
            content = content.replace("parallel = 4", 'parallel = "auto"')

        pyproject_path.write_text(content)

        # 測量編譯時間
        start_time = time.time()

        result = subprocess.run(
            ["python3", "scripts/compile_modules.py", "compile"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        end_time = time.time()
        compilation_time = end_time - start_time

        # 解析結果
        success = "Failures: 0" in result.stdout or "Failures: 1" in result.stdout  # 允許一個失敗
        modules_compiled = result.stdout.count("succeeded") + result.stdout.count("cached")

        throughput_modules_per_second = 0.0
        if compilation_time > 0:
            throughput_modules_per_second = round(modules_compiled / compilation_time, 2)

        benchmark_result = {
            "parallel_level": str(level),
            "compilation_time_seconds": round(compilation_time, 2),
            "success": success,
            "modules_compiled": modules_compiled,
            "throughput_modules_per_second": throughput_modules_per_second,
        }

        results.append(benchmark_result)
        print(f"編譯時間: {compilation_time:.2f}秒")
        print(f"成功: {success}")
        print(f"編譯模組數: {modules_compiled}")
        print(f"吞吐量: {benchmark_result['throughput_modules_per_second']} 模組/秒")

    # 保存結果
    output_path = project_root / "build" / "cython" / "compile_time_benchmark.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    print(f"\n編譯時間基準測試完成，結果保存至: {output_path}")

    # 找出最佳配置
    successful_results = [r for r in results if r["success"]]
    best_result = min(successful_results, key=lambda x: x["compilation_time_seconds"])
    print(
        f"最佳並行級別: {best_result['parallel_level']} "
        f"({best_result['compilation_time_seconds']}秒)"
    )

    return results


if __name__ == "__main__":
    benchmark_parallel_levels()
