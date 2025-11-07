from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
@pytest.mark.timeout(30)
def test_external_db_unavailable_reports_exit_69_and_event() -> None:
    """將 DATABASE_URL 指向不可達主機時，應在重試後以 69 結束並輸出 db.unavailable。"""

    script = REPO_ROOT / "docker" / "bin" / "entrypoint.sh"
    assert script.exists(), f"入口腳本不存在: {script}"

    # 203.0.113.0/24 為測試保留網段，應不可達
    env = os.environ.copy()
    env["DISCORD_TOKEN"] = env.get("DISCORD_TOKEN", "test-token")
    env["DATABASE_URL"] = "postgresql://user:pass@203.0.113.10:5432/db"
    env["RETRY_MAX_ATTEMPTS"] = "2"
    env["RETRY_BASE_DELAY_MS"] = "50"
    env["RETRY_MAX_TOTAL_MS"] = "500"

    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env)

    assert proc.returncode == 69, (
        f"應以 69 退出（依賴不可用），實際: {proc.returncode},\n"
        f"stderr={proc.stderr}\nstdout={proc.stdout}"
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    assert "db.unavailable" in output, "應輸出 db.unavailable 事件"
