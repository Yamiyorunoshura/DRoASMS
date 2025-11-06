"""Unit tests for help information formatting logic."""

from __future__ import annotations

import pytest

from src.bot.commands.help_data import CollectedHelpData
from src.bot.commands.help_formatter import (
    format_command_detail_embed,
    format_help_list_embed,
)


@pytest.mark.unit
def test_format_grouped_list() -> None:
    """Test that commands are grouped by category."""
    commands = {
        "transfer": CollectedHelpData(
            name="transfer",
            description="轉帳點數",
            category="economy",
            parameters=[],
            permissions=[],
            examples=[],
            tags=[],
            subcommands={},
        ),
        "balance": CollectedHelpData(
            name="balance",
            description="查詢餘額",
            category="economy",
            parameters=[],
            permissions=[],
            examples=[],
            tags=[],
            subcommands={},
        ),
        "council panel": CollectedHelpData(
            name="council panel",
            description="開啟理事會面板",
            category="governance",
            parameters=[],
            permissions=[],
            examples=[],
            tags=[],
            subcommands={},
        ),
    }

    embed = format_help_list_embed(commands)

    assert embed.title == "📚 指令列表"
    # Check that economy commands are in fields (category is translated to Chinese)
    assert any("經濟類" in str(field.name) for field in embed.fields) or any(
        "transfer" in str(field.value).lower() or "balance" in str(field.value).lower()
        for field in embed.fields
    )
    # Check that governance commands are in fields
    assert any("治理類" in str(field.name) for field in embed.fields) or any(
        "council" in str(field.value).lower() for field in embed.fields
    )


@pytest.mark.unit
def test_format_command_detail() -> None:
    """Test detailed command information formatting."""
    command = CollectedHelpData(
        name="transfer",
        description="轉帳虛擬貨幣給其他成員",
        category="economy",
        parameters=[
            {"name": "target", "description": "接收點數的成員", "required": True},
            {"name": "amount", "description": "要轉出的整數點數", "required": True},
            {"name": "reason", "description": "選填備註", "required": False},
        ],
        permissions=[],
        examples=["/transfer @user 100", "/transfer @user 50 生日禮物"],
        tags=[],
        subcommands={},
    )

    embed = format_command_detail_embed(command)

    assert embed.title == "`/transfer`"
    assert embed.description is not None
    assert "轉帳虛擬貨幣" in embed.description
    # Should contain parameter information
    assert any("target" in str(field.name).lower() for field in embed.fields) or any(
        "target" in str(field.value).lower() for field in embed.fields
    )


@pytest.mark.unit
def test_format_with_permissions() -> None:
    """Test that permissions are displayed in detail view."""
    command = CollectedHelpData(
        name="adjust",
        description="管理員調整點數",
        category="economy",
        parameters=[],
        permissions=["administrator", "manage_guild"],
        examples=[],
        tags=[],
        subcommands={},
    )

    embed = format_command_detail_embed(command)

    # Should mention permissions
    assert any("administrator" in str(field.value).lower() for field in embed.fields) or (
        embed.description is not None and "administrator" in embed.description.lower()
    )


@pytest.mark.unit
def test_format_group_with_subcommands() -> None:
    """Test formatting group commands with subcommands."""
    group = CollectedHelpData(
        name="council",
        description="理事會治理指令",
        category="governance",
        parameters=[],
        permissions=[],
        examples=[],
        tags=[],
        subcommands={
            "config_role": CollectedHelpData(
                name="config_role",
                description="設定理事角色",
                category="governance",
                parameters=[],
                permissions=[],
                examples=[],
                tags=[],
                subcommands={},
            ),
            "panel": CollectedHelpData(
                name="panel",
                description="開啟面板",
                category="governance",
                parameters=[],
                permissions=[],
                examples=[],
                tags=[],
                subcommands={},
            ),
        },
    )

    embed = format_command_detail_embed(group)

    assert embed.title is not None
    assert "/council" in embed.title
    # Should list subcommands
    assert any(
        "config_role" in str(field.value).lower() if field.value else False
        for field in embed.fields
    ) or any(
        "panel" in str(field.value).lower() if field.value else False for field in embed.fields
    )


@pytest.mark.unit
def test_embed_field_length_limit() -> None:
    """Test that long descriptions are truncated to fit Discord limits."""
    # Discord embed field value limit is 1024 characters
    long_description = "a" * 2000
    command = CollectedHelpData(
        name="test",
        description=long_description,
        category="general",
        parameters=[],
        permissions=[],
        examples=[],
        tags=[],
        subcommands={},
    )

    embed = format_command_detail_embed(command)

    # All field values should be <= 1024 characters
    for field in embed.fields:
        assert field.value is not None
        assert len(field.value) <= 1024

    # Description should also be truncated if needed (limit 4096)
    if embed.description:
        assert len(embed.description) <= 4096


@pytest.mark.unit
def test_empty_commands_list() -> None:
    """Test formatting empty command list."""
    embed = format_help_list_embed({})

    assert embed.title == "📚 指令列表"
    assert (
        embed.description is not None and "目前沒有可用指令" in embed.description.lower()
    ) or len(embed.fields) == 0


@pytest.mark.unit
def test_command_not_found_message() -> None:
    """Test formatting for command not found case."""
    # This will be handled in the help command itself
    # But we can test that formatter handles missing commands gracefully
    pass
