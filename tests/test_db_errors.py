"""Tests for database error mapping helpers."""

from __future__ import annotations

import asyncpg
import pytest

import src.infra.db_errors as db_errors_module
from src.infra.db_errors import (
    DatabaseErrorHandler,
    is_retryable_error,
    map_asyncpg_error,
    map_connection_pool_error,
    map_postgres_error,
    with_db_error_handler,
)
from src.infra.result import DatabaseError, Err, Ok, SystemError


def _build_pg_error(sqlstate: str, detail: str | None = None) -> asyncpg.PostgresError:
    error = asyncpg.PostgresError(f"error-{sqlstate}")
    error.sqlstate = sqlstate
    # 提供最小但具代表性的表/約束上下文，驗證 DatabaseError context 內容
    error.table_name = "accounts"
    error.schema_name = "public"
    if detail:
        error.detail = detail
    error.constraint_name = "uniq_accounts"
    return error


def test_map_postgres_error_sets_context() -> None:
    pg_error = _build_pg_error("23505", detail="duplicate key")
    mapped = map_postgres_error(pg_error)

    assert isinstance(mapped, DatabaseError)
    assert mapped.context["sqlstate"] == "23505"
    assert mapped.context["constraint_name"] == "uniq_accounts"
    assert "duplicate" in mapped.context["detail"]
    # 新增：表/結構描述上下文，符合 error-handling 規格
    assert mapped.context["table_name"] == "accounts"
    assert mapped.context["schema_name"] == "public"


def test_map_connection_pool_error_marks_retryable() -> None:
    pool_error = asyncpg.TooManyConnectionsError("pool full")
    mapped = map_connection_pool_error(pool_error)

    assert isinstance(mapped, SystemError)
    assert mapped.context["too_many_connections"] is True
    assert mapped.context["retry_possible"] is True


def test_map_asyncpg_error_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyPoolError(Exception):
        pass

    monkeypatch.setattr(db_errors_module, "PoolError", DummyPoolError, raising=False)

    result = map_asyncpg_error(TimeoutError("db slow"))

    assert isinstance(result, Err)
    err_obj = result.unwrap_err()
    assert isinstance(err_obj, SystemError)
    assert err_obj.context["timeout"] is True


def test_map_asyncpg_error_postgres_err() -> None:
    pg_error = _build_pg_error("40001")
    result = map_asyncpg_error(pg_error)

    assert isinstance(result, Err)
    err_obj = result.unwrap_err()
    assert isinstance(err_obj, DatabaseError)
    assert err_obj.context["retry_possible"] is True


def test_is_retryable_error_for_system_error() -> None:
    system_error = SystemError("pool busy", context={"too_many_connections": True})
    assert is_retryable_error(system_error) is True

    generic = SystemError("generic", context={})
    assert is_retryable_error(generic) is False


@pytest.mark.asyncio
async def test_with_db_error_handler_success() -> None:
    @with_db_error_handler("fetch")
    async def fetch_row() -> int:
        return 10

    result = await fetch_row()
    assert isinstance(result, Ok)
    assert result.unwrap() == 10


@pytest.mark.asyncio
async def test_with_db_error_handler_maps_exception() -> None:
    @with_db_error_handler("insert")
    async def insert_row() -> int:
        raise _build_pg_error("23503")

    result = await insert_row()
    assert result.is_err()
    assert isinstance(result.unwrap_err(), DatabaseError)


@pytest.mark.asyncio
async def test_database_error_handler_direct_usage() -> None:
    handler = DatabaseErrorHandler("insert")
    await handler.__aenter__()  # start context manager without raising
    rv = await handler.__aexit__(None, None, None)
    assert rv is False
    assert handler.last_result is not None and handler.last_result.is_ok()
