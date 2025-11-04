from __future__ import annotations

import asyncio
import os
from importlib import import_module
from pkgutil import iter_modules
from typing import Iterable, Sequence

import discord
import structlog
from discord import app_commands
from dotenv import load_dotenv

from src.bot.services.transfer_event_pool import TransferEventPoolCoordinator
from src.config.settings import BotSettings
from src.db import pool as db_pool
from src.infra.logging.config import configure_logging
from src.infra.telemetry.listener import TelemetryListener

# Configure logging as soon as this module is imported
configure_logging()
LOGGER = structlog.get_logger(__name__)


class EconomyBot(discord.Client):
    """Discord client wired for slash command registration and telemetry."""

    def __init__(self, settings: BotSettings) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        # Council governance requires reading role membership for snapshots.
        intents.members = True

        super().__init__(intents=intents)
        self.settings = settings
        self.tree = app_commands.CommandTree(self)

        # Initialize transfer event pool coordinator if enabled
        load_dotenv(override=False)
        event_pool_enabled = os.getenv("TRANSFER_EVENT_POOL_ENABLED", "false").lower() == "true"
        self._transfer_coordinator: TransferEventPoolCoordinator | None = None
        if event_pool_enabled:
            self._transfer_coordinator = TransferEventPoolCoordinator()

        self._telemetry_listener = TelemetryListener(
            transfer_coordinator=self._transfer_coordinator,
            discord_client=self,
        )

    async def setup_hook(self) -> None:
        """Run once when the bot starts up to prepare global services."""
        await db_pool.init_pool()

        # Start transfer event pool coordinator if enabled
        if self._transfer_coordinator is not None:
            await self._transfer_coordinator.start()

        _bootstrap_command_tree(self.tree)

        LOGGER.info("bot.commands.loaded", count=len(self.tree.get_commands()))

        if self.settings.guild_allowlist:
            await self._sync_guild_commands(self.settings.guild_allowlist)
            # 為避免允許清單中的伺服器同時看到「全域」與「Guild 專屬」兩份指令，
            # 在完成 Guild 同步後，主動清空並同步全域指令為空集合，
            # 以移除先前部署遺留在應用程式層的全域指令。
            await self._clear_global_commands()
        else:
            await self.tree.sync()

        await self._telemetry_listener.start()
        LOGGER.info(
            "bot.setup.complete",
            guild_allowlist=list(self.settings.guild_allowlist),
            event_pool_enabled=self._transfer_coordinator is not None,
        )

    async def close(self) -> None:
        """Ensure background workers shut down before closing the client."""
        try:
            await self._telemetry_listener.stop()
            if self._transfer_coordinator is not None:
                await self._transfer_coordinator.stop()
        finally:
            await db_pool.close_pool()
            await super().close()

    async def on_ready(self) -> None:  # T015: emit readiness event
        user = str(self.user) if getattr(self, "user", None) else None
        LOGGER.info("bot.ready", user=user)

    async def _sync_guild_commands(self, guild_ids: Sequence[int]) -> None:
        """Sync commands to specific guilds for immediate availability.

        In discord.py, commands registered on the command tree are global by
        default. To make them appear instantly in selected guilds we need to
        copy the global commands to each guild before syncing that guild.
        """
        for guild_id in guild_ids:
            guild = discord.Object(id=guild_id)
            # Copy global commands to the guild for instant propagation.
            try:
                # Older/newer discord.py versions may or may not have
                # clear_commands; guard its usage for compatibility.
                if hasattr(self.tree, "clear_commands"):
                    self.tree.clear_commands(guild=guild)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                LOGGER.info("bot.commands.synced_guild", guild_id=guild_id)
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.exception("bot.commands.sync_error", guild_id=guild_id, error=str(exc))

    async def _clear_global_commands(self) -> None:
        """Purge global application commands to avoid duplicates in allowed guilds.

        當採用 guild allowlist 時，我們只需要在指定的 Guild 中註冊指令。
        若歷史上曾經同步過全域指令，Discord 可能會同時顯示全域與 Guild 版，
        導致使用者在允許的 Guild 看到重複的斜線指令。本方法會將本地的全域
        指令集清空並同步，藉此刪除應用程式上殘留的全域指令。
        """
        try:
            if not hasattr(self.tree, "clear_commands"):
                # 舊版 discord.py 若無法清空本地集合，避免意外將全域指令再次同步上去
                LOGGER.warning("bot.commands.clear_global_unsupported")
                return

            # 不帶 guild 參數即代表清空全域命令集合
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            LOGGER.info("bot.commands.cleared_global")
        except Exception as exc:  # pragma: no cover - 防禦性處理
            LOGGER.exception("bot.commands.clear_global_error", error=str(exc))


def _bootstrap_command_tree(tree: app_commands.CommandTree) -> None:
    """Import command modules so they can register handlers with the tree."""
    for module_name in _iter_command_modules():
        module = import_module(module_name)
        register = getattr(module, "register", None)
        if callable(register):
            register(tree)
            LOGGER.debug("bot.command.registered", module=module_name)


def _iter_command_modules() -> Iterable[str]:
    commands_package = import_module("src.bot.commands")
    package_path = commands_package.__path__

    for module_info in iter_modules(package_path):
        if not module_info.ispkg:
            yield f"{commands_package.__name__}.{module_info.name}"


def main() -> None:
    """Entry point invoked via `python -m src.bot.main`."""
    # Load .env file manually for compatibility with existing code
    load_dotenv(override=False)
    settings = BotSettings.model_validate({})  # Load from environment variables
    bot = EconomyBot(settings)

    try:
        bot.run(settings.token)
    except KeyboardInterrupt:
        LOGGER.warning("bot.run.interrupted")
    finally:
        if not bot.is_closed():
            asyncio.run(bot.close())


if __name__ == "__main__":
    main()
