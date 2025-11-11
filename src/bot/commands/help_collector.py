"""Collect help information from command tree."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_data import CollectedHelpData, HelpData

LOGGER = structlog.get_logger(__name__)


def collect_help_data(
    tree: app_commands.CommandTree,
    guild: discord.abc.Snowflake | None = None,
) -> dict[str, CollectedHelpData]:
    """Collect help data from all commands in the command tree.

    Priority order:
    1. JSON file in `help_data/` directory (unified registry)
    2. `get_help_data()` function from command module
    3. Auto-extracted from command metadata (fallback)

    Returns:
        Dictionary mapping command full names (e.g., "transfer", "council panel")
        to CollectedHelpData instances.
    """
    result: dict[str, CollectedHelpData] = {}

    # 在採用 guild allowlist 的部署模式下，我們會先將全域指令複製到指定 Guild，
    # 接著清空本地樹上的全域指令集合以避免重複顯示。此時若直接呼叫
    # tree.get_commands()（不帶 guild），會得到空集合，導致 /help 看不到任何指令。
    #
    # 因此這裡根據互動發生的 guild（若有）去讀取該 guild 作用域內的指令；
    # 若互動不是在 guild（例如 DM；通常 slash 指令本身就不可用），則回退至全域集合。
    commands = tree.get_commands(guild=guild) if guild is not None else tree.get_commands()

    for command in commands:
        # Skip context menus, only process commands and groups
        if isinstance(command, (app_commands.Command, app_commands.Group)):
            _collect_command_help(command, result, parent_name="")

    return result


def _collect_command_help(
    command: app_commands.Command[Any, Any, Any] | app_commands.Group,
    result: dict[str, CollectedHelpData],
    parent_name: str = "",
) -> None:
    """Recursively collect help data from a command or group."""
    full_name = f"{parent_name} {command.name}".strip() if parent_name else command.name

    # Try JSON file first (unified registry)
    help_data: HelpData | None = None
    json_data = _load_help_json(command.name, parent_name)
    if json_data:
        help_data = json_data
        LOGGER.debug("help.collect.from_json", command=full_name)

    # Try module function if JSON didn't provide data
    # 先取模組名稱，以便後續群組子指令也能使用（避免未繫結警告）
    module_name: str | None = getattr(command, "__module__", None)
    if help_data is None:
        if module_name:
            try:
                module = import_module(module_name)
                get_help_func = getattr(module, "get_help_data", None)
                if callable(get_help_func):
                    # IMPORTANT: avoid shadowing the outer `result` collector dict.
                    func_result = get_help_func()
                    # Handle both single HelpData and dict[str, HelpData] cases
                    if isinstance(func_result, dict):
                        # If it's a dict, look up by command name
                        fd = cast(dict[str, HelpData], func_result)
                        help_data = fd.get(command.name) or fd.get(full_name)
                    else:
                        # Single HelpData object
                        help_data = cast(HelpData, func_result)
                    if help_data:
                        LOGGER.debug("help.collect.from_function", command=full_name)
            except Exception as exc:
                LOGGER.warning("help.collect.function_error", command=full_name, error=str(exc))

    # Fallback to command metadata
    if help_data is None:
        help_data = _extract_from_command_metadata(command)

    # Create CollectedHelpData
    # HelpData is a TypedDict, which is compatible with dict[str, Any]
    collected = CollectedHelpData.from_dict(dict(help_data), name=full_name)

    # Handle subcommands for groups
    if isinstance(command, app_commands.Group):
        # Try to get subcommand help data from parent module's get_help_data
        parent_module_help: dict[str, HelpData] | None = None
        if module_name:
            try:
                module = import_module(module_name)
                get_help_func = getattr(module, "get_help_data", None)
                if callable(get_help_func):
                    result_data = get_help_func()
                    if isinstance(result_data, dict):
                        parent_module_help = cast(dict[str, HelpData], result_data)
            except Exception:
                pass

        for subcommand in command.commands:
            subcommand_full_name = f"{full_name} {subcommand.name}"
            # Try to get help data for subcommand from parent module dict
            subcommand_help_data: HelpData | None = None
            if parent_module_help:
                subcommand_help_data = parent_module_help.get(
                    subcommand_full_name
                ) or parent_module_help.get(subcommand.name)

            if subcommand_help_data:
                # Use provided help data
                # HelpData is a TypedDict, which is compatible with dict[str, Any]
                subcommand_collected = CollectedHelpData.from_dict(
                    dict(subcommand_help_data), name=subcommand_full_name
                )
                collected.subcommands[subcommand.name] = subcommand_collected
            else:
                # Fallback to normal collection
                _collect_command_help(subcommand, collected.subcommands, parent_name=full_name)

    # Store into the shared collection passed by the caller.
    result[full_name] = collected


def _load_help_json(command_name: str, parent_name: str = "") -> HelpData | None:
    """Load help data from JSON file in help_data/ directory."""
    # Determine file path
    if parent_name:
        # For subcommands: help_data/council/panel.json
        parts = parent_name.split()
        file_path = Path("src/bot/commands/help_data") / "/".join(parts) / f"{command_name}.json"
    else:
        # For top-level commands: help_data/transfer.json
        file_path = Path("src/bot/commands/help_data") / f"{command_name}.json"

    if not file_path.exists():
        return None

    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return cast(HelpData, data)
    except Exception as exc:
        LOGGER.warning("help.collect.json_error", path=str(file_path), error=str(exc))
        return None


def _extract_from_command_metadata(
    command: app_commands.Command[Any, Any, Any] | app_commands.Group,
) -> HelpData:
    """Extract basic help data from command metadata as fallback."""
    description = command.description or "無描述"

    # Extract parameters from command
    from src.bot.commands.help_data import HelpParameter

    parameters: list[HelpParameter] = []
    if isinstance(command, app_commands.Command):
        # Access parameters via the command's _params attribute or similar
        # discord.py stores parameter metadata differently
        # For now, we'll leave it empty and rely on explicit help data
        pass

    return {
        "name": command.name,
        "description": description,
        "category": "general",
        "parameters": parameters,
        "permissions": [],
        "examples": [],
        "tags": [],
    }
