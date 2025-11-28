from __future__ import annotations

from dataclasses import dataclass
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
from src.bot.services.council_service import CouncilServiceResult, GovernanceNotConfiguredError
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
from src.infra.result import Err, Error, Ok, Result

LOGGER = structlog.get_logger(__name__)


# --- Error Types ---


class AdjustCommandError(Error):
    """adjust 命令專屬錯誤基類"""


class GuildRequiredError(AdjustCommandError):
    """非伺服器環境錯誤"""

    def __init__(self) -> None:
        super().__init__("此命令僅能在伺服器內執行。")


class NoPermissionError(AdjustCommandError):
    """權限不足錯誤，區分一般無權限與法務部無權限"""

    permission_type: str  # "general" | "justice_department"

    def __init__(self, permission_type: str = "general") -> None:
        self.permission_type = permission_type
        if permission_type == "justice_department":
            message = "法務部無權調整其他部門餘額"
        else:
            message = "您沒有權限執行此操作"
        super().__init__(message)


class InvalidTargetError(AdjustCommandError):
    """無效目標錯誤"""

    def __init__(self, message: str = "無效的目標") -> None:
        super().__init__(message)


# --- Permission Resolution ---


@dataclass
class AdjustPermission:
    """權限解析結果"""

    has_admin_rights: bool
    is_justice_leader: bool
    can_adjust_target: bool


async def resolve_adjust_permission(
    interaction: discord.Interaction,
    target: Union[discord.Member, discord.User, discord.Role],
    state_council_service: StateCouncilService,
) -> Result[AdjustPermission, NoPermissionError]:
    """解析並驗證 adjust 命令的權限。

    Args:
        interaction: Discord 互動對象
        target: 調整目標（成員或角色）
        state_council_service: 國務院服務實例

    Returns:
        Result[AdjustPermission, NoPermissionError]: 成功時回傳權限結構，失敗時回傳錯誤
    """
    guild_id = interaction.guild_id
    if guild_id is None:
        return Err(NoPermissionError("general"))

    # 檢查基本管理員權限
    perms = getattr(interaction.user, "guild_permissions", None)
    has_admin_rights = bool(perms and (perms.administrator or perms.manage_guild))

    # 檢查法務部特殊權限
    is_justice_leader = False
    can_adjust_target = has_admin_rights  # 管理員可以調整任何目標

    try:
        user_roles_ids = [
            getattr(role, "id", 0) for role in (getattr(interaction.user, "roles", []) or [])
        ]
        is_justice_leader = await state_council_service.check_leader_permission(
            guild_id=guild_id,
            user_id=interaction.user.id,
            user_roles=user_roles_ids,
        )

        if is_justice_leader and not has_admin_rights:
            # 法務部領導人需要額外檢查目標權限
            if isinstance(target, discord.Role):
                target_dept = await state_council_service.find_department_by_role(
                    guild_id=guild_id, role_id=target.id
                )
                if target_dept is not None:
                    # 目標為其他政府部門帳戶，法務部無權調整
                    return Err(NoPermissionError("justice_department"))
                # 不是部門角色，可以調整
                can_adjust_target = True
            else:
                # 目標是個人成員，法務部領導人可以調整
                can_adjust_target = True
    except Exception:
        # 未設定國務院或檢查過程出現任何錯誤時，略過法務部特殊權限檢查
        pass

    return Ok(
        AdjustPermission(
            has_admin_rights=has_admin_rights,
            is_justice_leader=is_justice_leader,
            can_adjust_target=can_adjust_target,
        )
    )


async def resolve_target_account_id(
    guild_id: int,
    target: Union[discord.Member, discord.User, discord.Role],
    council_service: CouncilServiceResult,
    state_council_service: StateCouncilService,
    supreme_assembly_service: SupremeAssemblyService,
) -> Result[int, InvalidTargetError]:
    """解析目標的帳戶 ID。

    支援以下映射：
    - 常任理事會身分組 -> 理事會公共帳戶
    - 部門領導人身分組 -> 對應部門政府帳戶
    - 最高人民會議議長身分組 -> 最高人民會議帳戶
    - 一般成員 -> 成員 ID

    Args:
        guild_id: 伺服器 ID
        target: 調整目標（成員或角色）
        council_service: 理事會服務（Result 版本）
        state_council_service: 國務院服務
        supreme_assembly_service: 最高人民會議服務

    Returns:
        Result[int, InvalidTargetError]: 成功時回傳帳戶 ID，失敗時回傳錯誤
    """
    if not isinstance(target, discord.Role):
        # 一般成員，直接回傳成員 ID
        return Ok(target.id)

    # 嘗試理事會身分組
    cfg: CouncilConfig | None = None
    try:
        service_result = await council_service.get_config(guild_id=guild_id)
        if isinstance(service_result, Ok):
            cfg = service_result.value  # type: ignore[assignment]
    except GovernanceNotConfiguredError:
        pass  # 容忍未設定，改試其他身分組
    except Exception:
        pass

    if cfg and target.id == cfg.council_role_id:
        return Ok(CouncilServiceResult.derive_council_account_id(guild_id))

    # 嘗試最高人民會議議長身分組
    try:
        sa_cfg = await supreme_assembly_service.get_config(guild_id=guild_id)
        if sa_cfg and target.id == sa_cfg.speaker_role_id:
            account_id = await supreme_assembly_service.get_or_create_account_id(guild_id)
            return Ok(account_id)
    except SAGovernanceNotConfiguredError:
        pass
    except Exception:
        pass

    # 嘗試國務院部門身分組
    try:
        department = await state_council_service.find_department_by_role(
            guild_id=guild_id, role_id=target.id
        )
        if department is not None:
            account_id = await state_council_service.get_department_account_id(
                guild_id=guild_id, department=department
            )
            return Ok(account_id)
    except StateCouncilNotConfiguredError:
        pass
    except Exception:
        pass

    # 沒有匹配到任何已知的身分組
    return Err(
        InvalidTargetError(
            "僅支援提及常任理事會、最高人民會議議長或已綁定之部門領導人身分組，"
            "或直接指定個別成員。"
        )
    )


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
        state_council_service = StateCouncilService()
        council_service = CouncilServiceResult()
        supreme_assembly_service = SupremeAssemblyService()
    else:
        service = container.resolve(AdjustmentService)
        currency_service = container.resolve(CurrencyConfigService)
        state_council_service = container.resolve(StateCouncilService)
        council_service = container.resolve(CouncilServiceResult)
        supreme_assembly_service = container.resolve(SupremeAssemblyService)

    command = build_adjust_command(
        service,
        currency_service,
        state_council_service=state_council_service,
        council_service=council_service,
        supreme_assembly_service=supreme_assembly_service,
    )
    tree.add_command(command)
    LOGGER.debug("bot.command.adjust.registered")


def build_adjust_command(
    service: AdjustmentService,
    currency_service: CurrencyConfigService,
    *,
    state_council_service: StateCouncilService | None = None,
    council_service: CouncilServiceResult | None = None,
    supreme_assembly_service: SupremeAssemblyService | None = None,
    can_adjust: Callable[[discord.Interaction], bool] | None = None,
) -> app_commands.Command[Any, Any, Any]:
    """Build the `/adjust` slash command bound to the provided service.

    Args:
        service: 調整服務實例
        currency_service: 貨幣設定服務實例
        state_council_service: 國務院服務實例（可選，預設為新建實例）
        council_service: 理事會服務實例（可選，預設為新建實例）
        supreme_assembly_service: 最高人民會議服務實例（可選，預設為新建實例）
        can_adjust: 保留供測試相容性（已棄用）
    """
    # Note: can_adjust parameter preserved for test compatibility but not actively used
    _ = can_adjust  # Silence unused parameter warning

    # 使用傳入的服務或建立新實例（backward compatibility）
    _state_council_service = state_council_service or StateCouncilService()
    _council_service = council_service or CouncilServiceResult()
    _supreme_assembly_service = supreme_assembly_service or SupremeAssemblyService()

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
                content=_format_error_response(GuildRequiredError()),
                ephemeral=True,
            )
            return

        # 解析權限（使用 Result 模式，使用 DI 注入的服務）
        permission_result = await resolve_adjust_permission(
            interaction, target, _state_council_service
        )
        if permission_result.is_err():
            error: Error = permission_result.unwrap_err()
            await interaction.response.send_message(
                content=_format_error_response(error),
                ephemeral=True,
            )
            return

        permission = permission_result.unwrap()
        can_adjust = permission.has_admin_rights or (
            permission.is_justice_leader and permission.can_adjust_target
        )

        # 解析目標帳戶 ID（使用 Result 模式，使用 DI 注入的服務）
        target_result = await resolve_target_account_id(
            guild_id,
            target,
            _council_service,
            _state_council_service,
            _supreme_assembly_service,
        )
        if target_result.is_err():
            error = target_result.unwrap_err()
            await interaction.response.send_message(
                content=_format_error_response(error),
                ephemeral=True,
            )
            return

        target_id = target_result.unwrap()

        # 呼叫服務層（Result 模式）
        service_result: Any = await service.adjust_balance(
            guild_id=guild_id,
            admin_id=interaction.user.id,
            target_id=target_id,
            amount=amount,
            reason=reason,
            can_adjust=can_adjust,
            connection=None,
        )

        # 處理服務回傳結果
        adjustment_result: AdjustmentResult
        if isinstance(service_result, Err):
            error = cast(Error, service_result.unwrap_err())
            LOGGER.error(
                "bot.adjust.service_error", error=str(error), error_type=type(error).__name__
            )
            await interaction.response.send_message(
                content=_format_error_response(error),
                ephemeral=True,
            )
            return
        elif isinstance(service_result, Ok):
            adjustment_result = cast(AdjustmentResult, service_result.unwrap())
        else:
            # 舊版合約：直接回傳 AdjustmentResult
            adjustment_result = cast(AdjustmentResult, service_result)

        # 取得貨幣設定並格式化成功訊息
        currency_config = await currency_service.get_currency_config(guild_id=guild_id)
        message = _format_success_message(target, adjustment_result, currency_config)
        await interaction.response.send_message(content=message, ephemeral=True)

    # Pylance 在嚴格模式下無法從 decorators 推導泛型參數，導致回傳型別含 Unknown。
    # 這裡以顯式 cast 讓型別檢查器理解實際回傳為 `app_commands.Command`。
    return cast(app_commands.Command[Any, Any, None], adjust)


def _format_error_response(error: Exception) -> str:
    """格式化錯誤訊息。

    Args:
        error: 錯誤實例

    Returns:
        格式化後的錯誤訊息字串
    """
    if isinstance(error, (AdjustCommandError, ValidationError)):
        return str(error)
    return "處理管理調整時發生錯誤，請稍後再試。"


def _format_success_message(
    target: Union[discord.Member, discord.User, discord.Role],
    result: AdjustmentResult,
    currency_config: CurrencyConfigResult,
) -> str:
    """格式化成功訊息。"""
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
