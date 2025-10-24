from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_missing_env_fails_fast_exit_64_and_event_present() -> None:
    script = REPO_ROOT / "docker" / "bin" / "entrypoint.sh"
    assert script.exists(), f"入口腳本不存在: {script}"

    env = os.environ.copy()
    env.pop("DISCORD_TOKEN", None)  # 確保缺少必要變數

    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env)

    # 退出碼 64
    assert proc.returncode == 64, (
        "應以 64 退出，實際: " f"{proc.returncode}, stderr={proc.stderr} stdout={proc.stdout}"
    )

    output = (proc.stdout or "") + (proc.stderr or "")
    assert "bot.config.error" in output, "應輸出 bot.config.error 事件"
