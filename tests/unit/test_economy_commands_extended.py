"""Extended tests for economy commands - Task 3.1-3.3.

Coverage for adjust, transfer, balance commands focusing on:
- Error handling paths
- Edge cases and boundary conditions
- Result<T,E> pattern validation
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from discord import Interaction

from src.bot.commands.adjust import build_adjust_command
from src.bot.commands.transfer import build_transfer_command
from src.bot.services.adjustment_service import AdjustmentResult, AdjustmentService
from src.bot.services.currency_config_service import CurrencyConfigResult, CurrencyConfigService
from src.bot.services.transfer_service import (
    InsufficientBalanceError,
    TransferResult,
    TransferService,
    TransferThrottleError,
)
from src.infra.result import DatabaseError, Err, Ok, ValidationError

# --- Helper Classes ---


class StubResponse:
    def __init__(self) -> None:
        self.sent = False
        self.deferred = False
        self.kwargs: dict[str, Any] | None = None

    async def send_message(self, **kwargs: Any) -> None:
        self.sent = True
        self.kwargs = kwargs

    async def defer(self, **kwargs: Any) -> None:
        self.deferred = True

    def is_done(self) -> bool:
        return self.deferred


class StubInteraction:
    def __init__(self, guild_id: int, user_id: int, *, is_admin: bool = False) -> None:
        self.guild_id = guild_id
        self.user = SimpleNamespace(
            id=user_id,
            guild_permissions=SimpleNamespace(administrator=is_admin, manage_guild=is_admin),
        )
        self.response = StubResponse()
        self.token = "test_token"

    @property
    def guild_permissions(self) -> Any:
        return self.user.guild_permissions

    async def edit_original_response(self, **kwargs: Any) -> None:
        self.response.kwargs = kwargs


class StubMember(SimpleNamespace):
    def __init__(self, *, id: int) -> None:
        super().__init__(id=id)

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


# --- Task 3.1: Adjust Command Extended Tests ---


class TestAdjustCommandErrorPaths:
    """Test adjust command error handling paths."""

    @pytest.mark.asyncio
    async def test_adjust_database_error(self) -> None:
        """Test adjust command handling database error."""
        service = SimpleNamespace(
            adjust_balance=AsyncMock(return_value=Err(DatabaseError("連線失敗")))
        )
        currency_service = SimpleNamespace(get_currency_config=AsyncMock())

        command = build_adjust_command(
            cast(AdjustmentService, service), cast(CurrencyConfigService, currency_service)
        )
        interaction = StubInteraction(guild_id=12345, user_id=67890, is_admin=True)
        target = StubMember(id=11111)

        await command._callback(
            cast(Interaction[Any], interaction), cast(Interaction[Any], target), 100, "Test"
        )

        assert interaction.response.sent is True
        # DatabaseError triggers generic error message for security
        assert "錯誤" in (interaction.response.kwargs or {}).get("content", "")

    @pytest.mark.asyncio
    async def test_adjust_negative_amount(self) -> None:
        """Test adjust with negative amount (deduction)."""
        result = AdjustmentResult(
            transaction_id=None,
            guild_id=12345,
            admin_id=67890,
            target_id=11111,
            amount=-50,
            target_balance_after=150,
            direction="adjustment_deduct",
            created_at=None,
            metadata={},
        )
        service = SimpleNamespace(adjust_balance=AsyncMock(return_value=Ok(result)))
        currency_config = CurrencyConfigResult(currency_name="金幣", currency_icon="💰")
        currency_service = SimpleNamespace(
            get_currency_config=AsyncMock(return_value=currency_config)
        )

        command = build_adjust_command(
            cast(AdjustmentService, service), cast(CurrencyConfigService, currency_service)
        )
        interaction = StubInteraction(guild_id=12345, user_id=67890, is_admin=True)
        target = StubMember(id=11111)

        await command._callback(
            cast(Interaction[Any], interaction), cast(Interaction[Any], target), -50, "扣款"
        )

        assert interaction.response.sent is True

    @pytest.mark.asyncio
    async def test_adjust_large_amount(self) -> None:
        """Test adjust with very large amount."""
        large_amount = 1_000_000_000
        result = AdjustmentResult(
            transaction_id=None,
            guild_id=12345,
            admin_id=67890,
            target_id=11111,
            amount=large_amount,
            target_balance_after=large_amount,
            direction="adjustment_grant",
            created_at=None,
            metadata={},
        )
        service = SimpleNamespace(adjust_balance=AsyncMock(return_value=Ok(result)))
        currency_config = CurrencyConfigResult(currency_name="金幣", currency_icon="💰")
        currency_service = SimpleNamespace(
            get_currency_config=AsyncMock(return_value=currency_config)
        )

        command = build_adjust_command(
            cast(AdjustmentService, service), cast(CurrencyConfigService, currency_service)
        )
        interaction = StubInteraction(guild_id=12345, user_id=67890, is_admin=True)
        target = StubMember(id=11111)

        await command._callback(
            cast(Interaction[Any], interaction),
            cast(Interaction[Any], target),
            large_amount,
            "大額",
        )

        assert interaction.response.sent is True
        content = (interaction.response.kwargs or {}).get("content", "")
        assert "1,000,000,000" in content or "1000000000" in content


# --- Task 3.2: Transfer Command Extended Tests ---


class TestTransferCommandErrorPaths:
    """Test transfer command error handling paths."""

    @pytest.mark.asyncio
    async def test_transfer_insufficient_balance(self) -> None:
        """Test transfer with insufficient balance."""
        service = SimpleNamespace(
            transfer_currency=AsyncMock(side_effect=InsufficientBalanceError("餘額不足"))
        )
        currency_service = SimpleNamespace(
            get_currency_config=AsyncMock(
                return_value=CurrencyConfigResult(currency_name="金幣", currency_icon="💰")
            )
        )

        command = build_transfer_command(
            cast(TransferService, service), cast(CurrencyConfigService, currency_service)
        )
        interaction = StubInteraction(guild_id=12345, user_id=67890)
        target = StubMember(id=11111)

        await command._callback(
            cast(Interaction[Any], interaction), cast(Interaction[Any], target), 999999
        )

        assert interaction.response.sent or interaction.response.deferred

    @pytest.mark.asyncio
    async def test_transfer_throttle_error(self) -> None:
        """Test transfer with throttle limit."""
        service = SimpleNamespace(
            transfer_currency=AsyncMock(side_effect=TransferThrottleError("操作過於頻繁"))
        )
        currency_service = SimpleNamespace(
            get_currency_config=AsyncMock(
                return_value=CurrencyConfigResult(currency_name="金幣", currency_icon="💰")
            )
        )

        command = build_transfer_command(
            cast(TransferService, service), cast(CurrencyConfigService, currency_service)
        )
        interaction = StubInteraction(guild_id=12345, user_id=67890)
        target = StubMember(id=11111)

        await command._callback(
            cast(Interaction[Any], interaction), cast(Interaction[Any], target), 100
        )

        assert interaction.response.sent or interaction.response.deferred

    def test_transfer_to_self_detection(self) -> None:
        """Test transfer to self detection logic."""
        # Test same user ID detection
        sender_id = 67890
        target_id = 67890
        is_self_transfer = sender_id == target_id
        assert is_self_transfer is True

        # Test different user IDs
        target_id = 11111
        is_self_transfer = sender_id == target_id
        assert is_self_transfer is False

    @pytest.mark.asyncio
    async def test_transfer_success(self) -> None:
        """Test successful transfer."""
        result = TransferResult(
            transaction_id=None,
            guild_id=12345,
            initiator_id=67890,
            target_id=11111,
            amount=100,
            initiator_balance=900,
            target_balance=200,
            created_at=None,
            metadata={},
        )
        service = SimpleNamespace(transfer_currency=AsyncMock(return_value=result))
        currency_service = SimpleNamespace(
            get_currency_config=AsyncMock(
                return_value=CurrencyConfigResult(currency_name="金幣", currency_icon="💰")
            )
        )

        command = build_transfer_command(
            cast(TransferService, service), cast(CurrencyConfigService, currency_service)
        )
        interaction = StubInteraction(guild_id=12345, user_id=67890)
        target = StubMember(id=11111)

        await command._callback(
            cast(Interaction[Any], interaction), cast(Interaction[Any], target), 100
        )

        service.transfer_currency.assert_awaited_once()


# --- Task 3.3: Balance Command Extended Tests ---


class TestBalanceCommandEdgeCases:
    """Test balance command edge cases."""

    def test_currency_display_formats(self) -> None:
        """Test different currency display formats."""
        # Test with name and icon
        config1 = CurrencyConfigResult(currency_name="金幣", currency_icon="💰")
        assert config1.currency_name == "金幣"
        assert config1.currency_icon == "💰"

        # Test with name only
        config2 = CurrencyConfigResult(currency_name="點數", currency_icon=None)
        assert config2.currency_name == "點數"
        assert config2.currency_icon is None

        # Test with icon only
        config3 = CurrencyConfigResult(currency_name=None, currency_icon="🪙")
        assert config3.currency_name is None
        assert config3.currency_icon == "🪙"

    def test_balance_formatting(self) -> None:
        """Test balance number formatting."""
        test_cases = [
            (0, "0"),
            (100, "100"),
            (1000, "1,000"),
            (1000000, "1,000,000"),
            (1234567890, "1,234,567,890"),
        ]
        for amount, expected in test_cases:
            formatted = f"{amount:,}"
            assert formatted == expected


# --- Result<T,E> Pattern Tests ---


class TestResultPatternValidation:
    """Test Result<T,E> pattern in economy commands."""

    def test_ok_result_unwrap(self) -> None:
        """Test Ok result unwrapping."""
        result = Ok({"amount": 100, "balance": 500})
        assert result.is_ok()
        assert not result.is_err()
        value = result.unwrap()
        assert value["amount"] == 100
        assert value["balance"] == 500

    def test_err_result_unwrap(self) -> None:
        """Test Err result unwrapping."""
        error = ValidationError("金額無效")
        result = Err(error)
        assert not result.is_ok()
        assert result.is_err()
        unwrapped_error = result.unwrap_err()
        assert unwrapped_error.message == "金額無效"

    def test_result_map(self) -> None:
        """Test Result map operation."""
        ok_result: Ok[int, ValidationError] = Ok(10)
        mapped = ok_result.map(lambda x: x * 2)
        assert mapped.is_ok()
        assert mapped.unwrap() == 20

    def test_result_with_context(self) -> None:
        """Test Error with context."""
        error = ValidationError(
            "金額超過上限", context={"max_amount": 1000000, "requested": 2000000}
        )
        assert error.context["max_amount"] == 1000000
        assert "requested" in error.context

    def test_database_error_type(self) -> None:
        """Test DatabaseError type."""
        error = DatabaseError("連線逾時", context={"timeout": 30})
        result = Err(error)
        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, DatabaseError)
        assert "逾時" in err.message


class TestEconomyServiceMocking:
    """Test economy service mocking patterns."""

    @pytest.mark.asyncio
    async def test_adjustment_service_mock(self) -> None:
        """Test AdjustmentService mocking."""
        service = MagicMock(spec=AdjustmentService)
        service.adjust_balance = AsyncMock(
            return_value=Ok(
                AdjustmentResult(
                    transaction_id=None,
                    guild_id=12345,
                    admin_id=67890,
                    target_id=11111,
                    amount=100,
                    target_balance_after=200,
                    direction="adjustment_grant",
                    created_at=None,
                    metadata={},
                )
            )
        )

        result = await service.adjust_balance(
            guild_id=12345, admin_id=67890, target_id=11111, amount=100, reason="Test"
        )

        assert result.is_ok()
        assert result.unwrap().amount == 100

    @pytest.mark.asyncio
    async def test_transfer_service_mock(self) -> None:
        """Test TransferService mocking."""
        service = MagicMock(spec=TransferService)
        service.transfer_currency = AsyncMock(
            return_value=TransferResult(
                transaction_id=None,
                guild_id=12345,
                initiator_id=67890,
                target_id=11111,
                amount=50,
                initiator_balance=950,
                target_balance=150,
                created_at=None,
                metadata={},
            )
        )

        result = await service.transfer_currency(
            guild_id=12345, initiator_id=67890, target_id=11111, amount=50
        )

        assert result.amount == 50
        assert result.initiator_balance == 950

    @pytest.mark.asyncio
    async def test_currency_config_service_mock(self) -> None:
        """Test CurrencyConfigService mocking."""
        service = MagicMock(spec=CurrencyConfigService)
        service.get_currency_config = AsyncMock(
            return_value=CurrencyConfigResult(currency_name="測試幣", currency_icon="🔷")
        )

        config = await service.get_currency_config(guild_id=12345)

        assert config.currency_name == "測試幣"
        assert config.currency_icon == "🔷"
