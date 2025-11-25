"""Unit tests for the help slash command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord import app_commands

from src.bot.commands.help import build_help_command, register
from src.bot.commands.help_data import CollectedHelpData


def _create_mock_client() -> MagicMock:
    """Create a mock Discord client with required attributes."""
    client = MagicMock(spec=discord.Client)
    client.http = MagicMock()
    connection = MagicMock()
    connection._command_tree = None
    client._connection = connection
    return client


def _create_mock_interaction(
    guild_id: int = 123456789,
    user_id: int = 987654321,
) -> MagicMock:
    """Create a mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = MagicMock(spec=discord.Guild)
    interaction.guild.id = guild_id
    interaction.user = MagicMock(spec=discord.User)
    interaction.user.id = user_id
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    return interaction


class TestHelpCommandRegister:
    """Test cases for help command registration."""

    @pytest.mark.unit
    def test_register_adds_command_to_tree(self) -> None:
        """Test that register() adds the help command to the tree."""
        tree = app_commands.CommandTree(_create_mock_client())
        register(tree)

        # Get command from tree
        commands = tree.get_commands()
        command_names = [cmd.name for cmd in commands]

        assert "help" in command_names

    @pytest.mark.unit
    def test_build_help_command_returns_command(self) -> None:
        """Test that build_help_command() returns a valid command."""
        tree = app_commands.CommandTree(_create_mock_client())
        command = build_help_command(tree)

        assert command is not None
        assert command.name == "help"
        assert "指令" in command.description


class TestHelpCommandExecution:
    """Test cases for help command execution."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_help_command_list_all(self) -> None:
        """Test /help command showing list of all commands."""
        tree = app_commands.CommandTree(_create_mock_client())

        # Add a test command
        @app_commands.command(name="test_cmd", description="Test command")
        async def test_cmd(interaction: discord.Interaction) -> None:
            pass

        tree.add_command(test_cmd)  # type: ignore[arg-type]
        command = build_help_command(tree)

        # Create mock interaction
        interaction = _create_mock_interaction()

        # Execute command (no specific command argument)
        with patch(
            "src.bot.commands.help.collect_help_data",
            return_value={
                "test_cmd": CollectedHelpData(
                    name="test_cmd",
                    description="Test command",
                    category="general",
                    parameters=[],
                    permissions=[],
                    examples=[],
                    tags=[],
                    subcommands={},
                )
            },
        ):
            # Get callback and call it
            callback = command.callback
            await callback(interaction, command=None)  # type: ignore[call-arg]

        # Verify response was sent with embed
        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert "embed" in call_kwargs
        assert call_kwargs["ephemeral"] is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_help_command_specific_command_found(self) -> None:
        """Test /help command with specific command that exists."""
        tree = app_commands.CommandTree(_create_mock_client())
        command = build_help_command(tree)

        interaction = _create_mock_interaction()

        with patch(
            "src.bot.commands.help.collect_help_data",
            return_value={
                "transfer": CollectedHelpData(
                    name="transfer",
                    description="轉帳虛擬貨幣",
                    category="economy",
                    parameters=[],
                    permissions=[],
                    examples=["/transfer @user 100"],
                    tags=[],
                    subcommands={},
                )
            },
        ):
            callback = command.callback
            await callback(interaction, command="transfer")  # type: ignore[call-arg]

        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert "embed" in call_kwargs
        assert call_kwargs["ephemeral"] is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_help_command_specific_command_not_found(self) -> None:
        """Test /help command with specific command that doesn't exist."""
        tree = app_commands.CommandTree(_create_mock_client())
        command = build_help_command(tree)

        interaction = _create_mock_interaction()

        with patch(
            "src.bot.commands.help.collect_help_data",
            return_value={
                "transfer": CollectedHelpData(
                    name="transfer",
                    description="轉帳虛擬貨幣",
                    category="economy",
                    parameters=[],
                    permissions=[],
                    examples=[],
                    tags=[],
                    subcommands={},
                )
            },
        ):
            callback = command.callback
            await callback(interaction, command="nonexistent")  # type: ignore[call-arg]

        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert "content" in call_kwargs
        assert "找不到指令" in call_kwargs["content"]
        assert call_kwargs["ephemeral"] is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_help_command_subcommand_search(self) -> None:
        """Test /help command searching for subcommands."""
        tree = app_commands.CommandTree(_create_mock_client())
        command = build_help_command(tree)

        interaction = _create_mock_interaction()

        # Create nested structure with subcommands
        subcommand_data = CollectedHelpData(
            name="council panel",
            description="開啟理事會面板",
            category="governance",
            parameters=[],
            permissions=[],
            examples=["/council panel"],
            tags=[],
            subcommands={},
        )

        council_data = CollectedHelpData(
            name="council",
            description="理事會指令",
            category="governance",
            parameters=[],
            permissions=[],
            examples=[],
            tags=[],
            subcommands={"council panel": subcommand_data},
        )

        with patch(
            "src.bot.commands.help.collect_help_data",
            return_value={"council": council_data},
        ):
            callback = command.callback
            await callback(interaction, command="council panel")  # type: ignore[call-arg]

        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert "embed" in call_kwargs

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_help_command_with_many_commands(self) -> None:
        """Test /help command with more than 10 commands shows truncated list."""
        tree = app_commands.CommandTree(_create_mock_client())
        command = build_help_command(tree)

        interaction = _create_mock_interaction()

        # Create 15 mock commands
        commands_dict = {}
        for i in range(15):
            commands_dict[f"cmd{i}"] = CollectedHelpData(
                name=f"cmd{i}",
                description=f"Command {i}",
                category="general",
                parameters=[],
                permissions=[],
                examples=[],
                tags=[],
                subcommands={},
            )

        with patch(
            "src.bot.commands.help.collect_help_data",
            return_value=commands_dict,
        ):
            callback = command.callback
            await callback(interaction, command="nonexistent_cmd")  # type: ignore[call-arg]

        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert "共 15 個指令" in call_kwargs["content"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_help_command_error_handling(self) -> None:
        """Test /help command error handling."""
        tree = app_commands.CommandTree(_create_mock_client())
        command = build_help_command(tree)

        interaction = _create_mock_interaction()

        with patch(
            "src.bot.commands.help.collect_help_data",
            side_effect=Exception("Test error"),
        ):
            callback = command.callback
            await callback(interaction, command=None)  # type: ignore[call-arg]

        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert "content" in call_kwargs
        assert "發生錯誤" in call_kwargs["content"]
        assert call_kwargs["ephemeral"] is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_help_command_whitespace_in_search(self) -> None:
        """Test /help command handles whitespace in command search."""
        tree = app_commands.CommandTree(_create_mock_client())
        command = build_help_command(tree)

        interaction = _create_mock_interaction()

        with patch(
            "src.bot.commands.help.collect_help_data",
            return_value={
                "transfer": CollectedHelpData(
                    name="transfer",
                    description="轉帳",
                    category="economy",
                    parameters=[],
                    permissions=[],
                    examples=[],
                    tags=[],
                    subcommands={},
                )
            },
        ):
            callback = command.callback
            # Pass command with extra whitespace
            await callback(interaction, command="  transfer  ")  # type: ignore[call-arg]

        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert "embed" in call_kwargs

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_help_command_case_insensitive_search(self) -> None:
        """Test /help command search is case insensitive."""
        tree = app_commands.CommandTree(_create_mock_client())
        command = build_help_command(tree)

        interaction = _create_mock_interaction()

        with patch(
            "src.bot.commands.help.collect_help_data",
            return_value={
                "Transfer": CollectedHelpData(
                    name="Transfer",
                    description="轉帳",
                    category="economy",
                    parameters=[],
                    permissions=[],
                    examples=[],
                    tags=[],
                    subcommands={},
                )
            },
        ):
            callback = command.callback
            await callback(interaction, command="transfer")  # type: ignore[call-arg]

        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert "embed" in call_kwargs

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_help_command_partial_match_last_part(self) -> None:
        """Test /help command partial match on last part of compound command."""
        tree = app_commands.CommandTree(_create_mock_client())
        command = build_help_command(tree)

        interaction = _create_mock_interaction()

        with patch(
            "src.bot.commands.help.collect_help_data",
            return_value={
                "council panel": CollectedHelpData(
                    name="council panel",
                    description="開啟面板",
                    category="governance",
                    parameters=[],
                    permissions=[],
                    examples=[],
                    tags=[],
                    subcommands={},
                )
            },
        ):
            callback = command.callback
            # Search by just "panel" should match "council panel"
            await callback(interaction, command="panel")  # type: ignore[call-arg]

        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert "embed" in call_kwargs

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_help_command_partial_match_first_part(self) -> None:
        """Test /help command partial match when searching with first part of group."""
        tree = app_commands.CommandTree(_create_mock_client())
        command = build_help_command(tree)

        interaction = _create_mock_interaction()

        with patch(
            "src.bot.commands.help.collect_help_data",
            return_value={
                "council panel": CollectedHelpData(
                    name="council panel",
                    description="開啟面板",
                    category="governance",
                    parameters=[],
                    permissions=[],
                    examples=[],
                    tags=[],
                    subcommands={},
                )
            },
        ):
            callback = command.callback
            # Search by "council sub" should match "council panel" via first part
            await callback(interaction, command="council sub")  # type: ignore[call-arg]

        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert "embed" in call_kwargs
