"""SQL error mapping and connection pool error management for Result-based error handling.

This module provides utilities to map PostgreSQL and asyncpg errors to our Result types,
handle connection pool errors, and provide proper error context for debugging.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

import asyncpg

from src.infra.result import DatabaseError, Err, Ok, Result, SystemError

T = TypeVar("T")

# asyncpg 並未在型別註解中公開 PoolError，因此以 getattr 動態取得，並提供合理的型別。
PoolError: type[BaseException] = getattr(asyncpg, "PoolError", Exception)

# PostgreSQL error codes that we handle
POSTGRES_ERROR_CODES = {
    # Connection errors
    "08000": "connection_exception",
    "08003": "connection_does_not_exist",
    "08006": "connection_failure",
    "08001": "sqlclient_unable_to_establish_sqlconnection",
    "08004": "sqlserver_rejected_establishment_of_sqlconnection",
    # Integrity constraint violations
    "23000": "integrity_constraint_violation",
    "23001": "restrict_violation",
    "23502": "not_null_violation",
    "23503": "foreign_key_violation",
    "23505": "unique_violation",
    "23514": "check_violation",
    "23P01": "exclusion_violation",
    # Transaction errors
    "25000": "invalid_transaction_state",
    "25001": "active_sql_transaction",
    "25002": "branch_transaction_already_active",
    "25008": "held_cursor_requires_same_isolation_level",
    "25003": "inappropriate_access_mode_for_branch_transaction",
    "25004": "inappropriate_isolation_level_for_branch_transaction",
    "25005": "no_active_sql_transaction_for_branch_transaction",
    "25006": "read_only_sql_transaction",
    "25007": "schema_and_data_statement_mixing_not_supported",
    # Lock/Deadlock errors
    "40001": "serialization_failure",
    "40P01": "deadlock_detected",
    # Timeout errors
    "57014": "query_canceled",
    "72000": "snapshot_too_old",
    # Configuration errors
    "42P01": "undefined_table",
    "42P02": "undefined_parameter",
    "42703": "undefined_column",
    "42883": "undefined_function",
    "42P03": "duplicate_cursor",
    "42P04": "duplicate_database",
    "42710": "duplicate_object",
    "42704": "undefined_object",
}


def map_postgres_error(error: asyncpg.PostgresError) -> DatabaseError:
    """Map a PostgreSQL error to our DatabaseError type with appropriate context.

    Args:
        error: The asyncpg PostgresError exception

    Returns:
        DatabaseError with appropriate category and context
    """
    raw_sqlstate = getattr(error, "sqlstate", None)
    sqlstate: str | None = str(raw_sqlstate) if raw_sqlstate is not None else None
    message = str(error)

    # Base context with error details
    context: Dict[str, Any] = {
        "sqlstate": sqlstate,
        "error_type": (
            POSTGRES_ERROR_CODES.get(sqlstate, "unknown_postgres_error")
            if sqlstate is not None
            else "unknown_postgres_error"
        ),
        "original_message": message,
    }

    # Best-effort table/schema metadata for observability
    table_name = getattr(error, "table_name", None)
    if table_name:
        context["table_name"] = table_name
    schema_name = getattr(error, "schema_name", None)
    if schema_name:
        context["schema_name"] = schema_name

    # Add additional context based on error type
    if sqlstate == "23505":  # unique_violation
        # Extract constraint name if available
        constraint_name = getattr(error, "constraint_name", None)
        if constraint_name:
            context["constraint_name"] = constraint_name
        # Extract detail about which values caused the violation
        detail = getattr(error, "detail", None)
        if detail:
            context["detail"] = detail

    elif sqlstate == "23503":  # foreign_key_violation
        constraint_name = getattr(error, "constraint_name", None)
        if constraint_name:
            context["constraint_name"] = constraint_name
        detail = getattr(error, "detail", None)
        if detail:
            context["detail"] = detail

    elif sqlstate == "23502":  # not_null_violation
        column_name = getattr(error, "column_name", None)
        if column_name:
            context["column_name"] = column_name

    elif sqlstate == "40001":  # serialization_failure
        context["retry_possible"] = True

    elif sqlstate == "40P01":  # deadlock_detected
        context["retry_possible"] = True

    elif sqlstate == "57014":  # query_canceled
        context["timeout"] = True

    # Connection-related errors
    elif sqlstate is not None and sqlstate.startswith("08"):
        context["connection_error"] = True

    return DatabaseError(
        message=message,
        context=context,
        cause=error,
    )


def map_connection_pool_error(error: BaseException) -> SystemError:
    """Map asyncpg pool errors to our SystemError type.

    Args:
        error: The asyncpg PoolError exception

    Returns:
        SystemError with appropriate context
    """
    error_type = type(error).__name__
    message = str(error)

    context: Dict[str, Any] = {
        "error_type": error_type,
        "original_message": message,
        "pool_error": True,
    }

    # Add specific context based on error type
    if isinstance(error, asyncpg.TooManyConnectionsError):
        context["too_many_connections"] = True
        context["retry_possible"] = True
    elif isinstance(error, asyncpg.InterfaceError):
        context["interface_error"] = True
    elif isinstance(error, asyncpg.InterfaceWarning):
        context["interface_warning"] = True

    return SystemError(
        message=f"Connection pool error: {message}",
        context=context,
        cause=error,
    )


def map_asyncpg_error(error: BaseException) -> Result[Any, DatabaseError | SystemError]:
    """Map any asyncpg exception to a Result type.

    This is the main entry point for converting asyncpg errors to Results.

    Args:
        error: The exception from asyncpg

    Returns:
        Err containing the appropriate error type
    """
    if isinstance(error, asyncpg.PostgresError):
        return Err(map_postgres_error(error))
    elif isinstance(error, PoolError):
        return Err(map_connection_pool_error(error))
    elif isinstance(error, asyncpg.InterfaceError):
        return Err(
            SystemError(
                message=f"Database interface error: {error}",
                context={"interface_error": True, "original_error": str(error)},
                cause=error,
            )
        )
    elif isinstance(error, TimeoutError):
        return Err(
            SystemError(
                message=f"Database operation timed out: {error}",
                context={"timeout": True, "original_error": str(error)},
                cause=error,
            )
        )
    else:
        # Generic asyncpg error
        return Err(
            SystemError(
                message=f"Database error: {error}",
                context={"generic_db_error": True, "original_error": str(error)},
                cause=error,
            )
        )


def is_retryable_error(error: DatabaseError | SystemError) -> bool:
    """Check if an error is potentially retryable.

    Args:
        error: The error to check

    Returns:
        True if the error might succeed on retry
    """
    if isinstance(error, DatabaseError):
        sqlstate = error.context.get("sqlstate")
        if sqlstate in ("40001", "40P01", "57014"):  # serialization, deadlock, timeout
            return True
        if error.context.get("retry_possible"):
            return True
    else:
        # 此處可視為 SystemError；透過 context 判斷是否可重試
        if error.context.get("too_many_connections"):
            return True
        if error.context.get("retry_possible"):
            return True
    return False


class DatabaseErrorHandler:
    """Context manager for handling database operations with Result types."""

    def __init__(self, operation: str, context: Optional[Dict[str, Any]] = None):
        self.operation = operation
        self.context = context or {}
        self.start_time: Optional[float] = None
        self.last_result: Result[None, DatabaseError | SystemError] | None = None

    async def __aenter__(self) -> "DatabaseErrorHandler":
        import time

        self.start_time = time.time()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        import time

        duration = time.time() - self.start_time if self.start_time else None

        if exc_val is not None:
            # Add operation context before mapping
            if isinstance(exc_val, (asyncpg.PostgresError, PoolError)):
                # These errors will have context added in map_asyncpg_error
                pass
            else:
                # Add context to other exceptions
                self.context.update(
                    {
                        "operation": self.operation,
                        "duration_seconds": duration,
                    }
                )
            self.last_result = map_asyncpg_error(exc_val)
            return False

        self.last_result = Ok(None)
        return False


def with_db_error_handler(
    operation: str,
    context: Optional[Dict[str, Any]] = None,
) -> Callable[
    [Callable[..., Awaitable[T]]],
    Callable[..., Awaitable[Result[T, DatabaseError | SystemError]]],
]:
    """Decorator for database operations that handles errors and returns Result types.

    Args:
        operation: Name of the database operation for logging
        context: Additional context to include in errors

    Returns:
        Decorator that wraps async functions to handle database errors
    """
    from functools import wraps

    def decorator(
        func: Callable[..., Awaitable[T]]
    ) -> Callable[..., Awaitable[Result[T, DatabaseError | SystemError]]]:
        @wraps(func)
        async def wrapper(
            *args: object, **kwargs: object
        ) -> Result[T, DatabaseError | SystemError]:
            try:
                async with DatabaseErrorHandler(operation, context):
                    result = await func(*args, **kwargs)
                    return Ok(result)
            except BaseException as e:
                # This should not happen if the context manager works correctly,
                # but we handle it just in case
                return map_asyncpg_error(e)

            # Defensive: this point should be unreachable, but we keep an explicit
            # raise so that static type checkers see the function as total.
            raise AssertionError("with_db_error_handler.wrapper reached unreachable state")

        return wrapper

    return decorator
