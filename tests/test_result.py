"""
Tests for the Result<T,E> error handling system.
"""

import pytest

from src.common.errors import (
    BaseError,
    DatabaseError,
    DiscordError,
    ErrorCategory,
    ErrorSeverity,
    ValidationError,
)
from src.common.result import Err, Ok, collect, returns_result, safe_call


class TestResultBasic:
    """Test basic Result functionality."""

    def test_ok_creation(self):
        """Test creating Ok values."""
        result = Ok(42)
        assert result.is_ok() is True
        assert result.is_err() is False
        assert result.unwrap() == 42
        assert str(result) == "Ok(42)"
        assert bool(result) is True

    def test_err_creation(self):
        """Test creating Err values."""
        error = ValidationError(
            message="Invalid input",
            category=ErrorCategory.VALIDATION,
            field="email",
            value="invalid-email",
        )
        result = Err(error)
        assert result.is_ok() is False
        assert result.is_err() is True
        assert result.unwrap_err() == error
        assert bool(result) is False

    def test_ok_unwrap_err_raises(self):
        """Test calling unwrap_err on Ok raises ValueError."""
        result = Ok(42)
        with pytest.raises(ValueError, match="Called unwrap_err on Ok value"):
            result.unwrap_err()

    def test_err_unwrap_raises(self):
        """Test calling unwrap on Err raises ValueError."""
        error = ValidationError(message="Test error", category=ErrorCategory.VALIDATION)
        result = Err(error)
        with pytest.raises(ValueError, match="Called unwrap on Err value"):
            result.unwrap()

    def test_unwrap_or(self):
        """Test unwrap_or method."""
        ok_result = Ok(42)
        err_result = Err(ValidationError(message="Test error", category=ErrorCategory.VALIDATION))

        assert ok_result.unwrap_or(0) == 42
        assert err_result.unwrap_or(0) == 0

    def test_expect(self):
        """Test expect method."""
        ok_result = Ok(42)
        error = ValidationError(message="Test error", category=ErrorCategory.VALIDATION)
        err_result = Err(error)

        assert ok_result.expect("Should not fail") == 42
        with pytest.raises(ValueError, match="Custom message"):
            err_result.expect("Custom message")


class TestResultChain:
    """Test Result chaining operations."""

    def test_map_ok(self):
        """Test map on Ok values."""
        result = Ok(42).map(lambda x: x * 2)
        assert isinstance(result, Ok)
        assert result.unwrap() == 84

    def test_map_err(self):
        """Test map on Err values."""
        error = ValidationError(message="Test error", category=ErrorCategory.VALIDATION)
        result = Err(error).map(lambda x: x * 2)
        assert isinstance(result, Err)
        assert result.unwrap_err() == error

    def test_map_err_with_exception(self):
        """Test map where function raises exception."""
        result = Ok(42).map(lambda x: 1 / 0)
        assert isinstance(result, Err)
        assert isinstance(result.unwrap_err(), BaseError)

    def test_map_err_method(self):
        """Test map_err method."""
        error = ValidationError(message="Original error", category=ErrorCategory.VALIDATION)
        result = Err(error).map_err(
            lambda e: DatabaseError(
                message=f"Database: {e.message}",
                category=ErrorCategory.DATABASE,
                operation="select",
            )
        )
        assert isinstance(result, Err)
        mapped_error = result.unwrap_err()
        assert isinstance(mapped_error, DatabaseError)
        assert "Database: Original error" in mapped_error.message

    def test_and_then_ok(self):
        """Test and_then on Ok values."""

        def double_if_even(x):
            if x % 2 == 0:
                return Ok(x * 2)
            else:
                return Err(
                    ValidationError(message="Number is odd", category=ErrorCategory.VALIDATION)
                )

        result = Ok(42).and_then(double_if_even)
        assert isinstance(result, Ok)
        assert result.unwrap() == 84

        result = Ok(41).and_then(double_if_even)
        assert isinstance(result, Err)

    def test_and_then_err(self):
        """Test and_then on Err values."""
        error = ValidationError(message="Test error", category=ErrorCategory.VALIDATION)

        def double(x):
            return Ok(x * 2)

        result = Err(error).and_then(double)
        assert isinstance(result, Err)
        assert result.unwrap_err() == error

    def test_or_else_ok(self):
        """Test or_else on Ok values."""

        def recover(error):
            return Ok(0)

        result = Ok(42).or_else(recover)
        assert isinstance(result, Ok)
        assert result.unwrap() == 42

    def test_or_else_err(self):
        """Test or_else on Err values."""
        error = ValidationError(message="Original error", category=ErrorCategory.VALIDATION)

        def recover(e):
            return Ok(0)

        result = Err(error).or_else(recover)
        assert isinstance(result, Ok)
        assert result.unwrap() == 0


class TestResultUtilities:
    """Test Result utility functions."""

    def test_collect_all_ok(self):
        """Test collect with all Ok values."""
        results = [Ok(1), Ok(2), Ok(3)]
        collected = collect(results)
        assert isinstance(collected, Ok)
        assert collected.unwrap() == [1, 2, 3]

    def test_collect_with_err(self):
        """Test collect with some Err values."""
        error = ValidationError(message="Test error", category=ErrorCategory.VALIDATION)
        results = [Ok(1), Err(error), Ok(3)]
        collected = collect(results)
        assert isinstance(collected, Err)
        assert collected.unwrap_err() == error

    def test_safe_call_success(self):
        """Test safe_call with successful function."""

        def add_one(x):
            return x + 1

        result = safe_call(add_one, 41)
        assert isinstance(result, Ok)
        assert result.unwrap() == 42

    def test_safe_call_exception(self):
        """Test safe_call with function that raises."""

        def raise_error():
            raise ValueError("Test error")

        result = safe_call(raise_error)
        assert isinstance(result, Err)
        error = result.unwrap_err()
        assert isinstance(error, ValidationError)
        assert "Test error" in error.message

    def test_returns_result_decorator(self):
        """Test returns_result decorator."""

        @returns_result(ValidationError)
        def validate_positive(x):
            if x > 0:
                return x
            else:
                raise ValueError("Value must be positive")

        result = validate_positive(42)
        assert isinstance(result, Ok)
        assert result.unwrap() == 42

        result = validate_positive(-1)
        assert isinstance(result, Err)
        assert isinstance(result.unwrap_err(), ValidationError)


class TestErrorTypes:
    """Test error type hierarchy and functionality."""

    def test_database_error(self):
        """Test DatabaseError creation and methods."""
        error = DatabaseError(
            message="Connection failed",
            category=ErrorCategory.DATABASE,
            operation="connect",
            table="users",
        )
        assert error.category == ErrorCategory.DATABASE
        assert error.operation == "connect"
        assert error.table == "users"

        error_dict = error.to_dict()
        assert error_dict["type"] == "DatabaseError"
        assert error_dict["message"] == "Connection failed"
        assert error_dict["category"] == "database"

    def test_discord_error(self):
        """Test DiscordError creation and methods."""
        error = DiscordError(
            message="API rate limited",
            category=ErrorCategory.DISCORD,
            api_method="send_message",
            user_id=12345,
        )
        assert error.category == ErrorCategory.DISCORD
        assert error.api_method == "send_message"
        assert error.user_id == 12345

    def test_validation_error(self):
        """Test ValidationError creation and methods."""
        error = ValidationError(
            message="Invalid email format",
            category=ErrorCategory.VALIDATION,
            field="email",
            value="invalid-email",
        )
        assert error.category == ErrorCategory.VALIDATION
        assert error.field == "email"
        assert error.value == "invalid-email"

    def test_error_json_serialization(self):
        """Test error JSON serialization."""
        error = ValidationError(
            message="Test error",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            context={"user_id": 12345},
        )

        json_str = error.to_json()
        assert "Test error" in json_str
        assert "validation" in json_str
        assert "high" in json_str
        assert "12345" in json_str


if __name__ == "__main__":
    pytest.main([__file__])
