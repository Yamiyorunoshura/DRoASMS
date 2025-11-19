#!/usr/bin/env python3
"""
Migration script to help transition from exception-based to Result-based error handling.

This script analyzes Python files and provides suggestions for migrating to the Result pattern.
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infra.migration_tools import analyze_exception_usage


class ResultMigrationAnalyzer(ast.NodeVisitor):
    """Analyze Python code for Result pattern migration opportunities."""

    def __init__(self) -> None:
        self.try_blocks: List[Dict[str, Any]] = []
        self.raise_statements: List[Dict[str, Any]] = []
        self.exception_classes: Set[str] = set()
        self.functions_needing_migration: Set[str] = set()
        self.imports: Set[str] = set()

    def visit_Try(self, node: ast.Try) -> None:
        """Visit try blocks."""
        # Get line number and surrounding context
        try_block = {
            "line_start": getattr(node, "lineno", 0),
            "line_end": getattr(node, "end_lineno", 0),
            "has_finally": bool(node.finalbody),
            "except_types": [],
            "complexity": "simple" if len(node.handlers) <= 2 else "complex",
        }

        # Analyze exception handlers
        for handler in node.handlers:
            if handler.type:
                if isinstance(handler.type, ast.Name):
                    try_block["except_types"].append(handler.type.id)
                elif isinstance(handler.type, ast.Tuple):
                    for elt in handler.type.elts:
                        if isinstance(elt, ast.Name):
                            try_block["except_types"].append(elt.id)

        self.try_blocks.append(try_block)
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        """Visit raise statements."""
        raise_info = {
            "line": getattr(node, "lineno", 0),
            "exception_type": None,
        }

        if node.exc:
            if isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                raise_info["exception_type"] = node.exc.func.id
                self.exception_classes.add(node.exc.func.id)

        self.raise_statements.append(raise_info)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions."""
        # Check if function has try blocks
        for child in ast.walk(node):
            if isinstance(child, ast.Try) and child != node:
                self.functions_needing_migration.add(node.name)
                break

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definitions."""
        self.visit_FunctionDef(node)  # Same logic applies

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statements."""
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from import statements."""
        if node.module:
            for alias in node.names:
                self.imports.add(f"{node.module}.{alias.name}")
        self.generic_visit(node)


def analyze_file(file_path: Path) -> Dict[str, Any]:
    """Analyze a single Python file for migration opportunities."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(file_path))
        analyzer = ResultMigrationAnalyzer()
        analyzer.visit(tree)

        # Also use the basic analysis
        basic_analysis = analyze_exception_usage(source)

        return {
            "file": str(file_path),
            "try_blocks": analyzer.try_blocks,
            "raise_statements": analyzer.raise_statements,
            "exception_classes": list(analyzer.exception_classes),
            "functions_needing_migration": list(analyzer.functions_needing_migration),
            "imports": list(analyzer.imports),
            "basic_analysis": basic_analysis,
            "migration_priority": calculate_priority(analyzer),
        }
    except Exception as e:
        return {
            "file": str(file_path),
            "error": str(e),
        }


def calculate_priority(analyzer: ResultMigrationAnalyzer) -> str:
    """Calculate migration priority based on analysis."""
    score = 0

    # Score based on number of try blocks
    score += len(analyzer.try_blocks) * 2

    # Score based on complexity
    for try_block in analyzer.try_blocks:
        if try_block["complexity"] == "complex":
            score += 3
        if len(try_block["except_types"]) > 2:
            score += 2

    # Score based on raise statements
    score += len(analyzer.raise_statements)

    if score >= 20:
        return "high"
    elif score >= 10:
        return "medium"
    else:
        return "low"


def generate_suggestions(analysis: Dict[str, Any]) -> List[str]:
    """Generate migration suggestions based on analysis."""
    suggestions = []

    if "error" in analysis:
        return [f"Error analyzing file: {analysis['error']}"]

    # General suggestions
    if analysis["try_blocks"]:
        suggestions.append(
            f"Convert {len(analysis['try_blocks'])} try/except blocks to Result pattern"
        )

    if analysis["raise_statements"]:
        suggestions.append(
            f"Replace {len(analysis['raise_statements'])} raise statements with Result returns"
        )

    # Specific suggestions based on patterns
    for try_block in analysis["try_blocks"]:
        if "ValidationError" in try_block["except_types"]:
            suggestions.append("Use ValidationError from src.infra.result for validation errors")
        if (
            "DatabaseError" in try_block["except_types"]
            or "PostgresError" in try_block["except_types"]
        ):
            suggestions.append("Use DatabaseError from src.infra.result for database errors")

    # Import suggestions
    if any("src.bot.services" in str(analysis["file"]) for _ in [0]):
        suggestions.append("Consider adding @async_returns_result decorator to service methods")

    # Function-specific suggestions
    for func_name in analysis["functions_needing_migration"][:5]:  # Top 5
        suggestions.append(f"Migrate function '{func_name}' to return Result type")

    return suggestions


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description="Analyze Python files for Result pattern migration opportunities"
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Files or directories to analyze",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file for report (default: stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--priority",
        choices=["high", "medium", "low", "all"],
        default="all",
        help="Only show files with this priority level",
    )

    args = parser.parse_args()

    # Collect files to analyze
    files_to_analyze = []
    for path in args.paths:
        path_obj = Path(path)
        if path_obj.is_file() and path_obj.suffix == ".py":
            files_to_analyze.append(path_obj)
        elif path_obj.is_dir():
            files_to_analyze.extend(path_obj.rglob("*.py"))

    if not files_to_analyze:
        print("No Python files found to analyze", file=sys.stderr)
        sys.exit(1)

    # Analyze files
    analyses = []
    for file_path in files_to_analyze:
        analysis = analyze_file(file_path)
        if args.priority == "all" or analysis.get("migration_priority") == args.priority:
            analyses.append(analysis)

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2, None: 3}
    analyses.sort(key=lambda x: priority_order.get(x.get("migration_priority"), 3))

    # Generate output
    if args.format == "json":
        import json

        output = json.dumps(analyses, indent=2, ensure_ascii=False)
    else:
        output_lines = [
            "# Result Pattern Migration Analysis",
            "",
            f"Analyzed {len(files_to_analyze)} files",
            f"Showing {len(analyses)} files with priority: {args.priority}",
            "",
        ]

        for i, analysis in enumerate(analyses, 1):
            if "error" in analysis:
                output_lines.extend(
                    [
                        f"## {i}. {analysis['file']}",
                        "",
                        f"Error: {analysis['error']}",
                        "",
                    ]
                )
                continue

            output_lines.extend(
                [
                    f"## {i}. {analysis['file']}",
                    "",
                    f"Priority: {analysis['migration_priority']}",
                    "",
                    "### Statistics",
                    "",
                    f"- Try blocks: {len(analysis['try_blocks'])}",
                    f"- Raise statements: {len(analysis['raise_statements'])}",
                    f"- Functions needing migration: {len(analysis['functions_needing_migration'])}"
                    "",
                    "### Migration Suggestions",
                    "",
                ]
            )

            suggestions = generate_suggestions(analysis)
            for suggestion in suggestions:
                output_lines.append(f"- {suggestion}")

            # Show first function to migrate
            if analysis["functions_needing_migration"]:
                output_lines.extend(
                    [
                        "",
                        "### Top Functions to Migrate",
                        "",
                    ]
                )
                for func_name in analysis["functions_needing_migration"][:3]:
                    output_lines.append(f"- {func_name}")

            output_lines.append("")

        output = "\n".join(output_lines)

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
