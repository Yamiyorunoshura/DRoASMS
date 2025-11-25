#!/usr/bin/env python3
"""Coverage monitoring script for slash command tests.

This script monitors test coverage for slash commands and enforces
a minimum coverage threshold of 90%.

Usage:
    python scripts/check_coverage.py [--threshold 90] [--report]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Minimum coverage threshold (90%)
DEFAULT_THRESHOLD = 90.0

# Command modules to track
COMMAND_MODULES = [
    "src/bot/commands/adjust.py",
    "src/bot/commands/balance.py",
    "src/bot/commands/council.py",
    "src/bot/commands/currency_config.py",
    "src/bot/commands/help.py",
    "src/bot/commands/help_collector.py",
    "src/bot/commands/help_formatter.py",
    "src/bot/commands/state_council.py",
    "src/bot/commands/supreme_assembly.py",
    "src/bot/commands/transfer.py",
]


@dataclass
class CoverageResult:
    """Coverage result for a single module."""

    module: str
    statements: int
    missing: int
    coverage: float


def run_coverage(test_path: str = "tests/") -> dict[str, CoverageResult]:
    """Run pytest with coverage and return results per module."""
    # Run pytest with coverage
    cmd = [
        "uv",
        "run",
        "pytest",
        test_path,
        "--cov=src/bot/commands",
        "--cov-report=json:coverage.json",
        "--cov-report=term-missing",
        "-q",
        "--tb=no",
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0 and "error" in result.stderr.lower():
        print(f"Error running tests: {result.stderr}")
        sys.exit(1)

    # Parse coverage.json
    coverage_file = Path("coverage.json")
    if not coverage_file.exists():
        print("coverage.json not found. Make sure pytest-cov is installed.")
        sys.exit(1)

    with open(coverage_file) as f:
        coverage_data = json.load(f)

    results: dict[str, CoverageResult] = {}

    for module_path in COMMAND_MODULES:
        # Try different path formats
        for key in coverage_data.get("files", {}):
            if module_path in key or key.endswith(Path(module_path).name):
                file_data = coverage_data["files"][key]
                summary = file_data.get("summary", {})
                results[module_path] = CoverageResult(
                    module=module_path,
                    statements=summary.get("num_statements", 0),
                    missing=summary.get("missing_lines", 0),
                    coverage=summary.get("percent_covered", 0.0),
                )
                break
        else:
            # Module not found in coverage data
            results[module_path] = CoverageResult(
                module=module_path,
                statements=0,
                missing=0,
                coverage=0.0,
            )

    return results


def print_coverage_report(
    results: dict[str, CoverageResult],
    threshold: float = DEFAULT_THRESHOLD,
) -> bool:
    """Print coverage report and return True if all modules meet threshold."""
    print("\n" + "=" * 80)
    print("SLASH COMMAND COVERAGE REPORT")
    print("=" * 80)
    print(f"{'Module':<45} {'Stmts':>8} {'Miss':>8} {'Cover':>8} {'Status':>10}")
    print("-" * 80)

    all_pass = True
    total_statements = 0
    total_covered = 0

    for module_path, result in sorted(results.items()):
        status = "✓ PASS" if result.coverage >= threshold else "✗ FAIL"
        if result.coverage < threshold:
            all_pass = False

        module_name = Path(module_path).stem
        print(
            f"{module_name:<45} {result.statements:>8} {result.missing:>8} "
            f"{result.coverage:>7.1f}% {status:>10}"
        )

        total_statements += result.statements
        total_covered += result.statements - result.missing

    # Print summary
    overall_coverage = (total_covered / total_statements * 100) if total_statements > 0 else 0.0
    print("-" * 80)
    print(
        f"{'TOTAL':<45} {total_statements:>8} {total_statements - total_covered:>8} "
        f"{overall_coverage:>7.1f}%"
    )
    print("=" * 80)

    print(f"\nThreshold: {threshold}%")
    if all_pass:
        print("✓ All modules meet coverage threshold!")
    else:
        print("✗ Some modules are below coverage threshold!")

    return all_pass


def get_low_coverage_modules(
    results: dict[str, CoverageResult],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[CoverageResult]:
    """Return list of modules below threshold, sorted by coverage."""
    low_coverage = [r for r in results.values() if r.coverage < threshold]
    return sorted(low_coverage, key=lambda x: x.coverage)


def generate_improvement_suggestions(
    results: dict[str, CoverageResult],
    threshold: float = DEFAULT_THRESHOLD,
) -> None:
    """Generate suggestions for improving coverage."""
    low_coverage = get_low_coverage_modules(results, threshold)

    if not low_coverage:
        print("\nAll modules meet the coverage threshold. Great job!")
        return

    print("\n" + "=" * 80)
    print("IMPROVEMENT SUGGESTIONS")
    print("=" * 80)

    for result in low_coverage:
        lines_needed = int(
            (threshold / 100 * result.statements) - (result.statements - result.missing)
        )
        print(f"\n{result.module}:")
        covered = result.statements - result.missing
        print(f"  Current: {result.coverage:.1f}% ({covered}/{result.statements} lines)")
        print(f"  Target:  {threshold}%")
        print(f"  Need to cover approximately {lines_needed} more lines")

        # Suggest specific test files
        module_name = Path(result.module).stem
        print(f"  Test file: tests/unit/test_{module_name}.py")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Check slash command test coverage")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Minimum coverage threshold (default: {DEFAULT_THRESHOLD}%)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate detailed improvement report",
    )
    parser.add_argument(
        "--test-path",
        type=str,
        default="tests/",
        help="Path to test directory",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: fail if any module is below threshold",
    )

    args = parser.parse_args()

    print(f"Running coverage check with threshold: {args.threshold}%")

    results = run_coverage(args.test_path)
    all_pass = print_coverage_report(results, args.threshold)

    if args.report:
        generate_improvement_suggestions(results, args.threshold)

    if args.ci and not all_pass:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
