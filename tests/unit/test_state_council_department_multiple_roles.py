"""Test State Council Department Multiple Roles functionality"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

import pytest

from src.bot.services.state_council_service import StateCouncilService
from src.db.gateway.state_council_governance import (
    DepartmentConfig,
    DepartmentRoleConfig,
    StateCouncilConfig,
    StateCouncilGovernanceGateway,
)


class _FakeConnection:
    """Fake connection for testing."""

    def __init__(self, gateway: StateCouncilGovernanceGateway) -> None:
        self._gateway = gateway
        self._data = {
            "department_role_ids": {},
            "department_configs": {},
            "state_council_configs": {},
            "department_role_configs": [],
        }

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        # Simulate get_department_role_ids function
        if "get_state_council_department_role_ids" in query:
            guild_id, department = args
            role_ids = self._data["department_role_ids"].get((guild_id, department), [])
            return {"get_state_council_department_role_ids": role_ids}

        # Simulate add/remove department role functions
        if "add_state_council_department_role" in query:
            guild_id, department, role_id = args
            key = (guild_id, department)
            if key not in self._data["department_role_ids"]:
                self._data["department_role_ids"][key] = []

            if role_id in self._data["department_role_ids"][key]:
                return {"add_state_council_department_role": False}

            self._data["department_role_ids"][key].append(role_id)
            return {"add_state_council_department_role": True}

        if "remove_state_council_department_role" in query:
            guild_id, department, role_id = args
            key = (guild_id, department)
            if key not in self._data["department_role_ids"]:
                return {"remove_state_council_department_role": False}

            if role_id not in self._data["department_role_ids"][key]:
                return {"remove_state_council_department_role": False}

            self._data["department_role_ids"][key].remove(role_id)
            return {"remove_state_council_department_role": True}

        return None

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        # Simulate list_department_role_configs function
        if "list_state_council_department_role_configs" in query:
            guild_id = args[0]
            configs = []
            for (g, d), role_ids in self._data["department_role_ids"].items():
                if g == guild_id:
                    for role_id in role_ids:
                        configs.append(
                            {
                                "id": len(configs) + 1,
                                "guild_id": g,
                                "department": d,
                                "role_id": role_id,
                                "created_at": datetime.now(timezone.utc),
                                "updated_at": datetime.now(timezone.utc),
                            }
                        )
            return configs

        return []

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction(self)


class _FakeTransaction:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> _FakeConnection:
        return self._connection

    async def __aexit__(self, *args: Any) -> None:
        pass


class _FakePool:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    async def acquire(self) -> _FakeConnection:
        return self._connection


class _FakeGateway(StateCouncilGovernanceGateway):
    """Fake gateway for testing."""

    def __init__(self) -> None:
        # Skip parent class initialization to avoid schema parameter issues
        self._schema = "governance"
        self._data = {
            "department_configs": {},
            "state_council_configs": {},
            "department_role_ids": {},
        }

    async def fetch_config(self, connection: Any, *, guild_id: int) -> StateCouncilConfig | None:
        return self._data["state_council_configs"].get(guild_id)

    async def fetch_state_council_config(
        self, connection: Any, *, guild_id: int
    ) -> StateCouncilConfig | None:
        return self._data["state_council_configs"].get(guild_id)

    async def fetch_department_config(
        self, connection: Any, *, guild_id: int, department: str
    ) -> DepartmentConfig | None:
        return self._data["department_configs"].get((guild_id, department))

    async def get_department_role_ids(
        self, connection: Any, *, guild_id: int, department: str
    ) -> Sequence[int]:
        return self._data.get("department_role_ids", {}).get((guild_id, department), [])

    async def add_department_role(
        self, connection: Any, *, guild_id: int, department: str, role_id: int
    ) -> bool:
        key = (guild_id, department)
        if "department_role_ids" not in self._data:
            self._data["department_role_ids"] = {}
        if key not in self._data["department_role_ids"]:
            self._data["department_role_ids"][key] = []

        if role_id in self._data["department_role_ids"][key]:
            return False

        self._data["department_role_ids"][key].append(role_id)
        return True

    async def remove_department_role(
        self, connection: Any, *, guild_id: int, department: str, role_id: int
    ) -> bool:
        key = (guild_id, department)
        if "department_role_ids" not in self._data:
            return False
        if key not in self._data["department_role_ids"]:
            return False

        if role_id not in self._data["department_role_ids"][key]:
            return False

        self._data["department_role_ids"][key].remove(role_id)
        return True

    async def list_department_role_configs(
        self, connection: Any, *, guild_id: int
    ) -> Sequence[DepartmentRoleConfig]:
        configs = []
        for (g, d), role_ids in self._data.get("department_role_ids", {}).items():
            if g == guild_id:
                for role_id in role_ids:
                    configs.append(
                        DepartmentRoleConfig(
                            id=len(configs) + 1,
                            guild_id=g,
                            department=d,
                            role_id=role_id,
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
        return configs

    def set_department_config(
        self, guild_id: int, department: str, config: DepartmentConfig
    ) -> None:
        self._data["department_configs"][(guild_id, department)] = config


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_department_permission_multiple_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test department permission checking with multiple role configuration."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)

    # Setup department config and add multiple roles
    dept_config = DepartmentConfig(
        id=1,
        guild_id=100,
        department="內政部",
        role_id=200,  # Traditional single role
        welfare_amount=1000,
        welfare_interval_hours=24,
        tax_rate_basis=10000,
        tax_rate_percent=5,
        max_issuance_per_month=5000,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    gw.set_department_config(100, "內政部", dept_config)

    # Mock get_config to return a basic state council config
    state_council_config = StateCouncilConfig(
        guild_id=100,
        leader_id=1,
        leader_role_id=50,
        internal_affairs_account_id=1001,
        finance_account_id=1002,
        security_account_id=1003,
        central_bank_account_id=1004,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    gw._data["state_council_configs"][100] = state_council_config

    # Add multiple roles to the department
    await svc.add_department_role(guild_id=100, department="內政部", role_id=300)
    await svc.add_department_role(guild_id=100, department="內政部", role_id=400)

    # Test permission with any of the department roles (multiple roles)
    assert (
        await svc.check_department_permission(
            guild_id=100, user_id=1, department="內政部", user_roles=[300]
        )
        is True
    )
    assert (
        await svc.check_department_permission(
            guild_id=100, user_id=1, department="內政部", user_roles=[400]
        )
        is True
    )

    # Test permission with traditional single role (backward compatibility)
    assert (
        await svc.check_department_permission(
            guild_id=100, user_id=1, department="內政部", user_roles=[200]
        )
        is True
    )

    # Test permission with leader role (should have access to all departments)
    assert (
        await svc.check_department_permission(
            guild_id=100, user_id=1, department="內政部", user_roles=[50]
        )
        is True
    )

    # Test no permission
    assert (
        await svc.check_department_permission(
            guild_id=100, user_id=2, department="內政部", user_roles=[999]
        )
        is False
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_department_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test adding a role to a department."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)

    # Add a role to department
    result = await svc.add_department_role(guild_id=100, department="財政部", role_id=300)
    assert result is True

    # Adding the same role again should return False
    result = await svc.add_department_role(guild_id=100, department="財政部", role_id=300)
    assert result is False

    # Verify the role was added
    role_ids = await svc.get_department_role_ids(guild_id=100, department="財政部")
    assert role_ids == [300]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remove_department_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test removing a role from a department."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)

    # Add a role first
    await svc.add_department_role(guild_id=100, department="國土安全部", role_id=300)

    # Remove the role
    result = await svc.remove_department_role(guild_id=100, department="國土安全部", role_id=300)
    assert result is True

    # Removing the same role again should return False
    result = await svc.remove_department_role(guild_id=100, department="國土安全部", role_id=300)
    assert result is False

    # Verify the role was removed
    role_ids = await svc.get_department_role_ids(guild_id=100, department="國土安全部")
    assert role_ids == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_department_role_ids_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test getting role IDs for a department with no roles."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)

    # Get role IDs for department with no roles
    role_ids = await svc.get_department_role_ids(guild_id=100, department="中央銀行")
    assert role_ids == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_department_role_configs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test listing all department role configurations."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)

    # Add multiple roles to different departments
    await svc.add_department_role(guild_id=100, department="內政部", role_id=300)
    await svc.add_department_role(guild_id=100, department="內政部", role_id=301)
    await svc.add_department_role(guild_id=100, department="財政部", role_id=400)

    # List configurations
    configs = await svc.list_department_role_configs(guild_id=100)
    assert len(configs) == 3

    # Verify configurations
    departments = {config.department for config in configs}
    role_ids = {config.role_id for config in configs}

    assert departments == {"內政部", "財政部"}
    assert role_ids == {300, 301, 400}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backward_compatibility_with_existing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that existing single role configurations still work."""
    gw = _FakeGateway()
    conn = _FakeConnection(gw)
    pool = _FakePool(conn)
    monkeypatch.setattr("src.bot.services.state_council_service.get_pool", lambda: pool)

    svc = StateCouncilService(gateway=gw)

    # Setup traditional department config without multiple roles
    dept_config = DepartmentConfig(
        id=1,
        guild_id=100,
        department="內政部",
        role_id=200,
        welfare_amount=1000,
        welfare_interval_hours=24,
        tax_rate_basis=10000,
        tax_rate_percent=5,
        max_issuance_per_month=5000,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    gw.set_department_config(100, "內政部", dept_config)

    # Mock get_config to return a basic state council config
    state_council_config = StateCouncilConfig(
        guild_id=100,
        leader_id=1,
        leader_role_id=50,
        internal_affairs_account_id=1001,
        finance_account_id=1002,
        security_account_id=1003,
        central_bank_account_id=1004,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    gw._data["state_council_configs"][100] = state_council_config

    # Test permission with traditional role (should still work)
    assert (
        await svc.check_department_permission(
            guild_id=100, user_id=1, department="內政部", user_roles=[200]
        )
        is True
    )

    # Test permission with leader role (should still work)
    assert (
        await svc.check_department_permission(
            guild_id=100, user_id=1, department="內政部", user_roles=[50]
        )
        is True
    )

    # Test no permission (should still be denied)
    assert (
        await svc.check_department_permission(
            guild_id=100, user_id=2, department="內政部", user_roles=[999]
        )
        is False
    )

    # Verify no multiple roles are configured
    role_ids = await svc.get_department_role_ids(guild_id=100, department="內政部")
    assert role_ids == []
