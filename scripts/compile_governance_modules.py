#!/usr/bin/env python3
"""Legacy stub for governance compilation."""

from __future__ import annotations

import sys
from pathlib import Path

LEGACY_PATH = Path(__file__).resolve().parent / "archive" / "compile_governance_modules.py"


def main() -> None:
    sys.stderr.write(
        "compile_governance_modules.py 已封存，請改用 "
        "`python scripts/compile_modules.py compile`。\n"
    )
    sys.stderr.write(f"Legacy script 保留於: {LEGACY_PATH}\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
