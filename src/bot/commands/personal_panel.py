"""Slash command for personal economic panel."""

from __future__ import annotations

from typing import Any, cast

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_data import HelpData
from src.bot.services.balance_service import (
    BalancePermissionError,
    BalanceService,
    BalanceSnapshot,
    HistoryEntry,
)
from src.bot.services.currency_config_service import (
    CurrencyConfigService,
)
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.transfer_service import (
    TransferError,
    TransferResult,
    TransferService,
)
from src.bot.ui.personal_panel_paginator import PersonalPanelView
from src.infra.di.container import DependencyContainer
from src.infra.result import BusinessLogicError, Err, Ok, ValidationError

LOGGER = structlog.get_logger(__name__)


def get_help_data() -> HelpData:
    """Return help information for the personal_panel command."""
    return {
        "name": "personal_panel",
        "description": "開啟個人面板，查看餘額、交易歷史和進行轉帳。",
        "category": "economy",
        "parameters": [],
        "permissions": [],
        "examples": ["/personal_panel"],
        "tags": ["個人", "面板", "餘額", "轉帳", "歷史"],
    }


def register(
    tree: app_commands.CommandTree, *, container: DependencyContainer | None = None
) -> None:
    """Register the /personal_panel slash command with the provided command tree."""
    if container is None:
        # Fallback to old behavior for backward compatibility during migration
        import os

        from dotenv import load_dotenv

        from src.db import pool as db_pool

        load_dotenv(override=False)
        event_pool_enabled = os.getenv("TRANSFER_EVENT_POOL_ENABLED", "false").lower() == "true"
        pool = db_pool.get_pool()
        balance_service = BalanceService(pool)
        transfer_service = TransferService(pool, event_pool_enabled=event_pool_enabled)
        currency_service = CurrencyConfigService(pool)
        state_council_service = StateCouncilService(transfer_service=transfer_service)
    else:
        balance_service = container.resolve(BalanceService)
        transfer_service = container.resolve(TransferService)
        currency_service = container.resolve(CurrencyConfigService)
        state_council_service = container.resolve(StateCouncilService)

    command = build_personal_panel_command(
        balance_service,
        transfer_service,
        currency_service,
        state_council_service,
    )
    tree.add_command(command)
    LOGGER.debug("bot.command.personal_panel.registered")


def build_personal_panel_command(
    balance_service: BalanceService,
    transfer_service: TransferService,
    currency_service: CurrencyConfigService,
    state_council_service: StateCouncilService,
) -> app_commands.Command[Any, Any, Any]:
    """Build the `/personal_panel` slash command bound to the provided services."""

    @app_commands.command(
        name="personal_panel",
        description="開啟個人面板，查看餘額、交易歷史和進行轉帳。",
    )
    async def personal_panel(interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        if guild_id is None:
            await interaction.response.send_message(
                content="此命令僅能在伺服器內執行。",
                ephemeral=True,
            )
            return

        # Defer response to avoid 3 second timeout
        try:
            is_done = bool(getattr(interaction.response, "is_done", lambda: False)())
        except Exception:
            is_done = False
        if not is_done:
            try:
                defer = getattr(interaction.response, "defer", None)
                if callable(defer):
                    await cast(Any, defer)(ephemeral=True)
            except Exception as exc:
                LOGGER.debug("bot.personal_panel.defer_failed", error=str(exc))

        user_id = interaction.user.id

        # Fetch balance snapshot
        try:
            balance_result = await balance_service.get_balance_snapshot(
                guild_id=guild_id,
                requester_id=user_id,
                target_member_id=None,
                can_view_others=False,
                connection=None,
            )
        except BalancePermissionError as error:
            LOGGER.warning("bot.personal_panel.permission_denied", error=str(error))
            await _respond(interaction, str(error))
            return
        except Exception as exc:
            LOGGER.error("bot.personal_panel.balance_error", error=str(exc))
            await _respond(interaction, "查詢餘額時發生錯誤，請稍後再試。")
            return

        # Handle Result type
        balance_snapshot: BalanceSnapshot
        if hasattr(balance_result, "is_err") and callable(cast(Any, balance_result).is_err):
            result_obj = cast(Any, balance_result)
            if result_obj.is_err():
                error = result_obj.unwrap_err()
                LOGGER.error("bot.personal_panel.balance_error", error=str(error))
                await _respond(interaction, "查詢餘額時發生錯誤，請稍後再試。")
                return
            balance_snapshot = result_obj.unwrap()
        else:
            balance_snapshot = cast(BalanceSnapshot, balance_result)

        # Fetch history
        try:
            history_result = await balance_service.get_history(
                guild_id=guild_id,
                requester_id=user_id,
                target_member_id=None,
                can_view_others=False,
                limit=50,  # Fetch more for pagination
                cursor=None,
                connection=None,
            )
        except Exception as exc:
            LOGGER.error("bot.personal_panel.history_error", error=str(exc))
            await _respond(interaction, "查詢交易歷史時發生錯誤，請稍後再試。")
            return

        # Handle Result type
        history_entries: list[HistoryEntry]
        if hasattr(history_result, "is_err") and callable(cast(Any, history_result).is_err):
            result_obj = cast(Any, history_result)
            if result_obj.is_err():
                error = result_obj.unwrap_err()
                LOGGER.error("bot.personal_panel.history_error", error=str(error))
                await _respond(interaction, "查詢交易歷史時發生錯誤，請稍後再試。")
                return
            page = result_obj.unwrap()
            history_entries = list(page.items)
        else:
            from src.bot.services.balance_service import HistoryPage

            page = cast(HistoryPage, history_result)
            history_entries = list(page.items)

        # Get currency config
        currency_config = await currency_service.get_currency_config(guild_id=guild_id)

        # Create transfer callback
        async def transfer_callback(
            g_id: int,
            initiator_id: int,
            target_id: int,
            reason: str | None,
            amount: int,
        ) -> tuple[bool, str]:
            """Execute transfer and return (success, message)."""
            try:
                raw_result: Any = await transfer_service.transfer_currency(
                    guild_id=g_id,
                    initiator_id=initiator_id,
                    target_id=target_id,
                    amount=amount,
                    reason=reason,
                    connection=None,
                    metadata=None,
                )
            except (TransferError, ValidationError, BusinessLogicError) as exc:
                return (False, str(exc))
            except Exception as exc:
                LOGGER.exception("bot.personal_panel.transfer_error", error=str(exc))
                return (False, "處理轉帳時發生未預期錯誤，請稍後再試。")

            # Handle Result type
            if isinstance(raw_result, Err):
                err_result = cast(Err[TransferResult, Exception], raw_result)
                error = err_result.error
                if isinstance(error, ValidationError):
                    return (False, str(error))
                elif isinstance(error, BusinessLogicError):
                    error_type = error.context.get("error_type")
                    if error_type in ("insufficient_balance", "throttle"):
                        return (False, str(error))
                    return (False, "處理轉帳時發生錯誤，請稍後再試。")
                return (False, "處理轉帳時發生未預期錯誤，請稍後再試。")
            elif isinstance(raw_result, Ok):
                return (True, "轉帳成功")
            else:
                # Legacy mode: direct TransferResult
                return (True, "轉帳成功")

        # Create refresh callback
        async def refresh_callback() -> tuple[BalanceSnapshot, list[HistoryEntry]]:
            """Refresh balance and history data."""
            # Fetch balance
            new_balance_result = await balance_service.get_balance_snapshot(
                guild_id=guild_id,
                requester_id=user_id,
                target_member_id=None,
                can_view_others=False,
                connection=None,
            )
            new_balance: BalanceSnapshot
            if hasattr(new_balance_result, "is_err") and callable(
                cast(Any, new_balance_result).is_err
            ):
                result_obj = cast(Any, new_balance_result)
                if result_obj.is_err():
                    raise result_obj.unwrap_err()
                new_balance = result_obj.unwrap()
            else:
                new_balance = cast(BalanceSnapshot, new_balance_result)

            # Fetch history
            new_history_result = await balance_service.get_history(
                guild_id=guild_id,
                requester_id=user_id,
                target_member_id=None,
                can_view_others=False,
                limit=50,
                cursor=None,
                connection=None,
            )
            new_history: list[HistoryEntry]
            if hasattr(new_history_result, "is_err") and callable(
                cast(Any, new_history_result).is_err
            ):
                result_obj = cast(Any, new_history_result)
                if result_obj.is_err():
                    raise result_obj.unwrap_err()
                page = result_obj.unwrap()
                new_history = list(page.items)
            else:
                from src.bot.services.balance_service import HistoryPage

                page = cast(HistoryPage, new_history_result)
                new_history = list(page.items)

            return (new_balance, new_history)

        # Create the panel view
        view = PersonalPanelView(
            author_id=user_id,
            guild_id=guild_id,
            balance_snapshot=balance_snapshot,
            history_entries=history_entries,
            currency_config=currency_config,
            transfer_callback=transfer_callback,
            refresh_callback=refresh_callback,
            state_council_service=state_council_service,
        )

        # Send the panel
        embed = view.create_home_embed()
        await _respond_with_view(interaction, embed=embed, view=view)

    return cast(app_commands.Command[Any, Any, None], personal_panel)


async def _respond(interaction: discord.Interaction, content: str) -> None:
    """Safely respond to interaction."""
    try:
        try:
            is_done = bool(getattr(interaction.response, "is_done", lambda: False)())
        except Exception:
            is_done = False
        if is_done and hasattr(interaction, "edit_original_response"):
            await interaction.edit_original_response(content=content)
            try:
                if hasattr(interaction.response, "sent"):
                    cast(Any, interaction.response).sent = True
            except Exception:
                pass
        else:
            await interaction.response.send_message(content=content, ephemeral=True)
    except Exception:
        try:
            await interaction.followup.send(content=content, ephemeral=True)
        except Exception:
            LOGGER.exception("bot.personal_panel.respond_failed")


async def _respond_with_view(
    interaction: discord.Interaction,
    *,
    embed: discord.Embed,
    view: discord.ui.View,
) -> None:
    """Safely respond to interaction with embed and view."""
    try:
        try:
            is_done = bool(getattr(interaction.response, "is_done", lambda: False)())
        except Exception:
            is_done = False
        if is_done and hasattr(interaction, "edit_original_response"):
            await interaction.edit_original_response(embed=embed, view=view)
            try:
                if hasattr(interaction.response, "sent"):
                    cast(Any, interaction.response).sent = True
            except Exception:
                pass
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    except Exception:
        try:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception:
            LOGGER.exception("bot.personal_panel.respond_with_view_failed")


__all__ = ["build_personal_panel_command", "get_help_data", "register"]
