from __future__ import annotations

from typing import Any, Callable, Union, cast

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_data import HelpData
from src.bot.services.adjustment_service import (
    AdjustmentResult,
    AdjustmentService,
    ValidationError,
)
from src.bot.services.council_service import GovernanceNotConfiguredError
from src.bot.services.council_service_result import CouncilServiceResult
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
from src.db.gateway.council_governance import CouncilConfig
from src.infra.di.container import DependencyContainer
from src.infra.result import Err, Ok

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

        # 檢查法務部特殊權限（以國務院領袖身分作為判定基準）
        is_justice_leader = False
        justice_can_adjust_target = False
        justice_target_is_department = False
        try:
            sc_service = StateCouncilService()
            user_roles_ids = [
                getattr(role, "id", 0) for role in (getattr(interaction.user, "roles", []) or [])
            ]
            is_justice_leader = await sc_service.check_leader_permission(
                guild_id=guild_id,
                user_id=interaction.user.id,
                user_roles=user_roles_ids,
            )

            # 如果是法務部領導人，檢查目標權限
            if is_justice_leader:
                if isinstance(target, discord.Role):
                    # 法務部不能調整其他政府部門
                    target_dept = await sc_service.find_department_by_role(
                        guild_id=guild_id, role_id=target.id
                    )
                    if target_dept is None:
                        # 不是部門角色，法務部領導人可以調整
                        justice_can_adjust_target = True
                    else:
                        # 目標為其他政府部門帳戶，記錄以便回報專用錯誤訊息
                        justice_target_is_department = True
                else:
                    # 目標是個人成員，法務部領導人可以調整
                    justice_can_adjust_target = True
        except Exception:
            # 未設定國務院或檢查過程出現任何錯誤時，略過法務部特殊權限檢查，
            # 僅依照基本管理員權限與下游 service 的 UnauthorizedAdjustmentError 處理。
            pass

        # 僅在「法務部領導人嘗試調整其他部門餘額、且本身不是管理員」時，提前回傳專用錯誤訊息；
        # 其他情況一律交由 service 透過 can_adjust 與 UnauthorizedAdjustmentError 處理。
        if is_justice_leader and justice_target_is_department and not has_right:
            await interaction.response.send_message(
                content="法務部無權調整其他部門餘額", ephemeral=True
            )
            return

        # 支援以下映射：
        # - 常任理事會身分組 -> 理事會公共帳戶
        # - 部門領導人身分組 -> 對應部門政府帳戶
        # - 最高人民會議議長身分組 -> 最高人民會議帳戶
        target_id: int
        if isinstance(target, discord.Role):
            # 先嘗試理事會身分組
            cfg: CouncilConfig | None = None
            try:
                service_result = await CouncilServiceResult().get_config(guild_id=guild_id)

                if isinstance(service_result, Ok):
                    cfg = service_result.value  # type: ignore[assignment]
                else:
                    cfg = None
            except GovernanceNotConfiguredError:
                cfg = None  # 容忍未設定，改試其他身分組
            if cfg and target.id == cfg.council_role_id:
                target_id = CouncilServiceResult.derive_council_account_id(guild_id)
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

        # 呼叫服務層：同時支援 Result 模式與舊版直接回傳 AdjustmentResult 的實作
        try:
            raw_result: Any = await service.adjust_balance(
                guild_id=guild_id,
                admin_id=interaction.user.id,
                target_id=target_id,
                amount=amount,
                reason=reason,
                can_adjust=has_right or (is_justice_leader and justice_can_adjust_target),
                connection=None,
            )
        except ValidationError as exc:
            # 權限 / 參數驗證錯誤：直接顯示訊息
            await interaction.response.send_message(content=str(exc), ephemeral=True)
            return
        except Exception as exc:  # pragma: no cover - 防禦性日誌
            LOGGER.exception("bot.adjust.service_exception", error=str(exc))
            await interaction.response.send_message(
                content="處理管理調整時發生錯誤，請稍後再試。",
                ephemeral=True,
            )
            return

        adjustment_result: AdjustmentResult
        if isinstance(raw_result, Err):
            err_result = cast(Err[AdjustmentResult, Exception], raw_result)
            error = err_result.error
            LOGGER.error(
                "bot.adjust.service_error", error=str(error), error_type=type(error).__name__
            )
            if isinstance(error, ValidationError):
                await interaction.response.send_message(content=str(error), ephemeral=True)
            else:
                await interaction.response.send_message(
                    content="處理管理調整時發生錯誤，請稍後再試。",
                    ephemeral=True,
                )
            return
        elif isinstance(raw_result, Ok):
            ok_result = cast(Ok[AdjustmentResult, Any], raw_result)
            adjustment_result = ok_result.value
        else:
            # 舊版合約：直接回傳 AdjustmentResult
            adjustment_result = cast(AdjustmentResult, raw_result)

        # Get currency config
        currency_config = await currency_service.get_currency_config(guild_id=guild_id)

        message = _format_success_message(target, adjustment_result, currency_config)
        await interaction.response.send_message(content=message, ephemeral=True)

    # Pylance 在嚴格模式下無法從 decorators 推導泛型參數，導致回傳型別含 Unknown。
    # 這裡以顯式 cast 讓型別檢查器理解實際回傳為 `app_commands.Command`。
    return cast(app_commands.Command[Any, Any, None], adjust)


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
