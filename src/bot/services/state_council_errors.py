"""State council governance specific error types."""

from __future__ import annotations

from src.infra.result import (
    Error,
    ValidationError,
)
from src.infra.result import (
    PermissionDeniedError as BasePermissionDeniedError,
)


class StateCouncilError(Error):
    """Base error for state council governance operations."""


class StateCouncilNotConfiguredError(StateCouncilError):
    """Raised when state council governance is not configured for a guild."""


class StateCouncilValidationError(StateCouncilError, ValidationError):
    """Validation error for state council operations."""


class StateCouncilPermissionDeniedError(StateCouncilError, BasePermissionDeniedError):
    """Permission denied for state council operations."""


class InsufficientFundsError(StateCouncilError):
    """Raised when there are insufficient funds for an operation."""


class MonthlyIssuanceLimitExceededError(StateCouncilError):
    """Raised when monthly issuance limit is exceeded."""


class DepartmentNotFoundError(StateCouncilError):
    """Raised when a department is not found."""


class IdentityNotFoundError(StateCouncilError):
    """Raised when an identity record is not found."""


class AccountNotFoundError(StateCouncilError):
    """Raised when a government account is not found."""


class InvalidTransferError(StateCouncilError):
    """Raised when a transfer operation is invalid."""


__all__ = [
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
]
