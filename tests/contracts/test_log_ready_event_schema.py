from __future__ import annotations

import json
from typing import Any

import structlog

from src.infra.logging.config import configure_logging
from tests.contracts._utils import load_json_schema


def _validate_against_schema(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    """以最小驗證邏輯檢查必要鍵與條件（避免額外相依）。"""
    required = set(schema.get("required", []))
    missing = [k for k in required if k not in payload]
    assert not missing, f"缺少必要鍵: {missing}"

    # event 為 bot.ready 的情形，需等於常值
    for rule in schema.get("allOf", []):
        cond = rule.get("if", {}).get("properties", {}).get("event", {})
        if cond.get("const") == "bot.ready" and payload.get("event") == "bot.ready":
            then = rule.get("then", {})
            props = then.get("properties", {}).get("event", {})
            if "const" in props:
                assert payload["event"] == props["const"]


def test_log_ready_event_matches_schema(capsys: Any) -> None:
    schema = load_json_schema("log-events.schema.json")
    configure_logging()
    logger = structlog.get_logger("test")

    logger.info("bot.ready", extra="sample")
    captured = capsys.readouterr().out.strip()
    assert captured, "應有一行 JSON 日誌輸出"

    payload = json.loads(captured)
    _validate_against_schema(payload, schema)
