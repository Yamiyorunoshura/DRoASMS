from __future__ import annotations

# mypy: ignore-errors
import asyncio
import csv
import io
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Sequence, cast
from uuid import UUID

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_data import HelpData
from src.bot.interaction_compat import send_message_compat
from src.bot.services.balance_service import BalanceService
from src.bot.services.council_service import (
    CouncilService,
    CouncilServiceResult,
    GovernanceNotConfiguredError,
    VoteTotals,
)
from src.bot.services.department_registry import get_registry
from src.bot.services.permission_service import PermissionResult, PermissionService
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.supreme_assembly_service import SupremeAssemblyService
from src.bot.ui.base import PersistentPanelView
from src.bot.ui.council_paginator import CouncilProposalPaginator
from src.bot.utils.error_templates import ErrorMessageTemplates
from src.db.gateway.council_governance import CouncilConfig, Proposal
from src.db.pool import get_pool
from src.infra.di.container import DependencyContainer
from src.infra.events.council_events import CouncilEvent
from src.infra.events.council_events import subscribe as subscribe_council_events
from src.infra.result import (
    Err,
    Ok,
)

LOGGER = structlog.get_logger(__name__)


# 針對 Discord Interaction 的 values 解析做統一型別收斂，
# 以免 Pylance 在嚴格模式下將 comprehension 內的變數判為 Unknown。
def _extract_select_values(interaction: discord.Interaction) -> list[str]:
    data = cast(dict[str, Any], interaction.data or {})
    raw_values = data.get("values")
    if not isinstance(raw_values, list):
        return []
    typed_values = cast(list[Any], raw_values)
    vals: list[str] = []
    for item in typed_values:
        if isinstance(item, str):
            vals.append(item)
    return vals


def _unwrap_result(result: Any) -> tuple[Any | None, Any | None]:
    """將可能是 Result / 巢狀 Result 的值展平成 (ok_value, error)。

    - 若為 Err 或 Ok(Err(...))，回傳 (None, error)
    - 若為 Ok(value) 或 Ok(Ok(value))，回傳 (value, None)
    - 若非 Result 型別，視為成功值 (result, None)
    """
    current: Any = result

    # 最多展開兩層 Ok/Err：Ok(value) 或 Ok(Ok(value)) / Ok(Err(error))
    for _ in range(2):
        if isinstance(current, Err):
            error = getattr(cast(Any, current), "error", None)
            return None, error
        if isinstance(current, Ok):
            current = cast(Any, getattr(current, "value", None))
            continue
        break

    return current, None


def get_help_data() -> dict[str, HelpData]:
    """Return help information for council commands."""
    return {
        "council": {
            "name": "council",
            "description": "理事會治理指令群組",
            "category": "governance",
            "parameters": [],
            "permissions": [],
            "examples": [],
            "tags": ["理事會", "治理"],
        },
        "council config_role": {
            "name": "council config_role",
            "description": "設定常任理事身分組（角色）。需要管理員或管理伺服器權限。",
            "category": "governance",
            "parameters": [
                {
                    "name": "role",
                    "description": "Discord 角色，將作為理事名冊來源",
                    "required": True,
                },
            ],
            "permissions": ["administrator", "manage_guild"],
            "examples": ["/council config_role @CouncilRole"],
            "tags": ["設定", "配置"],
        },
        "council add_role": {
            "name": "council add_role",
            "description": "新增常任理事身分組（支援多個身分組）。需要管理員或管理伺服器權限。",
            "category": "governance",
            "parameters": [
                {
                    "name": "role",
                    "description": "要加入理事名冊的 Discord 身分組",
                    "required": True,
                },
            ],
            "permissions": ["administrator", "manage_guild"],
            "examples": ["/council add_role @副議長"],
            "tags": ["設定", "權限", "身分組"],
        },
        "council remove_role": {
            "name": "council remove_role",
            "description": "移除常任理事身分組（支援多個身分組）。需要管理員或管理伺服器權限。",
            "category": "governance",
            "parameters": [
                {
                    "name": "role",
                    "description": "要從理事名冊移除的 Discord 身分組",
                    "required": True,
                },
            ],
            "permissions": ["administrator", "manage_guild"],
            "examples": ["/council remove_role @榮譽理事"],
            "tags": ["設定", "權限", "身分組"],
        },
        "council list_roles": {
            "name": "council list_roles",
            "description": "列出所有常任理事身分組設定。",
            "category": "governance",
            "parameters": [],
            "permissions": [],
            "examples": ["/council list_roles"],
            "tags": ["查詢", "權限"],
        },
        "council panel": {
            "name": "council panel",
            "description": "開啟理事會面板（建案/投票/撤案/匯出）。僅限理事使用。",
            "category": "governance",
            "parameters": [],
            "permissions": [],
            "examples": ["/council panel"],
            "tags": ["面板", "操作"],
        },
    }


def register(
    tree: app_commands.CommandTree,
    *,
    container: DependencyContainer | None = None,
    council_service: CouncilService | None = None,
    state_council_service: StateCouncilService | None = None,
    supreme_assembly_service: SupremeAssemblyService | None = None,
) -> None:
    """Register the /council slash command group with the provided command tree."""
    if container is None:
        service = council_service or CouncilService()
        service_result = council_service or CouncilServiceResult()
        state_service = state_council_service or StateCouncilService()
        supreme_service = supreme_assembly_service or SupremeAssemblyService()
        permission_service = PermissionService(
            council_service=service_result,
            state_council_service=state_service,
            supreme_assembly_service=supreme_service,
        )
    else:
        service = container.resolve(CouncilService)
        service_result = container.resolve(CouncilServiceResult)
        permission_service = container.resolve(PermissionService)

    tree.add_command(
        build_council_group(service, service_result, permission_service=permission_service)
    )
    _install_background_scheduler(tree.client, service_result)

    LOGGER.debug("bot.command.council.registered")


def build_council_group(
    service: CouncilService,
    service_result: CouncilServiceResult | None = None,
    permission_service: PermissionService | None = None,
) -> app_commands.Group:
    """建立 /council 指令群組。

    - service_result 為 None 時，視為「舊版服務模式」，直接使用 service 物件，
      以保持對舊測試與既有程式的相容性。
    - service_result 存在時，使用 Result 型服務以符合新規格。
    """
    legacy_mode = service_result is None
    if service_result is None:
        # 在舊版模式下，commands 會直接呼叫 CouncilService（或其 MagicMock）。
        # 這裡僅為型別提示，實際上透過 _unwrap_result 與 try/except 處理回傳值與例外。
        service_result = cast(CouncilServiceResult, service)  # type: ignore[assignment]

    council = app_commands.Group(name="council", description="理事會治理指令群組")

    @council.command(name="config_role", description="設定常任理事身分組（角色）")
    @app_commands.describe(role="Discord 角色，將作為理事名冊來源")
    async def config_role(  # pyright: ignore[reportUnusedFunction]
        interaction: discord.Interaction, role: discord.Role
    ) -> None:
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
        # Result 模式 + 舊版直接回傳模式兼容
        try:
            raw_result = await service_result.set_config(
                guild_id=interaction.guild_id, council_role_id=role.id
            )
        except Exception as exc:
            LOGGER.error("council.config_role.error", error=str(exc))
            await send_message_compat(
                interaction,
                content=f"設定失敗：{exc}",
                ephemeral=True,
            )
            return

        cfg_ok, cfg_err = _unwrap_result(raw_result)
        if cfg_err is not None:
            LOGGER.error("council.config_role.error", error=str(cfg_err))
            error_message = ErrorMessageTemplates.from_error(cfg_err)
            await send_message_compat(interaction, content=error_message, ephemeral=True)
            return

        cfg = cast(CouncilConfig, cfg_ok)
        await send_message_compat(
            interaction,
            content=(f"已設定理事角色：{role.mention}（帳戶ID {cfg.council_account_member_id}）"),
            ephemeral=True,
        )

    # 依規範：移除與面板重疊之撤案/建案/匯出斜線指令（保留 panel/config_role）

    @council.command(name="panel", description="開啟理事會面板（建案/投票/撤案/匯出）")
    async def panel(  # pyright: ignore[reportUnusedFunction]
        interaction: discord.Interaction,
    ) -> None:
        # 僅允許在伺服器使用
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return
        # 檢查是否完成治理設定（支援 Result 模式與舊版直接丟例外）
        try:
            raw_config = await service_result.get_config(guild_id=interaction.guild_id)
        except GovernanceNotConfiguredError:
            # 舊版服務：依舊測試訊息回應
            message = (
                "尚未完成治理設定，請先執行 /council config_role。"
                if legacy_mode
                else ErrorMessageTemplates.not_configured("理事會治理")
            )
            await send_message_compat(interaction, content=message, ephemeral=True)
            return
        except Exception as exc:
            LOGGER.error("council.panel.get_config.error", error=str(exc))
            error_message = ErrorMessageTemplates.from_error(exc)
            await send_message_compat(
                interaction,
                content=error_message,
                ephemeral=True,
            )
            return

        config_ok, config_err = _unwrap_result(raw_config)
        if config_err is not None:
            error = config_err
            if isinstance(error, GovernanceNotConfiguredError):
                message = (
                    "尚未完成治理設定，請先執行 /council config_role。"
                    if legacy_mode
                    else ErrorMessageTemplates.not_configured("理事會治理")
                )
            else:
                message = ErrorMessageTemplates.from_error(error)
            await send_message_compat(
                interaction,
                content=message,
                ephemeral=True,
            )
            return

        cfg = cast(CouncilConfig, config_ok)

        user_roles = [role.id for role in getattr(interaction.user, "roles", [])]
        permission_result: PermissionResult | None = None
        if permission_service is not None:
            perm_check = await permission_service.check_council_permission(
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                user_roles=user_roles,
                operation="panel_access",
            )
            if isinstance(perm_check, Err):
                message = ErrorMessageTemplates.from_error(perm_check.error)
                await send_message_compat(
                    interaction,
                    content=message,
                    ephemeral=True,
                )
                return
            permission_result = perm_check.value
            has_permission = permission_result.allowed
        else:
            # Result 模式 + 舊版直接回傳模式兼容
            try:
                raw_perm = await service_result.check_council_permission(
                    guild_id=interaction.guild_id, user_roles=user_roles
                )
            except Exception as exc:
                LOGGER.error("council.panel.permission_check_failed", error=str(exc))
                has_permission = False
            else:
                perm_ok, perm_err = _unwrap_result(raw_perm)
                if perm_err is not None:
                    LOGGER.error("council.panel.permission_check_failed", error=str(perm_err))
                    has_permission = False
                else:
                    has_permission = bool(perm_ok)

        if not has_permission:
            denial_reason = (
                permission_result.reason
                if permission_result and permission_result.reason
                else "僅限具備常任理事身分組的人員可開啟面板。"
            )
            await send_message_compat(
                interaction,
                content=denial_reason,
                ephemeral=True,
            )
            return

        view = CouncilPanelView(
            service=service_result,
            guild=interaction.guild,
            author_id=interaction.user.id,
            council_role_id=cfg.council_role_id,  # 保持向下相容
        )
        await view.refresh_options()
        embed = await view.build_summary_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            message = await interaction.original_response()
            await view.bind_message(message)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning(
                "council.panel.bind_failed",
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                error=str(exc),
            )
        LOGGER.info(
            "council.panel.open",
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
        )

    @council.command(name="add_role", description="新增常任理事身分組（支援多組）")
    @app_commands.describe(role="要加入理事名冊的 Discord 身分組")
    async def add_role(  # pyright: ignore[reportUnusedFunction]
        interaction: discord.Interaction, role: discord.Role
    ) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return
        perms = getattr(interaction.user, "guild_permissions", None)
        if not perms or not (perms.administrator or perms.manage_guild):
            await send_message_compat(
                interaction, content="需要管理員或管理伺服器權限。", ephemeral=True
            )
            return
        # Result 模式 + 舊版直接回傳模式兼容
        try:
            raw_result = await service_result.add_council_role(
                guild_id=interaction.guild_id, role_id=role.id
            )
        except Exception as exc:
            LOGGER.error("council.add_role.error", error=str(exc))
            await send_message_compat(interaction, content=f"新增身分組失敗：{exc}", ephemeral=True)
            return

        added_ok, added_err = _unwrap_result(raw_result)
        if added_err is not None:
            LOGGER.error("council.add_role.error", error=str(added_err))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.from_error(added_err),
                ephemeral=True,
            )
            return

        added = bool(added_ok)
        if added:
            content = f"已新增 {role.mention} 到常任理事名冊。"
        else:
            content = f"{role.mention} 已存在於常任理事名冊。"
        await send_message_compat(interaction, content=content, ephemeral=True)

    @council.command(name="remove_role", description="移除常任理事身分組")
    @app_commands.describe(role="要從理事名冊移除的 Discord 身分組")
    async def remove_role(  # pyright: ignore[reportUnusedFunction]
        interaction: discord.Interaction, role: discord.Role
    ) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return
        perms = getattr(interaction.user, "guild_permissions", None)
        if not perms or not (perms.administrator or perms.manage_guild):
            await send_message_compat(
                interaction, content="需要管理員或管理伺服器權限。", ephemeral=True
            )
            return
        # Result 模式 + 舊版直接回傳模式兼容
        try:
            raw_result = await service_result.remove_council_role(
                guild_id=interaction.guild_id, role_id=role.id
            )
        except Exception as exc:
            LOGGER.error("council.remove_role.error", error=str(exc))
            await send_message_compat(interaction, content=f"移除身分組失敗：{exc}", ephemeral=True)
            return

        removed_ok, removed_err = _unwrap_result(raw_result)
        if removed_err is not None:
            LOGGER.error("council.remove_role.error", error=str(removed_err))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.from_error(removed_err),
                ephemeral=True,
            )
            return

        removed = bool(removed_ok)
        if removed:
            content = f"已將 {role.mention} 從常任理事名冊移除。"
        else:
            content = f"{role.mention} 不在常任理事名冊中。"
        await send_message_compat(interaction, content=content, ephemeral=True)

    @council.command(name="list_roles", description="列出所有常任理事身分組")
    async def list_roles(  # pyright: ignore[reportUnusedFunction]
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return
        # 同時支援 Result 模式與舊版直接回傳模式
        try:
            raw_role_ids = await service_result.get_council_role_ids(guild_id=interaction.guild_id)
            raw_config = await service_result.get_config(guild_id=interaction.guild_id)
        except GovernanceNotConfiguredError:
            error_message = ErrorMessageTemplates.not_configured("理事會治理")
            await send_message_compat(
                interaction,
                content=error_message,
                ephemeral=True,
            )
            return
        except Exception as exc:
            LOGGER.error("council.list_roles.error", error=str(exc))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error(str(exc)),
                ephemeral=True,
            )
            return

        role_ids_ok, role_ids_err = _unwrap_result(raw_role_ids)
        if role_ids_err is not None:
            LOGGER.error("council.list_roles.error", error=str(role_ids_err))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.from_error(role_ids_err),
                ephemeral=True,
            )
            return

        config_ok, config_err = _unwrap_result(raw_config)
        if config_err is not None:
            error = config_err
            if isinstance(error, GovernanceNotConfiguredError):
                error_message = ErrorMessageTemplates.not_configured("理事會治理")
            else:
                error_message = ErrorMessageTemplates.from_error(error)
            await send_message_compat(
                interaction,
                content=error_message,
                ephemeral=True,
            )
            return

        role_ids = cast(Sequence[int], role_ids_ok or [])
        cfg = cast(CouncilConfig, config_ok)

        lines: list[str] = []
        mentioned_ids: set[int] = set()
        for role_id in role_ids:
            role = interaction.guild.get_role(role_id)
            mention = role.mention if role else f"`{role_id}`"
            lines.append(f"• {mention}")
            mentioned_ids.add(role_id)

        # 保持向下相容：若舊的 council_role_id 仍存在且未列出，也顯示
        if cfg.council_role_id and cfg.council_role_id not in mentioned_ids:
            legacy = interaction.guild.get_role(cfg.council_role_id)
            mention = legacy.mention if legacy else f"`{cfg.council_role_id}`"
            lines.append(f"• {mention}（舊版設定）")

        content = (
            "目前沒有額外的常任理事身分組。"
            if not lines
            else "常任理事身分組：\n" + "\n".join(lines)
        )
        await send_message_compat(interaction, content=content, ephemeral=True)

    return council


# --- Voting UI ---


class VotingView(discord.ui.View):
    def __init__(self, *, proposal_id: UUID, service: CouncilServiceResult) -> None:
        super().__init__(timeout=None)
        self.proposal_id = proposal_id
        self.service = service

    @discord.ui.button(
        label="同意",
        style=discord.ButtonStyle.success,
        custom_id="council_vote_approve",
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[Any],
    ) -> None:
        await _handle_vote(interaction, self.service, self.proposal_id, "approve")

    @discord.ui.button(
        label="反對",
        style=discord.ButtonStyle.danger,
        custom_id="council_vote_reject",
    )
    async def reject(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[Any],
    ) -> None:
        await _handle_vote(interaction, self.service, self.proposal_id, "reject")

    @discord.ui.button(
        label="棄權",
        style=discord.ButtonStyle.secondary,
        custom_id="council_vote_abstain",
    )
    async def abstain(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[Any],
    ) -> None:
        await _handle_vote(interaction, self.service, self.proposal_id, "abstain")


async def _handle_vote(
    interaction: discord.Interaction,
    service: CouncilServiceResult,
    proposal_id: UUID,
    choice: str,
) -> None:
    from src.bot.services.council_errors import CouncilPermissionDeniedError

    # 同時支援 Result 模式與舊版「直接丟例外」的 service.vote 實作
    try:
        raw_result = await service.vote(
            proposal_id=proposal_id,
            voter_id=interaction.user.id,
            choice=choice,
        )
    except CouncilPermissionDeniedError as error:
        await interaction.response.send_message(
            getattr(error, "message", str(error)), ephemeral=True
        )
        return
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.error("council.vote.error", error=str(exc))
        await interaction.response.send_message("投票失敗。", ephemeral=True)
        return

    ok_value, error = _unwrap_result(raw_result)

    if isinstance(error, CouncilPermissionDeniedError):
        await interaction.response.send_message(error.message, ephemeral=True)
        return
    if error is not None:
        LOGGER.error("council.vote.error", error=str(error))
        await interaction.response.send_message("投票失敗。", ephemeral=True)
        return

    totals, status = cast(tuple[VoteTotals, str], ok_value)

    embed = discord.Embed(title="理事會轉帳提案（投票）", color=0x2ECC71)
    embed.add_field(name="狀態", value=status, inline=False)
    embed.add_field(
        name="合計票數",
        value=f"同意 {totals.approve} / 反對 {totals.reject} / 棄權 {totals.abstain}",
    )
    embed.add_field(name="門檻 T", value=str(totals.threshold_t))
    await interaction.response.send_message("已記錄您的投票。", ephemeral=True)
    try:
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception:
        pass

    # 若已結案，廣播結果（揭露個別票）
    if status in ("已執行", "執行失敗", "已否決", "已逾時"):
        guild = interaction.guild
        if guild is None and interaction.guild_id is not None:
            guild = interaction.client.get_guild(interaction.guild_id)
        if guild is None:
            return
        try:
            await _broadcast_result(interaction.client, guild, service, proposal_id, status)
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("council.result_dm.error", error=str(exc))


async def _dm_council_for_voting(
    client: discord.Client,
    guild: discord.Guild,
    service: CouncilServiceResult,
    proposal: Any,
) -> None:
    # 直接使用傳入的 Result 服務，移除 DI 回退與臨時新建

    view = VotingView(proposal_id=proposal.proposal_id, service=service)
    # Anonymous in-progress: only aggregated counts are shown in the button acknowledgment

    # 使用新的多身分組機制獲取所有理事
    members: list[discord.Member] = []
    try:
        # 以 Result 模式取得理事會身分組 ID（相容巢狀 Result）
        role_ids_ok, role_ids_err = _unwrap_result(
            await service.get_council_role_ids(guild_id=guild.id)
        )
        if role_ids_err is not None:
            LOGGER.warning("council.dm.fetch_members_error", error=str(role_ids_err))
        else:
            council_role_ids = list(cast(Sequence[int], role_ids_ok or []))
            for role_id in council_role_ids:
                role = guild.get_role(role_id)
                if role:
                    members.extend(role.members)

            # 如果沒有多身分組配置，向下相容使用單一身分組
            if not members:
                cfg_ok, cfg_err = _unwrap_result(await service.get_config(guild_id=guild.id))
                if cfg_err is not None:
                    LOGGER.warning("council.dm.fetch_members_error", error=str(cfg_err))
                else:
                    cfg = cast(CouncilConfig, cfg_ok)
                    role = guild.get_role(cfg.council_role_id)
                    if role:
                        members.extend(role.members)
    except Exception as exc:  # pragma: no cover - best effort
        LOGGER.warning("council.dm.fetch_members_error", error=str(exc))

    embed = discord.Embed(title="理事會轉帳提案（請投票）", color=0x3498DB)
    embed.add_field(name="提案編號", value=str(proposal.proposal_id), inline=False)
    # Show department name if target_department_id exists, otherwise show user mention
    registry = get_registry()
    if hasattr(proposal, "target_department_id") and proposal.target_department_id:
        dept = registry.get_by_id(proposal.target_department_id)
        target_str = dept.name if dept else proposal.target_department_id
    else:
        target_str = f"<@{proposal.target_id}>"
    embed.add_field(name="受款人", value=target_str)
    embed.add_field(name="金額", value=str(proposal.amount))
    if proposal.description:
        embed.add_field(name="用途", value=proposal.description, inline=False)
    if proposal.attachment_url:
        embed.add_field(name="附件", value=proposal.attachment_url, inline=False)
    embed.set_footer(
        text=(f"門檻 T={proposal.threshold_t}，" f"截止：{proposal.deadline_at:%Y-%m-%d %H:%M UTC}")
    )

    for m in members:
        try:
            await m.send(embed=embed, view=view)
        except Exception as exc:
            LOGGER.warning("council.dm.failed", member=m.id, error=str(exc))


# --- Background scheduler for reminders and timeouts ---


_scheduler_task: asyncio.Task[None] | None = None


def _install_background_scheduler(client: discord.Client, service: CouncilServiceResult) -> None:
    global _scheduler_task
    if _scheduler_task is not None:
        return

    async def _runner() -> None:
        await client.wait_until_ready()
        # 以 persistent view 註冊現有進行中的提案投票按鈕（重啟後舊按鈕仍可用）
        try:
            await _register_persistent_views(client, service)
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("council.persistent_view.error", error=str(exc))

        # 避免重複廣播：維護已廣播結果的提案集合（僅於本次執行期間有效）
        broadcasted: set[UUID] = set()
        while not client.is_closed():
            try:
                # 先抓取逾時候選，供結束後廣播使用
                from src.infra.types.db import ConnectionProtocol, PoolProtocol

                pool: PoolProtocol = cast(PoolProtocol, get_pool())
                due_before: list[UUID] = []
                async with pool.acquire() as conn:
                    from src.db.gateway.council_governance import CouncilGovernanceGateway

                    gw = CouncilGovernanceGateway()
                    c: ConnectionProtocol = conn
                    for p in await gw.list_due_proposals(c):
                        due_before.append(p.proposal_id)

                # Expire due proposals (timeout or execute if reached threshold unseen)
                changed = await service.expire_due_proposals()
                if changed:
                    LOGGER.info("council.scheduler.expire", changed=changed)

                # Send T-24h reminders to non-voters
                async with pool.acquire() as conn:
                    from src.db.gateway.council_governance import CouncilGovernanceGateway

                    gw = CouncilGovernanceGateway()
                    c2: ConnectionProtocol = conn
                    for p in await gw.list_reminder_candidates(c2):
                        unvoted_ok, unvoted_err = _unwrap_result(
                            await service.list_unvoted_members(proposal_id=p.proposal_id)
                        )
                        if unvoted_err is not None:
                            continue
                        unvoted = cast(Sequence[int], unvoted_ok or [])
                        # Try DM only unvoted members
                        guild = client.get_guild(p.guild_id)
                        if guild is not None:
                            for uid in unvoted:
                                member = guild.get_member(uid)
                                if member is None:
                                    try:
                                        user = await client.fetch_user(uid)
                                        await user.send(
                                            f"提案 {p.proposal_id} 24 小時內截止，請盡速投票。"
                                        )
                                    except Exception:
                                        pass
                                else:
                                    try:
                                        await member.send(
                                            f"提案 {p.proposal_id} 24 小時內截止，請盡速投票。"
                                        )
                                    except Exception:
                                        pass
                        await gw.mark_reminded(c2, proposal_id=p.proposal_id)

                # 廣播剛結束的提案結果（逾時或已執行/失敗），避免重複
                for pid in due_before:
                    if pid in broadcasted:
                        continue
                    # 嘗試抓 guild 與最新狀態
                    try:
                        # 透過 service 取回提案，若已結束則廣播
                        proposal_result = await service.get_proposal(proposal_id=pid)
                        if isinstance(proposal_result, Err):
                            continue
                        proposal_raw = proposal_result.value
                        proposal = cast(Proposal | None, proposal_raw)
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
                LOGGER.exception("council.scheduler.error", error=str(exc))
            await asyncio.sleep(60)

    try:
        _scheduler_task = asyncio.create_task(_runner(), name="council-scheduler")
    except RuntimeError:
        # 沒有運行的事件循環，通常在測試環境中
        pass


__all__ = ["get_help_data", "register", "SupremeAssemblyService"]


# --- Panel UI ---


class CouncilPanelView(PersistentPanelView):
    """理事會面板容器（ephemeral）。"""

    panel_type = "council"

    def __init__(
        self,
        *,
        service: CouncilServiceResult,
        guild: discord.Guild,
        author_id: int,
        council_role_id: int,
    ) -> None:
        super().__init__(author_id=author_id, timeout=600.0)
        self.service = service
        self.guild = guild
        self.council_role_id = council_role_id
        self._unsubscribe: Callable[[], Awaitable[None]] | None = None
        self._update_lock = asyncio.Lock()
        self._paginator: CouncilProposalPaginator | None = None

        # 元件：建案、提案選擇、匯出
        self._propose_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="建立轉帳提案",
            style=discord.ButtonStyle.primary,
        )
        self._propose_btn.callback = self._on_click_propose
        self.add_item(self._propose_btn)

        # 查看所有提案按鈕（使用新的分頁系統）
        self._view_all_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="📋 查看所有提案",
            style=discord.ButtonStyle.secondary,
        )
        self._view_all_btn.callback = self._on_click_view_all_proposals
        self.add_item(self._view_all_btn)

        self._export_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="匯出資料",
            style=discord.ButtonStyle.secondary,
        )
        self._export_btn.callback = self._on_click_export
        self.add_item(self._export_btn)

        # 使用指引按鈕：顯示依理事會面板操作而設計之說明
        self._help_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="使用指引",
            style=discord.ButtonStyle.secondary,
        )
        self._help_btn.callback = self._on_click_help
        self.add_item(self._help_btn)

        self._select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder="選擇進行中提案以投票/撤案",
            min_values=1,
            max_values=1,
            options=[],
        )
        self._select.callback = self._on_select_proposal
        self.add_item(self._select)

    async def _resolve_council_account_id(self) -> int:
        """優先使用政府帳戶映射取得常任理事會帳戶 ID，失敗時回退舊版推導值。"""
        try:
            sc_service = StateCouncilService()
            accounts = await sc_service.get_all_accounts(guild_id=self.guild.id)
            for acc in accounts:
                department = getattr(acc, "department", None)
                if department in {"常任理事會", "permanent_council"}:
                    account_id = getattr(acc, "account_id", None)
                    if account_id is not None:
                        return int(account_id)
        except Exception as exc:  # pragma: no cover - 記錄並回退
            LOGGER.debug(
                "council.panel.account.resolve_failed",
                guild_id=self.guild.id,
                error=str(exc),
            )
            return CouncilService.derive_council_account_id(self.guild.id)

        return CouncilService.derive_council_account_id(self.guild.id)

    async def bind_message(self, message: discord.Message) -> None:
        """綁定訊息並訂閱治理事件，以便即時更新。"""
        if self._message is not None:
            return
        await super().bind_message(message)
        try:
            self._unsubscribe = await subscribe_council_events(
                self.guild.id,
                self._handle_event,
            )
            LOGGER.info(
                "council.panel.subscribe",
                guild_id=self.guild.id,
                message_id=message.id,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._unsubscribe = None
            LOGGER.warning(
                "council.panel.subscribe_failed",
                guild_id=self.guild.id,
                error=str(exc),
            )

    async def build_summary_embed(self) -> discord.Embed:
        """產生面板摘要 Embed（餘額、理事名單）。"""
        embed = discord.Embed(title="常任理事會面板", color=0x95A5A6)
        balance_str = "N/A"
        try:
            if self.author_id is None:
                raise ValueError("author_id is required")
            balance_service = BalanceService(get_pool())
            council_account_id = await self._resolve_council_account_id()
            snap_result = await balance_service.get_balance_snapshot(
                guild_id=self.guild.id,
                requester_id=self.author_id,
                target_member_id=council_account_id,
                can_view_others=True,
            )
            if isinstance(snap_result, Ok):
                snap = snap_result.value
                balance_str = f"{snap.balance:,}"
        except Exception as exc:  # pragma: no cover - best effort
            LOGGER.warning(
                "council.panel.summary.balance_error",
                guild_id=self.guild.id,
                error=str(exc),
            )

        # 使用新的多身分組機制獲取所有理事
        council_members: list[discord.Member] = []
        try:
            # 以 Result 模式取得理事會身分組 ID（相容巢狀 Result）
            role_ids_ok, role_ids_err = _unwrap_result(
                await self.service.get_council_role_ids(guild_id=self.guild.id)
            )
            if role_ids_err is not None:
                LOGGER.warning(
                    "council.panel.members_fetch_error",
                    guild_id=self.guild.id,
                    error=str(role_ids_err),
                )
            else:
                council_role_ids = list(cast(Sequence[int], role_ids_ok or []))
                for role_id in council_role_ids:
                    role = self.guild.get_role(role_id)
                    if role:
                        members = cast(Sequence[discord.Member], getattr(role, "members", []))
                        council_members.extend(members)

                # 如果沒有多身分組配置，向下相容使用單一身分組
                if not council_members and self.council_role_id:
                    role = self.guild.get_role(self.council_role_id)
                    if role:
                        members = cast(Sequence[discord.Member], getattr(role, "members", []))
                        council_members.extend(members)

            # 若 Result 取得失敗亦嘗試使用單一身分組
            if not council_members and self.council_role_id:
                role = self.guild.get_role(self.council_role_id)
                if role:
                    members = cast(Sequence[discord.Member], getattr(role, "members", []))
                    council_members.extend(members)
        except Exception as exc:  # pragma: no cover - best effort
            LOGGER.warning(
                "council.panel.members_fetch_error",
                guild_id=self.guild.id,
                error=str(exc),
            )

        # 去除重複成員
        deduped: dict[int, discord.Member] = {member.id: member for member in council_members}
        unique_members: list[discord.Member] = list(deduped.values())
        N = 10
        top_mentions = (
            ", ".join(m.mention for m in unique_members[:N]) if unique_members else "(無)"
        )
        summary = f"餘額：{balance_str}｜理事（{len(unique_members)}）: {top_mentions}"
        embed.add_field(name="Council 摘要", value=summary, inline=False)
        embed.description = "在此可：建立提案、檢視進行中提案並投票、撤案與匯出。"
        return embed

    def _build_help_embed(self) -> discord.Embed:
        """建構理事會面板之使用指引。"""
        lines = [
            "• 開啟方式：於伺服器使用 /council panel（僅限理事）。",
            (
                "• 建立提案：點擊『建立轉帳提案』，選擇轉帳類型（轉帳給使用者或政府部門），"
                "然後選擇受款人、輸入金額、用途與附件（選填）。"
            ),
            (
                "• 轉帳類型：可選擇轉帳給使用者（使用 Discord 使用者選擇器）"
                "或轉帳給政府部門（從下拉選單選擇）。"
            ),
            "• 名冊快照：建案當下鎖定理事名單與投票門檻 T，用於後續投票與決議。",
            "• 投票：於『進行中提案』下拉選擇提案後可進行『同意/反對/棄權』。",
            "• 撤案限制：僅提案人且在『尚無任何投票』時可按『撤案（無票前）』。",
            "• 匯出：管理員或具 manage_guild 可按『匯出資料』輸出 JSON/CSV（可選期間）。",
            "• 即時更新：面板開啟期間會自動刷新清單與合計票數。",
            "• 私密性：所有回覆皆為 ephemeral，僅對開啟者可見。",
        ]
        embed = discord.Embed(title="ℹ️ 使用指引｜常任理事會面板", color=0x95A5A6)
        embed.description = "\n".join(lines)
        return embed

    async def _on_click_help(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("僅限面板開啟者操作。", ephemeral=True)
            return
        try:
            await interaction.response.send_message(embed=self._build_help_embed(), ephemeral=True)
        except Exception:
            # 後援：若已回覆，改用 followup
            try:
                await interaction.followup.send(embed=self._build_help_embed(), ephemeral=True)
            except Exception:
                pass

    async def refresh_options(self) -> None:
        """以最近進行中提案刷新選單（使用新的分頁系統）。"""
        try:
            # Get active proposals using Result pattern
            active_result = await self.service.list_active_proposals()
            if isinstance(active_result, Ok):
                active = cast(Sequence[Proposal], active_result.value)
                # 僅顯示本 guild 的進行中提案（依 created_at 降冪）
                items = [p for p in active if p.guild_id == self.guild.id and p.status == "進行中"]
                items.sort(key=lambda p: p.created_at, reverse=True)
            else:
                # If error, use empty list
                LOGGER.error("council.panel.refresh.error", error=str(active_result.error))
                items = []

            # 更新分頁器
            if hasattr(self, "_paginator") and self._paginator:
                await self._paginator.refresh_items(items)
            else:
                # 初始化分頁器
                from src.bot.ui.council_paginator import CouncilProposalPaginator

                self._paginator = CouncilProposalPaginator(
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
            LOGGER.exception("council.panel.refresh.error", error=str(exc))

    async def _on_click_propose(self, interaction: discord.Interaction) -> None:
        # 僅限理事（面板開啟時已檢查，此處再保險一次）
        user_roles = [role.id for role in getattr(interaction.user, "roles", [])]
        perm_result = await self.service.check_council_permission(
            guild_id=self.guild.id, user_roles=user_roles
        )
        if isinstance(perm_result, Ok):
            has_permission = bool(perm_result.value)
        else:
            # Log error but deny permission by default
            LOGGER.error("council.propose.permission_check_failed", error=str(perm_result.error))
            has_permission = False

        if not has_permission:
            await interaction.response.send_message(
                "僅限具備常任理事身分組的人員可建立提案。", ephemeral=True
            )
            return

        # Show transfer type selection view instead of modal
        view = TransferTypeSelectionView(service=self.service, guild=self.guild)
        await interaction.response.send_message("請選擇轉帳類型：", view=view, ephemeral=True)

    async def _on_click_export(self, interaction: discord.Interaction) -> None:
        # 僅限管理員/管理伺服器權限
        perms = getattr(interaction.user, "guild_permissions", None)
        if not perms or not (perms.administrator or perms.manage_guild):
            await interaction.response.send_message(
                "匯出需管理員或管理伺服器權限。",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ExportModal(service=self.service, guild=self.guild))

    async def _on_select_proposal(self, interaction: discord.Interaction) -> None:
        # 直接讀取選擇值
        pid_str = self._select.values[0] if self._select.values else None
        if pid_str in (None, "none"):
            await interaction.response.send_message("沒有可操作的提案。", ephemeral=True)
            return
        from uuid import UUID as _UUID

        try:
            pid = _UUID(pid_str)
        except Exception:
            await interaction.response.send_message("選項格式錯誤。", ephemeral=True)
            return
        # Get proposal using Result pattern（相容巢狀 Result）
        proposal_ok, proposal_err = _unwrap_result(await self.service.get_proposal(proposal_id=pid))
        if proposal_err is not None:
            message = getattr(proposal_err, "message", str(proposal_err))
            await interaction.response.send_message(f"取得提案失敗：{message}", ephemeral=True)
            return

        if proposal_ok is None:
            await interaction.response.send_message("提案不存在或不屬於此伺服器。", ephemeral=True)
            return

        proposal = cast(Proposal, proposal_ok)
        if proposal.guild_id != self.guild.id:
            await interaction.response.send_message("提案不存在或不屬於此伺服器。", ephemeral=True)
            return

        embed = discord.Embed(title="提案詳情", color=0x3498DB)
        embed.add_field(name="摘要", value=_format_proposal_desc(proposal), inline=False)
        embed.add_field(name="提案 ID", value=str(proposal.proposal_id), inline=False)
        view = ProposalActionView(
            service=self.service,
            proposal_id=proposal.proposal_id,
            can_cancel=(interaction.user.id == proposal.proposer_id),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _handle_event(self, event: CouncilEvent) -> None:
        if event.guild_id != self.guild.id:
            return
        if self.is_finished() or self._message is None:
            return
        await self._apply_live_update(event)

    async def _apply_live_update(self, event: CouncilEvent) -> None:
        if self._message is None or self.is_finished():
            return
        async with self._update_lock:
            await self.refresh_options()
            embed: discord.Embed | None = None
            try:
                embed = await self.build_summary_embed()
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning(
                    "council.panel.summary.refresh_error",
                    guild_id=self.guild.id,
                    error=str(exc),
                )
            try:
                if embed is not None:
                    await self._message.edit(embed=embed, view=self)
                else:
                    await self._message.edit(view=self)
                LOGGER.debug(
                    "council.panel.live_update.applied",
                    guild_id=self.guild.id,
                    kind=event.kind,
                    proposal_id=str(event.proposal_id) if event.proposal_id else None,
                )
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning(
                    "council.panel.live_update.failed",
                    guild_id=self.guild.id,
                    error=str(exc),
                )

            # 同時更新分頁器以保持即時更新
            if hasattr(self, "_paginator") and self._paginator:
                try:
                    # 分頁器會透過回調自動更新數據
                    active_ok, active_err = _unwrap_result(
                        await self.service.list_active_proposals()
                    )
                    if active_err is not None:
                        LOGGER.warning(
                            "council.panel.paginator_update.failed",
                            guild_id=self.guild.id,
                            error=str(active_err),
                        )
                    else:
                        active = cast(Sequence[Proposal], active_ok or [])
                        await self._paginator.refresh_items(
                            [
                                p
                                for p in active
                                if p.guild_id == self.guild.id and p.status == "進行中"
                            ]
                        )
                except Exception as exc:  # pragma: no cover - defensive
                    LOGGER.warning(
                        "council.panel.paginator_update.failed",
                        guild_id=self.guild.id,
                        error=str(exc),
                    )

    async def _on_pagination_update(self) -> None:
        """分頁器更新回調，用於即時更新。"""
        # 當分頁器需要更新時，重新載入提案數據
        await self.refresh_options()

    async def _on_click_view_all_proposals(self, interaction: discord.Interaction) -> None:
        """查看所有提案的分頁列表。"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("僅限面板開啟者操作。", ephemeral=True)
            return

        if not hasattr(self, "_paginator") or not self._paginator:
            await interaction.response.send_message(
                "分頁器尚未初始化，請稍後再試。",
                ephemeral=True,
            )
            return

        try:
            # 創建分頁訊息
            embed = self._paginator.create_embed(0)
            view = self._paginator.create_view()

            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True,
            )
        except Exception as exc:
            LOGGER.exception(
                "council.panel.view_all_proposals.error",
                guild_id=self.guild.id,
                user_id=interaction.user.id,
                error=str(exc),
            )
            await interaction.response.send_message(
                "顯示提案列表時發生錯誤，請稍後再試。",
                ephemeral=True,
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
                "council.panel.unsubscribe",
                guild_id=self.guild.id,
                message_id=self._message.id if self._message else None,
            )
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning(
                "council.panel.unsubscribe_failed",
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


# --- Transfer Proposal UI Components ---


class TransferTypeSelectionView(discord.ui.View):
    """View for selecting transfer type (user, department, or company)."""

    def __init__(self, *, service: CouncilServiceResult, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild

    @discord.ui.button(
        label="轉帳給使用者",
        style=discord.ButtonStyle.primary,
        emoji="👤",
    )
    async def select_user(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        # Show user select component
        view = UserSelectView(service=self.service, guild=self.guild)
        await interaction.response.send_message("請選擇受款使用者：", view=view, ephemeral=True)

    @discord.ui.button(
        label="轉帳給政府部門",
        style=discord.ButtonStyle.primary,
        emoji="🏛️",
    )
    async def select_department(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        # Show department select view
        view = DepartmentSelectView(service=self.service, guild=self.guild)
        await interaction.response.send_message("請選擇受款部門：", view=view, ephemeral=True)

    @discord.ui.button(
        label="轉帳給公司",
        style=discord.ButtonStyle.primary,
        emoji="🏢",
    )
    async def select_company(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        # Show company select view
        view = CouncilCompanySelectView(service=self.service, guild=self.guild)
        has_companies = await view.setup()
        if not has_companies:
            await interaction.response.send_message(
                "❗ 此伺服器目前沒有已登記的公司。", ephemeral=True
            )
            return
        await interaction.response.send_message("請選擇受款公司：", view=view, ephemeral=True)


class DepartmentSelectView(discord.ui.View):
    """View for selecting a government department."""

    def __init__(self, *, service: CouncilServiceResult, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild
        registry = get_registry()
        # 僅列出部門等級（排除常任理事會與國務院），避免出現不支援的收款目標。
        departments = registry.get_by_level("department")

        # Create select menu with departments
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
            await interaction.response.send_message("請選擇一個部門。", ephemeral=True)
            return
        values = _extract_select_values(interaction)
        if not values:
            await interaction.response.send_message("請選擇一個部門。", ephemeral=True)
            return
        selected_id: str | None = values[0]
        if not selected_id:
            await interaction.response.send_message("請選擇一個部門。", ephemeral=True)
            return

        registry = get_registry()
        dept = registry.get_by_id(selected_id)
        if dept is None:
            await interaction.response.send_message("部門不存在。", ephemeral=True)
            return

        # Show transfer proposal modal with department selected
        modal = TransferProposalModal(
            service=self.service,
            guild=self.guild,
            target_department_id=selected_id,
            target_department_name=dept.name,
        )
        await interaction.response.send_modal(modal)


class UserSelectView(discord.ui.View):
    """View for selecting a user (using Discord User Select component)."""

    def __init__(self, *, service: CouncilServiceResult, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild

        # Use Discord User Select component
        user_select: discord.ui.UserSelect[Any] = discord.ui.UserSelect(
            placeholder="選擇使用者",
            min_values=1,
            max_values=1,
        )
        user_select.callback = self._on_select
        self.add_item(user_select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        # 直接從 interaction.data 取得被選取的使用者 ID
        # （UserSelect 的 callback 只會傳入 interaction）
        if not interaction.data:
            await interaction.response.send_message("請選擇一個使用者。", ephemeral=True)
            return
        values = _extract_select_values(interaction)
        if not values:
            await interaction.response.send_message("請選擇一個使用者。", ephemeral=True)
            return
        selected_id: str | None = values[0]
        if not selected_id:
            await interaction.response.send_message("請選擇一個使用者。", ephemeral=True)
            return

        # 嘗試從 guild 快取取得成員，以便展示名稱；若失敗則以 ID 代替
        member = self.guild.get_member(int(selected_id)) if self.guild else None
        display_name = member.display_name if member else str(selected_id)

        # 顯示建立轉帳提案的 Modal，帶入被選取的使用者
        modal = TransferProposalModal(
            service=self.service,
            guild=self.guild,
            target_user_id=int(selected_id),
            target_user_name=display_name,
        )
        await interaction.response.send_modal(modal)


class CouncilCompanySelectView(discord.ui.View):
    """View for selecting a company (for council transfer proposals)."""

    def __init__(self, *, service: CouncilServiceResult, guild: discord.Guild) -> None:
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
            await interaction.response.send_message("請選擇一家公司。", ephemeral=True)
            return

        values = _extract_select_values(interaction)
        if not values:
            await interaction.response.send_message("請選擇一家公司。", ephemeral=True)
            return

        try:
            company_id = int(values[0])
        except ValueError:
            await interaction.response.send_message("選項格式錯誤。", ephemeral=True)
            return

        company = self._companies.get(company_id)
        if company is None:
            await interaction.response.send_message("找不到指定的公司。", ephemeral=True)
            return

        # Show transfer proposal modal with company selected
        modal = TransferProposalModal(
            service=self.service,
            guild=self.guild,
            target_company_account_id=company.account_id,
            target_company_name=company.name,
        )
        await interaction.response.send_modal(modal)


class TransferProposalModal(discord.ui.Modal, title="建立轉帳提案"):
    """Modal for creating transfer proposal with amount, description, and attachment."""

    def __init__(
        self,
        *,
        service: CouncilServiceResult,
        guild: discord.Guild,
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
        self.target_user_id = target_user_id
        self.target_user_name = target_user_name
        self.target_department_id = target_department_id
        self.target_department_name = target_department_name
        self.target_company_account_id = target_company_account_id
        self.target_company_name = target_company_name

        # Show target info in a disabled text input
        target_label = "受款人"
        target_value = ""
        if target_company_name:
            target_value = f"公司：{target_company_name}"
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
        self.attachment_url: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="附件連結（可選）",
            required=False,
        )
        self.add_item(self.target_info)
        self.add_item(self.amount)
        self.add_item(self.description)
        self.add_item(self.attachment_url)

    async def on_submit(self, interaction: discord.Interaction) -> None:  # noqa: D401
        # Validate that a target is selected
        if (
            not self.target_user_id
            and not self.target_department_id
            and not self.target_company_account_id
        ):
            await interaction.response.send_message("錯誤：未選擇受款人。", ephemeral=True)
            return

        # Validate amount
        try:
            amt = int(str(self.amount.value).replace(",", "").strip())
        except Exception:
            await interaction.response.send_message("金額需為正整數。", ephemeral=True)
            return
        if amt <= 0:
            await interaction.response.send_message("金額需 > 0。", ephemeral=True)
            return
        # 以 Result 模式取得設定與快照名冊（同時支援舊版直接丟例外的服務）
        try:
            raw_cfg = await self.service.get_config(guild_id=self.guild.id)
        except GovernanceNotConfiguredError:
            await interaction.response.send_message("尚未完成治理設定。", ephemeral=True)
            return
        except Exception as exc:
            LOGGER.error("council.panel.propose.config_error", error=str(exc))
            await interaction.response.send_message(
                "建案失敗：" + str(exc),
                ephemeral=True,
            )
            return

        cfg_ok, cfg_err = _unwrap_result(raw_cfg)
        if cfg_err is not None:
            if isinstance(cfg_err, GovernanceNotConfiguredError):
                await interaction.response.send_message("尚未完成治理設定。", ephemeral=True)
            else:
                LOGGER.error("council.panel.propose.config_error", error=str(cfg_err))
                await interaction.response.send_message(
                    "建案失敗：" + str(cfg_err),
                    ephemeral=True,
                )
            return

        cfg = cast(CouncilConfig, cfg_ok)
        role = self.guild.get_role(cfg.council_role_id)
        snapshot_ids = [m.id for m in role.members] if role is not None else []
        if not snapshot_ids:
            await interaction.response.send_message(
                "理事名冊為空，請先確認角色有成員。",
                ephemeral=True,
            )
            return

        # Create proposal
        # For department transfers, we still need a target_id (use department account ID)
        # For user transfers, use the user ID
        # For company transfers, use the company account ID
        target_id = self.target_user_id
        if self.target_company_account_id and not target_id:
            # Use company account ID directly
            target_id = self.target_company_account_id
        elif self.target_department_id and not target_id:
            # Derive department account ID for the target_id field
            from src.bot.services.state_council_service import StateCouncilService

            registry = get_registry()
            dept = registry.get_by_id(self.target_department_id)
            if dept:
                target_id = StateCouncilService.derive_department_account_id(
                    self.guild.id, dept.name
                )

        if not target_id:
            await interaction.response.send_message("錯誤：無法確定受款帳戶。", ephemeral=True)
            return

        proposal_ok, proposal_err = _unwrap_result(
            await self.service.create_transfer_proposal(
                guild_id=self.guild.id,
                proposer_id=interaction.user.id,
                target_id=target_id,
                amount=amt,
                description=str(self.description.value or "").strip() or None,
                attachment_url=str(self.attachment_url.value or "").strip() or None,
                snapshot_member_ids=snapshot_ids,
                target_department_id=self.target_department_id,
            )
        )
        if proposal_err is not None:
            LOGGER.exception("council.panel.propose.error", error=str(proposal_err))
            await interaction.response.send_message(
                "建案失敗：" + str(proposal_err),
                ephemeral=True,
            )
            return

        proposal = cast(Proposal, proposal_ok)
        await interaction.response.send_message(
            f"已建立提案 {proposal.proposal_id}，並將以 DM 通知理事。",
            ephemeral=True,
        )
        try:
            await _dm_council_for_voting(interaction.client, self.guild, self.service, proposal)
        except Exception:
            pass
        LOGGER.info(
            "council.panel.propose",
            guild_id=self.guild.id,
            user_id=interaction.user.id,
            proposal_id=str(proposal.proposal_id),
        )


class ProposeTransferModal(discord.ui.Modal, title="建立轉帳提案"):
    def __init__(self, *, service: CouncilServiceResult, guild: discord.Guild) -> None:
        super().__init__()
        self.service = service
        self.guild = guild
        self.target: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="受款人（@mention 或 ID）",
            placeholder="@user 或 1234567890",
        )
        self.amount: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="金額（正整數）",
            placeholder="例如 100",
        )
        self.description: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="用途描述",
            style=discord.TextStyle.paragraph,
            required=False,
        )
        self.attachment_url: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="附件連結（可選）",
            required=False,
        )
        self.add_item(self.target)
        self.add_item(self.amount)
        self.add_item(self.description)
        self.add_item(self.attachment_url)

    async def on_submit(self, interaction: discord.Interaction) -> None:  # noqa: D401
        # 解析受款人
        raw = str(self.target.value).strip()
        uid: int | None = None
        try:
            if raw.startswith("<@") and raw.endswith(">"):
                raw = raw.strip("<@!>")
            uid = int(raw)
        except Exception:
            # 嘗試以 mention 名稱找（不一定可靠），否則回錯誤
            uid = None

        member: discord.Member | discord.User | None = None
        if uid is not None:
            member = self.guild.get_member(uid) or interaction.client.get_user(uid)
            if member is None:
                try:
                    member = await interaction.client.fetch_user(uid)
                except Exception:
                    member = None
        if member is None:
            await interaction.response.send_message(
                "無法辨識受款人，請輸入 @mention 或使用者 ID。",
                ephemeral=True,
            )
            return

        # 數值驗證
        try:
            amt = int(str(self.amount.value).replace(",", "").strip())
        except Exception:
            await interaction.response.send_message("金額需為正整數。", ephemeral=True)
            return
        if amt <= 0:
            await interaction.response.send_message("金額需 > 0。", ephemeral=True)
            return
        # 快照名冊（Result 模式，相容巢狀 Result，同時支援舊版直接丟例外的服務）
        try:
            raw_cfg = await self.service.get_config(guild_id=self.guild.id)
        except GovernanceNotConfiguredError:
            await interaction.response.send_message("尚未完成治理設定。", ephemeral=True)
            return
        except Exception as exc:
            LOGGER.error("council.panel.propose.config_error", error=str(exc))
            await interaction.response.send_message(
                "建案失敗：" + str(exc),
                ephemeral=True,
            )
            return

        cfg_ok, cfg_err = _unwrap_result(raw_cfg)
        if cfg_err is not None:
            if isinstance(cfg_err, GovernanceNotConfiguredError):
                await interaction.response.send_message("尚未完成治理設定。", ephemeral=True)
            else:
                LOGGER.error("council.panel.propose.config_error", error=str(cfg_err))
                await interaction.response.send_message(
                    "建案失敗：" + str(cfg_err),
                    ephemeral=True,
                )
            return

        cfg = cast(CouncilConfig, cfg_ok)
        role = self.guild.get_role(cfg.council_role_id)
        snapshot_ids = [m.id for m in role.members] if role is not None else []
        if not snapshot_ids:
            await interaction.response.send_message(
                "理事名冊為空，請先確認角色有成員。",
                ephemeral=True,
            )
            return

        proposal_ok, proposal_err = _unwrap_result(
            await self.service.create_transfer_proposal(
                guild_id=self.guild.id,
                proposer_id=interaction.user.id,
                target_id=member.id,
                amount=amt,
                description=str(self.description.value or "").strip() or None,
                attachment_url=str(self.attachment_url.value or "").strip() or None,
                snapshot_member_ids=snapshot_ids,
            )
        )
        if proposal_err is not None:
            LOGGER.exception("council.panel.propose.error", error=str(proposal_err))
            await interaction.response.send_message(
                "建案失敗：" + str(proposal_err),
                ephemeral=True,
            )
            return

        proposal = cast(Proposal, proposal_ok)
        await interaction.response.send_message(
            f"已建立提案 {proposal.proposal_id}，並將以 DM 通知理事。",
            ephemeral=True,
        )
        try:
            await _dm_council_for_voting(interaction.client, self.guild, self.service, proposal)
        except Exception:
            pass
        LOGGER.info(
            "council.panel.propose",
            guild_id=self.guild.id,
            user_id=interaction.user.id,
            proposal_id=str(proposal.proposal_id),
        )


class ExportModal(discord.ui.Modal, title="匯出治理資料"):
    def __init__(self, *, service: CouncilServiceResult, guild: discord.Guild) -> None:
        super().__init__()
        self.service = service
        self.guild = guild

        self.start: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="起始時間（ISO 8601，例如 2025-01-01T00:00:00Z）",
            required=True,
            placeholder="2025-01-01T00:00:00Z",
            max_length=40,
        )
        self.end: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="結束時間（ISO 8601，例如 2025-01-31T23:59:59Z）",
            required=True,
            placeholder="2025-01-31T23:59:59Z",
            max_length=40,
        )
        self.format: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="格式（json 或 csv）",
            required=True,
            placeholder="json 或 csv",
            max_length=10,
        )

        self.add_item(self.start)
        self.add_item(self.end)
        self.add_item(self.format)

    async def on_submit(self, interaction: discord.Interaction) -> None:  # noqa: D401
        # 權限再次確認（Modal 可能被開啟後角色有變更）
        perms = getattr(interaction.user, "guild_permissions", None)
        if not perms or not (perms.administrator or perms.manage_guild):
            await interaction.response.send_message("需要管理員或管理伺服器權限。", ephemeral=True)
            return

        if interaction.guild_id is None:
            await interaction.response.send_message("需在伺服器中執行。", ephemeral=True)
            return

        # 解析 ISO 8601
        try:

            def _parse_iso8601(s: str) -> datetime:
                t = s.strip()
                if t.endswith("Z"):
                    t = t[:-1] + "+00:00"
                dt = datetime.fromisoformat(t)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt

            start_dt = _parse_iso8601(str(self.start.value))
            end_dt = _parse_iso8601(str(self.end.value))
        except Exception:
            await interaction.response.send_message(
                "時間格式錯誤，請使用 ISO 8601（例如 2025-01-01T00:00:00Z）",
                ephemeral=True,
            )
            return

        if start_dt > end_dt:
            await interaction.response.send_message("起始時間不可晚於結束時間。", ephemeral=True)
            return

        fmt = str(self.format.value or "").strip().lower()
        if fmt not in ("json", "csv"):
            await interaction.response.send_message("格式必須是 json 或 csv。", ephemeral=True)
            return

        start_utc = start_dt.astimezone(timezone.utc)
        end_utc = end_dt.astimezone(timezone.utc)
        # 匯出資料：同時支援 Result 模式與舊版直接丟例外的服務
        try:
            raw_data = await self.service.export_interval(
                guild_id=interaction.guild_id,
                start=start_utc,
                end=end_utc,
            )
        except Exception as exc:
            LOGGER.exception("council.panel.export.error", error=str(exc))
            await interaction.response.send_message(
                "匯出失敗：" + str(exc),
                ephemeral=True,
            )
            return

        data_ok, data_err = _unwrap_result(raw_data)
        if data_err is not None:
            LOGGER.exception("council.panel.export.error", error=str(data_err))
            await interaction.response.send_message(
                "匯出失敗：" + str(data_err),
                ephemeral=True,
            )
            return

        rows = list(cast(list[dict[str, object]], data_ok or []))

        if fmt == "json":
            buf = io.BytesIO()
            import json

            buf.write(json.dumps(rows, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
            buf.seek(0)
            await interaction.response.send_message(
                content=f"共 {len(rows)} 筆。",
                file=discord.File(buf, filename="council_export.json"),
                ephemeral=True,
            )
        else:
            buf_txt = io.StringIO()
            writer = csv.writer(buf_txt)
            writer.writerow(
                [
                    "proposal_id",
                    "guild_id",
                    "proposer_id",
                    "target_id",
                    "target_department_id",
                    "amount",
                    "status",
                    "created_at",
                    "updated_at",
                    "deadline_at",
                    "snapshot_n",
                    "threshold_t",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row.get("proposal_id"),
                        row.get("guild_id"),
                        row.get("proposer_id"),
                        row.get("target_id"),
                        row.get("target_department_id"),
                        row.get("amount"),
                        row.get("status"),
                        row.get("created_at"),
                        row.get("updated_at"),
                        row.get("deadline_at"),
                        row.get("snapshot_n"),
                        row.get("threshold_t"),
                    ]
                )
            buf = io.BytesIO(buf_txt.getvalue().encode("utf-8"))
            await interaction.response.send_message(
                content=f"共 {len(rows)} 筆。",
                file=discord.File(buf, filename="council_export.csv"),
                ephemeral=True,
            )

        LOGGER.info(
            "council.panel.export",
            guild_id=self.guild.id,
            user_id=interaction.user.id,
            count=len(rows),
            format=fmt,
        )


class ProposalActionView(discord.ui.View):
    def __init__(
        self, *, service: CouncilServiceResult, proposal_id: UUID, can_cancel: bool
    ) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.proposal_id = proposal_id
        self._can_cancel = can_cancel
        # 如果不可撤案，待 view 初始化後移除按鈕
        if not can_cancel:
            # 延後到事件循環下一輪，避免在 __init__ 階段 children 尚未就緒
            async def _remove_later() -> None:
                await asyncio.sleep(0)  # 讓 UI 綁定完成
                for child in list(self.children):
                    if (
                        isinstance(child, discord.ui.Button)
                        and child.custom_id == "panel_cancel_btn"
                    ):
                        try:
                            self.remove_item(child)
                        except Exception:
                            pass

            try:
                asyncio.create_task(_remove_later())
            except Exception:
                pass

    @discord.ui.button(
        label="同意",
        style=discord.ButtonStyle.success,
        custom_id="panel_vote_approve",
    )
    async def approve(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:  # noqa: D401
        await _handle_vote(interaction, self.service, self.proposal_id, "approve")
        LOGGER.info(
            "council.panel.vote",
            user_id=interaction.user.id,
            proposal_id=str(self.proposal_id),
        )

    @discord.ui.button(
        label="反對",
        style=discord.ButtonStyle.danger,
        custom_id="panel_vote_reject",
    )
    async def reject(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:  # noqa: D401
        await _handle_vote(interaction, self.service, self.proposal_id, "reject")
        LOGGER.info(
            "council.panel.vote",
            user_id=interaction.user.id,
            proposal_id=str(self.proposal_id),
        )

    @discord.ui.button(
        label="棄權",
        style=discord.ButtonStyle.secondary,
        custom_id="panel_vote_abstain",
    )
    async def abstain(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:  # noqa: D401
        await _handle_vote(interaction, self.service, self.proposal_id, "abstain")
        LOGGER.info(
            "council.panel.vote",
            user_id=interaction.user.id,
            proposal_id=str(self.proposal_id),
        )

    @discord.ui.button(
        label="撤案（無票前）",
        style=discord.ButtonStyle.secondary,
        custom_id="panel_cancel_btn",
    )
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:  # noqa: D401
        # 僅提案人可見；若仍保留按鈕則再檢查一次
        if not self._can_cancel:
            await interaction.response.send_message("你不是此提案的提案人。", ephemeral=True)
            return
        cancel_ok, cancel_err = _unwrap_result(
            await self.service.cancel_proposal(proposal_id=self.proposal_id)
        )
        if cancel_err is not None:
            LOGGER.error("council.panel.cancel_error", error=str(cancel_err))
            ok = False
        else:
            ok = bool(cancel_ok)
        if ok:
            await interaction.response.send_message("已撤案。", ephemeral=True)
        else:
            await interaction.response.send_message(
                "撤案失敗：可能已有人投票或狀態非進行中。",
                ephemeral=True,
            )
        LOGGER.info(
            "council.panel.cancel",
            user_id=interaction.user.id,
            proposal_id=str(self.proposal_id),
            result="ok" if ok else "failed",
        )


def _format_proposal_title(p: Any) -> str:
    short = str(p.proposal_id)[:8]
    # Show department name if target_department_id exists, otherwise show user mention
    registry = get_registry()
    if hasattr(p, "target_department_id") and p.target_department_id:
        dept = registry.get_by_id(p.target_department_id)
        target_str = dept.name if dept else p.target_department_id
    else:
        target_str = f"<@{p.target_id}>"
    return f"#{short} → {target_str} {p.amount}"


def _format_proposal_desc(p: Any) -> str:
    deadline = p.deadline_at.strftime("%Y-%m-%d %H:%M UTC") if hasattr(p, "deadline_at") else ""
    desc = (p.description or "").strip()
    if desc:
        desc = desc[:60]
    return f"截止 {deadline}｜T={p.threshold_t}｜{desc or '無描述'}"


# --- Helpers ---


async def _broadcast_result(
    client: discord.Client,
    guild: discord.Guild,
    service: CouncilServiceResult,
    proposal_id: UUID,
    status: str,
) -> None:
    """向提案人與全體理事廣播最終結果（揭露個別票）。"""
    # 以 Result 模式取得快照與票數（相容巢狀 Result）
    snapshot_ok, snapshot_err = _unwrap_result(await service.get_snapshot(proposal_id=proposal_id))
    votes_ok, votes_err = _unwrap_result(await service.get_votes_detail(proposal_id=proposal_id))

    if snapshot_err is not None or votes_err is not None:
        LOGGER.error(
            "council.broadcast_result.error",
            snapshot_error=str(snapshot_err) if snapshot_err is not None else None,
            votes_error=str(votes_err) if votes_err is not None else None,
        )
        return

    snapshot = cast(Sequence[int], snapshot_ok or [])
    votes = cast(Sequence[tuple[int, str]], votes_ok or [])
    vote_map = dict(votes)
    lines: list[str] = []
    for uid in snapshot:
        choice_str = vote_map.get(uid, "未投")
        lines.append(f"<@{uid}> → {choice_str}")
    text = "\n".join(lines)
    color = 0x2ECC71 if status == "已執行" else 0xF1C40F
    result_embed = discord.Embed(title="提案結果", color=color)
    result_embed.add_field(name="最終狀態", value=status, inline=False)
    result_embed.add_field(name="個別投票", value=text or "(無)", inline=False)

    # 取得設定（Result 模式）
    config_ok, config_err = _unwrap_result(await service.get_config(guild_id=guild.id))
    if config_err is not None:
        LOGGER.error("council.broadcast_result.config_error", error=str(config_err))
        return

    cfg = cast(CouncilConfig, config_ok)
    role = guild.get_role(cfg.council_role_id)
    members = role.members if role is not None else []

    # 取得提案資訊（Result 模式）
    proposal_ok, proposal_err = _unwrap_result(await service.get_proposal(proposal_id=proposal_id))
    proposer_user: discord.User | discord.Member | None = None
    if proposal_err is None and proposal_ok is not None:
        proposal = cast(Proposal, proposal_ok)
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


async def _register_persistent_views(client: discord.Client, service: CouncilServiceResult) -> None:
    """在啟動後註冊所有進行中提案的 persistent VotingView。"""
    from src.infra.types.db import ConnectionProtocol, PoolProtocol

    pool: PoolProtocol = cast(PoolProtocol, get_pool())
    async with pool.acquire() as conn:
        from src.db.gateway.council_governance import CouncilGovernanceGateway

        gw = CouncilGovernanceGateway()
        c: ConnectionProtocol = conn
        active = await gw.list_active_proposals(c)
        for p in active:
            try:
                client.add_view(VotingView(proposal_id=p.proposal_id, service=service))
            except Exception:
                pass


async def _safe_fetch_user(client: discord.Client, user_id: int) -> discord.User | None:
    """嘗試以 API 取回使用者；若失敗回傳 None。"""
    try:
        return await client.fetch_user(user_id)
    except Exception:
        return None
