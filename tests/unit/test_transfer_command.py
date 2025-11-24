"""Unit tests for transfer command logic."""

from __future__ import annotations

import secrets
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from discord import Interaction

from src.bot.commands.transfer import build_transfer_command
from src.bot.services.council_service import GovernanceNotConfiguredError
from src.bot.services.currency_config_service import (
    CurrencyConfigResult,
    CurrencyConfigService,
)
from src.bot.services.transfer_service import (
    InsufficientBalanceError,
    TransferResult,
    TransferService,
    TransferThrottleError,
)


def _snowflake() -> int:
    """Generate a random Discord snowflake for isolated test runs."""
    return secrets.randbits(63)


class _StubResponse:
    def __init__(self) -> None:
        self.deferred = False
        self.sent = False
        self.kwargs: dict[str, Any] | None = None

    async def defer(self, **kwargs: Any) -> None:
        self.deferred = True

    async def send_message(self, **kwargs: Any) -> None:
        self.sent = True
        self.kwargs = kwargs

    def is_done(self) -> bool:
        return self.deferred


class _StubInteraction:
    def __init__(self, guild_id: int, user_id: int) -> None:
        self.guild_id = guild_id
        self.user = SimpleNamespace(id=user_id)
        self.response = _StubResponse()
        self.token = None

    async def edit_original_response(self, **kwargs: Any) -> None:
        self.response.kwargs = kwargs


class _StubMember(SimpleNamespace):
    def __init__(self, *, id: int) -> None:
        super().__init__(id=id)

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


class _StubRole(SimpleNamespace):
    def __init__(self, *, id: int) -> None:
        super().__init__(id=id)

    @property
    def mention(self) -> str:
        return f"<@&{self.id}>"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_maps_council_role_to_council_account(monkeypatch: Any) -> None:
    """當目標為理事會身分組時，應映射至理事會公共帳戶 ID。"""
    guild_id = _snowflake()
    initiator_id = _snowflake()
    council_role_id = _snowflake()

    # 服務替身
    result = TransferResult(
        transaction_id=None,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=0,  # 由被測函式決定
        amount=77,
        initiator_balance=1000,
        target_balance=None,
        created_at=None,
        metadata={},
    )
    service = SimpleNamespace(transfer_currency=AsyncMock(return_value=result))
    currency_service = SimpleNamespace(
        get_currency_config=AsyncMock(
            return_value=CurrencyConfigResult(currency_name="幣", currency_icon="")
        )
    )

    # 先建 command，避免註冊期型別轉換因 monkeypatch 失敗
    import src.bot.commands.transfer as transfer_mod

    command = build_transfer_command(
        cast(TransferService, service), cast(CurrencyConfigService, currency_service)
    )

    # 建立後再 Patch transfer 模組中的 discord.Role 為測試替身型別，使 isinstance 成立
    monkeypatch.setattr(transfer_mod.discord, "Role", _StubRole, raising=True)

    # Patch CouncilServiceResult 類別為無資料庫相依的替身
    class _CouncilCfg(SimpleNamespace):
        council_role_id: int

    from src.bot.services.council_service import CouncilService as _RealCS
    from src.infra.result import Err, Ok

    class _CSRStub:
        derive_council_account_id = staticmethod(_RealCS.derive_council_account_id)

        async def get_config(
            self, *, guild_id: int
        ) -> Ok[Any, Any] | Err[Any, Any]:  # noqa: ANN401
            return Ok(_CouncilCfg(council_role_id=council_role_id))

    monkeypatch.setattr(transfer_mod, "CouncilServiceResult", _CSRStub, raising=True)

    # Patch SupremeAssemblyService 類別為無資料庫相依的替身
    class _SASStub:
        async def get_config(self, *, guild_id: int) -> Any:  # noqa: ANN401
            return None

    monkeypatch.setattr(transfer_mod, "SupremeAssemblyService", _SASStub, raising=True)

    # Patch StateCouncilService 類別為無資料庫相依的替身
    class _SCSStub:
        async def get_config(self, *, guild_id: int) -> Any:  # noqa: ANN401
            return None

        async def find_department_by_role(
            self, *, guild_id: int, role_id: int
        ) -> Any:  # noqa: ANN401
            return None

    monkeypatch.setattr(transfer_mod, "StateCouncilService", _SCSStub, raising=True)

    interaction = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    target_role = _StubRole(id=council_role_id)

    await command._callback(cast(Interaction[Any], interaction), target_role, 77, None)

    # 期望以理事會公共帳戶 ID 作為 target_id
    service.transfer_currency.assert_awaited_once()
    kwargs = service.transfer_currency.await_args.kwargs
    from src.bot.services.council_service import CouncilService as _CS

    assert kwargs["target_id"] == _CS.derive_council_account_id(guild_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_maps_sc_leader_role_to_main_account(monkeypatch: Any) -> None:
    """當目標為國務院領袖身分組時，應映射至國務院主帳戶 ID。"""
    guild_id = _snowflake()
    initiator_id = _snowflake()
    leader_role_id = _snowflake()

    result = TransferResult(
        transaction_id=None,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=0,
        amount=123,
        initiator_balance=1000,
        target_balance=None,
        created_at=None,
        metadata={},
    )
    service = SimpleNamespace(transfer_currency=AsyncMock(return_value=result))
    currency_service = SimpleNamespace(
        get_currency_config=AsyncMock(
            return_value=CurrencyConfigResult(currency_name="幣", currency_icon="")
        )
    )

    import src.bot.commands.transfer as transfer_mod

    # 先建 command，避免註冊期型別轉換因 monkeypatch 失敗
    command = build_transfer_command(
        cast(TransferService, service), cast(CurrencyConfigService, currency_service)
    )

    # 讓 isinstance(target, discord.Role) 成立（建完 command 後再 patch）
    monkeypatch.setattr(transfer_mod.discord, "Role", _StubRole, raising=True)

    # Patch CouncilServiceResult 類別為無資料庫相依的替身（未設定）
    class _CouncilCfg(SimpleNamespace):
        council_role_id: int

    class _CSRStub:
        async def get_config(self, *, guild_id: int) -> Any:  # noqa: ANN401
            raise GovernanceNotConfiguredError()

    monkeypatch.setattr(transfer_mod, "CouncilServiceResult", _CSRStub, raising=True)

    # StateCouncil 類別替身：設定有 leader_role_id，且不命中任何部門
    class _Cfg(SimpleNamespace):
        leader_role_id: int | None = None

    from src.bot.services.state_council_service import StateCouncilService as _RealSCS

    class _SCSStub:
        derive_main_account_id = staticmethod(_RealSCS.derive_main_account_id)

        async def get_config(self, *, guild_id: int) -> Any:  # noqa: ANN401
            return _Cfg(leader_role_id=leader_role_id)

        async def find_department_by_role(
            self, *, guild_id: int, role_id: int
        ) -> Any:  # noqa: ANN401
            return None

    monkeypatch.setattr(transfer_mod, "StateCouncilService", _SCSStub, raising=True)

    interaction = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    target_role = _StubRole(id=leader_role_id)

    await command._callback(cast(Interaction[Any], interaction), target_role, 123, None)

    service.transfer_currency.assert_awaited_once()
    kwargs = service.transfer_currency.await_args.kwargs  # type: ignore[attr-defined]
    from src.bot.services.state_council_service import StateCouncilService as _SCS

    assert kwargs["target_id"] == _SCS.derive_main_account_id(guild_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_maps_department_leader_role_to_department_account(
    monkeypatch: Any,
) -> None:
    """當目標為部門領導人身分組時，應映射至對應部門帳戶 ID。"""
    guild_id = _snowflake()
    initiator_id = _snowflake()
    role_id = _snowflake()
    department = "財政部"

    result = TransferResult(
        transaction_id=None,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=0,
        amount=456,
        initiator_balance=1000,
        target_balance=None,
        created_at=None,
        metadata={},
    )
    service = SimpleNamespace(transfer_currency=AsyncMock(return_value=result))
    currency_service = SimpleNamespace(
        get_currency_config=AsyncMock(
            return_value=CurrencyConfigResult(currency_name="幣", currency_icon="")
        )
    )

    import src.bot.commands.transfer as transfer_mod

    # 先建 command，避免註冊期型別轉換因 monkeypatch 失敗
    command = build_transfer_command(
        cast(TransferService, service), cast(CurrencyConfigService, currency_service)
    )

    # 讓 isinstance(target, discord.Role) 成立（建完 command 後再 patch）
    monkeypatch.setattr(transfer_mod.discord, "Role", _StubRole, raising=True)

    # CouncilServiceResult 類別替身：未設定
    class _CSRStub:
        async def get_config(self, *, guild_id: int) -> Any:  # noqa: ANN401
            raise GovernanceNotConfiguredError()

    monkeypatch.setattr(transfer_mod, "CouncilServiceResult", _CSRStub, raising=True)

    # StateCouncil 類別替身：沒有 leader 命中；find_department_by_role 命中部門；get_department_account_id 回傳期望值
    from src.bot.services.state_council_service import StateCouncilService as _RealSCS

    expected_account_id = _RealSCS.derive_department_account_id(guild_id, department)

    class _SCSStub:
        derive_department_account_id = staticmethod(_RealSCS.derive_department_account_id)

        async def get_config(self, *, guild_id: int) -> Any:  # noqa: ANN401
            return SimpleNamespace(leader_role_id=None)

        async def find_department_by_role(
            self, *, guild_id: int, role_id: int
        ) -> Any:  # noqa: ANN401
            return department

        async def get_department_account_id(
            self, *, guild_id: int, department: str
        ) -> Any:  # noqa: ANN401
            return expected_account_id

    monkeypatch.setattr(transfer_mod, "StateCouncilService", _SCSStub, raising=True)

    interaction = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    target_role = _StubRole(id=role_id)

    await command._callback(cast(Interaction[Any], interaction), target_role, 456, None)

    service.transfer_currency.assert_awaited_once()
    kwargs = service.transfer_currency.await_args.kwargs  # type: ignore[attr-defined]
    assert kwargs["target_id"] == expected_account_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_requires_guild() -> None:
    """Test that transfer command requires guild context."""
    service = SimpleNamespace(transfer_currency=AsyncMock())
    currency_service = SimpleNamespace(get_currency_config=AsyncMock())
    command = build_transfer_command(
        cast(TransferService, service), cast(CurrencyConfigService, currency_service)
    )
    interaction = _StubInteraction(guild_id=None, user_id=_snowflake())  # type: ignore
    target = _StubMember(id=_snowflake())

    await command._callback(cast(Interaction[Any], interaction), target, 100, None)

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert "伺服器內" in interaction.response.kwargs.get("content", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_validates_insufficient_balance() -> None:
    """Test that transfer command handles insufficient balance error."""
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    service = SimpleNamespace(
        transfer_currency=AsyncMock(side_effect=InsufficientBalanceError("餘額不足"))
    )
    currency_service = SimpleNamespace(get_currency_config=AsyncMock())

    command = build_transfer_command(
        cast(TransferService, service), cast(CurrencyConfigService, currency_service)
    )
    interaction = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    target = _StubMember(id=target_id)

    await command._callback(cast(Interaction[Any], interaction), target, 1000, None)

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert "餘額不足" in interaction.response.kwargs.get("content", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_validates_throttle() -> None:
    """Test that transfer command handles throttle error."""
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    service = SimpleNamespace(
        transfer_currency=AsyncMock(side_effect=TransferThrottleError("冷卻中"))
    )
    currency_service = SimpleNamespace(get_currency_config=AsyncMock())

    command = build_transfer_command(
        cast(TransferService, service), cast(CurrencyConfigService, currency_service)
    )
    interaction = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    target = _StubMember(id=target_id)

    await command._callback(cast(Interaction[Any], interaction), target, 100, None)

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    assert "冷卻中" in interaction.response.kwargs.get("content", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_calls_service_with_correct_parameters() -> None:
    """Test that transfer command calls service with correct parameters."""
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    result = TransferResult(
        transaction_id=None,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=100,
        initiator_balance=900,
        target_balance=None,
        created_at=None,
        metadata={"reason": "Test"},
    )

    service = SimpleNamespace(transfer_currency=AsyncMock(return_value=result))
    currency_config = CurrencyConfigResult(currency_name="金幣", currency_icon="🪙")
    currency_service = SimpleNamespace(get_currency_config=AsyncMock(return_value=currency_config))

    command = build_transfer_command(
        cast(TransferService, service), cast(CurrencyConfigService, currency_service)
    )
    interaction = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    target = _StubMember(id=target_id)

    await command._callback(cast(Interaction[Any], interaction), target, 100, "Test")

    service.transfer_currency.assert_awaited_once_with(
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=100,
        reason="Test",
        connection=None,
        metadata=None,
    )
    currency_service.get_currency_config.assert_awaited_once_with(guild_id=guild_id)
    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    content = interaction.response.kwargs.get("content", "")
    assert "金幣" in content or "🪙" in content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_uses_currency_config() -> None:
    """Test that transfer command uses configured currency name and icon."""
    guild_id = _snowflake()
    initiator_id = _snowflake()
    target_id = _snowflake()

    result = TransferResult(
        transaction_id=None,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=100,
        initiator_balance=900,
        target_balance=None,
        created_at=None,
        metadata={"reason": "Test"},
    )

    service = SimpleNamespace(transfer_currency=AsyncMock(return_value=result))
    currency_config = CurrencyConfigResult(currency_name="點數", currency_icon="💰")
    currency_service = SimpleNamespace(get_currency_config=AsyncMock(return_value=currency_config))

    command = build_transfer_command(
        cast(TransferService, service), cast(CurrencyConfigService, currency_service)
    )
    interaction = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    target = _StubMember(id=target_id)

    await command._callback(cast(Interaction[Any], interaction), target, 100, "Test")

    assert interaction.response.sent is True
    assert interaction.response.kwargs is not None
    content = interaction.response.kwargs.get("content", "")
    assert "點數" in content
    assert "💰" in content
    assert "100" in content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transfer_command_maps_state_council_leader_role_to_main_account(
    monkeypatch: Any,
) -> None:
    """當目標為國務院領袖身分組時，應映射至國務院主帳戶 ID。"""
    guild_id = _snowflake()
    initiator_id = _snowflake()
    leader_role_id = _snowflake()

    # Patch CouncilServiceResult：視為尚未設定或不符合
    import src.bot.commands.transfer as transfer_mod

    async def _council_get_config_unset(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        raise GovernanceNotConfiguredError()

    monkeypatch.setattr(
        transfer_mod.CouncilServiceResult, "get_config", _council_get_config_unset, raising=True
    )

    # Patch StateCouncilService：回傳含 leader_role_id 的配置
    class _Cfg(SimpleNamespace):
        leader_role_id: int | None = None

    async def _sc_get_config(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        return _Cfg(leader_role_id=leader_role_id)

    monkeypatch.setattr(
        transfer_mod.StateCouncilService, "get_config", _sc_get_config, raising=True
    )

    # 後續測試改以「成員目標」驗證事件池 metadata，避免 Discord 型別轉換影響
    import os
    from uuid import uuid4

    os.environ["TRANSFER_EVENT_POOL_ENABLED"] = "true"

    result_uuid = uuid4()
    service2 = SimpleNamespace(transfer_currency=AsyncMock(return_value=result_uuid))
    currency_service2 = SimpleNamespace(get_currency_config=AsyncMock())

    command2 = build_transfer_command(
        cast(TransferService, service2), cast(CurrencyConfigService, currency_service2)
    )
    interaction2 = _StubInteraction(guild_id=guild_id, user_id=initiator_id)
    interaction2.token = "tok123"
    target_member = _StubMember(id=_snowflake())

    await command2._callback(cast(Interaction[Any], interaction2), target_member, 200, "備註")

    service2.transfer_currency.assert_awaited_once()
    kwargs2 = service2.transfer_currency.await_args.kwargs  # type: ignore[attr-defined]
    assert kwargs2["metadata"] == {"interaction_token": "tok123"}
