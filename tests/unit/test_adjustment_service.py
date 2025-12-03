"""測試餘額調整服務 (adjustment_service.py)。

涵蓋範圍：
- Result 模式與 legacy 連線模式的錯誤映射
- asyncpg PostgresError 映射為 ValidationError
- 權限檢查與驗證
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from src.bot.services.adjustment_service import (
    AdjustmentService,
    UnauthorizedAdjustmentError,
)
from src.cython_ext.economy_adjustment_models import AdjustmentResult
from src.infra.result import DatabaseError, Err, Ok, ValidationError

# --- Mock Objects ---


class MockAdjustmentProcedureResult:
    """模擬調整程序結果。"""

    def __init__(
        self,
        new_balance: int = 5000,
        prev_balance: int = 10000,
        adjustment_id: str = "test-adjustment-id",
    ) -> None:
        self.new_balance = new_balance
        self.prev_balance = prev_balance
        self.adjustment_id = adjustment_id


@pytest.fixture
def mock_pool() -> MagicMock:
    """創建假連線池。"""
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncMock())
    return pool


@pytest.fixture
def mock_gateway() -> MagicMock:
    """創建假 EconomyAdjustmentGateway。"""
    gateway = MagicMock()
    gateway.adjust_balance = AsyncMock()
    return gateway


@pytest.fixture
def mock_connection() -> MagicMock:
    """創建假資料庫連線。"""
    return MagicMock()


@pytest.fixture
def adjustment_service(mock_pool: MagicMock, mock_gateway: MagicMock) -> AdjustmentService:
    """創建 AdjustmentService 實例。"""
    return AdjustmentService(mock_pool, gateway=mock_gateway)


# --- Test AdjustmentService Initialization ---


class TestAdjustmentServiceInit:
    """測試 AdjustmentService 初始化。"""

    def test_init_with_pool(self, mock_pool: MagicMock) -> None:
        """測試使用連線池初始化。"""
        service = AdjustmentService(mock_pool)
        assert service._pool == mock_pool
        assert service._gateway is not None

    def test_init_with_custom_gateway(self, mock_pool: MagicMock, mock_gateway: MagicMock) -> None:
        """測試使用自定義 gateway 初始化。"""
        service = AdjustmentService(mock_pool, gateway=mock_gateway)
        assert service._gateway == mock_gateway


# --- Test Legacy Mode (with connection) ---


class TestAdjustmentServiceLegacyMode:
    """測試傳統連線模式（提供 connection）。"""

    @pytest.mark.asyncio
    async def test_adjust_balance_success(
        self,
        adjustment_service: AdjustmentService,
        mock_gateway: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """測試調整餘額成功。"""
        mock_result = MockAdjustmentProcedureResult()
        mock_gateway.adjust_balance = AsyncMock(return_value=Ok(mock_result))

        with patch.object(
            adjustment_service, "_to_result", return_value=MagicMock(spec=AdjustmentResult)
        ):
            result = await adjustment_service.adjust_balance(
                guild_id=12345,
                admin_id=67890,
                target_id=11111,
                amount=-5000,
                reason="測試調整",
                can_adjust=True,
                connection=mock_connection,
            )

        assert result is not None
        mock_gateway.adjust_balance.assert_called_once()

    @pytest.mark.asyncio
    async def test_adjust_balance_unauthorized_raises(
        self,
        adjustment_service: AdjustmentService,
        mock_connection: MagicMock,
    ) -> None:
        """測試未授權調整拋出例外。"""
        with pytest.raises(UnauthorizedAdjustmentError) as exc_info:
            await adjustment_service.adjust_balance(
                guild_id=12345,
                admin_id=67890,
                target_id=11111,
                amount=-5000,
                reason="測試調整",
                can_adjust=False,  # 無權限
                connection=mock_connection,
            )

        assert "permission" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_adjust_balance_empty_reason_raises(
        self,
        adjustment_service: AdjustmentService,
        mock_connection: MagicMock,
    ) -> None:
        """測試空原因拋出 ValidationError。"""
        with pytest.raises(ValidationError) as exc_info:
            await adjustment_service.adjust_balance(
                guild_id=12345,
                admin_id=67890,
                target_id=11111,
                amount=-5000,
                reason="",  # 空原因
                can_adjust=True,
                connection=mock_connection,
            )

        assert "reason is required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_adjust_balance_whitespace_reason_raises(
        self,
        adjustment_service: AdjustmentService,
        mock_connection: MagicMock,
    ) -> None:
        """測試只有空格的原因拋出 ValidationError。"""
        with pytest.raises(ValidationError) as exc_info:
            await adjustment_service.adjust_balance(
                guild_id=12345,
                admin_id=67890,
                target_id=11111,
                amount=-5000,
                reason="   ",  # 只有空格
                can_adjust=True,
                connection=mock_connection,
            )

        assert "reason is required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_adjust_balance_zero_amount_raises(
        self,
        adjustment_service: AdjustmentService,
        mock_connection: MagicMock,
    ) -> None:
        """測試零金額拋出 ValidationError。"""
        with pytest.raises(ValidationError) as exc_info:
            await adjustment_service.adjust_balance(
                guild_id=12345,
                admin_id=67890,
                target_id=11111,
                amount=0,  # 零金額
                reason="測試調整",
                can_adjust=True,
                connection=mock_connection,
            )

        assert "non-zero" in str(exc_info.value).lower()


# --- Test Result Mode (without connection) ---


class TestAdjustmentServiceResultMode:
    """測試 Result 模式（不提供 connection）。"""

    @pytest.mark.asyncio
    async def test_adjust_balance_result_success(
        self, mock_pool: MagicMock, mock_gateway: MagicMock
    ) -> None:
        """測試 Result 模式調整成功。"""
        mock_result = MockAdjustmentProcedureResult()
        mock_gateway.adjust_balance = AsyncMock(return_value=Ok(mock_result))

        # 設置假連線
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        service = AdjustmentService(mock_pool, gateway=mock_gateway)

        with patch.object(service, "_to_result", return_value=MagicMock(spec=AdjustmentResult)):
            result = await service.adjust_balance(
                guild_id=12345,
                admin_id=67890,
                target_id=11111,
                amount=-5000,
                reason="測試調整",
                can_adjust=True,
                connection=None,  # Result 模式
            )

        assert isinstance(result, Ok)

    @pytest.mark.asyncio
    async def test_adjust_balance_result_unauthorized(
        self, mock_pool: MagicMock, mock_gateway: MagicMock
    ) -> None:
        """測試 Result 模式未授權返回 Err。"""
        service = AdjustmentService(mock_pool, gateway=mock_gateway)

        result = await service.adjust_balance(
            guild_id=12345,
            admin_id=67890,
            target_id=11111,
            amount=-5000,
            reason="測試調整",
            can_adjust=False,  # 無權限
            connection=None,
        )

        assert isinstance(result, Err)
        assert isinstance(result.error, ValidationError)
        assert "permission" in str(result.error).lower()

    @pytest.mark.asyncio
    async def test_adjust_balance_result_empty_reason(
        self, mock_pool: MagicMock, mock_gateway: MagicMock
    ) -> None:
        """測試 Result 模式空原因返回 Err。"""
        service = AdjustmentService(mock_pool, gateway=mock_gateway)

        result = await service.adjust_balance(
            guild_id=12345,
            admin_id=67890,
            target_id=11111,
            amount=-5000,
            reason="",
            can_adjust=True,
            connection=None,
        )

        assert isinstance(result, Err)
        assert isinstance(result.error, ValidationError)
        assert "reason is required" in str(result.error).lower()

    @pytest.mark.asyncio
    async def test_adjust_balance_result_zero_amount(
        self, mock_pool: MagicMock, mock_gateway: MagicMock
    ) -> None:
        """測試 Result 模式零金額返回 Err。"""
        service = AdjustmentService(mock_pool, gateway=mock_gateway)

        result = await service.adjust_balance(
            guild_id=12345,
            admin_id=67890,
            target_id=11111,
            amount=0,
            reason="測試調整",
            can_adjust=True,
            connection=None,
        )

        assert isinstance(result, Err)
        assert isinstance(result.error, ValidationError)
        assert "non-zero" in str(result.error).lower()


# --- Test PostgresError Mapping ---


class TestPostgresErrorMapping:
    """測試 asyncpg PostgresError 映射。"""

    def test_handle_postgres_error_balance_below_zero(
        self, adjustment_service: AdjustmentService
    ) -> None:
        """測試餘額低於零的錯誤映射為 ValidationError。"""
        mock_error = MagicMock(spec=asyncpg.PostgresError)
        mock_error.__str__ = lambda self: "cannot drop below zero"

        result = adjustment_service._handle_postgres_error(mock_error)

        assert isinstance(result, Err)
        assert isinstance(result.error, ValidationError)
        assert "cannot drop below zero" in str(result.error).lower()

    def test_handle_postgres_error_other_error(self, adjustment_service: AdjustmentService) -> None:
        """測試其他 PostgresError 映射為 DatabaseError。"""
        mock_error = MagicMock(spec=asyncpg.PostgresError)
        mock_error.__str__ = lambda self: "some other database error"

        with patch("src.bot.services.adjustment_service.LOGGER"):
            result = adjustment_service._handle_postgres_error(mock_error)

        assert isinstance(result, Err)
        assert isinstance(result.error, DatabaseError)

    @pytest.mark.asyncio
    async def test_legacy_mode_postgres_error_raises_validation(
        self,
        mock_pool: MagicMock,
        mock_gateway: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """測試傳統模式下 PostgresError 會拋出 ValidationError。"""
        mock_error = MagicMock(spec=asyncpg.PostgresError)
        mock_error.__str__ = lambda self: "cannot drop below zero"

        db_error = DatabaseError("Database error")
        db_error.cause = mock_error
        mock_gateway.adjust_balance = AsyncMock(return_value=Err(db_error))

        service = AdjustmentService(mock_pool, gateway=mock_gateway)

        with pytest.raises(ValidationError) as exc_info:
            await service.adjust_balance(
                guild_id=12345,
                admin_id=67890,
                target_id=11111,
                amount=-5000,
                reason="測試調整",
                can_adjust=True,
                connection=mock_connection,
            )

        assert "cannot drop below zero" in str(exc_info.value).lower()


# --- Test Helper Methods ---


class TestHelperMethods:
    """測試輔助方法。"""

    def test_to_result(self, adjustment_service: AdjustmentService) -> None:
        """測試 _to_result 方法。"""
        mock_record = MockAdjustmentProcedureResult(
            new_balance=5000,
            prev_balance=10000,
            adjustment_id="test-id",
        )

        with patch(
            "src.bot.services.adjustment_service.adjustment_result_from_procedure"
        ) as mock_from_procedure:
            mock_adjustment = MagicMock(spec=AdjustmentResult)
            mock_from_procedure.return_value = mock_adjustment

            result = adjustment_service._to_result(mock_record)

            mock_from_procedure.assert_called_once_with(mock_record)
            assert result == mock_adjustment

    def test_exception_to_result_unauthorized(self, adjustment_service: AdjustmentService) -> None:
        """測試 _exception_to_result 處理 UnauthorizedAdjustmentError。"""
        exc = UnauthorizedAdjustmentError("No permission")
        result = adjustment_service._exception_to_result(exc)

        assert isinstance(result, Err)
        assert isinstance(result.error, DatabaseError)
        assert "UnauthorizedAdjustmentError" in result.error.context.get("original_exception", "")

    def test_exception_to_result_validation(self, adjustment_service: AdjustmentService) -> None:
        """測試 _exception_to_result 處理 ValidationError。"""
        exc = ValidationError("Invalid input")
        result = adjustment_service._exception_to_result(exc)

        assert isinstance(result, Err)
        assert isinstance(result.error, DatabaseError)
        assert "ValidationError" in result.error.context.get("original_exception", "")

    def test_exception_to_result_generic(self, adjustment_service: AdjustmentService) -> None:
        """測試 _exception_to_result 處理一般例外。"""
        exc = RuntimeError("Unexpected error")
        result = adjustment_service._exception_to_result(exc)

        assert isinstance(result, Err)
        assert isinstance(result.error, DatabaseError)
        assert "RuntimeError" in result.error.context.get("original_exception", "")
        assert "Unexpected error" in str(result.error)


# --- Test Edge Cases ---


class TestEdgeCases:
    """測試邊界情況。"""

    @pytest.mark.asyncio
    async def test_positive_adjustment(
        self,
        mock_pool: MagicMock,
        mock_gateway: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """測試正數調整（增加餘額）。"""
        mock_result = MockAdjustmentProcedureResult(
            new_balance=15000,
            prev_balance=10000,
        )
        mock_gateway.adjust_balance = AsyncMock(return_value=Ok(mock_result))

        service = AdjustmentService(mock_pool, gateway=mock_gateway)

        with patch.object(service, "_to_result", return_value=MagicMock(spec=AdjustmentResult)):
            result = await service.adjust_balance(
                guild_id=12345,
                admin_id=67890,
                target_id=11111,
                amount=5000,  # 正數調整
                reason="獎勵",
                can_adjust=True,
                connection=mock_connection,
            )

        assert result is not None
        mock_gateway.adjust_balance.assert_called_once()

    @pytest.mark.asyncio
    async def test_negative_adjustment(
        self,
        mock_pool: MagicMock,
        mock_gateway: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """測試負數調整（減少餘額）。"""
        mock_result = MockAdjustmentProcedureResult(
            new_balance=5000,
            prev_balance=10000,
        )
        mock_gateway.adjust_balance = AsyncMock(return_value=Ok(mock_result))

        service = AdjustmentService(mock_pool, gateway=mock_gateway)

        with patch.object(service, "_to_result", return_value=MagicMock(spec=AdjustmentResult)):
            result = await service.adjust_balance(
                guild_id=12345,
                admin_id=67890,
                target_id=11111,
                amount=-5000,  # 負數調整
                reason="罰款",
                can_adjust=True,
                connection=mock_connection,
            )

        assert result is not None
        mock_gateway.adjust_balance.assert_called_once()

    @pytest.mark.asyncio
    async def test_large_amount_adjustment(
        self,
        mock_pool: MagicMock,
        mock_gateway: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """測試大金額調整。"""
        mock_result = MockAdjustmentProcedureResult(
            new_balance=1000000000,
            prev_balance=0,
        )
        mock_gateway.adjust_balance = AsyncMock(return_value=Ok(mock_result))

        service = AdjustmentService(mock_pool, gateway=mock_gateway)

        with patch.object(service, "_to_result", return_value=MagicMock(spec=AdjustmentResult)):
            result = await service.adjust_balance(
                guild_id=12345,
                admin_id=67890,
                target_id=11111,
                amount=1000000000,  # 大金額
                reason="大額調整",
                can_adjust=True,
                connection=mock_connection,
            )

        assert result is not None

    @pytest.mark.asyncio
    async def test_gateway_returns_err(
        self,
        mock_pool: MagicMock,
        mock_gateway: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """測試 gateway 返回錯誤時的處理。"""
        mock_gateway.adjust_balance = AsyncMock(
            return_value=Err(DatabaseError("Connection failed"))
        )

        service = AdjustmentService(mock_pool, gateway=mock_gateway)

        with pytest.raises(DatabaseError):
            await service.adjust_balance(
                guild_id=12345,
                admin_id=67890,
                target_id=11111,
                amount=-5000,
                reason="測試調整",
                can_adjust=True,
                connection=mock_connection,
            )


if __name__ == "__main__":
    pytest.main([__file__])
