"""Legacy re-export module for backward compatibility.

新的程式碼應直接從 ``src.infra.result`` 匯入；此模組僅保留給未改寫的
相依，以免破壞既有匯入路徑。
"""

from src.infra.result import (
    AsyncResult,
    DatabaseError,
    DiscordError,
    Err,
    Ok,
    Result,
    ValidationError,
)
from src.infra.result import (
    Error as BaseError,
)

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
