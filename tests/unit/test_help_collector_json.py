"""Unit tests for help_collector JSON registry functionality."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

from src.bot.commands.help_collector import _load_help_json


class TestHelpCollectorJSON:
    """Test cases for JSON-based help registry."""

    def test_load_help_json_file_not_found(self) -> None:
        """Test loading help data when file doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            result = _load_help_json("nonexistent", "")
            assert result is None

    def test_load_help_json_invalid_json(self) -> None:
        """Test loading help data with invalid JSON."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open") as mock_open,
        ):
            mock_file = Mock()
            mock_file.read.return_value = "invalid json"
            mock_open.return_value.__enter__.return_value = mock_file

            result = _load_help_json("invalid", "")
            assert result is None

    def test_load_help_json_valid_data(self) -> None:
        """Test loading valid help data."""
        test_data = {
            "name": "test",
            "description": "Test command",
            "category": "general",
            "parameters": [],
            "permissions": [],
            "examples": ["/test"],
            "tags": ["test"],
        }

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open") as mock_open,
        ):
            mock_file = Mock()
            mock_file.read.return_value = json.dumps(test_data)
            mock_open.return_value.__enter__.return_value = mock_file

            result = _load_help_json("test", "")
            assert result is not None
            assert result["name"] == "test"
            assert result["description"] == "Test command"
            assert result["category"] == "general"

    def test_load_help_json_subcommand(self) -> None:
        """Test loading help data for a subcommand."""
        test_data = {
            "name": "panel",
            "description": "Panel command",
            "category": "governance",
            "parameters": [],
            "permissions": ["administrator"],
            "examples": ["/council panel"],
            "tags": ["panel"],
        }

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open") as mock_open,
        ):
            mock_file = Mock()
            mock_file.read.return_value = json.dumps(test_data)
            mock_open.return_value.__enter__.return_value = mock_file

            result = _load_help_json("panel", "council")
            assert result is not None
            assert result["name"] == "panel"
            assert result["description"] == "Panel command"
            assert "administrator" in result["permissions"]

    def test_load_help_json_with_optional_fields(self) -> None:
        """Test loading help data with all optional fields."""
        test_data = {
            "name": "complete",
            "description": "Complete command with all fields",
            "category": "economy",
            "parameters": [
                {"name": "amount", "description": "Amount to transfer", "required": True}
            ],
            "permissions": ["administrator"],
            "examples": ["/complete 100", "/complete 100 @user"],
            "tags": ["economy", "transfer"],
        }

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open") as mock_open,
        ):
            mock_file = Mock()
            mock_file.read.return_value = json.dumps(test_data)
            mock_open.return_value.__enter__.return_value = mock_file

            result = _load_help_json("complete", "")
            assert result is not None
            assert result["name"] == "complete"
            assert len(result["parameters"]) == 1
            assert result["parameters"][0]["name"] == "amount"
            assert "administrator" in result["permissions"]
            assert len(result["examples"]) == 2
            assert "economy" in result["tags"]

    def test_load_help_json_empty_data(self) -> None:
        """Test loading empty help data."""
        test_data = {}

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open") as mock_open,
        ):
            mock_file = Mock()
            mock_file.read.return_value = json.dumps(test_data)
            mock_open.return_value.__enter__.return_value = mock_file

            result = _load_help_json("empty", "")
            assert result is not None
            assert result == test_data

    def test_load_help_json_partial_data(self) -> None:
        """Test loading help data with partial fields."""
        test_data = {"name": "partial", "description": "Partial command"}

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open") as mock_open,
        ):
            mock_file = Mock()
            mock_file.read.return_value = json.dumps(test_data)
            mock_open.return_value.__enter__.return_value = mock_file

            result = _load_help_json("partial", "")
            assert result is not None
            assert result["name"] == "partial"
            assert result["description"] == "Partial command"
