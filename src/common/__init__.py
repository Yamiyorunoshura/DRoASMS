"""
Common utilities and types for DRoASMS Discord bot.
"""

from .errors import BaseError, DatabaseError, DiscordError, ValidationError
from .result import AsyncResult, Err, Ok, Result

__all__ = [
    "Result",
    "Ok",
    "Err",
    "AsyncResult",
    "BaseError",
    "DatabaseError",
    "DiscordError",
    "ValidationError",
]
