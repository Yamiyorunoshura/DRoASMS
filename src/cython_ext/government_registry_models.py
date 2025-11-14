from __future__ import annotations

from dataclasses import dataclass

__all__ = ["GovernmentDepartment", "DepartmentEdge"]


@dataclass(slots=True, frozen=True)
class GovernmentDepartment:
    department_id: str
    display_name: str
    level: int
    parent_id: str | None
    is_council: bool = False
    subordinates: tuple[str, ...] | None = None


@dataclass(slots=True, frozen=True)
class DepartmentEdge:
    parent_id: str
    child_id: str
    weight: int = 1
