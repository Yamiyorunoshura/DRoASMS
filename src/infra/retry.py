from __future__ import annotations

from typing import Callable, TypeVar, cast

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
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

    Args:
        max_attempts: Maximum number of retry attempts
        initial_wait: Initial wait time in seconds
        max_wait: Maximum wait time in seconds
        jitter_range: Jitter range as (min, max) multiplier (e.g., (-0.2, 0.2) for ±20%)
        retry_on: Exception types to retry on

    Returns:
        A retry decorator function
    """
    wait_strategy = wait_exponential(
        multiplier=initial_wait,
        max=max_wait,
    ) + wait_random(*jitter_range)

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
