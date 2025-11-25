"""Permission check test fixtures for slash command testing."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import discord
import pytest
from discord import Member, Role

from src.infra.result import Err, Ok, Result, ValidationError


class PermissionTestFixture:
    """Test fixtures for various permission scenarios."""

    @staticmethod
    def create_admin_member(
        user_id: int = 123456789,
        guild_id: int = 987654321,
        department: str = "法務部",
    ) -> tuple[MagicMock, MagicMock]:
        """Create an admin member with full permissions."""
        mock_member = MagicMock(spec=Member)
        mock_member.id = user_id
        mock_member.guild.id = guild_id
        mock_member.name = "admin_user"
        mock_member.display_name = "Admin User"
        mock_member.discriminator = "1234"

        # Give administrator permissions
        mock_member.permissions = discord.Permissions(administrator=True)

        # Create admin role
        admin_role = MagicMock(spec=Role)
        admin_role.id = 888888888
        admin_role.name = "Admin"
        admin_role.permissions = discord.Permissions(administrator=True)
        mock_member.roles = [admin_role]

        # Create department registry mock
        mock_registry = MagicMock()
        mock_registry.is_admin.return_value = True
        mock_registry.has_department.return_value = True
        mock_registry.get_department_name.return_value = department

        return mock_member, mock_registry

    @staticmethod
    def create_department_member(
        user_id: int = 123456789,
        guild_id: int = 987654321,
        department: str = "法務部",
        is_admin: bool = False,
    ) -> tuple[MagicMock, MagicMock]:
        """Create a member with specific department permissions."""
        mock_member = MagicMock(spec=Member)
        mock_member.id = user_id
        mock_member.guild.id = guild_id
        mock_member.name = "dept_user"
        mock_member.display_name = "Department User"
        mock_member.discriminator = "1234"

        # Limited permissions
        mock_member.permissions = discord.Permissions.none()

        # Create department role
        dept_role = MagicMock(spec=Role)
        dept_role.id = 999999999
        dept_role.name = department
        dept_role.permissions = discord.Permissions.none()
        mock_member.roles = [dept_role]

        # Create department registry mock
        mock_registry = MagicMock()
        mock_registry.is_admin.return_value = is_admin
        mock_registry.has_department.return_value = True
        mock_registry.get_department_name.return_value = department

        return mock_member, mock_registry

    @staticmethod
    def create_regular_member(
        user_id: int = 123456789,
        guild_id: int = 987654321,
    ) -> tuple[MagicMock, MagicMock]:
        """Create a regular member with no special permissions."""
        mock_member = MagicMock(spec=Member)
        mock_member.id = user_id
        mock_member.guild.id = guild_id
        mock_member.name = "regular_user"
        mock_member.display_name = "Regular User"
        mock_member.discriminator = "1234"

        # No special permissions
        mock_member.permissions = discord.Permissions.none()
        mock_member.roles = []

        # Create department registry mock
        mock_registry = MagicMock()
        mock_registry.is_admin.return_value = False
        mock_registry.has_department.return_value = False
        mock_registry.get_department_name.return_value = None

        return mock_member, mock_registry

    @staticmethod
    def create_guild_owner(
        user_id: int = 111111111,
        guild_id: int = 987654321,
    ) -> tuple[MagicMock, MagicMock]:
        """Create a guild owner with maximum permissions."""
        mock_member = MagicMock(spec=Member)
        mock_member.id = user_id
        mock_member.guild.id = guild_id
        mock_member.guild.owner_id = user_id  # Set as owner
        mock_member.name = "guild_owner"
        mock_member.display_name = "Guild Owner"
        mock_member.discriminator = "1234"

        # Owner has all permissions
        mock_member.permissions = discord.Permissions.all()

        # Create owner role
        owner_role = MagicMock(spec=Role)
        owner_role.id = 666666666
        owner_role.name = "Guild Owner"
        owner_role.permissions = discord.Permissions.all()
        mock_member.roles = [owner_role]

        # Create department registry mock
        mock_registry = MagicMock()
        mock_registry.is_admin.return_value = True
        mock_registry.has_department.return_value = True
        mock_registry.get_department_name.return_value = "法務部"

        return mock_member, mock_registry


class PermissionTestScenarios:
    """Common permission test scenarios for slash commands."""

    @staticmethod
    def admin_permission_check() -> Result[bool, ValidationError]:
        """Simulate successful admin permission check."""
        return Ok(True)

    @staticmethod
    def admin_permission_denied() -> Result[bool, ValidationError]:
        """Simulate failed admin permission check."""
        return ValidationError("需要管理員權限", context={"permission": "administrator"})

    @staticmethod
    def department_permission_check(
        department: str = "法務部",
        user_id: int = 123456789,
    ) -> Result[bool, ValidationError]:
        """Simulate successful department permission check."""
        return Ok(True)

    @staticmethod
    def department_permission_denied(
        department: str = "法務部",
        user_id: int = 123456789,
    ) -> Result[bool, ValidationError]:
        """Simulate failed department permission check."""
        return ValidationError(
            f"需要 {department} 權限", context={"department": department, "user_id": user_id}
        )

    @staticmethod
    def justice_department_special_permission() -> Result[bool, ValidationError]:
        """Simulate justice department special permission (for adjust command)."""
        return Ok(True)

    @staticmethod
    def justice_department_permission_denied() -> Result[bool, ValidationError]:
        """Simulate failed justice department permission check."""
        return ValidationError("只有法務部可以使用調整命令", context={"department": "法務部"})


class DepartmentPermissionMock:
    """Mock for department-specific permission checks."""

    def __init__(self, user_departments: dict[int, str], admin_users: set[int] | None = None):
        """Initialize with user department mappings and optional admin set."""
        self.user_departments = user_departments
        self.admin_users = admin_users or set()

    def check_permission(
        self, user_id: int, required_department: str | None = None
    ) -> Result[bool, ValidationError]:
        """Check if user has permission for the required department."""
        if user_id in self.admin_users:
            return Ok(True)

        if required_department is None:
            return ValidationError("需要指定部門", context={"user_id": user_id})

        user_department = self.user_departments.get(user_id)
        if user_department == required_department:
            return Ok(True)

        return ValidationError(
            f"用戶不屬於 {required_department}",
            context={
                "user_id": user_id,
                "required_department": required_department,
                "user_department": user_department,
            },
        )

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in self.admin_users

    def get_user_department(self, user_id: int) -> str | None:
        """Get user's department."""
        return self.user_departments.get(user_id)


# Pytest fixtures for permission testing
@pytest.fixture
def admin_member() -> tuple[MagicMock, MagicMock]:
    """Provide admin member and registry for testing."""
    return PermissionTestFixture.create_admin_member()


@pytest.fixture
def justice_department_member() -> tuple[MagicMock, MagicMock]:
    """Provide justice department member for testing."""
    return PermissionTestFixture.create_department_member(department="法務部")


@pytest.fixture
def finance_department_member() -> tuple[MagicMock, MagicMock]:
    """Provide finance department member for testing."""
    return PermissionTestFixture.create_department_member(department="財政部")


@pytest.fixture
def regular_member() -> tuple[MagicMock, MagicMock]:
    """Provide regular member with no permissions for testing."""
    return PermissionTestFixture.create_regular_member()


@pytest.fixture
def guild_owner() -> tuple[MagicMock, MagicMock]:
    """Provide guild owner for testing."""
    return PermissionTestFixture.create_guild_owner()


@pytest.fixture
def department_permission_mock() -> DepartmentPermissionMock:
    """Provide department permission mock for testing."""
    user_departments = {
        123456789: "法務部",
        234567890: "財政部",
        345678901: "內政部",
        456789012: "國防部",
    }
    admin_users = {111111111, 222222222}
    return DepartmentPermissionMock(user_departments, admin_users)


@pytest.fixture
def permission_test_scenarios() -> PermissionTestScenarios:
    """Provide permission test scenarios for testing."""
    return PermissionTestScenarios()


@pytest.fixture
def mock_department_registry() -> MagicMock:
    """Provide a mock department registry for testing."""
    mock_registry = MagicMock()
    mock_registry.is_admin.return_value = False
    mock_registry.has_department.return_value = False
    mock_registry.get_department_name.return_value = None
    mock_registry.check_permission.return_value = Err(
        ValidationError("權限不足", context={"user_id": 123456789})
    )
    return mock_registry


@pytest.fixture
def mock_admin_registry() -> MagicMock:
    """Provide a mock admin department registry for testing."""
    mock_registry = MagicMock()
    mock_registry.is_admin.return_value = True
    mock_registry.has_department.return_value = True
    mock_registry.get_department_name.return_value = "法務部"
    mock_registry.check_permission.return_value = Ok(True)
    return mock_registry


@pytest.fixture
def mock_justice_registry() -> MagicMock:
    """Provide a mock justice department registry for testing."""
    mock_registry = MagicMock()
    mock_registry.is_admin.return_value = False
    mock_registry.has_department.return_value = True
    mock_registry.get_department_name.return_value = "法務部"
    mock_registry.check_permission.return_value = Ok(True)
    return mock_registry


class PermissionAssertionHelper:
    """Helper for asserting permission-related behaviors in tests."""

    @staticmethod
    def assert_permission_denied_response(
        interaction: MagicMock,
        expected_message: str | None = None,
    ) -> None:
        """Assert that a permission denied response was sent."""
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args

        content = call_args[0][0] if call_args[0] else ""
        kwargs = call_args[1] if call_args[1] else {}

        # Should be ephemeral
        assert kwargs.get("ephemeral", False) is True, "Permission denied should be ephemeral"

        # Should contain error message
        if expected_message:
            assert expected_message in content, f"Expected '{expected_message}' in '{content}'"
        else:
            # Default error message check
            assert any(
                word in content.lower() for word in ["權限", "permission", "沒有", "無法", "denied"]
            ), f"Expected permission error in '{content}'"

    @staticmethod
    def assert_admin_check_called(
        registry: MagicMock,
        user_id: int = 123456789,
    ) -> None:
        """Assert that admin check was called with correct user ID."""
        registry.is_admin.assert_called_with(user_id)

    @staticmethod
    def assert_department_check_called(
        registry: MagicMock,
        user_id: int = 123456789,
        department: str = "法務部",
    ) -> None:
        """Assert that department check was called with correct parameters."""
        registry.has_department.assert_called_with(user_id, department)

    @staticmethod
    def create_permission_test_data() -> dict[str, Any]:
        """Create comprehensive test data for permission scenarios."""
        return {
            "admin_user_id": 111111111,
            "justice_user_id": 123456789,
            "finance_user_id": 234567890,
            "regular_user_id": 345678901,
            "guild_id": 987654321,
            "departments": ["法務部", "財政部", "內政部", "國防部"],
            "permission_messages": {
                "admin_required": "需要管理員權限",
                "department_required": "需要部門權限",
                "justice_only": "只有法務部可以使用此命令",
            },
        }


@pytest.fixture
def permission_assertion_helper() -> PermissionAssertionHelper:
    """Provide permission assertion helper for testing."""
    return PermissionAssertionHelper()


@pytest.fixture
def permission_test_data() -> dict[str, Any]:
    """Provide comprehensive permission test data."""
    return PermissionAssertionHelper.create_permission_test_data()
