"""Migration tools for transitioning from exception-based to Result-based error handling.

This module provides utilities to help migrate existing code that uses traditional
try/except patterns to the new Result<T,E> pattern.
"""

from __future__ import annotations

import ast
from types import TracebackType
from typing import Any, Callable, Type, TypedDict, TypeVar, cast

from src.infra.result import Err, Error, Ok, Result

T = TypeVar("T")
E = TypeVar("E", bound=Error)


def exception_to_result(
    func: Callable[..., T],
    error_type: Type[Error] = Error,
) -> Callable[..., Result[T, Error]]:
    """Convert a function that raises exceptions to return Result types.

    This is a migration helper that wraps existing functions to convert
    exceptions to Result types. It should be used during the transition
    period.

    Args:
        func: The function to wrap
        error_type: The error type to use for exceptions

    Returns:
        A new function that returns Result[T, E] instead of raising exceptions

    Example:
        @exception_to_result
        def risky_operation():
            if something_wrong:
                raise ValueError("Something went wrong")
            return "success"

        result = risky_operation()
        if result.is_err():
            print(f"Error: {result.unwrap_err()}")
    """

    def wrapper(*args: object, **kwargs: object) -> Result[T, Error]:
        try:
            return Ok(func(*args, **kwargs))
        except Exception as e:
            error = error_type(str(e))
            return Err(error)

    return wrapper


def result_to_exception(result: Result[T, E]) -> T:
    """Convert a Result back to exception-throwing behavior.

    This is useful for:
    - Interfacing with code that expects exceptions
    - Gradual migration where some parts still use exceptions
    - Testing and debugging

    Args:
        result: The Result to unwrap

    Returns:
        The success value if Ok

    Raises:
        Exception: The underlying error if Err
    """
    if result.is_err():
        error = result.unwrap_err()
        # Try to reconstruct the original exception if possible
        if hasattr(error, "cause") and error.cause:
            raise error.cause
        else:
            raise Exception(str(error))
    return result.unwrap()


class ExceptionAdapter:
    """Adapter class to make Result-based code work with exception-based interfaces.

    This class provides a context manager and decorator to temporarily
    convert Result types back to exceptions for compatibility with
    existing code during migration.
    """

    def __init__(self, error_map: dict[Type[Error], Type[Exception]] | None = None):
        """Initialize the adapter with optional error type mapping.

        Args:
            error_map: Mapping from Result error types to exception types
        """
        self.error_map = error_map or {}

    def __enter__(self) -> "ExceptionAdapter":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # ExceptionAdapter 本身目前不攔截例外，只提供語意化區段。
        return None

    def adapt_result(self, result: Result[T, E]) -> T:
        """Adapt a Result to either return value or raise exception.

        Args:
            result: The Result to adapt

        Returns:
            The success value

        Raises:
            Exception: Mapped from the Result error
        """
        if result.is_ok():
            return result.unwrap()

        error = result.unwrap_err()
        # Check if we have a mapping for this error type
        for error_type, exc_type in self.error_map.items():
            if isinstance(error, error_type):
                raise exc_type(str(error)) from getattr(error, "cause", None)

        # Default: raise generic exception
        raise Exception(str(error)) from getattr(error, "cause", None)


def adapt_function(
    error_map: dict[Type[Error], Type[Exception]] | None = None
) -> Callable[[Callable[..., Result[T, E]]], Callable[..., T]]:
    """Decorator to adapt Result-returning functions to exception-throwing ones.

    Args:
        error_map: Optional mapping of error types to exception types

    Returns:
        Decorator that adapts functions

    Example:
        error_map = {
            ValidationError: ValueError,
            DatabaseError: RuntimeError
        }

        @adapt_function(error_map)
        def my_function() -> Result[str, Error]:
            return Err(ValidationError("Invalid input"))

        # This will now raise ValueError instead of returning Result
        my_function()
    """
    adapter = ExceptionAdapter(error_map)

    def decorator(func: Callable[..., Result[T, E]]) -> Callable[..., T]:
        def wrapper(*args: object, **kwargs: object) -> T:
            result = func(*args, **kwargs)
            return adapter.adapt_result(result)

        return wrapper

    return decorator


class TryExceptToResultTransformer(ast.NodeTransformer):
    """AST transformer to convert try/except blocks to Result pattern.

    This is an experimental tool for automatically converting code.
    Use with caution and review the output carefully.
    """

    def visit_Try(self, node: ast.Try) -> ast.AST:
        """Transform try/except blocks to Result pattern."""
        # This is a simplified transformation - real implementation would be more complex
        # For now, we'll just return the original node
        return node


class ExceptionUsageAnalysis(TypedDict):
    """結構化的例外使用分析結果。"""

    try_blocks: int
    except_handlers: int
    raise_statements: int
    functions_with_try: list[str]
    custom_exceptions: set[str]


def analyze_exception_usage(source_code: str) -> ExceptionUsageAnalysis:
    """Analyze a Python source file for exception usage patterns.

    This helps identify areas that need migration to Result pattern.

    Args:
        source_code: The Python source code to analyze

    Returns:
        Dictionary with analysis results
    """
    tree = ast.parse(source_code)

    analysis: ExceptionUsageAnalysis = {
        "try_blocks": 0,
        "except_handlers": 0,
        "raise_statements": 0,
        "functions_with_try": [],
        "custom_exceptions": set(),
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            analysis["try_blocks"] += 1
            analysis["except_handlers"] += len(node.handlers)
            # Find function containing this try block
            for parent in ast.walk(tree):
                if isinstance(parent, ast.FunctionDef):
                    for child in ast.walk(parent):
                        if child is node:
                            analysis["functions_with_try"].append(parent.name)
                            break

        elif isinstance(node, ast.Raise):
            analysis["raise_statements"] += 1
            if isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                analysis["custom_exceptions"].add(node.exc.func.id)

    # Convert set to list for JSON serialization / reporting convenience
    analysis["functions_with_try"] = list(set(analysis["functions_with_try"]))

    return analysis


def generate_migration_report(source_files: list[str]) -> str:
    """Generate a migration report for multiple source files.

    Args:
        source_files: List of Python file paths to analyze

    Returns:
        Formatted migration report
    """
    reports: list[dict[str, Any]] = []

    for file_path in source_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            analysis = analyze_exception_usage(source)
            reports.append({"file": file_path, "analysis": analysis})
        except Exception as e:
            reports.append({"file": file_path, "error": str(e)})

    # Generate report
    report_lines: list[str] = [
        "# Result Pattern Migration Report",
        "",
        "## Summary",
        "",
    ]

    total_try_blocks = 0
    total_except_handlers = 0
    total_raise_statements = 0

    for report in reports:
        if "analysis" not in report:
            continue
        analysis = cast(ExceptionUsageAnalysis, report["analysis"])
        total_try_blocks += analysis["try_blocks"]
        total_except_handlers += analysis["except_handlers"]
        total_raise_statements += analysis["raise_statements"]

    report_lines.extend(
        [
            f"- Total try blocks: {total_try_blocks}",
            f"- Total except handlers: {total_except_handlers}",
            f"- Total raise statements: {total_raise_statements}",
            "",
            "## Files Analysis",
            "",
        ]
    )

    for report in reports:
        if "error" in report:
            report_lines.append(f"### {report['file']}")
            report_lines.append(f"Error: {report['error']}")
            report_lines.append("")
        else:
            analysis = cast(ExceptionUsageAnalysis, report["analysis"])
            report_lines.extend(
                [
                    f"### {report['file']}",
                    "",
                    f"- Try blocks: {analysis['try_blocks']}",
                    f"- Except handlers: {analysis['except_handlers']}",
                    f"- Raise statements: {analysis['raise_statements']}",
                    "",
                    "Functions with try blocks:",
                ]
            )
            for func_name in analysis["functions_with_try"]:
                report_lines.append(f"- {func_name}")
            if analysis["custom_exceptions"]:
                report_lines.append("")
                report_lines.append("Custom exceptions raised:")
                for exc_name in analysis["custom_exceptions"]:
                    report_lines.append(f"- {exc_name}")
            report_lines.append("")

    return "\n".join(report_lines)


# Example migration patterns
def example_migration_patterns() -> None:
    """Show example patterns for migrating from exceptions to Results."""

    # Pattern 1: Simple validation
    print("Pattern 1: Simple validation")
    print("Before (exceptions):")
    print(
        """
def validate_user(data):
    if not data.get('name'):
        raise ValueError('Name is required')
    if not data.get('email'):
        raise ValueError('Email is required')
    return True
"""
    )

    print("After (Result pattern):")
    print(
        """
def validate_user(data):
    if not data.get('name'):
        return Err(ValidationError('Name is required'))
    if not data.get('email'):
        return Err(ValidationError('Email is required'))
    return Ok(True)
"""
    )

    # Pattern 2: Chaining operations
    print("\nPattern 2: Chaining operations")
    print("Before (exceptions):")
    print(
        """
def process_payment(user_id, amount):
    try:
        user = get_user(user_id)
        if user.balance < amount:
            raise InsufficientBalanceError()

        transaction = create_transaction(user, amount)
        update_balance(user, -amount)
        return transaction
    except Exception as e:
        logger.error(f"Payment failed: {e}")
        raise
"""
    )

    print("After (Result pattern):")
    print(
        """
def process_payment(user_id, amount):
    return (
        get_user(user_id)
        .and_then(lambda user: validate_balance(user, amount))
        .and_then(lambda user: create_transaction(user, amount))
        .and_then(lambda txn: update_balance(txn.user, -amount).map(lambda _: txn))
        .map_err(lambda e: logger.error(f"Payment failed: {e}") or e)
    )
"""
    )


if __name__ == "__main__":
    # Show example patterns
    example_migration_patterns()
