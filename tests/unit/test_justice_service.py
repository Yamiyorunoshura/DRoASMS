from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot.services.state_council_service import StateCouncilService
from src.infra.result import Ok


@pytest.mark.asyncio
async def test_get_active_suspects_result_ok() -> None:
    svc = StateCouncilService()
    svc._justice_gateway = AsyncMock()  # type: ignore[attr-defined]
    fake_suspects = [object()]
    # 模擬 gateway 回傳列表
    svc._justice_gateway.get_active_suspects.return_value = fake_suspects  # type: ignore[attr-defined]

    # 模擬 conn.fetchrow
    async def _fetchrow(_: str, __: int, ___: list[str]) -> dict[str, int]:
        return {"total": 42}

    # 注入 acquire()/__aenter__/fetchrow 行為
    class _Conn:
        async def fetchrow(self, sql: str, guild_id: int, statuses: list[str]) -> dict[str, int]:
            return await _fetchrow(sql, guild_id, statuses)

    class _Acq:
        async def __aenter__(self) -> _Conn:
            return _Conn()

        async def __aexit__(self, *args: object) -> None:
            return None

    class _Pool:
        def acquire(self) -> _Acq:
            return _Acq()

    import src.bot.services.state_council_service as sc

    sc.get_pool = lambda: _Pool()  # type: ignore[assignment]

    res = await svc.get_active_suspects(guild_id=1, page=2, page_size=5)
    assert isinstance(res, Ok)
    suspects, total = res.value
    assert suspects == fake_suspects
    assert total == 42


@pytest.mark.asyncio
async def test_is_member_charged_true_when_status_charged() -> None:
    svc = StateCouncilService()
    suspect = SimpleNamespace(status="charged")
    svc.get_suspect_by_member = AsyncMock(return_value=Ok(suspect))  # type: ignore[assignment]

    result = await svc.is_member_charged(guild_id=1, member_id=2)

    svc.get_suspect_by_member.assert_awaited_once_with(guild_id=1, member_id=2)
    assert isinstance(result, Ok)
    assert result.value is True


@pytest.mark.asyncio
async def test_is_member_charged_false_for_non_charged_or_missing() -> None:
    svc = StateCouncilService()
    svc.get_suspect_by_member = AsyncMock(return_value=Ok(None))  # type: ignore[assignment]

    result_none = await svc.is_member_charged(guild_id=1, member_id=2)

    svc.get_suspect_by_member.assert_awaited_with(guild_id=1, member_id=2)
    assert isinstance(result_none, Ok)
    assert result_none.value is False

    # 非 charged 狀態也應回傳 False
    svc.get_suspect_by_member.reset_mock()
    svc.get_suspect_by_member.return_value = Ok(SimpleNamespace(status="detained"))  # type: ignore[assignment]

    result_detained = await svc.is_member_charged(guild_id=3, member_id=4)

    svc.get_suspect_by_member.assert_awaited_once_with(guild_id=3, member_id=4)
    assert isinstance(result_detained, Ok)
    assert result_detained.value is False
