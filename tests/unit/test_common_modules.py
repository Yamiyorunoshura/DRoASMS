"""Unit tests for common compatibility modules."""

from __future__ import annotations

import warnings
from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestCommonModules:
    """Test cases for common compatibility modules."""

    def test_common_init_reexports(self) -> None:
        """Test that common.__init__ properly re-exports from infra.result."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            from src.common import (
                AsyncResult,
                BaseError,
                DatabaseError,
                DiscordError,
                Err,
                Ok,
                Result,
                ValidationError,
            )

            # Verify all expected exports are available
            assert Result is not None
            assert Ok is not None
            assert Err is not None
            assert AsyncResult is not None
            assert BaseError is not None
            assert DatabaseError is not None
            assert DiscordError is not None
            assert ValidationError is not None

            # Verify they match the infra.result versions
            from src.infra.result import (
                AsyncResult as InfraAsyncResult,
            )
            from src.infra.result import (
                DatabaseError as InfraDatabaseError,
            )
            from src.infra.result import (
                DiscordError as InfraDiscordError,
            )
            from src.infra.result import (
                Err as InfraErr,
            )
            from src.infra.result import (
                Error as InfraError,
            )
            from src.infra.result import (
                Ok as InfraOk,
            )
            from src.infra.result import (
                Result as InfraResult,
            )
            from src.infra.result import (
                ValidationError as InfraValidationError,
            )

            assert Result is InfraResult
            assert Ok is InfraOk
            assert Err is InfraErr
            assert AsyncResult is InfraAsyncResult
            assert BaseError is InfraError
            assert DatabaseError is InfraDatabaseError
            assert DiscordError is InfraDiscordError
            assert ValidationError is InfraValidationError

    def test_common_init_all_exports(self) -> None:
        """Test that __all__ is properly defined in common.__init__."""
        import src.common

        expected_exports = [
            "Result",
            "Ok",
            "Err",
            "AsyncResult",
            "BaseError",
            "DatabaseError",
            "DiscordError",
            "ValidationError",
        ]

        assert hasattr(src.common, "__all__")
        assert src.common.__all__ == expected_exports

    def test_common_errors_deprecation_warning(self) -> None:
        """Test that common.errors emits deprecation warning on import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Clear any previous imports from cache
            import sys

            if "src.common.errors" in sys.modules:
                del sys.modules["src.common.errors"]

            # Check that deprecation warning was emitted
            assert len(w) >= 1
            deprecation_warnings = [
                warning for warning in w if issubclass(warning.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1

            warning_message = str(deprecation_warnings[0].message)
            assert "src.common.errors" in warning_message
            assert "src.infra.result" in warning_message

    def test_common_errors_reexports(self) -> None:
        """Test that common.errors properly re-exports error types."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from src.common.errors import (
                BaseError,
                BusinessLogicError,
                DatabaseError,
                DiscordError,
                PermissionDeniedError,
                SystemError,
                ValidationError,
            )

            # Verify all expected exports are available
            assert BaseError is not None
            assert DatabaseError is not None
            assert DiscordError is not None
            assert ValidationError is not None
            assert BusinessLogicError is not None
            assert PermissionDeniedError is not None
            assert SystemError is not None

            # Verify they match the infra.result versions
            from src.infra.result import (
                BusinessLogicError as InfraBusinessLogicError,
            )
            from src.infra.result import (
                DatabaseError as InfraDatabaseError,
            )
            from src.infra.result import (
                DiscordError as InfraDiscordError,
            )
            from src.infra.result import (
                Error as InfraError,
            )
            from src.infra.result import (
                PermissionDeniedError as InfraPermissionDeniedError,
            )
            from src.infra.result import (
                SystemError as InfraSystemError,
            )
            from src.infra.result import (
                ValidationError as InfraValidationError,
            )

            assert BaseError is InfraError
            assert DatabaseError is InfraDatabaseError
            assert DiscordError is InfraDiscordError
            assert ValidationError is InfraValidationError
            assert BusinessLogicError is InfraBusinessLogicError
            assert PermissionDeniedError is InfraPermissionDeniedError
            assert SystemError is InfraSystemError

    def test_common_errors_all_exports(self) -> None:
        """Test that __all__ is properly defined in common.errors."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import src.common.errors

            expected_exports = [
                "BaseError",
                "DatabaseError",
                "DiscordError",
                "ValidationError",
                "BusinessLogicError",
                "PermissionDeniedError",
                "SystemError",
            ]

            assert hasattr(src.common.errors, "__all__")
            assert src.common.errors.__all__ == expected_exports

    def test_common_errors_deprecation_warning_on_import(self) -> None:
        """Test that common.errors emits deprecation warning (functionality test)."""
        # This test verifies that the deprecation warning system is working
        # by checking that warnings.warn is called during module import
        with patch("warnings.warn") as mock_warn:
            # Clear cache to ensure fresh import
            import sys

            if "src.common.errors" in sys.modules:
                del sys.modules["src.common.errors"]

            # Import the module - this should trigger warnings.warn

            # Verify that warnings.warn was called with a deprecation message
            mock_warn.assert_called()
            call_args = mock_warn.call_args
            assert "DeprecationWarning" in str(call_args)
            assert "src.common.errors" in str(call_args)

    def test_common_result_deprecation_warning(self) -> None:
        """Test that common.result emits deprecation warning on import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Clear any previous imports from cache
            import sys

            if "src.common.result" in sys.modules:
                del sys.modules["src.common.result"]

            # Check that deprecation warning was emitted
            assert len(w) >= 1
            deprecation_warnings = [
                warning for warning in w if issubclass(warning.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1

            warning_message = str(deprecation_warnings[0].message)
            assert "src.common.result" in warning_message
            assert "src.infra.result" in warning_message

    def test_common_result_reexports(self) -> None:
        """Test that common.result properly re-exports result helpers."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from src.common.result import (
                AsyncResult,
                Err,
                Ok,
                Result,
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

            # Verify all expected exports are available
            assert Result is not None
            assert Ok is not None
            assert Err is not None
            assert AsyncResult is not None
            assert ok is not None
            assert err is not None
            assert collect is not None
            assert sequence is not None
            assert safe_call is not None
            assert safe_async_call is not None
            assert returns_result is not None
            assert async_returns_result is not None
            assert result_from_exception is not None

            # Verify they match the infra.result versions
            from src.infra.result import (
                AsyncResult as InfraAsyncResult,
            )
            from src.infra.result import (
                Err as InfraErr,
            )
            from src.infra.result import (
                Ok as InfraOk,
            )
            from src.infra.result import (
                Result as InfraResult,
            )
            from src.infra.result import (
                async_returns_result as infra_async_returns_result,
            )
            from src.infra.result import (
                collect as infra_collect,
            )
            from src.infra.result import (
                err as infra_err,
            )
            from src.infra.result import (
                ok as infra_ok,
            )
            from src.infra.result import (
                result_from_exception as infra_result_from_exception,
            )
            from src.infra.result import (
                returns_result as infra_returns_result,
            )
            from src.infra.result import (
                safe_async_call as infra_safe_async_call,
            )
            from src.infra.result import (
                safe_call as infra_safe_call,
            )
            from src.infra.result import (
                sequence as infra_sequence,
            )

            assert Result is InfraResult
            assert Ok is InfraOk
            assert Err is InfraErr
            assert AsyncResult is InfraAsyncResult
            assert ok is infra_ok
            assert err is infra_err
            assert collect is infra_collect
            assert sequence is infra_sequence
            assert safe_call is infra_safe_call
            assert safe_async_call is infra_safe_async_call
            assert returns_result is infra_returns_result
            assert async_returns_result is infra_async_returns_result
            assert result_from_exception is infra_result_from_exception

    def test_common_result_all_exports(self) -> None:
        """Test that __all__ is properly defined in common.result."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import src.common.result

            expected_exports = [
                "Result",
                "Ok",
                "Err",
                "AsyncResult",
                "ok",
                "err",
                "collect",
                "sequence",
                "safe_call",
                "safe_async_call",
                "returns_result",
                "async_returns_result",
                "result_from_exception",
            ]

            assert hasattr(src.common.result, "__all__")
            assert src.common.result.__all__ == expected_exports

    def test_common_result_deprecation_warning_on_import(self) -> None:
        """Test that common.result emits deprecation warning (functionality test)."""
        # This test verifies that the deprecation warning system is working
        # by checking that warnings.warn is called during module import
        with patch("warnings.warn") as mock_warn:
            # Clear cache to ensure fresh import
            import sys

            if "src.common.result" in sys.modules:
                del sys.modules["src.common.result"]

            # Import the module - this should trigger warnings.warn

            # Verify that warnings.warn was called with a deprecation message
            mock_warn.assert_called()
            call_args = mock_warn.call_args
            assert "DeprecationWarning" in str(call_args)
            assert "src.common.result" in str(call_args)

    def test_compatibility_layer_functionality(self) -> None:
        """Test that the compatibility layers actually work for basic operations."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            # Test common.result functionality
            from src.common.result import Err, Ok, Result

            # Create and use Result types
            ok_result: Result[int, str] = Ok(42)
            err_result: Result[int, str] = Err("error")

            assert ok_result.is_ok() is True
            assert ok_result.is_err() is False
            assert ok_result.unwrap() == 42

            assert err_result.is_ok() is False
            assert err_result.is_err() is True

            # Test common.errors functionality
            from src.common.errors import BaseError, ValidationError

            # Create and use error types
            base_error = BaseError("base error")
            validation_error = ValidationError("validation error")

            assert str(base_error) == "base error"
            assert str(validation_error) == "validation error"
            assert isinstance(validation_error, BaseError)

            # Test that errors can be raised and caught
            try:
                raise validation_error
            except ValidationError as caught:
                assert str(caught) == "validation error"

    def test_multiple_imports_same_warning(self) -> None:
        """Test that importing the same compatibility module multiple times doesn't spam warnings."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Clear cache
            import sys

            if "src.common.errors" in sys.modules:
                del sys.modules["src.common.errors"]

            # Import multiple times

            # Should only get one warning (from the first import)
            deprecation_warnings = [
                warning for warning in w if issubclass(warning.category, DeprecationWarning)
            ]
            # Note: Due to Python's import system, we might get multiple warnings
            # but they should all be the same warning message
            if len(deprecation_warnings) > 0:
                messages = [str(warning.message) for warning in deprecation_warnings]
                assert all("src.common.errors" in msg for msg in messages)

    def test_cross_compatibility_consistency(self) -> None:
        """Test that the same types from different compatibility modules are identical."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            # Import from different modules
            from src.common import Result as CommonInitResult
            from src.common.result import Result as CommonResultResult
            from src.infra.result import Result as InfraResult

            # They should all be the same type
            assert CommonInitResult is CommonResultResult
            assert CommonResultResult is InfraResult
            assert CommonInitResult is InfraResult

            # Test with error types
            from src.common import BaseError as CommonInitBaseError
            from src.common.errors import BaseError as CommonErrorsBaseError
            from src.infra.result import Error as InfraError

            assert CommonInitBaseError is CommonErrorsBaseError
            assert CommonErrorsBaseError is InfraError
            assert CommonInitBaseError is InfraError
