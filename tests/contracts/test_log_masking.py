from __future__ import annotations

import json
from typing import Any

import pytest
import structlog

from src.infra.logging.config import configure_logging


@pytest.mark.contract
def test_sensitive_values_are_masked_in_logs(capsys: Any) -> None:
    """Logger should not leak raw secrets for common sensitive keys.

    Verifies masking for both top-level and nested keys (e.g., token, authorization).
    """

    configure_logging()
    logger = structlog.get_logger("test.masking")

    secret_token = "secret_token_1234567890"
    bearer = "Bearer very_secret_authorization_value"

    logger.info(
        "test.masking.emit",
        token=secret_token,
        authorization=bearer,
        nested={"token": secret_token, "other": "ok"},
    )

    out = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(out)

    # Top-level masking
    assert payload.get("token") != secret_token
    assert payload.get("authorization") != bearer

    # Deep/nested masking
    assert payload.get("nested", {}).get("token") != secret_token

    # Raw secrets must not appear in serialized line
    assert secret_token not in out
    assert bearer not in out
