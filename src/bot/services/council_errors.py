"""Council governance specific error types."""

from __future__ import annotations

from enum import Enum
from typing import Any

from src.infra.result import (
    Error,
    ValidationError,
)
from src.infra.result import (
    PermissionDeniedError as BasePermissionDeniedError,
)


class CouncilErrorCode(str, Enum):
    """常任理事會操作錯誤代碼。

    命名規則: COUNCIL_<CATEGORY>_<DETAIL>
    - CONFIG: 配置相關錯誤
    - VALIDATION: 輸入驗證錯誤
    - PERMISSION: 權限相關錯誤
    - PROPOSAL: 提案相關錯誤
    - VOTING: 投票相關錯誤
    - EXECUTION: 執行相關錯誤
    """

    # 配置錯誤
    COUNCIL_CONFIG_NOT_CONFIGURED = "COUNCIL_CONFIG_NOT_CONFIGURED"

    # 驗證錯誤
    COUNCIL_VALIDATION_INVALID_AMOUNT = "COUNCIL_VALIDATION_INVALID_AMOUNT"
    COUNCIL_VALIDATION_SELF_TARGET = "COUNCIL_VALIDATION_SELF_TARGET"
    COUNCIL_VALIDATION_INVALID_CHOICE = "COUNCIL_VALIDATION_INVALID_CHOICE"
    COUNCIL_VALIDATION_INVALID_TARGET = "COUNCIL_VALIDATION_INVALID_TARGET"

    # 權限錯誤
    COUNCIL_PERMISSION_DENIED = "COUNCIL_PERMISSION_DENIED"
    COUNCIL_PERMISSION_NO_MEMBERS = "COUNCIL_PERMISSION_NO_MEMBERS"
    COUNCIL_PERMISSION_NOT_IN_SNAPSHOT = "COUNCIL_PERMISSION_NOT_IN_SNAPSHOT"

    # 提案錯誤
    COUNCIL_PROPOSAL_NOT_FOUND = "COUNCIL_PROPOSAL_NOT_FOUND"
    COUNCIL_PROPOSAL_INVALID_STATUS = "COUNCIL_PROPOSAL_INVALID_STATUS"
    COUNCIL_PROPOSAL_LIMIT_EXCEEDED = "COUNCIL_PROPOSAL_LIMIT_EXCEEDED"

    # 投票錯誤
    COUNCIL_VOTING_NOT_ALLOWED = "COUNCIL_VOTING_NOT_ALLOWED"

    # 執行錯誤
    COUNCIL_EXECUTION_FAILED = "COUNCIL_EXECUTION_FAILED"
    COUNCIL_EXECUTION_NO_CONFIG = "COUNCIL_EXECUTION_NO_CONFIG"
    COUNCIL_EXECUTION_DEPARTMENT_NOT_FOUND = "COUNCIL_EXECUTION_DEPARTMENT_NOT_FOUND"
    COUNCIL_EXECUTION_TRANSFER_FAILED = "COUNCIL_EXECUTION_TRANSFER_FAILED"

    # 通用錯誤
    COUNCIL_UNKNOWN_ERROR = "COUNCIL_UNKNOWN_ERROR"


class CouncilError(Error):
    """常任理事會操作的基礎錯誤類型。"""

    error_code: CouncilErrorCode = CouncilErrorCode.COUNCIL_UNKNOWN_ERROR

    def __init__(
        self, message: str, *, error_code: CouncilErrorCode | None = None, **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)
        if error_code is not None:
            self.error_code = error_code


class GovernanceNotConfiguredError(CouncilError):
    """當公會未配置常任理事會治理時拋出。"""

    error_code = CouncilErrorCode.COUNCIL_CONFIG_NOT_CONFIGURED

    def __init__(
        self,
        message: str = "此公會尚未配置常任理事會治理。",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message, error_code=CouncilErrorCode.COUNCIL_CONFIG_NOT_CONFIGURED, **kwargs
        )


class CouncilValidationError(CouncilError, ValidationError):
    """常任理事會操作的輸入驗證錯誤。"""

    error_code = CouncilErrorCode.COUNCIL_VALIDATION_INVALID_AMOUNT

    def __init__(
        self,
        message: str,
        *,
        error_code: CouncilErrorCode = CouncilErrorCode.COUNCIL_VALIDATION_INVALID_AMOUNT,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, error_code=error_code, **kwargs)


class CouncilPermissionDeniedError(CouncilError, BasePermissionDeniedError):
    """常任理事會操作的權限被拒絕錯誤。"""

    error_code = CouncilErrorCode.COUNCIL_PERMISSION_DENIED

    def __init__(
        self,
        message: str,
        *,
        error_code: CouncilErrorCode = CouncilErrorCode.COUNCIL_PERMISSION_DENIED,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, error_code=error_code, **kwargs)


class ProposalNotFoundError(CouncilError):
    """當找不到提案時拋出。"""

    error_code = CouncilErrorCode.COUNCIL_PROPOSAL_NOT_FOUND

    def __init__(self, message: str = "找不到指定的提案。", **kwargs: Any) -> None:
        super().__init__(message, error_code=CouncilErrorCode.COUNCIL_PROPOSAL_NOT_FOUND, **kwargs)


class InvalidProposalStatusError(CouncilError):
    """當提案狀態對於該操作無效時拋出。"""

    error_code = CouncilErrorCode.COUNCIL_PROPOSAL_INVALID_STATUS

    def __init__(self, message: str = "提案狀態不允許此操作。", **kwargs: Any) -> None:
        super().__init__(
            message, error_code=CouncilErrorCode.COUNCIL_PROPOSAL_INVALID_STATUS, **kwargs
        )


class VotingNotAllowedError(CouncilError):
    """當不允許對提案投票時拋出。"""

    error_code = CouncilErrorCode.COUNCIL_VOTING_NOT_ALLOWED

    def __init__(self, message: str = "不允許對此提案投票。", **kwargs: Any) -> None:
        super().__init__(message, error_code=CouncilErrorCode.COUNCIL_VOTING_NOT_ALLOWED, **kwargs)


class ProposalLimitExceededError(CouncilError):
    """當公會有過多進行中提案時拋出。"""

    error_code = CouncilErrorCode.COUNCIL_PROPOSAL_LIMIT_EXCEEDED

    def __init__(
        self, message: str = "公會已達提案上限，請先完成或取消現有提案。", **kwargs: Any
    ) -> None:
        super().__init__(
            message, error_code=CouncilErrorCode.COUNCIL_PROPOSAL_LIMIT_EXCEEDED, **kwargs
        )


class ExecutionFailedError(CouncilError):
    """當提案執行失敗時拋出。"""

    error_code = CouncilErrorCode.COUNCIL_EXECUTION_FAILED

    def __init__(
        self,
        message: str = "提案執行失敗。",
        *,
        execution_error: str | None = None,
        error_code: CouncilErrorCode = CouncilErrorCode.COUNCIL_EXECUTION_FAILED,
        **context: Any,
    ) -> None:
        super().__init__(message, error_code=error_code, context=context)
        self.execution_error = execution_error


__all__ = [
    "CouncilErrorCode",
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
