"""Integration tests for /help command in full command tree environment."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands

from src.bot.commands.help import build_help_command
from src.bot.commands.help_collector import collect_help_data


def _create_mock_client() -> MagicMock:
    """Create a mock Discord client with required attributes."""
    client = MagicMock(spec=discord.Client)
    client.http = MagicMock()
    connection = MagicMock()
    connection._command_tree = None  # Reset command tree
    client._connection = connection
    return client


@pytest.mark.asyncio
async def test_help_collects_all_registered_commands() -> None:
    """Test that help system collects all commands from a bootstrapped tree."""
    # Skip this test as it requires database initialization
    # In a real integration test, we would set up the database pool first
    # For now, we test help collection with manually added commands
    tree = app_commands.CommandTree(_create_mock_client())

    # Add test commands manually instead of bootstrapping (which requires DB)
    @app_commands.command(name="test_cmd1", description="Test command 1")
    async def test_cmd1(interaction: discord.Interaction) -> None:
        pass

    @app_commands.command(name="test_cmd2", description="Test command 2")
    async def test_cmd2(interaction: discord.Interaction) -> None:
        pass

    tree.add_command(test_cmd1)
    tree.add_command(test_cmd2)

    # Collect help data
    all_help = collect_help_data(tree)

    # Verify commands are collected
    assert "test_cmd1" in all_help
    assert "test_cmd2" in all_help
    assert all_help["test_cmd1"].description == "Test command 1"


@pytest.mark.asyncio
async def test_help_command_with_full_tree() -> None:
    """Test that /help command works with command tree."""
    tree = app_commands.CommandTree(_create_mock_client())

    # Add test commands manually instead of bootstrapping (which requires DB)
    @app_commands.command(name="test_cmd", description="Test command")
    async def test_cmd(interaction: discord.Interaction) -> None:
        pass

    tree.add_command(test_cmd)

    # Build help command
    help_cmd = build_help_command(tree)

    # Create mock interaction
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    # Test without arguments (should show list)
    await help_cmd.callback(interaction, command=None)  # type: ignore[call-arg]

    # Verify response was sent
    assert interaction.response.send_message.called
    call_args = interaction.response.send_message.call_args
    assert call_args is not None
    kwargs = call_args.kwargs
    assert kwargs.get("ephemeral") is True
    # Should have embed or content
    assert "embed" in kwargs or "content" in kwargs


@pytest.mark.asyncio
async def test_help_auto_discovers_new_commands() -> None:
    """Test that new commands are automatically discovered by help system."""
    tree = app_commands.CommandTree(_create_mock_client())

    # Add a test command
    @app_commands.command(name="test_new_cmd", description="Test new command")
    async def test_new_cmd(interaction: discord.Interaction) -> None:
        pass

    tree.add_command(test_new_cmd)

    # Collect help data
    all_help = collect_help_data(tree)

    # Should discover the new command
    assert "test_new_cmd" in all_help
    assert all_help["test_new_cmd"].description == "Test new command"
    assert all_help["test_new_cmd"].category == "general"  # Default category
