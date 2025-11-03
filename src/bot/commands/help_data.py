"""Data structures and utilities for command help information."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict


class HelpParameter(TypedDict, total=False):
    """Parameter description for a command."""

    name: str
    description: str
    required: bool


class HelpData(TypedDict, total=False):
    """Standardized help information for a command.

    Commands can provide help data via:
    1. A `get_help_data()` function that returns HelpData
    2. A JSON file in `help_data/` directory
    3. Auto-extracted from command metadata (fallback)
    """

    name: str  # Command name (e.g., "transfer", "council panel")
    description: str  # Brief description
    category: str  # Category tag (e.g., "economy", "governance")
    parameters: list[HelpParameter]  # Parameter descriptions
    permissions: list[str]  # Required permissions (e.g., ["administrator"])
    examples: list[str]  # Usage examples
    tags: list[str]  # Additional tags for grouping/search


@dataclass(frozen=True)
class CollectedHelpData:
    """Collected help data for a command or group."""

    name: str
    description: str
    category: str
    parameters: list[HelpParameter]
    permissions: list[str]
    examples: list[str]
    tags: list[str]
    subcommands: dict[str, CollectedHelpData]  # For groups

    @classmethod
    def from_dict(cls, data: dict[str, Any], name: str | None = None) -> CollectedHelpData:
        """Create CollectedHelpData from a dict (e.g., HelpData)."""
        return cls(
            name=name or data.get("name", ""),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            parameters=data.get("parameters", []),
            permissions=data.get("permissions", []),
            examples=data.get("examples", []),
            tags=data.get("tags", []),
            subcommands={},
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.parameters,
            "permissions": self.permissions,
            "examples": self.examples,
            "tags": self.tags,
            "subcommands": (
                {k: v.to_dict() for k, v in self.subcommands.items()} if self.subcommands else {}
            ),
        }
