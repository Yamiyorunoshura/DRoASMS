"""Department registry for unified department identification."""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any, Sequence, cast

import structlog

LOGGER = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Department:
    """Department metadata."""

    id: str
    name: str
    code: int
    emoji: str | None = None
    level: str = "department"  # executive, governance, department
    description: str | None = None
    parent: str | None = None  # Parent department ID
    subordinates: list[str] | None = None  # List of subordinate department IDs


class DepartmentRegistry:
    """Central registry for government departments.

    Loads department definitions from JSON and provides lookup methods.
    Supports both ID-based and name-based lookups for backward compatibility.
    """

    def __init__(self, config_path: str | pathlib.Path | None = None) -> None:
        """Initialize registry with optional config path.

        Args:
            config_path: Path to departments.json. If None, uses default location.
        """
        if config_path is None:
            # Default to src/config/departments.json relative to this file
            base = pathlib.Path(__file__).parent.parent.parent
            config_path = base / "config" / "departments.json"
        self._config_path = pathlib.Path(config_path)
        self._departments: dict[str, Department] = {}
        self._name_to_id: dict[str, str] = {}
        self._loaded = False
        self._load_departments()

    def _load_departments(self) -> None:
        """Load departments from JSON file."""
        if self._loaded:
            return

        try:
            if not self._config_path.exists():
                LOGGER.warning(
                    "department_registry.file_not_found",
                    path=str(self._config_path),
                )
                # Use default departments as fallback
                self._departments = self._get_default_departments()
                self._build_name_mapping()
                self._loaded = True
                return

            with self._config_path.open(encoding="utf-8") as f:
                raw_loaded: Any = json.load(f)

            if not isinstance(raw_loaded, list):
                raise ValueError("Departments JSON must be a list")

            # 前面已保證為 list，移除冗餘 cast
            raw: list[Any] = raw_loaded
            for obj in raw:
                if not isinstance(obj, dict):
                    raise ValueError("Each department must be a dict")
                item = cast(dict[str, Any], obj)
                if "id" not in item or "name" not in item or "code" not in item:
                    raise ValueError("Department must have id, name, and code")
                if not isinstance(item["code"], int) or item["code"] < 0:
                    raise ValueError("Department code must be a non-negative integer")
                # 類型收斂：subordinates 僅接受字串陣列
                subs_raw = item.get("subordinates")
                subordinates: list[str] | None
                if isinstance(subs_raw, list) and all(isinstance(s, str) for s in subs_raw):
                    subordinates = list(cast(list[str], subs_raw))
                else:
                    subordinates = None

                dept = Department(
                    id=str(item["id"]),
                    name=str(item["name"]),
                    code=int(item["code"]),
                    emoji=str(item["emoji"]) if "emoji" in item else None,
                    level=str(item.get("level", "department")),
                    description=str(item["description"]) if "description" in item else None,
                    parent=str(item["parent"]) if "parent" in item else None,
                    subordinates=subordinates,
                )
                self._departments[dept.id] = dept

            self._build_name_mapping()
            self._loaded = True
            LOGGER.info(
                "department_registry.loaded",
                count=len(self._departments),
                path=str(self._config_path),
            )
        except Exception as exc:
            LOGGER.exception(
                "department_registry.load_error",
                path=str(self._config_path),
                error=str(exc),
            )
            # Fallback to defaults
            self._departments = self._get_default_departments()
            self._build_name_mapping()
            self._loaded = True

    def _get_default_departments(self) -> dict[str, Department]:
        """Return default department definitions as fallback."""
        return {
            "permanent_council": Department(
                id="permanent_council",
                name="常任理事會",
                code=0,
                emoji="👑",
                level="executive",
                description="國家最高決策機構",
            ),
            "state_council": Department(
                id="state_council",
                name="國務院",
                code=100,
                emoji="🏛️",
                level="governance",
                description="國家治理執行機構",
                subordinates=["interior_affairs", "finance", "homeland_security", "central_bank"],
            ),
            "interior_affairs": Department(
                id="interior_affairs",
                name="內政部",
                code=1,
                emoji="🏘️",
                level="department",
                parent="state_council",
            ),
            "finance": Department(
                id="finance",
                name="財政部",
                code=2,
                emoji="💰",
                level="department",
                parent="state_council",
            ),
            "homeland_security": Department(
                id="homeland_security",
                name="國土安全部",
                code=3,
                emoji="🛡️",
                level="department",
                parent="state_council",
            ),
            "central_bank": Department(
                id="central_bank",
                name="中央銀行",
                code=4,
                emoji="🏦",
                level="department",
                parent="state_council",
            ),
        }

    def _build_name_mapping(self) -> None:
        """Build name-to-ID mapping for backward compatibility."""
        self._name_to_id = {dept.name: dept.id for dept in self._departments.values()}

    def get_hierarchy(self) -> dict[str, list[Department]]:
        """Get government hierarchy organized by level.

        Returns:
            Dictionary mapping levels to lists of departments
        """
        hierarchy: dict[str, list[Department]] = {
            "executive": [],
            "governance": [],
            "department": [],
        }

        for dept in self._departments.values():
            level = dept.level or "department"
            if level in hierarchy:
                hierarchy[level].append(dept)
            else:
                hierarchy[level] = [dept]

        return hierarchy

    def get_subordinates(self, department_id: str) -> list[Department]:
        """Get subordinate departments for a given department.

        Args:
            department_id: Parent department ID

        Returns:
            List of subordinate departments
        """
        dept = self._departments.get(department_id)
        if not dept or not dept.subordinates:
            return []

        subordinates: list[Department] = []
        for sub_id in dept.subordinates:
            sub_dept = self._departments.get(sub_id)
            if sub_dept:
                subordinates.append(sub_dept)

        return subordinates

    def get_parent(self, department_id: str) -> Department | None:
        """Get parent department for a given department.

        Args:
            department_id: Child department ID

        Returns:
            Parent department or None if not found
        """
        dept = self._departments.get(department_id)
        if not dept or not dept.parent:
            return None

        return self._departments.get(dept.parent)

    def get_by_level(self, level: str) -> list[Department]:
        """Get all departments of a specific level.

        Args:
            level: Department level (executive, governance, department)

        Returns:
            List of departments at the specified level
        """
        return [dept for dept in self._departments.values() if dept.level == level]

    def get_by_id(self, department_id: str) -> Department | None:
        """Get department by ID.

        Args:
            department_id: Department ID (e.g., "interior_affairs")

        Returns:
            Department or None if not found
        """
        return self._departments.get(department_id)

    def get_by_name(self, name: str) -> Department | None:
        """Get department by display name (backward compatibility).

        Args:
            name: Department name (e.g., "內政部")

        Returns:
            Department or None if not found
        """
        dept_id = self._name_to_id.get(name)
        if dept_id is None:
            return None
        return self._departments.get(dept_id)

    def get_by_code(self, code: int) -> Department | None:
        """Get department by numeric code.

        Args:
            code: Department code (e.g., 1)

        Returns:
            Department or None if not found
        """
        for dept in self._departments.values():
            if dept.code == code:
                return dept
        return None

    def list_all(self) -> Sequence[Department]:
        """Get all departments.

        Returns:
            List of all departments, sorted by code
        """
        return sorted(self._departments.values(), key=lambda d: d.code)

    def get_id_by_name(self, name: str) -> str | None:
        """Get department ID by name (for backward compatibility).

        Args:
            name: Department name (e.g., "內政部")

        Returns:
            Department ID or None if not found
        """
        return self._name_to_id.get(name)

    def get_name_by_id(self, department_id: str) -> str | None:
        """Get department name by ID.

        Args:
            department_id: Department ID (e.g., "interior_affairs")

        Returns:
            Department name or None if not found
        """
        dept = self._departments.get(department_id)
        return dept.name if dept else None


# Global singleton instance
_registry: DepartmentRegistry | None = None


def get_registry() -> DepartmentRegistry:
    """Get global department registry instance."""
    global _registry
    if _registry is None:
        _registry = DepartmentRegistry()
    return _registry


__all__ = ["Department", "DepartmentRegistry", "get_registry"]
