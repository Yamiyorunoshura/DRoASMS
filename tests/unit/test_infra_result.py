"""完整的 Result 模組單元測試，目標覆蓋率 80%+。

此測試套件涵蓋：
- Ok 和 Err 的基本操作
- map, map_err, and_then, or_else 等組合器
- unwrap, unwrap_or, unwrap_or_else 等取值方法
- is_ok, is_err 判斷方法
- 錯誤型別階層
- 敏感資訊遮罩
- 錯誤統計功能
- AsyncResult 包裝器
- 裝飾器（returns_result, async_returns_result）
- 邊界情況和錯誤處理
"""

from __future__ import annotations

import pytest

from src.infra.result import (
    AsyncResult,
    BusinessLogicError,
    DatabaseError,
    DiscordError,
    Err,
    Error,
    Ok,
    PermissionDeniedError,
    Result,
    SystemError,
    ValidationError,
    async_returns_result,
    collect,
    err,
    get_error_metrics,
    ok,
    reset_error_metrics,
    result_from_exception,
    returns_result,
    safe_async_call,
    safe_call,
    sequence,
)


@pytest.mark.unit
class TestOkBasicOperations:
    """測試 Ok 的基本操作。"""

    def test_ok_is_ok_and_is_err(self) -> None:
        """測試 Ok 的 is_ok 和 is_err 方法。"""
        result: Result[int, Error] = Ok(42)
        assert result.is_ok() is True
        assert result.is_err() is False

    def test_ok_unwrap(self) -> None:
        """測試 Ok 的 unwrap 方法。"""
        result: Result[str, Error] = Ok("success")
        assert result.unwrap() == "success"

    def test_ok_unwrap_err_raises(self) -> None:
        """測試在 Ok 上呼叫 unwrap_err 會拋出異常。"""
        result: Result[int, Error] = Ok(100)
        with pytest.raises(RuntimeError, match="Called unwrap_err\\(\\) on Ok value"):
            result.unwrap_err()

    def test_ok_unwrap_or(self) -> None:
        """測試 Ok 的 unwrap_or 方法返回內部值。"""
        result: Result[int, Error] = Ok(42)
        assert result.unwrap_or(0) == 42

    def test_ok_unwrap_or_else(self) -> None:
        """測試 Ok 的 unwrap_or_else 方法返回內部值。"""
        result: Result[int, Error] = Ok(42)
        assert result.unwrap_or_else(lambda: 0) == 42

    def test_ok_iteration(self) -> None:
        """測試 Ok 的迭代支援。"""
        result: Result[int, Error] = Ok(42)
        assert list(result) == [42]


@pytest.mark.unit
class TestErrBasicOperations:
    """測試 Err 的基本操作。"""

    def test_err_is_ok_and_is_err(self) -> None:
        """測試 Err 的 is_ok 和 is_err 方法。"""
        result: Result[int, Error] = Err(Error("failed"))
        assert result.is_ok() is False
        assert result.is_err() is True

    def test_err_unwrap_raises(self) -> None:
        """測試在 Err 上呼叫 unwrap 會拋出異常。"""
        result: Result[int, Error] = Err(Error("boom"))
        with pytest.raises(RuntimeError, match="Called unwrap\\(\\) on Err value"):
            result.unwrap()

    def test_err_unwrap_err(self) -> None:
        """測試 Err 的 unwrap_err 方法。"""
        error = Error("failed")
        result: Result[int, Error] = Err(error)
        assert result.unwrap_err() is error

    def test_err_unwrap_or(self) -> None:
        """測試 Err 的 unwrap_or 方法返回預設值。"""
        result: Result[int, Error] = Err(Error("failed"))
        assert result.unwrap_or(99) == 99

    def test_err_unwrap_or_else(self) -> None:
        """測試 Err 的 unwrap_or_else 方法。"""
        result: Result[int, Error] = Err(Error("failed"))
        assert result.unwrap_or_else(lambda: 88) == 88

    def test_err_iteration(self) -> None:
        """測試 Err 的迭代支援（空集合）。"""
        result: Result[int, Error] = Err(Error("failed"))
        assert list(result) == []


@pytest.mark.unit
class TestMapOperations:
    """測試 map 和 map_err 組合器。"""

    def test_ok_map(self) -> None:
        """測試 Ok 的 map 操作。"""
        result: Result[int, Error] = Ok(10)
        mapped = result.map(lambda x: x * 2)
        assert isinstance(mapped, Ok)
        assert mapped.unwrap() == 20

    def test_err_map(self) -> None:
        """測試 Err 的 map 操作（不改變錯誤）。"""
        error = Error("original")
        result: Result[int, Error] = Err(error)
        mapped = result.map(lambda x: x * 2)
        assert isinstance(mapped, Err)
        assert mapped.unwrap_err() is error

    def test_ok_map_err(self) -> None:
        """測試 Ok 的 map_err 操作（不改變成功值）。"""
        result: Result[int, Error] = Ok(10)
        mapped = result.map_err(lambda e: DatabaseError(str(e)))
        assert isinstance(mapped, Ok)
        assert mapped.unwrap() == 10

    def test_err_map_err(self) -> None:
        """測試 Err 的 map_err 操作。"""
        result: Result[int, Error] = Err(Error("generic error"))
        mapped = result.map_err(lambda e: DatabaseError(e.message))
        assert isinstance(mapped, Err)
        error = mapped.unwrap_err()
        assert isinstance(error, DatabaseError)
        assert error.message == "generic error"


@pytest.mark.unit
class TestAndThenOrElseOperations:
    """測試 and_then 和 or_else 組合器。"""

    def test_ok_and_then(self) -> None:
        """測試 Ok 的 and_then 操作。"""
        result: Result[int, Error] = Ok(5)
        chained = result.and_then(lambda x: Ok(x * 3))
        assert isinstance(chained, Ok)
        assert chained.unwrap() == 15

    def test_ok_and_then_returns_err(self) -> None:
        """測試 Ok 的 and_then 可以返回 Err。"""
        result: Result[int, Error] = Ok(5)
        chained = result.and_then(lambda x: Err(Error("failed in chain")))
        assert isinstance(chained, Err)
        assert chained.unwrap_err().message == "failed in chain"

    def test_err_and_then(self) -> None:
        """測試 Err 的 and_then 操作（短路）。"""
        error = Error("original")
        result: Result[int, Error] = Err(error)
        chained = result.and_then(lambda x: Ok(x * 2))
        assert isinstance(chained, Err)
        assert chained.unwrap_err() is error

    def test_ok_or_else(self) -> None:
        """測試 Ok 的 or_else 操作（不執行恢復函數）。"""
        result: Result[int, Error] = Ok(42)
        recovered = result.or_else(lambda e: Ok(0))
        assert isinstance(recovered, Ok)
        assert recovered.unwrap() == 42

    def test_err_or_else(self) -> None:
        """測試 Err 的 or_else 操作（執行恢復函數）。"""
        result: Result[int, Error] = Err(Error("failed"))
        recovered = result.or_else(lambda e: Ok(999))
        assert isinstance(recovered, Ok)
        assert recovered.unwrap() == 999

    def test_err_or_else_returns_err(self) -> None:
        """測試 Err 的 or_else 可以返回另一個 Err。"""
        result: Result[int, Error] = Err(Error("first error"))
        recovered = result.or_else(lambda e: Err(DatabaseError("second error")))
        assert isinstance(recovered, Err)
        assert isinstance(recovered.unwrap_err(), DatabaseError)


@pytest.mark.unit
class TestErrorTypes:
    """測試錯誤型別階層。"""

    def test_error_basic_creation(self) -> None:
        """測試基礎 Error 創建。"""
        error = Error("test message")
        assert error.message == "test message"
        assert error.context == {}
        assert error.cause is None

    def test_error_with_context(self) -> None:
        """測試帶 context 的 Error。"""
        error = Error("test", context={"user_id": 123, "guild_id": 456})
        assert error.context == {"user_id": 123, "guild_id": 456}

    def test_error_with_cause(self) -> None:
        """測試帶 cause 的 Error。"""
        cause = ValueError("root cause")
        error = Error("wrapped", cause=cause)
        assert error.cause is cause

    def test_error_to_dict(self) -> None:
        """測試 Error.to_dict() 方法。"""
        cause = ValueError("root cause")
        error = Error("test", context={"key": "value"}, cause=cause)
        result = error.to_dict()
        assert result["message"] == "test"
        assert result["context"] == {"key": "value"}
        assert "ValueError" in result["cause"]

    def test_error_to_dict_no_cause(self) -> None:
        """測試沒有 cause 時的 to_dict()。"""
        error = Error("test")
        result = error.to_dict()
        assert result["cause"] is None

    def test_database_error(self) -> None:
        """測試 DatabaseError 子類型。"""
        error = DatabaseError("connection failed")
        assert isinstance(error, Error)
        assert error.message == "connection failed"

    def test_discord_error(self) -> None:
        """測試 DiscordError 子類型。"""
        error = DiscordError("API rate limit")
        assert isinstance(error, Error)
        assert error.message == "API rate limit"

    def test_validation_error(self) -> None:
        """測試 ValidationError 子類型。"""
        error = ValidationError("invalid input")
        assert isinstance(error, Error)
        assert error.message == "invalid input"

    def test_business_logic_error(self) -> None:
        """測試 BusinessLogicError 子類型。"""
        error = BusinessLogicError("rule violation")
        assert isinstance(error, Error)
        assert error.message == "rule violation"

    def test_permission_denied_error(self) -> None:
        """測試 PermissionDeniedError 子類型。"""
        error = PermissionDeniedError("access denied")
        assert isinstance(error, Error)
        assert error.message == "access denied"

    def test_system_error(self) -> None:
        """測試 SystemError 子類型。"""
        error = SystemError("infrastructure failure")
        assert isinstance(error, Error)
        assert error.message == "infrastructure failure"


@pytest.mark.unit
class TestSensitiveDataSanitization:
    """測試敏感資訊遮罩功能。"""

    def test_sanitize_password(self) -> None:
        """測試密碼欄位遮罩。"""
        error = Error("auth failed", context={"password": "secret123", "username": "alice"})
        safe_context = error.log_safe_context()
        assert safe_context["password"] == "***redacted***"
        assert safe_context["username"] == "alice"

    def test_sanitize_api_key(self) -> None:
        """測試 API key 遮罩。"""
        error = Error("api error", context={"api_key": "abc123", "endpoint": "/users"})
        safe_context = error.log_safe_context()
        assert safe_context["api_key"] == "***redacted***"
        assert safe_context["endpoint"] == "/users"

    def test_sanitize_token(self) -> None:
        """測試 token 遮罩。"""
        error = Error("auth error", context={"token": "jwt.token.here", "user_id": 123})
        safe_context = error.log_safe_context()
        assert safe_context["token"] == "***redacted***"
        assert safe_context["user_id"] == 123

    def test_sanitize_nested_dict(self) -> None:
        """測試巢狀 dict 中的敏感資訊遮罩。"""
        error = Error(
            "error",
            context={
                "user": {"name": "alice", "password": "secret"},
                "api": {"endpoint": "/auth", "secret": "key123"},
            },
        )
        safe_context = error.log_safe_context()
        assert safe_context["user"]["password"] == "***redacted***"
        assert safe_context["user"]["name"] == "alice"
        assert safe_context["api"]["secret"] == "***redacted***"
        assert safe_context["api"]["endpoint"] == "/auth"

    def test_sanitize_case_insensitive(self) -> None:
        """測試遮罩是否不區分大小寫。"""
        error = Error(
            "error",
            context={"PASSWORD": "secret1", "ApiKey": "secret2", "Authorization": "Bearer token"},
        )
        safe_context = error.log_safe_context()
        assert safe_context["PASSWORD"] == "***redacted***"
        assert safe_context["ApiKey"] == "***redacted***"
        assert safe_context["Authorization"] == "***redacted***"

    def test_sanitize_empty_context(self) -> None:
        """測試空 context 的處理。"""
        error = Error("error", context=None)
        safe_context = error.log_safe_context()
        assert safe_context == {}


@pytest.mark.unit
class TestErrorMetrics:
    """測試錯誤統計功能。"""

    def test_error_metrics_increments(self) -> None:
        """測試錯誤統計計數器增加。"""
        reset_error_metrics()

        # 觸發幾個錯誤
        safe_call(lambda: 1 / 0)
        safe_call(lambda: 1 / 0)

        metrics = get_error_metrics()
        assert metrics["Error"] >= 2
        assert metrics["__total__"] >= 2

    def test_error_metrics_different_types(self) -> None:
        """測試不同錯誤型別的統計。"""
        reset_error_metrics()

        # 手動創建不同類型的錯誤並記錄
        from src.infra.result import _record_error

        _record_error(DatabaseError("db error"))
        _record_error(ValidationError("validation error"))
        _record_error(DatabaseError("another db error"))

        metrics = get_error_metrics()
        assert metrics["DatabaseError"] == 2
        assert metrics["ValidationError"] == 1
        assert metrics["__total__"] == 3

    def test_reset_error_metrics(self) -> None:
        """測試重置錯誤統計。"""
        reset_error_metrics()
        safe_call(lambda: 1 / 0)
        assert get_error_metrics()["__total__"] >= 1

        reset_error_metrics()
        assert get_error_metrics() == {}


@pytest.mark.unit
class TestHelperFunctions:
    """測試工具函數。"""

    def test_ok_helper(self) -> None:
        """測試 ok() 輔助函數。"""
        result = ok(42)
        assert isinstance(result, Ok)
        assert result.unwrap() == 42

    def test_err_helper(self) -> None:
        """測試 err() 輔助函數。"""
        error = Error("failed")
        result = err(error)
        assert isinstance(result, Err)
        assert result.unwrap_err() is error

    def test_collect_all_ok(self) -> None:
        """測試 collect() 處理全部成功的情況。"""
        results = [Ok(1), Ok(2), Ok(3)]
        collected = collect(results)
        assert isinstance(collected, Ok)
        assert collected.unwrap() == [1, 2, 3]

    def test_collect_with_err(self) -> None:
        """測試 collect() 遇到錯誤時短路。"""
        error = Error("failed")
        results: list[Result[int, Error]] = [Ok(1), Err(error), Ok(3)]
        collected = collect(results)
        assert isinstance(collected, Err)
        assert collected.unwrap_err() is error

    def test_sequence_alias(self) -> None:
        """測試 sequence() 是 collect() 的別名。"""
        results = [Ok("a"), Ok("b")]
        assert sequence(results).unwrap() == collect(results).unwrap()

    def test_result_from_exception_with_error(self) -> None:
        """測試 result_from_exception() 處理 Error 實例。"""
        original = ValidationError("custom")
        result = result_from_exception(original)
        assert isinstance(result, Err)
        assert result.unwrap_err() is original

    def test_result_from_exception_with_regular_exception(self) -> None:
        """測試 result_from_exception() 處理普通 Exception。"""
        exc = ValueError("boom")
        result = result_from_exception(exc, default_error=DatabaseError)
        assert isinstance(result, Err)
        error = result.unwrap_err()
        assert isinstance(error, DatabaseError)
        assert "boom" in error.message


@pytest.mark.unit
class TestSafeCall:
    """測試 safe_call() 函數。"""

    def test_safe_call_success(self) -> None:
        """測試 safe_call() 成功的情況。"""

        def add(a: int, b: int) -> int:
            return a + b

        result = safe_call(add, 1, 2)
        assert isinstance(result, Ok)
        assert result.unwrap() == 3

    def test_safe_call_exception(self) -> None:
        """測試 safe_call() 捕獲異常。"""

        def fail() -> None:
            raise ValueError("boom")

        result = safe_call(fail)
        assert isinstance(result, Err)
        assert "boom" in result.unwrap_err().message

    def test_safe_call_with_error_type(self) -> None:
        """測試 safe_call() 使用自定義錯誤型別。"""

        def fail() -> None:
            raise RuntimeError("error")

        result = safe_call(fail, error_type=DatabaseError)
        assert isinstance(result, Err)
        assert isinstance(result.unwrap_err(), DatabaseError)


@pytest.mark.unit
class TestSafeAsyncCall:
    """測試 safe_async_call() 函數。"""

    @pytest.mark.asyncio
    async def test_safe_async_call_success(self) -> None:
        """測試 safe_async_call() 成功的情況。"""

        async def async_add(a: int, b: int) -> int:
            return a + b

        result = await safe_async_call(async_add, 1, 2)
        assert isinstance(result, Ok)
        assert result.unwrap() == 3

    @pytest.mark.asyncio
    async def test_safe_async_call_exception(self) -> None:
        """測試 safe_async_call() 捕獲異常。"""

        async def async_fail() -> None:
            raise ValueError("async boom")

        result = await safe_async_call(async_fail)
        assert isinstance(result, Err)
        assert "async boom" in result.unwrap_err().message

    @pytest.mark.asyncio
    async def test_safe_async_call_with_error_type(self) -> None:
        """測試 safe_async_call() 使用自定義錯誤型別。"""

        async def async_fail() -> None:
            raise RuntimeError("error")

        result = await safe_async_call(async_fail, error_type=ValidationError)
        assert isinstance(result, Err)
        assert isinstance(result.unwrap_err(), ValidationError)


@pytest.mark.unit
class TestReturnsResultDecorator:
    """測試 returns_result 裝飾器。"""

    def test_returns_result_success(self) -> None:
        """測試裝飾器處理成功的情況。"""

        @returns_result()
        def add(a: int, b: int) -> int:
            return a + b

        result = add(1, 2)
        assert isinstance(result, Ok)
        assert result.unwrap() == 3

    def test_returns_result_exception(self) -> None:
        """測試裝飾器捕獲異常。"""

        @returns_result()
        def fail() -> None:
            raise ValueError("boom")

        result = fail()
        assert isinstance(result, Err)
        assert "boom" in result.unwrap_err().message

    def test_returns_result_with_error_type(self) -> None:
        """測試裝飾器使用自定義錯誤型別。"""

        @returns_result(DatabaseError)
        def fail() -> None:
            raise RuntimeError("db error")

        result = fail()
        assert isinstance(result, Err)
        assert isinstance(result.unwrap_err(), DatabaseError)

    def test_returns_result_with_exception_map(self) -> None:
        """測試裝飾器使用 exception_map。"""

        @returns_result(exception_map={ValueError: ValidationError, KeyError: DatabaseError})
        def maybe_fail(flag: str) -> str:
            if flag == "value":
                raise ValueError("validation failed")
            if flag == "key":
                raise KeyError("db failed")
            if flag == "other":
                raise RuntimeError("other error")
            return "ok"

        # ValueError -> ValidationError
        result1 = maybe_fail("value")
        assert isinstance(result1, Err)
        assert isinstance(result1.unwrap_err(), ValidationError)

        # KeyError -> DatabaseError
        result2 = maybe_fail("key")
        assert isinstance(result2, Err)
        assert isinstance(result2.unwrap_err(), DatabaseError)

        # RuntimeError -> 預設 Error
        result3 = maybe_fail("other")
        assert isinstance(result3, Err)
        assert type(result3.unwrap_err()) is Error

        # 成功情況
        result4 = maybe_fail("success")
        assert isinstance(result4, Ok)
        assert result4.unwrap() == "ok"


@pytest.mark.unit
class TestAsyncReturnsResultDecorator:
    """測試 async_returns_result 裝飾器。"""

    @pytest.mark.asyncio
    async def test_async_returns_result_success(self) -> None:
        """測試異步裝飾器處理成功的情況。"""

        @async_returns_result()
        async def async_add(a: int, b: int) -> int:
            return a + b

        result = await async_add(1, 2)
        assert isinstance(result, Ok)
        assert result.unwrap() == 3

    @pytest.mark.asyncio
    async def test_async_returns_result_exception(self) -> None:
        """測試異步裝飾器捕獲異常。"""

        @async_returns_result()
        async def async_fail() -> None:
            raise ValueError("async boom")

        result = await async_fail()
        assert isinstance(result, Err)
        assert "async boom" in result.unwrap_err().message

    @pytest.mark.asyncio
    async def test_async_returns_result_with_error_type(self) -> None:
        """測試異步裝飾器使用自定義錯誤型別。"""

        @async_returns_result(ValidationError)
        async def async_fail() -> None:
            raise RuntimeError("validation error")

        result = await async_fail()
        assert isinstance(result, Err)
        assert isinstance(result.unwrap_err(), ValidationError)

    @pytest.mark.asyncio
    async def test_async_returns_result_preserves_result(self) -> None:
        """測試異步裝飾器不會對已經是 Result 的返回值進行二次包裝。"""

        @async_returns_result()
        async def maybe_result(flag: bool) -> Result[int, Error] | int:
            if flag:
                return Ok(42)
            return Err(Error("failed"))

        result1 = await maybe_result(True)
        assert isinstance(result1, Ok)
        assert result1.unwrap() == 42

        result2 = await maybe_result(False)
        assert isinstance(result2, Err)
        assert result2.unwrap_err().message == "failed"

    @pytest.mark.asyncio
    async def test_async_returns_result_with_exception_map(self) -> None:
        """測試異步裝飾器使用 exception_map。"""

        @async_returns_result(exception_map={ValueError: ValidationError, KeyError: DatabaseError})
        async def async_maybe_fail(flag: str) -> str:
            if flag == "value":
                raise ValueError("validation failed")
            if flag == "key":
                raise KeyError("db failed")
            return "ok"

        result1 = await async_maybe_fail("value")
        assert isinstance(result1, Err)
        assert isinstance(result1.unwrap_err(), ValidationError)

        result2 = await async_maybe_fail("key")
        assert isinstance(result2, Err)
        assert isinstance(result2.unwrap_err(), DatabaseError)

    @pytest.mark.asyncio
    async def test_async_returns_result_preserves_cause(self) -> None:
        """測試異步裝飾器保留原始異常於 cause。"""

        @async_returns_result()
        async def async_fail() -> None:
            raise ValueError("original error")

        result = await async_fail()
        assert isinstance(result, Err)
        error = result.unwrap_err()
        assert error.cause is not None
        assert isinstance(error.cause, ValueError)


@pytest.mark.unit
class TestAsyncResult:
    """測試 AsyncResult 包裝器。"""

    @pytest.mark.asyncio
    async def test_async_result_map(self) -> None:
        """測試 AsyncResult 的 map 操作。"""

        async def make_result() -> Result[int, Error]:
            return Ok(5)

        wrapper = AsyncResult(make_result())
        mapped = await wrapper.map(lambda x: x * 2)
        final = await mapped
        assert isinstance(final, Ok)
        assert final.unwrap() == 10

    @pytest.mark.asyncio
    async def test_async_result_map_on_err(self) -> None:
        """測試 AsyncResult 在 Err 上的 map 操作。"""

        async def make_result() -> Result[int, Error]:
            return Err(Error("failed"))

        wrapper = AsyncResult(make_result())
        mapped = await wrapper.map(lambda x: x * 2)
        final = await mapped
        assert isinstance(final, Err)
        assert final.unwrap_err().message == "failed"

    @pytest.mark.asyncio
    async def test_async_result_map_err(self) -> None:
        """測試 AsyncResult 的 map_err 操作。"""

        async def make_result() -> Result[int, Error]:
            return Err(Error("generic error"))

        wrapper = AsyncResult(make_result())
        mapped = await wrapper.map_err(lambda e: DatabaseError(e.message))
        final = await mapped
        assert isinstance(final, Err)
        assert isinstance(final.unwrap_err(), DatabaseError)

    @pytest.mark.asyncio
    async def test_async_result_map_err_on_ok(self) -> None:
        """測試 AsyncResult 在 Ok 上的 map_err 操作。"""

        async def make_result() -> Result[int, Error]:
            return Ok(42)

        wrapper = AsyncResult(make_result())
        mapped = await wrapper.map_err(lambda e: DatabaseError(str(e)))
        final = await mapped
        assert isinstance(final, Ok)
        assert final.unwrap() == 42

    @pytest.mark.asyncio
    async def test_async_result_and_then(self) -> None:
        """測試 AsyncResult 的 and_then 操作。"""

        async def make_result() -> Result[int, Error]:
            return Ok(5)

        wrapper = AsyncResult(make_result())
        chained = await wrapper.and_then(lambda x: Ok(x * 3))
        final = await chained
        assert isinstance(final, Ok)
        assert final.unwrap() == 15

    @pytest.mark.asyncio
    async def test_async_result_and_then_returns_err(self) -> None:
        """測試 AsyncResult 的 and_then 可以返回 Err。"""

        async def make_result() -> Result[int, Error]:
            return Ok(5)

        wrapper = AsyncResult(make_result())
        chained = await wrapper.and_then(lambda x: Err(Error("failed in chain")))
        final = await chained
        assert isinstance(final, Err)
        assert final.unwrap_err().message == "failed in chain"

    @pytest.mark.asyncio
    async def test_async_result_and_then_on_err(self) -> None:
        """測試 AsyncResult 在 Err 上的 and_then 操作。"""

        async def make_result() -> Result[int, Error]:
            return Err(Error("original error"))

        wrapper = AsyncResult(make_result())
        chained = await wrapper.and_then(lambda x: Ok(x * 2))
        final = await chained
        assert isinstance(final, Err)
        assert final.unwrap_err().message == "original error"

    @pytest.mark.asyncio
    async def test_async_result_await_directly(self) -> None:
        """測試直接 await AsyncResult。"""

        async def make_result() -> Result[int, Error]:
            return Ok(100)

        wrapper = AsyncResult(make_result())
        result = await wrapper
        assert isinstance(result, Ok)
        assert result.unwrap() == 100
