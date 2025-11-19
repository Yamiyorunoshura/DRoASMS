"""Rust 風格 Result / AsyncResult 錯誤處理工具。

此模組提供：
- Ok / Err 包裝類型與 Result 聯集型別
- 具備 map/and_then 等鏈式操作方法
- AsyncResult 非同步包裝器
- 基礎錯誤類型階層與工具函數
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    ParamSpec,
    TypeVar,
    Union,
    cast,
)

import structlog

LOGGER = structlog.get_logger(__name__)

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")
F = TypeVar("F")

P = ParamSpec("P")


# --- 內部常數與工具 ---

_SENSITIVE_KEYS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
)

_ERROR_COUNTERS: Counter[str] = Counter()


def _sanitize_context(context: Mapping[str, Any] | None) -> dict[str, Any]:
    """對錯誤 context 進行敏感資訊遮罩處理。

    - 僅針對 key 名稱包含敏感關鍵字的欄位做遮罩
    - 遞迴處理巢狀 dict
    - 其他欄位原樣保留，避免過度清洗影響除錯
    """
    if not context:
        return {}

    def _sanitize(value: Any) -> Any:
        if isinstance(value, dict):
            mapping = cast(Mapping[str, Any], value)
            sanitized_inner: dict[str, Any] = {}
            for k, v in mapping.items():
                key_lower = str(k).lower()
                sanitized_inner[k] = _sanitize(
                    "***redacted***" if any(sk in key_lower for sk in _SENSITIVE_KEYS) else v
                )
            return sanitized_inner
        return value

    sanitized: dict[str, Any] = {}
    for key, value in context.items():
        key_lower = str(key).lower()
        if any(sk in key_lower for sk in _SENSITIVE_KEYS):
            sanitized[key] = "***redacted***"
        else:
            sanitized[key] = _sanitize(value)
    return sanitized


def _record_error(error: "Error") -> None:
    """更新模組層級錯誤統計資料。"""
    key = type(error).__name__
    _ERROR_COUNTERS[key] += 1
    _ERROR_COUNTERS["__total__"] += 1


def get_error_metrics() -> dict[str, int]:
    """取得目前錯誤統計數據（以錯誤型別名稱分組）。"""
    return dict(_ERROR_COUNTERS)


def reset_error_metrics() -> None:
    """重置錯誤統計數據（僅供測試或排錯使用）。"""
    _ERROR_COUNTERS.clear()


# --- 錯誤型別階層 ---


class Error(Exception):
    """Result 使用的基礎錯誤型別，攜帶訊息、可選上下文與 cause。"""

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = dict(context or {})
        self.cause: BaseException | None = cause

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "context": dict(self.context),
            "cause": repr(self.cause) if self.cause is not None else None,
        }

    def __str__(self) -> str:  # pragma: no cover - 委派給 message
        return self.message

    def log_safe_context(self) -> dict[str, Any]:
        """回傳已遮罩敏感資訊後可安全寫入日誌的 context。"""
        return _sanitize_context(self.context)


class DatabaseError(Error):
    """資料庫相關錯誤。"""


class DiscordError(Error):
    """Discord API 或互動相關錯誤。"""


class ValidationError(Error):
    """驗證失敗錯誤。"""


class BusinessLogicError(Error):
    """業務邏輯相關錯誤（如商業規則或流程違反）。"""


class PermissionDeniedError(Error):
    """權限拒絕錯誤。"""


class SystemError(Error):
    """系統層級錯誤（例如連線池錯誤或基礎設施故障）。"""


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

    # 迭代支援：Ok 迭代出單一成功值
    def __iter__(self) -> Iterator[T]:
        yield self.value


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

    # 迭代支援：Err 視為空集合
    def __iter__(self) -> Iterator[T]:
        return iter(())


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
    _record_error(error_obj)
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
        _record_error(error_obj)
        LOGGER.error(
            "result.safe_call.error",
            error=str(error_obj),
            context=error_obj.log_safe_context(),
        )
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
        _record_error(error_obj)
        LOGGER.error(
            "result.safe_async_call.error",
            error=str(error_obj),
            context=error_obj.log_safe_context(),
        )
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


def _select_error_type(
    exc: Exception,
    default_error_type: type[Error],
    exception_map: Mapping[type[Exception], type[Error]] | None,
) -> type[Error]:
    """根據 exception_map 選擇適用的錯誤型別。"""
    if exception_map:
        for exc_type, err_type in exception_map.items():
            if isinstance(exc, exc_type):
                return err_type
    return default_error_type


def returns_result(
    error_type: type[Error] = Error,
    *,
    exception_map: Mapping[type[Exception], type[Error]] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, Result[T, Error]]]:
    """將可能丟出例外的同步函數包裝為回傳 Result。"""

    def decorator(func: Callable[P, T]) -> Callable[P, Result[T, Error]]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Result[T, Error]:
            try:
                return Ok(func(*args, **kwargs))
            except Exception as exc:
                selected_error_type = _select_error_type(exc, error_type, exception_map)
                error_obj = selected_error_type(str(exc))
                _record_error(error_obj)
                LOGGER.error(
                    "result.returns_result.error",
                    function=getattr(func, "__name__", "<unknown>"),
                    error=str(error_obj),
                    context=error_obj.log_safe_context(),
                )
                return Err(error_obj)

        return wrapper

    return decorator


def async_returns_result(
    error_type: type[Error] = Error,
    *,
    exception_map: Mapping[type[Exception], type[Error]] | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[Result[T, Error]]]]:
    """將可能丟出例外的非同步函數包裝為回傳 Result。

    設計細節：
    - 若原函式回傳一般值 `T`，則包裝後回傳 `Ok(T)`。
    - 若原函式已回傳 `Ok` / `Err`（即 Result 物件），則**不再巢狀包裝**，
      直接透傳，避免出現 `Ok(Ok(value))` 或 `Ok(Err(error))` 的情況。
    - 若丟出例外，則依 `error_type` / `exception_map` 轉換為 `Err(Error)`。
    """

    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[Result[T, Error]]]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Result[T, Error]:
            try:
                value = await func(*args, **kwargs)
                # 若被包裝函式本身已採用 Result 型別，避免再次以 Ok 包起來
                if isinstance(value, (Ok, Err)):
                    return cast(Result[T, Error], value)
                return Ok(value)
            except Exception as exc:
                selected_error_type = _select_error_type(exc, error_type, exception_map)
                # 保留原始例外於 cause 以便後續映射或重新拋出
                error_obj = selected_error_type(str(exc), cause=exc)
                _record_error(error_obj)
                LOGGER.error(
                    "result.async_returns_result.error",
                    function=getattr(func, "__name__", "<unknown>"),
                    error=str(error_obj),
                    context=error_obj.log_safe_context(),
                )
                return cast(Result[T, Error], Err(error_obj))

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
    "BusinessLogicError",
    "PermissionDeniedError",
    "SystemError",
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
    "get_error_metrics",
    "reset_error_metrics",
]
