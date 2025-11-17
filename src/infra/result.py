"""Rust 風格 Result / AsyncResult 錯誤處理工具。

此模組提供：
- Ok / Err 包裝類型與 Result 聯集型別
- 具備 map/and_then 等鏈式操作方法
- AsyncResult 非同步包裝器
- 基礎錯誤類型階層與工具函數
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    Iterable,
    ParamSpec,
    TypeVar,
    Union,
)

import structlog

LOGGER = structlog.get_logger(__name__)

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")
F = TypeVar("F")

P = ParamSpec("P")


# --- 錯誤型別階層 ---


class Error(Exception):
    """Result 使用的基礎錯誤型別，攜帶訊息與可選上下文。"""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = dict(context or {})

    def to_dict(self) -> dict[str, Any]:
        return {"message": self.message, "context": dict(self.context)}

    def __str__(self) -> str:  # pragma: no cover - 委派給 message
        return self.message


class DatabaseError(Error):
    """資料庫相關錯誤。"""


class DiscordError(Error):
    """Discord API 或互動相關錯誤。"""


class ValidationError(Error):
    """驗證失敗錯誤。"""


# --- Result / Ok / Err ---


@dataclass(slots=True)
class Ok(Generic[T, E]):
    """代表成功結果的包裝類型。"""

    value: T

    # 基礎方法
    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_err(self) -> E:
        raise RuntimeError("Called unwrap_err() on Ok value.")

    # 鏈式操作
    def map(self, fn: Callable[[T], U]) -> "Result[U, E]":
        return Ok(fn(self.value))

    def map_err(self, fn: Callable[[E], F]) -> "Result[T, F]":
        # Ok 不觸及錯誤型別
        return Ok(self.value)

    def and_then(self, fn: Callable[[T], "Result[U, E]"]) -> "Result[U, E]":
        return fn(self.value)

    def or_else(self, fn: Callable[[E], "Result[T, F]"]) -> "Result[T, E]":
        return Ok(self.value)

    def unwrap_or(self, default: T) -> T:
        return self.value

    def unwrap_or_else(self, default_fn: Callable[[], T]) -> T:
        return self.value


@dataclass(slots=True)
class Err(Generic[T, E]):
    """代表失敗結果的包裝類型。"""

    error: E

    # 基礎方法
    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> T:
        raise RuntimeError(f"Called unwrap() on Err value: {self.error!r}")

    def unwrap_err(self) -> E:
        return self.error

    # 鏈式操作
    def map(self, fn: Callable[[T], U]) -> "Result[U, E]":
        return Err(self.error)

    def map_err(self, fn: Callable[[E], F]) -> "Result[T, F]":
        return Err(fn(self.error))

    def and_then(self, fn: Callable[[T], "Result[U, E]"]) -> "Result[U, E]":
        return Err(self.error)

    def or_else(self, fn: Callable[[E], "Result[T, F]"]) -> "Result[T, F]":
        return fn(self.error)

    def unwrap_or(self, default: T) -> T:
        return default

    def unwrap_or_else(self, default_fn: Callable[[], T]) -> T:
        return default_fn()


Result = Union[Ok[T, E], Err[T, E]]


# --- 工具函數 ---


def ok(value: T) -> Result[T, object]:
    """Helper to construct an Ok result with generic error type."""
    return Ok(value)


def err(error: E) -> Result[object, E]:
    """Helper to construct an Err result with generic success type."""
    return Err(error)


def result_from_exception(exc: Exception, *, default_error: type[Error] = Error) -> Err[Any, Error]:
    """將任意 Exception 轉換成 Err[Error]。"""
    if isinstance(exc, Error):
        error_obj = exc
    else:
        error_obj = default_error(str(exc))
    return Err(error_obj)


def safe_call(
    fn: Callable[..., T],
    *args: object,
    error_type: type[Error] = Error,
    **kwargs: object,
) -> Result[T, Error]:
    """執行同步函數並將例外轉為 Result。"""
    try:
        return Ok(fn(*args, **kwargs))
    except Exception as exc:  # pragma: no cover - 例外路徑由具體測試覆蓋
        error_obj = error_type(str(exc))
        LOGGER.error("result.safe_call.error", error=str(error_obj))
        return Err(error_obj)


async def safe_async_call(
    fn: Callable[..., Awaitable[T]],
    *args: object,
    error_type: type[Error] = Error,
    **kwargs: object,
) -> Result[T, Error]:
    """執行非同步函數並將例外轉為 Result。"""
    try:
        value = await fn(*args, **kwargs)
        return Ok(value)
    except Exception as exc:  # pragma: no cover - 例外路徑由具體測試覆蓋
        error_obj = error_type(str(exc))
        LOGGER.error("result.safe_async_call.error", error=str(error_obj))
        return Err(error_obj)


def collect(results: Iterable[Result[T, E]]) -> Result[list[T], E]:
    """收集一組 Result；若全部成功則回傳 Ok[list[T]]，否則回傳第一個 Err。"""
    values: list[T] = []
    for item in results:
        if isinstance(item, Ok):
            values.append(item.value)
        else:
            return Err(item.error)
    return Ok(values)


def sequence(results: Iterable[Result[T, E]]) -> Result[list[T], E]:
    """sequence() 是 collect() 的別名，符合函數式命名慣例。"""
    return collect(results)


# --- AsyncResult ---


class AsyncResult(Generic[T, E]):
    """將 Awaitable[Result[T,E]] 包裝為可鏈式操作的型別。"""

    def __init__(self, inner: Awaitable[Result[T, E]]) -> None:
        self._inner = inner

    def __await__(self) -> Any:
        return self._inner.__await__()

    async def _apply(self, fn: Callable[[Result[T, E]], Result[U, F]]) -> "AsyncResult[U, F]":
        result = await self._inner
        return AsyncResult(_wrap_result(fn(result)))

    async def map(self, fn: Callable[[T], U]) -> "AsyncResult[U, E]":
        def _inner(r: Result[T, E]) -> Result[U, E]:
            return r.map(fn)

        return await self._apply(_inner)

    async def map_err(self, fn: Callable[[E], F]) -> "AsyncResult[T, F]":
        def _inner(r: Result[T, E]) -> Result[T, F]:
            return r.map_err(fn)

        return await self._apply(_inner)

    async def and_then(self, fn: Callable[[T], Result[U, E]]) -> "AsyncResult[U, E]":
        def _inner(r: Result[T, E]) -> Result[U, E]:
            return r.and_then(fn)

        return await self._apply(_inner)


async def _wrap_result(value: Result[T, E]) -> Result[T, E]:
    return value


# --- 裝飾器 ---


def returns_result(
    error_type: type[Error] = Error,
) -> Callable[[Callable[P, T]], Callable[P, Result[T, Error]]]:
    """將可能丟出例外的同步函數包裝為回傳 Result。"""

    def decorator(func: Callable[P, T]) -> Callable[P, Result[T, Error]]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Result[T, Error]:
            try:
                return Ok(func(*args, **kwargs))
            except Exception as exc:
                error_obj = error_type(str(exc))
                LOGGER.error(
                    "result.returns_result.error",
                    function=getattr(func, "__name__", "<unknown>"),
                    error=str(error_obj),
                )
                return Err(error_obj)

        return wrapper

    return decorator


def async_returns_result(
    error_type: type[Error] = Error,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[Result[T, Error]]]]:
    """將可能丟出例外的非同步函數包裝為回傳 Result。"""

    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[Result[T, Error]]]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Result[T, Error]:
            try:
                value = await func(*args, **kwargs)
                return Ok(value)
            except Exception as exc:
                error_obj = error_type(str(exc))
                LOGGER.error(
                    "result.async_returns_result.error",
                    function=getattr(func, "__name__", "<unknown>"),
                    error=str(error_obj),
                )
                return Err(error_obj)

        return wrapper

    return decorator


__all__ = [
    "Ok",
    "Err",
    "Result",
    "Error",
    "DatabaseError",
    "DiscordError",
    "ValidationError",
    "AsyncResult",
    "ok",
    "err",
    "collect",
    "sequence",
    "safe_call",
    "safe_async_call",
    "result_from_exception",
    "returns_result",
    "async_returns_result",
]
