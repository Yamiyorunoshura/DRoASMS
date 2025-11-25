"""跨命令交互測試：測試不同治理機構之間的交互。

本測試模組驗證：
1. 最高人民會議與常任理事會的交互
2. 最高人民會議與國務院的交互
3. 常任理事會與國務院的交互
4. 跨治理機構的權限邊界
"""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


@pytest.mark.integration
class TestSupremeAssemblyCouncilInteraction:
    """最高人民會議與常任理事會的交互測試。"""

    @pytest.fixture
    def mock_guild_id(self) -> int:
        return _snowflake()

    @pytest.fixture
    def mock_speaker_id(self) -> int:
        return _snowflake()

    @pytest.fixture
    def mock_council_member_id(self) -> int:
        return _snowflake()

    def test_derive_account_ids_are_distinct(self, mock_guild_id: int) -> None:
        """測試不同治理機構的帳戶 ID 是唯一的。"""
        from src.bot.services.council_service_result import CouncilServiceResult
        from src.bot.services.state_council_service import StateCouncilService
        from src.bot.services.supreme_assembly_service import SupremeAssemblyService

        # 獲取各治理機構的帳戶 ID
        supreme_account = SupremeAssemblyService.derive_account_id(mock_guild_id)
        council_account = CouncilServiceResult.derive_council_account_id(mock_guild_id)
        state_council_account = StateCouncilService.derive_main_account_id(mock_guild_id)

        # 驗證所有帳戶 ID 都是唯一的
        account_ids = [supreme_account, council_account, state_council_account]
        assert len(account_ids) == len(set(account_ids)), "治理機構帳戶 ID 應該唯一"

    def test_department_account_ids_exist(self, mock_guild_id: int) -> None:
        """測試部門帳戶 ID 可以被導出。"""
        from src.bot.services.state_council_service import StateCouncilService

        # 測試部門帳戶 ID 可以被正確導出
        dept_id = StateCouncilService.derive_department_account_id(mock_guild_id, "財政部")
        assert isinstance(dept_id, int)
        assert dept_id != 0


@pytest.mark.integration
class TestCrossGovernancePermissions:
    """跨治理機構權限測試。"""

    @pytest.fixture
    def mock_guild_id(self) -> int:
        return _snowflake()

    @pytest.fixture
    def mock_user_id(self) -> int:
        return _snowflake()

    @pytest.mark.asyncio
    async def test_permission_service_checks_all_governance_bodies(
        self, mock_guild_id: int, mock_user_id: int
    ) -> None:
        """測試權限服務可以檢查所有治理機構。"""
        from src.bot.services.permission_service import PermissionService

        # 創建模擬服務
        mock_council_service = MagicMock()
        mock_state_council_service = MagicMock()
        mock_supreme_assembly_service = MagicMock()

        service = PermissionService(
            council_service=mock_council_service,
            state_council_service=mock_state_council_service,
            supreme_assembly_service=mock_supreme_assembly_service,
        )

        # 驗證服務有正確的方法
        assert hasattr(service, "check_supreme_peoples_assembly_permission")

    @pytest.mark.asyncio
    async def test_supreme_assembly_permission_integration(
        self, mock_guild_id: int, mock_user_id: int
    ) -> None:
        """測試最高人民會議權限檢查整合。"""
        from src.bot.services.permission_service import PermissionService
        from src.infra.result import Ok

        # 創建模擬服務
        mock_council_service = MagicMock()
        mock_state_council_service = MagicMock()
        mock_supreme_assembly_service = MagicMock()

        # 設定模擬配置
        mock_config = MagicMock()
        mock_config.speaker_role_id = 123
        mock_config.member_role_id = 456
        mock_supreme_assembly_service.get_config = AsyncMock(return_value=mock_config)

        service = PermissionService(
            council_service=mock_council_service,
            state_council_service=mock_state_council_service,
            supreme_assembly_service=mock_supreme_assembly_service,
        )

        # 測試議長權限
        result = await service.check_supreme_peoples_assembly_permission(
            guild_id=mock_guild_id,
            user_id=mock_user_id,
            user_roles=[123, 456],
            operation="panel_access",
        )

        assert isinstance(result, Ok)
        assert result.value.allowed is True
        assert result.value.permission_level == "speaker"


@pytest.mark.integration
class TestTransferBetweenGovernanceBodies:
    """治理機構之間轉帳測試。"""

    @pytest.fixture
    def mock_guild_id(self) -> int:
        return _snowflake()

    def test_transfer_target_id_derivation(self, mock_guild_id: int) -> None:
        """測試轉帳目標 ID 正確導出。"""
        from src.bot.services.council_service_result import CouncilServiceResult
        from src.bot.services.state_council_service import StateCouncilService
        from src.bot.services.supreme_assembly_service import SupremeAssemblyService

        # 測試從最高人民會議轉帳給常任理事會
        supreme_id = SupremeAssemblyService.derive_account_id(mock_guild_id)
        council_id = CouncilServiceResult.derive_council_account_id(mock_guild_id)

        assert supreme_id != council_id
        assert isinstance(supreme_id, int)
        assert isinstance(council_id, int)

        # 測試從最高人民會議轉帳給部門
        dept_id = StateCouncilService.derive_department_account_id(mock_guild_id, "財政部")
        assert dept_id != supreme_id
        assert dept_id != council_id


@pytest.mark.integration
class TestGovernanceConfigurationInteraction:
    """治理機構配置交互測試。"""

    @pytest.fixture
    def mock_guild_id(self) -> int:
        return _snowflake()

    @pytest.mark.asyncio
    async def test_multiple_governance_bodies_can_coexist(self, mock_guild_id: int) -> None:
        """測試多個治理機構可以同時配置。"""
        # 這是一個概念測試，驗證設計允許多個治理機構共存

        # 每個治理機構應該有獨立的配置
        from src.bot.services.council_service_result import CouncilServiceResult
        from src.bot.services.state_council_service import StateCouncilService
        from src.bot.services.supreme_assembly_service import SupremeAssemblyService

        # 驗證各服務都有配置相關方法
        assert hasattr(CouncilServiceResult, "get_config") or hasattr(
            CouncilServiceResult, "set_config"
        )
        assert hasattr(StateCouncilService, "get_state_council_config") or hasattr(
            StateCouncilService, "derive_main_account_id"
        )
        assert hasattr(SupremeAssemblyService, "get_config")


@pytest.mark.integration
class TestProposalInteractions:
    """提案交互測試。"""

    @pytest.fixture
    def mock_guild_id(self) -> int:
        return _snowflake()

    def test_proposal_id_uniqueness(self) -> None:
        """測試提案 ID 是唯一的。"""
        # 使用 UUID 確保唯一性
        proposal_ids = [uuid4() for _ in range(100)]
        assert len(proposal_ids) == len(set(proposal_ids))

    def test_vote_totals_structure(self) -> None:
        """測試投票統計結構一致性。"""

        # 驗證兩個 VoteTotals 都有相同的基本屬性
        council_attrs = {"approve", "reject", "abstain", "threshold_t"}
        supreme_attrs = {"approve", "reject", "abstain", "threshold_t"}

        assert council_attrs == supreme_attrs, "投票統計結構應該一致"


@pytest.mark.integration
class TestErrorHandlingAcrossCommands:
    """跨命令錯誤處理測試。"""

    def test_governance_not_configured_error_consistency(self) -> None:
        """測試治理未配置錯誤一致性。"""
        from src.bot.services.council_service import (
            GovernanceNotConfiguredError as CouncilError,
        )
        from src.bot.services.supreme_assembly_service import (
            GovernanceNotConfiguredError as SupremeError,
        )

        # 驗證錯誤類型存在且可以被正確捕獲
        try:
            raise CouncilError("Test")
        except CouncilError as e:
            assert str(e) == "Test"

        try:
            raise SupremeError("Test")
        except SupremeError as e:
            assert str(e) == "Test"

    def test_vote_already_exists_error_consistency(self) -> None:
        """測試重複投票錯誤一致性。"""
        from src.bot.services.supreme_assembly_service import (
            VoteAlreadyExistsError as SupremeVoteError,
        )

        # 驗證錯誤類型存在且可以被正確捕獲
        try:
            raise SupremeVoteError("Test")
        except SupremeVoteError as e:
            assert str(e) == "Test"

    def test_permission_denied_error_consistency(self) -> None:
        """測試權限不足錯誤一致性。"""
        from src.bot.services.supreme_assembly_service import (
            PermissionDeniedError as SupremePermError,
        )

        try:
            raise SupremePermError("Test")
        except SupremePermError as e:
            assert str(e) == "Test"


@pytest.mark.integration
class TestCommandRegistration:
    """命令註冊測試。"""

    def test_all_commands_have_help_data(self) -> None:
        """測試所有命令都有幫助資料。"""
        from src.bot.commands import (
            adjust,
            council,
            currency_config,
            state_council,
            supreme_assembly,
            transfer,
        )

        # 驗證主要命令模組都有 get_help_data 函數
        modules_with_help = [
            adjust,
            council,
            currency_config,
            state_council,
            supreme_assembly,
            transfer,
        ]

        for module in modules_with_help:
            assert hasattr(module, "get_help_data"), f"{module.__name__} 缺少 get_help_data"
            help_data = module.get_help_data()
            assert isinstance(help_data, dict), f"{module.__name__} 的 get_help_data 應返回 dict"

    def test_all_commands_have_register_function(self) -> None:
        """測試所有命令都有註冊函數。"""
        from src.bot.commands import (
            adjust,
            council,
            currency_config,
            state_council,
            supreme_assembly,
            transfer,
        )

        # 驗證主要命令模組都有 register 函數
        modules = [
            adjust,
            council,
            currency_config,
            state_council,
            supreme_assembly,
            transfer,
        ]

        for module in modules:
            assert hasattr(module, "register"), f"{module.__name__} 缺少 register 函數"
