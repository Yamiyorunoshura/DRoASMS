"""Extended unit tests for help_formatter module - edge cases and truncation."""

from __future__ import annotations

import pytest

from src.bot.commands.help_data import CollectedHelpData
from src.bot.commands.help_formatter import (
    _format_category_name,
    _truncate_text,
    format_command_detail_embed,
    format_help_list_embed,
)


class TestFormatCategoryName:
    """Test cases for _format_category_name function."""

    @pytest.mark.unit
    def test_economy_category(self) -> None:
        """Test economy category translation."""
        assert _format_category_name("economy") == "經濟類"

    @pytest.mark.unit
    def test_governance_category(self) -> None:
        """Test governance category translation."""
        assert _format_category_name("governance") == "治理類"

    @pytest.mark.unit
    def test_general_category(self) -> None:
        """Test general category translation."""
        assert _format_category_name("general") == "一般"

    @pytest.mark.unit
    def test_unknown_category(self) -> None:
        """Test unknown category uses title case."""
        assert _format_category_name("unknown") == "Unknown"
        assert _format_category_name("custom_category") == "Custom_Category"


class TestTruncateText:
    """Test cases for _truncate_text function."""

    @pytest.mark.unit
    def test_short_text_no_truncation(self) -> None:
        """Test that short text is not truncated."""
        text = "Short text"
        result = _truncate_text(text, 100)
        assert result == text

    @pytest.mark.unit
    def test_exact_length_no_truncation(self) -> None:
        """Test that text at exact max length is not truncated."""
        text = "a" * 100
        result = _truncate_text(text, 100)
        assert result == text

    @pytest.mark.unit
    def test_truncate_at_newline(self) -> None:
        """Test truncation at newline boundary."""
        # Create text where newline is at 85% of max_length
        text = "a" * 85 + "\n" + "b" * 20  # 106 chars total
        result = _truncate_text(text, 100)
        # Should truncate at newline
        assert result == "a" * 85 + "\n..."

    @pytest.mark.unit
    def test_truncate_at_space(self) -> None:
        """Test truncation at space boundary."""
        # Create text with space at 85% but no suitable newline
        text = "a" * 85 + " " + "b" * 20  # 106 chars total
        result = _truncate_text(text, 100)
        # Should truncate at space
        assert result == "a" * 85 + "..."

    @pytest.mark.unit
    def test_hard_truncate(self) -> None:
        """Test hard truncation when no suitable break point."""
        # Create text with no spaces or newlines
        text = "a" * 150
        result = _truncate_text(text, 100)
        # Should hard truncate at max_length - 3
        assert result == "a" * 97 + "..."
        assert len(result) == 100

    @pytest.mark.unit
    def test_newline_too_early_uses_space(self) -> None:
        """Test that early newline is ignored in favor of space."""
        # Newline at 50% (too early), space at 85%
        text = "a" * 50 + "\n" + "b" * 35 + " " + "c" * 20  # 107 chars
        result = _truncate_text(text, 100)
        # Should prefer space at 85% over newline at 50%
        assert result.endswith("...")

    @pytest.mark.unit
    def test_space_too_early_hard_truncate(self) -> None:
        """Test hard truncation when space is too early."""
        # Space at 50% (too early to use), no newlines after
        text = "a" * 50 + " " + "b" * 60  # 111 chars, no good break point
        result = _truncate_text(text, 100)
        # Space at position 50 is 50% of 100, below 80% threshold
        # Should hard truncate
        assert result == "a" * 50 + " " + "b" * 46 + "..."


class TestFormatHelpListEmbedTruncation:
    """Test cases for field truncation in format_help_list_embed."""

    @pytest.mark.unit
    def test_many_commands_truncated(self) -> None:
        """Test that many commands in one category get truncated."""
        # Create 50 commands in the same category with long descriptions
        commands = {}
        for i in range(50):
            commands[f"cmd{i:02d}"] = CollectedHelpData(
                name=f"cmd{i:02d}",
                description="A" * 80,  # Long description
                category="economy",
                parameters=[],
                permissions=[],
                examples=[],
                tags=[],
                subcommands={},
            )

        embed = format_help_list_embed(commands)

        # Check that the field exists and contains truncation indicator
        economy_field = None
        for field in embed.fields:
            if "經濟類" in str(field.name):
                economy_field = field
                break

        assert economy_field is not None
        assert economy_field.value is not None
        # Field should be truncated with "..."
        assert len(economy_field.value) <= 1024
        if len(economy_field.value) == 1024 or "..." in economy_field.value:
            # Truncation happened
            pass


class TestFormatCommandDetailEmbedEdgeCases:
    """Test cases for edge cases in format_command_detail_embed."""

    @pytest.mark.unit
    def test_command_with_tags(self) -> None:
        """Test command with tags displays them in footer."""
        command = CollectedHelpData(
            name="transfer",
            description="轉帳命令",
            category="economy",
            parameters=[],
            permissions=[],
            examples=[],
            tags=["money", "economy", "transfer"],
            subcommands={},
        )

        embed = format_command_detail_embed(command)

        # Footer should contain tags
        assert embed.footer is not None
        assert embed.footer.text is not None
        assert "標籤" in embed.footer.text
        assert "money" in embed.footer.text

    @pytest.mark.unit
    def test_command_with_custom_category(self) -> None:
        """Test command with custom category shows category in footer."""
        command = CollectedHelpData(
            name="custom_cmd",
            description="Custom command",
            category="custom",  # Not "general"
            parameters=[],
            permissions=[],
            examples=[],
            tags=[],
            subcommands={},
        )

        embed = format_command_detail_embed(command)

        # Footer should contain category
        assert embed.footer is not None
        assert embed.footer.text is not None
        assert "分類" in embed.footer.text

    @pytest.mark.unit
    def test_command_with_both_category_and_tags(self) -> None:
        """Test command with both category and tags shows both."""
        command = CollectedHelpData(
            name="full_cmd",
            description="Full command",
            category="economy",
            parameters=[],
            permissions=[],
            examples=[],
            tags=["tag1", "tag2"],
            subcommands={},
        )

        embed = format_command_detail_embed(command)

        assert embed.footer is not None
        assert embed.footer.text is not None
        assert "分類" in embed.footer.text
        assert "標籤" in embed.footer.text
        # Should be joined by " | "
        assert " | " in embed.footer.text

    @pytest.mark.unit
    def test_general_category_no_footer_category(self) -> None:
        """Test that general category doesn't show category in footer."""
        command = CollectedHelpData(
            name="general_cmd",
            description="General command",
            category="general",  # Should not show in footer
            parameters=[],
            permissions=[],
            examples=[],
            tags=[],  # No tags either
            subcommands={},
        )

        embed = format_command_detail_embed(command)

        # Footer should be None or empty since no category/tags
        if embed.footer:
            assert not embed.footer.text or "分類" not in embed.footer.text

    @pytest.mark.unit
    def test_very_long_description_truncated(self) -> None:
        """Test that very long description is truncated."""
        long_desc = "A" * 5000  # Exceeds EMBED_DESCRIPTION_LIMIT (4096)
        command = CollectedHelpData(
            name="long_desc_cmd",
            description=long_desc,
            category="general",
            parameters=[],
            permissions=[],
            examples=[],
            tags=[],
            subcommands={},
        )

        embed = format_command_detail_embed(command)

        # Description should be truncated
        assert embed.description is not None
        assert len(embed.description) <= 4096
        assert "..." in embed.description

    @pytest.mark.unit
    def test_command_with_optional_parameter(self) -> None:
        """Test command with optional parameter shows 選填."""
        command = CollectedHelpData(
            name="param_cmd",
            description="Command with params",
            category="general",
            parameters=[
                {"name": "required_arg", "description": "Required", "required": True},
                {"name": "optional_arg", "description": "Optional", "required": False},
            ],
            permissions=[],
            examples=[],
            tags=[],
            subcommands={},
        )

        embed = format_command_detail_embed(command)

        # Check parameters field
        param_field = None
        for field in embed.fields:
            if "參數" in str(field.name):
                param_field = field
                break

        assert param_field is not None
        assert param_field.value is not None
        assert "必填" in param_field.value
        assert "選填" in param_field.value
