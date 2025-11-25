"""Extended unit tests for help_collector module - registry and validation functions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.bot.commands.help_collector import (
    _build_registry_node,
    _dig_help_payload,
    _ensure_str_list,
    _extract_from_command_metadata,
    _extract_help_entry,
    _get_registry_node,
    _load_help_from_registry,
    _load_registry,
    _looks_like_help_data,
    _read_help_file,
    _registry_entry_name,
    _require_str,
    _validate_parameters,
)


class TestLooksLikeHelpData:
    """Test cases for _looks_like_help_data function."""

    @pytest.mark.unit
    def test_non_dict_returns_false(self) -> None:
        """Test that non-dict returns False."""
        assert _looks_like_help_data("string") is False
        assert _looks_like_help_data(123) is False
        assert _looks_like_help_data([1, 2, 3]) is False
        assert _looks_like_help_data(None) is False

    @pytest.mark.unit
    def test_empty_dict_returns_true(self) -> None:
        """Test that empty dict returns True."""
        assert _looks_like_help_data({}) is True

    @pytest.mark.unit
    def test_dict_with_known_keys_returns_true(self) -> None:
        """Test that dict with known help keys returns True."""
        assert _looks_like_help_data({"description": "test"}) is True
        assert _looks_like_help_data({"category": "economy"}) is True
        assert _looks_like_help_data({"parameters": []}) is True
        assert _looks_like_help_data({"permissions": ["admin"]}) is True
        assert _looks_like_help_data({"examples": ["/test"]}) is True
        assert _looks_like_help_data({"tags": ["test"]}) is True

    @pytest.mark.unit
    def test_dict_without_known_keys_returns_false(self) -> None:
        """Test that dict without known keys returns False."""
        assert _looks_like_help_data({"unknown_key": "value"}) is False
        assert _looks_like_help_data({"name": "cmd", "other": "data"}) is False


class TestDigHelpPayload:
    """Test cases for _dig_help_payload function."""

    @pytest.mark.unit
    def test_single_level_path(self) -> None:
        """Test digging with single level path."""
        payload = {
            "transfer": {
                "description": "Transfer command",
                "category": "economy",
            }
        }
        result = _dig_help_payload(payload, ["transfer"])
        assert result is not None
        assert result["description"] == "Transfer command"

    @pytest.mark.unit
    def test_nested_path_via_subcommands(self) -> None:
        """Test digging nested path via subcommands key."""
        payload = {
            "council": {
                "description": "Council group",
                "subcommands": {
                    "panel": {
                        "description": "Panel command",
                        "category": "governance",
                    }
                },
            }
        }
        result = _dig_help_payload(payload, ["council", "panel"])
        assert result is not None
        assert result["description"] == "Panel command"

    @pytest.mark.unit
    def test_direct_nested_path(self) -> None:
        """Test digging direct nested path."""
        payload = {
            "council": {
                "panel": {
                    "description": "Panel command",
                }
            }
        }
        result = _dig_help_payload(payload, ["council", "panel"])
        assert result is not None
        assert result["description"] == "Panel command"

    @pytest.mark.unit
    def test_path_not_found(self) -> None:
        """Test digging with non-existent path."""
        payload = {"transfer": {"description": "Transfer"}}
        result = _dig_help_payload(payload, ["nonexistent"])
        assert result is None

    @pytest.mark.unit
    def test_partial_path_not_found(self) -> None:
        """Test digging with partial path not found."""
        payload = {
            "council": {
                "description": "Council",
            }
        }
        result = _dig_help_payload(payload, ["council", "nonexistent"])
        assert result is None


class TestExtractHelpEntry:
    """Test cases for _extract_help_entry function."""

    @pytest.mark.unit
    def test_payload_looks_like_help_data(self) -> None:
        """Test extracting when payload already looks like help data."""
        payload = {
            "description": "Test command",
            "category": "general",
        }
        result = _extract_help_entry(payload, "test", "")
        assert result is not None
        assert result["description"] == "Test command"

    @pytest.mark.unit
    def test_extract_with_parent_name(self) -> None:
        """Test extracting with parent name."""
        payload = {
            "council": {
                "panel": {
                    "description": "Panel command",
                }
            }
        }
        result = _extract_help_entry(payload, "panel", "council")
        assert result is not None
        assert result["description"] == "Panel command"

    @pytest.mark.unit
    def test_extract_without_parent_fallback(self) -> None:
        """Test extraction falls back to command name without parent."""
        payload = {
            "panel": {
                "description": "Panel command",
            }
        }
        result = _extract_help_entry(payload, "panel", "council")
        assert result is not None
        assert result["description"] == "Panel command"


class TestReadHelpFile:
    """Test cases for _read_help_file function."""

    @pytest.mark.unit
    def test_file_not_exists(self) -> None:
        """Test reading non-existent file."""
        with patch.object(Path, "exists", return_value=False):
            result = _read_help_file(Path("nonexistent.json"))
            assert result is None

    @pytest.mark.unit
    def test_file_read_error(self) -> None:
        """Test handling file read error."""
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", side_effect=IOError("Read error")),
        ):
            result = _read_help_file(Path("error.json"))
            assert result is None

    @pytest.mark.unit
    def test_invalid_json(self) -> None:
        """Test handling invalid JSON."""
        mock_file = mock_open(read_data="invalid json")
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_file),
        ):
            result = _read_help_file(Path("invalid.json"))
            assert result is None

    @pytest.mark.unit
    def test_non_dict_json(self) -> None:
        """Test handling non-dict JSON."""
        mock_file = mock_open(read_data='["array", "data"]')
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_file),
        ):
            result = _read_help_file(Path("array.json"))
            assert result is None

    @pytest.mark.unit
    def test_valid_json_file(self) -> None:
        """Test reading valid JSON file."""
        test_data = {"description": "Test", "category": "general"}
        mock_file = mock_open(read_data=json.dumps(test_data))
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_file),
        ):
            result = _read_help_file(Path("valid.json"))
            assert result is not None
            assert result["description"] == "Test"


class TestRequireStr:
    """Test cases for _require_str function."""

    @pytest.mark.unit
    def test_valid_string(self) -> None:
        """Test with valid string."""
        entry = {"name": "test", "description": "Test description"}
        result = _require_str(entry, "description", ["test"])
        assert result == "Test description"

    @pytest.mark.unit
    def test_whitespace_only_raises(self) -> None:
        """Test that whitespace-only string raises ValueError."""
        entry = {"description": "   "}
        with pytest.raises(ValueError, match="description must be a non-empty string"):
            _require_str(entry, "description", ["test"])

    @pytest.mark.unit
    def test_missing_field_raises(self) -> None:
        """Test that missing field raises ValueError."""
        entry = {"name": "test"}
        with pytest.raises(ValueError, match="description must be a non-empty string"):
            _require_str(entry, "description", ["test"])

    @pytest.mark.unit
    def test_non_string_raises(self) -> None:
        """Test that non-string value raises ValueError."""
        entry = {"description": 123}
        with pytest.raises(ValueError, match="description must be a non-empty string"):
            _require_str(entry, "description", ["test"])


class TestEnsureStrList:
    """Test cases for _ensure_str_list function."""

    @pytest.mark.unit
    def test_none_returns_empty_list(self) -> None:
        """Test that None returns empty list."""
        assert _ensure_str_list(None) == []

    @pytest.mark.unit
    def test_valid_string_list(self) -> None:
        """Test with valid string list."""
        result = _ensure_str_list(["a", "b", "c"])
        assert result == ["a", "b", "c"]

    @pytest.mark.unit
    def test_filters_empty_strings(self) -> None:
        """Test that empty strings are filtered out."""
        result = _ensure_str_list(["a", "", "  ", "b"])
        assert result == ["a", "b"]

    @pytest.mark.unit
    def test_strips_whitespace(self) -> None:
        """Test that strings are stripped."""
        result = _ensure_str_list(["  a  ", "b  "])
        assert result == ["a", "b"]

    @pytest.mark.unit
    def test_non_list_raises(self) -> None:
        """Test that non-list raises ValueError."""
        with pytest.raises(ValueError, match="Expected list of strings"):
            _ensure_str_list("not a list")

    @pytest.mark.unit
    def test_filters_non_string_items(self) -> None:
        """Test that non-string items are filtered out."""
        result = _ensure_str_list(["a", 123, "b", None])
        assert result == ["a", "b"]


class TestValidateParameters:
    """Test cases for _validate_parameters function."""

    @pytest.mark.unit
    def test_none_returns_empty_list(self) -> None:
        """Test that None returns empty list."""
        assert _validate_parameters(None, ["test"]) == []

    @pytest.mark.unit
    def test_non_list_raises(self) -> None:
        """Test that non-list raises ValueError."""
        with pytest.raises(ValueError, match="parameters must be a list"):
            _validate_parameters("not a list", ["test"])

    @pytest.mark.unit
    def test_non_dict_item_raises(self) -> None:
        """Test that non-dict item raises ValueError."""
        with pytest.raises(ValueError, match="parameter 0 must be a dict"):
            _validate_parameters(["not a dict"], ["test"])

    @pytest.mark.unit
    def test_valid_parameters(self) -> None:
        """Test with valid parameters."""
        params = [
            {
                "name": "amount",
                "description": "Amount to transfer",
                "type": "int",
                "required": True,
            },
            {
                "name": "reason",
                "description": "Transfer reason",
                "type": "str",
                "required": False,
            },
        ]
        result = _validate_parameters(params, ["test"])
        assert len(result) == 2
        assert result[0]["name"] == "amount"
        assert result[0]["required"] is True
        assert result[1]["name"] == "reason"
        assert result[1]["required"] is False


class TestRegistryEntryName:
    """Test cases for _registry_entry_name function."""

    @pytest.mark.unit
    def test_uses_entry_name_if_present(self) -> None:
        """Test that entry name is used if present."""
        entry = {"name": "custom_name", "description": "Test"}
        result = _registry_entry_name(entry, ["path", "parts"])
        assert result == "custom_name"

    @pytest.mark.unit
    def test_uses_path_if_no_name(self) -> None:
        """Test that path is used if no name in entry."""
        entry = {"description": "Test"}
        result = _registry_entry_name(entry, ["council", "panel"])
        assert result == "council panel"

    @pytest.mark.unit
    def test_strips_whitespace_from_name(self) -> None:
        """Test that name is stripped of whitespace."""
        entry = {"name": "  spaced_name  "}
        result = _registry_entry_name(entry, ["path"])
        assert result == "spaced_name"


class TestBuildRegistryNode:
    """Test cases for _build_registry_node function."""

    @pytest.mark.unit
    def test_valid_entry(self) -> None:
        """Test building node from valid entry."""
        entry = {
            "description": "Test command",
            "category": "general",
            "parameters": [],
            "permissions": ["admin"],
            "examples": ["/test"],
            "tags": ["test"],
        }
        result = _build_registry_node(["test"], entry)
        assert result is not None
        assert result["data"]["name"] == "test"
        assert result["data"]["description"] == "Test command"
        assert result["data"]["category"] == "general"

    @pytest.mark.unit
    def test_invalid_entry_returns_none(self) -> None:
        """Test that invalid entry returns None."""
        entry = {
            "description": "",  # Empty description should fail
            "category": "general",
        }
        result = _build_registry_node(["test"], entry)
        assert result is None

    @pytest.mark.unit
    def test_with_subcommands(self) -> None:
        """Test building node with subcommands."""
        entry = {
            "description": "Group command",
            "category": "governance",
            "subcommands": {
                "sub1": {
                    "description": "Subcommand 1",
                    "category": "governance",
                }
            },
        }
        result = _build_registry_node(["council"], entry)
        assert result is not None
        assert "sub1" in result["subcommands"]
        assert result["subcommands"]["sub1"]["data"]["description"] == "Subcommand 1"

    @pytest.mark.unit
    def test_invalid_subcommands_type(self) -> None:
        """Test handling invalid subcommands type."""
        entry = {
            "description": "Test",
            "category": "general",
            "subcommands": "not a dict",
        }
        result = _build_registry_node(["test"], entry)
        assert result is not None
        assert result["subcommands"] == {}

    @pytest.mark.unit
    def test_invalid_subcommand_entry(self) -> None:
        """Test handling invalid subcommand entry."""
        entry = {
            "description": "Test",
            "category": "general",
            "subcommands": {
                "invalid_sub": "not a dict",
            },
        }
        result = _build_registry_node(["test"], entry)
        assert result is not None
        assert "invalid_sub" not in result["subcommands"]


class TestLoadRegistry:
    """Test cases for _load_registry function."""

    @pytest.mark.unit
    def test_missing_file(self) -> None:
        """Test handling missing registry file."""
        import src.bot.commands.help_collector as hc

        # Clear cache
        hc._registry_cache = None

        with patch.object(Path, "exists", return_value=False):
            result = _load_registry()
            assert result == {}

        # Clear cache after test
        hc._registry_cache = None

    @pytest.mark.unit
    def test_cache_hit(self) -> None:
        """Test that cached registry is returned."""
        import src.bot.commands.help_collector as hc

        test_cache = {"test": {"data": {}, "subcommands": {}}}
        hc._registry_cache = test_cache

        result = _load_registry()
        assert result == test_cache

        # Clear cache after test
        hc._registry_cache = None


class TestGetRegistryNode:
    """Test cases for _get_registry_node function."""

    @pytest.mark.unit
    def test_empty_name(self) -> None:
        """Test with empty name."""
        result = _get_registry_node("")
        assert result is None

    @pytest.mark.unit
    def test_single_level_name(self) -> None:
        """Test getting single level command."""
        import src.bot.commands.help_collector as hc

        test_node = {
            "data": {"name": "test", "description": "Test"},
            "subcommands": {},
        }
        hc._registry_cache = {"test": test_node}

        result = _get_registry_node("test")
        assert result == test_node

        hc._registry_cache = None

    @pytest.mark.unit
    def test_nested_name(self) -> None:
        """Test getting nested command."""
        import src.bot.commands.help_collector as hc

        sub_node = {
            "data": {"name": "council panel", "description": "Panel"},
            "subcommands": {},
        }
        hc._registry_cache = {
            "council": {
                "data": {"name": "council"},
                "subcommands": {"panel": sub_node},
            }
        }

        result = _get_registry_node("council panel")
        assert result == sub_node

        hc._registry_cache = None


class TestLoadHelpFromRegistry:
    """Test cases for _load_help_from_registry function."""

    @pytest.mark.unit
    def test_found_command(self) -> None:
        """Test loading help data for existing command."""
        import src.bot.commands.help_collector as hc

        hc._registry_cache = {
            "transfer": {
                "data": {
                    "name": "transfer",
                    "description": "Transfer command",
                    "category": "economy",
                },
                "subcommands": {},
            }
        }

        result = _load_help_from_registry("transfer")
        assert result is not None
        assert result["name"] == "transfer"
        assert result["description"] == "Transfer command"

        hc._registry_cache = None

    @pytest.mark.unit
    def test_not_found_command(self) -> None:
        """Test loading help data for non-existing command."""
        import src.bot.commands.help_collector as hc

        hc._registry_cache = {}

        result = _load_help_from_registry("nonexistent")
        assert result is None

        hc._registry_cache = None


class TestExtractFromCommandMetadata:
    """Test cases for _extract_from_command_metadata function."""

    @pytest.mark.unit
    def test_command_with_description(self) -> None:
        """Test extracting metadata from command with description."""
        from discord import app_commands

        command = MagicMock(spec=app_commands.Command)
        command.name = "test_cmd"
        command.description = "Test command description"

        result = _extract_from_command_metadata(command)

        assert result["name"] == "test_cmd"
        assert result["description"] == "Test command description"
        assert result["category"] == "general"

    @pytest.mark.unit
    def test_command_without_description(self) -> None:
        """Test extracting metadata from command without description."""
        from discord import app_commands

        command = MagicMock(spec=app_commands.Command)
        command.name = "test_cmd"
        command.description = None

        result = _extract_from_command_metadata(command)

        assert result["name"] == "test_cmd"
        assert result["description"] == "無描述"

    @pytest.mark.unit
    def test_group_command(self) -> None:
        """Test extracting metadata from group command."""
        from discord import app_commands

        group = MagicMock(spec=app_commands.Group)
        group.name = "test_group"
        group.description = "Test group"

        result = _extract_from_command_metadata(group)

        assert result["name"] == "test_group"
        assert result["description"] == "Test group"
