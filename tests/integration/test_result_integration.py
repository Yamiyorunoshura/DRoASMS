"""
測試 Result 模式在 Gateway 和服務層的集成。
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.bot.services.balance_service import BalanceService
from src.db.gateway.economy_queries import EconomyQueryGateway


@pytest.mark.asyncio
class TestResultIntegration:
    """測試 Result 模式的端到端集成。"""

    async def test_gateway_returns_result_on_success(self):
        """測試 Gateway 在成功時返回 Ok Result。"""
        # 準備
        mock_connection = AsyncMock()
        mock_record = {
            "guild_id": 12345,
            "member_id": 67890,
            "balance": 1000,
            "last_modified_at": datetime.now(),
            "throttled_until": None,
        }
        mock_connection.fetchrow.return_value = mock_record

        gateway = EconomyQueryGateway()

        # 執行
        result = await gateway.fetch_balance(
            mock_connection,
            guild_id=12345,
            member_id=67890,
        )

        # 驗證
        assert hasattr(result, "is_ok")
        assert hasattr(result, "is_err")
        assert result.is_ok()
        balance = result.unwrap()
        assert balance.guild_id == 12345
        assert balance.member_id == 67890
        assert balance.balance == 1000

    async def test_gateway_returns_result_on_failure(self):
        """測試 Gateway 在失敗時返回 Err Result。"""
        # 準備
        mock_connection = AsyncMock()
        mock_connection.fetchrow.return_value = None  # 模擬資料庫返回無結果

        gateway = EconomyQueryGateway()

        # 執行
        result = await gateway.fetch_balance(
            mock_connection,
            guild_id=12345,
            member_id=67890,
        )

        # 驗證
        assert hasattr(result, "is_ok")
        assert hasattr(result, "is_err")
        assert result.is_err()
        error = result.unwrap_err()
        assert type(error).__name__ == "DatabaseError"
        assert "fn_get_balance returned no result" in error.message

    async def test_service_handles_result_correctly(self):
        """測試服務層正確處理 Gateway 的 Result。"""
        # 準備
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        mock_record = {
            "guild_id": 12345,
            "member_id": 67890,
            "balance": 1000,
            "last_modified_at": datetime.now(),
            "throttled_until": None,
        }
        mock_connection.fetchrow.return_value = mock_record

        service = BalanceService(mock_pool)

        # 執行
        result = await service.get_balance_snapshot(
            guild_id=12345,
            requester_id=67890,
            target_member_id=67890,
            can_view_others=False,
            connection=None,
        )

        # 驗證
        assert hasattr(result, "is_ok")
        assert hasattr(result, "is_err")
        assert result.is_ok()
        snapshot = result.unwrap()
        assert snapshot.member_id == 67890
        assert snapshot.balance == 1000

    async def test_service_propagates_gateway_errors(self):
        """測試服務層正確傳播 Gateway 錯誤。"""
        # 準備
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None  # 模擬資料庫錯誤

        service = BalanceService(mock_pool)

        # 執行
        result = await service.get_balance_snapshot(
            guild_id=12345,
            requester_id=67890,
            target_member_id=67890,
            can_view_others=False,
            connection=None,
        )

        # 驗證
        assert hasattr(result, "is_ok")
        assert hasattr(result, "is_err")
        assert result.is_err()
        error = result.unwrap_err()
        assert type(error).__name__ == "DatabaseError"

    async def test_service_handles_permission_errors(self):
        """測試服務層正確處理權限錯誤。"""
        # 準備
        mock_pool = AsyncMock()
        service = BalanceService(mock_pool)

        # 執行 - 嘗試查看其他成員但沒有權限
        result = await service.get_balance_snapshot(
            guild_id=12345,
            requester_id=11111,
            target_member_id=22222,  # 不同的成員
            can_view_others=False,  # 沒有權限
            connection=None,
        )

        # 驗證 - 權限錯誤應該被轉換為 DatabaseError
        assert hasattr(result, "is_ok")
        assert hasattr(result, "is_err")
        assert result.is_err()
        error = result.unwrap_err()
        assert type(error).__name__ == "DatabaseError"
        assert "BalancePermissionError" in error.context.get("original_exception", "")
