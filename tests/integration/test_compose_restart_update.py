from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _compose_cmd(*args: str) -> list[str]:
    return ["docker", "compose", "-f", str(REPO_ROOT / "compose.yaml"), *args]


@pytest.mark.integration
def test_compose_restart_update_cycle(tmp_path: Path) -> None:
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

    # Fresh restart cycle
    subprocess.run(_compose_cmd("down"), check=False)
    subprocess.run(_compose_cmd("up", "-d", "--build"), check=True)

    # Observe first bot.ready
    pattern = re.compile(r"\{.*\"event\"\s*:\s*\"bot.ready\".*\}")
    first_seen = _wait_for_log(pattern, timeout=180)
    if not first_seen:
        pytest.fail("第一次啟動 180s 內未看到 bot.ready 事件")

    # Restart just the bot service to simulate update/redeploy
    subprocess.run(_compose_cmd("up", "-d", "--build", "bot"), check=True)

    # Count bot.ready occurrences – we expect to see at least two
    count = _count_ready_events(duration=180)
    assert count >= 2, f"預期至少兩次 bot.ready 事件（重啟後），實際 {count}"


def _wait_for_log(pattern: re.Pattern[str], timeout: int) -> bool:
    """Stream logs and return True once a line matches pattern or timeout occurs."""
    start = time.time()
    with subprocess.Popen(
        _compose_cmd("logs", "-f", "bot"),
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


def _count_ready_events(duration: int) -> int:
    """Count occurrences of bot.ready from logs within the given duration."""
    end = time.time() + duration
    count = 0
    with subprocess.Popen(
        _compose_cmd("logs", "-f", "bot"),
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
