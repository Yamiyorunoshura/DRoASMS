"""測試國務院面板視圖 (state_council.py StateCouncilPanelView)。

涵蓋範圍：
- 面板初始化與狀態
- 即時事件訂閱與更新
- 部門權限檢查
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.commands.state_council import (
    StateCouncilPanelView,
)
from src.bot.services.currency_config_service import CurrencyConfigResult, CurrencyConfigService
from src.bot.services.state_council_service import (
    StateCouncilService,
)
from src.infra.events.state_council_events import StateCouncilEvent

# --- Mock Objects ---


class MockStateCouncilConfig:
    """模擬國務院配置。"""

    def __init__(
        self,
        guild_id: int = 12345,
        leader_id: int = 67890,
        leader_role_id: int | None = 11111,
        citizen_role_id: int | None = 22222,
        suspect_role_id: int | None = 33333,
        internal_affairs_account_id: int = 44444,
        finance_account_id: int = 55555,
        security_account_id: int = 66666,
        central_bank_account_id: int = 77777,
        justice_account_id: int = 88888,
    ) -> None:
        self.guild_id = guild_id
        self.leader_id = leader_id
        self.leader_role_id = leader_role_id
        self.citizen_role_id = citizen_role_id
        self.suspect_role_id = suspect_role_id
        self.internal_affairs_account_id = internal_affairs_account_id
        self.finance_account_id = finance_account_id
        self.security_account_id = security_account_id
        self.central_bank_account_id = central_bank_account_id
        self.justice_account_id = justice_account_id


@pytest.fixture
def mock_state_council_service() -> MagicMock:
    """創建假 StateCouncilService。"""
    service = MagicMock(spec=StateCouncilService)
    service.get_config = AsyncMock(return_value=MockStateCouncilConfig())
    service.check_leader_permission = AsyncMock(return_value=False)
    service.check_department_permission = AsyncMock(return_value=False)
    service.ensure_government_accounts = AsyncMock()
    service.get_department_balance = AsyncMock(return_value=10000)
    service.issue_currency = AsyncMock()
    service.transfer_currency = AsyncMock()
    service.create_welfare_disbursement = AsyncMock()
    return service


@pytest.fixture
def mock_currency_config() -> MagicMock:
    """創建假貨幣配置。"""
    config = MagicMock(spec=CurrencyConfigResult)
    config.currency_name = "金幣"
    config.currency_icon = "💰"
    config.decimal_places = 0
    return config


@pytest.fixture
def mock_currency_service(mock_currency_config: MagicMock) -> MagicMock:
    """創建假 CurrencyConfigService。"""
    service = MagicMock(spec=CurrencyConfigService)
    service.get_currency_config = AsyncMock(return_value=mock_currency_config)
    return service


@pytest.fixture
def fake_guild() -> MagicMock:
    """創建假 Discord Guild。"""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 12345
    guild.name = "Test Guild"
    guild.get_member = MagicMock(return_value=None)
    guild.get_role = MagicMock(return_value=None)
    return guild


@pytest.fixture
def fake_message() -> MagicMock:
    """創建假 Discord Message。"""
    message = MagicMock(spec=discord.Message)
    message.id = 123456789
    message.edit = AsyncMock()
    return message


# --- Test StateCouncilPanelView Initialization ---


class TestStateCouncilPanelViewInit:
    """測試 StateCouncilPanelView 初始化。"""

    @pytest.mark.asyncio
    async def test_init_basic(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
    ) -> None:
        """測試基本初始化。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=67890,
            leader_id=67890,
            leader_role_id=11111,
            user_roles=[11111],
        )

        assert view.guild_id == 12345
        assert view.author_id == 67890
        assert view.leader_id == 67890
        assert view.leader_role_id == 11111
        assert view.current_page == "總覽"
        assert view.is_leader is True  # 作者是領袖

    @pytest.mark.asyncio
    async def test_init_non_leader(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
    ) -> None:
        """測試非領袖初始化。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=99999,  # 非領袖
            leader_id=67890,
            leader_role_id=11111,
            user_roles=[22222],  # 沒有領袖角色
        )

        assert view.is_leader is False

    @pytest.mark.asyncio
    async def test_init_leader_by_role(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
    ) -> None:
        """測試通過角色確認領袖。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=99999,  # 非領袖 ID
            leader_id=67890,
            leader_role_id=11111,
            user_roles=[11111],  # 有領袖角色
        )

        assert view.is_leader is True


# --- Test StateCouncilPanelView Event Subscription ---


class TestStateCouncilPanelViewSubscription:
    """測試事件訂閱功能。"""

    @pytest.mark.asyncio
    async def test_bind_message_subscribes_to_events(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
        fake_message: MagicMock,
    ) -> None:
        """測試綁定訊息時訂閱事件。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=67890,
            leader_id=67890,
            leader_role_id=None,
            user_roles=[],
        )

        mock_unsubscribe = AsyncMock()

        with patch(
            "src.bot.commands.state_council.subscribe_state_council_events",
            new_callable=AsyncMock,
            return_value=mock_unsubscribe,
        ) as mock_subscribe:
            await view.bind_message(fake_message)

        mock_subscribe.assert_called_once()
        assert view.message == fake_message
        assert view._unsubscribe == mock_unsubscribe

    @pytest.mark.asyncio
    async def test_bind_message_only_once(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
        fake_message: MagicMock,
    ) -> None:
        """測試只綁定一次訊息。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=67890,
            leader_id=67890,
            leader_role_id=None,
            user_roles=[],
        )

        with patch(
            "src.bot.commands.state_council.subscribe_state_council_events",
            new_callable=AsyncMock,
        ) as mock_subscribe:
            await view.bind_message(fake_message)
            await view.bind_message(fake_message)  # 第二次綁定

        # 只應該訂閱一次
        mock_subscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_subscription(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
        fake_message: MagicMock,
    ) -> None:
        """測試清理訂閱。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=67890,
            leader_id=67890,
            leader_role_id=None,
            user_roles=[],
        )

        mock_unsubscribe = AsyncMock()

        with patch(
            "src.bot.commands.state_council.subscribe_state_council_events",
            new_callable=AsyncMock,
            return_value=mock_unsubscribe,
        ):
            await view.bind_message(fake_message)

        await view._cleanup_subscription()

        mock_unsubscribe.assert_called_once()
        assert view.message is None
        assert view._unsubscribe is None


# --- Test StateCouncilPanelView Event Handling ---


class TestStateCouncilPanelViewEventHandling:
    """測試事件處理功能。"""

    @pytest.mark.asyncio
    async def test_handle_event_updates_message(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
        fake_message: MagicMock,
    ) -> None:
        """測試處理事件時更新訊息。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=67890,
            leader_id=67890,
            leader_role_id=None,
            user_roles=[],
        )
        view.message = fake_message

        event = StateCouncilEvent(
            guild_id=12345,
            kind="transfer",
            cause="user",
        )

        with patch.object(view, "refresh_options", new_callable=AsyncMock):
            with patch.object(view, "build_summary_embed", new_callable=AsyncMock) as mock_build:
                mock_embed = MagicMock(spec=discord.Embed)
                mock_build.return_value = mock_embed

                await view._handle_event(event)

        fake_message.edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_event_ignores_other_guilds(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
        fake_message: MagicMock,
    ) -> None:
        """測試忽略其他 guild 的事件。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=67890,
            leader_id=67890,
            leader_role_id=None,
            user_roles=[],
        )
        view.message = fake_message

        event = StateCouncilEvent(
            guild_id=99999,  # 不同 guild
            kind="transfer",
            cause="user",
        )

        with patch.object(view, "_apply_live_update", new_callable=AsyncMock) as mock_apply:
            await view._handle_event(event)

        mock_apply.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_event_ignores_when_no_message(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
    ) -> None:
        """測試無訊息時忽略事件。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=67890,
            leader_id=67890,
            leader_role_id=None,
            user_roles=[],
        )
        view.message = None

        event = StateCouncilEvent(
            guild_id=12345,
            kind="transfer",
            cause="user",
        )

        with patch.object(view, "_apply_live_update", new_callable=AsyncMock) as mock_apply:
            await view._handle_event(event)

        mock_apply.assert_not_called()


# --- Test StateCouncilPanelView Refresh Options ---


class TestStateCouncilPanelViewRefreshOptions:
    """測試選項刷新功能。"""

    @pytest.mark.asyncio
    async def test_refresh_options_leader(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
    ) -> None:
        """測試領袖刷新選項。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=67890,
            leader_id=67890,
            leader_role_id=None,
            user_roles=[],
        )
        view.is_leader = True

        await view.refresh_options()

        # 領袖應該可以訪問所有部門
        assert len(view._last_allowed_departments) == len(view.departments)

    @pytest.mark.asyncio
    async def test_refresh_options_department_permission(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
    ) -> None:
        """測試部門權限刷新選項。"""

        # 只允許財政部
        async def check_dept(
            guild_id: int, user_id: int, department: str, user_roles: list
        ) -> bool:
            return department == "財政部"

        mock_state_council_service.check_department_permission = AsyncMock(side_effect=check_dept)

        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=99999,  # 非領袖
            leader_id=67890,
            leader_role_id=11111,
            user_roles=[22222],  # 沒有領袖角色
        )
        view.is_leader = False

        await view.refresh_options()

        # 應該只有財政部
        assert "財政部" in view._last_allowed_departments


# --- Test StateCouncilPanelView Department Permissions ---


class TestStateCouncilPanelViewDeptPermissions:
    """測試部門權限檢查。"""

    @pytest.mark.asyncio
    async def test_has_department_permission_as_leader(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
    ) -> None:
        """測試領袖對所有部門都有權限。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=67890,
            leader_id=67890,
            leader_role_id=None,
            user_roles=[],
        )
        view.is_leader = True

        result = await view._has_department_permission("財政部")

        assert result is True

    @pytest.mark.asyncio
    async def test_has_department_permission_non_leader(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
    ) -> None:
        """測試非領袖的部門權限檢查。"""
        mock_state_council_service.check_department_permission = AsyncMock(return_value=True)

        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=99999,
            leader_id=67890,
            leader_role_id=11111,
            user_roles=[22222],
        )
        view.is_leader = False

        result = await view._has_department_permission("財政部")

        assert result is True
        mock_state_council_service.check_department_permission.assert_called_once()


# --- Test Allowed Departments Computation ---


class TestAllowedDepartmentsComputation:
    """測試允許部門計算。"""

    @pytest.mark.asyncio
    async def test_compute_allowed_departments_leader(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
    ) -> None:
        """測試領袖的允許部門計算。"""
        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=67890,
            leader_id=67890,
            leader_role_id=None,
            user_roles=[],
        )
        view.is_leader = True

        result = await view._compute_allowed_departments()

        assert result == list(view.departments)

    @pytest.mark.asyncio
    async def test_compute_allowed_departments_with_permissions(
        self,
        mock_state_council_service: MagicMock,
        mock_currency_service: MagicMock,
        fake_guild: MagicMock,
    ) -> None:
        """測試有部分權限的允許部門計算。"""

        # 只允許財政部和內政部
        async def check_dept(
            guild_id: int, user_id: int, department: str, user_roles: list
        ) -> bool:
            return department in ["財政部", "內政部"]

        mock_state_council_service.check_department_permission = AsyncMock(side_effect=check_dept)

        view = StateCouncilPanelView(
            service=mock_state_council_service,
            currency_service=mock_currency_service,
            guild=fake_guild,
            guild_id=12345,
            author_id=99999,
            leader_id=67890,
            leader_role_id=11111,
            user_roles=[22222],
        )
        view.is_leader = False

        result = await view._compute_allowed_departments()

        assert "財政部" in result
        assert "內政部" in result
        assert "國土安全部" not in result


if __name__ == "__main__":
    pytest.main([__file__])
