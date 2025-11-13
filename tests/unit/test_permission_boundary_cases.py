"""
權限邊界情況和錯誤處理測試。

測試各種權限檢查的邊界情況，包括：
- 空身分組列表
- 無效的身分組ID
- 網絡錯誤和數據庫錯誤
- 配置缺失情況
- 並發訪問情況
"""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.services.council_service import CouncilService
from src.bot.services.permission_service import (
    CouncilPermissionChecker,
    StateCouncilPermissionChecker,
    SupremePeoplesAssemblyPermissionChecker,
)
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.supreme_assembly_service import SupremeAssemblyService


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


@pytest.mark.unit
class TestPermissionBoundaryCases:
    """測試權限檢查的邊界情況"""

    @pytest.fixture
    def mock_council_service(self) -> MagicMock:
        """創建模擬的 CouncilService。"""
        service = MagicMock(spec=CouncilService)
        service.get_config = AsyncMock()
        service.get_council_role_ids = AsyncMock()
        return service

    @pytest.fixture
    def mock_state_council_service(self) -> MagicMock:
        """創建模擬的 StateCouncilService。"""
        service = MagicMock(spec=StateCouncilService)
        service.check_leader_permission = AsyncMock()
        service.check_department_permission = AsyncMock()
        return service

    @pytest.fixture
    def mock_supreme_assembly_service(self) -> MagicMock:
        """創建模擬的 SupremeAssemblyService。"""
        service = MagicMock(spec=SupremeAssemblyService)
        service.get_config = AsyncMock()
        return service

    # 測試空身分組列表
    @pytest.mark.asyncio
    async def test_empty_user_roles_council(self, mock_council_service: MagicMock) -> None:
        """測試常任理事會空身分組列表"""
        checker = CouncilPermissionChecker(mock_council_service)

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.council_role_id = 123
        mock_council_service.get_config.return_value = mock_config
        mock_council_service.get_council_role_ids.return_value = [456, 789]

        result = await checker.check_permission(
            guild_id=12345, user_id=67890, user_roles=[], operation="panel_access"  # 空身分組列表
        )

        assert result.allowed is False
        assert "不具備常任理事身分組" in result.reason

    @pytest.mark.asyncio
    async def test_empty_user_roles_supreme_assembly(
        self, mock_supreme_assembly_service: MagicMock
    ) -> None:
        """測試最高議會空身分組列表"""
        checker = SupremePeoplesAssemblyPermissionChecker(mock_supreme_assembly_service)

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_supreme_assembly_service.get_config.return_value = mock_config

        result = await checker.check_permission(
            guild_id=12345, user_id=67890, user_roles=[], operation="panel_access"  # 空身分組列表
        )

        assert result.allowed is False
        assert "不具備議長或人民代表身分組" in result.reason

    # 測試配置缺失情況
    @pytest.mark.asyncio
    async def test_missing_config_council(self, mock_council_service: MagicMock) -> None:
        """測試常任理事會配置缺失"""
        from src.bot.services.supreme_assembly_service import GovernanceNotConfiguredError

        checker = CouncilPermissionChecker(mock_council_service)
        mock_council_service.get_config.side_effect = GovernanceNotConfiguredError("未配置")

        result = await checker.check_permission(
            guild_id=12345, user_id=67890, user_roles=[123], operation="panel_access"
        )

        assert result.allowed is False
        assert result.reason == "權限檢查失敗"

    @pytest.mark.asyncio
    async def test_missing_config_supreme_assembly(
        self, mock_supreme_assembly_service: MagicMock
    ) -> None:
        """測試最高議會配置缺失"""
        from src.bot.services.supreme_assembly_service import GovernanceNotConfiguredError

        checker = SupremePeoplesAssemblyPermissionChecker(mock_supreme_assembly_service)
        mock_supreme_assembly_service.get_config.side_effect = GovernanceNotConfiguredError(
            "未配置"
        )

        result = await checker.check_permission(
            guild_id=12345, user_id=67890, user_roles=[123], operation="panel_access"
        )

        assert result.allowed is False
        assert result.reason == "權限檢查失敗"

    # 測試網絡錯誤
    @pytest.mark.asyncio
    async def test_network_error_council(self, mock_council_service: MagicMock) -> None:
        """測試常任理事會網絡錯誤"""
        checker = CouncilPermissionChecker(mock_council_service)
        mock_council_service.get_config.side_effect = ConnectionError("網絡錯誤")

        result = await checker.check_permission(
            guild_id=12345, user_id=67890, user_roles=[123], operation="panel_access"
        )

        assert result.allowed is False
        assert result.reason == "權限檢查失敗"

    # 測試數據庫錯誤
    @pytest.mark.asyncio
    async def test_database_error_state_council(
        self, mock_state_council_service: MagicMock
    ) -> None:
        """測試國務院數據庫錯誤"""
        checker = StateCouncilPermissionChecker(mock_state_council_service)
        mock_state_council_service.check_leader_permission.side_effect = Exception("數據庫錯誤")

        result = await checker.check_permission(
            guild_id=12345, user_id=67890, user_roles=[123], operation="panel_access"
        )

        assert result.allowed is False
        assert result.reason == "權限檢查失敗"

    # 測試無效的身分組ID
    @pytest.mark.asyncio
    async def test_invalid_role_ids(self, mock_supreme_assembly_service: MagicMock) -> None:
        """測試無效的身分組ID"""
        checker = SupremePeoplesAssemblyPermissionChecker(mock_supreme_assembly_service)

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123  # 有效ID
        mock_config.member_role_id = 456  # 有效ID
        mock_supreme_assembly_service.get_config.return_value = mock_config

        result = await checker.check_permission(
            guild_id=12345,
            user_id=67890,
            user_roles=[999, 888],  # 不匹配的有效ID
            operation="panel_access",
        )

        assert result.allowed is False
        assert "不具備議長或人民代表身分組" in result.reason

    # 測試極大的身分組ID
    @pytest.mark.asyncio
    async def test_extreme_role_ids(self, mock_supreme_assembly_service: MagicMock) -> None:
        """測試極大的身分組ID"""
        checker = SupremePeoplesAssemblyPermissionChecker(mock_supreme_assembly_service)

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 2**63 - 1  # 最大可能ID
        mock_config.member_role_id = 2**63 - 2
        mock_supreme_assembly_service.get_config.return_value = mock_config

        result = await checker.check_permission(
            guild_id=12345,
            user_id=67890,
            user_roles=[2**63 - 1],  # 最大ID
            operation="panel_access",
        )

        assert result.allowed is True
        assert result.permission_level == "speaker"

    # 測試重複的身分組
    @pytest.mark.asyncio
    async def test_duplicate_roles(self, mock_supreme_assembly_service: MagicMock) -> None:
        """測試重複的身分組"""
        checker = SupremePeoplesAssemblyPermissionChecker(mock_supreme_assembly_service)

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_supreme_assembly_service.get_config.return_value = mock_config

        result = await checker.check_permission(
            guild_id=12345,
            user_id=67890,
            user_roles=[123, 123, 456, 456],  # 重複的身分組
            operation="panel_access",
        )

        assert result.allowed is True
        assert result.permission_level == "speaker"

    # 測試超長操作字符串
    @pytest.mark.asyncio
    async def test_extremely_long_operation(self, mock_supreme_assembly_service: MagicMock) -> None:
        """測試超長的操作字符串"""
        checker = SupremePeoplesAssemblyPermissionChecker(mock_supreme_assembly_service)

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_supreme_assembly_service.get_config.return_value = mock_config

        long_operation = "a" * 1000  # 1000字符的操作名稱

        result = await checker.check_permission(
            guild_id=12345, user_id=67890, user_roles=[123], operation=long_operation
        )

        assert result.allowed is False
        assert "未知的操作類型" in result.reason

    # 測試特殊字符操作
    @pytest.mark.asyncio
    async def test_special_character_operations(
        self, mock_supreme_assembly_service: MagicMock
    ) -> None:
        """測試包含特殊字符的操作"""
        checker = SupremePeoplesAssemblyPermissionChecker(mock_supreme_assembly_service)

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_supreme_assembly_service.get_config.return_value = mock_config

        special_operations = [
            "panel_access\n\r\t",
            "panel_access\x00\x01",
            "panel_access<script>",
            "panel_access' OR '1'='1",
            "面板訪問",  # 中文字符
            "🎭panel_access",  # emoji
        ]

        for operation in special_operations:
            result = await checker.check_permission(
                guild_id=12345, user_id=67890, user_roles=[123], operation=operation
            )

            assert result.allowed is False
            assert "未知的操作類型" in result.reason

    # 測試極端guild_id和user_id
    @pytest.mark.asyncio
    async def test_extreme_ids(self, mock_supreme_assembly_service: MagicMock) -> None:
        """測試極端的guild_id和user_id"""
        checker = SupremePeoplesAssemblyPermissionChecker(mock_supreme_assembly_service)

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_supreme_assembly_service.get_config.return_value = mock_config

        extreme_cases = [
            (0, 0),  # 最小值
            (2**63 - 1, 2**63 - 1),  # 最大值
            (-1, -1),  # 負數
            (12345, 67890),  # 正常值
        ]

        for guild_id, user_id in extreme_cases:
            result = await checker.check_permission(
                guild_id=guild_id, user_id=user_id, user_roles=[123], operation="panel_access"
            )

            # 即使ID極端，只要有權限就應該通過
            if guild_id > 0 and user_id > 0:
                assert result.allowed is True

    # 測試超時情況
    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_supreme_assembly_service: MagicMock) -> None:
        """測試超時處理"""
        import asyncio

        checker = SupremePeoplesAssemblyPermissionChecker(mock_supreme_assembly_service)

        # 設定模擬配置，讓get_config超時
        async def slow_config(*args, **kwargs):
            await asyncio.sleep(10)  # 模擬長時間操作
            return MagicMock()

        mock_supreme_assembly_service.get_config.side_effect = slow_config

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                checker.check_permission(
                    guild_id=12345, user_id=67890, user_roles=[123], operation="panel_access"
                ),
                timeout=1.0,  # 1秒超時
            )
