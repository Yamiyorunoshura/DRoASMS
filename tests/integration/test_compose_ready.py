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


pytestmark = [
    pytest.mark.skipif(
        os.getenv("RUN_DISCORD_INTEGRATION_TESTS", "").lower() not in {"1", "true", "yes"},
        reason="未啟用 RUN_DISCORD_INTEGRATION_TESTS，略過 Discord/Compose 整合測試",
    ),
    pytest.mark.skipif(
        not (
            (_has_cmd("docker") and _has_cmd("docker-compose"))
            or (_has_cmd("docker") and os.environ.get("COMPOSE_DOCKER_CLI_BUILD") is not None)
        ),
        reason="Docker/Compose 不可用，略過 compose 就緒測試",
    ),
]


@pytest.mark.timeout(180)
@pytest.mark.integration
def test_compose_ready_event_within_slo(tmp_path: Path, docker_compose_project: str) -> None:
    """以 docker compose 啟動並在 120s 內解析到 bot.ready。

    啟動條件：需提供 `TEST_DISCORD_TOKEN` 或 `DISCORD_TOKEN`。
    若未提供，測試將以 skip 處理。
    """

    token = os.getenv("TEST_DISCORD_TOKEN") or os.getenv("DISCORD_TOKEN")
    if not token:
        pytest.skip("未提供 TEST_DISCORD_TOKEN/DISCORD_TOKEN，略過 compose 就緒測試")

    env_path = REPO_ROOT / ".env"
    env_backup = None
    try:
        # 建立臨時 .env （保留既有 .env 以便還原）
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

        # 啟動 compose，使用獨立的專案名稱
        subprocess.run(
            ["bash", "-lc", f"docker compose -p {docker_compose_project} up -d --build"],
            check=True,
            cwd=str(REPO_ROOT),
        )

        # 追蹤 bot 日誌直到看到 bot.ready 或逾時
        deadline = time.time() + 120
        pattern = re.compile(r"\{.*\"event\"\s*:\s*\"bot.ready\".*\}")
        proc = subprocess.Popen(
            ["bash", "-lc", f"docker compose -p {docker_compose_project} logs -f bot"],
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
                    return
                if time.time() > deadline:
                    pytest.fail("超出 120s 未看到 bot.ready 事件")
        finally:
            proc.terminate()
    finally:
        # 清理與還原
        subprocess.run(
            ["bash", "-lc", f"docker compose -p {docker_compose_project} down"],
            cwd=str(REPO_ROOT),
            check=False,
        )
        if env_backup is None:
            if env_path.exists():
                env_path.unlink()
        else:
            env_path.write_text(env_backup, encoding="utf-8")
