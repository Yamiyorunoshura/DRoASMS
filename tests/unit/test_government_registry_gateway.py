from __future__ import annotations

import pathlib

import pytest

from src.bot.services.department_registry import DepartmentRegistry
from src.db.gateway.government_registry import GovernmentRegistryGateway


@pytest.fixture()
def registry(tmp_path: pathlib.Path) -> DepartmentRegistry:
    # Force fallback to default departments by pointing to non-existent file
    return DepartmentRegistry(config_path=tmp_path / "missing.json")


def test_list_departments_returns_cython_models(registry: DepartmentRegistry) -> None:
    gateway = GovernmentRegistryGateway(registry=registry)
    departments = gateway.list_departments()

    assert departments, "expected default departments"
    assert any(dept.is_council for dept in departments)
    assert all(hasattr(dept, "department_id") for dept in departments)


def test_list_edges_contains_parent_relations(registry: DepartmentRegistry) -> None:
    gateway = GovernmentRegistryGateway(registry=registry)
    edges = gateway.list_edges()

    assert edges, "edges should not be empty"
    # Ensure at least one edge references state_council as parent
    assert any(edge.parent_id == "state_council" for edge in edges)
