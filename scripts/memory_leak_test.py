#!/usr/bin/env python3
"""記憶體洩漏檢測測試"""

import gc
import sys
from typing import List

try:
    import resource
except ImportError:
    resource = None


def get_memory_usage():
    """獲取當前記憶體使用量（MB）"""
    if resource:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        if sys.platform == "darwin":
            return usage.ru_maxrss / 1024 / 1024  # macOS: bytes to MB
        else:
            return usage.ru_maxrss / 1024  # Linux: KB to MB
    else:
        return 0.0


def test_memory_leak():
    """測試重複導入模組是否會造成記憶體洩漏"""

    modules_to_test = [
        "src.cython_ext.currency_models",
        "src.cython_ext.economy_configuration_models",
        "src.cython_ext.state_council_models",
    ]

    initial_memory = get_memory_usage()
    print(f"初始記憶體使用: {initial_memory:.2f} MB")

    memory_samples: List[float] = []

    # 重複導入測試
    for i in range(30):  # 減少迭代次數以加快測試
        for module in modules_to_test:
            try:
                exec(f"import {module}")
                exec(f"import importlib; importlib.reload({module})")
            except Exception as e:
                print(f"模組 {module} 導入失敗: {e}")

        if i % 5 == 0:
            gc.collect()  # 強制垃圾回收
            current_memory = get_memory_usage()
            memory_samples.append(current_memory)
            print(f"第 {i} 次迭代後記憶體: {current_memory:.2f} MB")

    final_memory = get_memory_usage()
    memory_increase = final_memory - initial_memory

    print("\n記憶體洩漏測試結果:")
    print(f"初始記憶體: {initial_memory:.2f} MB")
    print(f"最終記憶體: {final_memory:.2f} MB")
    print(f"記憶體增長: {memory_increase:.2f} MB")
    print(f"記憶體樣本數: {len(memory_samples)}")

    # 分析記憶體增長趨勢
    if len(memory_samples) >= 3:
        first_half = memory_samples[: len(memory_samples) // 2]
        second_half = memory_samples[len(memory_samples) // 2 :]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        trend_increase = avg_second - avg_first
        print(f"趨勢分析: 後半段比前半段平均增加 {trend_increase:.2f} MB")

        if trend_increase > 2.0:
            print("⚠️  可能存在記憶體洩漏")
            return False
        else:
            print("✅ 沒有明顯記憶體洩漏")
            return True

    return memory_increase < 5.0


if __name__ == "__main__":
    test_memory_leak()
