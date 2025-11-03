"""Contract tests for State Council Discord commands."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from discord import AppCommandOptionType, Interaction

from src.bot.commands.state_council import build_state_council_group
from src.bot.services.state_council_service import (
    StateCouncilNotConfiguredError,
    StateCouncilService,
)
from src.db.gateway.state_council_governance import StateCouncilConfig


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


class _StubInteraction:
    """Stub Discord Interaction for testing."""

    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        is_admin: bool = False,
        manage_guild: bool = False,
    ) -> None:
        self.guild_id = guild_id
        self.user = SimpleNamespace(id=user_id, roles=[])
        self.guild = SimpleNamespace(get_member=lambda uid: None)
        self.response_sent = False
        self.response_data: dict[str, object] | None = None
        # store flags for permission property
        self._is_admin = is_admin
        self._manage_guild = manage_guild

    @property
    def guild_permissions(self) -> SimpleNamespace:
        return SimpleNamespace(
            administrator=self._is_admin,
            manage_guild=self._manage_guild,
        )

    async def response_send_message(self, content: str, *, ephemeral: bool = False) -> None:
        self.response_sent = True
        self.response_data = {"content": content, "ephemeral": ephemeral}

    async def response_edit_message(self, *, embed: Any = None, view: Any = None) -> None:
        self.response_sent = True
        self.response_data = {"embed": embed, "view": view}

    async def response_send_modal(self, modal: Any) -> None:
        self.response_sent = True
        self.response_data = {"modal": modal}

    async def original_response(self) -> SimpleNamespace:
        return SimpleNamespace(id=_snowflake())


class _StubMember(SimpleNamespace):
    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


class _StubRole(SimpleNamespace):
    @property
    def mention(self) -> str:
        return f"<@&{self.id}>"


@pytest.mark.asyncio
async def test_state_council_config_leader_command_contract() -> None:
    """Test state council config leader command structure and behavior."""
    guild_id = _snowflake()
    admin_id = _snowflake()
    leader_id = _snowflake()
    leader_role_id = _snowflake()

    service = AsyncMock(spec=StateCouncilService)
    expected_config = StateCouncilConfig(
        guild_id=guild_id,
        leader_id=leader_id,
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
    assert command.name == "state_council"
    assert "國務院治理指令" in command.description

    # Find the config_leader command
    _config_leader_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "config_leader":
            _config_leader_cmd = cmd
            break

    assert _config_leader_cmd is not None
    _cfg_cmd = cast(Any, _config_leader_cmd)
    assert _cfg_cmd.name == "config_leader"
    assert "設定國務院領袖" in _cfg_cmd.description

    # Check parameters
    param_names = [param.name for param in _cfg_cmd.parameters]
    assert "leader" in param_names
    assert "leader_role" in param_names

    # Test successful configuration with user
    interaction = _StubInteraction(guild_id=guild_id, user_id=admin_id, is_admin=True)
    leader_member = _StubMember(id=leader_id, display_name="TestLeader")

    # Get the callback and call it
    callback = None
    for child in command.walk_commands():
        if child.name == "config_leader":
            callback = cast(Any, child).callback
            break

    assert callback is not None
    assert callback is not None
    await cast(Any, callback)(cast(Interaction[Any], interaction), leader_member, None)

    service.set_config.assert_called_once_with(
        guild_id=guild_id,
        leader_id=leader_id,
        leader_role_id=None,
    )
    assert interaction.response_sent

    # Test successful configuration with role
    interaction2 = _StubInteraction(guild_id=guild_id, user_id=admin_id, is_admin=True)
    leader_role = _StubRole(id=leader_role_id, name="Council Leader")

    await cast(Any, callback)(cast(Interaction[Any], interaction2), None, leader_role)

    service.set_config.assert_called_with(
        guild_id=guild_id,
        leader_id=None,
        leader_role_id=leader_role_id,
    )

    # Test error when neither leader nor role provided
    interaction3 = _StubInteraction(guild_id=guild_id, user_id=admin_id, is_admin=True)
    await cast(Any, callback)(cast(Interaction[Any], interaction3), None, None)

    assert interaction3.response_data is not None
    assert "必須指定一位使用者或一個身分組" in cast(str, interaction3.response_data["content"])


@pytest.mark.asyncio
async def test_state_council_config_leader_permission_denied() -> None:
    """Test config leader command with insufficient permissions."""
    guild_id = _snowflake()
    _user_id = _snowflake()

    service = AsyncMock(spec=StateCouncilService)
    command = build_state_council_group(service)

    # Find the config_leader command
    _config_leader_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "config_leader":
            _config_leader_cmd = cmd
            break

    callback = None
    for child in command.walk_commands():
        if child.name == "config_leader":
            callback = cast(Any, child).callback
            break

    # Test with non-admin user
    interaction = _StubInteraction(
        guild_id=guild_id,
        user_id=_user_id,
        is_admin=False,
        manage_guild=False,
    )
    leader_member = _StubMember(id=_snowflake(), display_name="TestLeader")

    await cast(Any, callback)(cast(Interaction[Any], interaction), leader_member, None)

    assert interaction.response_data is not None
    assert interaction.response_data is not None
    assert "需要管理員或管理伺服器權限" in cast(str, interaction.response_data["content"])
    assert not service.set_config.called


@pytest.mark.asyncio
async def test_state_council_panel_command_contract() -> None:
    """Test state council panel command structure and behavior."""
    guild_id = _snowflake()
    _user_id = _snowflake()
    leader_id = _snowflake()
    leader_role_id = _snowflake()

    service = AsyncMock(spec=StateCouncilService)
    expected_config = StateCouncilConfig(
        guild_id=guild_id,
        leader_id=leader_id,
        leader_role_id=leader_role_id,
        internal_affairs_account_id=9500000000000001,
        finance_account_id=9500000000000002,
        security_account_id=9500000000000003,
        central_bank_account_id=9500000000000004,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    service.get_config.return_value = expected_config
    service.check_leader_permission.return_value = True
    service.check_department_permission.return_value = True

    command = build_state_council_group(service)

    # Find the panel command
    panel_cmd = None
    for cmd in command.walk_commands():
        if cmd.name == "panel":
            panel_cmd = cmd
            break

    assert panel_cmd is not None
    _panel_cmd = cast(Any, panel_cmd)
    assert _panel_cmd.name == "panel"
    assert "開啟國務院面板" in _panel_cmd.description
    assert len(_panel_cmd.parameters) == 0  # No parameters required

    # Get the callback
    callback = None
    for child in command.walk_commands():
        if child.name == "panel":
            callback = cast(Any, child).callback
            break

    assert callback is not None

    # Test successful panel opening for leader
    interaction = _StubInteraction(guild_id=guild_id, user_id=leader_id)
    assert callback is not None
    await cast(Any, callback)(cast(Interaction[Any], interaction))

    service.get_config.assert_called_once_with(guild_id=guild_id)
    service.check_leader_permission.assert_called_once()
    assert interaction.response_sent
    assert interaction.response_data is not None
    assert "view" in interaction.response_data


@pytest.mark.asyncio
async def test_state_council_panel_not_configured() -> None:
    """Test panel command when State Council is not configured."""
    guild_id = _snowflake()
    user_id = _snowflake()

    service = AsyncMock(spec=StateCouncilService)
    service.get_config.side_effect = StateCouncilNotConfiguredError("Not configured")

    command = build_state_council_group(service)

    # Find the panel command callback
    callback = None
    for child in command.walk_commands():
        if child.name == "panel":
            callback = cast(Any, child).callback
            break

    interaction = _StubInteraction(guild_id=guild_id, user_id=user_id)
    assert callback is not None
    await cast(Any, callback)(cast(Interaction[Any], interaction))

    assert interaction.response_data is not None
    assert interaction.response_data is not None
    assert "尚未完成國務院設定" in cast(str, interaction.response_data["content"])
    assert interaction.response_data["ephemeral"] is True


@pytest.mark.asyncio
async def test_state_council_panel_permission_denied() -> None:
    """Test panel command with insufficient permissions."""
    guild_id = _snowflake()
    user_id = _snowflake()

    service = AsyncMock(spec=StateCouncilService)
    expected_config = StateCouncilConfig(
        guild_id=guild_id,
        leader_id=_snowflake(),
        leader_role_id=_snowflake(),
        internal_affairs_account_id=9500000000000001,
        finance_account_id=9500000000000002,
        security_account_id=9500000000000003,
        central_bank_account_id=9500000000000004,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    service.get_config.return_value = expected_config
    service.check_leader_permission.return_value = False
    service.check_department_permission.return_value = False

    command = build_state_council_group(service)

    # Find the panel command callback
    callback = None
    for child in command.walk_commands():
        if child.name == "panel":
            callback = cast(Any, child).callback
            break

    interaction = _StubInteraction(guild_id=guild_id, user_id=user_id)
    assert callback is not None
    await cast(Any, callback)(cast(Interaction[Any], interaction))

    assert interaction.response_data is not None
    assert "僅限國務院領袖或部門授權人員可開啟面板" in cast(
        str, interaction.response_data["content"]
    )
    assert interaction.response_data["ephemeral"] is True


@pytest.mark.asyncio
async def test_state_council_panel_role_based_leadership() -> None:
    """Test panel command with role-based leadership."""
    guild_id = _snowflake()
    user_id = _snowflake()
    leader_role_id = _snowflake()
    user_roles = [leader_role_id, _snowflake()]  # User has leader role

    service = AsyncMock(spec=StateCouncilService)
    expected_config = StateCouncilConfig(
        guild_id=guild_id,
        leader_id=None,  # No user-based leader
        leader_role_id=leader_role_id,  # Role-based leadership
        internal_affairs_account_id=9500000000000001,
        finance_account_id=9500000000000002,
        security_account_id=9500000000000003,
        central_bank_account_id=9500000000000004,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    service.get_config.return_value = expected_config
    service.check_leader_permission.return_value = True  # Should return True for role-based leader

    command = build_state_council_group(service)

    # Find the panel command callback
    callback = None
    for child in command.walk_commands():
        if child.name == "panel":
            callback = cast(Any, child).callback
            break

    # Mock interaction with roles
    interaction = _StubInteraction(guild_id=guild_id, user_id=user_id)
    interaction.user.roles = [SimpleNamespace(id=role_id) for role_id in user_roles]

    assert callback is not None
    await cast(Any, callback)(cast(Interaction[Any], interaction))

    service.check_leader_permission.assert_called_once_with(
        guild_id=guild_id, user_id=user_id, user_roles=user_roles
    )
    assert interaction.response_sent


@pytest.mark.asyncio
async def test_state_council_panel_department_access() -> None:
    """Test panel command with department-based access."""
    guild_id = _snowflake()
    user_id = _snowflake()
    dept_role_id = _snowflake()
    user_roles = [dept_role_id]

    service = AsyncMock(spec=StateCouncilService)
    expected_config = StateCouncilConfig(
        guild_id=guild_id,
        leader_id=_snowflake(),
        leader_role_id=_snowflake(),
        internal_affairs_account_id=9500000000000001,
        finance_account_id=9500000000000002,
        security_account_id=9500000000000003,
        central_bank_account_id=9500000000000004,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    service.get_config.return_value = expected_config
    service.check_leader_permission.return_value = False  # Not a leader
    service.check_department_permission.return_value = True  # But has department access

    command = build_state_council_group(service)

    # Find the panel command callback
    callback = None
    for child in command.walk_commands():
        if child.name == "panel":
            callback = cast(Any, child).callback
            break

    # Mock interaction with department role
    interaction = _StubInteraction(guild_id=guild_id, user_id=user_id)
    interaction.user.roles = [SimpleNamespace(id=role_id) for role_id in user_roles]

    assert callback is not None
    await cast(Any, callback)(cast(Interaction[Any], interaction))

    # Should check leader permission first, then department permissions
    assert service.check_leader_permission.called
    assert service.check_department_permission.called
    assert interaction.response_sent


@pytest.mark.asyncio
async def test_state_council_command_error_handling() -> None:
    """Test State Council command error handling."""
    guild_id = _snowflake()
    admin_id = _snowflake()

    service = AsyncMock(spec=StateCouncilService)
    service.set_config.side_effect = Exception("Database error")

    command = build_state_council_group(service)

    # Find the config_leader command callback
    callback = None
    for child in command.walk_commands():
        if child.name == "config_leader":
            callback = cast(Any, child).callback
            break

    interaction = _StubInteraction(guild_id=guild_id, user_id=admin_id, is_admin=True)
    leader_member = _StubMember(id=_snowflake(), display_name="TestLeader")

    assert callback is not None
    await cast(Any, callback)(cast(Interaction[Any], interaction), leader_member, None)

    assert interaction.response_data is not None
    assert "設定失敗，請稍後再試" in cast(str, interaction.response_data["content"])
    assert interaction.response_data["ephemeral"] is True


@pytest.mark.asyncio
async def test_state_council_command_guild_validation() -> None:
    """Test State Council commands require guild context."""
    user_id = _snowflake()

    service = AsyncMock(spec=StateCouncilService)
    command = build_state_council_group(service)

    # Test config_leader without guild
    interaction = SimpleNamespace(guild_id=None, user_id=user_id)
    interaction.response_send_message = AsyncMock()

    # Find the config_leader command callback
    callback = None
    for child in command.walk_commands():
        if child.name == "config_leader":
            callback = cast(Any, child).callback
            break

    assert callback is not None
    await cast(Any, callback)(interaction, None, None)

    interaction.response_send_message.assert_called_once_with(
        "本指令需在伺服器中執行。", ephemeral=True
    )

    # Test panel without guild
    interaction2 = SimpleNamespace(guild_id=None, user_id=user_id)
    interaction2.response_send_message = AsyncMock()

    # Find the panel command callback
    callback2 = None
    for child in command.walk_commands():
        if child.name == "panel":
            callback2 = cast(Any, child).callback
            break

    assert callback2 is not None
    await cast(Any, callback2)(interaction2)

    interaction2.response_send_message.assert_called_once_with(
        "本指令需在伺服器中執行。", ephemeral=True
    )


def test_state_council_command_structure() -> None:
    """Test State Council command group structure."""
    service = AsyncMock(spec=StateCouncilService)
    command = build_state_council_group(service)

    # Verify command group
    assert command.name == "state_council"
    assert "國務院治理指令" in command.description
    any_command = cast(Any, command)
    assert any_command.type == AppCommandOptionType.subcommand_group

    # Verify subcommands exist
    subcommand_names = [cmd.name for cmd in command.walk_commands()]
    assert "config_leader" in subcommand_names
    assert "panel" in subcommand_names

    # Verify config_leader command structure
    config_leader = None
    for cmd in command.walk_commands():
        if cmd.name == "config_leader":
            config_leader = cmd
            break

    assert config_leader is not None
    _cfg_cmd2 = cast(Any, config_leader)
    assert len(_cfg_cmd2.parameters) == 2  # leader and leader_role

    # Verify parameter types
    leader_param = next(p for p in _cfg_cmd2.parameters if p.name == "leader")
    assert leader_param.required is False  # Optional
    assert leader_param.type == AppCommandOptionType.user

    leader_role_param = next(p for p in _cfg_cmd2.parameters if p.name == "leader_role")
    assert leader_role_param.required is False  # Optional
    assert leader_role_param.type == AppCommandOptionType.role

    # Verify panel command structure
    panel = None
    for cmd in command.walk_commands():
        if cmd.name == "panel":
            panel = cmd
            break

    assert panel is not None
    _panel_cmd2 = cast(Any, panel)
    assert len(_panel_cmd2.parameters) == 0  # No parameters
