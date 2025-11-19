"""Compatibility Result<T,E> API for `src.common` 命名空間。

此模組提供一個較「傳統」的 Result 介面，主要用途：
- 讓既有程式碼與 `tests/test_result.py` 可以繼續使用舊語意
- 不影響新的核心錯誤處理實作（`src.infra.result`）

新的基礎實作與進階功能（AsyncResult、統計等）仍由 `src.infra.result`
負責；這裡僅實作相容層。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Iterable, Iterator, Mapping, Type, TypeVar, Union

from src.common.errors import (
    BaseError,
    DatabaseError,
    DiscordError,
    ErrorCategory,
    ValidationError,
)
from src.infra.result import AsyncResult  # 保留新的 AsyncResult 供外部使用

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E", bound=BaseError)
F = TypeVar("F", bound=BaseError)


@dataclass
class Ok(Generic[T, E]):
    """代表成功結果的包裝類型（相容層）。"""

    value: T

    # 狀態判斷
    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    # 解包相關
    def unwrap(self) -> T:
        return self.value

    def unwrap_err(self) -> E:
        # 與舊測試相容：在 Ok 上呼叫 unwrap_err 會拋出 ValueError
        raise ValueError("Called unwrap_err on Ok value")

    def unwrap_or(self, default: T) -> T:
        return self.value

    def expect(self, message: str) -> T:  # noqa: ARG002 - message 僅用於 Err 分支
        return self.value

    # 鏈式操作
    def map(self, fn: Callable[[T], U]) -> "Result[U, BaseError]":
        try:
            return Ok(fn(self.value))
        except Exception as exc:  # 將函數中的例外轉成 ValidationError（舊語意）
            err = ValidationError(
                message=str(exc),
                category=ErrorCategory.VALIDATION,
            )
            return Err(err)

    def map_err(self, fn: Callable[[E], F]) -> "Result[T, F]":
        # Ok 不會觸及錯誤型別
        return Ok(self.value)

    def and_then(self, fn: Callable[[T], "Result[U, E]"]) -> "Result[U, E]":
        return fn(self.value)

    def or_else(self, fn: Callable[[E], "Result[T, F]"]) -> "Result[T, F]":  # noqa: ARG002
        return Ok(self.value)

    # 迭代 / 轉型
    def __iter__(self) -> Iterator[T]:
        yield self.value

    def __bool__(self) -> bool:
        # 舊測試期望 Ok 轉為 bool 時為 True
        return True

    def __str__(self) -> str:
        # 舊測試期望 str(Ok(42)) == "Ok(42)"
        return f"Ok({self.value})"


@dataclass
class Err(Generic[T, E]):
    """代表失敗結果的包裝類型（相容層）。"""

    error: E

    # 狀態判斷
    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    # 解包相關
    def unwrap(self) -> T:
        # 與舊測試相容：在 Err 上呼叫 unwrap 會拋出 ValueError
        raise ValueError("Called unwrap on Err value")

    def unwrap_err(self) -> E:
        return self.error

    def unwrap_or(self, default: T) -> T:
        return default

    def expect(self, message: str) -> T:
        # 舊測試期望 expect 在 Err 上拋出 ValueError，訊息為自訂文字
        raise ValueError(message)

    # 鏈式操作
    def map(self, fn: Callable[[T], U]) -> "Result[U, E]":  # noqa: ARG002
        return Err(self.error)

    def map_err(self, fn: Callable[[E], F]) -> "Result[T, F]":
        return Err(fn(self.error))

    def and_then(self, fn: Callable[[T], "Result[U, E]"]) -> "Result[U, E]":  # noqa: ARG002
        return Err(self.error)

    def or_else(self, fn: Callable[[E], "Result[T, F]"]) -> "Result[T, F]":
        return fn(self.error)

    # 迭代 / 轉型
    def __iter__(self) -> Iterator[T]:
        # Err 被視為空集合
        return iter(())

    def __bool__(self) -> bool:
        # 舊測試期望 Err 轉為 bool 時為 False
        return False

    def __str__(self) -> str:
        return f"Err({self.error})"


Result = Union[Ok[T, E], Err[T, E]]


def _build_error(error_type: Type[E], exc: Exception) -> E:
    """依 error_type 建立對應的 BaseError 實例。"""
    # 常見型別針對 category 做合理預設，其餘則落在 BUSINESS_LOGIC。
    if issubclass(error_type, ValidationError):
        category = ErrorCategory.VALIDATION
    elif issubclass(error_type, DatabaseError):
        category = ErrorCategory.DATABASE
    elif issubclass(error_type, DiscordError):
        category = ErrorCategory.DISCORD
    else:
        category = ErrorCategory.BUSINESS_LOGIC

    # 型別簽章為 (message, category, ...)；context 交由呼叫端自訂
    return error_type(message=str(exc), category=category)


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
    """與 collect 等價，提供函數式命名相容性。"""
    return collect(results)


def safe_call(
    fn: Callable[..., T],
    *args: object,
    error_type: Type[E] = ValidationError,  # type: ignore[assignment]
    **kwargs: object,
) -> Result[T, E]:
    """執行同步函數並將例外轉為 Result。

    - 成功：回傳 Ok(value)
    - 失敗：將例外轉為指定的 BaseError 子類（預設 ValidationError），回傳 Err(error)
    """
    try:
        return Ok(fn(*args, **kwargs))
    except Exception as exc:
        error = _build_error(error_type, exc)
        return Err(error)


def returns_result(
    error_type: Type[E] = ValidationError,  # type: ignore[assignment]
    *,
    exception_map: Mapping[type[Exception], Type[E]] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., Result[T, E]]]:
    """將可能丟出例外的同步函數包裝為回傳 Result（相容層）。

    - 正常回傳 -> Ok(value)
    - 丟出例外 -> Err(mapped_error)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., Result[T, E]]:
        def wrapper(*args: object, **kwargs: object) -> Result[T, E]:
            try:
                return Ok(func(*args, **kwargs))
            except Exception as exc:
                # 若有提供 exception_map，優先依照例外型別對應
                selected_error_type: Type[E] = error_type
                if exception_map is not None:
                    for exc_type, mapped_type in exception_map.items():
                        if isinstance(exc, exc_type):
                            selected_error_type = mapped_type
                            break
                error = _build_error(selected_error_type, exc)
                return Err(error)

        return wrapper

    return decorator


__all__ = [
    "Result",
    "Ok",
    "Err",
    "AsyncResult",
    "collect",
    "sequence",
    "safe_call",
    "returns_result",
]
