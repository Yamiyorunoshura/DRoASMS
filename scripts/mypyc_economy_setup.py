#!/usr/bin/env python3
"""Legacy stub for mypyc economy setup."""

from __future__ import annotations

import sys
from pathlib import Path

LEGACY_PATH = Path(__file__).resolve().parent / "archive" / "mypyc_economy_setup.py"


def main() -> None:
    sys.stderr.write(
        "mypy c 經濟模組腳本已封存，請改用 "
        "`python scripts/compile_modules.py compile` 或 Makefile 統一目標。\n"
    )
    sys.stderr.write(f"Legacy script 保留於: {LEGACY_PATH}\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
