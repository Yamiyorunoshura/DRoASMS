"""Unit tests for state council error types."""

from __future__ import annotations

import pytest

from src.bot.services import state_council_errors
from src.infra.result import (
    Error,
    PermissionDeniedError,
    ValidationError,
)


@pytest.mark.unit
class TestStateCouncilErrors:
    """Test cases for state council error types."""

    def test_state_council_error_inheritance(self) -> None:
        """Test that StateCouncilError inherits from Error."""
        error = state_council_errors.StateCouncilError("Test error")

        assert isinstance(error, Error)
        assert str(error) == "Test error"

    def test_state_council_not_configured_error(self) -> None:
        """Test StateCouncilNotConfiguredError."""
        error = state_council_errors.StateCouncilNotConfiguredError("Not configured")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert str(error) == "Not configured"

    def test_state_council_validation_error_inheritance(self) -> None:
        """Test StateCouncilValidationError inherits from both StateCouncilError and ValidationError."""
        error = state_council_errors.StateCouncilValidationError("Validation failed")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert isinstance(error, ValidationError)
        assert str(error) == "Validation failed"

    def test_state_council_permission_denied_error_inheritance(self) -> None:
        """Test StateCouncilPermissionDeniedError inherits from both StateCouncilError and PermissionDeniedError."""
        error = state_council_errors.StateCouncilPermissionDeniedError("Permission denied")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert isinstance(error, PermissionDeniedError)
        assert str(error) == "Permission denied"

    def test_insufficient_funds_error(self) -> None:
        """Test InsufficientFundsError."""
        error = state_council_errors.InsufficientFundsError("Insufficient funds")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert str(error) == "Insufficient funds"

    def test_monthly_issuance_limit_exceeded_error(self) -> None:
        """Test MonthlyIssuanceLimitExceededError."""
        error = state_council_errors.MonthlyIssuanceLimitExceededError("Limit exceeded")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert str(error) == "Limit exceeded"

    def test_department_not_found_error(self) -> None:
        """Test DepartmentNotFoundError."""
        error = state_council_errors.DepartmentNotFoundError("Department not found")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert str(error) == "Department not found"

    def test_identity_not_found_error(self) -> None:
        """Test IdentityNotFoundError."""
        error = state_council_errors.IdentityNotFoundError("Identity not found")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert str(error) == "Identity not found"

    def test_account_not_found_error(self) -> None:
        """Test AccountNotFoundError."""
        error = state_council_errors.AccountNotFoundError("Account not found")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert str(error) == "Account not found"

    def test_invalid_transfer_error(self) -> None:
        """Test InvalidTransferError."""
        error = state_council_errors.InvalidTransferError("Invalid transfer")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert str(error) == "Invalid transfer"

    def test_business_license_not_found_error(self) -> None:
        """Test BusinessLicenseNotFoundError."""
        error = state_council_errors.BusinessLicenseNotFoundError("License not found")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert str(error) == "License not found"

    def test_duplicate_license_error(self) -> None:
        """Test DuplicateLicenseError."""
        error = state_council_errors.DuplicateLicenseError("Duplicate license")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert str(error) == "Duplicate license"

    def test_invalid_license_status_error(self) -> None:
        """Test InvalidLicenseStatusError."""
        error = state_council_errors.InvalidLicenseStatusError("Invalid license status")

        assert isinstance(error, state_council_errors.StateCouncilError)
        assert str(error) == "Invalid license status"

    def test_all_error_exports(self) -> None:
        """Test that all expected errors are in __all__."""
        expected_errors = [
            "StateCouncilError",
            "StateCouncilNotConfiguredError",
            "StateCouncilValidationError",
            "StateCouncilPermissionDeniedError",
            "InsufficientFundsError",
            "MonthlyIssuanceLimitExceededError",
            "DepartmentNotFoundError",
            "IdentityNotFoundError",
            "AccountNotFoundError",
            "InvalidTransferError",
            "BusinessLicenseNotFoundError",
            "DuplicateLicenseError",
            "InvalidLicenseStatusError",
        ]

        assert state_council_errors.__all__ == expected_errors

    def test_error_types_can_be_used_in_result_context(self) -> None:
        """Test that error types can be safely used in Result context."""
        # Test that errors can be instantiated and have the expected attributes
        errors_to_test = [
            state_council_errors.StateCouncilError("Base error"),
            state_council_errors.StateCouncilNotConfiguredError("Not configured"),
            state_council_errors.StateCouncilValidationError("Validation error"),
            state_council_errors.StateCouncilPermissionDeniedError("Permission denied"),
            state_council_errors.InsufficientFundsError("Insufficient funds"),
            state_council_errors.MonthlyIssuanceLimitExceededError("Limit exceeded"),
            state_council_errors.DepartmentNotFoundError("Department not found"),
            state_council_errors.IdentityNotFoundError("Identity not found"),
            state_council_errors.AccountNotFoundError("Account not found"),
            state_council_errors.InvalidTransferError("Invalid transfer"),
            state_council_errors.BusinessLicenseNotFoundError("License not found"),
            state_council_errors.DuplicateLicenseError("Duplicate license"),
            state_council_errors.InvalidLicenseStatusError("Invalid license status"),
        ]

        for error in errors_to_test:
            # Verify they are exceptions
            assert isinstance(error, Exception)
            # Verify they have meaningful string representation
            assert str(error) != ""
            # Verify they can be raised and caught
            try:
                raise error
            except type(error) as caught:
                assert str(caught) == str(error)
