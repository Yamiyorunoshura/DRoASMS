"""Test helpers for Result<T,E> error path testing in slash commands."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar
from unittest.mock import AsyncMock, MagicMock

import pytest
from discord import Interaction
from discord.app_commands import CommandInvokeError

from src.infra.result import Err, Error, Ok, Result

T = TypeVar("T")
E = TypeVar("E", bound=Error)


class ResultTestHelper:
    """Helper class for testing Result<T,E> patterns in slash commands."""

    @staticmethod
    def assert_ok_result(result: Result[T, E], expected_value: T | None = None) -> T:
        """Assert that a Result is Ok and optionally check its value."""
        assert result.is_ok(), f"Expected Ok result, got Err: {result.unwrap_err()}"
        if expected_value is not None:
            assert result.unwrap() == expected_value
        return result.unwrap()

    @staticmethod
    def assert_err_result(result: Result[T, E], expected_error_type: type[E] | None = None) -> E:
        """Assert that a Result is Err and optionally check its type."""
        assert result.is_err(), f"Expected Err result, got Ok: {result.unwrap()}"
        error = result.unwrap_err()
        if expected_error_type is not None:
            assert isinstance(
                error, expected_error_type
            ), f"Expected {expected_error_type}, got {type(error)}"
        return error

    @staticmethod
    def create_mock_interaction(
        user_id: int = 123456789,
        guild_id: int = 987654321,
        channel_id: int = 555555555,
        response_sent: bool = False,
    ) -> MagicMock:
        """Create a mock Discord Interaction for testing."""
        mock_interaction = MagicMock(spec=Interaction)
        mock_interaction.user.id = user_id
        mock_interaction.guild.id = guild_id
        mock_interaction.channel.id = channel_id
        mock_interaction.response.send_message = AsyncMock()
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send_message = AsyncMock()
        mock_interaction.response.sent = response_sent
        return mock_interaction

    @staticmethod
    def create_mock_ctx(
        user_id: int = 123456789,
        guild_id: int = 987654321,
        channel_id: int = 555555555,
        author_name: str = "test_user",
    ) -> MagicMock:
        """Create a mock Discord Context for testing."""
        mock_ctx = MagicMock()
        mock_ctx.author.id = user_id
        mock_ctx.author.name = author_name
        mock_ctx.guild.id = guild_id
        mock_ctx.channel.id = channel_id
        mock_ctx.send = AsyncMock()
        mock_ctx.reply = AsyncMock()
        mock_ctx.invoke = AsyncMock()
        return mock_ctx

    @staticmethod
    async def assert_interaction_response(
        interaction: MagicMock,
        expected_content: str | None = None,
        expected_embed_count: int = 0,
        ephemeral: bool = False,
    ) -> None:
        """Assert that an interaction response was sent with expected parameters."""
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args

        if expected_content is not None:
            assert (
                expected_content in call_args[0][0]
            ), f"Expected '{expected_content}' in response content"

        if ephemeral:
            assert call_args[1]["ephemeral"] is True, "Expected response to be ephemeral"

    @staticmethod
    def create_command_error(error: Exception, command: Any | None = None) -> CommandInvokeError:
        """Create a Discord command error wrapper."""
        if command is None:
            command = MagicMock()
        return CommandInvokeError(command, error)

    @staticmethod
    def assert_error_handled(
        result: Result[T, E],
        expected_error_message: str | None = None,
        expected_error_type: type[E] | None = None,
    ) -> None:
        """Assert that an error was properly handled and converted to Result."""
        assert result.is_err(), "Expected error result"
        error = result.unwrap_err()

        if expected_error_type is not None:
            assert isinstance(
                error, expected_error_type
            ), f"Expected {expected_error_type}, got {type(error)}"

        if expected_error_message is not None:
            assert (
                expected_error_message in error.message
            ), f"Expected '{expected_error_message}' in error message"


class AsyncResultTestHelper:
    """Helper class for testing async Result<T,E> patterns."""

    @staticmethod
    async def assert_async_ok_result(
        async_result: Callable[[], Awaitable[Any]] | Awaitable[Any],
        expected_value: T | None = None,
    ) -> T:
        """Assert that an async Result is Ok and optionally check its value."""
        if callable(async_result):
            result = await async_result()
        else:
            result = await async_result

        return ResultTestHelper.assert_ok_result(result, expected_value)

    @staticmethod
    async def assert_async_err_result(
        async_result: Callable[[], Awaitable[Any]] | Awaitable[Any],
        expected_error_type: type[E] | None = None,
    ) -> E:
        """Assert that an async Result is Err and optionally check its type."""
        if callable(async_result):
            result = await async_result()
        else:
            result = await async_result

        return ResultTestHelper.assert_err_result(result, expected_error_type)


class DatabaseMockHelper:
    """Helper for mocking database operations in Result<T,E> tests."""

    @staticmethod
    def create_mock_pool(
        fetch_result: list[dict[str, Any]] | None = None,
        fetchrow_result: dict[str, Any] | None = None,
        execute_result: str | None = None,
        should_raise: Exception | None = None,
    ) -> AsyncMock:
        """Create a mock database pool with predefined results."""
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()

        if should_raise:
            mock_connection.fetch.side_effect = should_raise
            mock_connection.fetchrow.side_effect = should_raise
            mock_connection.execute.side_effect = should_raise
        else:
            mock_connection.fetch.return_value = fetch_result or []
            mock_connection.fetchrow.return_value = fetchrow_result
            mock_connection.execute.return_value = execute_result or "OK"

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        return mock_pool

    @staticmethod
    def create_mock_transaction(
        commit_result: Any = None,
        rollback_result: Any = None,
        should_raise: Exception | None = None,
    ) -> AsyncMock:
        """Create a mock database transaction."""
        mock_transaction = AsyncMock()
        mock_transaction.start = AsyncMock()
        mock_transaction.commit = AsyncMock(return_value=commit_result)
        mock_transaction.rollback = AsyncMock(return_value=rollback_result)

        if should_raise:
            mock_transaction.commit.side_effect = should_raise
            mock_transaction.rollback.side_effect = should_raise

        return mock_transaction


class PermissionMockHelper:
    """Helper for mocking permission checks in slash command tests."""

    @staticmethod
    def create_permission_check_result(
        has_permission: bool,
        user_id: int = 123456789,
        guild_id: int = 987654321,
        department: str | None = None,
        role: str | None = None,
    ) -> Result[bool, Error]:
        """Create a mock permission check result."""
        if has_permission:
            return Ok(True)

        error_message = f"User {user_id} lacks permission"
        if department:
            error_message += f" for department {department}"
        if role:
            error_message += f" with role {role}"

        from src.infra.result import ValidationError

        return Err(
            ValidationError(error_message, context={"user_id": user_id, "guild_id": guild_id})
        )

    @staticmethod
    def mock_department_registry(
        has_department: bool = True,
        is_admin: bool = False,
        department_name: str = "test_department",
    ) -> MagicMock:
        """Create a mock department registry for permission testing."""
        mock_registry = MagicMock()
        mock_registry.has_department.return_value = has_department
        mock_registry.is_admin.return_value = is_admin
        mock_registry.get_department_name.return_value = department_name
        return mock_registry


# Pytest fixtures for common test scenarios
@pytest.fixture
def result_helper() -> ResultTestHelper:
    """Provide ResultTestHelper instance for tests."""
    return ResultTestHelper()


@pytest.fixture
def async_result_helper() -> AsyncResultTestHelper:
    """Provide AsyncResultTestHelper instance for tests."""
    return AsyncResultTestHelper()


@pytest.fixture
def db_mock_helper() -> DatabaseMockHelper:
    """Provide DatabaseMockHelper instance for tests."""
    return DatabaseMockHelper()


@pytest.fixture
def permission_mock_helper() -> PermissionMockHelper:
    """Provide PermissionMockHelper instance for tests."""
    return PermissionMockHelper()


@pytest.fixture
def mock_interaction() -> MagicMock:
    """Provide a basic mock Discord Interaction."""
    return ResultTestHelper.create_mock_interaction()


@pytest.fixture
def mock_ctx() -> MagicMock:
    """Provide a basic mock Discord Context."""
    return ResultTestHelper.create_mock_ctx()
