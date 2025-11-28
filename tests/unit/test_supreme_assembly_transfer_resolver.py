from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.bot.commands.supreme_assembly import _resolve_department_account_id_for_supreme


class _DummyAcquire:
    async def __aenter__(self):  # pragma: no cover - trivial context manager
        return object()

    async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - trivial
        return None


class _DummyPool:
    def acquire(self):  # pragma: no cover - simple passthrough
        return _DummyAcquire()


@pytest.mark.asyncio
async def test_resolve_department_prefers_config(monkeypatch: pytest.MonkeyPatch) -> None:
    guild_id = 123
    cfg = SimpleNamespace(
        internal_affairs_account_id=11,
        finance_account_id=22,
        security_account_id=33,
        central_bank_account_id=44,
        welfare_account_id=999,  # 用於法務部回退欄位
    )

    class StubGateway:
        async def fetch_state_council_config(self, conn, guild_id: int):
            assert guild_id == 123
            return cfg

    class FailService:
        async def get_department_account_id(self, **kwargs):  # pragma: no cover - 不應被呼叫
            raise AssertionError("service fallback should not be used when config exists")

    monkeypatch.setattr("src.bot.commands.supreme_assembly.get_pool", lambda: _DummyPool())

    account_id = await _resolve_department_account_id_for_supreme(
        guild_id=guild_id,
        department_name="法務部",
        sc_gateway=StubGateway(),
        state_council_service=FailService(),
    )

    assert account_id == 999


@pytest.mark.asyncio
async def test_resolve_department_falls_back_to_service(monkeypatch: pytest.MonkeyPatch) -> None:
    guild_id = 456

    class StubGateway:
        async def fetch_state_council_config(self, conn, guild_id: int):
            return None

    class StubService:
        async def get_department_account_id(self, *, guild_id: int, department: str) -> int:
            assert guild_id == 456
            assert department == "財政部"
            return 4242

    monkeypatch.setattr("src.bot.commands.supreme_assembly.get_pool", lambda: _DummyPool())

    account_id = await _resolve_department_account_id_for_supreme(
        guild_id=guild_id,
        department_name="財政部",
        sc_gateway=StubGateway(),
        state_council_service=StubService(),
    )

    assert account_id == 4242
