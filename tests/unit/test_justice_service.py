from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot.services.justice_service import JusticeService


@pytest.mark.asyncio
async def test_get_suspects_alias_calls_active() -> None:
    service = JusticeService(gateway=None, state_council_gateway=None)
    service.get_active_suspects = AsyncMock(return_value=(["dummy"], 42))  # type: ignore[assignment]

    suspects, total = await service.get_suspects(guild_id=123, page=2, page_size=5)

    service.get_active_suspects.assert_awaited_once_with(guild_id=123, page=2, page_size=5)
    assert suspects == ["dummy"]
    assert total == 42


@pytest.mark.asyncio
async def test_is_member_charged_true_when_status_charged() -> None:
    service = JusticeService(gateway=None, state_council_gateway=None)
    suspect = SimpleNamespace(status="charged")
    service.get_suspect_by_member = AsyncMock(return_value=suspect)  # type: ignore[assignment]

    result = await service.is_member_charged(guild_id=1, member_id=2)

    service.get_suspect_by_member.assert_awaited_once_with(guild_id=1, member_id=2)
    assert result is True


@pytest.mark.asyncio
async def test_is_member_charged_false_for_non_charged_or_missing() -> None:
    service = JusticeService(gateway=None, state_council_gateway=None)
    service.get_suspect_by_member = AsyncMock(return_value=None)  # type: ignore[assignment]

    result_none = await service.is_member_charged(guild_id=1, member_id=2)

    service.get_suspect_by_member.assert_awaited_with(guild_id=1, member_id=2)
    assert result_none is False

    # 非 charged 狀態也應回傳 False
    service.get_suspect_by_member.reset_mock()
    service.get_suspect_by_member.return_value = SimpleNamespace(status="detained")  # type: ignore[assignment]

    result_detained = await service.is_member_charged(guild_id=3, member_id=4)

    service.get_suspect_by_member.assert_awaited_once_with(guild_id=3, member_id=4)
    assert result_detained is False
