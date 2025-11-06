"""Unit tests for retry mechanism with exponential backoff and jitter."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from src.infra.retry import exponential_backoff_with_jitter, simple_retry


class RetryableError(Exception):
    """Error that should trigger retry."""


class NonRetryableError(Exception):
    """Error that should not trigger retry."""


@pytest.mark.unit
def test_exponential_backoff_with_jitter_retries_on_matching_exception() -> None:
    """Test that exponential backoff retries on matching exception types."""
    call_count = [0]

    @exponential_backoff_with_jitter(
        max_attempts=3,
        initial_wait=0.01,
        max_wait=0.1,
        retry_on=RetryableError,
    )
    def failing_function() -> int:
        call_count[0] += 1
        if call_count[0] < 3:
            raise RetryableError("Temporary failure")
        return 42

    result = failing_function()
    assert result == 42
    assert call_count[0] == 3


@pytest.mark.unit
def test_exponential_backoff_with_jitter_does_not_retry_on_non_matching_exception() -> None:
    """Test that exponential backoff does not retry on non-matching exceptions."""
    call_count = [0]

    @exponential_backoff_with_jitter(
        max_attempts=3,
        initial_wait=0.01,
        max_wait=0.1,
        retry_on=RetryableError,
    )
    def failing_function() -> int:
        call_count[0] += 1
        raise NonRetryableError("Permanent failure")

    with pytest.raises(NonRetryableError):
        failing_function()
    assert call_count[0] == 1


@pytest.mark.unit
def test_exponential_backoff_with_jitter_respects_max_attempts() -> None:
    """Test that exponential backoff respects max_attempts limit."""
    call_count = [0]

    @exponential_backoff_with_jitter(
        max_attempts=2,
        initial_wait=0.01,
        max_wait=0.1,
        retry_on=RetryableError,
    )
    def always_failing_function() -> int:
        call_count[0] += 1
        raise RetryableError("Always fails")

    with pytest.raises(RetryableError):
        always_failing_function()
    assert call_count[0] == 2


@pytest.mark.unit
@patch("time.sleep")
def test_exponential_backoff_with_jitter_applies_jitter(mock_sleep: Mock) -> None:
    """Test that exponential backoff applies jitter to wait times."""
    call_count = [0]

    @exponential_backoff_with_jitter(
        max_attempts=3,
        initial_wait=0.1,
        max_wait=1.0,
        jitter_range=(-0.1, 0.1),
        retry_on=RetryableError,
    )
    def failing_function() -> int:
        call_count[0] += 1
        if call_count[0] < 3:
            raise RetryableError("Temporary failure")
        return 42

    failing_function()

    # Verify that sleep was called (with jitter applied)
    assert mock_sleep.call_count >= 2
    # Verify sleep times are within expected range (with jitter)
    for call in mock_sleep.call_args_list:
        sleep_time = call[0][0]
        assert 0.09 <= sleep_time <= 0.11  # 0.1 ± 10% jitter


@pytest.mark.unit
def test_simple_retry_retries_on_matching_exception() -> None:
    """Test that simple retry retries on matching exception types."""
    call_count = [0]

    @simple_retry(
        max_attempts=3,
        wait_seconds=0.01,
        retry_on=RetryableError,
    )
    def failing_function() -> int:
        call_count[0] += 1
        if call_count[0] < 3:
            raise RetryableError("Temporary failure")
        return 42

    result = failing_function()
    assert result == 42
    assert call_count[0] == 3


@pytest.mark.unit
def test_simple_retry_respects_max_attempts() -> None:
    """Test that simple retry respects max_attempts limit."""
    call_count = [0]

    @simple_retry(
        max_attempts=2,
        wait_seconds=0.01,
        retry_on=RetryableError,
    )
    def always_failing_function() -> int:
        call_count[0] += 1
        raise RetryableError("Always fails")

    with pytest.raises(RetryableError):
        always_failing_function()
    assert call_count[0] == 2


@pytest.mark.unit
@patch("time.sleep")
def test_simple_retry_uses_fixed_wait_time(mock_sleep: Mock) -> None:
    """Test that simple retry uses fixed wait time between retries."""
    call_count = [0]

    @simple_retry(
        max_attempts=3,
        wait_seconds=0.05,
        retry_on=RetryableError,
    )
    def failing_function() -> int:
        call_count[0] += 1
        if call_count[0] < 3:
            raise RetryableError("Temporary failure")
        return 42

    failing_function()

    # Verify that sleep was called with fixed wait time
    assert mock_sleep.call_count >= 2
    for call in mock_sleep.call_args_list:
        assert call[0][0] == 0.05
