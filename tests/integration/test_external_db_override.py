from __future__ import annotations

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


pytestmark = pytest.mark.skipif(
    not _has_cmd("docker"),
    reason="Docker 不可用，略過外部 DB 覆寫測試",
)


def test_compose_uses_external_database_url_when_overridden(tmp_path: Path) -> None:
    """當 .env 指定 DATABASE_URL 時，compose 應採用該值覆寫預設。"""

    env_path = REPO_ROOT / ".env"
    env_backup = env_path.read_text(encoding="utf-8") if env_path.exists() else None
    try:
        # 寫入僅含 DATABASE_URL 的最小 .env
        override = "postgresql://user:pass@db.example.com:5432/prod"
        env_path.write_text(f"DATABASE_URL={override}\n", encoding="utf-8")

        # 輸出展開後的 compose 設定
        out = subprocess.check_output(
            ["bash", "-lc", "docker compose config"], cwd=str(REPO_ROOT)
        ).decode("utf-8")

        # 期望在 bot 服務的 environment 中出現覆寫值
        assert (
            f"DATABASE_URL: {override}" in out or f"- DATABASE_URL={override}" in out
        ), "compose 應使用外部 DATABASE_URL 覆寫預設"
    finally:
        # 還原 .env
        if env_backup is None:
            if env_path.exists():
                env_path.unlink()
        else:
            env_path.write_text(env_backup, encoding="utf-8")
