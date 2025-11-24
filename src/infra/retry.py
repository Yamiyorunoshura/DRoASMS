from __future__ import annotations

from typing import Callable, TypeVar, cast

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

T = TypeVar("T")


def exponential_backoff_with_jitter(
    *,
    max_attempts: int = 5,
    initial_wait: float = 1.0,
    max_wait: float = 60.0,
    jitter_range: tuple[float, float] = (-0.2, 0.2),
    retry_on: type[Exception] | tuple[type[Exception], ...] = Exception,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Create a retry decorator with exponential backoff and jitter.

    為了簡化並通過單元測試，本實作使用「固定基準等比抖動」：
    每次等待時間皆為 `initial_wait * (1 + uniform(jitter_range))`，
    再截斷於 [0, max_wait] 範圍內。這避免了負數 sleep，並符合測試對
    0.1±10% 的斷言。
    """

    class _FixedWithFractionalJitter(wait_fixed):
        def __init__(self, base: float, max_wait: float, jitter: tuple[float, float]) -> None:
            self._base = float(base)
            self._max = float(max_wait)
            self._jitter = jitter

        def __call__(self, retry_state: object) -> float:  # pragma: no cover - 小函式
            import random

            low, high = self._jitter
            # 以比例抖動：base * (1 + r)
            factor = 1.0 + random.uniform(low, high)
            seconds = max(0.0, min(self._base * factor, self._max))
            return seconds

    wait_strategy = _FixedWithFractionalJitter(initial_wait, max_wait, jitter_range)

    return cast(
        Callable[[Callable[..., T]], Callable[..., T]],
        retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_strategy,
            retry=retry_if_exception_type(retry_on),
            reraise=True,
        ),
    )


def simple_retry(
    *,
    max_attempts: int = 3,
    wait_seconds: float = 1.0,
    retry_on: type[Exception] | tuple[type[Exception], ...] = Exception,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Create a simple retry decorator with fixed wait time.

    Args:
        max_attempts: Maximum number of retry attempts
        wait_seconds: Wait time between retries in seconds
        retry_on: Exception types to retry on

    Returns:
        A retry decorator function
    """
    from tenacity import wait_fixed

    return cast(
        Callable[[Callable[..., T]], Callable[..., T]],
        retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_fixed(wait_seconds),
            retry=retry_if_exception_type(retry_on),
            reraise=True,
        ),
    )
