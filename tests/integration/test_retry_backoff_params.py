from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
@pytest.mark.timeout(30)
def test_retry_backoff_attempt_count_and_delays() -> None:
    """設定小的重試/退避參數時，應輸出對應次數與 delay_ms 欄位。"""

    script = REPO_ROOT / "docker" / "bin" / "entrypoint.sh"
    assert script.exists(), f"入口腳本不存在: {script}"

    env = os.environ.copy()
    env["DISCORD_TOKEN"] = env.get("DISCORD_TOKEN", "test-token")
    env["DATABASE_URL"] = "postgresql://user:pass@203.0.113.10:5432/db"  # 不可達
    env["RETRY_MAX_ATTEMPTS"] = "3"
    env["RETRY_BASE_DELAY_MS"] = "50"
    env["RETRY_MAX_TOTAL_MS"] = "500"
    env["DB_CONNECT_TIMEOUT_MS"] = "50"

    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env)
    output = (proc.stdout or "") + (proc.stderr or "")

    attempts = [line for line in output.splitlines() if '"event":"db.connect.attempt"' in line]
    delays = [line for line in output.splitlines() if '"event":"db.connect.retry"' in line]

    assert len(attempts) == 3, f"應有 3 次嘗試，實際 {len(attempts)}，輸出:\n{output}"
    assert len(delays) >= 2, f"應至少有 2 次 retry delay 記錄，輸出:\n{output}"

    # 簡單驗證 delay_ms 欄位為整數
    for line in delays:
        m = re.search(r'"delay_ms":(\d+)', line)
        assert m, f"retry 日誌應包含 delay_ms 欄位: {line}"
