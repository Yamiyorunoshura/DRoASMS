"""Base test class for slash command testing.

Provides standardized testing patterns, fixtures, and utilities for testing
Discord slash commands with Result<T,E> error handling, permission checks,
and coverage monitoring integration.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from types import MethodType
from typing import Any, Callable, TypeVar, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infra.result import Err, Error, Result, ValidationError

from .discord_mocks import DiscordInteractionMock, InteractionResponseValidator
from .permission_fixtures import PermissionTestFixture
from .result_helpers import ResultTestHelper

T = TypeVar("T")
E = TypeVar("E", bound=Error)


class CommandTestCase(ABC):
    """Abstract base class for slash command test cases."""

    # Command configuration (to be overridden by subclasses)
    COMMAND_NAME: str = ""
    COMMAND_MODULE: str = ""
    MINIMUM_COVERAGE: float = 90.0

    @abstractmethod
    def get_command_function(self) -> Callable[..., Any]:
        """Get the command function to test."""
        pass

    @abstractmethod
    def get_mock_services(self) -> dict[str, MagicMock]:
        """Get mock services for the command."""
        pass

    @abstractmethod
    def get_expected_success_response(self) -> str | dict[str, Any]:
        """Get expected success response content."""
        pass

    def setup_command_test(
        self,
        user_id: int = 123456789,
        guild_id: int = 987654321,
        channel_id: int = 555555555,
        **kwargs: Any,
    ) -> tuple[MagicMock, dict[str, MagicMock]]:
        """Set up command test environment with mocks."""
        # Create mock interaction
        interaction = DiscordInteractionMock.create_mock_interaction(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            command_name=self.COMMAND_NAME,
            **kwargs,
        )

        # Get mock services
        services = self.get_mock_services()

        return interaction, services

    async def execute_command(
        self,
        interaction: MagicMock,
        services: dict[str, MagicMock],
        command_args: dict[str, Any] | None = None,
    ) -> Result[Any, Error]:
        """Execute the command with given arguments."""
        command_func = self.get_command_function()
        args = command_args or {}

        # Inject services into command function if needed
        if isinstance(command_func, MethodType):
            # Method on a service instance
            instance = command_func.__self__
            for service_name, service_mock in services.items():
                if hasattr(instance, service_name):
                    setattr(instance, service_name, service_mock)

        # Execute command
        if inspect.iscoroutinefunction(command_func):
            result = await command_func(interaction, **args)
        else:
            result = command_func(interaction, **args)
        return cast(Result[Any, Error], result)

    async def assert_command_success(
        self,
        result: Result[T, E],
        interaction: MagicMock,
        expected_content: str | None = None,
        expected_embeds: int = 0,
        ephemeral: bool = False,
    ) -> T:
        """Assert that command executed successfully."""
        # Check Result is Ok
        success_value = ResultTestHelper.assert_ok_result(result)

        # Check interaction response
        response_content: str | None = expected_content
        if response_content is None:
            expected_response = self.get_expected_success_response()
            if isinstance(expected_response, dict):
                response_content = str(expected_response)
            else:
                response_content = expected_response

        # Assert response was sent correctly
        validator = InteractionResponseValidator()
        await validator.assert_response_sent(
            interaction,
            expected_content=response_content,
            expected_embeds=expected_embeds,
            ephemeral=ephemeral,
        )

        return success_value

    async def assert_command_error(
        self,
        result: Result[T, E],
        interaction: MagicMock,
        expected_error_type: type[E] | None = None,
        expected_error_message: str | None = None,
        ephemeral: bool = True,
    ) -> E:
        """Assert that command failed with expected error."""
        # Check Result is Err
        error = ResultTestHelper.assert_err_result(result, expected_error_type)

        # Check error message if provided
        if expected_error_message:
            assert expected_error_message in error.message

        # Check error response was sent
        validator = InteractionResponseValidator()
        await validator.assert_error_response(
            interaction,
            expected_error_message=expected_error_message or error.message,
            ephemeral=ephemeral,
        )

        return error

    async def test_command_success_basic(self) -> None:
        """Test basic command success scenario."""
        interaction, services = self.setup_command_test()
        result = await self.execute_command(interaction, services)
        await self.assert_command_success(result, interaction)

    async def test_command_permission_denied(self) -> None:
        """Test command with insufficient permissions."""
        # Set up regular user without permissions
        interaction, services = self.setup_command_test()
        regular_member, _ = PermissionTestFixture.create_regular_member()
        interaction.member = regular_member

        result = await self.execute_command(interaction, services)
        await self.assert_command_error(result, interaction, expected_error_message="權限")

    async def test_command_database_error(self) -> None:
        """Test command with database error."""
        interaction, services = self.setup_command_test()

        # Make one of the services raise a database error
        for service_mock in services.values():
            if hasattr(service_mock, "execute"):
                service_mock.execute.side_effect = Exception("Database connection failed")
                break

        result = await self.execute_command(interaction, services)
        await self.assert_command_error(result, interaction, expected_error_message="資料庫")

    async def test_command_invalid_arguments(self) -> None:
        """Test command with invalid arguments."""
        interaction, services = self.setup_command_test()

        # Pass invalid arguments (empty dict to trigger validation errors)
        result = await self.execute_command(interaction, services, command_args={})

        # Most commands should handle empty args gracefully
        if result.is_err():
            await self.assert_command_error(result, interaction, expected_error_message="參數")


class SlashCommandTestBase(CommandTestCase):
    """Enhanced base class specifically for slash commands."""

    def setup_command_test_with_permissions(
        self,
        permission_type: str = "admin",
        user_id: int = 123456789,
        guild_id: int = 987654321,
        department: str | None = None,
    ) -> tuple[MagicMock, dict[str, MagicMock]]:
        """Set up command test with specific permission configuration."""
        if permission_type == "admin":
            member, registry = PermissionTestFixture.create_admin_member(
                user_id=user_id, guild_id=guild_id, department=department or "法務部"
            )
        elif permission_type == "department" and department:
            member, registry = PermissionTestFixture.create_department_member(
                user_id=user_id, guild_id=guild_id, department=department
            )
        elif permission_type == "owner":
            member, registry = PermissionTestFixture.create_guild_owner(
                user_id=user_id, guild_id=guild_id
            )
        else:
            member, registry = PermissionTestFixture.create_regular_member(
                user_id=user_id, guild_id=guild_id
            )

        interaction, services = self.setup_command_test(
            user_id=user_id, guild_id=guild_id, member=member
        )

        # Add permission registry to services if needed
        services["permission_registry"] = registry

        return interaction, services

    async def test_admin_only_command_success(self) -> None:
        """Test admin-only command with admin user."""
        interaction, services = self.setup_command_test_with_permissions("admin")
        result = await self.execute_command(interaction, services)
        await self.assert_command_success(result, interaction)

    async def test_admin_only_command_denied(self) -> None:
        """Test admin-only command with regular user."""
        interaction, services = self.setup_command_test_with_permissions("regular")
        result = await self.execute_command(interaction, services)
        await self.assert_command_error(result, interaction, expected_error_message="管理員")

    async def test_department_command_success(self, department: str = "法務部") -> None:
        """Test department-specific command with correct department member."""
        interaction, services = self.setup_command_test_with_permissions(
            "department", department=department
        )
        result = await self.execute_command(interaction, services)
        await self.assert_command_success(result, interaction)

    async def test_department_command_wrong_department(self) -> None:
        """Test department command with wrong department member."""
        interaction, services = self.setup_command_test_with_permissions(
            "department",
            department="財政部",  # Wrong department
        )
        result = await self.execute_command(interaction, services)
        await self.assert_command_error(result, interaction, expected_error_message="法務部")


class EconomyCommandTestBase(SlashCommandTestBase):
    """Base class for economy-related slash commands."""

    def get_mock_economy_services(self) -> dict[str, MagicMock]:
        """Get standard economy service mocks."""
        return {
            "adjustment_service": AsyncMock(),
            "transfer_service": AsyncMock(),
            "balance_service": AsyncMock(),
            "economy_gateway": AsyncMock(),
            "pending_transfer_gateway": AsyncMock(),
        }

    async def test_insufficient_balance_error(self) -> None:
        """Test economy command with insufficient balance."""
        interaction, services = self.setup_command_test()

        # Mock insufficient balance response
        services["balance_service"].get_balance.return_value = Err(
            ValidationError("餘額不足", context={"balance": 0, "required": 100})
        )

        result = await self.execute_command(interaction, services)
        await self.assert_command_error(result, interaction, expected_error_message="餘額不足")

    async def test_transfer_cooldown_error(self) -> None:
        """Test transfer command with cooldown active."""
        interaction, services = self.setup_command_test()

        # Mock cooldown response
        services["transfer_service"].check_cooldown.return_value = Err(
            ValidationError("轉帳冷卻中", context={"remaining_seconds": 60})
        )

        result = await self.execute_command(interaction, services)
        await self.assert_command_error(result, interaction, expected_error_message="冷卻")


class GovernanceCommandTestBase(SlashCommandTestBase):
    """Base class for governance-related slash commands."""

    def get_mock_governance_services(self) -> dict[str, MagicMock]:
        """Get standard governance service mocks."""
        return {
            "council_service": AsyncMock(),
            "state_council_service": AsyncMock(),
            "supreme_assembly_service": AsyncMock(),
            "council_gateway": AsyncMock(),
            "state_council_gateway": AsyncMock(),
            "supreme_assembly_gateway": AsyncMock(),
        }

    async def test_proposal_not_found_error(self) -> None:
        """Test governance command with non-existent proposal."""
        interaction, services = self.setup_command_test()

        # Mock proposal not found
        services["council_service"].get_proposal.return_value = Err(
            ValidationError("提案不存在", context={"proposal_id": 999})
        )

        result = await self.execute_command(interaction, services)
        await self.assert_command_error(result, interaction, expected_error_message="提案不存在")

    async def test_voting_period_ended_error(self) -> None:
        """Test governance command with ended voting period."""
        interaction, services = self.setup_command_test()

        # Mock voting period ended
        services["council_service"].check_voting_period.return_value = Err(
            ValidationError("投票期已結束", context={"proposal_id": 123})
        )

        result = await self.execute_command(interaction, services)
        await self.assert_command_error(result, interaction, expected_error_message="投票期")


def command_test_case(
    command_name: str,
    command_module: str,
    minimum_coverage: float = 90.0,
) -> Callable[[type[CommandTestCase]], type[CommandTestCase]]:
    """Decorator to configure command test case metadata."""

    def decorator(cls: type[CommandTestCase]) -> type[CommandTestCase]:
        cls.COMMAND_NAME = command_name
        cls.COMMAND_MODULE = command_module
        cls.MINIMUM_COVERAGE = minimum_coverage
        return cls

    return decorator


# Pytest fixtures for command testing
@pytest.fixture
def command_test_helper() -> type[CommandTestCase]:
    """Provide base command test helper class."""
    return CommandTestCase


@pytest.fixture
def slash_command_test_helper() -> type[SlashCommandTestBase]:
    """Provide slash command test helper class."""
    return SlashCommandTestBase


@pytest.fixture
def economy_command_test_helper() -> type[EconomyCommandTestBase]:
    """Provide economy command test helper class."""
    return EconomyCommandTestBase


@pytest.fixture
def governance_command_test_helper() -> type[GovernanceCommandTestBase]:
    """Provide governance command test helper class."""
    return GovernanceCommandTestBase
