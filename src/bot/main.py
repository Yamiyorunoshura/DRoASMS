from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from importlib import import_module
from pkgutil import iter_modules
from typing import Iterable, Sequence

import discord
import structlog
from discord import app_commands
from dotenv import load_dotenv

from src.db import pool as db_pool
from src.infra.telemetry.listener import TelemetryListener

LOGGER = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BotSettings:
    """Configuration values required to bootstrap the Discord bot."""

    token: str
    guild_allowlist: Sequence[int]

    @classmethod
    def from_env(cls) -> "BotSettings":
        """Load bot settings from the environment."""
        load_dotenv(override=False)

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("Missing DISCORD_TOKEN environment variable.")

        allowlist_raw = os.getenv("DISCORD_GUILD_ALLOWLIST", "")
        guild_allowlist = tuple(
            int(value.strip()) for value in allowlist_raw.split(",") if value.strip()
        )

        return cls(token=token, guild_allowlist=guild_allowlist)


class EconomyBot(discord.Client):
    """Discord client wired for slash command registration and telemetry."""

    def __init__(self, settings: BotSettings) -> None:
        intents = discord.Intents.default()
        intents.guilds = True

        super().__init__(intents=intents)
        self.settings = settings
        self.tree = app_commands.CommandTree(self)
        self._telemetry_listener = TelemetryListener()

    async def setup_hook(self) -> None:
        """Run once when the bot starts up to prepare global services."""
        await db_pool.init_pool()
        _bootstrap_command_tree(self.tree)

        LOGGER.info("bot.commands.loaded", count=len(self.tree.get_commands()))

        if self.settings.guild_allowlist:
            await self._sync_guild_commands(self.settings.guild_allowlist)
        else:
            await self.tree.sync()

        await self._telemetry_listener.start()
        LOGGER.info(
            "bot.setup.complete",
            guild_allowlist=list(self.settings.guild_allowlist),
        )

    async def close(self) -> None:
        """Ensure background workers shut down before closing the client."""
        try:
            await self._telemetry_listener.stop()
        finally:
            await db_pool.close_pool()
            await super().close()

    async def _sync_guild_commands(self, guild_ids: Sequence[int]) -> None:
        for guild_id in guild_ids:
            await self.tree.sync(guild=discord.Object(id=guild_id))


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
    settings = BotSettings.from_env()
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
