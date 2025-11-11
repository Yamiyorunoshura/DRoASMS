from __future__ import annotations

import logging
import os
import sys
from typing import Any, Mapping, MutableMapping

import structlog

_configured: bool = False


def _add_msg_from_event(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> Mapping[str, Any]:
    """Ensure `msg` exists by mirroring `event` for compatibility.

    Spec requires JSON Lines keys: ts, level, msg, event.
    structlog uses `event` as the message field; we also provide `msg`.
    """

    if "msg" not in event_dict and isinstance(event_dict.get("event"), str):
        event_dict["msg"] = event_dict["event"]
    return event_dict


_SENSITIVE_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "auth",
    "password",
    "secret",
    "api_key",
    "apikey",
    "client_secret",
}


def _mask_sensitive_values(
    _: Any, __: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    """Redact sensitive values from the log dictionary.

    - Applies to common secret-bearing keys (case-insensitive).
    - Masks values recursively in nested dicts/lists.
    """

    def mask_value(key: str, value: Any) -> Any:
        if isinstance(value, dict):
            from typing import Mapping as _Mapping
            from typing import cast as _cast

            d = _cast(_Mapping[str, Any], value)
            return {k: mask_value(k, v) for k, v in d.items()}
        if isinstance(value, list):
            # list 類型已由 isinstance 確認，無需再 cast
            return [mask_value(key, v) for v in value]
        if key.lower() in _SENSITIVE_KEYS:
            if isinstance(value, str):
                return "[REDACTED]"
            return "[REDACTED]"
        return value

    masked: dict[str, Any] = {k: mask_value(k, v) for k, v in event_dict.items()}
    return masked


def configure_logging(level: str | None = None) -> None:
    """Configure structlog/stdlib logging for JSON Lines output.

    - Keys: ts, level, msg, event
    - Timestamp: UTC ISO-8601
    - Output: one JSON object per line (stdout via stdlib logging)
    """

    global _configured

    raw_level: str = level if level is not None else os.getenv("LOG_LEVEL", "INFO")
    level_name = raw_level.upper()
    log_level = getattr(logging, level_name, logging.INFO)

    # stdlib logger prints structlog-rendered JSON to stdout without extra formatting.
    # Use force=True so that tests using capsys (which swaps sys.stdout) can reconfigure
    # the handler to the current stream by calling configure_logging() again.
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            _add_msg_from_event,
            _mask_sensitive_values,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configured = True
