from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    not os.getenv("TEST_MIGRATION_DB_URL"),
    reason="需提供 TEST_MIGRATION_DB_URL（可用資料庫）以模擬遷移失敗",
)
def test_migration_failure_exit_code_70() -> None:
    """使用存在的資料庫，但指定不存在的 Alembic 版本，應以 70 結束。"""

    script = REPO_ROOT / "docker" / "bin" / "entrypoint.sh"
    assert script.exists(), f"入口腳本不存在: {script}"

    env = os.environ.copy()
    env["DISCORD_TOKEN"] = env.get("DISCORD_TOKEN", "test-token")
    env["DATABASE_URL"] = os.environ["TEST_MIGRATION_DB_URL"]
    env["ALEMBIC_UPGRADE_TARGET"] = "__non_existent_revision__"
    # 快速通過連線檢查
    env.setdefault("RETRY_MAX_ATTEMPTS", "1")
    env.setdefault("RETRY_BASE_DELAY_MS", "1")
    env.setdefault("RETRY_MAX_TOTAL_MS", "1000")

    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env)

    assert proc.returncode == 70, (
        f"應以 70 退出（遷移失敗），實際: {proc.returncode},\n"
        f"stderr={proc.stderr}\nstdout={proc.stdout}"
    )
