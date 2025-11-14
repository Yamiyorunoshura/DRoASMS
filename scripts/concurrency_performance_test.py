#!/usr/bin/env python3
"""並發處理性能測試"""

import concurrent.futures
import os
import statistics
import sys
import threading
import time
from typing import Any, Dict, List

# 添加項目根目錄到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def import_module_timed(module_name: str) -> Dict[str, Any]:
    """測量單個模組導入時間"""
    start_time = time.time()
    try:
        exec(f"import {module_name}")
        success = True
        error = None
    except Exception as e:
        success = False
        error = str(e)

    end_time = time.time()
    import_time = end_time - start_time

    return {"module": module_name, "import_time": import_time, "success": success, "error": error}


def test_concurrent_imports(module_names: List[str], thread_count: int) -> Dict[str, Any]:
    """測試並發導入性能"""

    print(f"\n測試 {thread_count} 個線程並發導入...")

    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = [executor.submit(import_module_timed, module) for module in module_names]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    end_time = time.time()
    total_time = end_time - start_time

    successful_imports = [r for r in results if r["success"]]
    failed_imports = [r for r in results if not r["success"]]

    import_times = [r["import_time"] for r in successful_imports]

    return {
        "thread_count": thread_count,
        "total_time": total_time,
        "successful_imports": len(successful_imports),
        "failed_imports": len(failed_imports),
        "average_import_time": statistics.mean(import_times) if import_times else 0,
        "median_import_time": statistics.median(import_times) if import_times else 0,
        "max_import_time": max(import_times) if import_times else 0,
        "min_import_time": min(import_times) if import_times else 0,
        "throughput": len(successful_imports) / total_time if total_time > 0 else 0,
        "results": results,
    }


def test_thread_safety(module_names: List[str], iterations: int = 10) -> Dict[str, Any]:
    """測試線程安全性"""

    print(f"\n測試線程安全性 ({iterations} 次迭代)...")

    errors = []

    def worker_iteration():
        """單個工作線程的迭代測試"""
        iteration_results = []
        for _ in range(iterations):
            for module in module_names:
                try:
                    start = time.time()
                    exec(f"import {module}")
                    end = time.time()
                    iteration_results.append(
                        {"module": module, "import_time": end - start, "success": True}
                    )
                except Exception as e:
                    errors.append(
                        {
                            "module": module,
                            "error": str(e),
                            "thread_id": threading.current_thread().ident,
                        }
                    )
        return iteration_results

    # 啟動多個線程
    threads = []
    thread_results = []

    for _i in range(4):  # 4個線程同時測試
        thread = threading.Thread(target=lambda: thread_results.append(worker_iteration()))
        threads.append(thread)

    # 同時啟動所有線程
    start_time = time.time()
    for thread in threads:
        thread.start()

    # 等待所有線程完成
    for thread in threads:
        thread.join()

    end_time = time.time()

    # 合併結果
    all_results: list[dict[str, Any]] = []
    for result_list in thread_results:
        all_results.extend(result_list)

    error_rate = len(errors) / len(all_results) if all_results else 0
    average_import_time = (
        statistics.mean([r["import_time"] for r in all_results]) if all_results else 0
    )

    return {
        "concurrent_threads": 4,
        "iterations_per_thread": iterations,
        "total_time": end_time - start_time,
        "total_imports": len(all_results),
        "successful_imports": len([r for r in all_results if r["success"]]),
        "errors": len(errors),
        "error_rate": error_rate,
        "average_import_time": average_import_time,
        "thread_safety_passed": len(errors) == 0,
    }


def main():
    """主測試函數"""

    print("Cython 模組並發性能測試")
    print("=" * 50)

    # 測試模組列表
    test_modules = [
        "src.cython_ext.currency_models",
        "src.cython_ext.economy_configuration_models",
        "src.cython_ext.state_council_models",
        "src.cython_ext.economy_balance_models",
        "src.cython_ext.transfer_pool_core",
    ]

    # 串行基準測試
    print("\n串行導入基準測試...")
    serial_result = test_concurrent_imports(test_modules, 1)

    # 並發測試
    concurrent_results = []
    for thread_count in [2, 4, 8]:
        try:
            result = test_concurrent_imports(test_modules, thread_count)
            concurrent_results.append(result)
        except Exception as e:
            print(f"並發測試失敗 (線程數 {thread_count}): {e}")

    # 線程安全性測試
    thread_safety_result = test_thread_safety(test_modules, 5)

    # 分析結果
    print("\n並發性能分析結果:")
    print(f"串行基準時間: {serial_result['total_time']:.3f}秒")
    print(f"串行吞吐量: {serial_result['throughput']:.2f} 模組/秒")

    for result in concurrent_results:
        total_time = result["total_time"]
        speedup = serial_result["total_time"] / total_time if total_time > 0 else 0
        print(f"{result['thread_count']}線程並行: " f"{total_time:.3f}秒 (加速比: {speedup:.2f}x)")
        print(f"  吞吐量: {result['throughput']:.2f} 模組/秒")
        print(f"  成功率: {result['successful_imports']}/{len(test_modules)}")

    print("\n線程安全性測試:")
    print(f"錯誤率: {thread_safety_result['error_rate']:.2%}")
    print(f"線程安全性: {'✅ 通過' if thread_safety_result['thread_safety_passed'] else '❌ 失敗'}")

    # 保存結果
    import json

    if concurrent_results:
        best_speedup = max(
            (serial_result["total_time"] / r["total_time"] if r["total_time"] > 0 else 0)
            for r in concurrent_results
        )
    else:
        best_speedup = 1.0

    output_data = {
        "timestamp": time.time(),
        "serial_baseline": serial_result,
        "concurrent_tests": concurrent_results,
        "thread_safety": thread_safety_result,
        "summary": {
            "best_speedup": best_speedup,
            "thread_safe": thread_safety_result["thread_safety_passed"],
            "concurrency_efficiency": "good" if len(concurrent_results) > 0 else "failed",
        },
    }

    output_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "build",
        "cython",
        "concurrency_performance_test.json",
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n結果已保存至: {output_path}")


if __name__ == "__main__":
    main()
