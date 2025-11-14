"""Gateway for accessing normalized government department hierarchy data."""

from __future__ import annotations

from typing import Iterable, Sequence

from src.bot.services.department_registry import Department, DepartmentRegistry
from src.cython_ext.government_registry_models import DepartmentEdge, GovernmentDepartment


class GovernmentRegistryGateway:
    """Read-only gateway that bridges DepartmentRegistry to Cython models."""

    def __init__(self, *, registry: DepartmentRegistry | None = None) -> None:
        self._registry = registry or DepartmentRegistry()

    def list_departments(
        self,
        *,
        level: str | None = None,
        include_subordinates: bool = True,
    ) -> list[GovernmentDepartment]:
        """Return all departments, optionally filtered by level."""
        if level is None:
            departments = self._registry.get_hierarchy().values()
            flat: list[GovernmentDepartment] = []
            for bucket in departments:
                flat.extend(self._convert_many(bucket, include_subordinates))
            return flat

        return self._convert_many(self._registry.get_by_level(level), include_subordinates)

    def get_department(self, department_id: str) -> GovernmentDepartment | None:
        dept = self._registry.get_by_id(department_id)
        if dept is None:
            return None
        return self._to_model(dept, include_subordinates=True)

    def list_edges(self) -> list[DepartmentEdge]:
        """Return parent/child edges for the entire hierarchy."""
        edges: list[DepartmentEdge] = []
        for dept in self._registry.get_hierarchy().values():
            for item in dept:
                if item.parent:
                    edges.append(DepartmentEdge(parent_id=item.parent, child_id=item.id))
                if item.subordinates:
                    for child_id in item.subordinates:
                        edges.append(DepartmentEdge(parent_id=item.id, child_id=child_id))
        return edges

    def _convert_many(
        self, departments: Iterable[Department], include_subordinates: bool
    ) -> list[GovernmentDepartment]:
        return [
            self._to_model(dept, include_subordinates=include_subordinates) for dept in departments
        ]

    def _to_model(
        self,
        dept: Department,
        *,
        include_subordinates: bool,
    ) -> GovernmentDepartment:
        subordinates: Sequence[str] | None = dept.subordinates if include_subordinates else None
        subordinate_tuple = tuple(subordinates) if subordinates else None
        return GovernmentDepartment(
            department_id=dept.id,
            display_name=dept.name,
            level=self._coerce_level(dept.level),
            parent_id=dept.parent,
            is_council=dept.id == "permanent_council",
            subordinates=subordinate_tuple,
        )

    @staticmethod
    def _coerce_level(level: str | None) -> int:
        mapping = {"executive": 0, "governance": 1, "department": 2}
        return mapping.get(level or "department", 2)


__all__ = ["GovernmentRegistryGateway", "GovernmentDepartment", "DepartmentEdge"]
