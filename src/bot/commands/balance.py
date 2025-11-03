"""Slash commands for querying balance snapshots and history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Union

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_data import HelpData
from src.bot.services.balance_service import (
    BalancePermissionError,
    BalanceService,
    BalanceSnapshot,
    HistoryPage,
)
from src.db import pool as db_pool

LOGGER = structlog.get_logger(__name__)
_BALANCE_SERVICE: BalanceService | None = None


def get_help_data() -> dict[str, HelpData]:
    """Return help information for balance and history commands."""
    return {
        "balance": {
            "name": "balance",
            "description": "檢視你的虛擬貨幣餘額，或在有權限時查詢他人餘額。",
            "category": "economy",
            "parameters": [
                {
                    "name": "member",
                    "description": "選填參數；需要管理權限才能檢視其他成員。",
                    "required": False,
                },
            ],
            "permissions": [],
            "examples": ["/balance", "/balance @user"],
            "tags": ["餘額", "查詢"],
        },
        "history": {
            "name": "history",
            "description": "檢視虛擬貨幣的近期交易歷史。",
            "category": "economy",
            "parameters": [
                {
                    "name": "member",
                    "description": "選填參數；需要管理權限才能檢視其他成員。",
                    "required": False,
                },
                {
                    "name": "limit",
                    "description": "最多顯示多少筆紀錄（1-50，預設 10）。",
                    "required": False,
                },
                {
                    "name": "before",
                    "description": "選填 ISO 8601 時間戳，僅顯示該時間點之前的紀錄。",
                    "required": False,
                },
            ],
            "permissions": [],
            "examples": [
                "/history",
                "/history limit:20",
                "/history @user limit:50",
            ],
            "tags": ["歷史", "交易記錄"],
        },
    }


def register(tree: app_commands.CommandTree) -> None:
    """Register economy balance/history commands with the provided command tree."""
    service = _get_balance_service()
    tree.add_command(build_balance_command(service))
    tree.add_command(build_history_command(service))
    LOGGER.debug("bot.command.balance.registered")
    LOGGER.debug("bot.command.history.registered")


def build_balance_command(service: BalanceService) -> app_commands.Command[Any, Any, Any]:
    """Build the `/balance` slash command bound to the provided service."""

    @app_commands.command(
        name="balance",
        description="檢視你的虛擬貨幣餘額，或在有權限時查詢他人餘額。",
    )
    @app_commands.describe(
        member="選填參數；需要管理權限才能檢視其他成員。",
    )
    async def balance(
        interaction: discord.Interaction,
        member: Optional[Union[discord.Member, discord.User]] = None,
    ) -> None:
        if interaction.guild_id is None:
            await _respond(interaction, "此命令僅能在伺服器內執行。")
            return

        # 先嘗試 defer，以避免超過 3 秒導致 Unknown interaction（10062）
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
                LOGGER.debug("bot.balance.defer_failed", error=str(exc))

        target_id = member.id if member is not None else interaction.user.id
        can_view_others = _has_audit_permission(interaction)

        try:
            snapshot = await service.get_balance_snapshot(
                guild_id=interaction.guild_id,
                requester_id=interaction.user.id,
                target_member_id=target_id if target_id != interaction.user.id else None,
                can_view_others=can_view_others,
                connection=None,
            )
        except BalancePermissionError as exc:
            await _respond(interaction, str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive catch
            LOGGER.exception("bot.balance.unexpected_error", error=str(exc))
            await _respond(interaction, "查詢餘額時發生未預期錯誤，請稍後再試。")
            return

        target_display = member if member is not None else interaction.user
        message = _format_balance_response(snapshot, target_display)
        await _respond(interaction, message)

    return balance


def build_history_command(service: BalanceService) -> app_commands.Command[Any, Any, Any]:
    """Build the `/history` slash command bound to the provided service."""

    @app_commands.command(
        name="history",
        description="檢視虛擬貨幣的近期交易歷史。",
    )
    @app_commands.describe(
        member="選填參數；需要管理權限才能檢視其他成員。",
        limit="最多顯示多少筆紀錄（1-50，預設 10）。",
        before="選填 ISO 8601 時間戳，僅顯示該時間點之前的紀錄。",
    )
    async def history(
        interaction: discord.Interaction,
        member: Optional[Union[discord.Member, discord.User]] = None,
        limit: app_commands.Range[int, 1, 50] = 10,
        before: Optional[str] = None,
    ) -> None:
        if interaction.guild_id is None:
            await _respond(interaction, "此命令僅能在伺服器內執行。")
            return

        # 先嘗試 defer，以避免超過 3 秒導致 Unknown interaction（10062）
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
                LOGGER.debug("bot.history.defer_failed", error=str(exc))

        target_id = member.id if member is not None else interaction.user.id
        can_view_others = _has_audit_permission(interaction)

        cursor_dt: datetime | None = None
        if before:
            try:
                parsed = datetime.fromisoformat(before)
            except ValueError:
                await _respond(interaction, "`before` 參數必須是可解析的 ISO 8601 時間戳。")
                return
            cursor_dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            cursor_dt = cursor_dt.astimezone(timezone.utc)

        try:
            page = await service.get_history(
                guild_id=interaction.guild_id,
                requester_id=interaction.user.id,
                target_member_id=target_id if target_id != interaction.user.id else None,
                can_view_others=can_view_others,
                limit=limit,
                cursor=cursor_dt,
                connection=None,
            )
        except BalancePermissionError as exc:
            await _respond(interaction, str(exc))
            return
        except ValueError as exc:
            await _respond(interaction, str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive catch
            LOGGER.exception("bot.history.unexpected_error", error=str(exc))
            await _respond(interaction, "查詢歷史時發生未預期錯誤，請稍後再試。")
            return

        target_display = member if member is not None else interaction.user
        message = _format_history_response(page, target_display)
        await _respond(interaction, message)

    return history


async def _respond(interaction: discord.Interaction, content: str) -> None:
    """安全回覆互動：
    - 若先前已 defer，優先編輯原始回覆；
    - 若未 defer（理論上不會發生，但保險），則做初次回覆；
    - 若編輯失敗，退回 followup.send（仍為 ephemeral）。
    （兼容單元測試 stub：沒有 is_done()/defer/edit_original_response 時能正常工作。）
    """
    try:
        try:
            is_done = bool(getattr(interaction.response, "is_done", lambda: False)())
        except Exception:
            is_done = False
        if is_done and hasattr(interaction, "edit_original_response"):
            await interaction.edit_original_response(content=content)
        else:
            await interaction.response.send_message(content=content, ephemeral=True)
    except Exception:
        try:
            await interaction.followup.send(content=content, ephemeral=True)
        except Exception:
            LOGGER.exception("bot.respond_failed")


def _format_balance_response(
    snapshot: BalanceSnapshot,
    target: Union[discord.Member, discord.User],
) -> str:
    timestamp = snapshot.last_modified_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"📊 {target.mention} 的目前餘額為 {snapshot.balance:,} 點。",
        f"🕒 最後更新時間：{timestamp}",
    ]
    if snapshot.is_throttled and snapshot.throttled_until is not None:
        cooldown = snapshot.throttled_until.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"⏳ 冷卻中，預計至：{cooldown}")
    return "\n".join(lines)


def _format_history_response(
    page: HistoryPage,
    target: Union[discord.Member, discord.User],
) -> str:
    if not page.items:
        return f"📚 {target.mention} 目前沒有可顯示的交易紀錄。"

    lines = [f"📚 {target.mention} 的最近 {len(page.items)} 筆交易："]
    for entry in page.items:
        timestamp = entry.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        counterparty: int | None
        if entry.is_credit:
            verb = "收入"
            counterparty = entry.initiator_id
            sign = "+"
        elif entry.is_debit:
            verb = "支出"
            counterparty = entry.target_id
            sign = "-"
        else:
            verb = "紀錄"
            counterparty = entry.target_id or entry.initiator_id
            sign = "*"

        counterpart_display = f"<@{counterparty}>" if counterparty else "系統"
        summary = (
            f"{timestamp} · {verb} {sign}{entry.amount:,} 點（{entry.direction}）"
            f" → {counterpart_display}"
        )
        lines.append(summary)
        if entry.reason:
            lines.append(f"  └─ 備註：{entry.reason}")

    if page.next_cursor is not None:
        next_iso = page.next_cursor.astimezone(timezone.utc).isoformat()
        lines.append(f"… 還有更多紀錄，使用 `before={next_iso}` 可繼續查詢。")

    return "\n".join(lines)


def _has_audit_permission(interaction: discord.Interaction) -> bool:
    permissions = getattr(interaction.user, "guild_permissions", None)
    if permissions is None:
        return False
    return bool(
        getattr(permissions, "administrator", False) or getattr(permissions, "manage_guild", False)
    )


def _get_balance_service() -> BalanceService:
    global _BALANCE_SERVICE
    if _BALANCE_SERVICE is None:
        pool = db_pool.get_pool()
        _BALANCE_SERVICE = BalanceService(pool)
    return _BALANCE_SERVICE


__all__ = ["build_balance_command", "build_history_command", "get_help_data", "register"]
