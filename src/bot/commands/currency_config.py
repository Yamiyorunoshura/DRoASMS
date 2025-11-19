"""Slash command for configuring currency name and icon."""

from __future__ import annotations

from typing import Any, Optional, cast

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_data import HelpData
from src.bot.services.currency_config_service import CurrencyConfigService
from src.bot.utils.error_templates import ErrorMessageTemplates
from src.infra.di.container import DependencyContainer

LOGGER = structlog.get_logger(__name__)


def get_help_data() -> dict[str, HelpData]:
    """Return help information for currency_config command."""
    return {
        "currency_config": {
            "name": "currency_config",
            "description": "設定該伺服器的貨幣名稱和圖示（僅限管理員）。",
            "category": "economy",
            "parameters": [
                {
                    "name": "name",
                    "description": "貨幣名稱（1-20 字元）",
                    "required": False,
                },
                {
                    "name": "icon",
                    "description": "貨幣圖示（單一 emoji 或 Unicode 字元）",
                    "required": False,
                },
            ],
            "permissions": ["administrator", "manage_guild"],
            "examples": [
                "/currency_config name:金幣 icon:🪙",
                "/currency_config name:點數",
                "/currency_config icon:💰",
            ],
            "tags": ["設定", "貨幣"],
        },
    }


def register(
    tree: app_commands.CommandTree, *, container: DependencyContainer | None = None
) -> None:
    """Register currency_config command with the provided command tree."""
    if container is None:
        # Fallback to old behavior for backward compatibility during migration
        from src.db import pool as db_pool

        pool = db_pool.get_pool()
        service = CurrencyConfigService(pool)
    else:
        service = container.resolve(CurrencyConfigService)

    command = build_currency_config_command(service)
    tree.add_command(command)
    LOGGER.debug("bot.command.currency_config.registered")


def build_currency_config_command(
    service: CurrencyConfigService,
) -> app_commands.Command[Any, Any, Any]:
    """Build the `/currency_config` slash command bound to the provided service."""

    @app_commands.command(
        name="currency_config",
        description="設定該伺服器的貨幣名稱和圖示（僅限管理員）。",
    )
    @app_commands.describe(
        name="貨幣名稱（1-20 字元）",
        icon="貨幣圖示（單一 emoji 或 Unicode 字元）",
    )
    async def currency_config(
        interaction: discord.Interaction,
        name: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                content="此命令僅能在伺服器內執行。",
                ephemeral=True,
            )
            return

        # Check permissions
        permissions = getattr(interaction.user, "guild_permissions", None)
        if not permissions or not (
            getattr(permissions, "administrator", False)
            or getattr(permissions, "manage_guild", False)
        ):
            await interaction.response.send_message(
                content=ErrorMessageTemplates.permission_denied("設定貨幣配置", "僅限管理員"),
                ephemeral=True,
            )
            return

        # Validate name if provided
        if name is not None:
            name = name.strip()
            if not name or len(name) > 20:
                await interaction.response.send_message(
                    content=ErrorMessageTemplates.validation_failed(
                        "貨幣名稱", "必須為 1-20 字元的非空字串"
                    ),
                    ephemeral=True,
                )
                return

        # Validate icon if provided
        if icon is not None:
            icon = icon.strip()
            if len(icon) > 10:  # Reasonable limit for emoji/unicode
                await interaction.response.send_message(
                    content=ErrorMessageTemplates.validation_failed(
                        "貨幣圖示", "必須為單一 emoji 或 Unicode 字元（最多 10 字元）"
                    ),
                    ephemeral=True,
                )
                return

        # At least one parameter must be provided
        if name is None and icon is None:
            await interaction.response.send_message(
                content=ErrorMessageTemplates.validation_failed(
                    "參數", "請至少提供 name 或 icon 參數之一"
                ),
                ephemeral=True,
            )
            return

        try:
            result = await service.update_currency_config(
                guild_id=interaction.guild_id,
                currency_name=name,
                currency_icon=icon,
            )

            # Format success message
            icon_display = result.currency_icon if result.currency_icon else "（無圖示）"
            message = (
                f"✅ 貨幣配置已更新！\n"
                f"📝 貨幣名稱：{result.currency_name}\n"
                f"🎨 貨幣圖示：{icon_display}"
            )

            await interaction.response.send_message(content=message, ephemeral=True)
        except Exception as exc:  # pragma: no cover - defensive catch
            LOGGER.exception("bot.currency_config.unexpected_error", error=str(exc))
            await interaction.response.send_message(
                content=ErrorMessageTemplates.system_error("設定貨幣配置時發生未預期錯誤"),
                ephemeral=True,
            )

    # Pylance 在嚴格模式下無法從 decorators 推導泛型參數，導致回傳型別含 Unknown。
    # 以顯式 cast 告知其為 app_commands.Command。
    return cast(app_commands.Command[Any, Any, None], currency_config)


__all__ = ["build_currency_config_command", "get_help_data", "register"]
