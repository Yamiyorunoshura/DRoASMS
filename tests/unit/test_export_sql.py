from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from src.db.gateway.council_governance import CouncilGovernanceGateway


class _CaptureConn:
    def __init__(self) -> None:
        self.sql: str | None = None
        self.args: tuple[Any, ...] | None = None

    async def fetch(self, sql: str, guild_id: int, start: datetime, end: datetime) -> list[Any]:
        # 捕捉傳入 SQL 與參數以驗證 Gateway 只呼叫資料庫函式
        self.sql = sql
        self.args = (guild_id, start, end)
        return []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_export_interval_calls_db_function_only() -> None:
    """新版實作將匯出邏輯下放至資料庫函式。

    驗證 Gateway 僅呼叫 `governance.fn_export_interval($1,$2,$3)`，
    不再於 Python 端組裝包含 JOIN LATERAL 的查詢。
    """
    gw = CouncilGovernanceGateway()
    c = _CaptureConn()
    start = datetime.now(timezone.utc) - timedelta(days=1)
    end = datetime.now(timezone.utc)
    rows = await gw.export_interval(c, guild_id=1, start=start, end=end)
    assert rows == []
    assert c.sql is not None
    assert c.sql.strip() == "SELECT * FROM governance.fn_export_interval($1,$2,$3)"
    assert c.args == (1, start, end)
