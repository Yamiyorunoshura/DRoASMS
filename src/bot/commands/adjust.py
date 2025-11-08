from __future__ import annotations

from typing import Any, Callable, Union

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_data import HelpData
from src.bot.services.adjustment_service import (
    AdjustmentResult,
    AdjustmentService,
    UnauthorizedAdjustmentError,
    ValidationError,
)
from src.bot.services.council_service import CouncilService, GovernanceNotConfiguredError
from src.bot.services.currency_config_service import (
    CurrencyConfigResult,
    CurrencyConfigService,
)
from src.bot.services.state_council_service import (
    StateCouncilNotConfiguredError,
    StateCouncilService,
)
from src.bot.services.supreme_assembly_service import (
    GovernanceNotConfiguredError as SAGovernanceNotConfiguredError,
)
from src.bot.services.supreme_assembly_service import (
    SupremeAssemblyService,
)
from src.infra.di.container import DependencyContainer

LOGGER = structlog.get_logger(__name__)


def get_help_data() -> HelpData:
    """Return help information for the adjust command."""
    return {
        "name": "adjust",
        "description": (
            "管理員調整成員點數（正數加值，負數扣點）。"
            "支援調整個別成員、理事會身分組、最高人民會議議長身分組或部門領導人身分組的點數。"
        ),
        "category": "economy",
        "parameters": [
            {
                "name": "target",
                "description": (
                    "要調整點數的成員、理事會身分組、最高人民會議議長身分組或部門" "領導人身分組"
                ),
                "required": True,
            },
            {
                "name": "amount",
                "description": "可以為正數（加值）或負數（扣點）",
                "required": True,
            },
            {
                "name": "reason",
                "description": "必填，將寫入審計紀錄",
                "required": True,
            },
        ],
        "permissions": ["administrator", "manage_guild"],
        "examples": [
            "/adjust @user 100 活動獎勵",
            "/adjust @user -50 違規扣點",
            "/adjust @CouncilRole 1000 理事會補助",
        ],
        "tags": ["管理", "調整"],
    }


def register(
    tree: app_commands.CommandTree, *, container: DependencyContainer | None = None
) -> None:
    """Register the /adjust slash command with the provided command tree."""
    if container is None:
        # Fallback to old behavior for backward compatibility during migration
        from src.db import pool as db_pool

        pool = db_pool.get_pool()
        service = AdjustmentService(pool)
        currency_service = CurrencyConfigService(pool)
    else:
        service = container.resolve(AdjustmentService)
        currency_service = container.resolve(CurrencyConfigService)

    command = build_adjust_command(service, currency_service)
    tree.add_command(command)
    LOGGER.debug("bot.command.adjust.registered")


def build_adjust_command(
    service: AdjustmentService,
    currency_service: CurrencyConfigService,
    *,
    can_adjust: Callable[[discord.Interaction], bool] | None = None,
) -> app_commands.Command[Any, Any, Any]:
    """Build the `/adjust` slash command bound to the provided service.

    The `can_adjust` predicate determines if the invoking user has admin rights.
    Defaults to True if the user has Administrator or Manage Guild permissions.
    """

    def _default_can_adjust(interaction: discord.Interaction) -> bool:
        perms = getattr(interaction.user, "guild_permissions", None)
        return bool(perms and (perms.administrator or perms.manage_guild))

    predicate = can_adjust or _default_can_adjust

    @app_commands.command(
        name="adjust",
        description="管理員調整成員點數（正數加值，負數扣點）。",
    )
    @app_commands.describe(
        target=("要調整點數的成員、理事會身分組、最高人民會議議長身分組或部門" "領導人身分組"),
        amount="可以為正數（加值）或負數（扣點）",
        reason="必填，將寫入審計紀錄",
    )
    async def adjust(
        interaction: discord.Interaction,
        target: Union[discord.Member, discord.User, discord.Role],
        amount: int,
        reason: str,
    ) -> None:
        guild_id = interaction.guild_id
        if guild_id is None:
            await interaction.response.send_message(
                content="此命令僅能在伺服器內執行。",
                ephemeral=True,
            )
            return

        has_right = predicate(interaction)

        # 支援以下映射：
        # - 常任理事會身分組 -> 理事會公共帳戶
        # - 部門領導人身分組 -> 對應部門政府帳戶
        # - 最高人民會議議長身分組 -> 最高人民會議帳戶
        target_id: int
        if isinstance(target, discord.Role):
            # 先嘗試理事會身分組
            try:
                cfg = await CouncilService().get_config(guild_id=guild_id)
            except GovernanceNotConfiguredError:
                cfg = None  # 容忍未設定，改試其他身分組
            if cfg and target.id == cfg.council_role_id:
                target_id = CouncilService.derive_council_account_id(guild_id)
            else:
                # 嘗試最高人民會議議長身分組
                sa_service = SupremeAssemblyService()
                try:
                    sa_cfg = await sa_service.get_config(guild_id=guild_id)
                except SAGovernanceNotConfiguredError:
                    sa_cfg = None
                if sa_cfg and target.id == sa_cfg.speaker_role_id:
                    target_id = SupremeAssemblyService.derive_account_id(guild_id)
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
                                "僅支援提及常任理事會、最高人民會議議長或已綁定之部門領導人身分組，"
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
        try:
            result = await service.adjust_balance(
                guild_id=guild_id,
                admin_id=interaction.user.id,
                target_id=target_id,
                amount=amount,
                reason=reason,
                can_adjust=has_right,
                connection=None,
            )
        except UnauthorizedAdjustmentError as exc:
            await interaction.response.send_message(content=str(exc), ephemeral=True)
            return
        except ValidationError as exc:
            await interaction.response.send_message(content=str(exc), ephemeral=True)
            return
        except Exception as exc:  # pragma: no cover - unexpected
            LOGGER.exception("bot.adjust.unexpected_error", error=str(exc))
            await interaction.response.send_message(
                content="處理管理調整時發生未預期錯誤，請稍後再試。",
                ephemeral=True,
            )
            return

        # Get currency config
        currency_config = await currency_service.get_currency_config(guild_id=guild_id)

        message = _format_success_message(target, result, currency_config)
        await interaction.response.send_message(content=message, ephemeral=True)

    return adjust


def _format_success_message(
    target: Union[discord.Member, discord.User, discord.Role],
    result: AdjustmentResult,
    currency_config: CurrencyConfigResult,
) -> str:
    action = "加值" if result.direction == "adjustment_grant" else "扣點"
    currency_display = (
        f"{currency_config.currency_name} {currency_config.currency_icon}".strip()
        if currency_config.currency_icon
        else currency_config.currency_name
    )
    parts = [
        f"✅ 已對 {target.mention} 進行{action} {result.amount:,} {currency_display}。",
        f"👉 目前餘額為 {result.target_balance_after:,} {currency_display}。",
    ]
    reason = result.metadata.get("reason")
    if reason:
        parts.append(f"📝 原因：{reason}")
    return "\n".join(parts)


__all__ = ["build_adjust_command", "get_help_data", "register"]
