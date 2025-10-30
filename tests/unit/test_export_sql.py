from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.db.gateway.council_governance import CouncilGovernanceGateway


class _CaptureConn:
    def __init__(self) -> None:
        self.sql: str | None = None
        self.args: tuple | None = None

    async def fetch(self, sql: str, guild_id: int, start: datetime, end: datetime):  # type: ignore[override]
        self.sql = sql
        self.args = (guild_id, start, end)
        return []


@pytest.mark.asyncio
async def test_export_interval_uses_lateral_subqueries() -> None:
    gw = CouncilGovernanceGateway()
    c = _CaptureConn()
    start = datetime.now(timezone.utc) - timedelta(days=1)
    end = datetime.now(timezone.utc)
    rows = await gw.export_interval(c, guild_id=1, start=start, end=end)
    assert rows == []
    assert c.sql is not None
    # 確認使用兩個 JOIN LATERAL（votes 與 snapshot 各一次）
    assert c.sql.count("JOIN LATERAL") >= 2
    assert "FROM governance.votes v" in c.sql
    assert "FROM governance.proposal_snapshots ps" in c.sql
