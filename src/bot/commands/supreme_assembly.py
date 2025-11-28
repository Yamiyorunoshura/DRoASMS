from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, cast
from uuid import UUID

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_data import HelpData
from src.bot.interaction_compat import (
    send_message_compat,
    send_modal_compat,
)
from src.bot.services.balance_service import BalanceService
from src.bot.services.council_service import CouncilServiceResult
from src.bot.services.department_registry import get_registry
from src.bot.services.permission_service import PermissionService
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.supreme_assembly_service import (
    GovernanceNotConfiguredError,
    PermissionDeniedError,
    SupremeAssemblyService,
    VoteAlreadyExistsError,
)
from src.bot.services.supreme_assembly_service_result import SupremeAssemblyServiceResult
from src.bot.services.transfer_service import TransferService, TransferValidationError
from src.bot.ui.base import PersistentPanelView
from src.bot.utils.error_templates import ErrorMessageTemplates
from src.db.pool import get_pool
from src.infra.di.container import DependencyContainer
from src.infra.events.supreme_assembly_events import (
    SupremeAssemblyEvent,
)
from src.infra.events.supreme_assembly_events import (
    subscribe as subscribe_supreme_assembly_events,
)
from src.infra.result import Err, Error, Result
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)


# 針對 Discord Interaction 的 values 解析做統一型別收斂，
# 以免 Pylance 在嚴格模式下將 comprehension 內的 v 判為 Unknown。
def _extract_select_values(interaction: discord.Interaction) -> list[str]:
    data = cast(dict[str, Any], interaction.data or {})
    raw_values = data.get("values")
    if not isinstance(raw_values, list):
        return []
    typed_values = cast(list[str], raw_values)
    return typed_values


async def _resolve_department_account_id_for_supreme(
    *,
    guild_id: int,
    department_name: str,
    sc_gateway: "Any | None" = None,
    state_council_service: "StateCouncilService | None" = None,
) -> int:
    """取得部門帳戶 ID（最高人民會議轉帳使用）。

    優先順序：
    1) 讀取國務院組態中的對應帳戶 ID（含法務部/社福部欄位相容）。
    2) 回退至 StateCouncilService.get_department_account_id（會查詢政府帳戶表）。
    3) 最後以 derive_department_account_id 推導穩定值。
    """

    # 1) 嘗試從國務院組態取得實際帳戶 ID，避免歷史資料與推導規則不一致
    try:
        from src.db.gateway.state_council_governance import StateCouncilGovernanceGateway

        gateway = sc_gateway or StateCouncilGovernanceGateway()
        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            cfg = await gateway.fetch_state_council_config(conn, guild_id=guild_id)

        if cfg is not None:
            name_to_account: dict[str, int | None] = {
                "內政部": cfg.internal_affairs_account_id,
                "財政部": cfg.finance_account_id,
                "國土安全部": cfg.security_account_id,
                "中央銀行": cfg.central_bank_account_id,
            }

            # 法務部欄位：若新欄位不存在，回退舊版 welfare_account_id
            justice_id = getattr(cfg, "justice_account_id", None)
            if justice_id is None:
                justice_id = getattr(cfg, "welfare_account_id", None)
            if justice_id is not None:
                name_to_account["法務部"] = justice_id

            account_id = name_to_account.get(department_name)
            if account_id is not None:
                return int(account_id)
    except Exception as exc:  # pragma: no cover - 失敗時記錄並回退
        LOGGER.debug(
            "supreme_assembly.transfer.department_config_lookup_failed",
            guild_id=guild_id,
            department=department_name,
            error=str(exc),
        )

    # 2) 改用 StateCouncilService 的查詢邏輯（會查政府帳戶表，缺失時回退推導值）
    sc_service = state_council_service or StateCouncilService()
    try:
        return await sc_service.get_department_account_id(
            guild_id=guild_id, department=department_name
        )
    except Exception as exc:  # pragma: no cover - 最後回退推導值
        LOGGER.debug(
            "supreme_assembly.transfer.department_account_lookup_failed",
            guild_id=guild_id,
            department=department_name,
            error=str(exc),
        )
        return StateCouncilService.derive_department_account_id(guild_id, department_name)


def get_help_data() -> dict[str, HelpData]:
    """Return help information for supreme_assembly commands."""
    return {
        "supreme_assembly": {
            "name": "supreme_assembly",
            "description": "最高人民會議治理指令群組",
            "category": "governance",
            "parameters": [],
            "permissions": [],
            "examples": [],
            "tags": ["最高人民會議", "治理"],
        },
        "supreme_assembly config_speaker_role": {
            "name": "supreme_assembly config_speaker_role",
            "description": "設定最高人民會議議長身分組（角色）。需要管理員或管理伺服器權限。",
            "category": "governance",
            "parameters": [
                {
                    "name": "role",
                    "description": "Discord 角色，將作為議長身分組",
                    "required": True,
                },
            ],
            "permissions": ["administrator", "manage_guild"],
            "examples": ["/supreme_assembly config_speaker_role @SpeakerRole"],
            "tags": ["設定", "配置"],
        },
        "supreme_assembly config_member_role": {
            "name": "supreme_assembly config_member_role",
            "description": "設定最高人民會議議員身分組（角色）。需要管理員或管理伺服器權限。",
            "category": "governance",
            "parameters": [
                {
                    "name": "role",
                    "description": "Discord 角色，將作為議員名冊來源",
                    "required": True,
                },
            ],
            "permissions": ["administrator", "manage_guild"],
            "examples": ["/supreme_assembly config_member_role @MemberRole"],
            "tags": ["設定", "配置"],
        },
        "supreme_assembly panel": {
            "name": "supreme_assembly panel",
            "description": "開啟最高人民會議面板（表決/投票/傳召）。僅限議長或議員使用。",
            "category": "governance",
            "parameters": [],
            "permissions": [],
            "examples": ["/supreme_assembly panel"],
            "tags": ["面板", "操作"],
        },
    }


def register(
    tree: app_commands.CommandTree, *, container: DependencyContainer | None = None
) -> None:
    """Register the /supreme_assembly slash command group with the provided command tree."""
    if container is None:
        # Fallback to old behavior for backward compatibility during migration
        service = SupremeAssemblyService()
        service_result = SupremeAssemblyServiceResult(legacy_service=service)
        council_service = CouncilServiceResult()
        state_council_service = StateCouncilService()
        permission_service = PermissionService(
            council_service=council_service,
            state_council_service=state_council_service,
            supreme_assembly_service=service,
        )
    else:
        service = container.resolve(SupremeAssemblyService)
        service_result = container.resolve(SupremeAssemblyServiceResult)
        permission_service = container.resolve(PermissionService)

    tree.add_command(
        build_supreme_assembly_group(
            service,
            permission_service=permission_service,
            service_result=service_result,
        )
    )
    # Install background scheduler if client is available
    client = getattr(tree, "client", None)
    if client is not None:
        _install_background_scheduler(client, service)
    LOGGER.debug("bot.command.supreme_assembly.registered")


def build_supreme_assembly_group(
    service: SupremeAssemblyService,
    *,
    permission_service: PermissionService | None = None,
    service_result: SupremeAssemblyServiceResult | None = None,
) -> app_commands.Group:
    """Build the /supreme_assembly command group."""
    supreme_assembly = app_commands.Group(
        name="supreme_assembly", description="最高人民會議治理指令群組"
    )

    async def _invoke_supreme(
        method: str, **kwargs: Any
    ) -> tuple[Any | None, Error | Exception | None]:
        if service_result is not None:
            raw = await getattr(service_result, method)(**kwargs)
            result = cast(Result[Any, Error], raw)
            if isinstance(result, Err):
                return None, result.error
            value = getattr(result, "value", result)
            return cast(Any, value), None
        try:
            value = await getattr(service, method)(**kwargs)
            return value, None
        except Exception as exc:  # pragma: no cover - defensive
            return None, exc

    async def _reply_supreme_error(
        *,
        interaction: discord.Interaction,
        error: Error | Exception,
        title: str,
        log_event: str,
        context: dict[str, Any],
    ) -> None:
        if isinstance(error, Error):
            description = error.message
        else:
            LOGGER.warning(log_event, **context, error=str(error))
            description = str(error)
        embed = discord.Embed(
            title=title,
            description=description,
            color=0xE74C3C,
        )
        await send_message_compat(interaction, embed=embed, ephemeral=True)

    @supreme_assembly.command(
        name="config_speaker_role", description="設定最高人民會議議長身分組（角色）"
    )
    @app_commands.describe(role="Discord 角色，將作為議長身分組")
    async def config_speaker_role(interaction: discord.Interaction, role: discord.Role) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return
        # Require admin/manage_guild
        perms = getattr(interaction.user, "guild_permissions", None)
        if not perms or not (perms.administrator or perms.manage_guild):
            await send_message_compat(
                interaction, content="需要管理員或管理伺服器權限。", ephemeral=True
            )
            return
        existing_cfg, cfg_error = await _invoke_supreme(
            "get_config",
            guild_id=interaction.guild_id,
        )

        bootstrapped = False
        member_role_id = 0
        if cfg_error is None and existing_cfg is not None:
            member_role_id = existing_cfg.member_role_id
        elif isinstance(cfg_error, GovernanceNotConfiguredError):
            bootstrapped = True
        elif cfg_error is not None:
            await _reply_supreme_error(
                interaction=interaction,
                error=cfg_error,
                title="設定議長身分組失敗",
                log_event="supreme_assembly.config_speaker_role.error",
                context={
                    "guild_id": interaction.guild_id,
                    "role_id": role.id,
                    "user_id": interaction.user.id,
                },
            )
            return

        _, set_error = await _invoke_supreme(
            "set_config",
            guild_id=interaction.guild_id,
            speaker_role_id=role.id,
            member_role_id=member_role_id,
        )
        if set_error is not None:
            await _reply_supreme_error(
                interaction=interaction,
                error=set_error,
                title="設定議長身分組失敗",
                log_event="supreme_assembly.config_speaker_role.error",
                context={
                    "guild_id": interaction.guild_id,
                    "role_id": role.id,
                    "user_id": interaction.user.id,
                },
            )
            return

        account_id = await service.get_or_create_account_id(interaction.guild_id)
        if bootstrapped:
            await send_message_compat(
                interaction,
                content=(
                    f"已設定議長角色：{role.mention}（帳戶ID {account_id}）。"
                    " 已建立治理設定，請再執行 /supreme_assembly"
                    " config_member_role 設定議員身分組。"
                ),
                ephemeral=True,
            )
        else:
            await send_message_compat(
                interaction,
                content=f"已設定議長角色：{role.mention}（帳戶ID {account_id}）",
                ephemeral=True,
            )

    @supreme_assembly.command(
        name="config_member_role", description="設定最高人民會議議員身分組（角色）"
    )
    @app_commands.describe(role="Discord 角色，將作為議員名冊來源")
    async def config_member_role(interaction: discord.Interaction, role: discord.Role) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return
        # Require admin/manage_guild
        perms = getattr(interaction.user, "guild_permissions", None)
        if not perms or not (perms.administrator or perms.manage_guild):
            await send_message_compat(
                interaction, content="需要管理員或管理伺服器權限。", ephemeral=True
            )
            return
        existing_cfg, cfg_error = await _invoke_supreme(
            "get_config",
            guild_id=interaction.guild_id,
        )

        bootstrapped = False
        speaker_role_id = 0
        if cfg_error is None and existing_cfg is not None:
            speaker_role_id = existing_cfg.speaker_role_id
        elif isinstance(cfg_error, GovernanceNotConfiguredError):
            bootstrapped = True
        elif cfg_error is not None:
            await _reply_supreme_error(
                interaction=interaction,
                error=cfg_error,
                title="設定議員身分組失敗",
                log_event="supreme_assembly.config_member_role.error",
                context={
                    "guild_id": interaction.guild_id,
                    "role_id": role.id,
                    "user_id": interaction.user.id,
                },
            )
            return

        _, set_error = await _invoke_supreme(
            "set_config",
            guild_id=interaction.guild_id,
            speaker_role_id=speaker_role_id,
            member_role_id=role.id,
        )
        if set_error is not None:
            await _reply_supreme_error(
                interaction=interaction,
                error=set_error,
                title="設定議員身分組失敗",
                log_event="supreme_assembly.config_member_role.error",
                context={
                    "guild_id": interaction.guild_id,
                    "role_id": role.id,
                    "user_id": interaction.user.id,
                },
            )
            return

        account_id = await service.get_or_create_account_id(interaction.guild_id)
        if bootstrapped:
            await send_message_compat(
                interaction,
                content=(
                    f"已設定議員角色：{role.mention}（帳戶ID {account_id}）。"
                    " 已建立治理設定，請再執行 /supreme_assembly"
                    " config_speaker_role 設定議長身分組。"
                ),
                ephemeral=True,
            )
        else:
            await send_message_compat(
                interaction,
                content=f"已設定議員角色：{role.mention}（帳戶ID {account_id}）",
                ephemeral=True,
            )

    @supreme_assembly.command(name="panel", description="開啟最高人民會議面板（表決/投票/傳召）")
    async def panel(
        interaction: discord.Interaction,
    ) -> None:
        # 僅允許在伺服器使用
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return
        # 檢查是否完成治理設定
        try:
            cfg = await service.get_config(guild_id=interaction.guild_id)
        except GovernanceNotConfiguredError:
            await send_message_compat(
                interaction,
                content=(
                    "尚未完成治理設定，請先執行 /supreme_assembly config_speaker_role 和 "
                    "/supreme_assembly config_member_role。"
                ),
                ephemeral=True,
            )
            return

        user_roles = [role.id for role in getattr(interaction.user, "roles", [])]
        if permission_service is not None:
            # 使用最高人民議會權限檢查器以支援人民代表身分組
            perm_check = await permission_service.check_supreme_peoples_assembly_permission(
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                user_roles=user_roles,
                operation="panel_access",
            )
            if isinstance(perm_check, Err):
                error_message = ErrorMessageTemplates.from_error(perm_check.error)
                await send_message_compat(interaction, content=error_message, ephemeral=True)
                return
            perm_result = perm_check.value
            if not perm_result.allowed:
                error_message = perm_result.reason or "僅限議長或人民代表可開啟面板。"
                await send_message_compat(interaction, content=error_message, ephemeral=True)
                return
            is_speaker = perm_result.permission_level == "speaker"
            is_member = perm_result.permission_level in {"speaker", "representative", "member"}
        else:
            speaker_role = interaction.guild.get_role(cfg.speaker_role_id)
            member_role = interaction.guild.get_role(cfg.member_role_id)

            is_speaker = (
                speaker_role is not None
                and isinstance(interaction.user, discord.Member)
                and speaker_role in interaction.user.roles
            )
            is_member = (
                member_role is not None
                and isinstance(interaction.user, discord.Member)
                and member_role in interaction.user.roles
            )

            if not (is_speaker or is_member):
                await send_message_compat(
                    interaction, content="僅限議長或議員可開啟面板。", ephemeral=True
                )
                return

        view = SupremeAssemblyPanelView(
            service=service,
            guild=interaction.guild,
            author_id=interaction.user.id,
            speaker_role_id=cfg.speaker_role_id,
            member_role_id=cfg.member_role_id,
            is_speaker=is_speaker,
            is_member=is_member,
        )
        await view.refresh_options()
        embed = await view.build_summary_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            message = cast(discord.Message, await interaction.original_response())
            await view.bind_message(message)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning(
                "supreme_assembly.panel.bind_failed",
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                error=str(exc),
            )
        LOGGER.info(
            "supreme_assembly.panel.open",
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
        )

    # 型別標註：觸發對已裝飾之指令物件的存取，避免 Pylance 誤判未使用函式
    _ = (
        cast(app_commands.Command[Any, Any, None], config_speaker_role),
        cast(app_commands.Command[Any, Any, None], config_member_role),
        cast(app_commands.Command[Any, Any, None], panel),
    )
    return supreme_assembly


__all__ = ["build_supreme_assembly_group", "get_help_data", "register"]


# --- Panel UI ---


class SupremeAssemblyPanelView(PersistentPanelView):
    """最高人民會議面板容器（ephemeral）。"""

    panel_type = "supreme_assembly"

    def __init__(
        self,
        *,
        service: SupremeAssemblyService,
        guild: discord.Guild,
        author_id: int,
        speaker_role_id: int,
        member_role_id: int,
        is_speaker: bool,
        is_member: bool,
    ) -> None:
        super().__init__(author_id=author_id, timeout=600.0)
        self.service = service
        self.guild = guild
        self.speaker_role_id = speaker_role_id
        self.member_role_id = member_role_id
        self.is_speaker = is_speaker
        self.is_member = is_member
        self._unsubscribe: Callable[[], Awaitable[None]] | None = None
        self._update_lock = asyncio.Lock()
        self._paginator: Any | None = None  # 分頁器屬性

        # 元件：轉帳、發起表決（議長或人民代表）、傳召（僅議長）、使用指引
        self._transfer_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="轉帳",
            style=discord.ButtonStyle.primary,
        )
        self._transfer_btn.callback = self._on_click_transfer
        self.add_item(self._transfer_btn)

        if self.is_member:
            self._propose_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="發起表決",
                style=discord.ButtonStyle.primary,
            )
            self._propose_btn.callback = self._on_click_propose
            self.add_item(self._propose_btn)

        if self.is_speaker:
            self._summon_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="傳召",
                style=discord.ButtonStyle.secondary,
            )
            self._summon_btn.callback = self._on_click_summon
            self.add_item(self._summon_btn)

        self._help_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="使用指引",
            style=discord.ButtonStyle.secondary,
        )
        self._help_btn.callback = self._on_click_help
        self.add_item(self._help_btn)

        # 查看所有提案按鈕（使用新的分頁系統）
        self._view_all_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="📋 查看所有提案",
            style=discord.ButtonStyle.secondary,
        )
        self._view_all_btn.callback = self._on_click_view_all_proposals
        self.add_item(self._view_all_btn)

        self._select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder="選擇進行中表決提案以投票",
            min_values=1,
            max_values=1,
            options=[],
        )
        self._select.callback = self._on_select_proposal
        self.add_item(self._select)

    async def _resolve_account_id(self) -> int:
        try:
            return await self.service.get_or_create_account_id(self.guild.id)
        except Exception as exc:  # pragma: no cover - 記錄並回退
            LOGGER.debug(
                "supreme_assembly.panel.account.resolve_failed",
                guild_id=self.guild.id,
                error=str(exc),
            )
            return SupremeAssemblyService.derive_account_id(self.guild.id)

    async def bind_message(self, message: discord.Message) -> None:
        """綁定訊息並訂閱治理事件，以便即時更新。"""
        if self._message is not None:
            return
        await super().bind_message(message)
        try:
            self._unsubscribe = await subscribe_supreme_assembly_events(
                self.guild.id,
                self._handle_event,
            )
            LOGGER.info(
                "supreme_assembly.panel.subscribe",
                guild_id=self.guild.id,
                message_id=message.id,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._unsubscribe = None
            LOGGER.warning(
                "supreme_assembly.panel.subscribe_failed",
                guild_id=self.guild.id,
                error=str(exc),
            )

    async def build_summary_embed(self) -> discord.Embed:
        """產生面板摘要 Embed（餘額、議員名單）。"""
        embed = discord.Embed(title="最高人民會議面板", color=0xE74C3C)
        balance_str = "N/A"
        try:
            if self.author_id is None:
                raise ValueError("author_id is required")
            balance_service = BalanceService(get_pool())
            account_id = await self._resolve_account_id()
            snap_result = await balance_service.get_balance_snapshot(
                guild_id=self.guild.id,
                requester_id=self.author_id,
                target_member_id=account_id,
                can_view_others=True,
            )
            if hasattr(snap_result, "is_err") and callable(getattr(snap_result, "is_err", None)):
                _result = cast("Result[Any, Exception]", snap_result)
                if _result.is_err():
                    raise _result.unwrap_err()
                snap = _result.unwrap()
            else:
                snap = snap_result  # Legacy BalanceSnapshot
            balance_str = f"{getattr(snap, 'balance', 0):,}"
        except Exception as exc:  # pragma: no cover - best effort
            LOGGER.warning(
                "supreme_assembly.panel.summary.balance_error",
                guild_id=self.guild.id,
                error=str(exc),
            )

        role = self.guild.get_role(self.member_role_id)
        members = role.members if role is not None else []
        N = 10
        top_mentions = ", ".join(m.mention for m in members[:N]) if members else "(無)"
        member_type = "人民代表" if len(members) > 0 else "議員"
        summary = f"餘額：{balance_str}｜{member_type}（{len(members)}）：{top_mentions}"
        embed.add_field(name="摘要", value=summary, inline=False)

        # 根據使用者權限等級顯示不同的功能說明
        if self.is_speaker:
            embed.description = "在此可：轉帳、發起表決、投票、傳召。（議長權限）"
        elif self.is_member:
            embed.description = "在此可：轉帳、發起表決、投票。（人民代表權限）"
        else:
            embed.description = "在此可：轉帳、投票。"
        return embed

    def _build_help_embed(self) -> discord.Embed:
        """建構最高人民會議面板之使用指引。"""
        lines = [
            "• 開啟方式：於伺服器使用 /supreme_assembly panel（僅限議長或人民代表）。",
            (
                "• 轉帳功能：點擊「轉帳」，選擇轉帳類型（使用者、常任理事會、政府部門），"
                "然後選擇受款人、輸入金額和用途描述。"
            ),
            (
                "• 轉帳類型：可選擇轉帳給使用者（使用 Discord 使用者選擇器）、"
                "轉帳給常任理事會或轉帳給政府部門（從下拉選單選擇）。"
            ),
            "• 發起表決：僅議長或人民代表可發起表決，需填寫提案內容、金額（如適用）和用途描述。",
            "• 名冊快照：建案當下鎖定人民代表名單與投票門檻 T，用於後續投票與決議。",
            "• 投票：人民代表可於「進行中表決」下拉選擇提案後進行「同意/反對/棄權」。",
            "• 投票規則：投票後不可改選，與理事會機制不同。",
            "• 匿名投票：進行中僅顯示合計票數，結案後揭露個別投票。",
            "• 傳召功能：僅議長可使用，可傳召人民代表或政府官員，系統會發送私訊通知。",
            "• 即時更新：面板開啟期間會自動刷新清單與合計票數。",
            "• 私密性：所有回覆皆為 ephemeral，僅對開啟者可見。",
        ]
        embed = discord.Embed(title="ℹ️ 使用指引｜最高人民會議面板", color=0xE74C3C)
        embed.description = "\n".join(lines)
        return embed

    async def _on_click_help(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        try:
            await send_message_compat(interaction, embed=self._build_help_embed(), ephemeral=True)
        except Exception:
            # 後援：若已回覆，改用 followup
            try:
                await interaction.followup.send(embed=self._build_help_embed(), ephemeral=True)
            except Exception:
                pass

    async def _on_pagination_update(self) -> None:
        """分頁器更新回調，用於即時更新。"""
        # 當分頁器需要更新時，重新載入提案數據
        await self.refresh_options()

    async def _on_click_view_all_proposals(self, interaction: discord.Interaction) -> None:
        """查看所有提案的分頁列表。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        if not hasattr(self, "_paginator") or not self._paginator:
            await send_message_compat(
                interaction,
                content="分頁器尚未初始化，請稍後再試。",
                ephemeral=True,
            )
            return

        try:
            # 創建分頁訊息
            embed = self._paginator.create_embed(0)
            view = self._paginator.create_view()

            await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        except Exception as exc:
            LOGGER.exception(
                "supreme_assembly.panel.view_all_proposals.error",
                error=str(exc),
            )
            await interaction.response.send_message(
                "顯示提案列表時發生錯誤，請稍後再試。",
                ephemeral=True,
            )

    async def refresh_options(self) -> None:
        """以最近進行中提案刷新選單（使用新的分頁系統）。"""
        try:
            active = await self.service.list_active_proposals(guild_id=self.guild.id)
            # 僅顯示本 guild 的進行中提案（依 created_at 降冪）
            items = [p for p in active if p.status == "進行中"]
            items.sort(key=lambda p: p.created_at, reverse=True)

            # 更新分頁器
            if hasattr(self, "_paginator") and self._paginator:
                await self._paginator.refresh_items(items)
            else:
                # 初始化分頁器
                from src.bot.ui.supreme_assembly_paginator import SupremeAssemblyProposalPaginator

                self._paginator = SupremeAssemblyProposalPaginator(
                    proposals=items,
                    author_id=self.author_id,
                    guild=self.guild,
                )
                # 設置即時更新回調
                self._paginator.set_update_callback(self._on_pagination_update)

            # 維持向後相容：仍然更新傳統選單（但限制為最近 10 筆）
            recent_items = items[:10]
            options: list[discord.SelectOption] = []
            for p in recent_items:
                label = _format_proposal_title(p)
                desc = _format_proposal_desc(p)
                options.append(
                    discord.SelectOption(
                        label=label,
                        description=desc,
                        value=str(p.proposal_id),
                    )
                )
            # 當沒有提案時提供禁用項
            if not options:
                options = [
                    discord.SelectOption(
                        label="目前沒有進行中提案",
                        description="可先建立新提案",
                        value="none",
                        default=True,
                    )
                ]
                self._select.disabled = True
            else:
                self._select.disabled = False
            self._select.options = options
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("supreme_assembly.panel.refresh.error", error=str(exc))

    async def _on_click_transfer(self, interaction: discord.Interaction) -> None:
        # 僅限議長或議員
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("僅限面板開啟者操作。", ephemeral=True)
            return
        view = SupremeAssemblyTransferTypeSelectionView(service=self.service, guild=self.guild)
        await send_message_compat(
            interaction, content="請選擇轉帳類型：", view=view, ephemeral=True
        )

    async def _on_click_propose(self, interaction: discord.Interaction) -> None:
        # 僅限議長或人民代表
        can_propose = self.is_speaker or self.is_member
        if not can_propose or interaction.user.id != self.author_id:
            await send_message_compat(
                interaction, content="僅限議長或人民代表可發起表決。", ephemeral=True
            )
            return
        try:
            cfg = await self.service.get_config(guild_id=self.guild.id)
        except GovernanceNotConfiguredError:
            await send_message_compat(interaction, content="尚未完成治理設定。", ephemeral=True)
            return
        role = self.guild.get_role(cfg.member_role_id)
        if role is None or len(role.members) == 0:
            await send_message_compat(
                interaction, content="議員名冊為空，請先確認角色有成員。", ephemeral=True
            )
            return
        modal = CreateProposalModal(service=self.service, guild=self.guild)
        await send_modal_compat(interaction, modal)

    async def _on_click_summon(self, interaction: discord.Interaction) -> None:
        # 僅限議長
        if not self.is_speaker or interaction.user.id != self.author_id:
            await send_message_compat(
                interaction, content="僅限議長可使用傳召功能。", ephemeral=True
            )
            return
        view = SummonTypeSelectionView(service=self.service, guild=self.guild)
        await send_message_compat(
            interaction, content="請選擇傳召類型：", view=view, ephemeral=True
        )

    async def _on_select_proposal(self, interaction: discord.Interaction) -> None:
        # 直接讀取選擇值
        raw_values = self._select.values
        pid_str = raw_values[0] if raw_values else None
        if pid_str in (None, "none"):
            await send_message_compat(interaction, content="沒有可操作的提案。", ephemeral=True)
            return

        try:
            pid = UUID(pid_str)
        except Exception:
            await send_message_compat(interaction, content="選項格式錯誤。", ephemeral=True)
            return
        proposal = await self.service.get_proposal(proposal_id=pid)
        if proposal is None or proposal.guild_id != self.guild.id:
            await send_message_compat(
                interaction, content="提案不存在或不屬於此伺服器。", ephemeral=True
            )
            return

        embed = discord.Embed(title="表決提案詳情", color=0x3498DB)
        embed.add_field(name="提案編號", value=str(proposal.proposal_id), inline=False)
        if proposal.title:
            embed.add_field(name="標題", value=proposal.title, inline=False)
        if proposal.description:
            embed.add_field(name="內容", value=proposal.description, inline=False)
        embed.add_field(
            name="狀態",
            value=proposal.status,
            inline=False,
        )
        embed.add_field(
            name="截止時間",
            value=proposal.deadline_at.strftime("%Y-%m-%d %H:%M UTC"),
            inline=False,
        )

        # 獲取投票統計
        try:
            totals = await self.service.get_vote_totals(proposal_id=proposal.proposal_id)
            embed.add_field(
                name="合計票數",
                value=f"同意 {totals.approve} / 反對 {totals.reject} / 棄權 {totals.abstain}",
                inline=False,
            )
            embed.add_field(name="門檻 T", value=str(totals.threshold_t), inline=False)
        except Exception:
            pass

        view = ProposalDetailView(
            service=self.service,
            proposal_id=proposal.proposal_id,
            guild=self.guild,
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _handle_event(self, event: SupremeAssemblyEvent) -> None:
        if event.guild_id != self.guild.id:
            return
        if self.is_finished() or self._message is None:
            return
        await self._apply_live_update(event)

    async def _apply_live_update(self, event: SupremeAssemblyEvent) -> None:
        if self._message is None or self.is_finished():
            return
        async with self._update_lock:
            await self.refresh_options()
            embed: discord.Embed | None = None
            try:
                embed = await self.build_summary_embed()
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning(
                    "supreme_assembly.panel.summary.refresh_error",
                    guild_id=self.guild.id,
                    error=str(exc),
                )
            try:
                if embed is not None:
                    await self._message.edit(embed=embed, view=self)
                else:
                    await self._message.edit(view=self)
                LOGGER.debug(
                    "supreme_assembly.panel.live_update.applied",
                    guild_id=self.guild.id,
                    kind=event.kind,
                    proposal_id=str(event.proposal_id) if event.proposal_id else None,
                )
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning(
                    "supreme_assembly.panel.live_update.failed",
                    guild_id=self.guild.id,
                    error=str(exc),
                )

    async def _cleanup_subscription(self) -> None:
        if self._unsubscribe is None:
            self._message = None
            return
        unsubscribe = self._unsubscribe
        self._unsubscribe = None
        try:
            await unsubscribe()
            LOGGER.info(
                "supreme_assembly.panel.unsubscribe",
                guild_id=self.guild.id,
                message_id=self._message.id if self._message else None,
            )
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning(
                "supreme_assembly.panel.unsubscribe_failed",
                guild_id=self.guild.id,
                error=str(exc),
            )
        finally:
            self._message = None

    async def on_timeout(self) -> None:
        await self._cleanup_subscription()
        await super().on_timeout()

    def stop(self) -> None:
        if self._unsubscribe is not None:
            try:
                asyncio.create_task(self._cleanup_subscription())
            except RuntimeError:
                asyncio.run(self._cleanup_subscription())
        super().stop()


# --- Transfer UI Components ---


class SupremeAssemblyTransferTypeSelectionView(discord.ui.View):
    """View for selecting transfer type."""

    def __init__(self, *, service: SupremeAssemblyService, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild

        # Create select menu with transfer type options
        options: list[discord.SelectOption] = [
            discord.SelectOption(
                label="轉帳給使用者",
                value="user",
                description="使用 Discord 使用者選擇器",
                emoji="👤",
            ),
            discord.SelectOption(
                label="轉帳給常任理事會",
                value="council",
                description="轉帳給常任理事會",
                emoji="🏛️",
            ),
            discord.SelectOption(
                label="轉帳給政府部門",
                value="department",
                description="從下拉選單選擇部門",
                emoji="🏢",
            ),
            discord.SelectOption(
                label="轉帳給公司",
                value="company",
                description="從下拉選單選擇公司",
                emoji="🏢",
            ),
        ]

        select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder="選擇轉帳類型",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if not interaction.data:
            await send_message_compat(interaction, content="請選擇一個轉帳類型。", ephemeral=True)
            return
        values = _extract_select_values(interaction)
        if not values:
            await send_message_compat(interaction, content="請選擇一個轉帳類型。", ephemeral=True)
            return
        selected_type: str | None = values[0] if values else None
        if not selected_type:
            await send_message_compat(interaction, content="請選擇一個轉帳類型。", ephemeral=True)
            return

        if selected_type == "user":
            view = SupremeAssemblyUserSelectView(service=self.service, guild=self.guild)
            await send_message_compat(
                interaction, content="請選擇受款使用者：", view=view, ephemeral=True
            )
        elif selected_type == "council":
            modal = SupremeAssemblyTransferModal(
                service=self.service,
                guild=self.guild,
                target_type="council",
            )
            await send_modal_compat(interaction, modal)
        elif selected_type == "department":
            dept_view: SupremeAssemblyDepartmentSelectView = SupremeAssemblyDepartmentSelectView(
                service=self.service, guild=self.guild
            )
            await send_message_compat(
                interaction, content="請選擇受款部門：", view=dept_view, ephemeral=True
            )
        elif selected_type == "company":
            company_view = SupremeAssemblyCompanySelectView(service=self.service, guild=self.guild)
            has_companies = await company_view.setup()
            if not has_companies:
                await send_message_compat(
                    interaction, content="❗ 此伺服器目前沒有已登記的公司。", ephemeral=True
                )
                return
            await send_message_compat(
                interaction, content="請選擇受款公司：", view=company_view, ephemeral=True
            )
        else:
            await send_message_compat(interaction, content="未知的轉帳類型。", ephemeral=True)


class SupremeAssemblyUserSelectView(discord.ui.View):
    """View for selecting a user."""

    def __init__(self, *, service: SupremeAssemblyService, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild

        user_select: discord.ui.UserSelect[Any] = discord.ui.UserSelect(
            placeholder="選擇使用者",
            min_values=1,
            max_values=1,
        )
        user_select.callback = self._on_select
        self.add_item(user_select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if not interaction.data:
            await send_message_compat(interaction, content="請選擇一個使用者。", ephemeral=True)
            return
        values = _extract_select_values(interaction)
        if not values:
            await send_message_compat(interaction, content="請選擇一個使用者。", ephemeral=True)
            return
        selected_id: str | None = values[0] if values else None
        if not selected_id:
            await send_message_compat(interaction, content="請選擇一個使用者。", ephemeral=True)
            return

        member = self.guild.get_member(int(selected_id)) if self.guild else None
        display_name = member.display_name if member else str(selected_id)

        modal = SupremeAssemblyTransferModal(
            service=self.service,
            guild=self.guild,
            target_type="user",
            target_user_id=int(selected_id),
            target_user_name=display_name,
        )
        await send_modal_compat(interaction, modal)


class SupremeAssemblyDepartmentSelectView(discord.ui.View):
    """View for selecting a government department."""

    def __init__(self, *, service: SupremeAssemblyService, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild
        registry = get_registry()
        # 僅列出一般部門，排除常任理事會與國務院，避免與下方專屬選項重複。
        departments = registry.get_by_level("department")

        options: list[discord.SelectOption] = []
        for dept in departments:
            label = dept.name
            if dept.emoji:
                label = f"{dept.emoji} {label}"
            options.append(
                discord.SelectOption(
                    label=label,
                    value=dept.id,
                    description=f"部門代碼: {dept.code}",
                )
            )

        if options:
            select: discord.ui.Select[Any] = discord.ui.Select(
                placeholder="選擇政府部門",
                options=options,
                min_values=1,
                max_values=1,
            )
            select.callback = self._on_select
            self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if not interaction.data:
            await send_message_compat(interaction, content="請選擇一個部門。", ephemeral=True)
            return
        values = _extract_select_values(interaction)
        if not values:
            await send_message_compat(interaction, content="請選擇一個部門。", ephemeral=True)
            return
        selected_id: str | None = values[0] if values else None
        if not selected_id:
            await send_message_compat(interaction, content="請選擇一個部門。", ephemeral=True)
            return

        registry = get_registry()
        dept = registry.get_by_id(selected_id)
        if dept is None:
            await send_message_compat(interaction, content="部門不存在。", ephemeral=True)
            return

        modal = SupremeAssemblyTransferModal(
            service=self.service,
            guild=self.guild,
            target_type="department",
            target_department_id=selected_id,
            target_department_name=dept.name,
        )
        await interaction.response.send_modal(modal)


class SupremeAssemblyCompanySelectView(discord.ui.View):
    """View for selecting a company (for Supreme Assembly transfers)."""

    def __init__(self, *, service: SupremeAssemblyService, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild
        self._companies: dict[int, Any] = {}

    async def setup(self) -> bool:
        """Fetch companies and setup the select menu.

        Returns:
            True if companies are available, False otherwise
        """
        from src.bot.ui.company_select import build_company_select_options, get_active_companies

        companies = await get_active_companies(self.guild.id)
        if not companies:
            return False

        self._companies = {c.id: c for c in companies}
        options = build_company_select_options(companies)

        select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder="🏢 選擇公司...",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)
        return True

    async def _on_select(self, interaction: discord.Interaction) -> None:
        """Handle company selection."""
        if not interaction.data:
            await send_message_compat(interaction, content="請選擇一家公司。", ephemeral=True)
            return

        values = _extract_select_values(interaction)
        if not values:
            await send_message_compat(interaction, content="請選擇一家公司。", ephemeral=True)
            return

        try:
            company_id = int(values[0])
        except ValueError:
            await send_message_compat(interaction, content="選項格式錯誤。", ephemeral=True)
            return

        company = self._companies.get(company_id)
        if company is None:
            await send_message_compat(interaction, content="找不到指定的公司。", ephemeral=True)
            return

        # Show transfer modal with company selected
        modal = SupremeAssemblyTransferModal(
            service=self.service,
            guild=self.guild,
            target_type="company",
            target_company_account_id=company.account_id,
            target_company_name=company.name,
        )
        await send_modal_compat(interaction, modal)


class SupremeAssemblyTransferModal(discord.ui.Modal, title="轉帳"):
    """Modal for creating transfer."""

    def __init__(
        self,
        *,
        service: SupremeAssemblyService,
        guild: discord.Guild,
        target_type: str,
        target_user_id: int | None = None,
        target_user_name: str | None = None,
        target_department_id: str | None = None,
        target_department_name: str | None = None,
        target_company_account_id: int | None = None,
        target_company_name: str | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.guild = guild
        self.target_type = target_type
        self.target_user_id = target_user_id
        self.target_user_name = target_user_name
        self.target_department_id = target_department_id
        self.target_department_name = target_department_name
        self.target_company_account_id = target_company_account_id
        self.target_company_name = target_company_name

        # Show target info
        target_label = "受款人"
        target_value = ""
        if target_type == "company" and target_company_name:
            target_value = f"公司：{target_company_name}"
        elif target_type == "council":
            target_value = "常任理事會"
        elif target_department_name:
            target_value = f"部門：{target_department_name}"
        elif target_user_name:
            target_value = f"使用者：{target_user_name}"

        self.target_info: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label=target_label,
            placeholder=target_value,
            default=target_value,
            required=False,
            style=discord.TextStyle.short,
        )
        self.amount: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="金額（正整數）",
            placeholder="例如 100",
            required=True,
        )
        self.description: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="用途描述",
            style=discord.TextStyle.paragraph,
            required=False,
        )
        self.add_item(self.target_info)
        self.add_item(self.amount)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction) -> None:  # noqa: D401
        # Validate amount
        try:
            amt = int(str(self.amount.value).replace(",", "").strip())
        except Exception:
            await send_message_compat(interaction, content="金額需為正整數。", ephemeral=True)
            return
        if amt <= 0:
            await send_message_compat(interaction, content="金額需 > 0。", ephemeral=True)
            return

        async def _resolve_institution_account(
            department_name: str, fallback: Callable[[int], int]
        ) -> int:
            """優先使用政府帳戶記錄取得帳戶 ID，找不到則回退舊版推導值。"""
            try:
                if department_name == "最高人民會議":
                    return await self.service.get_or_create_account_id(self.guild.id)

                sc_service = StateCouncilService()
                accounts = await sc_service.get_all_accounts(guild_id=self.guild.id)
                aliases = {department_name}
                if department_name == "常任理事會":
                    aliases.add("permanent_council")
                for acc in accounts:
                    dept = getattr(acc, "department", None)
                    if dept in aliases:
                        account_id = getattr(acc, "account_id", None)
                        if account_id is not None:
                            return int(account_id)
            except Exception as exc:  # pragma: no cover - 記錄後回退
                LOGGER.debug(
                    "supreme_assembly.transfer.account.resolve_failed",
                    guild_id=self.guild.id,
                    department=department_name,
                    error=str(exc),
                )
            return fallback(self.guild.id)

        # Determine target account ID
        target_id: int | None = None
        if self.target_type == "user" and self.target_user_id:
            target_id = self.target_user_id
        elif self.target_type == "council":
            target_id = await _resolve_institution_account(
                "常任理事會", CouncilServiceResult.derive_council_account_id
            )
        elif self.target_type == "company" and self.target_company_account_id:
            target_id = self.target_company_account_id
        elif self.target_type == "department" and self.target_department_id:
            registry = get_registry()
            dept = registry.get_by_id(self.target_department_id)
            if dept:
                target_id = await _resolve_department_account_id_for_supreme(
                    guild_id=self.guild.id,
                    department_name=dept.name,
                )

        if not target_id:
            await send_message_compat(
                interaction, content="錯誤：無法確定受款帳戶。", ephemeral=True
            )
            return

        # Get initiator account ID
        initiator_id = await _resolve_institution_account(
            "最高人民會議", SupremeAssemblyService.derive_account_id
        )

        # Execute transfer
        try:
            pool = get_pool()
            transfer_service = TransferService(pool)
            await transfer_service.transfer_currency(
                guild_id=self.guild.id,
                initiator_id=initiator_id,
                target_id=target_id,
                amount=amt,
                reason=str(self.description.value or "").strip() or None,
            )
            await send_message_compat(
                interaction,
                content=f"轉帳成功！金額：{amt:,}，受款人：{self.target_info.value}",
                ephemeral=True,
            )
            LOGGER.info(
                "supreme_assembly.panel.transfer",
                guild_id=self.guild.id,
                user_id=interaction.user.id,
                amount=amt,
                target_id=target_id,
            )
        except TransferValidationError as exc:
            await send_message_compat(interaction, content=f"轉帳失敗：{exc}", ephemeral=True)
        except Exception as exc:
            LOGGER.exception("supreme_assembly.panel.transfer.error", error=str(exc))
            await send_message_compat(interaction, content="轉帳失敗，請稍後再試。", ephemeral=True)


# --- Proposal UI Components ---


class CreateProposalModal(discord.ui.Modal, title="發起表決"):
    """Modal for creating a proposal."""

    def __init__(self, *, service: SupremeAssemblyService, guild: discord.Guild) -> None:
        super().__init__()
        self.service = service
        self.guild = guild

        self.title_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="提案標題",
            placeholder="例如：預算案",
            required=False,
        )
        self.description: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="提案內容",
            style=discord.TextStyle.paragraph,
            required=True,
        )
        self.add_item(self.title_input)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction) -> None:  # noqa: D401
        try:
            cfg = await self.service.get_config(guild_id=self.guild.id)
        except GovernanceNotConfiguredError:
            await interaction.response.send_message("尚未完成治理設定。", ephemeral=True)
            return

        role = self.guild.get_role(cfg.member_role_id)
        snapshot_ids = [m.id for m in role.members] if role is not None else []
        if not snapshot_ids:
            await interaction.response.send_message(
                "議員名冊為空，請先確認角色有成員。", ephemeral=True
            )
            return

        title = str(self.title_input.value or "").strip() or None
        description = str(self.description.value or "").strip() or None

        try:
            proposal = await self.service.create_proposal(
                guild_id=self.guild.id,
                proposer_id=interaction.user.id,
                title=title,
                description=description,
                snapshot_member_ids=snapshot_ids,
                deadline_hours=72,
            )
            await interaction.response.send_message(
                f"已建立表決提案 {proposal.proposal_id}，並將以 DM 通知議員。",
                ephemeral=True,
            )
            try:
                await _dm_members_for_voting(interaction.client, self.guild, proposal)
            except Exception:
                pass
            LOGGER.info(
                "supreme_assembly.panel.propose",
                guild_id=self.guild.id,
                user_id=interaction.user.id,
                proposal_id=str(proposal.proposal_id),
            )
        except Exception as exc:
            LOGGER.exception("supreme_assembly.panel.propose.error", error=str(exc))
            await interaction.response.send_message(f"建案失敗：{exc}", ephemeral=True)


class ProposalDetailView(discord.ui.View):
    """View for proposal details and voting."""

    def __init__(
        self,
        *,
        service: SupremeAssemblyService,
        proposal_id: UUID,
        guild: discord.Guild,
    ) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.proposal_id = proposal_id
        self.guild = guild

    @discord.ui.button(
        label="同意",
        style=discord.ButtonStyle.success,
        custom_id="sa_vote_approve",
    )
    async def approve(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await _handle_vote(interaction, self.service, self.proposal_id, "approve")

    @discord.ui.button(
        label="反對",
        style=discord.ButtonStyle.danger,
        custom_id="sa_vote_reject",
    )
    async def reject(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await _handle_vote(interaction, self.service, self.proposal_id, "reject")

    @discord.ui.button(
        label="棄權",
        style=discord.ButtonStyle.secondary,
        custom_id="sa_vote_abstain",
    )
    async def abstain(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await _handle_vote(interaction, self.service, self.proposal_id, "abstain")


class SupremeAssemblyVotingView(discord.ui.View):
    """Persistent view for voting on proposals."""

    def __init__(self, *, proposal_id: UUID, service: SupremeAssemblyService) -> None:
        super().__init__(timeout=None)
        self.proposal_id = proposal_id
        self.service = service

    @discord.ui.button(
        label="同意",
        style=discord.ButtonStyle.success,
        custom_id="sa_vote_approve_persistent",
    )
    async def approve(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await _handle_vote(interaction, self.service, self.proposal_id, "approve")

    @discord.ui.button(
        label="反對",
        style=discord.ButtonStyle.danger,
        custom_id="sa_vote_reject_persistent",
    )
    async def reject(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await _handle_vote(interaction, self.service, self.proposal_id, "reject")

    @discord.ui.button(
        label="棄權",
        style=discord.ButtonStyle.secondary,
        custom_id="sa_vote_abstain_persistent",
    )
    async def abstain(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await _handle_vote(interaction, self.service, self.proposal_id, "abstain")


async def _handle_vote(
    interaction: discord.Interaction,
    service: SupremeAssemblyService,
    proposal_id: UUID,
    choice: str,
) -> None:
    try:
        totals, status = await service.vote(
            proposal_id=proposal_id,
            voter_id=interaction.user.id,
            choice=choice,
        )
    except VoteAlreadyExistsError:
        await send_message_compat(interaction, content="已投票，無法改選。", ephemeral=True)
        return
    except PermissionDeniedError as exc:
        await send_message_compat(interaction, content=str(exc), ephemeral=True)
        return
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("supreme_assembly.vote.error", error=str(exc))
        await send_message_compat(interaction, content="投票失敗。", ephemeral=True)
        return

    embed = discord.Embed(title="最高人民會議表決（投票）", color=0xE74C3C)
    embed.add_field(name="狀態", value=status, inline=False)
    embed.add_field(
        name="合計票數",
        value=f"同意 {totals.approve} / 反對 {totals.reject} / 棄權 {totals.abstain}",
    )
    embed.add_field(name="門檻 T", value=str(totals.threshold_t))
    await send_message_compat(interaction, content="已記錄您的投票。", ephemeral=True)
    try:
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception:
        pass

    # 若已結案，廣播結果（揭露個別票）
    if status in ("已通過", "已否決", "已逾時"):
        guild = interaction.guild
        if guild is None and interaction.guild_id is not None:
            guild = interaction.client.get_guild(interaction.guild_id)
        if guild is None:
            return
        try:
            await _broadcast_result(interaction.client, guild, service, proposal_id, status)
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("supreme_assembly.result_dm.error", error=str(exc))


async def _dm_members_for_voting(
    client: discord.Client,
    guild: discord.Guild,
    proposal: Any,
) -> None:
    """Send DM to members with voting buttons."""
    service = SupremeAssemblyService()
    view = SupremeAssemblyVotingView(proposal_id=proposal.proposal_id, service=service)
    try:
        cfg = await service.get_config(guild_id=guild.id)
    except GovernanceNotConfiguredError:
        return
    role = guild.get_role(cfg.member_role_id)
    members: list[discord.Member] = list(role.members) if role is not None else []

    embed = discord.Embed(title="最高人民會議表決（請投票）", color=0xE74C3C)
    embed.add_field(name="提案編號", value=str(proposal.proposal_id), inline=False)
    if proposal.title:
        embed.add_field(name="標題", value=proposal.title, inline=False)
    if proposal.description:
        embed.add_field(name="內容", value=proposal.description, inline=False)
    embed.set_footer(
        text=(f"門檻 T={proposal.threshold_t}，" f"截止：{proposal.deadline_at:%Y-%m-%d %H:%M UTC}")
    )

    for m in members:
        try:
            await m.send(embed=embed, view=view)
        except Exception as exc:
            LOGGER.warning("supreme_assembly.dm.failed", member=m.id, error=str(exc))


async def _broadcast_result(
    client: discord.Client,
    guild: discord.Guild,
    service: SupremeAssemblyService,
    proposal_id: UUID,
    status: str,
) -> None:
    """向提案人與全體議員廣播最終結果（揭露個別票）。"""
    snapshot = await service.get_snapshot(proposal_id=proposal_id)
    votes = await service.get_votes_detail(proposal_id=proposal_id)
    vote_map = dict(votes)
    lines: list[str] = []
    for uid in snapshot:
        choice_str = vote_map.get(uid, "未投")
        if choice_str == "approve":
            choice_str = "同意"
        elif choice_str == "reject":
            choice_str = "反對"
        elif choice_str == "abstain":
            choice_str = "棄權"
        lines.append(f"<@{uid}> → {choice_str}")
    text = "\n".join(lines)
    color = 0x2ECC71 if status == "已通過" else 0xF1C40F
    result_embed = discord.Embed(title="表決結果", color=color)
    result_embed.add_field(name="最終狀態", value=status, inline=False)
    result_embed.add_field(name="個別投票", value=text or "(無)", inline=False)

    cfg = await service.get_config(guild_id=guild.id)
    role = guild.get_role(cfg.member_role_id)
    members = role.members if role is not None else []

    # 確認提案人
    proposal = await service.get_proposal(proposal_id=proposal_id)
    proposer_user: discord.User | discord.Member | None = None
    if proposal is not None:
        proposer_user = guild.get_member(proposal.proposer_id) or await _safe_fetch_user(
            client, proposal.proposer_id
        )

    recipients: list[discord.abc.Messageable] = []
    recipients.extend(members)
    if proposer_user is not None and proposer_user.id not in [m.id for m in members]:
        recipients.append(proposer_user)
    for m in recipients:
        try:
            await m.send(embed=result_embed)
        except Exception:
            pass


# --- Summon UI Components ---


class SummonTypeSelectionView(discord.ui.View):
    """View for selecting summon type."""

    def __init__(self, *, service: SupremeAssemblyService, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild

    @discord.ui.button(
        label="傳召議員",
        style=discord.ButtonStyle.primary,
    )
    async def select_member(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        # 預先載入議員清單以正確顯示下拉式選單
        view = await SummonMemberSelectView.build(service=self.service, guild=self.guild)
        await send_message_compat(
            interaction, content="請選擇要傳召的議員：", view=view, ephemeral=True
        )

    @discord.ui.button(
        label="傳召政府官員",
        style=discord.ButtonStyle.primary,
    )
    async def select_official(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        view = SummonOfficialSelectView(service=self.service, guild=self.guild)
        await send_message_compat(
            interaction, content="請選擇要傳召的政府官員：", view=view, ephemeral=True
        )


class SummonMemberSelectView(discord.ui.View):
    """View for selecting a member to summon."""

    def __init__(self, *, service: SupremeAssemblyService, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild

    @classmethod
    async def build(
        cls, *, service: SupremeAssemblyService, guild: discord.Guild
    ) -> "SummonMemberSelectView":
        """Async builder that preloads member options so the select shows immediately."""
        self = cls(service=service, guild=guild)
        try:
            cfg_obj = await service.get_config(guild_id=guild.id)
            role = guild.get_role(cfg_obj.member_role_id)
            if role:
                members = role.members
                options: list[discord.SelectOption] = []
                for m in members[:25]:  # Discord limit
                    options.append(
                        discord.SelectOption(
                            label=m.display_name,
                            value=str(m.id),
                            description=f"議員：{m.name}",
                        )
                    )
                if options:
                    select: discord.ui.Select[Any] = discord.ui.Select(
                        placeholder="選擇議員",
                        options=options,
                        min_values=1,
                        max_values=1,
                    )
                    select.callback = self._on_select
                    self.add_item(select)
                else:
                    # 無成員時顯示停用的下拉，避免出現空白視圖
                    disabled_select: discord.ui.Select[Any] = discord.ui.Select(
                        placeholder="目前沒有可傳召的議員（請確認設定）",
                        options=[discord.SelectOption(label="無可選項", value="none")],
                        min_values=1,
                        max_values=1,
                    )
                    disabled_select.disabled = True
                    self.add_item(disabled_select)
        except Exception:
            # 靜默失敗：保持無項目，讓上層以訊息提示
            pass
        return self

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if not interaction.data:
            await send_message_compat(interaction, content="請選擇一個議員。", ephemeral=True)
            return
        values = _extract_select_values(interaction)
        if not values:
            await send_message_compat(interaction, content="請選擇一個議員。", ephemeral=True)
            return
        selected_id: str | None = values[0] if values else None
        if not selected_id:
            await send_message_compat(interaction, content="請選擇一個議員。", ephemeral=True)
            return

        try:
            summon = await self.service.create_summon(
                guild_id=self.guild.id,
                invoked_by=interaction.user.id,
                target_id=int(selected_id),
                target_kind="member",
                note=None,
            )
            member = self.guild.get_member(int(selected_id))
            if member:
                try:
                    embed = discord.Embed(
                        title="最高人民會議傳召",
                        color=0xE74C3C,
                        description=f"議長 {interaction.user.mention} 傳召您出席最高人民會議。",
                    )
                    await member.send(embed=embed)
                    await self.service.mark_summon_delivered(summon_id=summon.summon_id)
                except Exception:
                    pass
            await send_message_compat(
                interaction,
                content=f"已傳召議員 {member.mention if member else selected_id}。",
                ephemeral=True,
            )
            LOGGER.info(
                "supreme_assembly.panel.summon",
                guild_id=self.guild.id,
                user_id=interaction.user.id,
                target_id=int(selected_id),
                target_kind="member",
            )
        except Exception as exc:
            LOGGER.exception("supreme_assembly.panel.summon.error", error=str(exc))
            await send_message_compat(interaction, content="傳召失敗，請稍後再試。", ephemeral=True)


class SummonOfficialSelectView(discord.ui.View):
    """View for selecting a government official to summon."""

    def __init__(self, *, service: SupremeAssemblyService, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild
        registry = get_registry()
        # 僅提供部門等級選擇，不含常任理事會與國務院。
        departments = registry.get_by_level("department")

        # Create options for department leaders
        options: list[discord.SelectOption] = []
        for dept in departments:
            label = f"{dept.name}部長"
            if dept.emoji:
                label = f"{dept.emoji} {label}"
            options.append(
                discord.SelectOption(
                    label=label,
                    value=f"dept_{dept.id}",
                    description=f"部門：{dept.name}",
                )
            )
        # Add State Council leader and Permanent Council
        options.append(
            discord.SelectOption(
                label="國務院領袖",
                value="state_council_leader",
                description="國務院主帳戶",
            )
        )
        options.append(
            discord.SelectOption(
                label="常任理事會成員",
                value="permanent_council",
                description="常任理事會",
            )
        )

        if options:
            select: discord.ui.Select[Any] = discord.ui.Select(
                placeholder="選擇政府官員",
                options=options,
                min_values=1,
                max_values=1,
            )
            select.callback = self._on_select
            self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if not interaction.data:
            await send_message_compat(interaction, content="請選擇一個官員。", ephemeral=True)
            return
        values = _extract_select_values(interaction)
        if not values:
            await send_message_compat(interaction, content="請選擇一個官員。", ephemeral=True)
            return
        selected_value: str | None = values[0] if values else None
        if not selected_value:
            await send_message_compat(interaction, content="請選擇一個官員。", ephemeral=True)
            return

        # 針對政府官員：導出對應的帳戶 ID 以記錄 summon，並實際 DM 給可辨識之使用者（領袖/角色成員）
        target_id = 0
        target_name = ""
        recipients: list[discord.abc.Messageable] = []

        try:
            if selected_value.startswith("dept_"):
                dept_id = selected_value.replace("dept_", "")
                registry = get_registry()
                dept = registry.get_by_id(dept_id)
                if dept:
                    target_id = StateCouncilService.derive_department_account_id(
                        self.guild.id, dept.name
                    )
                    target_name = f"{dept.name}部長"

                    # 依部門設定找出部長身分組並 DM 該角色所有成員
                    from src.db.gateway.state_council_governance import (
                        StateCouncilGovernanceGateway,
                    )
                    from src.db.pool import get_pool as _get_pool

                    gw = StateCouncilGovernanceGateway()
                    pool: PoolProtocol = cast(PoolProtocol, _get_pool())
                    async with pool.acquire() as conn:
                        c: ConnectionProtocol = conn
                        cfg = await gw.fetch_department_config(
                            c, guild_id=self.guild.id, department=dept.name
                        )
                    if cfg and cfg.role_id:
                        role = self.guild.get_role(int(cfg.role_id))
                        if role:
                            recipients.extend(role.members)

            elif selected_value == "state_council_leader":
                target_id = StateCouncilService.derive_main_account_id(self.guild.id)
                target_name = "國務院領袖"

                # 優先 DM 指定的領袖 user_id；否則 DM 領袖身分組所有成員
                from src.db.gateway.state_council_governance import (
                    StateCouncilGovernanceGateway,
                )
                from src.db.pool import get_pool as _get_pool

                gw = StateCouncilGovernanceGateway()
                pool2: PoolProtocol = cast(PoolProtocol, _get_pool())
                async with pool2.acquire() as conn:
                    c2: ConnectionProtocol = conn
                    sc_cfg = await gw.fetch_state_council_config(c2, guild_id=self.guild.id)
                if sc_cfg:
                    if sc_cfg.leader_id:
                        member = self.guild.get_member(int(sc_cfg.leader_id))
                        if member is not None:
                            recipients.append(member)
                        else:
                            try:
                                user = await interaction.client.fetch_user(int(sc_cfg.leader_id))
                                recipients.append(user)
                            except Exception:
                                pass
                    if not recipients and sc_cfg.leader_role_id:
                        role = self.guild.get_role(int(sc_cfg.leader_role_id))
                        if role:
                            recipients.extend(role.members)

            elif selected_value == "permanent_council":
                # 顯示常任理事會成員多選，下拉選單需預先載入
                view = await SummonPermanentCouncilView.build(
                    service=self.service, guild=self.guild, original_view=self
                )
                await send_message_compat(
                    interaction,
                    content="請選擇要傳召的常任理事會成員（可多選）：",
                    view=view,
                    ephemeral=True,
                )
                return

            if not target_id:
                await send_message_compat(interaction, content="無法確定目標官員。", ephemeral=True)
                return

            # 建立 summon 紀錄
            summon = await self.service.create_summon(
                guild_id=self.guild.id,
                invoked_by=interaction.user.id,
                target_id=target_id,
                target_kind="official",
                note=f"傳召 {target_name}",
            )

            # 準備 DM 內容
            embed = discord.Embed(
                title="最高人民會議傳召",
                color=0xE74C3C,
                description=(
                    f"議長 {interaction.user.mention} 傳召您出席最高人民會議（{target_name}）。"
                ),
            )

            sent = 0
            # 若無法解析任何收件人，仍回覆已建立傳召但提示未能私訊
            for m in recipients:
                try:
                    await m.send(embed=embed)
                    sent += 1
                except Exception:
                    continue

            if sent > 0:
                try:
                    await self.service.mark_summon_delivered(summon_id=summon.summon_id)
                except Exception:
                    pass

            await send_message_compat(
                interaction,
                content=(
                    f"已傳召 {target_name}（帳戶 ID: {target_id}）。"
                    + (
                        f" 已成功私訊 {sent} 人。"
                        if sent > 0
                        else " 未能私訊任何成員（可能關閉 DM 或未設定身分組）。"
                    )
                ),
                ephemeral=True,
            )
            LOGGER.info(
                "supreme_assembly.panel.summon",
                guild_id=self.guild.id,
                user_id=interaction.user.id,
                target_id=target_id,
                target_kind="official",
                dm_sent=sent,
            )
        except Exception as exc:
            LOGGER.exception("supreme_assembly.panel.summon.error", error=str(exc))
            await send_message_compat(interaction, content="傳召失敗，請稍後再試。", ephemeral=True)


class SummonPermanentCouncilView(discord.ui.View):
    """View for selecting permanent council members to summon (multi-select)."""

    def __init__(
        self,
        *,
        service: SupremeAssemblyService,
        guild: discord.Guild,
        original_view: SummonOfficialSelectView,
    ) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild
        self.original_view = original_view

    @classmethod
    async def build(
        cls,
        *,
        service: SupremeAssemblyService,
        guild: discord.Guild,
        original_view: SummonOfficialSelectView,
    ) -> "SummonPermanentCouncilView":
        """Async builder that preloads permanent council member options for multi-select."""
        self = cls(service=service, guild=guild, original_view=original_view)
        try:
            # 讀取理事會角色設定
            from src.db.gateway.council_governance import CouncilGovernanceGateway
            from src.db.pool import get_pool as _get_pool

            council_gw: CouncilGovernanceGateway = CouncilGovernanceGateway()
            pool: PoolProtocol = cast(PoolProtocol, _get_pool())
            async with pool.acquire() as conn:
                c: ConnectionProtocol = conn
                c_cfg = await council_gw.fetch_config(c, guild_id=guild.id)
            if c_cfg:
                council_role_id = int(c_cfg.council_role_id)
                role = guild.get_role(council_role_id)
                if role:
                    members = role.members
                    options: list[discord.SelectOption] = []
                    for m in members[:25]:  # Discord limit
                        options.append(
                            discord.SelectOption(
                                label=m.display_name,
                                value=str(m.id),
                                description=f"常任理事：{m.name}",
                            )
                        )
                    if options:
                        select: discord.ui.Select[Any] = discord.ui.Select(
                            placeholder="選擇常任理事會成員（可多選）",
                            options=options,
                            min_values=1,
                            max_values=min(len(options), 25),
                        )
                        select.callback = self._on_select
                        self.add_item(select)
                    else:
                        disabled_select: discord.ui.Select[Any] = discord.ui.Select(
                            placeholder="目前沒有可傳召的常任理事（請確認設定）",
                            options=[discord.SelectOption(label="無可選項", value="none")],
                            min_values=1,
                            max_values=1,
                        )
                        disabled_select.disabled = True
                        self.add_item(disabled_select)
        except Exception:
            # 靜默失敗，保持空白視圖讓上層訊息提示
            pass
        return self

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if not interaction.data:
            await send_message_compat(
                interaction, content="請選擇至少一個常任理事。", ephemeral=True
            )
            return
        values = _extract_select_values(interaction)
        if not values:
            await send_message_compat(
                interaction, content="請選擇至少一個常任理事。", ephemeral=True
            )
            return
        selected_ids = [int(v) for v in values if v.isdigit()]

        if not selected_ids:
            await send_message_compat(
                interaction, content="請選擇至少一個常任理事。", ephemeral=True
            )
            return

        try:
            # Create summon records for each selected member
            from src.bot.services.council_service import CouncilServiceResult

            target_id = CouncilServiceResult.derive_council_account_id(self.guild.id)
            target_name = "常任理事會成員"

            # Prepare DM content
            embed = discord.Embed(
                title="最高人民會議傳召",
                color=0xE74C3C,
                description=(
                    f"議長 {interaction.user.mention} 傳召您出席最高人民會議（{target_name}）。"
                ),
            )

            sent = 0
            summoned_members: list[str] = []

            # Send DM to each selected member
            for member_id in selected_ids:
                member = self.guild.get_member(member_id)
                if member:
                    try:
                        await member.send(embed=embed)
                        sent += 1
                        summoned_members.append(member.mention)
                    except Exception:
                        summoned_members.append(f"<@{member_id}>")

            # Create summon record (using the council account ID as target)
            summon = await self.service.create_summon(
                guild_id=self.guild.id,
                invoked_by=interaction.user.id,
                target_id=target_id,
                target_kind="official",
                note=f"傳召常任理事會成員：{', '.join([str(mid) for mid in selected_ids])}",
            )

            if sent > 0:
                try:
                    await self.service.mark_summon_delivered(summon_id=summon.summon_id)
                except Exception:
                    pass

            members_list = ", ".join(summoned_members[:5])  # Limit display
            if len(summoned_members) > 5:
                members_list += f" 等 {len(summoned_members)} 人"

            await send_message_compat(
                interaction,
                content=(
                    f"已傳召 {members_list}。"
                    + (
                        f" 已成功私訊 {sent} 人。"
                        if sent > 0
                        else " 未能私訊任何成員（可能關閉 DM）。"
                    )
                ),
                ephemeral=True,
            )
            LOGGER.info(
                "supreme_assembly.panel.summon.permanent_council",
                guild_id=self.guild.id,
                user_id=interaction.user.id,
                target_ids=selected_ids,
                target_kind="official",
                dm_sent=sent,
            )
        except Exception as exc:
            LOGGER.exception(
                "supreme_assembly.panel.summon.permanent_council.error", error=str(exc)
            )
            await send_message_compat(interaction, content="傳召失敗，請稍後再試。", ephemeral=True)


# --- Helpers ---


def _format_proposal_title(p: Any) -> str:
    """Format proposal title for select menu."""
    short = str(p.proposal_id)[:8]
    title = p.title or "無標題"
    if len(title) > 50:
        title = title[:47] + "..."
    return f"#{short} {title}"


def _format_proposal_desc(p: Any) -> str:
    """Format proposal description for select menu."""
    deadline = p.deadline_at.strftime("%Y-%m-%d %H:%M UTC") if hasattr(p, "deadline_at") else ""
    desc = (p.description or "").strip()
    if desc:
        desc = desc[:60]
    return f"截止 {deadline}｜T={p.threshold_t}｜{desc or '無描述'}"


async def _safe_fetch_user(client: discord.Client, user_id: int) -> discord.User | None:
    """嘗試以 API 取回使用者；若失敗回傳 None。"""
    try:
        return await client.fetch_user(user_id)
    except Exception:
        return None


# --- Background scheduler ---

_scheduler_task: asyncio.Task[None] | None = None


def _install_background_scheduler(client: discord.Client, service: SupremeAssemblyService) -> None:
    """Install background scheduler for proposal timeouts and reminders."""
    global _scheduler_task
    if _scheduler_task is not None:
        return

    async def _runner() -> None:
        await client.wait_until_ready()
        # Register persistent views for active proposals
        try:
            await _register_persistent_views(client, service)
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("supreme_assembly.persistent_view.error", error=str(exc))

        # Avoid duplicate broadcasts: maintain set of broadcasted proposals
        broadcasted: set[UUID] = set()
        while not client.is_closed():
            try:
                # Get due proposals before expiration
                pool: PoolProtocol = cast(PoolProtocol, get_pool())
                due_before: list[UUID] = []
                async with pool.acquire() as conn:
                    c: ConnectionProtocol = conn
                    from src.db.gateway.supreme_assembly_governance import (
                        SupremeAssemblyGovernanceGateway,
                    )

                    gw = SupremeAssemblyGovernanceGateway()
                    for p in await gw.list_due_proposals(c):
                        due_before.append(p.proposal_id)

                # Expire due proposals
                changed = await service.expire_due_proposals()
                if changed:
                    LOGGER.info("supreme_assembly.scheduler.expire", changed=changed)

                # Send T-24h reminders to non-voters
                async with pool.acquire() as conn:
                    c2: ConnectionProtocol = conn
                    from src.db.gateway.supreme_assembly_governance import (
                        SupremeAssemblyGovernanceGateway,
                    )

                    gw = SupremeAssemblyGovernanceGateway()
                    # Note: This assumes a similar method exists in the gateway
                    # You may need to implement reminder_candidates method
                    for p in await gw.list_due_proposals(c2):
                        # Check if reminder needed (24h before deadline)
                        from datetime import datetime, timezone

                        if (p.deadline_at - datetime.now(timezone.utc)).total_seconds() < 86400:
                            unvoted = await service.list_unvoted_members(proposal_id=p.proposal_id)
                            guild = client.get_guild(p.guild_id)
                            if guild is not None:
                                for uid in unvoted:
                                    member = guild.get_member(uid)
                                    if member is None:
                                        try:
                                            user = await client.fetch_user(uid)
                                            await user.send(
                                                (
                                                    f"表決提案 {p.proposal_id} 24 小時內截止，"
                                                    "請盡速投票。"
                                                )
                                            )
                                        except Exception:
                                            pass
                                    else:
                                        try:
                                            await member.send(
                                                (
                                                    f"表決提案 {p.proposal_id} 24 小時內截止，"
                                                    "請盡速投票。"
                                                )
                                            )
                                        except Exception:
                                            pass

                # Broadcast results for completed proposals
                for pid in due_before:
                    if pid in broadcasted:
                        continue
                    try:
                        proposal = await service.get_proposal(proposal_id=pid)
                        if proposal is None:
                            continue
                        if proposal.status != "進行中":
                            guild = client.get_guild(proposal.guild_id)
                            if guild is not None:
                                await _broadcast_result(
                                    client,
                                    guild,
                                    service,
                                    pid,
                                    proposal.status,
                                )
                                broadcasted.add(pid)
                    except Exception:
                        pass
            except Exception as exc:  # pragma: no cover
                LOGGER.exception("supreme_assembly.scheduler.error", error=str(exc))
            await asyncio.sleep(60)

    _scheduler_task = asyncio.create_task(_runner(), name="supreme-assembly-scheduler")


async def _register_persistent_views(
    client: discord.Client, service: SupremeAssemblyService
) -> None:
    """Register persistent views for active proposals."""
    pool: PoolProtocol = cast(PoolProtocol, get_pool())
    async with pool.acquire() as conn:
        c: ConnectionProtocol = conn
        from src.db.gateway.supreme_assembly_governance import SupremeAssemblyGovernanceGateway

        gw = SupremeAssemblyGovernanceGateway()
        active = await gw.list_active_proposals(c)
        for p in active:
            try:
                client.add_view(
                    SupremeAssemblyVotingView(proposal_id=p.proposal_id, service=service)
                )
            except Exception:
                pass
