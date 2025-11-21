"""Unit tests for canonical Result<T,E> implementation."""

from __future__ import annotations

import asyncio

import pytest

from src.infra.result import (
    AsyncResult,
    BusinessLogicError,
    DatabaseError,
    Err,
    Error,
    Ok,
    Result,
    ValidationError,
    async_returns_result,
    collect,
    err,
    ok,
    result_from_exception,
    returns_result,
    safe_async_call,
    safe_call,
    sequence,
)


class TestBasicResult:
    def test_ok_behaviour(self) -> None:
        result = Ok[int, Error](42)
        assert result.is_ok() is True
        assert result.is_err() is False
        assert result.unwrap() == 42
        assert list(result) == [42]

    def test_err_behaviour(self) -> None:
        error = ValidationError("boom", context={"field": "email"})
        result = Err[int, ValidationError](error)

        assert result.is_err() is True
        assert result.unwrap_err() is error
        assert result.unwrap_or(0) == 0
        with pytest.raises(RuntimeError):
            result.unwrap()

    def test_map_and_and_then(self) -> None:
        result = Ok[int, Error](2).map(lambda v: v * 3)
        assert isinstance(result, Ok)
        assert result.unwrap() == 6

        chained = result.and_then(lambda v: Ok[str, Error](f"value={v}"))
        assert chained.unwrap() == "value=6"

        err_chain = Err[int, Error](Error("nope"))
        assert isinstance(err_chain.map(lambda _: 1), Err)

    def test_sequence_helpers(self) -> None:
        ok_list = collect([Ok(1), Ok(2), Ok(3)])
        assert ok_list.unwrap() == [1, 2, 3]

        err_result = Err[int, Error](Error("bad"))
        aggregated = collect([Ok(1), err_result, Ok(3)])
        assert aggregated.is_err() is True
        assert aggregated.unwrap_err() is err_result.error

        assert sequence([Ok("a"), Ok("b")]).unwrap() == ["a", "b"]


class TestHelpers:
    def test_safe_call_maps_exceptions(self) -> None:
        def raise_error() -> None:
            raise ValueError("boom")

        result = safe_call(raise_error, error_type=ValidationError)
        assert result.is_err()
        err_obj = result.unwrap_err()
        assert isinstance(err_obj, ValidationError)
        assert err_obj.message == "boom"

    @pytest.mark.asyncio
    async def test_safe_async_call_handles_async(self) -> None:
        async def add_one(x: int) -> int:
            await asyncio.sleep(0)
            return x + 1

        result = await safe_async_call(add_one, 1)
        assert result.unwrap() == 2

    def test_returns_result_decorator(self) -> None:
        @returns_result(ValidationError)
        def validate_positive(value: int) -> int:
            if value <= 0:
                raise ValueError("must be positive")
            return value

        assert validate_positive(1).unwrap() == 1
        neg = validate_positive(-5)
        assert neg.is_err()
        assert isinstance(neg.unwrap_err(), ValidationError)

    @pytest.mark.asyncio
    async def test_async_returns_result_preserves_existing_result(self) -> None:
        call_count = 0

        @async_returns_result()
        async def maybe_result(flag: bool) -> Result[int, Error] | int:
            nonlocal call_count
            call_count += 1
            if flag:
                return Ok(7)
            return Err(Error("boom"))

        ok_result = await maybe_result(True)
        assert ok_result.unwrap() == 7

        err_result = await maybe_result(False)
        assert err_result.is_err()
        assert isinstance(err_result.unwrap_err(), Error)
        assert call_count == 2

    def test_result_from_exception_reuses_error(self) -> None:
        original = ValidationError("custom")
        wrapped = result_from_exception(original)
        assert wrapped.is_err()
        assert wrapped.unwrap_err() is original

    def test_err_helper(self) -> None:
        error = BusinessLogicError("rule broken")
        result = err(error)
        assert result.is_err()
        assert result.unwrap_err() is error

    def test_ok_helper(self) -> None:
        result = ok({"value": 1})
        assert result.unwrap() == {"value": 1}


class TestAsyncResultWrapper:
    @pytest.mark.asyncio
    async def test_async_result_map(self) -> None:
        async def compute() -> Result[int, Error]:
            return Ok(5)

        wrapper = AsyncResult(compute())
        mapped = await wrapper.map(lambda x: x * 2)
        final = await mapped
        assert final.unwrap() == 10

    @pytest.mark.asyncio
    async def test_async_result_map_err(self) -> None:
        async def fail() -> Result[int, Error]:
            return Err(Error("nope"))

        wrapper = AsyncResult(fail())
        mapped = await wrapper.map_err(lambda err_obj: DatabaseError(str(err_obj)))
        final = await mapped
        assert final.is_err()
        assert isinstance(final.unwrap_err(), DatabaseError)
