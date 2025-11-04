from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

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


def _docker_compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["bash", "-lc", "docker compose " + " ".join(args)]
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=check,
    )


def _container_id(service: str) -> str:
    out = _docker_compose("ps -q", service, check=True).stdout.strip()
    if not out:
        raise RuntimeError(f"No container for service: {service}")
    return out.splitlines()[0].strip()


def _inspect_json(container: str) -> dict[str, Any]:
    raw = subprocess.check_output(
        ["bash", "-lc", f"docker inspect {shlex.quote(container)}"],
        cwd=str(REPO_ROOT),
    )
    data = json.loads(raw.decode("utf-8"))
    return data[0]  # type: ignore[no-any-return]


def _parse_time(ts: str) -> datetime:
    # Docker returns RFC3339 with Z; Python needs +00:00
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


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
        reason="Docker/Compose 不可用，略過依賴順序測試",
    ),
]


@pytest.mark.timeout(240)
def test_compose_dependencies_postgres_healthy_before_bot_ready(tmp_path: Path) -> None:
    """驗證 postgres 先變為 healthy，之後才出現 bot.ready。"""

    token = os.getenv("TEST_DISCORD_TOKEN") or os.getenv("DISCORD_TOKEN")
    if not token:
        pytest.skip("未提供 TEST_DISCORD_TOKEN/DISCORD_TOKEN，略過 compose 依賴順序測試")

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

        # 啟動 compose
        _docker_compose("up -d --build", check=True)

        # 等待 postgres 變為 healthy
        pg_id = _container_id("postgres")
        deadline = time.time() + 120
        became_healthy_at: datetime | None = None
        while time.time() < deadline:
            info = _inspect_json(pg_id)
            status = (info.get("State", {}).get("Health", {}) or {}).get("Status")
            if status == "healthy":
                # 取最後一次健康紀錄的結束時間
                log = info["State"]["Health"].get("Log") or []
                for rec in reversed(log):
                    if (rec.get("ExitCode") == 0) and rec.get("End"):
                        became_healthy_at = _parse_time(rec["End"])
                        break
                break
            time.sleep(2)

        if became_healthy_at is None:
            pytest.fail("postgres 未在 120s 內變為 healthy")

        # bot 應在 postgres healthy 之後才就緒
        # 先驗證容器啟動時間 > healthy 時間
        bot_id = _container_id("bot")
        bot_started_at = _parse_time(_inspect_json(bot_id)["State"]["StartedAt"])
        assert (
            bot_started_at >= became_healthy_at
        ), f"bot 啟動時間({bot_started_at}) 早於 postgres healthy({became_healthy_at})"

        # 再追蹤 bot 日誌確認就緒訊號
        pattern = re.compile(r"\{.*\"event\"\s*:\s*\"bot.ready\".*\}")
        deadline = time.time() + 120
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
                    return
                if time.time() > deadline:
                    pytest.fail("超出 120s 未看到 bot.ready 事件（在 postgres healthy 後）")
        finally:
            proc.terminate()
    finally:
        _docker_compose("down")
        if env_backup is None:
            if env_path.exists():
                env_path.unlink()
        else:
            env_path.write_text(env_backup, encoding="utf-8")
