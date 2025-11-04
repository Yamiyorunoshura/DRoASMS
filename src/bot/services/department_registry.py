"""Department registry for unified department identification."""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Sequence

import structlog

LOGGER = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Department:
    """Department metadata."""

    id: str
    name: str
    code: int
    emoji: str | None = None


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
                data = json.load(f)

            if not isinstance(data, list):
                raise ValueError("Departments JSON must be a list")

            for item in data:
                if not isinstance(item, dict):
                    raise ValueError("Each department must be a dict")
                if "id" not in item or "name" not in item or "code" not in item:
                    raise ValueError("Department must have id, name, and code")
                if not isinstance(item["code"], int) or item["code"] < 0:
                    raise ValueError("Department code must be a non-negative integer")

                dept = Department(
                    id=str(item["id"]),
                    name=str(item["name"]),
                    code=int(item["code"]),
                    emoji=str(item["emoji"]) if "emoji" in item else None,
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
            "interior_affairs": Department(
                id="interior_affairs",
                name="內政部",
                code=1,
                emoji="🏘️",
            ),
            "finance": Department(
                id="finance",
                name="財政部",
                code=2,
                emoji="💰",
            ),
            "homeland_security": Department(
                id="homeland_security",
                name="國土安全部",
                code=3,
                emoji="🛡️",
            ),
            "central_bank": Department(
                id="central_bank",
                name="中央銀行",
                code=4,
                emoji="🏦",
            ),
        }

    def _build_name_mapping(self) -> None:
        """Build name-to-ID mapping for backward compatibility."""
        self._name_to_id = {dept.name: dept.id for dept in self._departments.values()}

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
