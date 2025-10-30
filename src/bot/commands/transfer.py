from __future__ import annotations

from typing import Any, Optional, Union

import discord
import structlog
from discord import app_commands

from src.bot.services.council_service import CouncilService, GovernanceNotConfiguredError
from src.bot.services.transfer_service import (
    InsufficientBalanceError,
    TransferError,
    TransferResult,
    TransferService,
    TransferThrottleError,
    TransferValidationError,
)
from src.db import pool as db_pool

LOGGER = structlog.get_logger(__name__)
_TRANSFER_SERVICE: TransferService | None = None


def register(tree: app_commands.CommandTree) -> None:
    """Register the /transfer slash command with the provided command tree."""
    command = build_transfer_command(_get_transfer_service())
    tree.add_command(command)
    LOGGER.debug("bot.command.transfer.registered")


def build_transfer_command(service: TransferService) -> app_commands.Command[Any, Any, Any]:
    """Build the `/transfer` slash command bound to the provided service."""

    @app_commands.command(
        name="transfer",
        description="Transfer virtual currency to another member in this guild.",
    )
    @app_commands.describe(
        target="要接收點數的成員或理事會身分組",
        amount="要轉出的整數點數",
        reason="選填，會記錄在交易歷史中的備註",
    )
    async def transfer(
        interaction: discord.Interaction,
        target: Union[discord.Member, discord.User, discord.Role],
        amount: int,
        reason: Optional[str] = None,
    ) -> None:
        guild_id = interaction.guild_id
        if guild_id is None:
            await interaction.response.send_message(
                content="此命令僅能在伺服器內執行。",
                ephemeral=True,
            )
            return

        # 允許以理事會身分組映射至理事會帳戶
        target_id: int
        if isinstance(target, discord.Role):
            try:
                cfg = await CouncilService().get_config(guild_id=guild_id)
            except GovernanceNotConfiguredError:
                await interaction.response.send_message(
                    content=(
                        "尚未完成理事會設定，無法以身分組為目標。"
                        "請通知管理員執行 /council config_role。"
                    ),
                    ephemeral=True,
                )
                return
            if target.id != cfg.council_role_id:
                await interaction.response.send_message(
                    content="僅支援提及常任理事會身分組或個別成員。",
                    ephemeral=True,
                )
                return
            target_id = CouncilService.derive_council_account_id(guild_id)
        else:
            target_id = target.id

        try:
            result = await service.transfer_currency(
                guild_id=guild_id,
                initiator_id=interaction.user.id,
                target_id=target_id,
                amount=amount,
                reason=reason,
                connection=None,
            )
        except TransferValidationError as exc:
            await interaction.response.send_message(content=str(exc), ephemeral=True)
            return
        except InsufficientBalanceError as exc:
            await interaction.response.send_message(content=str(exc), ephemeral=True)
            return
        except TransferThrottleError as exc:
            await interaction.response.send_message(content=str(exc), ephemeral=True)
            return
        except TransferError as exc:
            LOGGER.exception("bot.transfer.unexpected_error", error=str(exc))
            await interaction.response.send_message(
                content="處理轉帳時發生未預期錯誤，請稍後再試。",
                ephemeral=True,
            )
            return

        message = _format_success_message(interaction.user, target, result)
        await interaction.response.send_message(content=message, ephemeral=True)

    return transfer


def _format_success_message(
    initiator: Union[discord.Member, discord.User],
    target: Union[discord.Member, discord.User, discord.Role],
    result: TransferResult,
) -> str:
    parts = [
        f"✅ 已成功將 {result.amount:,} 點轉給 {target.mention}。",
        f"👉 你目前的餘額為 {result.initiator_balance:,} 點。",
    ]
    reason = result.metadata.get("reason")
    if reason:
        parts.append(f"📝 備註：{reason}")
    return "\n".join(parts)


def _get_transfer_service() -> TransferService:
    global _TRANSFER_SERVICE
    if _TRANSFER_SERVICE is None:
        pool = db_pool.get_pool()
        _TRANSFER_SERVICE = TransferService(pool)
    return _TRANSFER_SERVICE


__all__ = ["build_transfer_command", "register"]
