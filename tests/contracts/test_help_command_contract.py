"""Contract tests for /help command output format."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands

from src.bot.commands.help import build_help_command


def _create_mock_client() -> MagicMock:
    """Create a mock Discord client with required attributes."""
    client = MagicMock(spec=discord.Client)
    client.http = MagicMock()
    connection = MagicMock()
    connection._command_tree = None  # Reset command tree
    client._connection = connection
    return client


@pytest.mark.asyncio
async def test_help_no_args_returns_list() -> None:
    """Test that /help (no args) returns ephemeral message with grouped list."""
    tree = app_commands.CommandTree(_create_mock_client())

    # Add some test commands
    @app_commands.command(name="test1", description="Test command 1")
    async def test1(interaction: discord.Interaction) -> None:
        pass

    @app_commands.command(name="test2", description="Test command 2")
    async def test2(interaction: discord.Interaction) -> None:
        pass

    tree.add_command(test1)
    tree.add_command(test2)

    # Build help command
    help_cmd = build_help_command(tree)

    # Create mock interaction
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = None
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    # Invoke help command without arguments
    await help_cmd.callback(interaction, command=None)  # type: ignore[call-arg]

    # Verify ephemeral response
    call_args = interaction.response.send_message.call_args
    assert call_args is not None
    kwargs = call_args.kwargs
    assert kwargs.get("ephemeral") is True
    assert "embed" in kwargs or "content" in kwargs


@pytest.mark.asyncio
async def test_help_with_command_arg_returns_detail() -> None:
    """Test that /help command:<name> returns detailed embed."""
    tree = app_commands.CommandTree(_create_mock_client())

    @app_commands.command(name="test_cmd", description="Test command description")
    async def test_cmd(interaction: discord.Interaction) -> None:
        pass

    tree.add_command(test_cmd)

    help_cmd = build_help_command(tree)

    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = None
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    # Invoke with command argument
    await help_cmd.callback(interaction, command="test_cmd")  # type: ignore[call-arg]

    # Verify response contains embed with command details
    call_args = interaction.response.send_message.call_args
    assert call_args is not None
    kwargs = call_args.kwargs
    assert kwargs.get("ephemeral") is True
    embed = kwargs.get("embed")
    assert embed is not None
    assert "test_cmd" in embed.title.lower() or "test_cmd" in str(embed.description).lower()


@pytest.mark.asyncio
async def test_help_invalid_command_returns_error() -> None:
    """Test that /help command:<invalid> returns error message."""
    tree = app_commands.CommandTree(_create_mock_client())

    help_cmd = build_help_command(tree)

    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = None
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    # Invoke with non-existent command
    await help_cmd.callback(interaction, command="nonexistent_command")  # type: ignore[call-arg]

    # Verify error message
    call_args = interaction.response.send_message.call_args
    assert call_args is not None
    kwargs = call_args.kwargs
    assert kwargs.get("ephemeral") is True
    content = kwargs.get("content", "")
    assert (
        "不存在" in content.lower() or "找不到" in content.lower() or "not found" in content.lower()
    )


@pytest.mark.asyncio
async def test_help_group_subcommand_detail() -> None:
    """Test that /help command:<group subcommand> shows subcommand details."""
    tree = app_commands.CommandTree(_create_mock_client())

    group = app_commands.Group(name="test_group", description="Test group")

    @group.command(name="sub", description="Subcommand description")
    async def sub(interaction: discord.Interaction) -> None:
        pass

    tree.add_command(group)

    help_cmd = build_help_command(tree)

    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = None
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    # Test accessing subcommand
    await help_cmd.callback(interaction, command="test_group sub")  # type: ignore[call-arg]

    call_args = interaction.response.send_message.call_args
    assert call_args is not None
    kwargs = call_args.kwargs
    assert kwargs.get("ephemeral") is True
    # Should show subcommand details or group with subcommands
    embed = kwargs.get("embed")
    assert embed is not None
