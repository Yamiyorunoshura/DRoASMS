from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.bot.services.state_council_service import (
    PermissionDeniedError,
    StateCouncilService,
)
from src.db.gateway.state_council_governance import IdentityRecord


class _DummyAcquire:
    async def __aenter__(self) -> object:  # pragma: no cover - trivial
        return object()

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - trivial
        return None


@pytest.fixture(autouse=True)
def patch_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_pool_cm(_pool: object) -> _DummyAcquire:
        return _DummyAcquire()

    monkeypatch.setattr(
        StateCouncilService,
        "_pool_acquire_cm",
        staticmethod(_fake_pool_cm),
    )
    monkeypatch.setattr(
        "src.bot.services.state_council_service.get_pool",
        lambda: object(),
    )


@pytest.mark.asyncio
async def test_list_suspects_includes_identity_and_schedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = StateCouncilService(transfer_service=MagicMock(), adjustment_service=MagicMock())
    service._gateway = MagicMock()
    sample_record = IdentityRecord(
        record_id=UUID(int=1),
        guild_id=123,
        target_id=111,
        action="標記疑犯",
        reason="測試逮捕",
        performed_by=456,
        performed_at=datetime(2025, 11, 10, tzinfo=timezone.utc),
    )
    service._gateway.fetch_identity_records = AsyncMock(return_value=[sample_record])
    cfg = SimpleNamespace(suspect_role_id=1, citizen_role_id=2)
    service.get_config = AsyncMock(return_value=cfg)
    monkeypatch.setattr(
        service,
        "_get_auto_release_jobs",
        lambda guild_id: {
            111: SimpleNamespace(release_at=datetime(2025, 11, 12, tzinfo=timezone.utc), hours=48)
        },
    )

    suspect_role = SimpleNamespace(
        members=[
            SimpleNamespace(
                id=111,
                display_name="嫌疑人A",
                joined_at=datetime(2025, 11, 1, tzinfo=timezone.utc),
                roles=[],
            ),
            SimpleNamespace(
                id=222,
                display_name="嫌疑人B",
                joined_at=datetime(2025, 11, 2, tzinfo=timezone.utc),
                roles=[],
            ),
        ]
    )
    guild = MagicMock()
    guild.get_role.side_effect = lambda role_id: suspect_role if role_id == 1 else None

    profiles = await service.list_suspects(guild=guild, guild_id=123)

    assert len(profiles) == 2
    enriched = next(profile for profile in profiles if profile.member_id == 111)
    assert enriched.arrest_reason == "測試逮捕"
    assert enriched.auto_release_hours == 48
    assert enriched.auto_release_at is not None


@pytest.mark.asyncio
async def test_release_suspects_updates_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    service = StateCouncilService(transfer_service=MagicMock(), adjustment_service=MagicMock())
    cfg = SimpleNamespace(suspect_role_id=11, citizen_role_id=22)
    service.get_config = AsyncMock(return_value=cfg)
    service.record_identity_action = AsyncMock()
    monkeypatch.setattr(service, "_cancel_auto_release_job", MagicMock())
    service.check_department_permission = AsyncMock(return_value=True)

    suspect_role = MagicMock()
    suspect_role.id = 11
    citizen_role = MagicMock()
    citizen_role.id = 22

    member = MagicMock()
    member.id = 555
    member.display_name = "測試嫌疑人"
    member.roles = [suspect_role]
    member.remove_roles = AsyncMock()
    member.add_roles = AsyncMock()

    guild = MagicMock()
    guild.get_role.side_effect = lambda rid: suspect_role if rid == 11 else citizen_role
    guild.get_member.return_value = member

    # JusticeService 替身：視所有嫌疑人為未起訴，並避免觸發真實資料庫
    class _FakeJusticeService:
        async def is_member_charged(self, *, guild_id: int, member_id: int) -> bool:  # noqa: D401
            return False

        async def mark_member_released_from_security(
            self, *, guild_id: int, member_id: int
        ) -> None:
            return None

    monkeypatch.setattr(
        "src.bot.services.state_council_service.JusticeService",
        _FakeJusticeService,
    )

    results = await service.release_suspects(
        guild=guild,
        guild_id=999,
        department="國土安全部",
        user_id=777,
        user_roles=[1, 2],
        suspect_ids=[555],
        reason="面板釋放",
    )

    assert results[0].released is True
    member.remove_roles.assert_awaited()
    member.add_roles.assert_awaited()
    service.record_identity_action.assert_awaited()
    service._cancel_auto_release_job.assert_called_with(999, 555)


@pytest.mark.asyncio
async def test_schedule_auto_release_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    service = StateCouncilService(transfer_service=MagicMock(), adjustment_service=MagicMock())
    service.check_department_permission = AsyncMock(return_value=True)
    cfg = SimpleNamespace(suspect_role_id=33)
    service.get_config = AsyncMock(return_value=cfg)
    member = SimpleNamespace(id=1, roles=[SimpleNamespace(id=33)])
    suspect_role = SimpleNamespace(members=[member])
    guild = MagicMock()
    guild.get_role.return_value = suspect_role
    guild.get_member.return_value = member
    monkeypatch.setattr(
        service,
        "_schedule_auto_release_job",
        MagicMock(return_value=SimpleNamespace(release_at=datetime.now(timezone.utc))),
    )

    scheduled = await service.schedule_auto_release(
        guild=guild,
        guild_id=1,
        department="國土安全部",
        user_id=10,
        user_roles=[],
        suspect_ids=[1],
        hours=24,
    )

    assert 1 in scheduled

    with pytest.raises(ValueError):
        await service.schedule_auto_release(
            guild=guild,
            guild_id=1,
            department="國土安全部",
            user_id=10,
            user_roles=[],
            suspect_ids=[1],
            hours=0,
        )


@pytest.mark.asyncio
async def test_schedule_auto_release_requires_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    service = StateCouncilService(transfer_service=MagicMock(), adjustment_service=MagicMock())
    service.check_department_permission = AsyncMock(return_value=False)
    cfg = SimpleNamespace(suspect_role_id=44)
    service.get_config = AsyncMock(return_value=cfg)
    guild = MagicMock()
    guild.get_role.return_value = SimpleNamespace(members=[])

    with pytest.raises(PermissionDeniedError):
        await service.schedule_auto_release(
            guild=guild,
            guild_id=1,
            department="國土安全部",
            user_id=77,
            user_roles=[],
            suspect_ids=[99],
            hours=24,
        )


@pytest.mark.asyncio
async def test_release_suspects_blocks_charged_suspects(monkeypatch: pytest.MonkeyPatch) -> None:
    service = StateCouncilService(transfer_service=MagicMock(), adjustment_service=MagicMock())
    cfg = SimpleNamespace(suspect_role_id=11, citizen_role_id=22)
    service.get_config = AsyncMock(return_value=cfg)
    service.record_identity_action = AsyncMock()
    monkeypatch.setattr(service, "_cancel_auto_release_job", MagicMock())
    service.check_department_permission = AsyncMock(return_value=True)

    # JusticeService 檢查時一律視為已起訴
    class _FakeJusticeService:
        async def is_member_charged(self, *, guild_id: int, member_id: int) -> bool:  # noqa: D401
            assert guild_id == 999
            return True

        async def mark_member_released_from_security(
            self, *, guild_id: int, member_id: int
        ) -> None:
            return None

    monkeypatch.setattr(
        "src.bot.services.state_council_service.JusticeService",
        _FakeJusticeService,
    )

    suspect_role = MagicMock()
    suspect_role.id = 11
    citizen_role = MagicMock()
    citizen_role.id = 22

    member = MagicMock()
    member.id = 555
    member.display_name = "測試嫌疑人"
    member.roles = [suspect_role]
    member.remove_roles = AsyncMock()
    member.add_roles = AsyncMock()

    guild = MagicMock()
    guild.get_role.side_effect = lambda rid: suspect_role if rid == 11 else citizen_role
    guild.get_member.return_value = member

    results = await service.release_suspects(
        guild=guild,
        guild_id=999,
        department="國土安全部",
        user_id=777,
        user_roles=[1, 2],
        suspect_ids=[555],
        reason="面板釋放",
    )

    assert len(results) == 1
    assert results[0].released is False
    assert "該嫌犯已被起訴，無法釋放" in (results[0].error or "")
    member.remove_roles.assert_not_awaited()
