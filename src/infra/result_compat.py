"""Compatibility layer for gradual migration to Result pattern.

This module provides compatibility shims to help gradually migrate existing
code to use Result types without breaking changes.
"""

from __future__ import annotations

import warnings
from types import TracebackType
from typing import Callable, Type, TypeVar, overload

from src.infra.result import DatabaseError, Err, Error, Ok, Result

T = TypeVar("T")


class CompatibilityWarning(UserWarning):
    """Warning for code using compatibility layer that should be migrated."""

    pass


class ResultCompat:
    """Compatibility layer for Result pattern migration.

    This class provides methods to gradually migrate from exception-based
    error handling to Result-based error handling without breaking existing code.
    """

    @staticmethod
    def wrap_function(
        func: Callable[..., T],
        *,
        exceptions: tuple[Type[Exception], ...] = (Exception,),
        error_type: Type[Error] = DatabaseError,
        warn_after: int = 10,
    ) -> Callable[..., T]:
        """Wrap a function to catch exceptions and convert to Result internally.

        This allows existing code to continue working while internally using
        Result pattern. After warn_after calls, it will emit warnings.

        Args:
            func: Function to wrap
            exceptions: Tuple of exception types to catch
            error_type: Error type to use in Result
            warn_after: Number of calls after which to emit warnings

        Returns:
            Wrapped function that still throws exceptions but logs Result usage
        """
        call_count = 0

        def wrapper(*args: object, **kwargs: object) -> T:
            nonlocal call_count
            call_count += 1

            # Internal Result-based implementation
            try:
                value = func(*args, **kwargs)
                # 使用 Ok 只是為了與 Result 模式保持一致，外部仍看到原本回傳值
                result: Result[T, Error] = Ok(value)
                return result.unwrap()
            except exceptions as e:
                error = error_type(str(e))
                result = Err(error)

                # Log the error for monitoring
                import structlog

                logger = structlog.get_logger(__name__)
                logger.warning(
                    "compat_exception_caught",
                    function=func.__name__,
                    error=str(error),
                    call_count=call_count,
                )

                # Emit warning after threshold
                if call_count > warn_after:
                    warnings.warn(
                        f"Function {func.__name__} is using compatibility layer. "
                        f"Consider migrating to explicit Result pattern.",
                        CompatibilityWarning,
                        stacklevel=2,
                    )

                # Convert back to exception for compatibility
                if hasattr(error, "cause") and error.cause:
                    # 儘量還原原始例外型別
                    raise error.cause from e
                raise Exception(str(error)) from e

        return wrapper

    @staticmethod
    def adapt_result_for_exception_code(result: Result[T, Error]) -> T:
        """Adapt a Result for code that expects exceptions.

        This is a temporary measure during migration. Code using this should
        be updated to handle Result types directly.

        Args:
            result: Result to adapt

        Returns:
            Success value

        Raises:
            Exception: Converted from Result error
        """
        warnings.warn(
            "Using compatibility adapter for Result pattern. "
            "Update code to handle Result types directly.",
            CompatibilityWarning,
            stacklevel=2,
        )

        if result.is_err():
            error = result.unwrap_err()
            # Try to preserve original exception if available
            if hasattr(error, "cause") and error.cause:
                raise error.cause
            else:
                raise Exception(str(error))
        return result.unwrap()

    @staticmethod
    def monitor_result_usage(
        func: Callable[..., Result[T, Error]]
    ) -> Callable[..., Result[T, Error]]:
        """Monitor usage of Result-based functions for migration tracking.

        Args:
            func: Result-based function to monitor

        Returns:
            Wrapped function that logs usage statistics
        """
        usage_count = 0

        def wrapper(*args: object, **kwargs: object) -> Result[T, Error]:
            nonlocal usage_count
            usage_count += 1

            # Log usage for migration tracking
            import structlog

            logger = structlog.get_logger(__name__)
            logger.info(
                "result_function_usage",
                function=func.__name__,
                usage_count=usage_count,
            )

            return func(*args, **kwargs)

        return wrapper


# Global compatibility instance
_compat = ResultCompat()

# Convenience aliases
wrap_function = _compat.wrap_function
adapt_result_for_exception_code = _compat.adapt_result_for_exception_code
monitor_result_usage = _compat.monitor_result_usage


# Migration decorators
@overload
def migrate_step1(
    *,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    error_type: Type[Error] = DatabaseError,
) -> Callable[[Callable[..., T]], Callable[..., T]]: ...


@overload
def migrate_step1(
    func: Callable[..., T],
    *,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    error_type: Type[Error] = DatabaseError,
) -> Callable[..., T]: ...


def migrate_step1(
    func: Callable[..., T] | None = None,
    *,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    error_type: Type[Error] = DatabaseError,
) -> Callable[..., T] | Callable[[Callable[..., T]], Callable[..., T]]:
    """Step 1 of migration: Wrap functions to use Result internally.

    This decorator wraps functions to catch exceptions and convert to Result
    internally while maintaining the same external interface.

    Step 2 would be to change the return type to Result[T, E]
    Step 3 would be to update callers to handle Result types

    Args:
        func: Function to wrap (or None if used as decorator)
        exceptions: Exceptions to catch
        error_type: Error type to use

    Returns:
        Decorator or wrapped function
    """

    def decorator(f: Callable[..., T]) -> Callable[..., T]:
        return wrap_function(f, exceptions=exceptions, error_type=error_type)

    if func is not None:
        return decorator(func)
    return decorator


def result_to_exception(result: Result[T, Error]) -> T:
    """Convert a Result to exception-throwing behavior (for temporary compatibility).

    Args:
        result: Result to convert

    Returns:
        Success value

    Raises:
        Exception: If result is Err
    """
    return adapt_result_for_exception_code(result)


# Context manager for temporary compatibility zones
class CompatibilityZone:
    """Context manager for sections of code still using exception pattern.

    Usage:
        with CompatibilityZone("legacy_service"):
            # Code that still uses exceptions
            result = some_legacy_function()
    """

    def __init__(self, zone_name: str):
        self.zone_name = zone_name

    def __enter__(self) -> "CompatibilityZone":
        warnings.warn(
            f"Entering compatibility zone: {self.zone_name}",
            CompatibilityWarning,
            stacklevel=2,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_val is not None:
            # Log exceptions in compatibility zones
            import structlog

            logger = structlog.get_logger(__name__)
            logger.warning(
                "exception_in_compatibility_zone",
                zone=self.zone_name,
                exception_type=type(exc_val).__name__,
                exception_message=str(exc_val),
            )


# Migration tracking
class MigrationTracker:
    """Track migration progress from exceptions to Result pattern."""

    def __init__(self) -> None:
        self.migrated_functions: set[str] = set()
        self.legacy_functions: set[str] = set()
        self.compatibility_warnings: list[str] = []

    def mark_migrated(self, function_name: str) -> None:
        """Mark a function as fully migrated to Result pattern."""
        self.migrated_functions.add(function_name)
        if function_name in self.legacy_functions:
            self.legacy_functions.remove(function_name)

    def mark_legacy(self, function_name: str) -> None:
        """Mark a function as still using exception pattern."""
        self.legacy_functions.add(function_name)

    def log_compatibility_warning(self, message: str) -> None:
        """Log a compatibility warning."""
        self.compatibility_warnings.append(message)

    def get_migration_report(self) -> str:
        """Generate a migration progress report."""
        total = len(self.migrated_functions) + len(self.legacy_functions)
        if total == 0:
            return "No functions tracked yet."

        migrated_pct = len(self.migrated_functions) / total * 100
        lines = [
            "# Result Pattern Migration Progress",
            "",
            f"Progress: {migrated_pct:.1f}% ({len(self.migrated_functions)}/{total})",
            "",
            "## Migrated Functions",
            "",
        ]
        for func in sorted(self.migrated_functions):
            lines.append(f"- ✅ {func}")

        lines.extend(
            [
                "",
                "## Legacy Functions (Need Migration)",
                "",
            ]
        )
        for func in sorted(self.legacy_functions):
            lines.append(f"- ❌ {func}")

        if self.compatibility_warnings:
            lines.extend(
                [
                    "",
                    "## Compatibility Warnings",
                    "",
                ]
            )
            for warning in self.compatibility_warnings[-10:]:  # Show last 10
                lines.append(f"- ⚠️  {warning}")

        return "\n".join(lines)

    def get_state(self) -> dict[str, object]:
        """Return structured migration state for tooling/CI."""
        return {
            "migrated": sorted(self.migrated_functions),
            "legacy": sorted(self.legacy_functions),
            "compatibility_warnings": list(self.compatibility_warnings),
        }


# Global migration tracker
_migration_tracker = MigrationTracker()


# Convenience functions for tracking
def mark_migrated(function_name: str) -> None:
    """Mark a function as migrated."""
    _migration_tracker.mark_migrated(function_name)


def mark_legacy(function_name: str) -> None:
    """Mark a function as legacy."""
    _migration_tracker.mark_legacy(function_name)


def get_migration_report() -> str:
    """Get migration progress report."""
    return _migration_tracker.get_migration_report()


def get_migration_state() -> dict[str, object]:
    """Expose structured migration tracker data."""
    return _migration_tracker.get_state()


# Example usage patterns
def example_compatibility_usage() -> None:
    """Show example usage of compatibility layer."""

    # Pattern 1: Wrap legacy function
    @migrate_step1(exceptions=(ValueError, TypeError))
    def legacy_function(x: int) -> int:
        if x < 0:
            raise ValueError("x must be positive")
        return x * 2

    # Pattern 2: Use compatibility zone
    def some_migration_function() -> Result[int, Error]:
        with CompatibilityZone("legacy_service_integration"):
            # Still using exceptions here
            legacy_result = legacy_function(5)
            return Ok(legacy_result)

    # Pattern 3: Monitor Result usage
    @monitor_result_usage
    def new_result_function() -> Result[int, Error]:
        return Ok(42)

    # Invoke examples so that helper functions are actually exercised
    _ = some_migration_function()
    _ = new_result_function()

    print("Compatibility layer examples completed")


if __name__ == "__main__":
    example_compatibility_usage()
