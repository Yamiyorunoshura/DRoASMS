"""Legacy compatibility shims for canonical Result error types.

此模組僅提供「相容層」匯入點，協助尚未完成遷移的模組在短期內
維持既有匯入路徑。所有新的錯誤型別 MUST 直接從 ``src.infra.result``
匯入；這裡只會 re-export 權威實作並在載入時發出棄用警告。
"""

from __future__ import annotations

import warnings

from src.infra.result import (
    BusinessLogicError,
    DatabaseError,
    DiscordError,
    PermissionDeniedError,
    SystemError,
    ValidationError,
)
from src.infra.result import (
    Error as BaseError,
)
from src.infra.result_compat import mark_legacy

warnings.warn(
    "`src.common.errors` 為僅供過渡期使用的匯入路徑；"
    "請改從 `src.infra.result` 匯入 Error/DatabaseError/ValidationError 等權威型別。",
    DeprecationWarning,
    stacklevel=2,
)

mark_legacy("src.common.errors")

__all__ = [
    "BaseError",
    "DatabaseError",
    "DiscordError",
    "ValidationError",
    "BusinessLogicError",
    "PermissionDeniedError",
    "SystemError",
]
