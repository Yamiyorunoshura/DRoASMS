from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    """Return repository root by walking up until ``pyproject.toml`` is found.

    在部分 CI 環境下，工作目錄或 symlink 可能使得 parents[] 推導不穩定，
    以往用 parents[2] 的相對層級法在某些 runner 上會失敗。
    因此改為由當前檔案一路向上尋找 pyproject.toml 作為倉庫根指標。
    """
    cur = Path(__file__).resolve()
    for p in [cur, *cur.parents]:
        if (p / "pyproject.toml").exists():
            return p
    # 後備：若未找到（理論上不會），退回到原邏輯
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
