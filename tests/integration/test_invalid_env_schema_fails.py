from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_invalid_database_url_schema_exit_78() -> None:
    """若 DATABASE_URL 非 postgresql:// 開頭，應以 78 結束並輸出 bot.config.invalid。"""

    script = REPO_ROOT / "docker" / "bin" / "entrypoint.sh"
    assert script.exists(), f"入口腳本不存在: {script}"

    env = os.environ.copy()
    env["DISCORD_TOKEN"] = env.get("DISCORD_TOKEN", "test-token")
    env["DATABASE_URL"] = "not-a-valid-dsn"

    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env)

    assert proc.returncode == 78, (
        f"應以 78 退出（無效設定/Schema），實際: {proc.returncode},\n"
        f"stderr={proc.stderr}\nstdout={proc.stdout}"
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    assert "bot.config.invalid" in output, "應輸出 bot.config.invalid 事件"
