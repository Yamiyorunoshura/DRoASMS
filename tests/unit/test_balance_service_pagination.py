from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Sequence, cast

import pytest

from src.bot.services.balance_service import BalanceService
from src.db.gateway.economy_queries import EconomyQueryGateway, HistoryRecord
from src.infra.result import Ok


class _FakeGateway:
    def __init__(self, records: Sequence[HistoryRecord]) -> None:
        self._records = list(records)

    async def fetch_history(
        self,
        connection: Any,
        *,
        guild_id: int,
        member_id: int,
        limit: int,
        cursor: datetime | None,
    ) -> Sequence[HistoryRecord]:
        # 回傳預先準備好的資料列；不強制等於傳入的 limit
        return list(self._records)


class _FakeConn:
    def __init__(self, *, has_more: bool) -> None:
        self.has_more = has_more
        self.sql_seen: str | None = None

    async def fetchval(
        self, sql: str, guild_id: int, member_id: int, last_created: datetime
    ) -> bool:
        self.sql_seen = sql
        return self.has_more


class _FakeAcquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._c = conn

    async def __aenter__(self) -> _FakeConn:
        return self._c

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._c = conn

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self._c)


def _mk_record(created_at: datetime) -> HistoryRecord:
    # 建立最小可用的 HistoryRecord 供轉換
    from uuid import uuid4

    return HistoryRecord(
        transaction_id=uuid4(),
        guild_id=1,
        initiator_id=10,
        target_id=None,
        amount=5,
        direction="adjust",
        reason=None,
        created_at=created_at,
        metadata={},
        balance_after_initiator=0,
        balance_after_target=None,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_history_pagination_calls_db_has_more(monkeypatch: pytest.MonkeyPatch) -> None:
    # 準備剛好等於 limit 筆數 → 會觸發 has_more 查詢
    now = datetime.now(timezone.utc)
    items = [_mk_record(now - timedelta(seconds=i)) for i in range(3)]

    fake_conn = _FakeConn(has_more=True)
    fake_pool = _FakePool(fake_conn)

    svc = BalanceService(fake_pool, gateway=cast(EconomyQueryGateway, _FakeGateway(items)))

    result = await svc.get_history(
        guild_id=1,
        requester_id=42,
        target_member_id=42,
        can_view_others=False,
        limit=3,
        cursor=None,
    )

    assert isinstance(result, Ok)
    page = result.unwrap()

    assert page.items and page.next_cursor is not None
    # 驗證經由 SQL 函式觸發 has_more 判斷
    assert fake_conn.sql_seen == "SELECT economy.fn_has_more_history($1,$2,$3)"


@pytest.mark.asyncio
async def test_history_no_next_cursor_when_less_than_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    # 筆數少於 limit → 不觸發 has_more 查詢
    now = datetime.now(timezone.utc)
    items = [_mk_record(now)]
    fake_conn = _FakeConn(has_more=True)
    fake_pool = _FakePool(fake_conn)
    svc = BalanceService(fake_pool, gateway=cast(EconomyQueryGateway, _FakeGateway(items)))

    result = await svc.get_history(
        guild_id=1,
        requester_id=42,
        target_member_id=42,
        can_view_others=False,
        limit=3,
        cursor=None,
    )

    assert isinstance(result, Ok)
    page = result.unwrap()

    assert page.items and page.next_cursor is None
    assert fake_conn.sql_seen is None
