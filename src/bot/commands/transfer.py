from __future__ import annotations

import os
from typing import Any, Optional, Union
from uuid import UUID

import discord
import structlog
from discord import app_commands
from dotenv import load_dotenv

from src.bot.commands.help_data import HelpData
from src.bot.services.council_service import CouncilService, GovernanceNotConfiguredError
from src.bot.services.state_council_service import (
    StateCouncilNotConfiguredError,
    StateCouncilService,
)
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


def get_help_data() -> HelpData:
    """Return help information for the transfer command."""
    return {
        "name": "transfer",
        "description": "轉帳虛擬貨幣給伺服器內的其他成員、理事會身分組，或部門領導人身分組。",
        "category": "economy",
        "parameters": [
            {
                "name": "target",
                "description": "要接收點數的成員、理事會身分組，或部門領導人身分組",
                "required": True,
            },
            {
                "name": "amount",
                "description": "要轉出的整數點數",
                "required": True,
            },
            {
                "name": "reason",
                "description": "選填，會記錄在交易歷史中的備註",
                "required": False,
            },
        ],
        "permissions": [],
        "examples": [
            "/transfer @user 100",
            "/transfer @user 50 生日禮物",
            "/transfer @CouncilRole 1000 理事會補助",
        ],
        "tags": ["轉帳", "點數"],
    }


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
        target="要接收點數的成員、理事會身分組，或部門領導人身分組",
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

        # 先回覆 defer 以避免 Discord 3 秒時限導致 Unknown interaction（10062）
        # 之後統一用 edit_original_response / followup 傳遞結果
        # 兼容測試 stub：某些測試替身沒有 is_done()/defer
        try:
            is_done = bool(getattr(interaction.response, "is_done", lambda: False)())
        except Exception:
            is_done = False
        if not is_done:
            try:
                defer = getattr(interaction.response, "defer", None)
                if callable(defer):
                    await defer(ephemeral=True)
            except Exception as exc:  # 防禦性：即使 defer 失敗也不終止流程
                LOGGER.debug("bot.transfer.defer_failed", error=str(exc))

        # 支援以身分組作為目標：
        # 1) 常任理事會身分組 -> 理事會公共帳戶
        # 2) 國務院部門領導人身分組 -> 對應部門政府帳戶
        target_id: int
        if isinstance(target, discord.Role):
            # 嘗試理事會身分組
            try:
                cfg = await CouncilService().get_config(guild_id=guild_id)
            except GovernanceNotConfiguredError:
                cfg = None
            if cfg and target.id == cfg.council_role_id:
                target_id = CouncilService.derive_council_account_id(guild_id)
            else:
                # 嘗試國務院部門身分組
                sc_service = StateCouncilService()
                try:
                    department = await sc_service.find_department_by_role(
                        guild_id=guild_id, role_id=target.id
                    )
                except StateCouncilNotConfiguredError:
                    department = None
                if department is None:
                    await interaction.response.send_message(
                        content=(
                            "僅支援提及常任理事會或已綁定之部門領導人身分組，"
                            "或直接指定個別成員。"
                        ),
                        ephemeral=True,
                    )
                    return
                target_id = await sc_service.get_department_account_id(
                    guild_id=guild_id, department=department
                )
        else:
            target_id = target.id

        # 在 event pool 模式下，將 interaction token 加入 metadata 以便後續發送 followup
        metadata: dict[str, Any] | None = None
        event_pool_enabled = os.getenv("TRANSFER_EVENT_POOL_ENABLED", "false").lower() == "true"
        if event_pool_enabled:
            metadata = {"interaction_token": interaction.token}

        try:
            # 一律傳入 metadata：同步模式為 None；事件池模式包含 interaction_token
            result = await service.transfer_currency(
                guild_id=guild_id,
                initiator_id=interaction.user.id,
                target_id=target_id,
                amount=amount,
                reason=reason,
                connection=None,
                metadata=metadata,
            )
        except TransferValidationError as exc:
            await _respond(interaction, str(exc))
            return
        except InsufficientBalanceError as exc:
            await _respond(interaction, str(exc))
            return
        except TransferThrottleError as exc:
            await _respond(interaction, str(exc))
            return
        except TransferError as exc:
            LOGGER.exception("bot.transfer.unexpected_error", error=str(exc))
            await _respond(interaction, "處理轉帳時發生未預期錯誤，請稍後再試。")
            return

        # Handle event pool mode (returns UUID) vs sync mode (returns TransferResult)
        if isinstance(result, UUID):
            message = _format_pending_message(interaction.user, target, result)
        else:
            message = _format_success_message(interaction.user, target, result)
        await _respond(interaction, message)

    return transfer


async def _respond(interaction: discord.Interaction, content: str) -> None:
    """安全回覆互動：
    - 若先前已 defer，優先編輯原始回覆；
    - 若未 defer（理論上不會發生，但保險），則做初次回覆；
    - 若編輯失敗，退回 followup.send（仍為 ephemeral）。
    """
    try:
        # 兼容測試 stub：沒有 is_done()/edit_original_response 的情況
        try:
            is_done = bool(getattr(interaction.response, "is_done", lambda: False)())
        except Exception:
            is_done = False
        if is_done and hasattr(interaction, "edit_original_response"):
            await interaction.edit_original_response(content=content)
        else:
            await interaction.response.send_message(content=content, ephemeral=True)
    except Exception as exc:
        LOGGER.debug("bot.transfer.respond_fallback", error=str(exc))
        try:
            await interaction.followup.send(content=content, ephemeral=True)
        except Exception:
            # 最後手段：記錄但不再拋出，避免噴錯打斷指令流程
            LOGGER.exception("bot.transfer.respond_failed")


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


def _format_pending_message(
    initiator: Union[discord.Member, discord.User],
    target: Union[discord.Member, discord.User, discord.Role],
    transfer_id: UUID,
) -> str:
    parts = [
        "⏳ 轉帳請求已提交，正在進行檢查中。",
        f"📋 轉帳 ID：`{transfer_id}`",
        "💡 系統將自動檢查餘額、冷卻時間和每日上限，通過後自動執行轉帳。",
    ]
    return "\n".join(parts)


def _get_transfer_service() -> TransferService:
    global _TRANSFER_SERVICE
    if _TRANSFER_SERVICE is None:
        load_dotenv(override=False)
        event_pool_enabled = os.getenv("TRANSFER_EVENT_POOL_ENABLED", "false").lower() == "true"
        pool = db_pool.get_pool()
        _TRANSFER_SERVICE = TransferService(
            pool,
            event_pool_enabled=event_pool_enabled,
        )
    return _TRANSFER_SERVICE


__all__ = ["build_transfer_command", "get_help_data", "register"]
