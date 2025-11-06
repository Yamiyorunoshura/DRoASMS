from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _has_cmd(cmd: str) -> bool:
    return (
        subprocess.call(
            ["bash", "-lc", f"command -v {shlex.quote(cmd)} >/dev/null"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        == 0
    )


pytestmark = [
    pytest.mark.skipif(
        os.getenv("RUN_DOCKER_TESTS", "").lower() not in {"1", "true", "yes"},
        reason="未啟用 RUN_DOCKER_TESTS，略過 Docker 組態測試",
    ),
    pytest.mark.skipif(
        not _has_cmd("docker"),
        reason="Docker 不可用，略過外部 DB 覆寫測試",
    ),
]


@pytest.mark.integration
def test_compose_uses_external_database_url_when_overridden(tmp_path: Path) -> None:
    """當 .env 指定 DATABASE_URL 時，compose 應採用該值覆寫預設。"""

    # 使用臨時 env 檔案搭配 --env-file，避免測試之間互相影響與系統環境變數干擾
    override = "postgresql://user:pass@db.example.com:5432/prod"
    override_env = tmp_path / "override.env"
    override_env.write_text(f"DATABASE_URL={override}\n", encoding="utf-8")

    # 以 JSON 讀取展開後的 compose 設定，避免 YAML 排版差異造成誤判
    raw = subprocess.check_output(
        [
            "bash",
            "-lc",
            f"docker compose --env-file {shlex.quote(str(override_env))} -f compose.yaml config --format json",
        ],
        cwd=str(REPO_ROOT),
    )
    cfg = json.loads(raw.decode("utf-8"))
    env = cfg.get("services", {}).get("bot", {}).get("environment", {}) or {}
    assert env.get("DATABASE_URL") == override, "compose 應使用外部 DATABASE_URL 覆寫預設"
