"""Tests for council multiple role permissions functionality."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

import pytest

from src.bot.services.council_service import CouncilService
from src.db.gateway.council_governance import (
    CouncilConfig,
    CouncilGovernanceGateway,
    CouncilRoleConfig,
)

# ---- Fakes for multiple role testing ----


class _FakeTxn:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class _FakeConnection:
    def __init__(self, gw: _FakeGateway) -> None:
        self._gw = gw

    def transaction(self) -> _FakeTxn:
        return _FakeTxn()

    async def fetchval(self, sql: str, *args: Any) -> Any:
        # Mock SQL responses based on function calls
        if "fn_get_council_role_ids" in sql:
            guild_id = args[0]
            return self._gw.council_role_ids.get(guild_id, [])
        return None

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        # Mock SQL responses for role config queries
        if (
            "SELECT guild_id, role_id, created_at, updated_at FROM governance.council_role_ids"
            in sql
        ):
            guild_id = args[0]
            configs: list[dict[str, Any]] = []
            for role_id in self._gw.council_role_ids.get(guild_id, []):
                configs.append(
                    {
                        "guild_id": guild_id,
                        "role_id": role_id,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
            return configs
        return []


class _FakeAcquire:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConnection:
        return self._conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self._conn)


class _FakeGateway(CouncilGovernanceGateway):
    def __init__(self, *, schema: str = "governance") -> None:
        # Don't call super().__init__() to avoid inheritance issues
        self._schema = schema
        self._cfg: dict[int, CouncilConfig] = {}
        self._council_role_ids: dict[int, list[int]] = {}

    @property
    def council_role_ids(self) -> dict[int, list[int]]:
        """Public property for test access."""
        return self._council_role_ids

    # config
    async def upsert_config(
        self,
        connection: Any,
        *,
        guild_id: int,
        council_role_id: int,
        council_account_member_id: int,
    ) -> CouncilConfig:
        cfg = CouncilConfig(
            guild_id=guild_id,
            council_role_id=council_role_id,
            council_account_member_id=council_account_member_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._cfg[guild_id] = cfg
        return cfg

    async def fetch_config(self, connection: Any, *, guild_id: int) -> CouncilConfig | None:
        return self._cfg.get(guild_id)

    # council role management
    async def get_council_role_ids(self, connection: Any, *, guild_id: int) -> Sequence[int]:
        return self._council_role_ids.get(guild_id, [])

    async def add_council_role(self, connection: Any, *, guild_id: int, role_id: int) -> bool:
        existing_roles: list[int] = list(self._council_role_ids.get(guild_id, []))
        if role_id in existing_roles:
            return False
        existing_roles.append(role_id)
        self._council_role_ids[guild_id] = existing_roles
        return True

    async def remove_council_role(self, connection: Any, *, guild_id: int, role_id: int) -> bool:
        existing_roles: list[int] = list(self._council_role_ids.get(guild_id, []))
        if role_id not in existing_roles:
            return False
        existing_roles.remove(role_id)
        self._council_role_ids[guild_id] = existing_roles
        return True

    async def list_council_role_configs(
        self, connection: Any, *, guild_id: int
    ) -> list[CouncilRoleConfig]:
        configs: list[CouncilRoleConfig] = []
        for role_id in self._council_role_ids.get(guild_id, []):
            configs.append(
                CouncilRoleConfig(
                    guild_id=guild_id,
                    role_id=role_id,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
        return configs

    # other methods...
    async def create_proposal(self, *args: Any, **kwargs: Any) -> Any:
        pass

    async def fetch_proposal(self, *args: Any, **kwargs: Any) -> Any:
        pass

    async def fetch_snapshot(self, *args: Any, **kwargs: Any) -> list[int]:
        return []

    async def cancel_proposal(self, *args: Any, **kwargs: Any) -> bool:
        return False

    async def upsert_vote(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def fetch_tally(self, *args: Any, **kwargs: Any) -> Any:
        pass

    async def mark_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def fetch_votes_detail(self, *args: Any, **kwargs: Any) -> list[tuple[int, str]]:
        return []

    async def list_due_proposals(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    async def mark_reminded(self, *args: Any, **kwargs: Any) -> None:
        pass


# ---- Tests ----


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_council_permission_single_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test council permission checking with traditional single role (backward compatibility)."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service_result.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)

    # Setup config with single role
    await svc.set_config(guild_id=100, council_role_id=200)

    # Test permission with matching role
    assert await svc.check_council_permission(guild_id=100, user_roles=[200]) is True

    # Test permission without matching role
    assert await svc.check_council_permission(guild_id=100, user_roles=[300]) is False

    # Test permission with multiple roles including correct one
    assert await svc.check_council_permission(guild_id=100, user_roles=[300, 200, 400]) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_council_permission_multiple_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test council permission checking with multiple role configuration."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service_result.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)

    # Setup config and add multiple roles
    await svc.set_config(guild_id=100, council_role_id=200)
    await svc.add_council_role(guild_id=100, role_id=300)
    await svc.add_council_role(guild_id=100, role_id=400)

    # Test permission with any of the council roles
    assert await svc.check_council_permission(guild_id=100, user_roles=[300]) is True
    assert await svc.check_council_permission(guild_id=100, user_roles=[400]) is True
    assert await svc.check_council_permission(guild_id=100, user_roles=[200]) is True

    # Test permission with multiple roles including council role
    assert await svc.check_council_permission(guild_id=100, user_roles=[500, 300, 600]) is True

    # Test permission without any council role
    assert await svc.check_council_permission(guild_id=100, user_roles=[500, 600]) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_council_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test adding council roles."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service_result.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    # Add new role
    result = await svc.add_council_role(guild_id=100, role_id=300)
    assert result is True

    # Verify role was added
    role_ids = await svc.get_council_role_ids(guild_id=100)
    assert 300 in role_ids

    # Try to add same role again
    result = await svc.add_council_role(guild_id=100, role_id=300)
    assert result is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remove_council_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test removing council roles."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service_result.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    # Add and then remove role
    await svc.add_council_role(guild_id=100, role_id=300)
    result = await svc.remove_council_role(guild_id=100, role_id=300)
    assert result is True

    # Verify role was removed
    role_ids = await svc.get_council_role_ids(guild_id=100)
    assert 300 not in role_ids

    # Try to remove non-existent role
    result = await svc.remove_council_role(guild_id=100, role_id=400)
    assert result is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_council_role_ids_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test getting council role IDs when none are configured."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service_result.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)

    # Test with no roles configured
    role_ids = await svc.get_council_role_ids(guild_id=100)
    assert role_ids == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_council_role_configs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test listing council role configurations."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service_result.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)
    await svc.set_config(guild_id=100, council_role_id=200)

    # Add multiple roles
    await svc.add_council_role(guild_id=100, role_id=300)
    await svc.add_council_role(guild_id=100, role_id=400)

    # List configurations
    configs = await svc.list_council_role_configs(guild_id=100)
    role_ids = [config.role_id for config in configs]

    assert 300 in role_ids
    assert 400 in role_ids
    assert len(configs) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backward_compatibility_with_existing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that existing single role configurations continue to work."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.council_service_result.get_pool", lambda: pool)

    svc = CouncilService(gateway=gw)

    # Setup only traditional single role config
    await svc.set_config(guild_id=100, council_role_id=200)

    # Should work with traditional role
    assert await svc.check_council_permission(guild_id=100, user_roles=[200]) is True

    # Should return empty list for new multiple role API (since none configured)
    role_ids = await svc.get_council_role_ids(guild_id=100)
    assert role_ids == []

    # But permission should still work through backward compatibility
    assert await svc.check_council_permission(guild_id=100, user_roles=[200]) is True
