"""Collect help information from command tree."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any, TypedDict, cast

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_data import CollectedHelpData, HelpData, HelpParameter

LOGGER = structlog.get_logger(__name__)

JsonDict = dict[str, Any]


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

    # Try unified registry first
    help_data: HelpData | None = None
    registry_data = _load_help_from_registry(full_name)
    if registry_data:
        help_data = registry_data
        LOGGER.debug("help.collect.from_registry", command=full_name)

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
        for subcommand in command.commands:
            _collect_command_help(subcommand, collected.subcommands, parent_name=full_name)

    # Store into the shared collection passed by the caller.
    result[full_name] = collected


class _RegistryNode(TypedDict):
    data: HelpData
    subcommands: dict[str, "_RegistryNode"]


_registry_cache: dict[str, _RegistryNode] | None = None


def _load_help_json(
    command_name: str, parent_name: str = ""
) -> HelpData | None:  # pyright: ignore[reportUnusedFunction]
    """Legacy loader kept for unit tests and transitional compatibility.

    It first tries to locate per-command JSON files (both legacy scattered files and
    the consolidated `commands.json`), and finally falls back to the unified registry.
    """

    def _legacy_candidates() -> list[Path]:
        base = Path("src/bot/commands/help_data")
        candidates: list[Path] = []
        if parent_name:
            candidates.append(base / parent_name / f"{command_name}.json")
            candidates.append(base / parent_name / "commands.json")
        candidates.append(base / f"{command_name}.json")
        candidates.append(base / "commands.json")
        return candidates

    for candidate in _legacy_candidates():
        data = _read_help_file(candidate)
        if data is None:
            continue
        entry = _extract_help_entry(data, command_name, parent_name)
        if entry is not None:
            result = dict(entry)
            if result and "name" not in result:
                result["name"] = " ".join(filter(None, [parent_name, command_name]))
            return cast(HelpData, result)

    # Final fallback: use the in-memory registry that powers the new collector.
    full_name = " ".join(filter(None, [parent_name, command_name])).strip()
    if not full_name:
        return None
    return _load_help_from_registry(full_name)


def _read_help_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fp:
            payload = json.load(fp)
    except Exception as exc:  # pragma: no cover - logging side effect
        LOGGER.warning("help.json.load_error", path=str(path), error=str(exc))
        return None
    if not isinstance(payload, dict):
        LOGGER.warning("help.json.invalid_format", path=str(path))
        return None
    typed_payload: JsonDict = payload
    return typed_payload


def _extract_help_entry(
    payload: dict[str, Any], command_name: str, parent_name: str = ""
) -> HelpData | None:
    # If payload already resembles HelpData (or even empty dict for tests), return it directly.
    if _looks_like_help_data(payload):
        return cast(HelpData, payload)

    path: list[str] = [command_name]
    if parent_name:
        path = [parent_name, command_name]

    entry = _dig_help_payload(payload, path)
    if entry is not None:
        return entry

    # Retry without parent in case file stores flat maps even for subcommands.
    if parent_name:
        return _dig_help_payload(payload, [command_name])
    return None


def _dig_help_payload(node: dict[str, Any], path: list[str]) -> HelpData | None:
    current: dict[str, Any] | None = node
    for part in path:
        if not isinstance(current, dict):
            return None
        current_dict: JsonDict = current
        # Direct key match
        direct = current_dict.get(part)
        if isinstance(direct, dict):
            current = cast(JsonDict, direct)
            continue
        # Nested under subcommands
        subcommands = current_dict.get("subcommands")
        if isinstance(subcommands, dict):
            nested = subcommands.get(part)
            if isinstance(nested, dict):
                current = cast(JsonDict, nested)
                continue
        return None

    if isinstance(current, dict):
        return cast(HelpData, current)
    return None


def _looks_like_help_data(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload == {}:
        return True
    known_keys = {"description", "category", "parameters", "permissions", "examples", "tags"}
    if any(key in payload for key in known_keys):
        # Heuristic: assume dict represents the help object instead of registry.
        return True
    return False


def _load_help_from_registry(full_name: str) -> HelpData | None:
    """Return help data for the given command name from the unified registry."""
    node = _get_registry_node(full_name)
    if node is None:
        return None

    data = dict(node["data"])
    data.setdefault("name", full_name)
    return cast(HelpData, data)


def _get_registry_node(full_name: str) -> _RegistryNode | None:
    registry = _load_registry()
    if not full_name:
        return None
    parts = full_name.split()
    node = registry.get(parts[0])
    for part in parts[1:]:
        if node is None:
            return None
        node = node["subcommands"].get(part)
    return node


def _load_registry() -> dict[str, _RegistryNode]:
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    path = Path("src/bot/commands/help_data/commands.json")
    if not path.exists():
        LOGGER.warning("help.registry.missing", path=str(path))
        _registry_cache = {}
        return _registry_cache

    try:
        with path.open("r", encoding="utf-8") as fp:
            raw_payload = json.load(fp)
    except Exception as exc:
        LOGGER.warning("help.registry.load_error", path=str(path), error=str(exc))
        _registry_cache = {}
        return _registry_cache

    if not isinstance(raw_payload, dict):
        LOGGER.warning("help.registry.invalid_format", path=str(path))
        _registry_cache = {}
        return _registry_cache

    raw_dict = cast(JsonDict, raw_payload)
    registry: dict[str, _RegistryNode] = {}
    for name, entry in raw_dict.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            LOGGER.warning("help.registry.invalid_entry", command=name)
            continue
        node = _build_registry_node([name], cast(JsonDict, entry))
        if node:
            registry[name] = node

    _registry_cache = registry
    return registry


def _build_registry_node(path: list[str], entry: dict[str, Any]) -> _RegistryNode | None:
    try:
        data: HelpData = {
            "name": entry.get("name", " ".join(path)),
            "description": _require_str(entry, "description", path),
            "category": _require_str(entry, "category", path),
            "parameters": _validate_parameters(entry.get("parameters"), path),
            "permissions": _ensure_str_list(entry.get("permissions", [])),
            "examples": _ensure_str_list(entry.get("examples", [])),
            "tags": _ensure_str_list(entry.get("tags", [])),
        }
    except ValueError as exc:
        LOGGER.warning("help.registry.entry_invalid", command=" ".join(path), error=str(exc))
        return None

    subcommands: dict[str, _RegistryNode] = {}
    raw_subs = entry.get("subcommands", {})
    if raw_subs:
        if not isinstance(raw_subs, dict):
            LOGGER.warning(
                "help.registry.subcommands_invalid", command=" ".join(path), subcommands=raw_subs
            )
        else:
            for sub_name, sub_entry in raw_subs.items():
                if not isinstance(sub_name, str) or not isinstance(sub_entry, dict):
                    LOGGER.warning(
                        "help.registry.subcommand_invalid",
                        command=" ".join(path),
                        subcommand=sub_name,
                    )
                    continue
                node = _build_registry_node(path + [sub_name], sub_entry)
                if node:
                    subcommands[sub_name] = node

    return {"data": data, "subcommands": subcommands}


def _require_str(entry: dict[str, Any], field: str, path: list[str]) -> str:
    value = entry.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string ({' '.join(path)})")
    return value.strip()


def _ensure_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if not isinstance(value, list):
        raise ValueError("Expected list of strings")
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result


def _validate_parameters(value: Any, path: list[str]) -> list[HelpParameter]:
    if not value:
        return []
    if not isinstance(value, list):
        raise ValueError("parameters must be a list")
    params: list[HelpParameter] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"parameter {idx} must be a dict")
        name = _require_str(item, "name", path)
        description = _require_str(item, "description", path)
        param_type = _require_str(item, "type", path)
        required = bool(item.get("required", False))
        params.append(
            {
                "name": name,
                "description": description,
                "required": required,
                "type": param_type,
            }
        )
    return params


def _extract_from_command_metadata(
    command: app_commands.Command[Any, Any, Any] | app_commands.Group,
) -> HelpData:
    """Extract basic help data from command metadata as fallback."""
    description = command.description or "無描述"

    # Extract parameters from command

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
