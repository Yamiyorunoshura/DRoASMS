from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
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


def _docker_compose(cmd: str) -> None:
    subprocess.run(["bash", "-lc", f"{cmd}"], cwd=str(REPO_ROOT), check=True)


pytestmark = pytest.mark.skipif(
    not (
        (_has_cmd("docker") and _has_cmd("docker-compose"))
        or (_has_cmd("docker") and os.environ.get("COMPOSE_DOCKER_CLI_BUILD") is not None)
    ),
    reason="Docker/Compose 不可用，略過依賴延遲測試",
)


@pytest.mark.timeout(300)
def test_db_not_ready_retry_eventually_succeeds(tmp_path: Path) -> None:
    """模擬 Postgres 延遲啟動，最終仍應成功並輸出 bot.ready。"""

    token = os.getenv("TEST_DISCORD_TOKEN") or os.getenv("DISCORD_TOKEN")
    if not token:
        pytest.skip("未提供 TEST_DISCORD_TOKEN/DISCORD_TOKEN，略過依賴延遲測試")

    env_path = REPO_ROOT / ".env"
    env_backup = None
    try:
        # 建立臨時 .env（保留既有以便還原）
        if env_path.exists():
            env_backup = env_path.read_text(encoding="utf-8")
        base = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        lines = []
        for line in base.splitlines():
            if line.startswith("DISCORD_TOKEN="):
                lines.append(f"DISCORD_TOKEN={token}")
            else:
                lines.append(line)
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # 啟動 compose，覆寫為慢啟動的 postgres
        start_time = time.time()
        cmd = (
            "docker compose -f compose.yaml "
            "-f tests/integration/overrides/compose.slow-postgres.yaml "
            "up -d --build"
        )
        _docker_compose(cmd)

        # 追蹤 bot 日誌直到看到 bot.ready 或逾時
        deadline = time.time() + 240
        pattern = re.compile(r"\{.*\"event\"\s*:\s*\"bot.ready\".*\}")
        proc = subprocess.Popen(
            ["bash", "-lc", "docker compose logs -f bot"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if pattern.search(line):
                    # 應經歷至少 15s（由慢啟動注入）
                    assert time.time() - start_time >= 15, "未觀察到延遲效應，可能覆寫未生效"
                    return
                if time.time() > deadline:
                    pytest.fail("超出 240s 未看到 bot.ready 事件（延遲啟動情境）")
        finally:
            proc.terminate()
    finally:
        subprocess.run(["bash", "-lc", "docker compose down"], cwd=str(REPO_ROOT))
        if env_backup is None:
            if env_path.exists():
                env_path.unlink()
        else:
            env_path.write_text(env_backup, encoding="utf-8")
