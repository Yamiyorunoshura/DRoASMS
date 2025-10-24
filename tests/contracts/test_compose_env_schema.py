from __future__ import annotations

from pathlib import Path

from tests.contracts._utils import load_json_schema


def _parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        data[key.strip()] = val.strip()
    return data


def test_env_example_contains_required_keys() -> None:
    schema = load_json_schema("compose.env.schema.json")
    required = set(schema.get("required", []))

    path = Path(".env.example")
    assert path.exists(), ".env.example 應存在於倉庫根目錄"

    env_data = _parse_env_file(path)

    missing = [k for k in required if k not in env_data]
    assert not missing, f".env.example 應包含必要鍵: 缺少 {missing}"
