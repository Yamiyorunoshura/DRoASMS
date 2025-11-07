from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _compose_cmd(project_name: str, *args: str) -> list[str]:
    return ["docker", "compose", "-p", project_name, "-f", str(REPO_ROOT / "compose.yaml"), *args]


def _has_cmd(cmd: str) -> bool:
    return (
        subprocess.call(
            ["bash", "-lc", f"command -v {shlex.quote(cmd)} >/dev/null"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        == 0
    )


# 在缺乏測試環境時（未顯式啟用或無 Docker）一律略過
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
        reason="Docker/Compose 不可用，略過整合測試",
    ),
]


@pytest.mark.timeout(300)
@pytest.mark.integration
def test_compose_restart_update_cycle(tmp_path: Path, docker_compose_project: str) -> None:
    """Down → Up → observe a second bot.ready event.

    Preconditions: requires TEST_DISCORD_TOKEN or DISCORD_TOKEN in env.
    The test is intentionally coarse and will be skipped when token is absent.
    """

    token = os.getenv("TEST_DISCORD_TOKEN") or os.getenv("DISCORD_TOKEN")
    if not token:
        pytest.skip("未提供 TEST_DISCORD_TOKEN/DISCORD_TOKEN，略過重啟/更新測試")

    # Ensure the token is present in .env used by compose
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.startswith("DISCORD_TOKEN="):
                lines[i] = f"DISCORD_TOKEN={token}"
                break
        else:
            lines.append(f"DISCORD_TOKEN={token}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        # Fresh restart cycle，使用獨立的專案名稱
        subprocess.run(_compose_cmd(docker_compose_project, "down"), check=False)
        subprocess.run(_compose_cmd(docker_compose_project, "up", "-d", "--build"), check=True)

        # Observe first bot.ready
        pattern = re.compile(r"\{.*\"event\"\s*:\s*\"bot.ready\".*\}")
        first_seen = _wait_for_log(docker_compose_project, pattern, timeout=180)
        if not first_seen:
            pytest.fail("第一次啟動 180s 內未看到 bot.ready 事件")

        # Restart just the bot service to simulate update/redeploy
        subprocess.run(
            _compose_cmd(docker_compose_project, "up", "-d", "--build", "bot"), check=True
        )

        # Count bot.ready occurrences – we expect to see at least two
        count = _count_ready_events(docker_compose_project, duration=180)
        assert count >= 2, f"預期至少兩次 bot.ready 事件（重啟後），實際 {count}"
    finally:
        # 確保清理 compose 專案
        subprocess.run(_compose_cmd(docker_compose_project, "down"), check=False)


def _wait_for_log(project_name: str, pattern: re.Pattern[str], timeout: int) -> bool:
    """Stream logs and return True once a line matches pattern or timeout occurs."""
    start = time.time()
    with subprocess.Popen(
        _compose_cmd(project_name, "logs", "-f", "bot"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1,
    ) as proc:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if pattern.search(line):
                    return True
                if time.time() - start > timeout:
                    return False
        finally:
            proc.terminate()
    return False


def _count_ready_events(project_name: str, duration: int) -> int:
    """Count occurrences of bot.ready from logs within the given duration."""
    end = time.time() + duration
    count = 0
    with subprocess.Popen(
        _compose_cmd(project_name, "logs", "-f", "bot"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1,
    ) as proc:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if '"event":"bot.ready"' in line:
                    count += 1
                if time.time() > end:
                    break
        finally:
            proc.terminate()
    return count
