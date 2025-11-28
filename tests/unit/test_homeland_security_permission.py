"""
測試國土安全部權限檢查功能（Result 版）。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.services.permission_service import HomelandSecurityPermissionChecker
from src.bot.services.state_council_service import StateCouncilService
from src.infra.result import DatabaseError, Err, Ok


@pytest.mark.asyncio
async def test_homeland_security_permission_with_department_role(
    homeland_security_checker: HomelandSecurityPermissionChecker,
    mock_state_council_service: MagicMock,
):
    """測試具備國土安全部身分組時的權限檢查"""
    # 設定模擬（Result 版：部門有權限、非領導）
    mock_state_council_service.check_department_permission.return_value = Ok(True)
    mock_state_council_service.check_leader_permission.return_value = Ok(False)

    result = await homeland_security_checker.check_permission(
        guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation="panel_access"
    )

    # 驗證結果（Result 版）
    assert isinstance(result, Ok)
    permission = result.value
    assert permission.allowed is True
    assert permission.permission_level == "department_head"
    assert permission.reason == "具備國土安全部權限"

    # 驗證調用（StateCouncilService 介面）
    mock_state_council_service.check_department_permission.assert_called_once_with(
        guild_id=12345, user_id=67890, department="國土安全部", user_roles=[11111, 22222]
    )


@pytest.mark.asyncio
async def test_homeland_security_permission_with_leader_role(
    homeland_security_checker, mock_state_council_service
):
    """測試具備國務院領導身分組時的權限檢查"""
    # 設定模擬（Result 版：僅領導有權限）
    mock_state_council_service.check_department_permission.return_value = Ok(False)
    mock_state_council_service.check_leader_permission.return_value = Ok(True)

    result = await homeland_security_checker.check_permission(
        guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation="panel_access"
    )

    assert isinstance(result, Ok)
    permission = result.value
    assert permission.allowed is True
    assert permission.permission_level == "leader"
    assert permission.reason == "具備國務院領導權限"


@pytest.mark.asyncio
async def test_homeland_security_permission_without_permission(
    homeland_security_checker: HomelandSecurityPermissionChecker,
    mock_state_council_service: MagicMock,
):
    """測試不具備國土安全部權限時的檢查"""
    # 設定模擬（Result 版：沒有部門與領導權限）
    mock_state_council_service.check_department_permission.return_value = Ok(False)
    mock_state_council_service.check_leader_permission.return_value = Ok(False)

    result = await homeland_security_checker.check_permission(
        guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation="panel_access"
    )

    assert isinstance(result, Ok)
    permission = result.value
    assert permission.allowed is False
    assert permission.permission_level is None
    assert permission.reason == "不具備國土安全部權限"


@pytest.mark.asyncio
async def test_homeland_security_different_operations(
    homeland_security_checker: HomelandSecurityPermissionChecker,
    mock_state_council_service: MagicMock,
):
    """測試不同操作類型的權限檢查"""
    # 設定模擬：部門有權限、非領導
    mock_state_council_service.check_department_permission.return_value = Ok(True)
    mock_state_council_service.check_leader_permission.return_value = Ok(False)

    operations = ["panel_access", "arrest", "release", "suspect_management"]

    for operation in operations:
        result = await homeland_security_checker.check_permission(
            guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation=operation
        )

        assert isinstance(result, Ok)
        permission = result.value
        assert permission.allowed is True
        assert permission.permission_level == "department_head"
        assert permission.reason == "具備國土安全部權限"


@pytest.mark.asyncio
async def test_homeland_security_unknown_operation(
    homeland_security_checker: HomelandSecurityPermissionChecker,
    mock_state_council_service: MagicMock,
):
    """測試未知操作類型的權限檢查"""
    # 設定模擬：部門有權限，但操作類型未知
    mock_state_council_service.check_department_permission.return_value = Ok(True)
    mock_state_council_service.check_leader_permission.return_value = Ok(False)

    result = await homeland_security_checker.check_permission(
        guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation="unknown_operation"
    )

    assert isinstance(result, Ok)
    permission = result.value
    assert permission.allowed is False
    assert permission.reason == "未知的操作類型: unknown_operation"


@pytest.mark.asyncio
async def test_homeland_security_permission_error_handling(
    homeland_security_checker: HomelandSecurityPermissionChecker,
    mock_state_council_service: MagicMock,
):
    """測試權限檢查時的錯誤處理"""
    # 設定模擬：部門權限檢查回傳資料庫錯誤（Result 版）
    mock_state_council_service.check_department_permission.return_value = Err(
        DatabaseError("資料庫錯誤")
    )
    mock_state_council_service.check_leader_permission.return_value = Ok(False)

    result = await homeland_security_checker.check_permission(
        guild_id=12345, user_id=67890, user_roles=[11111, 22222], operation="panel_access"
    )

    # 錯誤情況應該以 Err 回傳
    assert isinstance(result, Err)
    error = result.error
    assert isinstance(error, DatabaseError)


@pytest.fixture
def mock_state_council_service() -> MagicMock:
    """模擬國務院 Result 版服務"""
    service = MagicMock(spec=StateCouncilService)
    service.check_leader_permission = AsyncMock()
    service.check_department_permission = AsyncMock()
    return service


@pytest.fixture
def homeland_security_checker(
    mock_state_council_service: MagicMock,
) -> HomelandSecurityPermissionChecker:
    """國土安全部權限檢查器"""
    return HomelandSecurityPermissionChecker(mock_state_council_service)
