"""Simple contract tests for State Council Discord commands."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from discord import app_commands

from src.bot.commands.state_council import build_state_council_group
from src.db.gateway.state_council_governance import StateCouncilConfig


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


class _StubInteraction:
    """Stub Discord Interaction for testing."""

    def __init__(
        self,
        *,
        guild_id: int | None,
        user_id: int,
        is_admin: bool = False,
        manage_guild: bool = False,
    ) -> None:
        self.guild_id = guild_id
        self.user = _StubUser(id=user_id)
        self.response_sent = False
        self.response_data: dict[str, object] | None = None
        self.guild: _StubGuild | None = _StubGuild(id=guild_id) if guild_id is not None else None
        self._is_admin = is_admin
        self._manage_guild = manage_guild

    @property
    def guild_permissions(self) -> _StubPermissions:
        return _StubPermissions(administrator=self._is_admin, manage_guild=self._manage_guild)

    async def response_send_message(self, content: str, *, ephemeral: bool = False) -> None:
        self.response_sent = True
        self.response_data = {"content": content, "ephemeral": ephemeral}


class _StubUser:
    def __init__(self, *, id: int) -> None:
        self.id = id


class _StubGuild:
    def __init__(self, *, id: int) -> None:
        self.id = id

    def get_member(self, user_id: int) -> _StubMember | None:
        return _StubMember(id=user_id, display_name=f"User{user_id}")


class _StubMember:
    def __init__(self, *, id: int, display_name: str) -> None:
        self.id = id
        self.display_name = display_name

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


class _StubRole:
    def __init__(self, *, id: int, name: str) -> None:
        self.id = id
        self.name = name

    @property
    def mention(self) -> str:
        return f"<@&{self.id}>"


class _StubPermissions:
    def __init__(self, *, administrator: bool, manage_guild: bool) -> None:
        self.administrator = administrator
        self.manage_guild = manage_guild


def test_state_council_command_group_structure() -> None:
    """Test State Council command group structure."""
    service = AsyncMock()
    command = build_state_council_group(service)

    # Verify command group
    assert command.name == "state_council"
    assert "國務院治理指令" in command.description
    assert isinstance(command, app_commands.Group)

    # Verify subcommands exist
    subcommands = list(command.walk_commands())
    subcommand_names = [cmd.name for cmd in subcommands]

    assert "config_leader" in subcommand_names
    assert "panel" in subcommand_names


def test_state_council_config_leader_command_structure() -> None:
    """Test config_leader command structure."""
    service = AsyncMock()
    command = build_state_council_group(service)

    # Find the config_leader command
    config_leader_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "config_leader":
            config_leader_cmd = cmd
            break

    assert config_leader_cmd is not None
    cmd_typed = cast(Any, config_leader_cmd)
    assert cmd_typed.name == "config_leader"
    assert "設定國務院領袖" in cmd_typed.description

    # Check parameters
    param_names = [param.name for param in cmd_typed.parameters]
    assert "leader" in param_names
    assert "leader_role" in param_names

    # Verify parameters are optional
    leader_param = next(p for p in cmd_typed.parameters if p.name == "leader")
    leader_role_param = next(p for p in cmd_typed.parameters if p.name == "leader_role")
    assert leader_param.required is False
    assert leader_role_param.required is False


def test_state_council_panel_command_structure() -> None:
    """Test panel command structure."""
    service = AsyncMock()
    command = build_state_council_group(service)

    # Find the panel command
    panel_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "panel":
            panel_cmd = cmd
            break

    assert panel_cmd is not None
    panel_typed = cast(Any, panel_cmd)
    assert panel_typed.name == "panel"
    assert "開啟國務院面板" in panel_typed.description
    assert len(panel_typed.parameters) == 0  # No parameters required


@pytest.mark.asyncio
async def test_config_leader_admin_permission_required() -> None:
    """Test config_leader command requires admin permissions."""
    service = AsyncMock()
    command = build_state_council_group(service)

    # Find the config_leader command
    config_leader_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "config_leader":
            config_leader_cmd = cmd
            break

    # Test with non-admin user
    interaction = _StubInteraction(guild_id=_snowflake(), user_id=_snowflake(), is_admin=False)
    leader_member = _StubMember(id=_snowflake(), display_name="TestLeader")

    assert config_leader_cmd is not None
    await cast(Any, config_leader_cmd).callback(interaction, leader_member, None)

    assert interaction.response_sent
    assert interaction.response_data is not None
    content = cast(str, interaction.response_data["content"])
    assert "需要管理員或管理伺服器權限" in content
    assert not service.set_config.called


@pytest.mark.asyncio
async def test_config_leader_guild_required() -> None:
    """Test config_leader command requires guild context."""
    service = AsyncMock()
    command = build_state_council_group(service)

    # Find the config_leader command
    config_leader_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "config_leader":
            config_leader_cmd = cmd
            break

    # Test without guild
    interaction = _StubInteraction(guild_id=None, user_id=_snowflake(), is_admin=True)

    assert config_leader_cmd is not None
    await cast(Any, config_leader_cmd).callback(interaction, None, None)

    assert interaction.response_sent
    assert interaction.response_data is not None
    content = cast(str, interaction.response_data["content"])
    assert "本指令需在伺服器中執行" in content
    assert not service.set_config.called


@pytest.mark.asyncio
async def test_config_leader_neither_leader_nor_role_provided() -> None:
    """Test config_leader command requires either leader or role."""
    service = AsyncMock()
    command = build_state_council_group(service)

    # Find the config_leader command
    config_leader_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "config_leader":
            config_leader_cmd = cmd
            break

    # Test with neither leader nor role
    interaction = _StubInteraction(guild_id=_snowflake(), user_id=_snowflake(), is_admin=True)

    assert config_leader_cmd is not None
    await cast(Any, config_leader_cmd).callback(interaction, None, None)

    assert interaction.response_sent
    assert interaction.response_data is not None
    content = cast(str, interaction.response_data["content"])
    assert "必須指定一位使用者或一個身分組" in content
    assert not service.set_config.called


@pytest.mark.asyncio
async def test_config_leader_success_with_user() -> None:
    """Test successful config_leader with user."""
    guild_id = _snowflake()
    admin_id = _snowflake()
    leader_id = _snowflake()

    service = AsyncMock()
    expected_config = StateCouncilConfig(
        guild_id=guild_id,
        leader_id=leader_id,
        leader_role_id=None,
        internal_affairs_account_id=9500000000000001,
        finance_account_id=9500000000000002,
        security_account_id=9500000000000003,
        central_bank_account_id=9500000000000004,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    service.set_config.return_value = expected_config

    command = build_state_council_group(service)

    # Find the config_leader command
    config_leader_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "config_leader":
            config_leader_cmd = cmd
            break

    # Mock background scheduler
    with patch("src.bot.commands.state_council._install_background_scheduler"):
        interaction = _StubInteraction(guild_id=guild_id, user_id=admin_id, is_admin=True)
        leader_member = _StubMember(id=leader_id, display_name="TestLeader")

        assert config_leader_cmd is not None
        await cast(Any, config_leader_cmd).callback(interaction, leader_member, None)

        service.set_config.assert_called_once_with(
            guild_id=guild_id,
            leader_id=leader_id,
            leader_role_id=None,
        )
        assert interaction.response_sent


@pytest.mark.asyncio
async def test_config_leader_success_with_role() -> None:
    """Test successful config_leader with role."""
    guild_id = _snowflake()
    admin_id = _snowflake()
    leader_role_id = _snowflake()

    service = AsyncMock()
    expected_config = StateCouncilConfig(
        guild_id=guild_id,
        leader_id=None,
        leader_role_id=leader_role_id,
        internal_affairs_account_id=9500000000000001,
        finance_account_id=9500000000000002,
        security_account_id=9500000000000003,
        central_bank_account_id=9500000000000004,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    service.set_config.return_value = expected_config

    command = build_state_council_group(service)

    # Find the config_leader command
    config_leader_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "config_leader":
            config_leader_cmd = cmd
            break

    # Mock background scheduler
    with patch("src.bot.commands.state_council._install_background_scheduler"):
        interaction = _StubInteraction(guild_id=guild_id, user_id=admin_id, is_admin=True)
        leader_role = _StubRole(id=leader_role_id, name="Council Leader")

        assert config_leader_cmd is not None
        await cast(Any, config_leader_cmd).callback(interaction, None, leader_role)

        service.set_config.assert_called_once_with(
            guild_id=guild_id,
            leader_id=None,
            leader_role_id=leader_role_id,
        )
        assert interaction.response_sent


@pytest.mark.asyncio
async def test_panel_command_not_configured() -> None:
    """Test panel command when State Council is not configured."""
    service = AsyncMock()
    service.get_config.side_effect = Exception("Not configured")

    command = build_state_council_group(service)

    # Find the panel command
    panel_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "panel":
            panel_cmd = cmd
            break

    interaction = _StubInteraction(guild_id=_snowflake(), user_id=_snowflake())

    assert panel_cmd is not None
    await cast(Any, panel_cmd).callback(interaction)

    assert interaction.response_sent
    # Should contain error message about configuration


@pytest.mark.asyncio
async def test_panel_command_guild_required() -> None:
    """Test panel command requires guild context."""
    service = AsyncMock()
    command = build_state_council_group(service)

    # Find the panel command
    panel_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "panel":
            panel_cmd = cmd
            break

    # Test without guild
    interaction = _StubInteraction(guild_id=None, user_id=_snowflake())

    assert panel_cmd is not None
    await cast(Any, panel_cmd).callback(interaction)

    assert interaction.response_sent
    assert interaction.response_data is not None
    content = cast(str, interaction.response_data["content"])
    assert "本指令需在伺服器中執行" in content


@pytest.mark.asyncio
async def test_config_leader_error_handling() -> None:
    """Test config_leader command error handling."""
    service = AsyncMock()
    service.set_config.side_effect = Exception("Database error")

    command = build_state_council_group(service)

    # Find the config_leader command
    config_leader_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "config_leader":
            config_leader_cmd = cmd
            break

    # Mock background scheduler
    with patch("src.bot.commands.state_council._install_background_scheduler"):
        interaction = _StubInteraction(guild_id=_snowflake(), user_id=_snowflake(), is_admin=True)
        leader_member = _StubMember(id=_snowflake(), display_name="TestLeader")

        assert config_leader_cmd is not None
        await cast(Any, config_leader_cmd).callback(interaction, leader_member, None)

        assert interaction.response_sent
        assert interaction.response_data is not None
        content = cast(str, interaction.response_data["content"])
        assert "設定失敗，請稍後再試" in content
        assert interaction.response_data["ephemeral"] is True


def test_register_function_exists() -> None:
    """Test that register function exists and can be called."""
    from discord import app_commands

    from src.bot.commands.state_council import register

    # Create a mock tree
    mock_tree = AsyncMock(spec=app_commands.CommandTree)
    mock_client = AsyncMock()
    mock_tree.client = mock_client

    # Mock background scheduler and StateCouncilService
    with patch("src.bot.commands.state_council._install_background_scheduler") as mock_scheduler:
        with patch("src.bot.commands.state_council.StateCouncilService") as mock_service:
            register(mock_tree)

            # Verify tree.add_command was called
            mock_tree.add_command.assert_called_once()

            # Verify scheduler was installed
            mock_scheduler.assert_called_once_with(mock_client, mock_service.return_value)
