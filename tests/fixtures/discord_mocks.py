"""Discord interaction mock utilities for slash command testing."""

from __future__ import annotations

from typing import Any, TypeVar
from unittest.mock import AsyncMock, MagicMock

import discord
from discord import Interaction, Member, User
from discord.app_commands import AppCommandError, CommandTree

T = TypeVar("T")


class DiscordInteractionMock:
    """Comprehensive mock for Discord interactions and related objects."""

    @staticmethod
    def create_mock_user(
        user_id: int = 123456789,
        name: str = "test_user",
        display_name: str = "Test User",
        discriminator: str = "1234",
        bot: bool = False,
        system: bool = False,
    ) -> MagicMock:
        """Create a mock Discord User object."""
        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.name = name
        mock_user.display_name = display_name
        mock_user.discriminator = discriminator
        mock_user.bot = bot
        mock_user.system = system
        mock_user.mention = f"<@{user_id}>"
        mock_user.avatar_url = "https://cdn.discordapp.com/avatars/123456789/avatar.png"
        return mock_user

    @staticmethod
    def create_mock_member(
        user_id: int = 123456789,
        name: str = "test_member",
        display_name: str = "Test Member",
        guild_id: int = 987654321,
        roles: list[MagicMock] | None = None,
        permissions: discord.Permissions | None = None,
    ) -> MagicMock:
        """Create a mock Discord Member object."""
        mock_member = MagicMock(spec=Member)
        mock_member.id = user_id
        mock_member.name = name
        mock_member.display_name = display_name
        mock_member.discriminator = "1234"
        mock_member.mention = f"<@{user_id}>"
        mock_member.guild.id = guild_id
        mock_member.roles = roles or []
        mock_member.permissions = permissions or discord.Permissions(0)
        mock_member.joined_at = discord.utils.utcnow()
        mock_member.premium_since = None
        mock_member.nick = display_name
        return mock_member

    @staticmethod
    def create_mock_guild(
        guild_id: int = 987654321,
        name: str = "Test Guild",
        member_count: int = 100,
        owner_id: int = 111111111,
    ) -> MagicMock:
        """Create a mock Discord Guild object."""
        mock_guild = MagicMock()
        mock_guild.id = guild_id
        mock_guild.name = name
        mock_guild.member_count = member_count
        mock_guild.owner_id = owner_id
        mock_guild.me = DiscordInteractionMock.create_mock_member(
            user_id=222222222, name="bot_user", guild_id=guild_id
        )
        mock_guild.get_member.return_value = None
        mock_guild.fetch_member = AsyncMock(return_value=None)
        return mock_guild

    @staticmethod
    def create_mock_channel(
        channel_id: int = 555555555,
        name: str = "test-channel",
        guild_id: int = 987654321,
        channel_type: discord.ChannelType = discord.ChannelType.text,
    ) -> MagicMock:
        """Create a mock Discord Channel object."""
        mock_channel = MagicMock()
        mock_channel.id = channel_id
        mock_channel.name = name
        mock_channel.guild.id = guild_id
        mock_channel.type = channel_type
        mock_channel.mention = f"<#{channel_id}>"
        mock_channel.send = AsyncMock()
        mock_channel.fetch_message = AsyncMock(return_value=None)
        return mock_channel

    @staticmethod
    def create_mock_role(
        role_id: int = 777777777,
        name: str = "Test Role",
        permissions: discord.Permissions | None = None,
        position: int = 0,
    ) -> MagicMock:
        """Create a mock Discord Role object."""
        mock_role = MagicMock()
        mock_role.id = role_id
        mock_role.name = name
        mock_role.permissions = permissions or discord.Permissions(0)
        mock_role.position = position
        mock_role.mention = f"<@&{role_id}>"
        mock_role.colour = discord.Colour.blue()
        return mock_role

    @staticmethod
    def create_mock_interaction(
        user_id: int = 123456789,
        guild_id: int = 987654321,
        channel_id: int = 555555555,
        command_name: str = "test_command",
        response_sent: bool = False,
        deferred: bool = False,
        user: User | None = None,
        member: Member | None = None,
        guild: Any = None,
        channel: Any = None,
    ) -> MagicMock:
        """Create a comprehensive mock Discord Interaction."""
        mock_interaction = MagicMock(spec=Interaction)

        # Set up user/member
        mock_interaction.user = user or DiscordInteractionMock.create_mock_user(user_id=user_id)
        mock_interaction.member = member or DiscordInteractionMock.create_mock_member(
            user_id=user_id, guild_id=guild_id
        )

        # Set up guild and channel
        mock_interaction.guild = guild or DiscordInteractionMock.create_mock_guild(
            guild_id=guild_id
        )
        mock_interaction.channel = channel or DiscordInteractionMock.create_mock_channel(
            channel_id=channel_id, guild_id=guild_id
        )

        # Set up command information
        mock_interaction.command.name = command_name
        mock_interaction.command.qualified_name = command_name

        # Set up response methods
        mock_interaction.response.send_message = AsyncMock()
        mock_interaction.response.edit_message = AsyncMock()
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.response.send_modal = AsyncMock()
        mock_interaction.response.send_files = AsyncMock()

        # Set up followup methods
        mock_interaction.followup.send_message = AsyncMock()
        mock_interaction.followup.edit_message = AsyncMock()
        mock_interaction.followup.send_files = AsyncMock()

        # Set up state
        mock_interaction.response.sent = response_sent
        mock_interaction.response.deferred = deferred

        # Set up utility methods
        mock_interaction.client = MagicMock()
        mock_interaction.bot = MagicMock()

        return mock_interaction

    @staticmethod
    def create_mock_command_tree() -> MagicMock:
        """Create a mock CommandTree for testing command registration."""
        mock_tree = MagicMock(spec=CommandTree)
        mock_tree.get_command = MagicMock(return_value=None)
        mock_tree.add_command = MagicMock()
        mock_tree.remove_command = MagicMock()
        mock_tree.sync = AsyncMock()
        return mock_tree

    @staticmethod
    def create_mock_bot(
        command_prefix: str = "!",
        guild_id: int = 987654321,
        intents: discord.Intents | None = None,
    ) -> MagicMock:
        """Create a mock Discord bot instance."""
        mock_bot = MagicMock()
        mock_bot.command_prefix = command_prefix
        mock_bot.intents = intents or discord.Intents.default()
        mock_bot.tree = DiscordInteractionMock.create_mock_command_tree()
        mock_bot.get_guild.return_value = DiscordInteractionMock.create_mock_guild(
            guild_id=guild_id
        )
        mock_bot.get_user.return_value = DiscordInteractionMock.create_mock_user()
        mock_bot.get_channel.return_value = DiscordInteractionMock.create_mock_channel()
        mock_bot.add_listener = MagicMock()
        mock_bot.remove_listener = MagicMock()
        mock_bot.run = MagicMock()
        mock_bot.close = MagicMock()
        mock_bot.is_ready.return_value = True
        return mock_bot


class InteractionResponseValidator:
    """Validator for Discord interaction responses in tests."""

    @staticmethod
    async def assert_response_sent(
        interaction: MagicMock,
        expected_content: str | None = None,
        expected_embeds: int = 0,
        ephemeral: bool = False,
        view: Any = None,
    ) -> None:
        """Assert that interaction.response.send_message was called correctly."""
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        kwargs = call_args[1] if call_args[1] else {}

        if expected_content is not None:
            content = call_args[0][0] if call_args[0] else ""
            assert expected_content in content, f"Expected '{expected_content}' in '{content}'"

        if ephemeral:
            assert kwargs.get("ephemeral", False) is True, "Expected ephemeral response"

        if expected_embeds > 0:
            embeds = kwargs.get("embeds", [])
            assert (
                len(embeds) == expected_embeds
            ), f"Expected {expected_embeds} embeds, got {len(embeds)}"

        if view is not None:
            assert kwargs.get("view") is view, "Expected specific view object"

    @staticmethod
    async def assert_followup_sent(
        interaction: MagicMock,
        expected_content: str | None = None,
        expected_embeds: int = 0,
        ephemeral: bool = False,
    ) -> None:
        """Assert that interaction.followup.send_message was called correctly."""
        interaction.followup.send_message.assert_called_once()
        call_args = interaction.followup.send_message.call_args
        kwargs = call_args[1] if call_args[1] else {}

        if expected_content is not None:
            content = call_args[0][0] if call_args[0] else ""
            assert expected_content in content, f"Expected '{expected_content}' in '{content}'"

        if ephemeral:
            assert kwargs.get("ephemeral", False) is True, "Expected ephemeral followup"

    @staticmethod
    async def assert_deferred(interaction: MagicMock, ephemeral: bool = False) -> None:
        """Assert that interaction.response.defer was called correctly."""
        interaction.response.defer.assert_called_once()
        call_args = interaction.response.defer.call_args
        kwargs = call_args[1] if call_args[1] else {}

        if ephemeral:
            assert kwargs.get("ephemeral", False) is True, "Expected ephemeral defer"

    @staticmethod
    async def assert_error_response(
        interaction: MagicMock,
        expected_error_message: str | None = None,
        ephemeral: bool = True,
    ) -> None:
        """Assert that an error response was sent correctly."""
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        kwargs = call_args[1] if call_args[1] else {}

        content = call_args[0][0] if call_args[0] else ""

        if expected_error_message is not None:
            assert (
                expected_error_message in content
            ), f"Expected '{expected_error_message}' in '{content}'"

        # Error responses should typically be ephemeral
        if ephemeral:
            assert kwargs.get("ephemeral", False) is True, "Expected error response to be ephemeral"


class SlashCommandTestHelper:
    """Helper utilities specifically for slash command testing."""

    @staticmethod
    def create_command_context(
        command_name: str = "test_command",
        user_id: int = 123456789,
        guild_id: int = 987654321,
        channel_id: int = 555555555,
        options: dict[str, Any] | None = None,
    ) -> tuple[MagicMock, MagicMock]:
        """Create a complete command context with interaction and bot."""
        interaction = DiscordInteractionMock.create_mock_interaction(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            command_name=command_name,
        )

        bot = DiscordInteractionMock.create_mock_bot(guild_id=guild_id)

        # Set up command options if provided
        if options:
            interaction.namespace = MagicMock()
            for key, value in options.items():
                setattr(interaction.namespace, key, value)

        return interaction, bot

    @staticmethod
    def simulate_command_error(
        command_name: str = "test_command",
        error_message: str = "Test error",
        error_type: type[Exception] = Exception,
    ) -> AppCommandError:
        """Simulate a Discord command error for error handling tests."""
        error = error_type(error_message)
        return discord.app_commands.CommandInvokeError(error)

    @staticmethod
    def create_permission_denied_context(
        user_id: int = 123456789,
        guild_id: int = 987654321,
        required_permission: str = "administrator",
    ) -> tuple[MagicMock, MagicMock]:
        """Create a context for testing permission denied scenarios."""
        interaction = DiscordInteractionMock.create_mock_interaction(
            user_id=user_id,
            guild_id=guild_id,
        )

        # Remove administrator permissions
        interaction.member.permissions = discord.Permissions.none()

        bot = DiscordInteractionMock.create_mock_bot(guild_id=guild_id)

        return interaction, bot
