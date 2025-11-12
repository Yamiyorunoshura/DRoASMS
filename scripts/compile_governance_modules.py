#!/usr/bin/env python3
"""Legacy stub for governance compilation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LEGACY_PATH = Path(__file__).resolve().parent / "archive" / "compile_governance_modules.py"


def main() -> None:
    new_script = Path(__file__).resolve().parent / "compile_modules.py"
    if new_script.exists():
        cmd = [sys.executable, str(new_script), "compile"]
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            sys.stderr.write("compile_modules.py 執行失敗，請檢查輸出或改用 legacy 腳本。\n")
            sys.stderr.write(f"Legacy script 保留於: {LEGACY_PATH}\n")
        sys.exit(result.returncode)

    sys.stderr.write("找不到新的 compile_modules.py，改以 legacy 腳本路徑提示。\n")
    sys.stderr.write(f"Legacy script 保留於: {LEGACY_PATH}\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
