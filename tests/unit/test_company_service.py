from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.bot.services.company_service import CompanyService
from src.cython_ext.state_council_models import Company
from src.infra.result import Ok


class _DummyAcquire:
    def __init__(self, connection: object) -> None:
        self._connection = connection

    async def __aenter__(self) -> object:  # pragma: no cover - trivial
        return self._connection

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # pragma: no cover - trivial
        _ = exc_type, exc, tb
        return False


class _DummyPool:
    def __init__(self, connection: object) -> None:
        self._connection = connection

    def acquire(self) -> _DummyAcquire:  # pragma: no cover - trivial
        return _DummyAcquire(self._connection)


class _DummyConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, sql: str, *args: object) -> None:
        self.executed.append((sql, args))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_company_does_not_rewind_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_company 不應重置序列為未呼叫狀態，避免產生重複 ID。"""

    connection = _DummyConnection()
    pool = _DummyPool(connection)

    company = Company(
        id=42,
        guild_id=1,
        owner_id=2,
        license_id=uuid4(),
        name="Test Corp",
        account_id=999,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )

    gateway = SimpleNamespace(
        next_company_id=AsyncMock(return_value=Ok(company.id)),
        create_company=AsyncMock(return_value=Ok(company)),
        reset_company_sequence=AsyncMock(return_value=Ok(True)),
    )

    service = CompanyService(pool, gateway=gateway)

    result = await service.create_company(
        guild_id=company.guild_id,
        owner_id=company.owner_id,
        license_id=company.license_id,
        name=company.name,
    )

    assert isinstance(result, Ok)
    assert result.value == company

    # 不應呼叫 reset_company_sequence，避免下一個 nextval 重複上一個 ID。
    gateway.reset_company_sequence.assert_not_awaited()
