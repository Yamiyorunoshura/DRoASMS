#!/usr/bin/env python3
"""CLI 工具：輸出 Result 遷移追蹤報表（文字或 JSON）。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.infra.result_compat import get_migration_report, get_migration_state


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show structured Result migration status collected by MigrationTracker."
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="輸出格式（預設 text）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="若指定則將報表寫入檔案，否則輸出到 stdout",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.format == "text":
        content = get_migration_report()
    else:
        state = get_migration_state()
        content = json.dumps(state, ensure_ascii=False, indent=2)

    if args.output is not None:
        args.output.write_text(content + "\n", encoding="utf-8")
    else:
        print(content)


if __name__ == "__main__":
    main()
