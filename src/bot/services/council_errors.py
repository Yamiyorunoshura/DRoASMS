"""Council governance specific error types."""

from __future__ import annotations

from typing import Any

from src.infra.result import (
    Error,
    ValidationError,
)
from src.infra.result import (
    PermissionDeniedError as BasePermissionDeniedError,
)


class CouncilError(Error):
    """Base error for council governance operations."""


class GovernanceNotConfiguredError(CouncilError):
    """Raised when council governance is not configured for a guild."""

    def __init__(
        self, message: str = "Council governance is not configured for this guild", **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)


class CouncilValidationError(CouncilError, ValidationError):
    """Validation error for council operations."""


class CouncilPermissionDeniedError(CouncilError, BasePermissionDeniedError):
    """Permission denied for council operations."""


class ProposalNotFoundError(CouncilError):
    """Raised when a proposal is not found."""


class InvalidProposalStatusError(CouncilError):
    """Raised when proposal status is invalid for the operation."""


class VotingNotAllowedError(CouncilError):
    """Raised when voting is not allowed on a proposal."""


class ProposalLimitExceededError(CouncilError):
    """Raised when guild has too many active proposals."""


class ExecutionFailedError(CouncilError):
    """Raised when proposal execution fails."""

    def __init__(self, message: str, *, execution_error: str | None = None, **context: Any) -> None:
        super().__init__(message, context=context)
        self.execution_error = execution_error


__all__ = [
    "CouncilError",
    "GovernanceNotConfiguredError",
    "CouncilValidationError",
    "CouncilPermissionDeniedError",
    "ProposalNotFoundError",
    "InvalidProposalStatusError",
    "VotingNotAllowedError",
    "ProposalLimitExceededError",
    "ExecutionFailedError",
]
