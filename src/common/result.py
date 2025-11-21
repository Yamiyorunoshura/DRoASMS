"""Legacy compatibility facade for canonical Result helpers.

新的程式碼必須直接從 ``src.infra.result`` 匯入 Result / Error 相關型別；
此模組僅保留給尚未改寫的相依，並在載入時回報給遷移追蹤器。
"""

from __future__ import annotations

import warnings

from src.infra.result import (
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
from src.infra.result_compat import mark_legacy

warnings.warn(
    "`src.common.result` 僅做為相容層存在；請改用 `src.infra.result`.",
    DeprecationWarning,
    stacklevel=2,
)

mark_legacy("src.common.result")

__all__ = [
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
