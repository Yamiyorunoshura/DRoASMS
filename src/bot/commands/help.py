"""Slash command for displaying help information."""

from __future__ import annotations

from typing import Any, Optional

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_collector import collect_help_data
from src.bot.commands.help_data import CollectedHelpData
from src.bot.commands.help_formatter import format_command_detail_embed, format_help_list_embed

LOGGER = structlog.get_logger(__name__)


def register(tree: app_commands.CommandTree) -> None:
    """Register the /help slash command with the provided command tree."""
    command = build_help_command(tree)
    tree.add_command(command)
    LOGGER.debug("bot.command.help.registered")


def build_help_command(tree: app_commands.CommandTree) -> app_commands.Command[Any, Any, Any]:
    """Build the `/help` slash command bound to the provided command tree."""

    @app_commands.command(
        name="help",
        description="顯示所有可用指令的說明，或查詢特定指令的詳細資訊。",
    )
    @app_commands.describe(
        command="選填，要查詢的指令名稱（例如：transfer、council panel）",
    )
    async def help(
        interaction: discord.Interaction,
        command: Optional[str] = None,
    ) -> None:
        """Handle /help command with optional command parameter."""
        try:
            # 依照互動所屬的 Guild 收集該作用域的指令，
            # 避免在清空全域指令後（guild allowlist 模式）/help 看不到任何指令。
            all_help_data = collect_help_data(tree, guild=interaction.guild)

            if command:
                # Look up specific command
                command_input = command.strip()
                command_lower = command_input.lower()
                found = None

                def _find_command(
                    data: dict[str, CollectedHelpData], search: str
                ) -> CollectedHelpData | None:
                    """Recursively search for command in data and subcommands."""
                    # Try exact match first
                    for cmd_name, cmd_data in data.items():
                        if cmd_name.lower() == search:
                            return cmd_data
                        # Check subcommands
                        if cmd_data.subcommands:
                            sub_found = _find_command(cmd_data.subcommands, search)
                            if sub_found:
                                return sub_found
                    # Try partial match
                    for cmd_name, cmd_data in data.items():
                        cmd_parts = cmd_name.lower().split()
                        search_parts = search.split()
                        # Full match (e.g., "test_group sub" matches "test_group sub")
                        if " ".join(cmd_parts) == search:
                            return cmd_data
                        # Last part match (e.g., "sub" matches "test_group sub")
                        if len(cmd_parts) > 1 and cmd_parts[-1] == search:
                            return cmd_data
                        # First part match (e.g., "test_group" matches "test_group sub")
                        if len(search_parts) > 1 and cmd_parts[0] == search_parts[0]:
                            return cmd_data
                    return None

                found = _find_command(all_help_data, command_lower)

                if found:
                    embed = format_command_detail_embed(found)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    # Command not found
                    available = ", ".join(sorted(all_help_data.keys())[:10])
                    if len(all_help_data) > 10:
                        available += f" ... 共 {len(all_help_data)} 個指令"
                    await interaction.response.send_message(
                        content=f"找不到指令 `{command}`。\n可用指令：{available}",
                        ephemeral=True,
                    )
            else:
                # Show list of all commands
                embed = format_help_list_embed(all_help_data)
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as exc:
            LOGGER.exception("bot.help.error", error=str(exc))
            await interaction.response.send_message(
                content="查詢幫助資訊時發生錯誤，請稍後再試。",
                ephemeral=True,
            )

    return help
