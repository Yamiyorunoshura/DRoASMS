"""Format help information as Discord embeds."""

from __future__ import annotations

from collections import defaultdict

import discord
import structlog

from src.bot.commands.help_data import CollectedHelpData

LOGGER = structlog.get_logger(__name__)

# Discord limits
EMBED_TITLE_LIMIT = 256
EMBED_DESCRIPTION_LIMIT = 4096
EMBED_FIELD_NAME_LIMIT = 256
EMBED_FIELD_VALUE_LIMIT = 1024
EMBED_TOTAL_LIMIT = 6000


def format_help_list_embed(
    commands: dict[str, CollectedHelpData],
) -> discord.Embed:
    """Format a list of all commands grouped by category.

    Args:
        commands: Dictionary mapping command names to CollectedHelpData

    Returns:
        Discord Embed with grouped command list
    """
    embed = discord.Embed(
        title="📚 指令列表",
        description="使用 `/help command:<名稱>` 查看特定指令的詳細說明。",
        color=0x3498DB,
    )

    if not commands:
        embed.description = "目前沒有可用指令。"
        return embed

    # Group commands by category
    by_category: dict[str, list[CollectedHelpData]] = defaultdict(list)
    for cmd_data in commands.values():
        by_category[cmd_data.category].append(cmd_data)

    # Sort categories
    sorted_categories = sorted(by_category.keys())

    # Format each category
    for category in sorted_categories:
        category_commands = sorted(by_category[category], key=lambda c: c.name)
        category_display = _format_category_name(category)

        # Build command list for this category
        lines: list[str] = []
        for cmd in category_commands:
            # Format: /command_name - description
            name_display = f"`/{cmd.name}`"
            desc_preview = (
                cmd.description[:60] + "..." if len(cmd.description) > 60 else cmd.description
            )
            lines.append(f"{name_display} - {desc_preview}")

        # Combine lines, respecting field value limit
        field_value = "\n".join(lines)
        if len(field_value) > EMBED_FIELD_VALUE_LIMIT:
            # Truncate if too long
            truncated = field_value[: EMBED_FIELD_VALUE_LIMIT - 3]
            last_newline = truncated.rfind("\n")
            if last_newline > 0:
                truncated = truncated[:last_newline]
            field_value = truncated + "\n..."

        embed.add_field(
            name=f"📁 {category_display}",
            value=field_value or "(無指令)",
            inline=False,
        )

    return embed


def format_command_detail_embed(command: CollectedHelpData) -> discord.Embed:
    """Format detailed information for a single command.

    Args:
        command: CollectedHelpData for the command

    Returns:
        Discord Embed with command details
    """
    embed = discord.Embed(
        title=f"`/{command.name}`",
        description=_truncate_text(command.description, EMBED_DESCRIPTION_LIMIT),
        color=0x2ECC71,
    )

    # Parameters
    if command.parameters:
        param_lines: list[str] = []
        for param in command.parameters:
            name = param.get("name", "")
            desc = param.get("description", "")
            required = param.get("required", True)
            req_marker = "**必填**" if required else "選填"
            param_lines.append(f"• `{name}` ({req_marker}) - {desc}")

        param_text = "\n".join(param_lines)
        embed.add_field(
            name="📝 參數",
            value=_truncate_text(param_text, EMBED_FIELD_VALUE_LIMIT),
            inline=False,
        )

    # Permissions
    if command.permissions:
        perm_text = ", ".join(f"`{p}`" for p in command.permissions)
        embed.add_field(
            name="🔐 權限要求",
            value=_truncate_text(perm_text, EMBED_FIELD_VALUE_LIMIT),
            inline=False,
        )

    # Examples
    if command.examples:
        example_text = "\n".join(f"`{ex}`" for ex in command.examples)
        embed.add_field(
            name="💡 使用範例",
            value=_truncate_text(example_text, EMBED_FIELD_VALUE_LIMIT),
            inline=False,
        )

    # Subcommands (for groups)
    if command.subcommands:
        subcmd_lines: list[str] = []
        for subcmd_name, subcmd_data in sorted(command.subcommands.items()):
            full_name = f"{command.name} {subcmd_name}"
            desc_preview = (
                subcmd_data.description[:50] + "..."
                if len(subcmd_data.description) > 50
                else subcmd_data.description
            )
            subcmd_lines.append(f"• `/{full_name}` - {desc_preview}")

        subcmd_text = "\n".join(subcmd_lines)
        embed.add_field(
            name="📂 子指令",
            value=_truncate_text(subcmd_text, EMBED_FIELD_VALUE_LIMIT),
            inline=False,
        )

    # Category and tags
    footer_parts: list[str] = []
    if command.category != "general":
        footer_parts.append(f"分類: {_format_category_name(command.category)}")
    if command.tags:
        footer_parts.append(f"標籤: {', '.join(command.tags)}")

    if footer_parts:
        embed.set_footer(text=" | ".join(footer_parts))

    return embed


def _format_category_name(category: str) -> str:
    """Format category name for display."""
    category_map: dict[str, str] = {
        "economy": "經濟類",
        "governance": "治理類",
        "general": "一般",
    }
    return category_map.get(category, category.title())


def _truncate_text(text: str, max_length: int) -> str:
    """Truncate text to max_length, trying to break at word boundaries."""
    if len(text) <= max_length:
        return text

    truncated = text[: max_length - 3]
    # Try to break at newline first
    last_newline = truncated.rfind("\n")
    if last_newline > max_length * 0.8:  # If newline is reasonably close
        return truncated[:last_newline] + "\n..."
    # Otherwise break at space
    last_space = truncated.rfind(" ")
    if last_space > max_length * 0.8:
        return truncated[:last_space] + "..."
    # Fallback: hard truncate
    return truncated + "..."
