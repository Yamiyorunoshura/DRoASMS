"""
測試國土安全部權限檢查功能
"""

from unittest.mock import AsyncMock

import pytest

from src.bot.services.permission_service import (
    HomelandSecurityPermissionChecker,
)


@pytest.fixture
def mock_state_council_service():
    """模擬國務院服務"""
    service = AsyncMock()
    return service


@pytest.fixture
def homeland_security_checker(mock_state_council_service):
    """國土安全部權限檢查器"""
    return HomelandSecurityPermissionChecker(mock_state_council_service)


@pytest.mark.asyncio
async def test_homeland_security_permission_with_department_role(
    homeland_security_checker, mock_state_council_service
):
    """測試具備國土安全部身分組時的權限檢查"""
    # 設定模擬
    mock_state_council_service.check_department_permission.return_value = True
    mock_state_council_service.check_leader_permission.return_value = False

    # 執行測試
    result = await homeland_security_checker.check_permission(
        guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation="panel_access"
    )

    # 驗證結果
    assert result.allowed is True
    assert result.permission_level == "department_head"
    assert result.reason == "具備國土安全部權限"

    # 驗證調用
    mock_state_council_service.check_department_permission.assert_called_once_with(
        guild_id=12345, user_id=67890, department="國土安全部", user_roles=[11111, 22222]
    )


@pytest.mark.asyncio
async def test_homeland_security_permission_with_leader_role(
    homeland_security_checker, mock_state_council_service
):
    """測試具備國務院領導身分組時的權限檢查"""
    # 設定模擬
    mock_state_council_service.check_department_permission.return_value = False
    mock_state_council_service.check_leader_permission.return_value = True

    # 執行測試
    result = await homeland_security_checker.check_permission(
        guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation="panel_access"
    )

    # 驗證結果
    assert result.allowed is True
    assert result.permission_level == "leader"
    assert result.reason == "具備國務院領導權限"


@pytest.mark.asyncio
async def test_homeland_security_permission_without_permission(
    homeland_security_checker, mock_state_council_service
):
    """測試不具備國土安全部權限時的檢查"""
    # 設定模擬
    mock_state_council_service.check_department_permission.return_value = False
    mock_state_council_service.check_leader_permission.return_value = False

    # 執行測試
    result = await homeland_security_checker.check_permission(
        guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation="panel_access"
    )

    # 驗證結果
    assert result.allowed is False
    assert result.permission_level is None
    assert result.reason == "不具備國土安全部權限"


@pytest.mark.asyncio
async def test_homeland_security_different_operations(
    homeland_security_checker, mock_state_council_service
):
    """測試不同操作類型的權限檢查"""
    # 設定模擬
    mock_state_council_service.check_department_permission.return_value = True
    mock_state_council_service.check_leader_permission.return_value = False

    operations = ["panel_access", "arrest", "release", "suspect_management"]

    for operation in operations:
        result = await homeland_security_checker.check_permission(
            guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation=operation
        )

        assert result.allowed is True
        assert result.permission_level == "department_head"
        assert result.reason == "具備國土安全部權限"


@pytest.mark.asyncio
async def test_homeland_security_unknown_operation(
    homeland_security_checker, mock_state_council_service
):
    """測試未知操作類型的權限檢查"""
    # 設定模擬
    mock_state_council_service.check_department_permission.return_value = True
    mock_state_council_service.check_leader_permission.return_value = False

    # 執行測試
    result = await homeland_security_checker.check_permission(
        guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation="unknown_operation"
    )

    # 驗證結果
    assert result.allowed is False
    assert result.reason == "未知的操作類型: unknown_operation"


@pytest.mark.asyncio
async def test_homeland_security_permission_error_handling(
    homeland_security_checker, mock_state_council_service
):
    """測試權限檢查時的錯誤處理"""
    # 設定模擬拋出異常
    mock_state_council_service.check_department_permission.side_effect = Exception("資料庫錯誤")

    # 執行測試
    result = await homeland_security_checker.check_permission(
        guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation="panel_access"
    )

    # 驗證結果
    assert result.allowed is False
    assert result.reason == "權限檢查失敗"
