from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    """Return repository root inferred from tests directory position.

    tests/contracts/_utils.py -> repo_root = parents[2]
    """
    return Path(__file__).resolve().parents[2]


def contracts_dir() -> Path:
    """Directory containing JSON Schemas for this feature."""
    return repo_root() / "specs" / "002-docker-run-bot" / "contracts"


def contract_path(name: str) -> Path:
    """Return absolute path to a schema file in contracts/.

    Example: contract_path("log-events.schema.json")
    """
    path = contracts_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    return path


def load_json_schema(name: str) -> dict[str, Any]:
    """Load and return the JSON schema as a dict.

    Raises FileNotFoundError if the schema does not exist.
    """
    with contract_path(name).open("r", encoding="utf-8") as f:
        result = json.load(f)
        return result  # type: ignore[no-any-return]
