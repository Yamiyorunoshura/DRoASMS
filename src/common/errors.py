"""
Error types for Result<T,E> error handling system.

This module defines the hierarchy of error types used throughout the DRoASMS system
to provide type-safe, structured error handling.
"""

import json
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


def _empty_context() -> Dict[str, Any]:
    """Default factory for error context with precise typing."""
    return {}


class ErrorSeverity(Enum):
    """Error severity levels for classification and monitoring."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better error classification."""

    DATABASE = "database"
    DISCORD = "discord"
    VALIDATION = "validation"
    NETWORK = "network"
    PERMISSION = "permission"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"


@dataclass
class BaseError(ABC):
    """Base error class for all DRoASMS errors.

    Provides common structure for error handling, logging, and monitoring.
    """

    message: str
    category: ErrorCategory
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    context: Dict[str, Any] = field(default_factory=_empty_context)
    timestamp: datetime = field(default_factory=datetime.now)
    cause: Optional[Exception] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None,
        }

    def to_json(self) -> str:
        """Convert error to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.message}"


@dataclass
class DatabaseError(BaseError):
    """Error class for database-related operations."""

    operation: Optional[str] = None
    table: Optional[str] = None
    query: Optional[str] = None

    def __post_init__(self) -> None:
        if self.category == ErrorCategory.BUSINESS_LOGIC:  # Allow overriding category
            self.category = ErrorCategory.DATABASE


@dataclass
class DiscordError(BaseError):
    """Error class for Discord API related operations."""

    api_method: Optional[str] = None
    endpoint: Optional[str] = None
    user_id: Optional[int] = None
    guild_id: Optional[int] = None

    def __post_init__(self) -> None:
        if self.category == ErrorCategory.BUSINESS_LOGIC:  # Allow overriding category
            self.category = ErrorCategory.DISCORD


@dataclass
class ValidationError(BaseError):
    """Error class for data validation failures."""

    field: Optional[str] = None
    value: Optional[Any] = None
    constraint: Optional[str] = None

    def __post_init__(self) -> None:
        if self.category == ErrorCategory.BUSINESS_LOGIC:  # Allow overriding category
            self.category = ErrorCategory.VALIDATION


@dataclass
class NetworkError(BaseError):
    """Error class for network-related operations."""

    url: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None

    def __post_init__(self) -> None:
        if self.category == ErrorCategory.BUSINESS_LOGIC:  # Allow overriding category
            self.category = ErrorCategory.NETWORK


@dataclass
class PermissionError(BaseError):
    """Error class for permission-related failures."""

    required_permission: Optional[str] = None
    user_id: Optional[int] = None
    resource: Optional[str] = None

    def __post_init__(self) -> None:
        if self.category == ErrorCategory.BUSINESS_LOGIC:  # Allow overriding category
            self.category = ErrorCategory.PERMISSION


@dataclass
class BusinessLogicError(BaseError):
    """Error class for business logic violations."""

    business_rule: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.category == ErrorCategory.BUSINESS_LOGIC:  # Allow overriding category
            self.category = ErrorCategory.BUSINESS_LOGIC


@dataclass
class SystemError(BaseError):
    """Error class for system-level failures."""

    component: Optional[str] = None
    system_state: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.category == ErrorCategory.BUSINESS_LOGIC:  # Allow overriding category
            self.category = ErrorCategory.SYSTEM
