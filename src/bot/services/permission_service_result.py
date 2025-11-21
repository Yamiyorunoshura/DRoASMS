"""Legacy匯入路徑：改為 re-export Result 版 PermissionService。"""

from __future__ import annotations

from src.bot.services.permission_service import (
    PermissionChecker,
    PermissionError,
    PermissionResult,
    PermissionService,
)
from src.infra.result_compat import mark_legacy

mark_legacy("src.bot.services.permission_service_result")

__all__ = [
    "PermissionService",
    "PermissionResult",
    "PermissionError",
    "PermissionChecker",
]
