"""測試 Bot 主模組 (main.py)。

涵蓋範圍：
- intents 設定
- guild allowlist 同步/清空流程
- TransferEventPoolCoordinator 啟停開關
- 指令載入行為
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord import app_commands

from src.bot.main import (
    EconomyBot,
    _bootstrap_command_tree,
    _iter_command_modules,
)
from src.config.settings import BotSettings

# --- Mock Objects ---


@pytest.fixture
def mock_settings() -> MagicMock:
    """創建假 BotSettings。"""
    settings = MagicMock(spec=BotSettings)
    settings.token = "fake-token"
    settings.guild_allowlist = []
    return settings


@pytest.fixture
def mock_settings_with_allowlist() -> MagicMock:
    """創建帶有 guild allowlist 的假 BotSettings。"""
    settings = MagicMock(spec=BotSettings)
    settings.token = "fake-token"
    settings.guild_allowlist = [12345, 67890]
    return settings


# --- Test EconomyBot Initialization ---


class TestEconomyBotInit:
    """測試 EconomyBot 初始化。"""

    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    def test_init_basic(
        self, mock_telemetry: MagicMock, mock_coordinator: MagicMock, mock_settings: MagicMock
    ) -> None:
        """測試基本初始化。"""
        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings)

        assert bot.settings == mock_settings
        assert bot.tree is not None
        assert isinstance(bot.tree, app_commands.CommandTree)

    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    def test_init_intents(
        self, mock_telemetry: MagicMock, mock_coordinator: MagicMock, mock_settings: MagicMock
    ) -> None:
        """測試 intents 設定。"""
        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings)

        # 檢查 intents
        assert bot.intents.guilds is True
        assert bot.intents.members is True  # 理事會治理需要成員 intent

    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    def test_init_without_event_pool(
        self, mock_telemetry: MagicMock, mock_coordinator: MagicMock, mock_settings: MagicMock
    ) -> None:
        """測試禁用事件池時的初始化。"""
        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings)

        assert bot._transfer_coordinator is None

    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    def test_init_with_event_pool_enabled(
        self, mock_telemetry: MagicMock, mock_coordinator: MagicMock, mock_settings: MagicMock
    ) -> None:
        """測試啟用事件池時的初始化。"""
        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "true"}):
            bot = EconomyBot(mock_settings)

        mock_coordinator.assert_called_once()
        assert bot._transfer_coordinator is not None


# --- Test Setup Hook ---


class TestEconomyBotSetupHook:
    """測試 setup_hook 方法。"""

    @pytest.mark.asyncio
    @patch("src.bot.main.db_pool")
    @patch("src.bot.main.bootstrap_result_container")
    @patch("src.bot.main._bootstrap_command_tree")
    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    async def test_setup_hook_initializes_db(
        self,
        mock_telemetry: MagicMock,
        mock_coordinator: MagicMock,
        mock_bootstrap_tree: MagicMock,
        mock_bootstrap_container: MagicMock,
        mock_db_pool: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """測試 setup_hook 初始化資料庫。"""
        mock_db_pool.init_pool = AsyncMock()
        mock_bootstrap_container.return_value = (MagicMock(), MagicMock())
        mock_telemetry_instance = MagicMock()
        mock_telemetry_instance.start = AsyncMock()
        mock_telemetry.return_value = mock_telemetry_instance

        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings)
            bot.tree.sync = AsyncMock()

            await bot.setup_hook()

        mock_db_pool.init_pool.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.bot.main.db_pool")
    @patch("src.bot.main.bootstrap_result_container")
    @patch("src.bot.main._bootstrap_command_tree")
    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    async def test_setup_hook_syncs_global_commands(
        self,
        mock_telemetry: MagicMock,
        mock_coordinator: MagicMock,
        mock_bootstrap_tree: MagicMock,
        mock_bootstrap_container: MagicMock,
        mock_db_pool: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """測試無 allowlist 時同步全域指令。"""
        mock_db_pool.init_pool = AsyncMock()
        mock_bootstrap_container.return_value = (MagicMock(), MagicMock())
        mock_telemetry_instance = MagicMock()
        mock_telemetry_instance.start = AsyncMock()
        mock_telemetry.return_value = mock_telemetry_instance

        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings)
            bot.tree.sync = AsyncMock()

            await bot.setup_hook()

        bot.tree.sync.assert_called_once_with()  # 無參數表示全域同步

    @pytest.mark.asyncio
    @patch("src.bot.main.db_pool")
    @patch("src.bot.main.bootstrap_result_container")
    @patch("src.bot.main._bootstrap_command_tree")
    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    async def test_setup_hook_with_allowlist_syncs_guilds(
        self,
        mock_telemetry: MagicMock,
        mock_coordinator: MagicMock,
        mock_bootstrap_tree: MagicMock,
        mock_bootstrap_container: MagicMock,
        mock_db_pool: MagicMock,
        mock_settings_with_allowlist: MagicMock,
    ) -> None:
        """測試有 allowlist 時同步到特定 guild。"""
        mock_db_pool.init_pool = AsyncMock()
        mock_bootstrap_container.return_value = (MagicMock(), MagicMock())
        mock_telemetry_instance = MagicMock()
        mock_telemetry_instance.start = AsyncMock()
        mock_telemetry.return_value = mock_telemetry_instance

        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings_with_allowlist)
            bot.tree.sync = AsyncMock()
            bot.tree.copy_global_to = MagicMock()
            bot.tree.clear_commands = MagicMock()

            await bot.setup_hook()

        # 應該為每個 guild 同步
        assert bot.tree.sync.call_count >= 2  # 至少兩次 guild 同步

    @pytest.mark.asyncio
    @patch("src.bot.main.db_pool")
    @patch("src.bot.main.bootstrap_result_container")
    @patch("src.bot.main._bootstrap_command_tree")
    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    async def test_setup_hook_starts_event_pool(
        self,
        mock_telemetry: MagicMock,
        mock_coordinator_class: MagicMock,
        mock_bootstrap_tree: MagicMock,
        mock_bootstrap_container: MagicMock,
        mock_db_pool: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """測試 setup_hook 啟動事件池。"""
        mock_db_pool.init_pool = AsyncMock()
        mock_bootstrap_container.return_value = (MagicMock(), MagicMock())

        mock_coordinator_instance = MagicMock()
        mock_coordinator_instance.start = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator_instance

        mock_telemetry_instance = MagicMock()
        mock_telemetry_instance.start = AsyncMock()
        mock_telemetry.return_value = mock_telemetry_instance

        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "true"}):
            bot = EconomyBot(mock_settings)
            bot.tree.sync = AsyncMock()

            await bot.setup_hook()

        mock_coordinator_instance.start.assert_called_once()


# --- Test Guild Commands Sync ---


class TestGuildCommandsSync:
    """測試 guild 指令同步。"""

    @pytest.mark.asyncio
    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    async def test_sync_guild_commands(
        self,
        mock_telemetry: MagicMock,
        mock_coordinator: MagicMock,
        mock_settings_with_allowlist: MagicMock,
    ) -> None:
        """測試同步指令到特定 guild。"""
        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings_with_allowlist)
            bot.tree.sync = AsyncMock()
            bot.tree.copy_global_to = MagicMock()
            bot.tree.clear_commands = MagicMock()

            await bot._sync_guild_commands([12345, 67890])

        # 應該為每個 guild 複製並同步
        assert bot.tree.copy_global_to.call_count == 2
        assert bot.tree.sync.call_count == 2

    @pytest.mark.asyncio
    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    async def test_sync_guild_commands_clears_guild_first(
        self,
        mock_telemetry: MagicMock,
        mock_coordinator: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """測試同步前清空 guild 指令。"""
        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings)
            bot.tree.sync = AsyncMock()
            bot.tree.copy_global_to = MagicMock()
            bot.tree.clear_commands = MagicMock()

            await bot._sync_guild_commands([12345])

        # 應該先清空 guild 指令
        bot.tree.clear_commands.assert_called()


# --- Test Clear Global Commands ---


class TestClearGlobalCommands:
    """測試清空全域指令。"""

    @pytest.mark.asyncio
    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    async def test_clear_global_commands(
        self, mock_telemetry: MagicMock, mock_coordinator: MagicMock, mock_settings: MagicMock
    ) -> None:
        """測試清空全域指令。"""
        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings)
            bot.tree.sync = AsyncMock()
            bot.tree.clear_commands = MagicMock()

            await bot._clear_global_commands()

        bot.tree.clear_commands.assert_called_with(guild=None)
        bot.tree.sync.assert_called_once()


# --- Test Close ---


class TestEconomyBotClose:
    """測試 close 方法。"""

    @pytest.mark.asyncio
    @patch("src.bot.main.db_pool")
    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    async def test_close_stops_telemetry(
        self,
        mock_telemetry: MagicMock,
        mock_coordinator: MagicMock,
        mock_db_pool: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """測試關閉時停止 telemetry listener。"""
        mock_db_pool.close_pool = AsyncMock()
        mock_telemetry_instance = MagicMock()
        mock_telemetry_instance.stop = AsyncMock()
        mock_telemetry.return_value = mock_telemetry_instance

        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings)

        with patch.object(discord.Client, "close", new_callable=AsyncMock):
            await bot.close()

        mock_telemetry_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.bot.main.db_pool")
    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    async def test_close_stops_event_pool(
        self,
        mock_telemetry: MagicMock,
        mock_coordinator_class: MagicMock,
        mock_db_pool: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """測試關閉時停止事件池。"""
        mock_db_pool.close_pool = AsyncMock()

        mock_coordinator_instance = MagicMock()
        mock_coordinator_instance.stop = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator_instance

        mock_telemetry_instance = MagicMock()
        mock_telemetry_instance.stop = AsyncMock()
        mock_telemetry.return_value = mock_telemetry_instance

        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "true"}):
            bot = EconomyBot(mock_settings)

        with patch.object(discord.Client, "close", new_callable=AsyncMock):
            await bot.close()

        mock_coordinator_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.bot.main.db_pool")
    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    async def test_close_closes_db_pool(
        self,
        mock_telemetry: MagicMock,
        mock_coordinator: MagicMock,
        mock_db_pool: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """測試關閉時關閉資料庫連線池。"""
        mock_db_pool.close_pool = AsyncMock()
        mock_telemetry_instance = MagicMock()
        mock_telemetry_instance.stop = AsyncMock()
        mock_telemetry.return_value = mock_telemetry_instance

        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings)

        with patch.object(discord.Client, "close", new_callable=AsyncMock):
            await bot.close()

        mock_db_pool.close_pool.assert_called_once()


# --- Test On Ready ---


class TestOnReady:
    """測試 on_ready 事件。"""

    @pytest.mark.asyncio
    @patch("src.bot.main.TransferEventPoolCoordinator")
    @patch("src.bot.main.TelemetryListener")
    async def test_on_ready_logs_user(
        self, mock_telemetry: MagicMock, mock_coordinator: MagicMock, mock_settings: MagicMock
    ) -> None:
        """測試 on_ready 記錄用戶資訊。"""
        with patch.dict("os.environ", {"TRANSFER_EVENT_POOL_ENABLED": "false"}):
            bot = EconomyBot(mock_settings)

        # 設置假用戶
        mock_user = MagicMock()
        mock_user.__str__ = lambda self: "TestBot#1234"
        bot._connection._user = mock_user

        with patch("src.bot.main.LOGGER") as mock_logger:
            await bot.on_ready()

            mock_logger.info.assert_called_once()
            args, kwargs = mock_logger.info.call_args
            assert args[0] == "bot.ready"


# --- Test Bootstrap Command Tree ---


class TestBootstrapCommandTree:
    """測試指令樹啟動。"""

    def test_iter_command_modules(self) -> None:
        """測試迭代指令模組。"""
        modules = list(_iter_command_modules())

        # 應該找到一些指令模組
        assert len(modules) > 0
        assert all("src.bot.commands" in m for m in modules)

    @patch("src.bot.main.import_module")
    def test_bootstrap_command_tree_registers_commands(self, mock_import: MagicMock) -> None:
        """測試啟動指令樹註冊指令。"""
        # 創建假模組
        mock_module = MagicMock()
        mock_module.register = MagicMock()
        mock_import.return_value = mock_module

        mock_tree = MagicMock(spec=app_commands.CommandTree)

        with patch("src.bot.main._iter_command_modules", return_value=["test_module"]):
            _bootstrap_command_tree(mock_tree)

        mock_module.register.assert_called_once()

    @patch("src.bot.main.import_module")
    def test_bootstrap_command_tree_passes_container(self, mock_import: MagicMock) -> None:
        """測試啟動指令樹傳遞 container。"""
        import inspect

        # 創建假模組，register 函數接受 container 參數
        mock_module = MagicMock()

        def fake_register(tree: Any, container: Any = None) -> None:
            pass

        mock_module.register = MagicMock(side_effect=fake_register)
        # 設置正確的 signature
        mock_module.register.__signature__ = inspect.signature(fake_register)
        mock_import.return_value = mock_module

        mock_tree = MagicMock(spec=app_commands.CommandTree)
        mock_container = MagicMock()

        with patch("src.bot.main._iter_command_modules", return_value=["test_module"]):
            _bootstrap_command_tree(mock_tree, container=mock_container)

        mock_module.register.assert_called_once_with(mock_tree, container=mock_container)

    @patch("src.bot.main.import_module")
    def test_bootstrap_command_tree_skips_modules_without_register(
        self, mock_import: MagicMock
    ) -> None:
        """測試跳過沒有 register 函數的模組。"""
        mock_module = MagicMock(spec=[])  # 沒有 register 屬性
        del mock_module.register
        mock_import.return_value = mock_module

        mock_tree = MagicMock(spec=app_commands.CommandTree)

        with patch("src.bot.main._iter_command_modules", return_value=["test_module"]):
            # 不應該拋出例外
            _bootstrap_command_tree(mock_tree)


if __name__ == "__main__":
    pytest.main([__file__])
