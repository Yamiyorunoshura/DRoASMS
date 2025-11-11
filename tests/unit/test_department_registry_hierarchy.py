"""Unit tests for department registry hierarchy functionality."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from src.bot.services.department_registry import Department, DepartmentRegistry


class TestDepartmentRegistryHierarchy:
    """Test cases for department registry hierarchy features."""

    @pytest.fixture
    def sample_departments_json(self) -> str:
        """Sample departments JSON with hierarchy."""
        return json.dumps(
            [
                {
                    "id": "permanent_council",
                    "name": "常任理事會",
                    "code": 0,
                    "emoji": "👑",
                    "level": "executive",
                    "description": "國家最高決策機構",
                },
                {
                    "id": "state_council",
                    "name": "國務院",
                    "code": 100,
                    "emoji": "🏛️",
                    "level": "governance",
                    "description": "國家治理執行機構",
                    "subordinates": ["interior_affairs", "finance"],
                },
                {
                    "id": "interior_affairs",
                    "name": "內政部",
                    "code": 1,
                    "emoji": "🏘️",
                    "level": "department",
                    "parent": "state_council",
                },
                {
                    "id": "finance",
                    "name": "財政部",
                    "code": 2,
                    "emoji": "💰",
                    "level": "department",
                    "parent": "state_council",
                },
            ]
        )

    @pytest.fixture
    def registry_with_hierarchy(self, sample_departments_json: str) -> DepartmentRegistry:
        """Create registry with hierarchy data."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open", mock_open(read_data=sample_departments_json)),
        ):
            return DepartmentRegistry()

    def test_department_with_optional_fields(self) -> None:
        """Test Department creation with all optional fields."""
        dept = Department(
            id="test",
            name="Test Department",
            code=1,
            emoji="🧪",
            level="department",
            description="Test description",
            parent="parent_dept",
            subordinates=["child1", "child2"],
        )

        assert dept.id == "test"
        assert dept.name == "Test Department"
        assert dept.code == 1
        assert dept.emoji == "🧪"
        assert dept.level == "department"
        assert dept.description == "Test description"
        assert dept.parent == "parent_dept"
        assert dept.subordinates == ["child1", "child2"]

    def test_department_defaults(self) -> None:
        """Test Department with default values."""
        dept = Department(id="test", name="Test Department", code=1)

        assert dept.emoji is None
        assert dept.level == "department"
        assert dept.description is None
        assert dept.parent is None
        assert dept.subordinates is None

    def test_get_hierarchy(self, registry_with_hierarchy: DepartmentRegistry) -> None:
        """Test getting government hierarchy."""
        hierarchy = registry_with_hierarchy.get_hierarchy()

        assert "executive" in hierarchy
        assert "governance" in hierarchy
        assert "department" in hierarchy

        assert len(hierarchy["executive"]) == 1
        assert hierarchy["executive"][0].name == "常任理事會"

        assert len(hierarchy["governance"]) == 1
        assert hierarchy["governance"][0].name == "國務院"

        assert len(hierarchy["department"]) == 2
        dept_names = [dept.name for dept in hierarchy["department"]]
        assert "內政部" in dept_names
        assert "財政部" in dept_names

    def test_get_subordinates(self, registry_with_hierarchy: DepartmentRegistry) -> None:
        """Test getting subordinate departments."""
        subordinates = registry_with_hierarchy.get_subordinates("state_council")

        assert len(subordinates) == 2
        sub_names = [dept.name for dept in subordinates]
        assert "內政部" in sub_names
        assert "財政部" in sub_names

    def test_get_subordinates_none(self, registry_with_hierarchy: DepartmentRegistry) -> None:
        """Test getting subordinates for department with none."""
        subordinates = registry_with_hierarchy.get_subordinates("interior_affairs")
        assert len(subordinates) == 0

    def test_get_subordinates_nonexistent(
        self, registry_with_hierarchy: DepartmentRegistry
    ) -> None:
        """Test getting subordinates for nonexistent department."""
        subordinates = registry_with_hierarchy.get_subordinates("nonexistent")
        assert len(subordinates) == 0

    def test_get_parent(self, registry_with_hierarchy: DepartmentRegistry) -> None:
        """Test getting parent department."""
        parent = registry_with_hierarchy.get_parent("interior_affairs")

        assert parent is not None
        assert parent.name == "國務院"
        assert parent.id == "state_council"

    def test_get_parent_top_level(self, registry_with_hierarchy: DepartmentRegistry) -> None:
        """Test getting parent for top-level department."""
        parent = registry_with_hierarchy.get_parent("permanent_council")
        assert parent is None

    def test_get_parent_nonexistent(self, registry_with_hierarchy: DepartmentRegistry) -> None:
        """Test getting parent for nonexistent department."""
        parent = registry_with_hierarchy.get_parent("nonexistent")
        assert parent is None

    def test_get_by_level(self, registry_with_hierarchy: DepartmentRegistry) -> None:
        """Test getting departments by level."""
        executives = registry_with_hierarchy.get_by_level("executive")
        assert len(executives) == 1
        assert executives[0].name == "常任理事會"

        governance = registry_with_hierarchy.get_by_level("governance")
        assert len(governance) == 1
        assert governance[0].name == "國務院"

        departments = registry_with_hierarchy.get_by_level("department")
        assert len(departments) == 2

    def test_get_by_level_nonexistent(self, registry_with_hierarchy: DepartmentRegistry) -> None:
        """Test getting departments by nonexistent level."""
        depts = registry_with_hierarchy.get_by_level("nonexistent")
        assert len(depts) == 0

    def test_load_departments_with_hierarchy_from_json(self, tmp_path: Path) -> None:
        """Test loading departments with hierarchy from JSON file."""
        departments_json = [
            {"id": "test_parent", "name": "Test Parent", "code": 1, "subordinates": ["test_child"]},
            {"id": "test_child", "name": "Test Child", "code": 2, "parent": "test_parent"},
        ]

        config_path = tmp_path / "departments.json"
        config_path.write_text(json.dumps(departments_json))

        registry = DepartmentRegistry(config_path)

        parent = registry.get_by_id("test_parent")
        child = registry.get_by_id("test_child")

        assert parent is not None
        assert child is not None
        assert parent.subordinates == ["test_child"]
        assert child.parent == "test_parent"

    def test_default_departments_with_hierarchy(self) -> None:
        """Test that default departments include hierarchy."""
        registry = DepartmentRegistry()  # Uses defaults

        # Check executive level
        permanent_council = registry.get_by_id("permanent_council")
        assert permanent_council is not None
        assert permanent_council.level == "executive"

        # Check governance level
        state_council = registry.get_by_id("state_council")
        assert state_council is not None
        assert state_council.level == "governance"
        assert state_council.subordinates is not None
        assert "interior_affairs" in state_council.subordinates

        # Check department level
        interior_affairs = registry.get_by_id("interior_affairs")
        assert interior_affairs is not None
        assert interior_affairs.level == "department"
        assert interior_affairs.parent == "state_council"

    def test_backward_compatibility(self, registry_with_hierarchy: DepartmentRegistry) -> None:
        """Test that basic lookup methods still work with new structure."""
        # Test get_by_id
        dept = registry_with_hierarchy.get_by_id("interior_affairs")
        assert dept is not None
        assert dept.name == "內政部"

        # Test get_by_name
        dept = registry_with_hierarchy.get_by_name("國務院")
        assert dept is not None
        assert dept.id == "state_council"

        # Test get_all_departments
        all_depts = list(registry_with_hierarchy._departments.values())
        assert len(all_depts) == 4

    def test_error_handling_invalid_json(self) -> None:
        """Test error handling for invalid JSON."""
        invalid_json = "not valid json"

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open", mock_open(read_data=invalid_json)),
        ):
            registry = DepartmentRegistry()

            # Should fall back to defaults
            dept = registry.get_by_id("interior_affairs")
            assert dept is not None
            assert dept.name == "內政部"

    def test_error_handling_missing_required_fields(self) -> None:
        """Test error handling for JSON missing required fields."""
        incomplete_json = json.dumps([{"id": "test", "name": "Test"}])  # Missing code

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open", mock_open(read_data=incomplete_json)),
        ):
            registry = DepartmentRegistry()

            # Should fall back to defaults
            dept = registry.get_by_id("interior_affairs")
            assert dept is not None
            assert dept.name == "內政部"
