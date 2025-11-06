"""Unit tests for department registry."""

from __future__ import annotations

import json
import pathlib
import tempfile

import pytest

from src.bot.services.department_registry import Department, DepartmentRegistry, get_registry


@pytest.mark.unit
def test_registry_loads_default_departments() -> None:
    """Test that registry loads default departments when config file is missing."""
    registry = DepartmentRegistry(config_path="/nonexistent/path/departments.json")

    dept = registry.get_by_id("interior_affairs")
    assert dept is not None
    assert dept.name == "內政部"
    assert dept.code == 1


@pytest.mark.unit
def test_registry_loads_from_json() -> None:
    """Test that registry loads departments from JSON file."""
    dept_data = [
        {"id": "test_dept", "name": "測試部門", "code": 99, "emoji": "🧪"},
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(dept_data, f, ensure_ascii=False)
        temp_path = pathlib.Path(f.name)

    try:
        registry = DepartmentRegistry(config_path=temp_path)
        dept = registry.get_by_id("test_dept")
        assert dept is not None
        assert dept.name == "測試部門"
        assert dept.code == 99
        assert dept.emoji == "🧪"
    finally:
        temp_path.unlink()


@pytest.mark.unit
def test_registry_query_methods() -> None:
    """Test all query methods of the registry."""
    registry = get_registry()

    # Test get_by_id
    dept = registry.get_by_id("interior_affairs")
    assert dept is not None
    assert isinstance(dept, Department)

    # Test get_by_name
    dept = registry.get_by_name("內政部")
    assert dept is not None
    assert dept.id == "interior_affairs"

    # Test get_by_code
    dept = registry.get_by_code(2)
    assert dept is not None
    assert dept.name == "財政部"

    # Test list_all
    all_depts = registry.list_all()
    assert len(all_depts) >= 4
    assert all(isinstance(d, Department) for d in all_depts)

    # Test get_id_by_name
    dept_id = registry.get_id_by_name("中央銀行")
    assert dept_id == "central_bank"

    # Test get_name_by_id
    dept_name = registry.get_name_by_id("homeland_security")
    assert dept_name == "國土安全部"


@pytest.mark.unit
def test_registry_handles_invalid_queries() -> None:
    """Test that registry handles invalid queries gracefully."""
    registry = get_registry()

    # Test non-existent ID
    assert registry.get_by_id("nonexistent") is None

    # Test non-existent name
    assert registry.get_by_name("不存在的部門") is None

    # Test non-existent code
    assert registry.get_by_code(999) is None

    # Test invalid ID for name lookup
    assert registry.get_name_by_id("invalid_id") is None

    # Test invalid name for ID lookup
    assert registry.get_id_by_name("不存在的部門") is None


@pytest.mark.unit
def test_registry_singleton() -> None:
    """Test that get_registry returns singleton instance."""
    registry1 = get_registry()
    registry2 = get_registry()
    assert registry1 is registry2


@pytest.mark.unit
def test_department_dataclass() -> None:
    """Test Department dataclass structure."""
    dept = Department(
        id="test",
        name="測試",
        code=1,
        emoji="🧪",
    )

    assert dept.id == "test"
    assert dept.name == "測試"
    assert dept.code == 1
    assert dept.emoji == "🧪"

    # Test optional emoji
    dept_no_emoji = Department(
        id="test2",
        name="測試2",
        code=2,
    )
    assert dept_no_emoji.emoji is None
