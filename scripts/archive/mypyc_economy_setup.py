#!/usr/bin/env python
"""
以 mypyc 編譯經濟模塊。

最小做法：
- 從 pyproject.toml 的 [tool.mypyc] 讀取目標與選項
- 使用 setuptools + mypyc.build.mypycify 建立擴充模組

使用方式：
  uv run python scripts/mypyc_economy_setup.py build_ext --build-lib build/mypyc_out

注意：
- 將輸出目錄（例如 build/mypyc_out）加入 PYTHONPATH 以覆蓋純 Python 版本：
    PYTHONPATH=build/mypyc_out:src uv run python -c \\
        "import src.bot.services.balance_service as m; \\
         print(m.__name__)"
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - 後援方案（理論上不會用到）
    import tomli as tomllib  # type: ignore

from mypyc.build import mypycify
from setuptools import setup

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _load_mypyc_config() -> dict:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    # 嘗試載入統一配置
    unified_cfg = data.get("tool", {}).get("unified-compiler", {})
    if unified_cfg:
        print("✅ 使用統一編譯器配置")
        # 將統一配置轉換為 mypyc 格式
        mypc_backend = unified_cfg.get("backends", {}).get("mypyc", {})
        economy_modules = unified_cfg.get("modules", {}).get("economy_modules", [])

        return {
            "targets": economy_modules,
            "opt_level": mypc_backend.get("opt_level", 3),
            "debug_level": mypc_backend.get("debug_level", 1),
            "strip_asserts": mypc_backend.get("strip_asserts", True),
        }

    # 回退到舊的 [tool.mypyc] 配置
    cfg = data.get("tool", {}).get("mypyc", {})
    if not cfg:
        raise SystemExit("未在 pyproject.toml 找到 [tool.unified-compiler] 或 [tool.mypyc] 設定")

    print("⚠️  回退到舊版 [tool.mypyc] 配置（建議遷移到統一配置）")
    return cfg


def _resolve_targets(targets: list[str]) -> list[str]:
    paths: list[str] = []
    for t in targets:
        p = (ROOT / t).resolve()
        if not p.exists():
            raise SystemExit(f"目標檔案不存在：{t}")
        # mypycify 接受檔案路徑清單
        paths.append(str(p))
    return paths


def main() -> None:
    cfg = _load_mypyc_config()
    targets = _resolve_targets(cfg.get("targets", []))

    opt_level = str(cfg.get("opt_level", 3))

    # 最小且保守的參數組合；避免因版本差異使用到不存在的參數
    ext_modules = mypycify(targets, opt_level=opt_level, multi_file=True)

    # 允許透過命令列傳入 build_ext 參數，例如：
    #   build_ext --build-lib build/mypyc_out
    # 以便不污染原始 src/ 目錄
    setup(
        name="droasms-economy-mypyc",
        version="0.0.0",
        ext_modules=ext_modules,
        zip_safe=False,
    )


if __name__ == "__main__":
    # 確保從專案根目錄執行（避免本機的 build/ 目錄覆蓋到 Python 套件 `build`）
    os.chdir(ROOT)
    main()
