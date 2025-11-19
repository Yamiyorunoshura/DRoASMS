from __future__ import annotations

import asyncio

import pytest

from src.infra.result import (
    AsyncResult,
    DatabaseError,
    Err,
    Error,
    Ok,
    Result,
    async_returns_result,
    collect,
    get_error_metrics,
    reset_error_metrics,
    result_from_exception,
    returns_result,
    safe_async_call,
    safe_call,
    sequence,
)


@pytest.mark.unit
def test_ok_and_err_basic_methods() -> None:
    ok_value: Result[int, Error] = Ok(10)
    assert ok_value.is_ok()
    assert not ok_value.is_err()
    assert ok_value.unwrap() == 10
    # 迭代支援：Ok 應該產出單一值
    assert list(ok_value) == [10]

    err_value: Result[int, Error] = Err(Error("failure"))
    assert not err_value.is_ok()
    assert err_value.is_err()
    assert err_value.unwrap_err().message == "failure"
    with pytest.raises(RuntimeError):
        err_value.unwrap()
    # 迭代支援：Err 視為空集合
    assert list(err_value) == []


@pytest.mark.unit
def test_result_map_and_then_chaining() -> None:
    base: Result[int, Error] = Ok(2)

    mapped = base.map(lambda x: x * 3)
    assert isinstance(mapped, Ok)
    assert mapped.unwrap() == 6

    chained = mapped.and_then(lambda x: Ok(x + 1))
    assert isinstance(chained, Ok)
    assert chained.unwrap() == 7

    err: Result[int, Error] = Err(Error("bad"))
    assert isinstance(err.map(lambda x: x * 2), Err)
    assert isinstance(err.and_then(lambda x: Ok(x * 2)), Err)


@pytest.mark.unit
def test_collect_and_sequence() -> None:
    ok_list = [Ok(1), Ok(2), Ok(3)]
    collected = collect(ok_list)
    assert isinstance(collected, Ok)
    assert collected.unwrap() == [1, 2, 3]

    mixed: list[Result[int, Error]] = [Ok(1), Err(Error("x")), Ok(3)]
    seq = sequence(mixed)
    assert isinstance(seq, Err)
    assert seq.unwrap_err().message == "x"


@pytest.mark.unit
def test_safe_call_and_safe_async_call() -> None:
    def succeed(x: int) -> int:
        return x * 2

    def fail(_: int) -> int:
        raise ValueError("boom")

    ok_result = safe_call(succeed, 5)
    assert isinstance(ok_result, Ok)
    assert ok_result.unwrap() == 10

    err_result = safe_call(fail, 1)
    assert isinstance(err_result, Err)

    async def async_succeed(x: int) -> int:
        return x + 1

    async def async_fail(_: int) -> int:
        raise RuntimeError("async boom")

    ok_async = asyncio.get_event_loop().run_until_complete(safe_async_call(async_succeed, 5))
    assert isinstance(ok_async, Ok)
    assert ok_async.unwrap() == 6

    err_async = asyncio.get_event_loop().run_until_complete(safe_async_call(async_fail, 0))
    assert isinstance(err_async, Err)


@pytest.mark.asyncio
async def test_async_result_map_and_map_err() -> None:
    async def make_result_ok() -> Result[int, Error]:
        return Ok(5)

    base = AsyncResult(make_result_ok())
    mapped = await base.map(lambda x: x * 2)
    final = await mapped
    assert isinstance(final, Ok)
    assert final.unwrap() == 10

    async def make_result_err() -> Result[int, Error]:
        return Err(Error("db error"))

    base_err = AsyncResult(make_result_err())
    mapped_err = await base_err.map_err(lambda e: DatabaseError(e.message))
    final_err = await mapped_err
    assert isinstance(final_err, Err)
    assert isinstance(final_err.unwrap_err(), DatabaseError)


@pytest.mark.unit
def test_returns_result_with_exception_map() -> None:
    class CustomDatabaseError(Error):
        """自定義錯誤型別，用於測試 exception_map。"""

    @returns_result(exception_map={ValueError: CustomDatabaseError})
    def may_fail(flag: bool) -> int:
        if flag:
            raise ValueError("bad")
        raise RuntimeError("boom")

    err_on_value: Result[int, Error] = may_fail(True)
    assert isinstance(err_on_value, Err)
    mapped_error = err_on_value.unwrap_err()
    assert isinstance(mapped_error, CustomDatabaseError)

    err_on_runtime: Result[int, Error] = may_fail(False)
    assert isinstance(err_on_runtime, Err)
    default_error = err_on_runtime.unwrap_err()
    # RuntimeError 應使用預設 Error 型別
    assert type(default_error) is Error


@pytest.mark.unit
def test_result_from_exception_and_decorators() -> None:
    exc = RuntimeError("db down")
    err_result = result_from_exception(exc, default_error=DatabaseError)
    assert isinstance(err_result, Err)
    assert isinstance(err_result.unwrap_err(), DatabaseError)

    @returns_result()
    def may_fail(flag: bool) -> int:
        if flag:
            raise ValueError("bad flag")
        return 42

    ok_val = may_fail(False)
    assert isinstance(ok_val, Ok)
    assert ok_val.unwrap() == 42

    err_val = may_fail(True)
    assert isinstance(err_val, Err)


@pytest.mark.asyncio
async def test_async_returns_result_decorator() -> None:
    @async_returns_result()
    async def async_may_fail(flag: bool) -> str:
        if flag:
            raise RuntimeError("oops")
        return "ok"

    ok_res = await async_may_fail(False)
    assert isinstance(ok_res, Ok)
    assert ok_res.unwrap() == "ok"

    err_res = await async_may_fail(True)
    assert isinstance(err_res, Err)


@pytest.mark.asyncio
async def test_async_returns_result_with_exception_map() -> None:
    class CustomDatabaseError(Error):
        """自定義錯誤型別，用於測試 async exception_map。"""

    @async_returns_result(exception_map={ValueError: CustomDatabaseError})
    async def async_may_fail(flag: bool) -> str:
        if flag:
            raise ValueError("bad")
        raise RuntimeError("boom")

    err_on_value = await async_may_fail(True)
    assert isinstance(err_on_value, Err)
    mapped_error = err_on_value.unwrap_err()
    assert isinstance(mapped_error, CustomDatabaseError)

    err_on_runtime = await async_may_fail(False)
    assert isinstance(err_on_runtime, Err)
    default_error = err_on_runtime.unwrap_err()
    assert type(default_error) is Error


@pytest.mark.unit
def test_error_metrics_counter_updates() -> None:
    reset_error_metrics()

    def fail(_: int) -> int:
        raise ValueError("boom")

    # 觸發一次 safe_call 失敗
    result = safe_call(fail, 1)
    assert isinstance(result, Err)

    metrics = get_error_metrics()
    # 至少應該有一筆 Error 類型與總計
    assert metrics.get("Error", 0) >= 1
    assert metrics.get("__total__", 0) >= metrics.get("Error", 0)
