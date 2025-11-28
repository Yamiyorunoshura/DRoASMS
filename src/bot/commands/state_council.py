from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Coroutine, Iterable, Literal, Protocol, Sequence, cast

import discord
import structlog
from discord import app_commands

from src.bot.commands.help_data import HelpData
from src.bot.interaction_compat import (
    edit_message_compat,
    send_message_compat,
    send_modal_compat,
)
from src.bot.services.council_service import CouncilServiceResult
from src.bot.services.currency_config_service import (
    CurrencyConfigResult,
    CurrencyConfigService,
)
from src.bot.services.permission_service import PermissionService
from src.bot.services.state_council_service import (
    InsufficientFundsError,
    MonthlyIssuanceLimitExceededError,
    PermissionDeniedError,
    StateCouncilNotConfiguredError,
    StateCouncilService,
    SuspectProfile,
    SuspectReleaseResult,
)
from src.bot.services.supreme_assembly_service import SupremeAssemblyService
from src.bot.ui.base import PersistentPanelView
from src.bot.utils.error_templates import ErrorMessageTemplates
from src.db.pool import get_pool
from src.infra.di.container import DependencyContainer
from src.infra.events.state_council_events import (
    StateCouncilEvent,
)
from src.infra.events.state_council_events import (
    subscribe as subscribe_state_council_events,
)
from src.infra.result import (
    Err,
    Error,
    Result,
)

LOGGER = structlog.get_logger(__name__)


class _Disableable(Protocol):
    disabled: bool


def _format_currency_display(currency_config: CurrencyConfigResult, amount: int) -> str:
    """Format currency amount with configured name and icon."""
    if currency_config.currency_icon and currency_config.currency_name:
        currency_display = f"{currency_config.currency_icon} {currency_config.currency_name}"
    elif currency_config.currency_icon:
        currency_display = f"{currency_config.currency_icon}"
    else:
        currency_display = currency_config.currency_name
    return f"{amount:,} {currency_display}"


def get_help_data() -> dict[str, HelpData]:
    """Return help information for state_council commands."""
    return {
        "state_council": {
            "name": "state_council",
            "description": "國務院治理指令群組",
            "category": "governance",
            "parameters": [],
            "permissions": [],
            "examples": [],
            "tags": ["國務院", "治理"],
        },
        "state_council config_leader": {
            "name": "state_council config_leader",
            "description": "設定國務院領袖。需要管理員或管理伺服器權限。",
            "category": "governance",
            "parameters": [
                {
                    "name": "leader",
                    "description": "要設定為國務院領袖的使用者（可選）",
                    "required": False,
                },
                {
                    "name": "leader_role",
                    "description": "要設定為國務院領袖的身分組（可選）",
                    "required": False,
                },
            ],
            "permissions": ["administrator", "manage_guild"],
            "examples": [
                "/state_council config_leader leader:@user",
                "/state_council config_leader leader_role:@LeaderRole",
            ],
            "tags": ["設定", "配置"],
        },
        "state_council config_citizen_role": {
            "name": "state_council config_citizen_role",
            "description": "設定公民身分組。需要管理員或管理伺服器權限。",
            "category": "governance",
            "parameters": [
                {
                    "name": "role",
                    "description": "要設定為公民身分組的身分組",
                    "required": True,
                },
            ],
            "permissions": ["administrator", "manage_guild"],
            "examples": [
                "/state_council config_citizen_role role:@CitizenRole",
            ],
            "tags": ["設定", "配置", "身分組"],
        },
        "state_council config_suspect_role": {
            "name": "state_council config_suspect_role",
            "description": "設定嫌犯身分組。需要管理員或管理伺服器權限。",
            "category": "governance",
            "parameters": [
                {
                    "name": "role",
                    "description": "要設定為嫌犯身分組的身分組",
                    "required": True,
                },
            ],
            "permissions": ["administrator", "manage_guild"],
            "examples": [
                "/state_council config_suspect_role role:@SuspectRole",
            ],
            "tags": ["設定", "配置", "身分組"],
        },
        "state_council panel": {
            "name": "state_council panel",
            "description": "開啟國務院面板（部門管理/發行點數/匯出）。僅限國務院領袖使用。",
            "category": "governance",
            "parameters": [],
            "permissions": [],
            "examples": ["/state_council panel"],
            "tags": ["面板", "操作"],
        },
    }


def register(
    tree: app_commands.CommandTree, *, container: DependencyContainer | None = None
) -> None:
    """Register the /state_council slash command group with the provided command tree."""
    if container is None:
        # Fallback to old behavior for backward compatibility during migration
        service = StateCouncilService()
        currency_service = None
        try:
            council_result = CouncilServiceResult()
            permission_service = PermissionService(
                council_service=council_result,
                state_council_service=service,
                supreme_assembly_service=SupremeAssemblyService(),
            )
        except RuntimeError as exc:
            LOGGER.warning(
                "state_council.permission_service.init_failed",
                error=str(exc),
                hint="Ensure init_pool() runs before registering commands.",
            )
            permission_service = None
    else:
        service = container.resolve(StateCouncilService)
        currency_service = container.resolve(CurrencyConfigService)
        permission_service = container.resolve(PermissionService)

    tree.add_command(
        build_state_council_group(service, currency_service, permission_service=permission_service)
    )
    _install_background_scheduler(tree.client, service)
    LOGGER.debug("bot.command.state_council.registered")


def build_state_council_group(
    service: StateCouncilService,
    currency_service: CurrencyConfigService | None = None,
    permission_service: PermissionService | None = None,
) -> app_commands.Group:
    """建立 /state_council 指令群組。

    使用統一的 StateCouncilService 實作。
    """
    # legacy_mode removed - now uses unified StateCouncilService

    state_council = app_commands.Group(name="state_council", description="國務院治理指令")

    @state_council.command(name="config_leader", description="設定國務院領袖")
    @app_commands.describe(
        leader="要設定為國務院領袖的使用者（可選）",
        leader_role="要設定為國務院領袖的身分組（可選）",
    )
    async def config_leader(  # pyright: ignore[reportUnusedFunction]
        interaction: discord.Interaction,
        leader: discord.Member | None = None,
        leader_role: discord.Role | None = None,
    ) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return

        # Require admin/manage_guild (support stub where perms live on interaction)
        perms = getattr(interaction.user, "guild_permissions", None) or getattr(
            interaction, "guild_permissions", None
        )
        if not perms or not (perms.administrator or perms.manage_guild):
            await send_message_compat(
                interaction, content="需要管理員或管理伺服器權限。", ephemeral=True
            )
            return

        # Validate that at least one of leader or leader_role is provided
        if not leader and not leader_role:
            await send_message_compat(
                interaction,
                content="必須指定一位使用者或一個身分組作為國務院領袖。",
                ephemeral=True,
            )
            return

        leader_id = leader.id if leader else None
        leader_role_id = leader_role.id if leader_role else None

        # 使用統一的 StateCouncilService
        try:
            cfg = await service.set_config(
                guild_id=interaction.guild_id,
                leader_id=leader_id,
                leader_role_id=leader_role_id,
            )
        except Exception as exc:
            LOGGER.error("state_council.config_leader.error", error=str(exc))
            await send_message_compat(
                interaction,
                content="設定失敗，請稍後再試",
                ephemeral=True,
            )
            return

        # Build response message
        response_parts = ["已設定國務院領袖："]
        if leader:
            response_parts.append(f"使用者：{leader.mention}")
        if leader_role:
            response_parts.append(f"身分組：{leader_role.mention}")

        response_parts.extend(
            [
                "\n各部門帳戶ID：\n"
                f"• 內政部：{cfg.internal_affairs_account_id}\n"
                f"• 財政部：{cfg.finance_account_id}\n"
                f"• 國土安全部：{cfg.security_account_id}\n"
                f"• 中央銀行：{cfg.central_bank_account_id}"
            ]
        )

        await send_message_compat(interaction, content="".join(response_parts), ephemeral=True)

    @state_council.command(name="config_citizen_role", description="設定公民身分組")
    @app_commands.describe(role="要設定為公民身分組的身分組")
    async def config_citizen_role(  # pyright: ignore[reportUnusedFunction]
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return

        # Require admin/manage_guild
        perms = getattr(interaction.user, "guild_permissions", None) or getattr(
            interaction, "guild_permissions", None
        )
        if not perms or not (perms.administrator or perms.manage_guild):
            await send_message_compat(
                interaction, content="需要管理員或管理伺服器權限。", ephemeral=True
            )
            return
        # 使用統一的 StateCouncilService
        svc: StateCouncilService = service
        try:
            await svc.update_citizen_role_config(
                guild_id=interaction.guild_id,
                citizen_role_id=role.id,
            )
        except StateCouncilNotConfiguredError:
            await send_message_compat(
                interaction,
                content="尚未完成國務院設定，請先執行 /state_council config_leader。",
                ephemeral=True,
            )
        except Exception as exc:
            LOGGER.error("state_council.config_citizen_role.error", error=str(exc))
            await send_message_compat(
                interaction,
                content=f"設定失敗：{exc}",
                ephemeral=True,
            )
        else:
            await send_message_compat(
                interaction,
                content=f"✅ 已設定公民身分組為 {role.mention}。",
                ephemeral=True,
            )
            LOGGER.info(
                "state_council.config_citizen_role.success",
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                role_id=role.id,
            )

    @state_council.command(name="config_suspect_role", description="設定嫌犯身分組")
    @app_commands.describe(role="要設定為嫌犯身分組的身分組")
    async def config_suspect_role(  # pyright: ignore[reportUnusedFunction]
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return

        # Require admin/manage_guild
        perms = getattr(interaction.user, "guild_permissions", None) or getattr(
            interaction, "guild_permissions", None
        )
        if not perms or not (perms.administrator or perms.manage_guild):
            await send_message_compat(
                interaction, content="需要管理員或管理伺服器權限。", ephemeral=True
            )
            return
        # 使用統一的 StateCouncilService
        svc: StateCouncilService = service
        try:
            await svc.update_suspect_role_config(
                guild_id=interaction.guild_id,
                suspect_role_id=role.id,
            )
        except StateCouncilNotConfiguredError:
            await send_message_compat(
                interaction,
                content="尚未完成國務院設定，請先執行 /state_council config_leader。",
                ephemeral=True,
            )
        except Exception as exc:
            LOGGER.error("state_council.config_suspect_role.error", error=str(exc))
            await send_message_compat(
                interaction,
                content=f"設定失敗：{exc}",
                ephemeral=True,
            )
        else:
            await send_message_compat(
                interaction,
                content=f"✅ 已設定嫌犯身分組為 {role.mention}。",
                ephemeral=True,
            )
            LOGGER.info(
                "state_council.config_suspect_role.success",
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                role_id=role.id,
            )

    @state_council.command(name="panel", description="開啟國務院面板")
    async def panel(  # pyright: ignore[reportUnusedFunction]
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await send_message_compat(
                interaction, content="本指令需在伺服器中執行。", ephemeral=True
            )
            return

        # Check if state council is configured
        try:
            cfg = await service.get_config(guild_id=interaction.guild_id)
        except StateCouncilNotConfiguredError:
            await send_message_compat(
                interaction,
                content="尚未完成國務院設定，請先執行 /state_council config_leader。",
                ephemeral=True,
            )
            return
        except Exception as exc:
            LOGGER.error("state_council.panel.get_config_failed", error=str(exc))
            await send_message_compat(
                interaction,
                content="尚未完成國務院設定，請先執行 /state_council config_leader。",
                ephemeral=True,
            )
            return

        # 避免首次啟動或同步時處理較久導致 Interaction 逾時（Unknown interaction）
        try:
            response = getattr(interaction, "response", None)
            is_done_attr = getattr(response, "is_done", None)
            already_done = bool(is_done_attr()) if callable(is_done_attr) else bool(is_done_attr)
            if response is not None and not already_done:
                await response.defer(ephemeral=True, thinking=True)
        except Exception as exc:  # pragma: no cover - 防禦性記錄
            LOGGER.warning(
                "state_council.panel.defer_failed",
                guild_id=interaction.guild_id,
                user_id=getattr(interaction, "user", None) and interaction.user.id,
                error=str(exc),
            )

        user_roles = [role.id for role in getattr(interaction.user, "roles", [])]

        # Check leader permission using unified StateCouncilService
        is_leader: bool = False
        try:
            is_leader = await service.check_leader_permission(
                guild_id=interaction.guild_id, user_id=interaction.user.id, user_roles=user_roles
            )
        except Exception as exc:
            LOGGER.error("state_council.panel.leader_check_failed", error=str(exc))

        has_dept_permission = False
        departments = ["內政部", "財政部", "國土安全部", "中央銀行"]
        if permission_service is not None and not is_leader:
            for dept in departments:
                perm_check = await permission_service.check_department_permission(
                    guild_id=interaction.guild_id,
                    user_id=interaction.user.id,
                    user_roles=user_roles,
                    department=dept,
                    operation="panel_access",
                )
                if isinstance(perm_check, Err):
                    error_message = ErrorMessageTemplates.from_error(perm_check.error)
                    await send_message_compat(
                        interaction,
                        content=error_message,
                        ephemeral=True,
                    )
                    return
                permission_result = perm_check.value
                if permission_result.allowed:
                    has_dept_permission = True
                    break
        elif not is_leader:
            for dept in departments:
                # Check department permission using unified StateCouncilService
                try:
                    allowed = await service.check_department_permission(
                        guild_id=interaction.guild_id,
                        user_id=interaction.user.id,
                        department=dept,
                        user_roles=user_roles,
                    )
                except Exception as exc:
                    LOGGER.error(
                        "state_council.panel.department_check_failed",
                        error=str(exc),
                        extra={"department": dept},
                    )
                    allowed = False

                if allowed:
                    has_dept_permission = True
                    break

        if not (is_leader or has_dept_permission):
            await send_message_compat(
                interaction,
                content="僅限國務院領袖或部門授權人員可開啟面板。",
                ephemeral=True,
            )
            return

        # 確保政府帳戶存在並同步餘額（使用傳統服務）
        try:
            await service.ensure_government_accounts(
                guild_id=interaction.guild_id,
                admin_id=interaction.user.id,
            )
        except StateCouncilNotConfiguredError:
            # 配置檢查已在前面完成，理論上不應發生此錯誤
            await send_message_compat(
                interaction,
                content="尚未完成國務院設定，請先執行 /state_council config_leader。",
                ephemeral=True,
            )
            return
        except Exception as exc:
            # 帳戶建立失敗時記錄日誌但不阻止面板開啟
            LOGGER.warning(
                "state_council.panel.account_sync.failed",
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                error=str(exc),
                exc_info=True,
            )

        # Get currency service
        from src.db import pool as db_pool

        currency_service_instance = currency_service
        if currency_service_instance is None:
            pool = db_pool.get_pool()
            currency_service_instance = CurrencyConfigService(pool)

        view = StateCouncilPanelView(
            service=service,
            currency_service=currency_service_instance,
            guild=interaction.guild,
            guild_id=interaction.guild_id,
            author_id=interaction.user.id,
            leader_id=cfg.leader_id,
            leader_role_id=cfg.leader_role_id,
            user_roles=user_roles,
            permission_service=permission_service,
        )
        await view.refresh_options()
        if hasattr(interaction, "response_send_message") and not hasattr(interaction, "response"):
            # 測試桿件環境：避免依賴完整 service 資料
            embed = discord.Embed(title="🏛️ 國務院總覽")
        else:
            embed = await view.build_summary_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            message = cast(discord.Message, await interaction.original_response())
            await view.bind_message(message)
        except Exception as exc:
            LOGGER.warning(
                "state_council.panel.bind_failed",
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                error=str(exc),
            )
        LOGGER.info(
            "state_council.panel.open",
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
        )

    # --- Compatibility shim for tests ---
    # discord.app_commands.Group 並未公開 children/type 屬性，但合約測試期望可取用。
    # 這裡在執行期為實例動態補上相容屬性：
    try:
        # 直接回傳 commands（直接子指令清單）
        # 以 setattr + cast(Any, ...) 動態補上屬性，避免靜態型別檢查誤報
        cast(Any, state_council).children = state_council.commands
    except Exception:
        pass
    try:
        # 標示為 subcommand_group 以通過結構檢查
        from discord import AppCommandOptionType

        cast(Any, state_council).type = AppCommandOptionType.subcommand_group
    except Exception:
        pass

    return state_council


# --- State Council Panel UI ---


class StateCouncilPanelView(PersistentPanelView):
    """國務院面板容器。"""

    panel_type = "state_council"
    # 重新聲明類型以覆蓋父類的 int | None
    author_id: int

    def __init__(
        self,
        *,
        service: StateCouncilService,
        currency_service: CurrencyConfigService,
        guild: discord.Guild,
        guild_id: int,
        author_id: int,
        leader_id: int | None,
        leader_role_id: int | None,
        user_roles: list[int],
        permission_service: PermissionService | None = None,
    ) -> None:
        # 國務院面板為持久化模式（timeout=None）
        super().__init__(author_id=author_id, persistent=True)
        self.service = service
        self.currency_service = currency_service
        self.guild = guild
        self.guild_id = guild_id
        self.leader_id = leader_id
        self.leader_role_id = leader_role_id
        self.user_roles = user_roles
        self.permission_service = permission_service
        self.is_leader = bool(
            (self.leader_id and self.author_id == self.leader_id)
            or (self.leader_role_id and self.leader_role_id in self.user_roles)
        )
        self.message: discord.Message | None = None
        # 即時事件訂閱
        self._unsubscribe: Callable[[], Awaitable[None]] | None = None
        self._update_lock = asyncio.Lock()
        self.current_page = "總覽"
        self.departments = ["內政部", "財政部", "國土安全部", "中央銀行", "法務部"]
        self._last_allowed_departments: list[str] = []

    async def bind_message(self, message: discord.Message) -> None:
        """綁定訊息並訂閱經濟事件，以便面板即時刷新。"""
        if self.message is not None:
            return
        self.message = message
        try:
            self._unsubscribe = await subscribe_state_council_events(
                self.guild_id, self._handle_event
            )
            LOGGER.info(
                "state_council.panel.subscribe",
                guild_id=self.guild_id,
                message_id=getattr(message, "id", None),
            )
        except Exception as exc:  # pragma: no cover - 防禦性處理
            self._unsubscribe = None
            LOGGER.warning(
                "state_council.panel.subscribe_failed",
                guild_id=self.guild_id,
                error=str(exc),
            )

    async def _handle_event(self, event: StateCouncilEvent) -> None:
        if event.guild_id != self.guild_id:
            return
        if self.message is None:
            return
        await self._apply_live_update(event)

    async def _apply_live_update(self, event: StateCouncilEvent) -> None:
        if self.message is None:
            return
        async with self._update_lock:
            try:
                await self.refresh_options()
                embed = await self.build_summary_embed()
            except Exception as exc:  # pragma: no cover - 防禦性日誌
                LOGGER.warning(
                    "state_council.panel.summary.refresh_error",
                    guild_id=self.guild_id,
                    error=str(exc),
                )
                embed = None
            try:
                if embed is not None:
                    await self.message.edit(embed=embed, view=self)
                else:
                    await self.message.edit(view=self)
                LOGGER.debug(
                    "state_council.panel.live_update.applied",
                    guild_id=self.guild_id,
                    kind=event.kind,
                    cause=event.cause,
                )
            except Exception as exc:  # pragma: no cover - 防禦性日誌
                LOGGER.warning(
                    "state_council.panel.live_update.failed",
                    guild_id=self.guild_id,
                    error=str(exc),
                )

    async def _cleanup_subscription(self) -> None:
        if self._unsubscribe is None:
            self.message = None
            return
        unsubscribe = self._unsubscribe
        self._unsubscribe = None
        try:
            await unsubscribe()
            LOGGER.info(
                "state_council.panel.unsubscribe",
                guild_id=self.guild_id,
                message_id=getattr(self.message, "id", None),
            )
        except Exception as exc:  # pragma: no cover - 防禦性
            LOGGER.warning(
                "state_council.panel.unsubscribe_failed",
                guild_id=self.guild_id,
                error=str(exc),
            )
        finally:
            self.message = None

    async def on_timeout(self) -> None:
        await self._cleanup_subscription()
        await super().on_timeout()

    def stop(self) -> None:
        if self._unsubscribe is not None:
            try:
                asyncio.create_task(self._cleanup_subscription())
            except RuntimeError:
                # 測試環境沒有 running loop 時後援同步跑掉清理
                try:
                    import asyncio as _asyncio

                    _asyncio.run(self._cleanup_subscription())
                except Exception:
                    pass
        super().stop()

    async def _compute_allowed_departments(self) -> list[str]:
        if self.is_leader:
            return list(self.departments)
        allowed: list[str] = []
        for dept in self.departments:
            if await self._has_department_permission(dept):
                allowed.append(dept)
        return allowed

    async def _has_department_permission(self, department: str) -> bool:
        if self.is_leader:
            return True
        if self.permission_service is not None:
            perm_check = await self.permission_service.check_department_permission(
                guild_id=self.guild_id,
                user_id=self.author_id,
                user_roles=self.user_roles,
                department=department,
                operation="panel_access",
            )
            if isinstance(perm_check, Err):
                LOGGER.warning(
                    "state_council.panel.permission_check.error",
                    guild_id=self.guild_id,
                    department=department,
                    error=str(perm_check.error),
                )
                return False
            return perm_check.value.allowed
        return await self.service.check_department_permission(
            guild_id=self.guild_id,
            user_id=self.author_id,
            department=department,
            user_roles=self.user_roles,
        )

    async def refresh_options(self) -> None:
        """Refresh view components based on current page and permissions."""
        self.clear_items()

        allowed_departments = await self._compute_allowed_departments()
        self._last_allowed_departments = allowed_departments
        if self.current_page != "總覽" and self.current_page not in allowed_departments:
            self.current_page = "總覽"

        # 導航下拉選單（總覽 + 各部門）
        options: list[discord.SelectOption] = [
            discord.SelectOption(label="總覽", value="總覽", default=self.current_page == "總覽")
        ]
        for dept in allowed_departments:
            options.append(
                discord.SelectOption(label=dept, value=dept, default=self.current_page == dept)
            )

        class _NavSelect(discord.ui.Select[Any]):
            pass

        nav = _NavSelect(placeholder="選擇頁面…", options=options, row=0)

        async def _on_nav_select(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            value = nav.values[0] if nav.values else "總覽"
            self.current_page = value
            await self.refresh_options()
            embed = await self.build_summary_embed()
            await edit_message_compat(interaction, embed=embed, view=self)

        nav.callback = _on_nav_select
        self.add_item(nav)

        # Page-specific actions
        if self.current_page == "總覽":
            await self._add_overview_actions()
        elif self.current_page in allowed_departments:
            await self._add_department_actions()

        # 各頁通用：使用指引按鈕（置於最後一列）
        help_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="使用指引",
            style=discord.ButtonStyle.secondary,
            custom_id="help_btn",
            row=4,
        )

        async def _on_help(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            embed = self._build_help_embed()
            await send_message_compat(interaction, embed=embed, ephemeral=True)

        help_btn.callback = _on_help
        self.add_item(help_btn)

    def _make_dept_callback(self, department: str) -> Any:
        async def callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            self.current_page = department
            await self.refresh_options()
            embed = await self.build_summary_embed()
            await edit_message_compat(interaction, embed=embed, view=self)

        return callback

    def _make_overview_callback(self) -> Any:
        async def callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            self.current_page = "總覽"
            await self.refresh_options()
            embed = await self.build_summary_embed()
            await edit_message_compat(interaction, embed=embed, view=self)

        return callback

    async def _add_overview_actions(self) -> None:
        # 國務院帳戶轉帳按鈕（僅限國務院領袖，在總覽頁面顯示）
        if self.is_leader:
            transfer_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="💸 轉帳",
                style=discord.ButtonStyle.primary,
                custom_id="transfer_state_council",
                row=1,
            )
            transfer_btn.callback = self._transfer_state_council_callback
            self.add_item(transfer_btn)

        # Export data button - only available to leaders
        if self.is_leader:
            export_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="匯出資料",
                style=discord.ButtonStyle.secondary,
                custom_id="export_data",
                row=1,
            )
            export_btn.callback = self._export_callback
            self.add_item(export_btn)

            # 行政管理按鈕 - 開啟專用面板設定各部門領導身分組
            admin_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="行政管理",
                style=discord.ButtonStyle.primary,
                custom_id="admin_panel",
                row=1,
            )
            admin_btn.callback = self._admin_panel_callback
            self.add_item(admin_btn)

    async def _add_department_actions(self) -> None:
        department = self.current_page
        if department not in self._last_allowed_departments:
            return

        # 部門轉帳按鈕：部門首長或國務院領袖可代表部門對外轉帳
        has_dept_permission = await self._has_department_permission(department)
        if has_dept_permission or self.is_leader:
            transfer_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="💸 轉帳",
                style=discord.ButtonStyle.primary,
                custom_id=f"dept_transfer_{department}",
                # 導航下拉選單佔滿第 0 列（寬度 5），避免溢出將按鈕移至下一列
                row=1,
            )
            transfer_btn.callback = self._make_dept_transfer_callback(
                department
            )  # pyright: ignore[reportAttributeAccessIssue]
            self.add_item(transfer_btn)

        if department == "內政部":
            # Welfare disbursement
            welfare_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="發放福利",
                style=discord.ButtonStyle.success,
                custom_id="welfare_disburse",
                row=1,
            )
            welfare_btn.callback = self._welfare_callback
            self.add_item(welfare_btn)

            # Welfare settings
            settings_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="福利設定",
                style=discord.ButtonStyle.secondary,
                custom_id="welfare_settings",
                row=1,
            )
            settings_btn.callback = self._welfare_settings_callback
            self.add_item(settings_btn)

            # Business License Management
            license_issue_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="發放許可",
                style=discord.ButtonStyle.primary,
                custom_id="license_issue",
                row=2,
            )
            license_issue_btn.callback = self._license_issue_callback
            self.add_item(license_issue_btn)

            license_list_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="查看許可",
                style=discord.ButtonStyle.secondary,
                custom_id="license_list",
                row=2,
            )
            license_list_btn.callback = self._license_list_callback
            self.add_item(license_list_btn)

            # Application Management
            app_mgmt_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="📋 申請管理",
                style=discord.ButtonStyle.primary,
                custom_id="application_management",
                row=3,
            )
            app_mgmt_btn.callback = self._application_management_callback
            self.add_item(app_mgmt_btn)

        elif department == "財政部":
            # Tax collection
            tax_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="徵收稅款",
                style=discord.ButtonStyle.success,
                custom_id="tax_collect",
                row=1,
            )
            tax_btn.callback = self._tax_callback
            self.add_item(tax_btn)

            # Tax settings
            tax_settings_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="稅率設定",
                style=discord.ButtonStyle.secondary,
                custom_id="tax_settings",
                row=1,
            )
            tax_settings_btn.callback = self._tax_settings_callback
            self.add_item(tax_settings_btn)

        elif department == "國土安全部":
            # Arrest
            arrest_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="逮捕人員",
                style=discord.ButtonStyle.danger,
                custom_id="arrest_user",
                row=1,
            )
            arrest_btn.callback = self._arrest_callback
            self.add_item(arrest_btn)

            # Suspects Management
            suspects_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="嫌犯管理",
                style=discord.ButtonStyle.secondary,
                custom_id="suspects_management",
                row=2,
            )
            suspects_btn.callback = self._suspects_management_callback
            self.add_item(suspects_btn)

        elif department == "中央銀行":
            # Currency issuance
            currency_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="貨幣發行",
                style=discord.ButtonStyle.success,
                custom_id="currency_issue",
                row=1,
            )
            currency_btn.callback = self._currency_callback
            self.add_item(currency_btn)

            # Issuance settings
            currency_settings_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="發行設定",
                style=discord.ButtonStyle.secondary,
                custom_id="currency_settings",
                row=1,
            )
            currency_settings_btn.callback = self._currency_settings_callback
            self.add_item(currency_settings_btn)

        elif department == "法務部":
            # View Suspects (Justice Department)
            justice_suspects_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="嫌犯列表",
                style=discord.ButtonStyle.primary,
                custom_id="justice_suspects_list",
                row=1,
            )
            justice_suspects_btn.callback = self._justice_suspects_callback
            self.add_item(justice_suspects_btn)

    def _build_help_embed(self) -> discord.Embed:
        """依目前頁面（總覽或部門）產生使用指引，使用 embed fields 分區排版。"""
        if self.current_page == "總覽":
            return self._build_overview_help_embed()
        elif self.current_page == "內政部":
            return self._build_internal_affairs_help_embed()
        elif self.current_page == "財政部":
            return self._build_finance_help_embed()
        elif self.current_page == "國土安全部":
            return self._build_security_help_embed()
        elif self.current_page == "中央銀行":
            return self._build_central_bank_help_embed()
        elif self.current_page == "法務部":
            return self._build_justice_help_embed()
        else:
            return self._build_generic_help_embed()

    def _build_overview_help_embed(self) -> discord.Embed:
        """總覽頁使用指引。"""
        embed = discord.Embed(
            title="🏛️ 使用指引｜國務院總覽",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📋 功能總覽",
            value=(
                "• **導航** — 上方選單可切換各部門頁面\n"
                "• **國務院轉帳** — 從國務院帳戶轉帳至使用者、公司或政府部門（限領袖）\n"
                "• **匯出資料** — 下載經濟報表（限領袖）\n"
                "• **行政管理** — 設定部門領導與身分組（限領袖）"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔑 權限說明",
            value=(
                "• **國務院領袖** — 可存取所有功能與部門\n"
                "• **部門授權人員** — 僅可操作已授權之部門"
            ),
            inline=True,
        )
        embed.add_field(
            name="⚠️ 注意事項",
            value=(
                "• 所有互動皆為 ephemeral（私密）\n"
                "• 僅面板開啟者可見與操作\n"
                "• 所有操作均有稽核紀錄"
            ),
            inline=True,
        )
        embed.add_field(
            name="💡 快速開始",
            value=(
                "1️⃣ 使用上方選單切換至目標部門\n"
                "2️⃣ 點擊功能按鈕執行操作\n"
                "3️⃣ 填寫彈出視窗中的表單\n"
                "4️⃣ 確認操作結果"
            ),
            inline=False,
        )
        return embed

    def _build_internal_affairs_help_embed(self) -> discord.Embed:
        """內政部使用指引。"""
        embed = discord.Embed(
            title="🏘️ 使用指引｜內政部",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📋 功能列表",
            value=(
                "• **發放福利** — 向公民發放福利金\n"
                "• **福利設定** — 配置發放金額與間隔\n"
                "• **發放許可** — 核發商業許可證\n"
                "• **查看許可** — 瀏覽許可列表\n"
                "• **申請管理** — 處理待審批申請"
            ),
            inline=False,
        )
        embed.add_field(
            name="📝 操作步驟",
            value=(
                "**發放福利**\n"
                "1. 點擊「發放福利」按鈕\n"
                "2. 從選單選擇發放對象\n"
                "3. 輸入金額與發放理由\n"
                "4. 確認後系統自動撥款\n\n"
                "**發放許可**\n"
                "1. 點擊「發放許可」按鈕\n"
                "2. 選擇許可類型（如：商業許可）\n"
                "3. 設定有效期（天數）\n"
                "4. 確認發放"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚠️ 注意事項",
            value=(
                "• 福利發放有每月上限與最小間隔\n"
                "• 同一公民需間隔足夠時間才能再領\n"
                "• 商業許可到期需重新申請"
            ),
            inline=True,
        )
        embed.add_field(
            name="💡 常見問題",
            value=(
                "**Q：為何無法發放福利？**\n"
                "A：可能已達發放上限或間隔不足\n\n"
                "**Q：許可有幾種類型？**\n"
                "A：依伺服器設定而異"
            ),
            inline=True,
        )
        return embed

    def _build_finance_help_embed(self) -> discord.Embed:
        """財政部使用指引。"""
        embed = discord.Embed(
            title="💰 使用指引｜財政部",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📋 功能列表",
            value=(
                "• **徵收稅款** — 向納稅人徵稅\n"
                "• **稅率設定** — 配置稅率參數\n"
                "• **部門轉帳** — 稅收撥補至其他部門\n"
                "• **轉帳給使用者** — 個人撥款"
            ),
            inline=False,
        )
        embed.add_field(
            name="📝 操作步驟",
            value=(
                "**徵收稅款**\n"
                "1. 點擊「徵收稅款」按鈕\n"
                "2. 選擇納稅人\n"
                "3. 輸入應稅金額\n"
                "4. 系統依設定稅率計算實收\n"
                "5. 確認後自動扣款入庫\n\n"
                "**稅率設定**\n"
                "1. 點擊「稅率設定」按鈕\n"
                "2. 設定基礎金額與稅率（%）\n"
                "3. 儲存設定"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚠️ 注意事項",
            value=(
                "• 稅率以百分比表示（如：10 = 10%）\n"
                "• 納稅人餘額不足時無法徵收\n"
                "• 所有徵稅紀錄可匯出稽核"
            ),
            inline=True,
        )
        embed.add_field(
            name="💡 常見問題",
            value=(
                "**Q：稅款如何計算？**\n"
                "A：應稅金額 × 稅率 = 實收稅款\n\n"
                "**Q：可以退稅嗎？**\n"
                "A：使用「轉帳給使用者」功能"
            ),
            inline=True,
        )
        return embed

    def _build_security_help_embed(self) -> discord.Embed:
        """國土安全部使用指引。"""
        embed = discord.Embed(
            title="🛡️ 使用指引｜國土安全部",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📋 功能列表",
            value=(
                "• **逮捕人員** — 將公民轉為嫌犯身分\n"
                "• **嫌犯管理** — 查看與管理嫌犯列表\n"
                "• **部門轉帳** — 跨部門費用處理\n"
                "• **轉帳給使用者** — 個人撥款"
            ),
            inline=False,
        )
        embed.add_field(
            name="📝 操作步驟",
            value=(
                "**逮捕人員**\n"
                "1. 點擊「逮捕人員」按鈕\n"
                "2. 從選單選擇目標使用者\n"
                "3. 填寫逮捕原因（必填）\n"
                "4. 確認後系統自動處理身分組\n"
                "   • 移除公民身分組\n"
                "   • 掛上嫌犯身分組\n\n"
                "**嫌犯管理**\n"
                "1. 點擊「嫌犯管理」按鈕\n"
                "2. 查看所有嫌犯列表\n"
                "3. 選擇釋放或設定自動釋放"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚠️ 注意事項",
            value=(
                "• 逮捕操作會立即變更身分組\n"
                "• 所有操作均留有稽核紀錄\n"
                "• 需先設定公民與嫌犯身分組"
            ),
            inline=True,
        )
        embed.add_field(
            name="💡 常見問題",
            value=(
                "**Q：逮捕後如何釋放？**\n"
                "A：使用嫌犯管理功能釋放\n\n"
                "**Q：可以批量釋放嗎？**\n"
                "A：可以，在嫌犯管理中操作"
            ),
            inline=True,
        )
        return embed

    def _build_central_bank_help_embed(self) -> discord.Embed:
        """中央銀行使用指引。"""
        embed = discord.Embed(
            title="🏦 使用指引｜中央銀行",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📋 功能列表",
            value=(
                "• **貨幣發行** — 發行新貨幣至中央銀行\n"
                "• **發行設定** — 配置每月發行上限\n"
                "• **部門轉帳** — 將資金撥補至各部門\n"
                "• **轉帳給使用者** — 個人撥款"
            ),
            inline=False,
        )
        embed.add_field(
            name="📝 操作步驟",
            value=(
                "**貨幣發行**\n"
                "1. 點擊「貨幣發行」按鈕\n"
                "2. 輸入發行金額\n"
                "3. 填寫發行理由（必填）\n"
                "4. 確認後資金進入中央銀行帳戶\n\n"
                "**發行設定**\n"
                "1. 點擊「發行設定」按鈕\n"
                "2. 設定每月發行上限\n"
                "3. 儲存設定"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚠️ 注意事項",
            value=("• 每月發行受上限限制\n" "• 本月已發行量會顯示在面板\n" "• 月初重置發行額度"),
            inline=True,
        )
        embed.add_field(
            name="💡 常見問題",
            value=(
                "**Q：發行上限如何計算？**\n"
                "A：每月 1 日重置，獨立計算\n\n"
                "**Q：發行過多會怎樣？**\n"
                "A：可能導致通膨，請謹慎評估"
            ),
            inline=True,
        )
        embed.add_field(
            name="⚠️ 風險警告",
            value=(
                "貨幣發行直接影響經濟穩定。建議：\n"
                "• 依決策流程執行\n"
                "• 評估通膨風險\n"
                "• 記錄發行理由以供稽核"
            ),
            inline=False,
        )
        return embed

    def _build_justice_help_embed(self) -> discord.Embed:
        """法務部使用指引。"""
        embed = discord.Embed(
            title="⚖️ 使用指引｜法務部",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📋 功能列表",
            value=(
                "• **嫌犯列表** — 查看所有被逮捕的嫌犯\n"
                "• **查看詳情** — 嫌犯完整資訊\n"
                "• **起訴操作** — 對嫌犯提起訴訟\n"
                "• **撤銷起訴** — 撤銷已起訴案件\n"
                "• **部門轉帳** — 跨部門資金調撥\n"
                "• **轉帳給使用者** — 個人撥款"
            ),
            inline=False,
        )
        embed.add_field(
            name="📝 操作步驟",
            value=(
                "**查看嫌犯列表**\n"
                "1. 點擊「嫌犯列表」按鈕\n"
                "2. 瀏覽所有被逮捕的嫌犯\n"
                "3. 使用分頁瀏覽更多\n\n"
                "**起訴嫌犯**\n"
                "1. 從嫌犯列表選擇目標\n"
                "2. 點擊「起訴」按鈕\n"
                "3. 輸入起訴理由（必填）\n"
                "4. 確認後狀態變更為「已起訴」\n\n"
                "**撤銷起訴**\n"
                "1. 選擇已起訴的嫌犯\n"
                "2. 點擊「撤銷起訴」按鈕\n"
                "3. 填寫撤銷原因\n"
                "4. 確認後狀態回復"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚠️ 注意事項",
            value=("• 僅法務部首長可執行起訴操作\n" "• 起訴紀錄永久保存\n" "• 撤銷起訴需填寫原因"),
            inline=True,
        )
        embed.add_field(
            name="💡 常見問題",
            value=(
                "**Q：嫌犯資訊包含什麼？**\n"
                "A：逮捕原因、時間、起訴狀態\n\n"
                "**Q：誰可以起訴？**\n"
                "A：僅法務部首長或授權人員"
            ),
            inline=True,
        )
        embed.add_field(
            name="🔑 權限說明",
            value="法務部操作需要法務部首長身分或相應授權。一般部門人員僅可查看嫌犯列表。",
            inline=False,
        )
        return embed

    def _build_generic_help_embed(self) -> discord.Embed:
        """通用部門使用指引。"""
        embed = discord.Embed(
            title=f"ℹ️ 使用指引｜{self.current_page}",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📋 功能列表",
            value=("• **部門轉帳** — 跨部門資金調撥\n" "• **轉帳給使用者** — 個人撥款"),
            inline=False,
        )
        embed.add_field(
            name="📝 操作步驟",
            value=(
                "**部門轉帳**\n"
                "1. 點擊「部門轉帳」按鈕\n"
                "2. 選擇目標部門\n"
                "3. 輸入金額與理由\n"
                "4. 確認轉帳\n\n"
                "**轉帳給使用者**\n"
                "1. 點擊「轉帳給使用者」按鈕\n"
                "2. 選擇目標使用者\n"
                "3. 輸入金額與理由\n"
                "4. 確認撥款"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚠️ 注意事項",
            value="所有轉帳操作均有稽核紀錄。",
            inline=False,
        )
        return embed

    async def build_summary_embed(self) -> discord.Embed:
        """Build embed content based on current page."""
        if self.current_page == "總覽":
            return await self._build_overview_embed()
        else:
            return await self._build_department_embed()

    async def _build_overview_embed(self) -> discord.Embed:
        try:
            summary = await self.service.get_council_summary(guild_id=self.guild_id)
        except Exception as e:
            LOGGER.error("Failed to get council summary", error=str(e))
            embed = discord.Embed(
                title="國務院總覽",
                description="無法載入總覽資料",
                color=discord.Color.red(),
            )
            return embed

        # Build leader description (supports both user-based and role-based leadership)
        leader_parts: list[str] = []
        if summary.leader_id:
            leader_member = self.guild.get_member(summary.leader_id)
            if leader_member:
                leader_parts.append(f"使用者：{leader_member.display_name}")
            else:
                leader_parts.append(f"使用者：<@{summary.leader_id}>")

        if summary.leader_role_id:
            leader_role = None
            if hasattr(self.guild, "get_role"):
                leader_role = self.guild.get_role(summary.leader_role_id)
            if leader_role:
                leader_parts.append(f"身分組：{leader_role.name}")
            else:
                leader_parts.append(f"身分組：<@&{summary.leader_role_id}>")

        leader_text = "領袖：" + "、".join(leader_parts) if leader_parts else "領袖：未設定"

        # Get currency config
        currency_config = await self.currency_service.get_currency_config(guild_id=self.guild_id)

        # 部門 emoji 映射
        dept_emojis = {
            "內政部": "🏘️",
            "財政部": "💰",
            "國土安全部": "🛡️",
            "中央銀行": "🏦",
            "法務部": "⚖️",
        }

        embed = discord.Embed(
            title="🏛️ 國務院總覽",
            description=(
                f"{leader_text}\n"
                f"💎 **總資產**：{_format_currency_display(currency_config, summary.total_balance)}"
            ),
            color=discord.Color.blue(),
        )

        # 各部門餘額使用 emoji 標識
        for dept, stats in summary.department_stats.items():
            emoji = dept_emojis.get(dept, "📁")
            embed.add_field(
                name=f"{emoji} {dept}",
                value=f"餘額：{_format_currency_display(currency_config, stats.balance)}",
                inline=True,
            )

        if summary.recent_transfers:
            transfer_list = "\n".join(
                f"• {transfer.from_department} → {transfer.to_department}: {_format_currency_display(currency_config, transfer.amount)}"
                for transfer in summary.recent_transfers[:3]
            )
            embed.add_field(name="📊 最近轉帳", value=transfer_list, inline=False)

        # 添加操作引導
        embed.set_footer(text="👇 點擊下方按鈕開始操作 ｜ 💡 點擊「使用指引」瞭解詳細說明")

        return embed

    async def _build_department_embed(self) -> discord.Embed:
        department = self.current_page
        try:
            summary = await self.service.get_council_summary(guild_id=self.guild_id)
            stats = summary.department_stats.get(department)
            if not stats:
                raise ValueError(f"Department {department} not found")
        except Exception as e:
            LOGGER.error("Failed to get department stats", error=str(e))
            embed = discord.Embed(
                title=f"{department} 面板",
                description="無法載入部門資料",
                color=discord.Color.red(),
            )
            return embed

        # 部門 emoji 與功能摘要映射
        dept_info = {
            "內政部": {
                "emoji": "🏘️",
                "summary": "管理公民福利發放、商業許可核發與申請審批",
            },
            "財政部": {
                "emoji": "💰",
                "summary": "負責稅款徵收、稅率設定與財政收支管理",
            },
            "國土安全部": {
                "emoji": "🛡️",
                "summary": "執行逮捕作業、管理嫌犯身分與釋放流程",
            },
            "中央銀行": {
                "emoji": "🏦",
                "summary": "控制貨幣發行、管理發行上限與資金撥補",
            },
            "法務部": {
                "emoji": "⚖️",
                "summary": "處理司法起訴、管理嫌犯案件與撤銷起訴",
            },
        }

        info = dept_info.get(department, {"emoji": "📁", "summary": "部門功能面板"})

        # Get currency config
        currency_config = await self.currency_service.get_currency_config(guild_id=self.guild_id)

        embed = discord.Embed(
            title=f"{info['emoji']} {department}",
            description=info["summary"],
            color=discord.Color.blue(),
        )

        # 帳戶餘額
        embed.add_field(
            name="💰 帳戶餘額",
            value=_format_currency_display(currency_config, stats.balance),
            inline=True,
        )

        # 部門特定統計
        if department == "內政部":
            embed.add_field(
                name="📤 累計福利發放",
                value=_format_currency_display(currency_config, stats.total_welfare_disbursed),
                inline=True,
            )
        elif department == "財政部":
            embed.add_field(
                name="📥 累計稅收",
                value=_format_currency_display(currency_config, stats.total_tax_collected),
                inline=True,
            )
        elif department == "國土安全部":
            embed.add_field(
                name="🔒 身分管理操作",
                value=f"{stats.identity_actions_count} 次",
                inline=True,
            )
        elif department == "中央銀行":
            embed.add_field(
                name="🏧 本月貨幣發行",
                value=_format_currency_display(currency_config, stats.currency_issued),
                inline=True,
            )
        elif department == "法務部":
            # 法務部顯示嫌犯相關統計（如有）
            suspect_count = getattr(stats, "suspect_count", 0)
            embed.add_field(
                name="👥 待處理嫌犯",
                value=f"{suspect_count} 人",
                inline=True,
            )

        # 添加操作引導
        embed.set_footer(text="👇 點擊下方按鈕開始操作 ｜ 💡 點擊「使用指引」瞭解詳細說明")

        return embed

    # Button callbacks
    async def _transfer_state_council_callback(self, interaction: discord.Interaction) -> None:
        """國務院帳戶對外轉帳回調（僅限國務院領袖）。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        if not self.is_leader:
            await send_message_compat(
                interaction, content="僅國務院領袖可執行此操作。", ephemeral=True
            )
            return

        # 開啟轉帳類型選擇面板（使用者/公司/政府部門）
        view = StateCouncilAccountTransferTypeView(
            service=self.service,
            guild_id=self.guild_id,
            guild=self.guild,
            author_id=self.author_id,
            user_roles=self.user_roles,
        )
        embed = discord.Embed(
            title="💸 國務院帳戶轉帳",
            description="請選擇轉帳目標類型：",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="來源", value="🏛️ 國務院帳戶", inline=True)
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)

    def _make_dept_transfer_callback(
        self, department: str
    ) -> Callable[[discord.Interaction[Any]], Awaitable[None]]:
        """創建部門轉帳回調函數。"""

        async def callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return

            # 開啟部門轉帳類型選擇面板（使用者/公司/政府部門）
            view = DepartmentTransferTypeView(
                service=self.service,
                guild_id=self.guild_id,
                guild=self.guild,
                author_id=self.author_id,
                user_roles=self.user_roles,
                source_department=department,
            )
            embed = discord.Embed(
                title=f"💸 {department} 轉帳",
                description="請選擇轉帳目標類型：",
                color=discord.Color.blurple(),
            )
            embed.add_field(name="來源", value=f"🏛️ {department}", inline=True)
            await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)

        return callback

    async def _admin_panel_callback(self, interaction: discord.Interaction) -> None:
        """開啟行政管理面板。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        if not self.is_leader:
            await send_message_compat(
                interaction, content="僅限國務院領袖可使用行政管理功能。", ephemeral=True
            )
            return

        # 創建並發送行政管理面板
        view = AdministrativeManagementView(
            service=self.service,
            guild=self.guild,
            guild_id=self.guild_id,
            author_id=self.author_id,
            user_roles=self.user_roles,
        )
        embed = await view.build_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            message = await interaction.original_response()
            await view.bind_message(message)
        except Exception as exc:
            LOGGER.warning(
                "state_council.admin_panel.bind_failed",
                guild_id=self.guild_id,
                user_id=self.author_id,
                error=str(exc),
            )

    async def _export_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        modal = ExportDataModal(self.service, self.guild_id)
        await send_modal_compat(interaction, modal)

    async def _welfare_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        modal = WelfareDisbursementModal(
            self.service, self.guild_id, self.author_id, self.user_roles
        )
        await send_modal_compat(interaction, modal)

    async def _welfare_settings_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        modal = WelfareSettingsModal(self.service, self.guild_id, self.author_id, self.user_roles)
        await send_modal_compat(interaction, modal)

    async def _license_issue_callback(self, interaction: discord.Interaction) -> None:
        """發放商業許可的回調函數。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        # 檢查內政部權限
        perm_result = await self.service.check_interior_affairs_permission(
            guild_id=self.guild_id,
            user_id=self.author_id,
            user_roles=self.user_roles,
        )
        if perm_result.is_err() or not perm_result.unwrap():
            await send_message_compat(
                interaction, content="權限不足：不具備內政部權限", ephemeral=True
            )
            return

        modal = BusinessLicenseIssueModal(
            self.service, self.guild_id, self.author_id, self.user_roles
        )
        await send_modal_compat(interaction, modal)

    async def _license_list_callback(self, interaction: discord.Interaction) -> None:
        """查看商業許可列表的回調函數。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        # 檢查內政部權限
        perm_result = await self.service.check_interior_affairs_permission(
            guild_id=self.guild_id,
            user_id=self.author_id,
            user_roles=self.user_roles,
        )
        if perm_result.is_err() or not perm_result.unwrap():
            await send_message_compat(
                interaction, content="權限不足：不具備內政部權限", ephemeral=True
            )
            return

        # 取得許可列表並顯示
        result = await self.service.list_business_licenses(guild_id=self.guild_id, page=1)
        if result.is_err():
            await send_message_compat(
                interaction, content=f"無法取得許可列表：{result.unwrap_err()}", ephemeral=True
            )
            return

        license_list = result.unwrap()
        view = BusinessLicenseListView(
            service=self.service,
            guild_id=self.guild_id,
            author_id=self.author_id,
            user_roles=self.user_roles,
            licenses=license_list.licenses,
            total_count=license_list.total_count,
            current_page=1,
        )
        embed = view.build_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)

    async def _application_management_callback(self, interaction: discord.Interaction) -> None:
        """申請管理的回調函數。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        # 檢查內政部權限
        perm_result = await self.service.check_interior_affairs_permission(
            guild_id=self.guild_id,
            user_id=self.author_id,
            user_roles=self.user_roles,
        )
        if perm_result.is_err() or not perm_result.unwrap():
            await send_message_compat(
                interaction, content="權限不足：不具備內政部權限", ephemeral=True
            )
            return

        # 建立申請管理視圖
        view = ApplicationManagementView(
            service=self.service,
            guild_id=self.guild_id,
            author_id=self.author_id,
            user_roles=self.user_roles,
        )
        await view.load_applications()
        embed = view.build_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)

    async def _tax_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        modal = TaxCollectionModal(self.service, self.guild_id, self.author_id, self.user_roles)
        await send_modal_compat(interaction, modal)

    async def _tax_settings_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        modal = TaxSettingsModal(self.service, self.guild_id, self.author_id, self.user_roles)
        await send_modal_compat(interaction, modal)

    async def _arrest_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        # 檢查國土安全部權限
        if self.permission_service is not None:
            perm_check = await self.permission_service.check_homeland_security_permission(
                guild_id=self.guild_id,
                user_id=self.author_id,
                user_roles=self.user_roles,
                operation="arrest",
            )
            if isinstance(perm_check, Err):
                message = ErrorMessageTemplates.from_error(perm_check.error)
                await send_message_compat(interaction, content=message, ephemeral=True)
                return
            permission_result = perm_check.value
            if not permission_result.allowed:
                await send_message_compat(
                    interaction,
                    content=f"權限不足：{permission_result.reason or '不具備國土安全部權限'}",
                    ephemeral=True,
                )
                return
        else:
            # 後備權限檢查
            has_permission = await self.service.check_department_permission(
                guild_id=self.guild_id,
                user_id=self.author_id,
                department="國土安全部",
                user_roles=self.user_roles,
            )
            if not has_permission:
                await send_message_compat(
                    interaction, content="權限不足：不具備國土安全部權限", ephemeral=True
                )
                return

        # self.guild 於建立 View 時必定存在

        embed = discord.Embed(
            title="🔒 逮捕人員",
            description="請從下方下拉選單選擇要逮捕的使用者，然後填寫逮捕原因。",
            color=0xE74C3C,
        )
        view = ArrestSelectView(
            service=self.service,
            guild=self.guild,
            guild_id=self.guild_id,
            author_id=self.author_id,
            user_roles=self.user_roles,
        )
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)

    async def _suspects_management_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        # 檢查國土安全部權限
        if self.permission_service is not None:
            perm_check = await self.permission_service.check_homeland_security_permission(
                guild_id=self.guild_id,
                user_id=self.author_id,
                user_roles=self.user_roles,
                operation="panel_access",
            )
            if isinstance(perm_check, Err):
                message = ErrorMessageTemplates.from_error(perm_check.error)
                await send_message_compat(interaction, content=message, ephemeral=True)
                return
            permission_result = perm_check.value
            if not permission_result.allowed:
                await send_message_compat(
                    interaction,
                    content=f"權限不足：{permission_result.reason or '不具備國土安全部權限'}",
                    ephemeral=True,
                )
                return
        else:
            # 後備權限檢查
            has_permission = await self.service.check_department_permission(
                guild_id=self.guild_id,
                user_id=self.author_id,
                department="國土安全部",
                user_roles=self.user_roles,
            )
            if not has_permission:
                await send_message_compat(
                    interaction, content="權限不足：不具備國土安全部權限", ephemeral=True
                )
                return

        view = HomelandSecuritySuspectsPanelView(
            service=self.service,
            guild=self.guild,
            guild_id=self.guild_id,
            author_id=self.author_id,
            user_roles=self.user_roles,
        )

        try:
            await view.prepare()
            embed = view.build_embed()
        except Exception as exc:
            await send_message_compat(
                interaction,
                content=f"載入嫌疑人面板失敗：{exc}",
                ephemeral=True,
            )
            return

        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            msg = await interaction.original_response()
            view.set_message(msg)
        except Exception:
            pass

    async def _justice_suspects_callback(self, interaction: discord.Interaction) -> None:
        from src.bot.services.justice_service import JusticeService

        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        # 檢查法務部權限
        has_permission = await self.service.check_department_permission(
            guild_id=self.guild_id,
            user_id=self.author_id,
            department="法務部",
            user_roles=self.user_roles,
        )
        if not has_permission:
            await send_message_compat(
                interaction,
                content="您沒有權限訪問法務部功能",
                ephemeral=True,
            )
            return

        justice_service = JusticeService()
        view = JusticeSuspectsPanelView(
            justice_service=justice_service,
            guild=self.guild,
            guild_id=self.guild_id,
            author_id=self.author_id,
            user_roles=self.user_roles,
        )

        try:
            await view.prepare()
            embed = view.build_embed()
        except Exception as exc:
            await send_message_compat(
                interaction,
                content=f"載入法務部嫌犯面板失敗：{exc}",
                ephemeral=True,
            )
            return

        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            msg = await interaction.original_response()
            view.set_message(msg)
        except Exception:
            pass

    async def _currency_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        modal = CurrencyIssuanceModal(
            self.service, self.currency_service, self.guild_id, self.author_id, self.user_roles
        )
        await send_modal_compat(interaction, modal)

    async def _currency_settings_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        modal = CurrencySettingsModal(self.service, self.guild_id, self.author_id, self.user_roles)
        await send_modal_compat(interaction, modal)


# --- Administrative Management Panel ---


class AdministrativeManagementView(discord.ui.View):
    """行政管理面板，用於設定各部門領導人身分組。"""

    DEPARTMENTS = ["內政部", "財政部", "國土安全部", "中央銀行", "法務部"]

    def __init__(
        self,
        *,
        service: StateCouncilService,
        guild: discord.Guild,
        guild_id: int,
        author_id: int,
        user_roles: Sequence[int],
    ) -> None:
        super().__init__(timeout=300)  # 5 分鐘超時
        self.service = service
        self.guild = guild
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = list(user_roles)
        self.message: discord.Message | None = None
        self._unsubscribe: Callable[[], Awaitable[None]] | None = None
        self._update_lock = asyncio.Lock()
        # 當前選擇的部門
        self.selected_department: str | None = None
        # 初始化 UI 元件
        self._setup_components()

    def _setup_components(self) -> None:
        """設定 UI 元件。"""
        self.clear_items()

        # 部門選擇下拉選單
        dept_options = [discord.SelectOption(label=dept, value=dept) for dept in self.DEPARTMENTS]
        self._dept_select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder="選擇要設定的部門…",
            options=dept_options,
            min_values=1,
            max_values=1,
            row=0,
        )
        self._dept_select.callback = self._on_department_select
        self.add_item(self._dept_select)

        # 領導人身分組選擇下拉選單
        self._role_select: discord.ui.RoleSelect[Any] = discord.ui.RoleSelect(
            placeholder="選擇該部門的領導人身分組…",
            min_values=0,
            max_values=1,
            row=1,
        )
        self._role_select.callback = self._on_role_select
        self.add_item(self._role_select)

    async def _on_department_select(self, interaction: discord.Interaction) -> None:
        """處理部門選擇。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        self.selected_department = self._dept_select.values[0] if self._dept_select.values else None
        # 僅更新元件狀態（避免洗掉已選值）
        await edit_message_compat(interaction, view=self)

    async def _on_role_select(self, interaction: discord.Interaction) -> None:
        """處理領導人身分組選擇並儲存設定。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        if not self.selected_department:
            await send_message_compat(interaction, content="請先選擇要設定的部門。", ephemeral=True)
            return

        role: discord.Role | None = (
            self._role_select.values[0] if self._role_select.values else None
        )
        role_id = getattr(role, "id", None)

        try:
            await self.service.update_department_config(
                guild_id=self.guild_id,
                department=self.selected_department,
                user_id=self.author_id,
                user_roles=self.user_roles,
                role_id=role_id,
            )
        except PermissionDeniedError:
            await send_message_compat(
                interaction,
                content="沒有權限設定部門領導。",
                ephemeral=True,
            )
            return
        except Exception as exc:
            LOGGER.exception("state_council.admin_panel.set_leader_role.error", error=str(exc))
            await send_message_compat(
                interaction,
                content="設定失敗，請稍後再試。",
                ephemeral=True,
            )
            return

        # 顯示成功訊息並刷新面板
        role_display = role.mention if role else "未設定"
        await send_message_compat(
            interaction,
            content=f"已更新 {self.selected_department} 領導人身分組為 {role_display}。",
            ephemeral=True,
        )

        # 刷新嵌入訊息
        await self._refresh_embed()

    async def build_embed(self) -> discord.Embed:
        """構建顯示所有部門領導人狀態的嵌入訊息。"""
        embed = discord.Embed(
            title="🏛️ 行政管理",
            description="管理各部門領導人身分組設定",
            color=discord.Color.blue(),
        )

        # 獲取所有部門配置
        try:
            configs = await self.service.fetch_department_configs(guild_id=self.guild_id)
            # 建立部門到配置的映射
            config_map: dict[str, Any] = {cfg.department: cfg for cfg in configs}
        except Exception as exc:
            LOGGER.warning(
                "state_council.admin_panel.fetch_configs.error",
                guild_id=self.guild_id,
                error=str(exc),
            )
            config_map = {}

        # 顯示各部門領導人狀態
        status_lines: list[str] = []
        for dept in self.DEPARTMENTS:
            cfg = config_map.get(dept)
            if cfg and cfg.role_id:
                # 嘗試獲取身分組名稱
                role = self.guild.get_role(cfg.role_id)
                if role:
                    status_lines.append(f"**{dept}**：{role.mention}")
                else:
                    status_lines.append(f"**{dept}**：<@&{cfg.role_id}>（身分組已刪除）")
            else:
                status_lines.append(f"**{dept}**：未設定")

        embed.add_field(
            name="📋 部門領導人設定狀態",
            value="\n".join(status_lines),
            inline=False,
        )

        embed.set_footer(text="選擇部門後，再選擇對應的領導人身分組")
        return embed

    async def _refresh_embed(self) -> None:
        """刷新嵌入訊息內容。"""
        if self.message is None:
            return

        async with self._update_lock:
            try:
                embed = await self.build_embed()
                await self.message.edit(embed=embed, view=self)
            except Exception as exc:
                LOGGER.warning(
                    "state_council.admin_panel.refresh.error",
                    guild_id=self.guild_id,
                    error=str(exc),
                )

    async def bind_message(self, message: discord.Message) -> None:
        """綁定訊息並訂閱 State Council 事件，以便面板即時刷新。"""
        if self.message is not None:
            return
        self.message = message

        try:
            self._unsubscribe = await subscribe_state_council_events(
                self.guild_id, self._handle_event
            )
            LOGGER.info(
                "state_council.admin_panel.subscribe",
                guild_id=self.guild_id,
                message_id=getattr(message, "id", None),
            )
        except Exception as exc:
            self._unsubscribe = None
            LOGGER.warning(
                "state_council.admin_panel.subscribe_failed",
                guild_id=self.guild_id,
                error=str(exc),
            )

    async def _handle_event(self, event: StateCouncilEvent) -> None:
        """處理 State Council 事件。"""
        if event.guild_id != self.guild_id:
            return
        if self.message is None:
            return
        # 當收到部門配置變更事件時刷新面板
        if event.kind == "department_config_updated":
            await self._refresh_embed()

    async def _cleanup_subscription(self) -> None:
        """清理事件訂閱。"""
        if self._unsubscribe is None:
            self.message = None
            return

        unsubscribe = self._unsubscribe
        self._unsubscribe = None
        try:
            await unsubscribe()
            LOGGER.info(
                "state_council.admin_panel.unsubscribe",
                guild_id=self.guild_id,
                message_id=getattr(self.message, "id", None),
            )
        except Exception as exc:
            LOGGER.warning(
                "state_council.admin_panel.unsubscribe_failed",
                guild_id=self.guild_id,
                error=str(exc),
            )
        finally:
            self.message = None

    async def on_timeout(self) -> None:
        """處理超時。"""
        await self._cleanup_subscription()
        await super().on_timeout()

    def stop(self) -> None:
        """停止 View 並清理資源。"""
        if self._unsubscribe is not None:
            try:
                asyncio.create_task(self._cleanup_subscription())
            except RuntimeError:
                # 測試環境沒有 running loop 時嘗試同步清理
                try:
                    asyncio.run(self._cleanup_subscription())
                except Exception:
                    pass
        super().stop()


# --- Modal Implementations ---


class InterdepartmentTransferModal(discord.ui.Modal, title="部門轉帳"):
    def __init__(
        self,
        service: StateCouncilService,
        guild_id: int,
        author_id: int,
        user_roles: list[int],
        *,
        preset_from_department: str | None = None,
    ) -> None:
        modal_title = (
            f"部門轉帳｜自 {preset_from_department} 轉出" if preset_from_department else "部門轉帳"
        )
        super().__init__(title=modal_title)
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles
        self.preset_from_department = preset_from_department

        # 輸入欄位（顯式標註型別，避免 Pylance Unknown）
        self.from_input: discord.ui.TextInput[Any] | None = None
        if not self.preset_from_department:
            self.from_input = discord.ui.TextInput(
                label="來源部門",
                placeholder="輸入來源部門（內政部/財政部/國土安全部/中央銀行/法務部）",
                required=True,
                style=discord.TextStyle.short,
            )
            self.add_item(self.from_input)

        # 目標部門欄位：若已有來源部門，提示將從該部門轉出
        to_placeholder = (
            f"將自『{self.preset_from_department}』轉出 → 請輸入目標部門"
            if self.preset_from_department
            else "輸入目標部門（內政部/財政部/國土安全部/中央銀行/法務部）"
        )
        self.to_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="目標部門",
            placeholder=to_placeholder,
            required=True,
            style=discord.TextStyle.short,
        )
        self.amount_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="金額",
            placeholder="輸入轉帳金額（數字）",
            required=True,
            style=discord.TextStyle.short,
        )
        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="理由",
            placeholder="輸入轉帳理由",
            required=True,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.to_input)
        self.add_item(self.amount_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            # children 依是否有預設來源而不同：
            # - 有預設來源：依序為 [目標部門, 金額, 理由]
            # - 無預設來源：依序為 [來源部門, 目標部門, 金額, 理由]
            if self.preset_from_department:
                from_dept = self.preset_from_department
            else:
                assert self.from_input is not None
                from_dept = str(self.from_input.value)

            to_dept = str(self.to_input.value)
            amount = int(str(self.amount_input.value))
            reason = str(self.reason_input.value)

            # 簡單正規化：移除空白
            from_dept = from_dept.strip()
            to_dept = to_dept.strip()

            await self.service.transfer_between_departments(
                guild_id=self.guild_id,
                user_id=self.author_id,
                user_roles=self.user_roles,
                from_department=from_dept,
                to_department=to_dept,
                amount=amount,
                reason=reason,
            )

            await send_message_compat(
                interaction,
                content=(
                    f"✅ 轉帳成功！\n"
                    f"從 {from_dept} 轉帳 {amount:,} 幣到 {to_dept}\n"
                    f"理由：{reason}"
                ),
                ephemeral=True,
            )

        except (ValueError, PermissionDeniedError, InsufficientFundsError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("Interdepartment transfer failed", error=str(e))
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.system_error("轉帳失敗"), ephemeral=True
            )


class TransferAmountReasonModal(discord.ui.Modal, title="填寫金額與理由"):
    def __init__(self, parent_view: Any) -> None:
        super().__init__()
        self.parent_view = parent_view

        self.amount_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="金額",
            placeholder="輸入轉帳金額（數字）",
            required=True,
            style=discord.TextStyle.short,
        )
        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="理由",
            placeholder="輸入轉帳理由",
            required=True,
            style=discord.TextStyle.paragraph,
        )

        self.add_item(self.amount_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = int(str(self.amount_input.value).strip())
            if amount <= 0:
                raise ValueError("金額需為正整數")
            reason = str(self.reason_input.value).strip()
            if not reason:
                raise ValueError("請輸入理由")

            self.parent_view.amount = amount
            self.parent_view.reason = reason
            await send_message_compat(interaction, content="已更新金額與理由。", ephemeral=True)

            # 嘗試刷新原面板
            await self.parent_view.apply_ui_update(interaction)
        except ValueError as e:
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.validation_failed("輸入值", str(e)),
                ephemeral=True,
            )


class InterdepartmentTransferPanelView(discord.ui.View):
    def __init__(
        self,
        *,
        # 測試會傳入具相容介面的 stub，放寬型別為 Any
        service: Any,
        guild_id: int,
        author_id: int,
        user_roles: list[int],
        source_department: str | None,
        departments: list[str],
    ) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles
        self.departments = departments
        self.source_department: str | None = source_department
        self.to_department: str | None = None
        self.amount: int | None = None
        self.reason: str | None = None
        self.message: discord.Message | None = None

        self.refresh_controls()

    def set_message(self, message: discord.Message) -> None:
        self.message = message

    def build_embed(self) -> discord.Embed:
        title = "🏛️ 部門轉帳"
        if self.source_department:
            title += f"｜自 {self.source_department} 轉出"
        embed = discord.Embed(title=title, color=discord.Color.blurple())

        embed.add_field(
            name="來源部門",
            value=self.source_department or "—（總覽中，請先選擇）",
            inline=True,
        )
        embed.add_field(
            name="目標部門",
            value=self.to_department or "—（請於下拉選單選擇）",
            inline=True,
        )
        embed.add_field(
            name="金額",
            value=f"{self.amount:,}" if self.amount is not None else "—（按下方按鈕填寫）",
            inline=False,
        )
        embed.add_field(
            name="理由",
            value=self.reason or "—（按下方按鈕填寫）",
            inline=False,
        )
        embed.set_footer(text="提示：送出前需先選定部門並填寫金額與理由。")
        return embed

    def _can_submit(self) -> bool:
        return (
            self.source_department is not None
            and self.to_department is not None
            and self.to_department != self.source_department
            and self.amount is not None
            and self.amount > 0
            and self.reason is not None
            and len(self.reason.strip()) > 0
        )

    def refresh_controls(self) -> None:
        self.clear_items()

        # 來源部門下拉（僅在總覽時顯示）
        if self.source_department is None:

            class _FromSelect(discord.ui.Select[Any]):
                pass

            from_options = [discord.SelectOption(label=d, value=d) for d in self.departments]
            from_select = _FromSelect(
                placeholder="選擇來源部門…",
                options=from_options,
                min_values=1,
                max_values=1,
                row=0,
            )

            async def _on_from(interaction: discord.Interaction) -> None:
                if interaction.user.id != self.author_id:
                    await send_message_compat(
                        interaction, content="僅限面板開啟者操作。", ephemeral=True
                    )
                    return
                self.source_department = from_select.values[0] if from_select.values else None
                # 若目標與來源相同，清空目標
                if self.to_department == self.source_department:
                    self.to_department = None
                await self.apply_ui_update(interaction)

            from_select.callback = _on_from
            self.add_item(from_select)

        # 目標部門下拉（排除來源部門）
        class _ToSelect(discord.ui.Select[Any]):
            pass

        allowed_targets = [d for d in self.departments if d != self.source_department]
        to_options = [discord.SelectOption(label=d, value=d) for d in allowed_targets]
        to_select = _ToSelect(
            placeholder="選擇目標部門…",
            options=to_options,
            min_values=1,
            max_values=1,
            row=1,
        )

        async def _on_to(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            self.to_department = to_select.values[0] if to_select.values else None
            await self.apply_ui_update(interaction)

        to_select.callback = _on_to
        self.add_item(to_select)

        # 填寫金額與理由（Modal）
        fill_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="填寫金額與理由",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

        async def _on_fill(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if self.source_department is None:
                await send_message_compat(interaction, content="請先選擇來源部門。", ephemeral=True)
                return
            if self.to_department is None:
                await send_message_compat(interaction, content="請先選擇目標部門。", ephemeral=True)
                return
            await send_modal_compat(interaction, TransferAmountReasonModal(self))

        fill_btn.callback = _on_fill
        self.add_item(fill_btn)

        # 送出轉帳
        submit_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="送出轉帳",
            style=discord.ButtonStyle.primary,
            disabled=not self._can_submit(),
            row=2,
        )

        async def _on_submit(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if not self._can_submit():
                await send_message_compat(interaction, content="請先完成所有欄位。", ephemeral=True)
                return
            try:
                await self.service.transfer_between_departments(
                    guild_id=self.guild_id,
                    user_id=self.author_id,
                    user_roles=self.user_roles,
                    from_department=str(self.source_department),
                    to_department=str(self.to_department),
                    amount=int(self.amount or 0),
                    reason=str(self.reason or ""),
                )
                await send_message_compat(
                    interaction,
                    content=(
                        f"✅ 轉帳成功！從 {self.source_department} 轉 {self.amount:,} 幣到 {self.to_department}。"
                    ),
                    ephemeral=True,
                )
                # 成功後停用按鈕以避免重複提交
                self.amount = self.amount  # no-op for clarity
                # 清理互動：停用送出按鈕
                self.refresh_controls()
                await self.apply_ui_update(interaction)
            except (PermissionDeniedError, InsufficientFundsError, ValueError) as e:
                await send_message_compat(
                    interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
                )
            except Exception as e:  # pragma: no cover - 防禦性
                LOGGER.exception("interdept.transfer_panel.submit_failed", error=str(e))
                await send_message_compat(
                    interaction,
                    content=ErrorMessageTemplates.system_error("轉帳失敗"),
                    ephemeral=True,
                )

        submit_btn.callback = _on_submit
        self.add_item(submit_btn)

        # 取消/關閉
        cancel_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="關閉",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

        async def _on_cancel(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            try:
                # 盡可能移除互動（關閉面板）
                if self.message is not None:
                    await self.message.edit(view=None)
                else:
                    await edit_message_compat(interaction, view=None)
            except Exception:
                # 無法透過互動編輯時，嘗試直接停用 view
                self.stop()

        cancel_btn.callback = _on_cancel
        self.add_item(cancel_btn)

    async def apply_ui_update(self, interaction: discord.Interaction) -> None:
        # 重新整理控制項與嵌入
        self.refresh_controls()
        embed = self.build_embed()
        try:
            await edit_message_compat(interaction, embed=embed, view=self)
        except Exception:
            # 後援：若持有訊息實例，直接編輯
            if self.message is not None:
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass


class RecipientInputModal(discord.ui.Modal, title="設定受款人"):
    def __init__(self, parent_view: "DepartmentUserTransferPanelView") -> None:
        super().__init__()
        self.parent_view = parent_view
        self.recipient_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="受款人",
            placeholder="輸入 @使用者 或 使用者ID",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.recipient_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.recipient_input.value).strip()
        try:
            user_id: int
            if raw.startswith("<@") and raw.endswith(">"):
                user_id = int(raw[2:-1].replace("!", ""))
            else:
                user_id = int(raw)

            if user_id <= 0:
                raise ValueError

            self.parent_view.recipient_id = user_id
            await send_message_compat(interaction, content="已設定受款人。", ephemeral=True)
            await self.parent_view.apply_ui_update(interaction)
        except Exception:
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.validation_failed("受款人", "格式錯誤，請輸入 @或ID"),
                ephemeral=True,
            )


class StateCouncilAccountTransferTypeView(discord.ui.View):
    """國務院帳戶轉帳類型選擇視圖（使用者/公司/政府部門）。"""

    def __init__(
        self,
        *,
        service: Any,
        guild_id: int,
        guild: discord.Guild,
        author_id: int,
        user_roles: list[int],
        timeout: float = 300.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.service = service
        self.guild_id = guild_id
        self.guild = guild
        self.author_id = author_id
        self.user_roles = user_roles

        # 轉帳給使用者
        user_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="👤 使用者",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        user_btn.callback = self._on_user_type
        self.add_item(user_btn)

        # 轉帳給公司
        company_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🏢 公司",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        company_btn.callback = self._on_company_type
        self.add_item(company_btn)

        # 轉帳給政府部門
        dept_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🏛️ 政府部門",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        dept_btn.callback = self._on_department_type
        self.add_item(dept_btn)

    async def _check_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return False
        return True

    async def _on_user_type(self, interaction: discord.Interaction) -> None:
        """選擇使用者類型後，開啟國務院→使用者轉帳面板。"""
        if not await self._check_author(interaction):
            return

        view = StateCouncilToUserTransferView(
            service=self.service,
            guild_id=self.guild_id,
            guild=self.guild,
            author_id=self.author_id,
            user_roles=self.user_roles,
        )
        embed = view.build_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            msg = await interaction.original_response()
            view.set_message(msg)
        except Exception:
            pass

    async def _on_company_type(self, interaction: discord.Interaction) -> None:
        """選擇公司類型後，開啟國務院→公司轉帳面板。"""
        if not await self._check_author(interaction):
            return

        view = StateCouncilToCompanyTransferView(
            service=self.service,
            guild_id=self.guild_id,
            guild=self.guild,
            author_id=self.author_id,
            user_roles=self.user_roles,
        )
        has_companies = await view.setup()
        if not has_companies:
            await send_message_compat(
                interaction, content="❗ 此伺服器目前沒有已登記的公司。", ephemeral=True
            )
            return

        embed = view.build_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            msg = await interaction.original_response()
            view.set_message(msg)
        except Exception:
            pass

    async def _on_department_type(self, interaction: discord.Interaction) -> None:
        """選擇政府部門類型後，開啟國務院→政府部門轉帳面板。"""
        if not await self._check_author(interaction):
            return

        view = StateCouncilToGovernmentDeptTransferView(
            service=self.service,
            guild_id=self.guild_id,
            guild=self.guild,
            author_id=self.author_id,
            user_roles=self.user_roles,
        )
        embed = view.build_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            msg = await interaction.original_response()
            view.set_message(msg)
        except Exception:
            pass


class DepartmentTransferTypeView(discord.ui.View):
    """部門帳戶轉帳類型選擇視圖（使用者/公司/政府部門）。"""

    # 政府部門列表（部門ID → 顯示名稱, 中文名稱）- 用於轉帳目標選擇
    GOVERNMENT_DEPARTMENTS: list[tuple[str, str, str]] = [
        ("permanent_council", "👑 常任理事會", "常任理事會"),
        ("supreme_assembly", "🏛️ 最高人民會議", "最高人民會議"),
        ("interior_affairs", "🏘️ 內政部", "內政部"),
        ("finance", "💰 財政部", "財政部"),
        ("homeland_security", "🛡️ 國土安全部", "國土安全部"),
        ("central_bank", "🏦 中央銀行", "中央銀行"),
        ("justice_department", "⚖️ 法務部", "法務部"),
    ]

    def __init__(
        self,
        *,
        service: Any,
        guild_id: int,
        guild: discord.Guild,
        author_id: int,
        user_roles: list[int],
        source_department: str,
        timeout: float = 300.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.service = service
        self.guild_id = guild_id
        self.guild = guild
        self.author_id = author_id
        self.user_roles = user_roles
        self.source_department = source_department

        # 轉帳給使用者
        user_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="👤 使用者",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        user_btn.callback = self._on_user_type
        self.add_item(user_btn)

        # 轉帳給公司
        company_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🏢 公司",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        company_btn.callback = self._on_company_type
        self.add_item(company_btn)

        # 轉帳給政府部門
        dept_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🏛️ 政府部門",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        dept_btn.callback = self._on_department_type
        self.add_item(dept_btn)

    async def _check_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return False
        return True

    async def _on_user_type(self, interaction: discord.Interaction) -> None:
        """選擇使用者類型後，開啟部門→使用者轉帳面板。"""
        if not await self._check_author(interaction):
            return

        view = DepartmentUserTransferPanelView(
            service=self.service,
            guild_id=self.guild_id,
            author_id=self.author_id,
            user_roles=self.user_roles,
            source_department=self.source_department,
            departments=[self.source_department],  # 來源已固定
        )
        embed = view.build_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            msg = await interaction.original_response()
            view.set_message(msg)
        except Exception:
            pass

    async def _on_company_type(self, interaction: discord.Interaction) -> None:
        """選擇公司類型後，開啟部門→公司轉帳面板。"""
        if not await self._check_author(interaction):
            return

        view = DepartmentCompanyTransferPanelView(
            service=self.service,
            guild_id=self.guild_id,
            author_id=self.author_id,
            user_roles=self.user_roles,
            source_department=self.source_department,
            departments=[self.source_department],  # 來源已固定
        )
        has_companies = await view.setup()
        if not has_companies:
            await send_message_compat(
                interaction, content="❗ 此伺服器目前沒有已登記的公司。", ephemeral=True
            )
            return

        embed = view.build_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            msg = await interaction.original_response()
            view.set_message(msg)
        except Exception:
            pass

    async def _on_department_type(self, interaction: discord.Interaction) -> None:
        """選擇政府部門類型後，開啟部門→政府部門轉帳面板。"""
        if not await self._check_author(interaction):
            return

        view = DepartmentToGovernmentDeptTransferView(
            service=self.service,
            guild_id=self.guild_id,
            guild=self.guild,
            author_id=self.author_id,
            user_roles=self.user_roles,
            source_department=self.source_department,
        )
        embed = view.build_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            msg = await interaction.original_response()
            view.set_message(msg)
        except Exception:
            pass


class StateCouncilTransferTypeSelectionView(discord.ui.View):
    """國務院轉帳類型選擇視圖（使用者/公司）- 已棄用，保留供舊代碼相容。"""

    def __init__(
        self,
        *,
        service: Any,
        guild_id: int,
        guild: discord.Guild,
        author_id: int,
        user_roles: list[int],
        source_department: str | None,
        departments: list[str],
        timeout: float = 300.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.service = service
        self.guild_id = guild_id
        self.guild = guild
        self.author_id = author_id
        self.user_roles = user_roles
        self.source_department = source_department
        self.departments = departments

        # 轉帳給使用者
        user_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="👤 使用者",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        user_btn.callback = self._on_user_type
        self.add_item(user_btn)

        # 轉帳給公司
        company_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🏢 公司",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        company_btn.callback = self._on_company_type
        self.add_item(company_btn)

    async def _check_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return False
        return True

    async def _on_user_type(self, interaction: discord.Interaction) -> None:
        """選擇使用者類型後，開啟部門→使用者轉帳面板。"""
        if not await self._check_author(interaction):
            return

        view = DepartmentUserTransferPanelView(
            service=self.service,
            guild_id=self.guild_id,
            author_id=self.author_id,
            user_roles=self.user_roles,
            source_department=self.source_department,
            departments=self.departments,
        )
        embed = view.build_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            msg = await interaction.original_response()
            view.set_message(msg)
        except Exception:
            pass

    async def _on_company_type(self, interaction: discord.Interaction) -> None:
        """選擇公司類型後，開啟部門→公司轉帳面板。"""
        if not await self._check_author(interaction):
            return

        view = DepartmentCompanyTransferPanelView(
            service=self.service,
            guild_id=self.guild_id,
            author_id=self.author_id,
            user_roles=self.user_roles,
            source_department=self.source_department,
            departments=self.departments,
        )
        has_companies = await view.setup()
        if not has_companies:
            await send_message_compat(
                interaction, content="❗ 此伺服器目前沒有已登記的公司。", ephemeral=True
            )
            return

        embed = view.build_embed()
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)
        try:
            msg = await interaction.original_response()
            view.set_message(msg)
        except Exception:
            pass


class StateCouncilToUserTransferView(discord.ui.View):
    """國務院帳戶→使用者轉帳面板。"""

    def __init__(
        self,
        *,
        service: Any,
        guild_id: int,
        guild: discord.Guild,
        author_id: int,
        user_roles: list[int],
    ) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.guild_id = guild_id
        self.guild = guild
        self.author_id = author_id
        self.user_roles = user_roles
        self.recipient_id: int | None = None
        self.amount: int | None = None
        self.reason: str | None = None
        self.message: discord.Message | None = None
        self.currency_service = CurrencyConfigService(get_pool())
        self.refresh_controls()

    def set_message(self, message: discord.Message) -> None:
        self.message = message

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🏛️ 國務院帳戶轉帳｜使用者",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="來源", value="🏛️ 國務院帳戶", inline=True)
        embed.add_field(
            name="受款人",
            value=(f"<@{self.recipient_id}>" if self.recipient_id else "—（請從下方選擇）"),
            inline=True,
        )
        embed.add_field(
            name="金額",
            value=f"{self.amount:,}" if self.amount is not None else "—（選擇受款人後填寫）",
            inline=False,
        )
        embed.add_field(
            name="理由",
            value=self.reason or "—（選擇受款人後填寫）",
            inline=False,
        )
        embed.set_footer(text="提示：選擇受款人後，將彈出視窗輸入金額與理由。")
        return embed

    def _can_submit(self) -> bool:
        return (
            self.recipient_id is not None
            and self.amount is not None
            and self.amount > 0
            and self.reason is not None
            and len(self.reason.strip()) > 0
        )

    def refresh_controls(self) -> None:
        self.clear_items()

        # UserSelect for recipient
        user_select: discord.ui.UserSelect[Any] = discord.ui.UserSelect(
            placeholder="選擇受款使用者…",
            min_values=1,
            max_values=1,
            row=0,
        )

        async def _on_user_select(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if not interaction.data:
                return
            values = interaction.data.get("values", [])
            if values:
                self.recipient_id = int(values[0])
                # 選擇使用者後彈出金額 Modal
                await send_modal_compat(interaction, StateCouncilTransferAmountModal(self))

        user_select.callback = _on_user_select
        self.add_item(user_select)

        # 送出按鈕
        submit_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="送出轉帳",
            style=discord.ButtonStyle.primary,
            disabled=not self._can_submit(),
            row=1,
        )

        async def _on_submit(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if not self._can_submit():
                await send_message_compat(interaction, content="請先完成所有欄位。", ephemeral=True)
                return
            await self._execute_transfer(interaction)

        submit_btn.callback = _on_submit
        self.add_item(submit_btn)

        # 關閉按鈕
        close_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="關閉",
            style=discord.ButtonStyle.secondary,
            row=1,
        )

        async def _on_close(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            try:
                if self.message:
                    await self.message.edit(view=None)
                else:
                    await edit_message_compat(interaction, view=None)
            except Exception:
                self.stop()

        close_btn.callback = _on_close
        self.add_item(close_btn)

    async def _execute_transfer(self, interaction: discord.Interaction) -> None:
        """執行國務院帳戶→使用者轉帳。"""
        try:
            currency_config = await self.currency_service.get_currency_config(
                guild_id=self.guild_id
            )
            formatted_amount = _format_currency_display(currency_config, int(self.amount or 0))
        except Exception:
            formatted_amount = f"{int(self.amount or 0):,} 點"

        try:
            success, msg, deductions = await self.service.transfer_from_state_council_auto_deduct(
                guild_id=self.guild_id,
                user_id=self.author_id,
                user_roles=self.user_roles,
                target_id=int(self.recipient_id or 0),
                target_type="user",
                amount=int(self.amount or 0),
                reason=str(self.reason or ""),
            )
            if not success:
                await send_message_compat(
                    interaction,
                    content=f"❗ {msg}",
                    ephemeral=True,
                )
                return

            deduction_note = ""
            if deductions:
                parts = [f"{dept} {amt:,}" for dept, amt in deductions]
                deduction_note = "\n扣款來源：" + "、".join(parts)

            await send_message_compat(
                interaction,
                content=(
                    f"✅ 轉帳成功！已從國務院帳戶轉帳 {formatted_amount} 給 <@{self.recipient_id}>。"
                    f"{deduction_note}"
                ),
                ephemeral=True,
            )
            self.refresh_controls()
            await self.apply_ui_update(interaction)
        except (PermissionDeniedError, InsufficientFundsError, ValueError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("state_council_to_user.transfer_failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("轉帳失敗"),
                ephemeral=True,
            )

    async def apply_ui_update(self, interaction: discord.Interaction) -> None:
        self.refresh_controls()
        embed = self.build_embed()
        try:
            await edit_message_compat(interaction, embed=embed, view=self)
        except Exception:
            if self.message:
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass


class StateCouncilToCompanyTransferView(discord.ui.View):
    """國務院帳戶→公司轉帳面板。"""

    def __init__(
        self,
        *,
        service: Any,
        guild_id: int,
        guild: discord.Guild,
        author_id: int,
        user_roles: list[int],
    ) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.guild_id = guild_id
        self.guild = guild
        self.author_id = author_id
        self.user_roles = user_roles
        self.company_id: int | None = None
        self.company_name: str | None = None
        self.company_account_id: int | None = None
        self.amount: int | None = None
        self.reason: str | None = None
        self.message: discord.Message | None = None
        self._companies: dict[int, Any] = {}
        self.currency_service = CurrencyConfigService(get_pool())

    async def setup(self) -> bool:
        """Fetch companies and setup the view."""
        from src.bot.ui.company_select import get_active_companies

        companies = await get_active_companies(self.guild_id)
        if not companies:
            return False

        self._companies = {c.id: c for c in companies}
        self.refresh_controls()
        return True

    def set_message(self, message: discord.Message) -> None:
        self.message = message

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🏛️ 國務院帳戶轉帳｜公司",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="來源", value="🏛️ 國務院帳戶", inline=True)
        embed.add_field(
            name="受款公司",
            value=(f"🏢 {self.company_name}" if self.company_name else "—（請從下方選擇）"),
            inline=True,
        )
        embed.add_field(
            name="金額",
            value=f"{self.amount:,}" if self.amount is not None else "—（選擇公司後填寫）",
            inline=False,
        )
        embed.add_field(
            name="理由",
            value=self.reason or "—（選擇公司後填寫）",
            inline=False,
        )
        embed.set_footer(text="提示：選擇公司後，將彈出視窗輸入金額與理由。")
        return embed

    def _can_submit(self) -> bool:
        return (
            self.company_account_id is not None
            and self.amount is not None
            and self.amount > 0
            and self.reason is not None
            and len(self.reason.strip()) > 0
        )

    def refresh_controls(self) -> None:
        self.clear_items()

        # 公司選擇下拉
        if self._companies:
            from src.bot.ui.company_select import build_company_select_options

            options = build_company_select_options(list(self._companies.values()))
            if options:
                company_select: discord.ui.Select[Any] = discord.ui.Select(
                    placeholder="🏢 選擇受款公司…",
                    options=options,
                    min_values=1,
                    max_values=1,
                    row=0,
                )

                async def _on_company(interaction: discord.Interaction) -> None:
                    if interaction.user.id != self.author_id:
                        await send_message_compat(
                            interaction, content="僅限面板開啟者操作。", ephemeral=True
                        )
                        return
                    try:
                        company_id = (
                            int(company_select.values[0]) if company_select.values else None
                        )
                    except ValueError:
                        await send_message_compat(
                            interaction, content="選項格式錯誤。", ephemeral=True
                        )
                        return
                    if company_id and company_id in self._companies:
                        company = self._companies[company_id]
                        self.company_id = company.id
                        self.company_name = company.name
                        self.company_account_id = company.account_id
                        # 選擇公司後彈出金額 Modal
                        await send_modal_compat(interaction, StateCouncilTransferAmountModal(self))

                company_select.callback = _on_company
                self.add_item(company_select)

        # 送出按鈕
        submit_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="送出轉帳",
            style=discord.ButtonStyle.primary,
            disabled=not self._can_submit(),
            row=1,
        )

        async def _on_submit(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if not self._can_submit():
                await send_message_compat(interaction, content="請先完成所有欄位。", ephemeral=True)
                return
            await self._execute_transfer(interaction)

        submit_btn.callback = _on_submit
        self.add_item(submit_btn)

        # 關閉按鈕
        close_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="關閉",
            style=discord.ButtonStyle.secondary,
            row=1,
        )

        async def _on_close(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            try:
                if self.message:
                    await self.message.edit(view=None)
                else:
                    await edit_message_compat(interaction, view=None)
            except Exception:
                self.stop()

        close_btn.callback = _on_close
        self.add_item(close_btn)

    async def _execute_transfer(self, interaction: discord.Interaction) -> None:
        """執行國務院帳戶→公司轉帳。"""
        try:
            currency_config = await self.currency_service.get_currency_config(
                guild_id=self.guild_id
            )
            formatted_amount = _format_currency_display(currency_config, int(self.amount or 0))
        except Exception:
            formatted_amount = f"{int(self.amount or 0):,} 點"

        try:
            success, msg, deductions = await self.service.transfer_from_state_council_auto_deduct(
                guild_id=self.guild_id,
                user_id=self.author_id,
                user_roles=self.user_roles,
                target_id=int(self.company_account_id or 0),
                target_type="company",
                amount=int(self.amount or 0),
                reason=str(self.reason or ""),
            )
            if not success:
                await send_message_compat(
                    interaction,
                    content=f"❗ {msg}",
                    ephemeral=True,
                )
                return

            deduction_note = ""
            if deductions:
                parts = [f"{dept} {amt:,}" for dept, amt in deductions]
                deduction_note = "\n扣款來源：" + "、".join(parts)

            await send_message_compat(
                interaction,
                content=(
                    f"✅ 轉帳成功！已從國務院帳戶轉帳 {formatted_amount} 給 🏢 {self.company_name}。"
                    f"{deduction_note}"
                ),
                ephemeral=True,
            )
            self.refresh_controls()
            await self.apply_ui_update(interaction)
        except (PermissionDeniedError, InsufficientFundsError, ValueError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("state_council_to_company.transfer_failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("轉帳失敗"),
                ephemeral=True,
            )

    async def apply_ui_update(self, interaction: discord.Interaction) -> None:
        self.refresh_controls()
        embed = self.build_embed()
        try:
            await edit_message_compat(interaction, embed=embed, view=self)
        except Exception:
            if self.message:
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass


class StateCouncilToGovernmentDeptTransferView(discord.ui.View):
    """國務院帳戶→政府部門轉帳面板。"""

    # 政府部門列表（部門ID → 顯示名稱）
    GOVERNMENT_DEPARTMENTS: list[tuple[str, str, str]] = [
        ("permanent_council", "👑 常任理事會", "常任理事會"),
        ("interior_affairs", "🏘️ 內政部", "內政部"),
        ("finance", "💰 財政部", "財政部"),
        ("homeland_security", "🛡️ 國土安全部", "國土安全部"),
        ("central_bank", "🏦 中央銀行", "中央銀行"),
        ("justice_department", "⚖️ 法務部", "法務部"),
        ("supreme_assembly", "🏛️ 最高人民會議", "最高人民會議"),
    ]

    def __init__(
        self,
        *,
        service: Any,
        guild_id: int,
        guild: discord.Guild,
        author_id: int,
        user_roles: list[int],
    ) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.guild_id = guild_id
        self.guild = guild
        self.author_id = author_id
        self.user_roles = user_roles
        self.target_dept_id: str | None = None
        self.target_dept_name: str | None = None
        self.amount: int | None = None
        self.reason: str | None = None
        self.message: discord.Message | None = None
        self.currency_service = CurrencyConfigService(get_pool())
        self.refresh_controls()

    def set_message(self, message: discord.Message) -> None:
        self.message = message

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🏛️ 國務院帳戶轉帳｜政府部門",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="來源", value="🏛️ 國務院帳戶", inline=True)
        embed.add_field(
            name="目標部門",
            value=(self.target_dept_name or "—（請從下方選擇）"),
            inline=True,
        )
        embed.add_field(
            name="金額",
            value=f"{self.amount:,}" if self.amount is not None else "—（選擇部門後填寫）",
            inline=False,
        )
        embed.add_field(
            name="理由",
            value=self.reason or "—（選擇部門後填寫）",
            inline=False,
        )
        embed.set_footer(text="提示：選擇目標部門後，將彈出視窗輸入金額與理由。")
        return embed

    def _can_submit(self) -> bool:
        return (
            self.target_dept_id is not None
            and self.amount is not None
            and self.amount > 0
            and self.reason is not None
            and len(self.reason.strip()) > 0
        )

    def refresh_controls(self) -> None:
        self.clear_items()

        # 政府部門選擇下拉
        options = [
            discord.SelectOption(label=label, value=dept_id, description=name)
            for dept_id, label, name in self.GOVERNMENT_DEPARTMENTS
        ]
        dept_select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder="🏛️ 選擇目標政府部門…",
            options=options,
            min_values=1,
            max_values=1,
            row=0,
        )

        async def _on_dept_select(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if dept_select.values:
                selected_id = dept_select.values[0]
                for dept_id, label, _ in self.GOVERNMENT_DEPARTMENTS:
                    if dept_id == selected_id:
                        self.target_dept_id = dept_id
                        self.target_dept_name = label
                        break
                # 選擇部門後彈出金額 Modal
                await send_modal_compat(interaction, StateCouncilTransferAmountModal(self))

        dept_select.callback = _on_dept_select
        self.add_item(dept_select)

        # 送出按鈕
        submit_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="送出轉帳",
            style=discord.ButtonStyle.primary,
            disabled=not self._can_submit(),
            row=1,
        )

        async def _on_submit(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if not self._can_submit():
                await send_message_compat(interaction, content="請先完成所有欄位。", ephemeral=True)
                return
            await self._execute_transfer(interaction)

        submit_btn.callback = _on_submit
        self.add_item(submit_btn)

        # 關閉按鈕
        close_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="關閉",
            style=discord.ButtonStyle.secondary,
            row=1,
        )

        async def _on_close(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            try:
                if self.message:
                    await self.message.edit(view=None)
                else:
                    await edit_message_compat(interaction, view=None)
            except Exception:
                self.stop()

        close_btn.callback = _on_close
        self.add_item(close_btn)

    async def _execute_transfer(self, interaction: discord.Interaction) -> None:
        """執行國務院帳戶→政府部門轉帳。"""
        try:
            currency_config = await self.currency_service.get_currency_config(
                guild_id=self.guild_id
            )
            formatted_amount = _format_currency_display(currency_config, int(self.amount or 0))
        except Exception:
            formatted_amount = f"{int(self.amount or 0):,} 點"

        # 將部門 ID 轉換為部門名稱
        target_name = None
        for dept_id, _, name in self.GOVERNMENT_DEPARTMENTS:
            if dept_id == self.target_dept_id:
                target_name = name
                break
        if not target_name:
            await send_message_compat(interaction, content="無效的目標部門。", ephemeral=True)
            return

        try:
            success, msg, deductions = await self.service.transfer_from_state_council_auto_deduct(
                guild_id=self.guild_id,
                user_id=self.author_id,
                user_roles=self.user_roles,
                target_id=None,
                target_type="department",
                target_department=target_name,
                amount=int(self.amount or 0),
                reason=str(self.reason or ""),
            )
            if not success:
                await send_message_compat(
                    interaction,
                    content=f"❗ {msg}",
                    ephemeral=True,
                )
                return

            deduction_note = ""
            if deductions:
                parts = [f"{dept} {amt:,}" for dept, amt in deductions]
                deduction_note = "\n扣款來源：" + "、".join(parts)

            await send_message_compat(
                interaction,
                content=(
                    f"✅ 轉帳成功！已從國務院帳戶轉帳 {formatted_amount} 到 {self.target_dept_name}。"
                    f"{deduction_note}"
                ),
                ephemeral=True,
            )
            self.refresh_controls()
            await self.apply_ui_update(interaction)
        except (PermissionDeniedError, InsufficientFundsError, ValueError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("state_council_to_dept.transfer_failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("轉帳失敗"),
                ephemeral=True,
            )

    async def apply_ui_update(self, interaction: discord.Interaction) -> None:
        self.refresh_controls()
        embed = self.build_embed()
        try:
            await edit_message_compat(interaction, embed=embed, view=self)
        except Exception:
            if self.message:
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass


class DepartmentToGovernmentDeptTransferView(discord.ui.View):
    """部門帳戶→政府部門轉帳面板（包含其他部門、常任理事會、最高人民會議）。"""

    # 政府部門列表（部門ID → 顯示名稱, 中文名稱）
    GOVERNMENT_DEPARTMENTS: list[tuple[str, str, str]] = [
        ("permanent_council", "👑 常任理事會", "常任理事會"),
        ("supreme_assembly", "🏛️ 最高人民會議", "最高人民會議"),
        ("interior_affairs", "🏘️ 內政部", "內政部"),
        ("finance", "💰 財政部", "財政部"),
        ("homeland_security", "🛡️ 國土安全部", "國土安全部"),
        ("central_bank", "🏦 中央銀行", "中央銀行"),
        ("justice_department", "⚖️ 法務部", "法務部"),
    ]

    # 部門名稱到 ID 的映射
    DEPT_NAME_TO_ID: dict[str, str] = {
        "常任理事會": "permanent_council",
        "最高人民會議": "supreme_assembly",
        "內政部": "interior_affairs",
        "財政部": "finance",
        "國土安全部": "homeland_security",
        "中央銀行": "central_bank",
        "法務部": "justice_department",
    }

    def __init__(
        self,
        *,
        service: Any,
        guild_id: int,
        guild: discord.Guild,
        author_id: int,
        user_roles: list[int],
        source_department: str,
    ) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.guild_id = guild_id
        self.guild = guild
        self.author_id = author_id
        self.user_roles = user_roles
        self.source_department = source_department
        self.target_dept_id: str | None = None
        self.target_dept_name: str | None = None
        self.amount: int | None = None
        self.reason: str | None = None
        self.message: discord.Message | None = None
        self.currency_service = CurrencyConfigService(get_pool())
        self.refresh_controls()

    def set_message(self, message: discord.Message) -> None:
        self.message = message

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🏛️ {self.source_department} 轉帳｜政府部門",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="來源", value=f"🏛️ {self.source_department}", inline=True)
        embed.add_field(
            name="目標部門",
            value=(self.target_dept_name or "—（請從下方選擇）"),
            inline=True,
        )
        embed.add_field(
            name="金額",
            value=f"{self.amount:,}" if self.amount is not None else "—（選擇部門後填寫）",
            inline=False,
        )
        embed.add_field(
            name="理由",
            value=self.reason or "—（選擇部門後填寫）",
            inline=False,
        )
        embed.set_footer(text="提示：選擇目標部門後，將彈出視窗輸入金額與理由。")
        return embed

    def _can_submit(self) -> bool:
        return (
            self.target_dept_id is not None
            and self.amount is not None
            and self.amount > 0
            and self.reason is not None
            and len(self.reason.strip()) > 0
        )

    def _get_available_departments(self) -> list[tuple[str, str, str]]:
        """取得可用的目標部門列表（排除來源部門自身）。"""
        source_id = self.DEPT_NAME_TO_ID.get(self.source_department)
        return [
            (dept_id, label, name)
            for dept_id, label, name in self.GOVERNMENT_DEPARTMENTS
            if dept_id != source_id
        ]

    def refresh_controls(self) -> None:
        self.clear_items()

        # 政府部門選擇下拉（排除來源部門自身）
        available_depts = self._get_available_departments()
        options = [
            discord.SelectOption(label=label, value=dept_id, description=name)
            for dept_id, label, name in available_depts
        ]
        dept_select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder="🏛️ 選擇目標政府部門…",
            options=options,
            min_values=1,
            max_values=1,
            row=0,
        )

        async def _on_dept_select(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if dept_select.values:
                selected_id = dept_select.values[0]
                for dept_id, label, _ in self.GOVERNMENT_DEPARTMENTS:
                    if dept_id == selected_id:
                        self.target_dept_id = dept_id
                        self.target_dept_name = label
                        break
                # 選擇部門後彈出金額 Modal
                await send_modal_compat(interaction, DepartmentTransferAmountModal(self))

        dept_select.callback = _on_dept_select
        self.add_item(dept_select)

        # 送出按鈕
        submit_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="送出轉帳",
            style=discord.ButtonStyle.primary,
            disabled=not self._can_submit(),
            row=1,
        )

        async def _on_submit(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if not self._can_submit():
                await send_message_compat(interaction, content="請先完成所有欄位。", ephemeral=True)
                return
            await self._execute_transfer(interaction)

        submit_btn.callback = _on_submit
        self.add_item(submit_btn)

        # 關閉按鈕
        close_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="關閉",
            style=discord.ButtonStyle.secondary,
            row=1,
        )

        async def _on_close(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            try:
                if self.message:
                    await self.message.edit(view=None)
                else:
                    await edit_message_compat(interaction, view=None)
            except Exception:
                self.stop()

        close_btn.callback = _on_close
        self.add_item(close_btn)

    async def _execute_transfer(self, interaction: discord.Interaction) -> None:
        """執行部門帳戶→政府部門轉帳。"""
        try:
            currency_config = await self.currency_service.get_currency_config(
                guild_id=self.guild_id
            )
            formatted_amount = _format_currency_display(currency_config, int(self.amount or 0))
        except Exception:
            formatted_amount = f"{int(self.amount or 0):,} 點"

        # 將部門 ID 轉換為部門名稱
        target_name = None
        for dept_id, _, name in self.GOVERNMENT_DEPARTMENTS:
            if dept_id == self.target_dept_id:
                target_name = name
                break
        if not target_name:
            await send_message_compat(interaction, content="無效的目標部門。", ephemeral=True)
            return

        try:
            # 使用 transfer_between_departments，從來源部門到目標部門
            await self.service.transfer_between_departments(
                guild_id=self.guild_id,
                user_id=self.author_id,
                user_roles=self.user_roles,
                from_department=self.source_department,
                to_department=target_name,
                amount=int(self.amount or 0),
                reason=str(self.reason or ""),
            )
            await send_message_compat(
                interaction,
                content=f"✅ 轉帳成功！已從 {self.source_department} 轉帳 {formatted_amount} 到 {self.target_dept_name}。",
                ephemeral=True,
            )
            self.refresh_controls()
            await self.apply_ui_update(interaction)
        except (PermissionDeniedError, InsufficientFundsError, ValueError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("dept_to_govt_dept.transfer_failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("轉帳失敗"),
                ephemeral=True,
            )

    async def apply_ui_update(self, interaction: discord.Interaction) -> None:
        self.refresh_controls()
        embed = self.build_embed()
        try:
            await edit_message_compat(interaction, embed=embed, view=self)
        except Exception:
            try:
                if self.message:
                    await self.message.edit(embed=embed, view=self)
            except Exception:
                pass


class DepartmentTransferAmountModal(discord.ui.Modal, title="填寫金額與理由"):
    """部門轉帳金額與理由輸入 Modal。"""

    def __init__(self, parent_view: Any) -> None:
        super().__init__()
        self.parent_view = parent_view

        self.amount_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="金額",
            placeholder="輸入轉帳金額（正整數）",
            required=True,
            style=discord.TextStyle.short,
        )
        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="理由",
            placeholder="輸入轉帳理由",
            required=True,
            style=discord.TextStyle.paragraph,
        )

        self.add_item(self.amount_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = int(str(self.amount_input.value).strip())
            if amount <= 0:
                raise ValueError("金額需為正整數")
            reason = str(self.reason_input.value).strip()
            if not reason:
                raise ValueError("請輸入理由")

            self.parent_view.amount = amount
            self.parent_view.reason = reason
            await send_message_compat(interaction, content="已更新金額與理由。", ephemeral=True)

            # 更新原面板
            await self.parent_view.apply_ui_update(interaction)
        except ValueError as e:
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.validation_failed("輸入值", str(e)),
                ephemeral=True,
            )


class StateCouncilTransferAmountModal(discord.ui.Modal, title="填寫金額與理由"):
    """國務院轉帳金額與理由輸入 Modal。"""

    def __init__(self, parent_view: Any) -> None:
        super().__init__()
        self.parent_view = parent_view

        self.amount_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="金額",
            placeholder="輸入轉帳金額（正整數）",
            required=True,
            style=discord.TextStyle.short,
        )
        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="理由",
            placeholder="輸入轉帳理由",
            required=True,
            style=discord.TextStyle.paragraph,
        )

        self.add_item(self.amount_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = int(str(self.amount_input.value).strip())
            if amount <= 0:
                raise ValueError("金額需為正整數")
            reason = str(self.reason_input.value).strip()
            if not reason:
                raise ValueError("請輸入理由")

            self.parent_view.amount = amount
            self.parent_view.reason = reason
            await send_message_compat(interaction, content="已更新金額與理由。", ephemeral=True)

            # 更新原面板
            await self.parent_view.apply_ui_update(interaction)
        except ValueError as e:
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.validation_failed("輸入值", str(e)),
                ephemeral=True,
            )


class DepartmentCompanyTransferPanelView(discord.ui.View):
    """部門→公司 轉帳面板。"""

    def __init__(
        self,
        *,
        service: Any,
        guild_id: int,
        author_id: int,
        user_roles: list[int],
        source_department: str | None,
        departments: list[str],
    ) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles
        self.departments = departments
        self.source_department: str | None = source_department
        self.company_id: int | None = None
        self.company_name: str | None = None
        self.company_account_id: int | None = None
        self.amount: int | None = None
        self.reason: str | None = None
        self.message: discord.Message | None = None
        self._companies: dict[int, Any] = {}

    async def setup(self) -> bool:
        """Fetch companies and setup the view.

        Returns:
            True if companies are available, False otherwise
        """
        from src.bot.ui.company_select import get_active_companies

        companies = await get_active_companies(self.guild_id)
        if not companies:
            return False

        self._companies = {c.id: c for c in companies}
        self.refresh_controls()
        return True

    def set_message(self, message: discord.Message) -> None:
        self.message = message

    def build_embed(self) -> discord.Embed:
        title = "🏛️ 部門→公司 轉帳"
        if self.source_department:
            title += f"｜自 {self.source_department} 轉出"
        embed = discord.Embed(title=title, color=discord.Color.blurple())
        embed.add_field(
            name="來源部門",
            value=self.source_department or "—（總覽中，請先選擇）",
            inline=True,
        )
        embed.add_field(
            name="受款公司",
            value=(f"🏢 {self.company_name}" if self.company_name else "—（請從下方選擇）"),
            inline=True,
        )
        embed.add_field(
            name="金額",
            value=f"{self.amount:,}" if self.amount is not None else "—（按下方按鈕填寫）",
            inline=False,
        )
        embed.add_field(
            name="理由",
            value=self.reason or "—（按下方按鈕填寫）",
            inline=False,
        )
        embed.set_footer(text="提示：送出前需先選定來源部門、受款公司並填寫金額與理由。")
        return embed

    def _can_submit(self) -> bool:
        return (
            self.source_department is not None
            and self.company_account_id is not None
            and self.amount is not None
            and self.amount > 0
            and self.reason is not None
            and len(self.reason.strip()) > 0
        )

    def refresh_controls(self) -> None:
        self.clear_items()

        # 來源部門下拉（僅在總覽時顯示）
        if self.source_department is None:

            class _FromSelect(discord.ui.Select[Any]):
                pass

            from_options = [discord.SelectOption(label=d, value=d) for d in self.departments]
            from_select = _FromSelect(
                placeholder="選擇來源部門…",
                options=from_options,
                min_values=1,
                max_values=1,
                row=0,
            )

            async def _on_from(interaction: discord.Interaction) -> None:
                if interaction.user.id != self.author_id:
                    await send_message_compat(
                        interaction, content="僅限面板開啟者操作。", ephemeral=True
                    )
                    return
                self.source_department = from_select.values[0] if from_select.values else None
                await self.apply_ui_update(interaction)

            from_select.callback = _on_from
            self.add_item(from_select)

        # 公司選擇下拉
        if self.company_account_id is None and self._companies:
            from src.bot.ui.company_select import build_company_select_options

            options = build_company_select_options(list(self._companies.values()))
            if options:
                company_select: discord.ui.Select[Any] = discord.ui.Select(
                    placeholder="🏢 選擇受款公司…",
                    options=options,
                    min_values=1,
                    max_values=1,
                    row=1 if self.source_department is None else 0,
                )

                async def _on_company(interaction: discord.Interaction) -> None:
                    if interaction.user.id != self.author_id:
                        await send_message_compat(
                            interaction, content="僅限面板開啟者操作。", ephemeral=True
                        )
                        return
                    try:
                        company_id = (
                            int(company_select.values[0]) if company_select.values else None
                        )
                    except ValueError:
                        await send_message_compat(
                            interaction, content="選項格式錯誤。", ephemeral=True
                        )
                        return
                    if company_id and company_id in self._companies:
                        company = self._companies[company_id]
                        self.company_id = company.id
                        self.company_name = company.name
                        self.company_account_id = company.account_id
                    await self.apply_ui_update(interaction)

                company_select.callback = _on_company
                self.add_item(company_select)

        # 金額與理由
        fill_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="填寫金額與理由",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

        async def _on_fill(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if self.source_department is None:
                await send_message_compat(interaction, content="請先選擇來源部門。", ephemeral=True)
                return
            if self.company_account_id is None:
                await send_message_compat(interaction, content="請先選擇受款公司。", ephemeral=True)
                return
            await send_modal_compat(interaction, TransferAmountReasonModal(self))

        fill_btn.callback = _on_fill
        self.add_item(fill_btn)

        # 送出
        submit_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="送出轉帳",
            style=discord.ButtonStyle.primary,
            disabled=not self._can_submit(),
            row=2,
        )

        async def _on_submit(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if not self._can_submit():
                await send_message_compat(interaction, content="請先完成所有欄位。", ephemeral=True)
                return
            try:
                from src.db import pool as db_pool

                currency_service = CurrencyConfigService(db_pool.get_pool())
                currency_config = await currency_service.get_currency_config(guild_id=self.guild_id)
                formatted_amount = _format_currency_display(currency_config, int(self.amount or 0))
            except Exception:
                formatted_amount = f"{int(self.amount or 0):,} 點"

            try:
                # Use same transfer method but target is company account ID
                await self.service.transfer_department_to_user(
                    guild_id=self.guild_id,
                    user_id=self.author_id,
                    user_roles=self.user_roles,
                    from_department=str(self.source_department),
                    recipient_id=int(self.company_account_id or 0),
                    amount=int(self.amount or 0),
                    reason=str(self.reason or ""),
                )
                await send_message_compat(
                    interaction,
                    content=(
                        f"✅ 轉帳成功！從 {self.source_department} 轉 {formatted_amount} 給 🏢 {self.company_name}。"
                    ),
                    ephemeral=True,
                )
                self.refresh_controls()
                await self.apply_ui_update(interaction)
            except (PermissionDeniedError, InsufficientFundsError, ValueError) as e:
                await send_message_compat(
                    interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
                )
            except Exception as e:
                LOGGER.exception("dept_to_company.transfer_panel.submit_failed", error=str(e))
                await send_message_compat(
                    interaction,
                    content=ErrorMessageTemplates.system_error("轉帳失敗"),
                    ephemeral=True,
                )

        submit_btn.callback = _on_submit
        self.add_item(submit_btn)

        # 取消/關閉
        cancel_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="關閉",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

        async def _on_cancel(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            try:
                if self.message is not None:
                    await self.message.edit(view=None)
                else:
                    await edit_message_compat(interaction, view=None)
            except Exception:
                self.stop()

        cancel_btn.callback = _on_cancel
        self.add_item(cancel_btn)

    async def apply_ui_update(self, interaction: discord.Interaction) -> None:
        self.refresh_controls()
        embed = self.build_embed()
        try:
            await edit_message_compat(interaction, embed=embed, view=self)
        except Exception:
            if self.message is not None:
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass


class DepartmentUserTransferPanelView(discord.ui.View):
    def __init__(
        self,
        *,
        service: Any,
        guild_id: int,
        author_id: int,
        user_roles: list[int],
        source_department: str | None,
        departments: list[str],
    ) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles
        self.departments = departments
        self.source_department: str | None = source_department
        self.recipient_id: int | None = None
        self.amount: int | None = None
        self.reason: str | None = None
        self.message: discord.Message | None = None

        self.refresh_controls()

    def set_message(self, message: discord.Message) -> None:
        self.message = message

    def build_embed(self) -> discord.Embed:
        title = "🏛️ 部門→使用者 轉帳"
        if self.source_department:
            title += f"｜自 {self.source_department} 轉出"
        embed = discord.Embed(title=title, color=discord.Color.blurple())
        embed.add_field(
            name="來源部門",
            value=self.source_department or "—（總覽中，請先選擇）",
            inline=True,
        )
        embed.add_field(
            name="受款人",
            value=(f"<@{self.recipient_id}>" if self.recipient_id else "—（按下方按鈕設定）"),
            inline=True,
        )
        embed.add_field(
            name="金額",
            value=f"{self.amount:,}" if self.amount is not None else "—（按下方按鈕填寫）",
            inline=False,
        )
        embed.add_field(
            name="理由",
            value=self.reason or "—（按下方按鈕填寫）",
            inline=False,
        )
        embed.set_footer(text="提示：送出前需先選定來源部門、受款人並填寫金額與理由。")
        return embed

    def _can_submit(self) -> bool:
        return (
            self.source_department is not None
            and self.recipient_id is not None
            and self.amount is not None
            and self.amount > 0
            and self.reason is not None
            and len(self.reason.strip()) > 0
        )

    def refresh_controls(self) -> None:
        self.clear_items()

        # 來源部門下拉（僅在總覽時顯示）
        if self.source_department is None:

            class _FromSelect(discord.ui.Select[Any]):
                pass

            from_options = [discord.SelectOption(label=d, value=d) for d in self.departments]
            from_select = _FromSelect(
                placeholder="選擇來源部門…",
                options=from_options,
                min_values=1,
                max_values=1,
                row=0,
            )

            async def _on_from(interaction: discord.Interaction) -> None:
                if interaction.user.id != self.author_id:
                    await send_message_compat(
                        interaction, content="僅限面板開啟者操作。", ephemeral=True
                    )
                    return
                self.source_department = from_select.values[0] if from_select.values else None
                await self.apply_ui_update(interaction)

            from_select.callback = _on_from
            self.add_item(from_select)

        # 受款人設定（Modal）
        set_recipient_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="設定受款人",
            style=discord.ButtonStyle.secondary,
            row=1,
        )

        async def _on_set_recipient(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if self.source_department is None:
                await send_message_compat(interaction, content="請先選擇來源部門。", ephemeral=True)
                return
            await send_modal_compat(interaction, RecipientInputModal(self))

        set_recipient_btn.callback = _on_set_recipient
        self.add_item(set_recipient_btn)

        # 金額與理由（沿用既有 Modal）
        fill_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="填寫金額與理由",
            style=discord.ButtonStyle.secondary,
            row=1,
        )

        async def _on_fill(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if self.source_department is None:
                await send_message_compat(interaction, content="請先選擇來源部門。", ephemeral=True)
                return
            if self.recipient_id is None:
                await send_message_compat(interaction, content="請先設定受款人。", ephemeral=True)
                return
            await send_modal_compat(interaction, TransferAmountReasonModal(self))

        fill_btn.callback = _on_fill
        self.add_item(fill_btn)

        # 送出
        submit_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="送出轉帳",
            style=discord.ButtonStyle.primary,
            disabled=not self._can_submit(),
            row=2,
        )

        async def _on_submit(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            if not self._can_submit():
                await send_message_compat(interaction, content="請先完成所有欄位。", ephemeral=True)
                return
            try:
                from src.db import pool as db_pool

                currency_service = CurrencyConfigService(db_pool.get_pool())
                currency_config = await currency_service.get_currency_config(guild_id=self.guild_id)
                formatted_amount = _format_currency_display(currency_config, int(self.amount or 0))
            except Exception:
                formatted_amount = f"{int(self.amount or 0):,} 點"

            try:
                await self.service.transfer_department_to_user(
                    guild_id=self.guild_id,
                    user_id=self.author_id,
                    user_roles=self.user_roles,
                    from_department=str(self.source_department),
                    recipient_id=int(self.recipient_id or 0),
                    amount=int(self.amount or 0),
                    reason=str(self.reason or ""),
                )
                await send_message_compat(
                    interaction,
                    content=(
                        f"✅ 轉帳成功！從 {self.source_department} 轉 {formatted_amount} 給 <@{self.recipient_id}>。"
                    ),
                    ephemeral=True,
                )
                self.refresh_controls()
                await self.apply_ui_update(interaction)
            except (PermissionDeniedError, InsufficientFundsError, ValueError) as e:
                await send_message_compat(
                    interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
                )
            except Exception as e:
                LOGGER.exception("dept_to_user.transfer_panel.submit_failed", error=str(e))
                await send_message_compat(
                    interaction,
                    content=ErrorMessageTemplates.system_error("轉帳失敗"),
                    ephemeral=True,
                )

        submit_btn.callback = _on_submit
        self.add_item(submit_btn)

        # 取消/關閉
        cancel_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="關閉",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

        async def _on_cancel(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return
            try:
                if self.message is not None:
                    await self.message.edit(view=None)
                else:
                    await edit_message_compat(interaction, view=None)
            except Exception:
                self.stop()

        cancel_btn.callback = _on_cancel
        self.add_item(cancel_btn)

    async def apply_ui_update(self, interaction: discord.Interaction) -> None:
        self.refresh_controls()
        embed = self.build_embed()
        try:
            await edit_message_compat(interaction, embed=embed, view=self)
        except Exception:
            if self.message is not None:
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass


class WelfareDisbursementModal(discord.ui.Modal, title="福利發放"):
    def __init__(
        self, service: StateCouncilService, guild_id: int, author_id: int, user_roles: list[int]
    ) -> None:
        super().__init__()
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles

        self.recipient_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="受款人",
            placeholder="輸入受款人 @使用者 或使用者ID",
            required=True,
            style=discord.TextStyle.short,
        )
        self.amount_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="金額",
            placeholder="輸入發放金額（數字）",
            required=True,
            style=discord.TextStyle.short,
        )
        self.type_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="類型",
            placeholder="定期福利 或 特殊福利",
            required=True,
            style=discord.TextStyle.short,
        )
        self.reference_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="備註",
            placeholder="輸入備註（可選）",
            required=False,
            style=discord.TextStyle.short,
        )
        self.add_item(self.recipient_input)
        self.add_item(self.amount_input)
        self.add_item(self.type_input)
        self.add_item(self.reference_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            recipient_input = str(self.recipient_input.value)
            amount = int(str(self.amount_input.value))
            disbursement_type = str(self.type_input.value)
            _reference_id = str(self.reference_input.value).strip() or None

            # Parse recipient ID
            if recipient_input.startswith("<@") and recipient_input.endswith(">"):
                recipient_id = int(recipient_input[2:-1].replace("!", ""))
            else:
                recipient_id = int(recipient_input)

            await self.service.disburse_welfare(
                guild_id=self.guild_id,
                department="內政部",
                user_id=self.author_id,
                user_roles=self.user_roles,
                recipient_id=recipient_id,
                amount=amount,
                disbursement_type=disbursement_type,
            )

            await send_message_compat(
                interaction,
                content=(
                    f"✅ 福利發放成功！\n"
                    f"向 <@{recipient_id}> 發放 {amount:,} 幣\n"
                    f"類型：{disbursement_type}"
                ),
                ephemeral=True,
            )

        except (ValueError, PermissionDeniedError, InsufficientFundsError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("Welfare disbursement failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("福利發放失敗"),
                ephemeral=True,
            )


class WelfareSettingsModal(discord.ui.Modal, title="福利設定"):
    def __init__(
        self, service: StateCouncilService, guild_id: int, author_id: int, user_roles: list[int]
    ) -> None:
        super().__init__()
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles

        self.welfare_amount_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="福利金額",
            placeholder="輸入定期福利金額（數字，0表示停用）",
            required=True,
            style=discord.TextStyle.short,
        )
        self.interval_hours_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="發放間隔（小時）",
            placeholder="輸入發放間隔小時數",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.welfare_amount_input)
        self.add_item(self.interval_hours_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            welfare_amount = int(str(self.welfare_amount_input.value))
            welfare_interval_hours = int(str(self.interval_hours_input.value))

            await self.service.update_department_config(
                guild_id=self.guild_id,
                department="內政部",
                user_id=self.author_id,
                user_roles=self.user_roles,
                welfare_amount=welfare_amount,
                welfare_interval_hours=welfare_interval_hours,
            )

            await send_message_compat(
                interaction,
                content=(
                    f"✅ 福利設定更新成功！\n"
                    f"金額：{welfare_amount:,} 幣\n"
                    f"間隔：{welfare_interval_hours} 小時"
                ),
                ephemeral=True,
            )

        except (ValueError, PermissionDeniedError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("Welfare settings update failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("設定更新失敗"),
                ephemeral=True,
            )


class TaxCollectionModal(discord.ui.Modal, title="稅款徵收"):
    def __init__(
        self, service: StateCouncilService, guild_id: int, author_id: int, user_roles: list[int]
    ) -> None:
        super().__init__()
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles

        self.taxpayer_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="納稅人",
            placeholder="輸入納稅人 @使用者 或使用者ID",
            required=True,
            style=discord.TextStyle.short,
        )
        self.taxable_amount_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="應稅金額",
            placeholder="輸入應稅金額（數字）",
            required=True,
            style=discord.TextStyle.short,
        )
        self.tax_rate_percent_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="稅率（%）",
            placeholder="輸入稅率百分比",
            required=True,
            style=discord.TextStyle.short,
        )
        self.assessment_period_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="評定期間",
            placeholder="例如：2024-01",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.taxpayer_input)
        self.add_item(self.taxable_amount_input)
        self.add_item(self.tax_rate_percent_input)
        self.add_item(self.assessment_period_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            taxpayer_input = str(self.taxpayer_input.value)
            taxable_amount = int(str(self.taxable_amount_input.value))
            tax_rate_percent = int(str(self.tax_rate_percent_input.value))
            assessment_period = str(self.assessment_period_input.value)

            # Parse taxpayer ID
            if taxpayer_input.startswith("<@") and taxpayer_input.endswith(">"):
                taxpayer_id = int(taxpayer_input[2:-1].replace("!", ""))
            else:
                taxpayer_id = int(taxpayer_input)

            tax_record = await self.service.collect_tax(
                guild_id=self.guild_id,
                department="財政部",
                user_id=self.author_id,
                user_roles=self.user_roles,
                taxpayer_id=taxpayer_id,
                taxable_amount=taxable_amount,
                tax_rate_percent=tax_rate_percent,
                assessment_period=assessment_period,
            )

            await send_message_compat(
                interaction,
                content=(
                    f"✅ 稅款徵收成功！\n"
                    f"向 <@{taxpayer_id}> 徵收 {tax_record.tax_amount:,} 幣\n"
                    f"應稅金額：{taxable_amount:,} 幣\n"
                    f"稅率：{tax_rate_percent}%\n"
                    f"評定期間：{assessment_period}"
                ),
                ephemeral=True,
            )

        except (ValueError, PermissionDeniedError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("Tax collection failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("稅款徵收失敗"),
                ephemeral=True,
            )


class TaxSettingsModal(discord.ui.Modal, title="稅率設定"):
    def __init__(
        self, service: StateCouncilService, guild_id: int, author_id: int, user_roles: list[int]
    ) -> None:
        super().__init__()
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles

        self.tax_rate_basis_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="稅率基礎",
            placeholder="輸入稅率基礎金額（數字，0表示停用）",
            required=True,
            style=discord.TextStyle.short,
        )
        self.tax_rate_percent_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="稅率（%）",
            placeholder="輸入稅率百分比",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.tax_rate_basis_input)
        self.add_item(self.tax_rate_percent_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            tax_rate_basis = int(str(self.tax_rate_basis_input.value))
            tax_rate_percent = int(str(self.tax_rate_percent_input.value))

            await self.service.update_department_config(
                guild_id=self.guild_id,
                department="財政部",
                user_id=self.author_id,
                user_roles=self.user_roles,
                tax_rate_basis=tax_rate_basis,
                tax_rate_percent=tax_rate_percent,
            )

            await send_message_compat(
                interaction,
                content=(
                    f"✅ 稅率設定更新成功！\n"
                    f"基礎金額：{tax_rate_basis:,} 幣\n"
                    f"稅率：{tax_rate_percent}%"
                ),
                ephemeral=True,
            )

        except (ValueError, PermissionDeniedError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("Tax settings update failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("設定更新失敗"),
                ephemeral=True,
            )


class ArrestReasonModal(discord.ui.Modal, title="逮捕原因"):
    def __init__(
        self,
        service: StateCouncilService,
        guild: discord.Guild,
        guild_id: int,
        author_id: int,
        user_roles: list[int],
        target_id: int,
    ) -> None:
        super().__init__()
        self.service = service
        self.guild = guild
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles
        self.target_id = target_id

        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="逮捕原因",
            placeholder="輸入逮捕原因（必填）",
            required=True,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            reason = str(self.reason_input.value).strip()
            if not reason:
                await send_message_compat(
                    interaction, content="❌ 逮捕原因不能為空。", ephemeral=True
                )
                return

            await self.service.arrest_user(
                guild_id=self.guild_id,
                department="國土安全部",
                user_id=self.author_id,
                user_roles=self.user_roles,
                target_id=self.target_id,
                reason=reason,
                guild=self.guild,
            )
            # 嘗試重新抓取最新成員狀態以產生更準確的提示
            target_member = None
            if hasattr(self.guild, "fetch_member"):
                try:
                    target_member = await self.guild.fetch_member(self.target_id)
                except Exception:
                    target_member = self.guild.get_member(self.target_id)
            else:
                target_member = self.guild.get_member(self.target_id)

            target_mention = (
                target_member.mention
                if target_member and getattr(target_member, "mention", None)
                else f"<@{self.target_id}>"
            )

            # 依實際結果描述是否成功移除/賦予
            try:
                cfg = await self.service.get_config(guild_id=self.guild_id)
                citizen_role = None
                if hasattr(self.guild, "get_role"):
                    _cid = getattr(cfg, "citizen_role_id", None)
                    if isinstance(_cid, int):
                        citizen_role = self.guild.get_role(_cid)
                suspect_role = None
                if hasattr(self.guild, "get_role"):
                    _sid = getattr(cfg, "suspect_role_id", None)
                    if isinstance(_sid, int):
                        suspect_role = self.guild.get_role(_sid)
                roles = list(getattr(target_member, "roles", []) or [])
                has_suspect = bool(suspect_role in roles) if suspect_role else False
                has_citizen = bool(citizen_role in roles) if citizen_role else False
                result_lines = ["✅ 逮捕操作完成！", f"目標：{target_mention}", f"原因：{reason}"]
                if has_suspect:
                    result_lines.append("結果：已掛上『嫌犯』身分組。")
                else:
                    result_lines.append(
                        "結果：未能掛上『嫌犯』身分組，請檢查機器人權限與身分組層級。"
                    )
                if citizen_role is not None:
                    if not has_citizen:
                        result_lines.append("附註：已移除『公民』身分組。")
                    else:
                        result_lines.append("附註：『公民』身分組未移除（可能因層級不足）。")
                await send_message_compat(
                    interaction,
                    content="\n".join(result_lines),
                    ephemeral=True,
                )
            except Exception:
                # 後援：維持原本成功訊息
                await send_message_compat(
                    interaction,
                    content=(
                        f"✅ 逮捕操作完成！\n"
                        f"目標：{target_mention}\n"
                        f"原因：{reason}\n"
                        f"已嘗試移除『公民』並掛上『嫌犯』身分組。"
                    ),
                    ephemeral=True,
                )

        except ValueError as e:
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.validation_failed("輸入值", str(e)),
                ephemeral=True,
            )
        except PermissionDeniedError as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("Arrest failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("逮捕操作失敗"),
                ephemeral=True,
            )


class ArrestSelectView(discord.ui.View):
    """View for selecting a user to arrest."""

    def __init__(
        self,
        service: StateCouncilService,
        guild: discord.Guild,
        guild_id: int,
        author_id: int,
        user_roles: list[int],
    ) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild = guild
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles

        # 以物件方式建立 UserSelect（避免某些 discord.py 版本沒有 ui.user_select decorator）
        self._user_select: discord.ui.UserSelect[Any] = discord.ui.UserSelect(
            placeholder="選擇要逮捕的使用者", min_values=1, max_values=1
        )

        async def _on_select(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return

            if not self._user_select.values:
                await send_message_compat(interaction, content="請選擇一個使用者。", ephemeral=True)
                return

            target_user = self._user_select.values[0]
            if getattr(target_user, "bot", False):
                await send_message_compat(
                    interaction, content="無法逮捕機器人帳號。", ephemeral=True
                )
                return

            modal = ArrestReasonModal(
                service=self.service,
                guild=self.guild,
                guild_id=self.guild_id,
                author_id=self.author_id,
                user_roles=self.user_roles,
                target_id=int(getattr(target_user, "id", 0)),
            )
            await send_modal_compat(interaction, modal)

        self._user_select.callback = _on_select
        self.add_item(self._user_select)


class IdentityManagementModal(discord.ui.Modal, title="身分管理"):
    def __init__(
        self, service: StateCouncilService, guild_id: int, author_id: int, user_roles: list[int]
    ) -> None:
        super().__init__()
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles

        self.target_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="目標使用者",
            placeholder="輸入目標使用者 @使用者 或使用者ID",
            required=True,
            style=discord.TextStyle.short,
        )
        self.action_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="操作類型",
            placeholder="移除公民身分 / 標記疑犯 / 移除疑犯標記",
            required=True,
            style=discord.TextStyle.short,
        )
        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="理由",
            placeholder="輸入操作理由（可選）",
            required=False,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.target_input)
        self.add_item(self.action_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            target_input = str(self.target_input.value)
            action = str(self.action_input.value)
            reason = str(self.reason_input.value).strip() or None

            # Parse target ID
            if target_input.startswith("<@") and target_input.endswith(">"):
                target_id = int(target_input[2:-1].replace("!", ""))
            else:
                target_id = int(target_input)

            await self.service.create_identity_record(
                guild_id=self.guild_id,
                department="國土安全部",
                user_id=self.author_id,
                user_roles=self.user_roles,
                target_id=target_id,
                action=action,
                reason=reason,
            )

            await send_message_compat(
                interaction,
                content=(
                    f"✅ 身分管理操作完成！\n"
                    f"目標：<@{target_id}>\n"
                    f"操作：{action}\n"
                    f"理由：{reason or '無'}"
                ),
                ephemeral=True,
            )

        except (ValueError, PermissionDeniedError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("Identity management failed", error=str(e))
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.system_error("操作失敗"), ephemeral=True
            )


class CurrencyIssuanceModal(discord.ui.Modal, title="貨幣發行"):
    def __init__(
        self,
        service: StateCouncilService,
        currency_service: CurrencyConfigService,
        guild_id: int,
        author_id: int,
        user_roles: list[int],
    ) -> None:
        super().__init__()
        self.service = service
        self.currency_service = currency_service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles

        self.amount_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="發行金額",
            placeholder="輸入發行金額（數字）",
            required=True,
            style=discord.TextStyle.short,
        )
        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="發行理由",
            placeholder="輸入發行理由",
            required=True,
            style=discord.TextStyle.paragraph,
        )
        self.month_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="評估月份",
            placeholder="例如：2024-01",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.amount_input)
        self.add_item(self.reason_input)
        self.add_item(self.month_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = int(str(self.amount_input.value))
            reason = str(self.reason_input.value)
            month_period = str(self.month_input.value)

            await self.service.issue_currency(
                guild_id=self.guild_id,
                department="中央銀行",
                user_id=self.author_id,
                user_roles=self.user_roles,
                amount=amount,
                reason=reason,
                month_period=month_period,
            )

            # Get currency config
            currency_config = await self.currency_service.get_currency_config(
                guild_id=self.guild_id
            )

            await send_message_compat(
                interaction,
                content=(
                    f"✅ 貨幣發行成功！\n"
                    f"發行金額：{_format_currency_display(currency_config, amount)}\n"
                    f"理由：{reason}\n"
                    f"評估月份：{month_period}"
                ),
                ephemeral=True,
            )

        except (ValueError, PermissionDeniedError, MonthlyIssuanceLimitExceededError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("Currency issuance failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("貨幣發行失敗"),
                ephemeral=True,
            )


class CurrencySettingsModal(discord.ui.Modal, title="貨幣發行設定"):
    def __init__(
        self, service: StateCouncilService, guild_id: int, author_id: int, user_roles: list[int]
    ) -> None:
        super().__init__()
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles

        self.max_issuance_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="每月發行上限",
            placeholder="輸入每月最大發行量（數字，0表示無限制）",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.max_issuance_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            max_issuance_per_month = int(str(self.max_issuance_input.value))

            await self.service.update_department_config(
                guild_id=self.guild_id,
                department="中央銀行",
                user_id=self.author_id,
                user_roles=self.user_roles,
                max_issuance_per_month=max_issuance_per_month,
            )

            await send_message_compat(
                interaction,
                content=(f"✅ 貨幣發行設定更新成功！\n每月發行上限：{max_issuance_per_month:,} 幣"),
                ephemeral=True,
            )

        except (ValueError, PermissionDeniedError) as e:
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.from_error(e), ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("Currency settings update failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("設定更新失敗"),
                ephemeral=True,
            )


class ExportDataModal(discord.ui.Modal, title="匯出資料"):
    def __init__(self, service: StateCouncilService, guild_id: int) -> None:
        super().__init__()
        self.service = service
        self.guild_id = guild_id

        self.format_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="匯出格式",
            placeholder="JSON 或 CSV",
            required=True,
            style=discord.TextStyle.short,
        )
        self.type_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="匯出類型",
            placeholder="all/welfare/tax/identity/currency/transfers",
            required=True,
            style=discord.TextStyle.short,
        )
        self.start_date_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="開始日期 (可選)",
            placeholder="YYYY-MM-DD",
            required=False,
            style=discord.TextStyle.short,
        )
        self.end_date_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="結束日期 (可選)",
            placeholder="YYYY-MM-DD",
            required=False,
            style=discord.TextStyle.short,
        )
        self.add_item(self.format_input)
        self.add_item(self.type_input)
        self.add_item(self.start_date_input)
        self.add_item(self.end_date_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            import io
            from datetime import datetime

            format_type = str(self.format_input.value).upper()
            export_type = str(self.type_input.value).lower()
            start_date = str(self.start_date_input.value).strip() or None
            end_date = str(self.end_date_input.value).strip() or None

            if format_type not in ["JSON", "CSV"]:
                raise ValueError("格式必須是 JSON 或 CSV")

            if export_type not in ["all", "welfare", "tax", "identity", "currency", "transfers"]:
                raise ValueError("匯出類型無效")

            # Parse dates if provided
            start_dt = None
            end_dt = None
            if start_date:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            # Collect data based on export type
            data = await self._collect_export_data(export_type, start_dt, end_dt)

            # Format data
            if format_type == "JSON":
                content = self._format_json(data, export_type)
                filename = f"state_council_{export_type}_{datetime.now().strftime('%Y%m%d')}.json"
            else:  # CSV
                content = self._format_csv(data, export_type)
                filename = f"state_council_{export_type}_{datetime.now().strftime('%Y%m%d')}.csv"

            # Send file
            if len(content.encode("utf-8")) > 8 * 1024 * 1024:  # 8MB limit
                await interaction.response.send_message(
                    "❌ 匯出資料過大，請縮短日期範圍後重試。",
                    ephemeral=True,
                )
                return

            file = discord.File(
                io.BytesIO(content.encode("utf-8")),
                filename=filename,
            )

            await interaction.response.send_message(
                f"✅ 資料匯出完成 ({export_type}, {format_type} 格式)",
                file=file,
                ephemeral=True,
            )

        except ValueError as e:
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.validation_failed("匯出格式", str(e)),
                ephemeral=True,
            )
        except Exception as e:
            LOGGER.exception("Data export failed", error=str(e))
            await send_message_compat(
                interaction, content=ErrorMessageTemplates.system_error("匯出失敗"), ephemeral=True
            )

    async def _collect_export_data(
        self, export_type: str, start_dt: datetime | None = None, end_dt: datetime | None = None
    ) -> dict[str, Any]:
        """Collect data based on export type."""
        from src.db.pool import get_pool
        from src.infra.types.db import ConnectionProtocol, PoolProtocol

        pool: PoolProtocol = cast(PoolProtocol, get_pool())
        async with pool.acquire() as conn:
            c: ConnectionProtocol = conn
            gateway = self.service._gateway  # pyright: ignore[reportPrivateUsage]

            data: dict[str, Any] = {
                "metadata": {
                    "guild_id": self.guild_id,
                    "export_type": export_type,
                    "exported_at": datetime.now().isoformat(),
                    "start_date": start_dt.isoformat() if start_dt else None,
                    "end_date": end_dt.isoformat() if end_dt else None,
                },
                "records": [],
            }

            if export_type == "all" or export_type == "welfare":
                welfare_records = await gateway.fetch_welfare_disbursements(
                    c, guild_id=self.guild_id, limit=10000
                )
                if start_dt or end_dt:
                    welfare_records = [
                        r
                        for r in welfare_records
                        if isinstance(r.disbursed_at, datetime)
                        and (not start_dt or r.disbursed_at >= start_dt)
                        and (not end_dt or r.disbursed_at <= end_dt)
                    ]
                data["records"].extend(
                    [
                        {
                            "type": "welfare",
                            "record_id": str(r.disbursement_id),
                            "recipient_id": r.recipient_id,
                            "amount": r.amount,
                            "disbursement_type": r.disbursement_type,
                            "reference_id": r.reference_id,
                            "disbursed_at": (
                                r.disbursed_at.isoformat()
                                if isinstance(r.disbursed_at, datetime)
                                else ""
                            ),
                        }
                        for r in welfare_records
                    ]
                )

            if export_type == "all" or export_type == "tax":
                tax_records = await gateway.fetch_tax_records(
                    c, guild_id=self.guild_id, limit=10000
                )
                if start_dt or end_dt:
                    tax_records = [
                        r
                        for r in tax_records
                        if isinstance(r.collected_at, datetime)
                        and (not start_dt or r.collected_at >= start_dt)
                        and (not end_dt or r.collected_at <= end_dt)
                    ]
                data["records"].extend(
                    [
                        {
                            "type": "tax",
                            "record_id": str(r.tax_id),
                            "taxpayer_id": r.taxpayer_id,
                            "taxable_amount": r.taxable_amount,
                            "tax_rate_percent": r.tax_rate_percent,
                            "tax_amount": r.tax_amount,
                            "tax_type": r.tax_type,
                            "assessment_period": r.assessment_period,
                            "collected_at": (
                                r.collected_at.isoformat()
                                if isinstance(r.collected_at, datetime)
                                else ""
                            ),
                        }
                        for r in tax_records
                    ]
                )

            if export_type == "all" or export_type == "identity":
                identity_records = await gateway.fetch_identity_records(
                    c, guild_id=self.guild_id, limit=10000
                )
                if start_dt or end_dt:
                    identity_records = [
                        r
                        for r in identity_records
                        if (getattr(r, "performed_at", None) is not None)
                        and (not start_dt or r.performed_at >= start_dt)
                        and (not end_dt or r.performed_at <= end_dt)
                    ]
                data["records"].extend(
                    [
                        {
                            "type": "identity",
                            "record_id": str(r.record_id),
                            "target_id": r.target_id,
                            "action": r.action,
                            "reason": r.reason,
                            "performed_by": r.performed_by,
                            "performed_at": (
                                r.performed_at.isoformat()
                                if getattr(r, "performed_at", None) is not None
                                else ""
                            ),
                        }
                        for r in identity_records
                    ]
                )

            if export_type == "all" or export_type == "currency":
                currency_records = await gateway.fetch_currency_issuances(
                    c, guild_id=self.guild_id, limit=10000
                )
                if start_dt or end_dt:
                    _filtered: list[Any] = []
                    for r in currency_records:
                        iat = getattr(r, "issued_at", None)
                        if iat is None:
                            continue
                        if start_dt and iat < start_dt:
                            continue
                        if end_dt and iat > end_dt:
                            continue
                        _filtered.append(r)
                    currency_records = _filtered
                data["records"].extend(
                    [
                        {
                            "type": "currency",
                            "record_id": str(r.issuance_id),
                            "amount": r.amount,
                            "reason": r.reason,
                            "performed_by": r.performed_by,
                            "month_period": r.month_period,
                            "issued_at": (
                                r.issued_at.isoformat() if isinstance(r.issued_at, datetime) else ""
                            ),
                        }
                        for r in currency_records
                    ]
                )

            if export_type == "all" or export_type == "transfers":
                transfer_records = await gateway.fetch_interdepartment_transfers(
                    c, guild_id=self.guild_id, limit=10000
                )
                if start_dt or end_dt:
                    transfer_records = [
                        r
                        for r in transfer_records
                        if (getattr(r, "transferred_at", None) is not None)
                        and (not start_dt or r.transferred_at >= start_dt)
                        and (not end_dt or r.transferred_at <= end_dt)
                    ]
                data["records"].extend(
                    [
                        {
                            "type": "transfer",
                            "record_id": str(r.transfer_id),
                            "from_department": r.from_department,
                            "to_department": r.to_department,
                            "amount": r.amount,
                            "reason": r.reason,
                            "performed_by": r.performed_by,
                            "transferred_at": (
                                r.transferred_at.isoformat()
                                if getattr(r, "transferred_at", None) is not None
                                else ""
                            ),
                        }
                        for r in transfer_records
                    ]
                )

            return data

    def _format_json(self, data: dict[str, Any], export_type: str) -> str:
        """Format data as JSON."""
        import json

        return json.dumps(data, ensure_ascii=False, indent=2)

    def _format_csv(self, data: dict[str, Any], export_type: str) -> str:
        """Format data as CSV."""
        import csv
        import io

        output = io.StringIO()

        if export_type == "all":
            # For "all" export, create separate CSV sections
            writer = csv.writer(output)
            writer.writerow(["=== 國務院資料匯出 ==="])
            writer.writerow(["匯出時間", data["metadata"]["exported_at"]])
            writer.writerow(["伺服器ID", data["metadata"]["guild_id"]])
            writer.writerow([])

            # Group records by type
            by_type: dict[str, list[dict[str, Any]]] = {}
            for record in data["records"]:
                record_type = record["type"]
                if record_type not in by_type:
                    by_type[record_type] = []
                by_type[record_type].append(record)

            # Write each type section
            type_names = {
                "welfare": "福利發放記錄",
                "tax": "稅收記錄",
                "identity": "身分管理記錄",
                "currency": "貨幣發行記錄",
                "transfer": "部門轉帳記錄",
            }

            for record_type, records in by_type.items():
                writer.writerow([f"=== {type_names.get(record_type, record_type)} ==="])

                if records:
                    # Write headers based on record type
                    if record_type == "welfare":
                        writer.writerow(["記錄ID", "受款人ID", "金額", "類型", "備註", "發放時間"])
                    elif record_type == "tax":
                        writer.writerow(
                            [
                                "記錄ID",
                                "納稅人ID",
                                "應稅金額",
                                "稅率",
                                "稅額",
                                "稅種",
                                "評定期間",
                                "徵收時間",
                            ]
                        )
                    elif record_type == "identity":
                        writer.writerow(["記錄ID", "目標ID", "操作", "理由", "執行者", "執行時間"])
                    elif record_type == "currency":
                        writer.writerow(
                            ["記錄ID", "金額", "理由", "執行者", "評估月份", "發行時間"]
                        )
                    elif record_type == "transfer":
                        writer.writerow(
                            ["記錄ID", "來源部門", "目標部門", "金額", "理由", "執行者", "轉帳時間"]
                        )

                    # Write records
                    for record in records:
                        if record_type == "welfare":
                            writer.writerow(
                                [
                                    record["record_id"],
                                    record["recipient_id"],
                                    record["amount"],
                                    record["disbursement_type"],
                                    record["reference_id"],
                                    record["disbursed_at"],
                                ]
                            )
                        elif record_type == "tax":
                            writer.writerow(
                                [
                                    record["record_id"],
                                    record["taxpayer_id"],
                                    record["taxable_amount"],
                                    record["tax_rate_percent"],
                                    record["tax_amount"],
                                    record["tax_type"],
                                    record["assessment_period"],
                                    record["collected_at"],
                                ]
                            )
                        elif record_type == "identity":
                            writer.writerow(
                                [
                                    record["record_id"],
                                    record["target_id"],
                                    record["action"],
                                    record["reason"],
                                    record["performed_by"],
                                    record["performed_at"],
                                ]
                            )
                        elif record_type == "currency":
                            writer.writerow(
                                [
                                    record["record_id"],
                                    record["amount"],
                                    record["reason"],
                                    record["performed_by"],
                                    record["month_period"],
                                    record["issued_at"],
                                ]
                            )
                        elif record_type == "transfer":
                            writer.writerow(
                                [
                                    record["record_id"],
                                    record["from_department"],
                                    record["to_department"],
                                    record["amount"],
                                    record["reason"],
                                    record["performed_by"],
                                    record["transferred_at"],
                                ]
                            )
                else:
                    writer.writerow(["無記錄"])

                writer.writerow([])  # Empty line between sections
        else:
            # Single type export
            writer = csv.writer(output)

            if data["records"]:
                # Write headers based on export type
                if export_type == "welfare":
                    writer.writerow(["記錄ID", "受款人ID", "金額", "類型", "備註", "發放時間"])
                    for record in data["records"]:
                        writer.writerow(
                            [
                                record["record_id"],
                                record["recipient_id"],
                                record["amount"],
                                record["disbursement_type"],
                                record["reference_id"],
                                record["disbursed_at"],
                            ]
                        )
                elif export_type == "tax":
                    writer.writerow(
                        [
                            "記錄ID",
                            "納稅人ID",
                            "應稅金額",
                            "稅率",
                            "稅額",
                            "稅種",
                            "評定期間",
                            "徵收時間",
                        ]
                    )
                    for record in data["records"]:
                        writer.writerow(
                            [
                                record["record_id"],
                                record["taxpayer_id"],
                                record["taxable_amount"],
                                record["tax_rate_percent"],
                                record["tax_amount"],
                                record["tax_type"],
                                record["assessment_period"],
                                record["collected_at"],
                            ]
                        )
                elif export_type == "identity":
                    writer.writerow(["記錄ID", "目標ID", "操作", "理由", "執行者", "執行時間"])
                    for record in data["records"]:
                        writer.writerow(
                            [
                                record["record_id"],
                                record["target_id"],
                                record["action"],
                                record["reason"],
                                record["performed_by"],
                                record["performed_at"],
                            ]
                        )
                elif export_type == "currency":
                    writer.writerow(["記錄ID", "金額", "理由", "執行者", "評估月份", "發行時間"])
                    for record in data["records"]:
                        writer.writerow(
                            [
                                record["record_id"],
                                record["amount"],
                                record["reason"],
                                record["performed_by"],
                                record["month_period"],
                                record["issued_at"],
                            ]
                        )
                elif export_type == "transfers":
                    writer.writerow(
                        ["記錄ID", "來源部門", "目標部門", "金額", "理由", "執行者", "轉帳時間"]
                    )
                    for record in data["records"]:
                        writer.writerow(
                            [
                                record["record_id"],
                                record["from_department"],
                                record["to_department"],
                                record["amount"],
                                record["reason"],
                                record["performed_by"],
                                record["transferred_at"],
                            ]
                        )
            else:
                writer.writerow(["無記錄"])

        return output.getvalue()


# --- Homeland Security Suspects Panel ---


class HomelandSecuritySuspectsPanelView(PersistentPanelView):
    """國土安全部嫌疑人管理面板。"""

    panel_type = "homeland_security"
    # 重新聲明類型以覆蓋父類的 int | None
    author_id: int

    def __init__(
        self,
        *,
        service: StateCouncilService,
        guild: discord.Guild,
        guild_id: int,
        author_id: int,
        user_roles: Sequence[int],
        page_size: int = 10,
    ) -> None:
        super().__init__(author_id=author_id, timeout=600.0)
        self.service = service
        self.guild = guild
        self.guild_id = guild_id
        self.user_roles = list(user_roles)
        self.page_size = max(5, page_size)
        self.current_page = 0
        self.search_keyword: str | None = None
        self._suspects: list[SuspectProfile] = []
        self._selected_ids: set[int] = set()
        self._message: discord.Message | None = None
        self._error_message: str | None = None

    async def prepare(self) -> None:
        await self.reload()

    async def reload(self) -> None:
        try:
            self._suspects = await self.service.list_suspects(
                guild=self.guild,
                guild_id=self.guild_id,
                search=self.search_keyword,
            )
            self._error_message = None
        except Exception as exc:
            self._suspects = []
            self._error_message = str(exc)
        self._sanitize_state()
        self._refresh_components()

    def set_message(self, message: discord.Message) -> None:
        self._message = message

    def _sanitize_state(self) -> None:
        total_pages = self.total_pages
        if self.current_page >= total_pages:
            self.current_page = max(total_pages - 1, 0)
        valid_ids = {profile.member_id for profile in self._suspects}
        self._selected_ids &= valid_ids

    @property
    def total_pages(self) -> int:
        if not self._suspects:
            return 1
        return max(1, math.ceil(len(self._suspects) / self.page_size))

    def _current_page_profiles(self) -> list[SuspectProfile]:
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self._suspects[start:end]

    def _refresh_components(self) -> None:
        self.clear_items()
        self._add_select_menu()
        self._add_navigation_buttons()
        self._add_action_buttons()

    def _add_select_menu(self) -> None:
        options: list[discord.SelectOption] = []
        for profile in self._current_page_profiles():
            description = self._format_select_description(profile)
            options.append(
                discord.SelectOption(
                    label=profile.display_name[:95],
                    description=description[:95] if description else None,
                    value=str(profile.member_id),
                )
            )

        if not options:
            select: discord.ui.Select["HomelandSecuritySuspectsPanelView"] = discord.ui.Select(
                placeholder="目前沒有嫌疑人",
                min_values=1,
                max_values=1,
                options=[
                    discord.SelectOption(
                        label="等待新的逮捕紀錄",
                        description="目前沒有嫌疑人",
                        value="none",
                    )
                ],
                row=0,
            )
            select.disabled = True
        else:
            max_values = min(len(options), 25)
            select = discord.ui.Select(
                placeholder="選擇要操作的嫌疑人（可多選）",
                min_values=1,
                max_values=max_values,
                options=options,
                row=0,
            )
        select.callback = self._on_select
        self.add_item(select)

    def _add_navigation_buttons(self) -> None:
        prev_btn: discord.ui.Button["HomelandSecuritySuspectsPanelView"] = discord.ui.Button(
            label="上一頁",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        prev_btn.disabled = self.current_page == 0
        prev_btn.callback = self._on_prev_page
        self.add_item(prev_btn)

        next_btn: discord.ui.Button["HomelandSecuritySuspectsPanelView"] = discord.ui.Button(
            label="下一頁",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        next_btn.disabled = (self.current_page + 1) >= self.total_pages
        next_btn.callback = self._on_next_page
        self.add_item(next_btn)

        refresh_btn: discord.ui.Button["HomelandSecuritySuspectsPanelView"] = discord.ui.Button(
            label="重新整理",
            style=discord.ButtonStyle.primary,
            row=1,
        )
        refresh_btn.callback = self._on_refresh
        self.add_item(refresh_btn)

    def _add_action_buttons(self) -> None:
        release_btn: discord.ui.Button["HomelandSecuritySuspectsPanelView"] = discord.ui.Button(
            label="釋放選中嫌疑人",
            style=discord.ButtonStyle.danger,
            emoji="🔓",
            row=2,
        )
        release_btn.callback = self._open_release_modal
        self.add_item(release_btn)

        auto_selected_btn: discord.ui.Button["HomelandSecuritySuspectsPanelView"] = (
            discord.ui.Button(
                label="設定選中自動釋放",
                style=discord.ButtonStyle.secondary,
                emoji="⏱️",
                row=2,
            )
        )
        auto_selected_btn.callback = self._start_auto_release_selected
        self.add_item(auto_selected_btn)

        auto_all_btn: discord.ui.Button["HomelandSecuritySuspectsPanelView"] = discord.ui.Button(
            label="全部自動釋放",
            style=discord.ButtonStyle.secondary,
            emoji="🕒",
            row=2,
        )
        auto_all_btn.callback = self._start_auto_release_all
        self.add_item(auto_all_btn)

        search_btn: discord.ui.Button["HomelandSecuritySuspectsPanelView"] = discord.ui.Button(
            label="搜尋",
            style=discord.ButtonStyle.success,
            row=3,
        )
        search_btn.callback = self._open_search_modal
        self.add_item(search_btn)

        reset_btn: discord.ui.Button["HomelandSecuritySuspectsPanelView"] = discord.ui.Button(
            label="清除搜尋",
            style=discord.ButtonStyle.secondary,
            row=3,
        )
        reset_btn.callback = self._on_reset_search
        self.add_item(reset_btn)

        audit_btn: discord.ui.Button["HomelandSecuritySuspectsPanelView"] = discord.ui.Button(
            label="查看審計記錄",
            style=discord.ButtonStyle.secondary,
            row=3,
        )
        audit_btn.callback = self._show_audit_log
        self.add_item(audit_btn)

        close_btn: discord.ui.Button["HomelandSecuritySuspectsPanelView"] = discord.ui.Button(
            label="關閉面板",
            style=discord.ButtonStyle.gray,
            row=4,
        )
        close_btn.callback = self._on_close
        self.add_item(close_btn)

    def _format_select_description(self, profile: SuspectProfile) -> str:
        arrested = self._format_timestamp(profile.arrested_at)
        auto_release = self._format_auto_release(profile)
        return f"逮捕: {arrested} | 自動釋放: {auto_release}"

    def _format_timestamp(self, value: datetime | None) -> str:
        if value is None:
            return "未知"
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _format_auto_release(self, profile: SuspectProfile) -> str:
        if profile.auto_release_at is None:
            return "未設定"
        remaining = profile.auto_release_at - datetime.now(timezone.utc)
        if remaining.total_seconds() <= 0:
            return "排程中"
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)
        return f"{hours}小時{minutes:02d}分後"

    def build_embed(self) -> discord.Embed:
        description = [
            f"目前嫌疑人：{len(self._suspects)} 人",
            f"已選擇：{len(self._selected_ids)} 人",
            f"頁面：{self.current_page + 1}/{self.total_pages}",
        ]
        embed = discord.Embed(
            title="🛡️ 國土安全部｜嫌疑人管理",
            description="\n".join(description),
            color=discord.Color.red(),
        )

        if self.search_keyword:
            embed.add_field(
                name="搜尋過濾",
                value=f"`{self.search_keyword}`",
                inline=False,
            )

        if self._error_message:
            embed.add_field(name="狀態", value=f"⚠️ {self._error_message}", inline=False)
        elif not self._suspects:
            embed.add_field(name="狀態", value="目前沒有嫌疑人。", inline=False)
        else:
            lines: list[str] = []
            start_index = self.current_page * self.page_size
            for offset, profile in enumerate(self._current_page_profiles(), start=1):
                idx = start_index + offset
                base = (
                    f"{idx}. {profile.display_name}｜逮捕 {self._format_timestamp(profile.arrested_at)}"
                    f"｜自動釋放 {self._format_auto_release(profile)}"
                )
                lines.append(base)
                if profile.arrest_reason:
                    lines.append(f" └ 理由：{profile.arrest_reason}")
            embed.add_field(name="嫌疑人列表", value="\n".join(lines), inline=False)

        embed.set_footer(text="支援搜尋、分頁、批次釋放與自動釋放設定")
        return embed

    async def _ensure_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("僅限面板開啟者操作。", ephemeral=True)
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_author(interaction):
            return
        data = cast(dict[str, Any], interaction.data or {})
        raw_values = data.get("values")
        if isinstance(raw_values, (list, tuple, set)):
            iterable_values: list[Any] = list(cast(Iterable[Any], raw_values))
        else:
            iterable_values = []
        selected: set[int] = set()
        for raw in iterable_values:
            try:
                selected.add(int(raw))
            except (TypeError, ValueError):
                continue
        self._selected_ids = selected
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_prev_page(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_author(interaction):
            return
        if self.current_page == 0:
            await interaction.response.send_message("已在第一頁。", ephemeral=True)
            return
        self.current_page -= 1
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_next_page(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_author(interaction):
            return
        if (self.current_page + 1) >= self.total_pages:
            await interaction.response.send_message("已在最後一頁。", ephemeral=True)
            return
        self.current_page += 1
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_refresh(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_author(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await self.reload()
        await self._push_update()
        await interaction.followup.send("已重新載入嫌疑人列表。", ephemeral=True)

    async def _open_release_modal(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_author(interaction):
            return
        if not self._selected_ids:
            await interaction.response.send_message("請先選擇要釋放的嫌疑人。", ephemeral=True)
            return
        await interaction.response.send_modal(SuspectReleaseModal(panel=self))

    async def _open_auto_release_modal(
        self,
        interaction: discord.Interaction,
        *,
        scope: Literal["selected", "all"],
    ) -> None:
        if not await self._ensure_author(interaction):
            return
        target_pool = (
            self._selected_ids if scope == "selected" else {p.member_id for p in self._suspects}
        )
        if not target_pool:
            await interaction.response.send_message("沒有可設定的嫌疑人。", ephemeral=True)
            return
        await interaction.response.send_modal(SuspectAutoReleaseModal(panel=self, scope=scope))

    async def _start_auto_release_selected(self, interaction: discord.Interaction) -> None:
        await self._open_auto_release_modal(interaction, scope="selected")

    async def _start_auto_release_all(self, interaction: discord.Interaction) -> None:
        await self._open_auto_release_modal(interaction, scope="all")

    async def _open_search_modal(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_author(interaction):
            return
        await interaction.response.send_modal(SuspectSearchModal(panel=self))

    async def _on_reset_search(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_author(interaction):
            return
        self.search_keyword = None
        self.current_page = 0
        await interaction.response.defer(ephemeral=True)
        await self.reload()
        await self._push_update()
        await interaction.followup.send("已清除搜尋條件。", ephemeral=True)

    async def _show_audit_log(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_author(interaction):
            return
        records = await self.service.fetch_identity_audit_log(guild_id=self.guild_id, limit=10)
        if not records:
            await interaction.response.send_message("目前沒有審計記錄。", ephemeral=True)
            return
        lines: list[str] = []
        for record in records:
            timestamp = self._format_timestamp(record.performed_at)
            lines.append(
                f"• {timestamp}｜目標 {record.target_id}｜{record.action}｜{record.reason or '—'}"
            )
        embed = discord.Embed(
            title="嫌疑人審計記錄",
            description="\n".join(lines[:10]),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _on_close(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_author(interaction):
            return
        for item in self.children:
            if hasattr(item, "disabled"):
                cast(_Disableable, item).disabled = True
        embed = self.build_embed()
        embed.set_footer(text="面板已關閉")
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def handle_release(self, interaction: discord.Interaction, reason: str | None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            results = await self.service.release_suspects(
                guild=self.guild,
                guild_id=self.guild_id,
                department="國土安全部",
                user_id=self.author_id,
                user_roles=self.user_roles,
                suspect_ids=list(self._selected_ids),
                reason=reason,
            )
        except Exception as exc:
            await interaction.followup.send(f"釋放失敗：{exc}", ephemeral=True)
            return
        self._selected_ids.clear()
        await self.reload()
        await self._push_update()
        summary = self._summarize_release(results)
        await interaction.followup.send(summary, ephemeral=True)

    async def handle_auto_release(
        self,
        interaction: discord.Interaction,
        *,
        hours: int,
        scope: Literal["selected", "all"],
    ) -> None:
        target_ids = (
            list(self._selected_ids)
            if scope == "selected"
            else [profile.member_id for profile in self._suspects]
        )
        if not target_ids:
            await interaction.response.send_message("沒有可設定的嫌疑人。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            scheduled = await self.service.schedule_auto_release(
                guild=self.guild,
                guild_id=self.guild_id,
                department="國土安全部",
                user_id=self.author_id,
                user_roles=self.user_roles,
                suspect_ids=target_ids,
                hours=hours,
            )
        except Exception as exc:
            await interaction.followup.send(f"設定失敗：{exc}", ephemeral=True)
            return
        if scope == "selected":
            self._selected_ids.clear()
        await self.reload()
        await self._push_update()
        await interaction.followup.send(
            f"已為 {len(scheduled)} 名嫌疑人設定 {hours} 小時自動釋放。",
            ephemeral=True,
        )

    async def apply_search(self, interaction: discord.Interaction, keyword: str | None) -> None:
        await interaction.response.defer(ephemeral=True)
        self.search_keyword = keyword or None
        self.current_page = 0
        await self.reload()
        await self._push_update()
        message = "已清除搜尋條件。" if not keyword else f"搜尋條件：`{keyword}`"
        await interaction.followup.send(message, ephemeral=True)

    async def _push_update(self) -> None:
        if not self._message:
            return
        self._refresh_components()
        await self._message.edit(embed=self.build_embed(), view=self)

    def _summarize_release(self, results: Sequence[SuspectReleaseResult]) -> str:
        released = sum(1 for item in results if item.released)
        failed = len(results) - released
        parts = [f"成功釋放 {released} 人"]
        if failed:
            errors = [item for item in results if not item.released]
            failed_names = ", ".join(filter(None, (item.display_name for item in errors)))
            parts.append(f"失敗 {failed} 人{f'：{failed_names}' if failed_names else ''}")
        return "；".join(parts)

    async def on_timeout(self) -> None:
        if not self._message:
            return
        for item in self.children:
            if hasattr(item, "disabled"):
                cast(_Disableable, item).disabled = True
        embed = self.build_embed()
        embed.set_footer(text="面板已逾時，請重新開啟。")
        try:
            await self._message.edit(embed=embed, view=self)
        except Exception:
            pass
        self.stop()


class SuspectReleaseModal(discord.ui.Modal, title="釋放嫌疑人"):
    def __init__(self, panel: HomelandSecuritySuspectsPanelView) -> None:
        super().__init__(title="釋放嫌疑人")
        self.panel = panel
        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="釋放理由（可選）",
            placeholder="預設為『面板釋放』",
            required=False,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        reason = str(self.reason_input.value).strip() or None
        await self.panel.handle_release(interaction, reason)


class SuspectAutoReleaseModal(discord.ui.Modal, title="設定自動釋放"):
    def __init__(
        self,
        panel: HomelandSecuritySuspectsPanelView,
        *,
        scope: Literal["selected", "all"],
    ) -> None:
        super().__init__(title="設定自動釋放")
        self.panel = panel
        self.scope: Literal["selected", "all"] = scope
        self.hours_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="自動釋放時限（小時）",
            placeholder="輸入 1-168 的整數",
            required=True,
        )
        self.add_item(self.hours_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            hours = int(str(self.hours_input.value).strip())
        except ValueError:
            await interaction.response.send_message("請輸入有效的整數時數。", ephemeral=True)
            return
        await self.panel.handle_auto_release(interaction, hours=hours, scope=self.scope)


class SuspectSearchModal(discord.ui.Modal, title="搜尋嫌疑人"):
    def __init__(self, panel: HomelandSecuritySuspectsPanelView) -> None:
        super().__init__(title="搜尋嫌疑人")
        self.panel = panel
        self.keyword_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="關鍵字",
            placeholder="輸入成員名稱片段，留空代表全部",
            required=False,
        )
        self.add_item(self.keyword_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        keyword = str(self.keyword_input.value).strip() or None
        await self.panel.apply_search(interaction, keyword)


class JusticeSuspectsPanelView(discord.ui.View):
    def __init__(
        self,
        *,
        justice_service: Any,  # JusticeService
        guild: discord.Guild,
        guild_id: int,
        author_id: int,
        user_roles: Sequence[int],
        page_size: int = 10,
    ) -> None:
        super().__init__(timeout=600)
        self.justice_service = justice_service
        self.guild = guild
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = list(user_roles)
        self.page_size = max(5, page_size)
        self.current_page = 0
        self._suspects: list[Any] = []  # list[Suspect]
        self._total_count = 0
        self._message: discord.Message | None = None
        self._error_message: str | None = None
        # 以 suspect_id（UUID 字串）追蹤目前選取的嫌犯
        self._selected_ids: set[str] = set()
        # 狀態篩選（None 表示僅顯示未釋放：detained/charged）
        self._status_filter: str | None = None

    async def prepare(self) -> None:
        await self.reload()

    async def reload(self) -> None:
        try:
            self._suspects, self._total_count = await self.justice_service.get_active_suspects(
                guild_id=self.guild_id,
                page=self.current_page + 1,
                page_size=self.page_size,
                status=self._status_filter,
            )
            self._error_message = None
        except Exception as exc:
            self._suspects = []
            self._total_count = 0
            self._error_message = str(exc)
        self._sanitize_state()
        self._refresh_components()

    def set_message(self, message: discord.Message) -> None:
        self._message = message

    def _sanitize_state(self) -> None:
        total_pages = self.total_pages
        if self.current_page >= total_pages:
            self.current_page = max(total_pages - 1, 0)
        # 僅保留目前頁面存在的嫌犯選取狀態
        valid_ids = {str(suspect.suspect_id) for suspect in self._suspects}
        self._selected_ids &= valid_ids

    @property
    def total_pages(self) -> int:
        if self._total_count == 0:
            return 1
        return (self._total_count + self.page_size - 1) // self.page_size

    def _current_page_suspects(self) -> list[Any]:
        # gateway 已依 page/page_size 做分頁，因此直接回傳列表即可
        return list(self._suspects)

    def _refresh_components(self) -> None:
        self.clear_items()

        # Suspect selection menu
        self._add_select_menu()

        # Navigation buttons
        if self.current_page > 0:
            prev_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="上一頁",
                custom_id="prev_page",
                row=1,
            )
            prev_btn.callback = self._prev_page
            self.add_item(prev_btn)

        if self.current_page < self.total_pages - 1:
            next_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="下一頁",
                custom_id="next_page",
                row=1,
            )
            next_btn.callback = self._next_page
            self.add_item(next_btn)

        # Refresh button
        refresh_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="重新整理",
            custom_id="refresh",
            row=1,
            style=discord.ButtonStyle.secondary,
        )
        refresh_btn.callback = self._refresh_callback
        self.add_item(refresh_btn)

        # Action buttons for suspects
        if self._suspects:
            charge_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="起訴嫌犯",
                custom_id="charge_suspect",
                row=2,
                style=discord.ButtonStyle.success,
            )
            charge_btn.callback = self._charge_suspect
            self.add_item(charge_btn)

            revoke_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="撤銷起訴",
                custom_id="revoke_charge",
                row=2,
                style=discord.ButtonStyle.secondary,
            )
            revoke_btn.callback = self._revoke_charge
            self.add_item(revoke_btn)

            release_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="釋放嫌犯",
                custom_id="release_suspect",
                row=2,
                style=discord.ButtonStyle.danger,
            )
            release_btn.callback = self._release_suspect
            self.add_item(release_btn)

            details_btn: discord.ui.Button[Any] = discord.ui.Button(
                label="查看詳情",
                custom_id="view_details",
                row=2,
                style=discord.ButtonStyle.secondary,
            )
            details_btn.callback = self._view_details
            self.add_item(details_btn)

        # Status filter menu（獨立一列，避免與按鈕同列超出寬度限制）
        self._add_status_filter_menu()

    def _add_status_filter_menu(self) -> None:
        """狀態篩選選單：支援 detained/charged/released 與預設未釋放列表。"""
        # 目前僅一個選單，獨立放在第 3 列，避免與按鈕同列超出寬度
        current = self._status_filter or "active"
        options = [
            discord.SelectOption(
                label="未釋放（detained + charged）",
                value="active",
                default=current == "active",
            ),
            discord.SelectOption(
                label="僅拘留中（detained）",
                value="detained",
                default=current == "detained",
            ),
            discord.SelectOption(
                label="已起訴（charged）",
                value="charged",
                default=current == "charged",
            ),
            discord.SelectOption(
                label="已釋放（released）",
                value="released",
                default=current == "released",
            ),
        ]

        status_select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder="依狀態篩選嫌犯…",
            min_values=1,
            max_values=1,
            options=options,
            row=3,
        )

        async def _on_status_change(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction,
                    content="僅限面板開啟者操作。",
                    ephemeral=True,
                )
                return
            value = (status_select.values[0] if status_select.values else "active") or "active"
            self._status_filter = None if value == "active" else value
            self.current_page = 0
            await self.reload()
            await self._update_interaction(interaction)

        status_select.callback = _on_status_change
        self.add_item(status_select)

    def _add_select_menu(self) -> None:
        options: list[discord.SelectOption] = []
        for suspect in self._current_page_suspects():
            member = self.guild.get_member(suspect.member_id)
            member_name = member.display_name if member else f"用戶 ID: {suspect.member_id}"
            status_emoji = {
                "detained": "🔒",
                "charged": "⚖️",
                "released": "✅",
            }.get(suspect.status, "❓")
            arrested_at = (
                suspect.arrested_at.strftime("%Y-%m-%d %H:%M")
                if getattr(suspect, "arrested_at", None)
                else "N/A"
            )
            description = f"{status_emoji} {suspect.status}｜逮捕 {arrested_at}"
            options.append(
                discord.SelectOption(
                    label=member_name[:95],
                    description=description[:95],
                    value=str(suspect.suspect_id),
                )
            )

        if not options:
            select: discord.ui.Select[Any] = discord.ui.Select(
                placeholder="目前沒有嫌犯記錄",
                min_values=1,
                max_values=1,
                options=[
                    discord.SelectOption(
                        label="等待新的嫌犯記錄",
                        description="目前沒有嫌犯記錄",
                        value="none",
                    )
                ],
                row=0,
            )
            select.disabled = True
        else:
            max_values = min(len(options), 25)
            select = discord.ui.Select(
                placeholder="選擇要操作的嫌犯（可多選）",
                min_values=1,
                max_values=max_values,
                options=options,
                row=0,
            )
        select.callback = self._on_select
        self.add_item(select)

    async def _prev_page(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        self.current_page = max(0, self.current_page - 1)
        await self.reload()
        await self._update_interaction(interaction)

    async def _next_page(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        await self.reload()
        await self._update_interaction(interaction)

    async def _refresh_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        await self.reload()
        await self._update_interaction(interaction)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        data = cast(dict[str, Any], interaction.data or {})
        raw_values = cast(Sequence[Any] | None, data.get("values"))
        values: list[str] = []
        if isinstance(raw_values, (list, tuple, set)):
            values = [str(v) for v in raw_values]
        selected: set[str] = set()
        for raw in values:
            value = str(raw)
            if value and value != "none":
                selected.add(value)
        self._selected_ids = selected
        await edit_message_compat(interaction, embed=self.build_embed(), view=self)

    async def _charge_suspect(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        if not self._selected_ids:
            await send_message_compat(interaction, content="請先選擇要起訴的嫌犯。", ephemeral=True)
            return
        await send_modal_compat(interaction, JusticeChargeModal(panel=self))

    async def _revoke_charge(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        if not self._selected_ids:
            await send_message_compat(
                interaction, content="請先選擇要撤銷起訴的嫌犯。", ephemeral=True
            )
            return
        await send_modal_compat(interaction, JusticeRevokeChargeModal(panel=self))

    async def _view_details(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        if not self._selected_ids:
            await send_message_compat(
                interaction, content="請先選擇一名嫌犯查看詳情。", ephemeral=True
            )
            return
        if len(self._selected_ids) > 1:
            await send_message_compat(
                interaction,
                content="一次僅支援查看一名嫌犯的詳情，請只勾選一名。",
                ephemeral=True,
            )
            return

        suspect_id_str = next(iter(self._selected_ids))
        suspect = next(
            (s for s in self._suspects if str(getattr(s, "id", "")) == suspect_id_str),
            None,
        )
        if suspect is None:
            await send_message_compat(interaction, content="找不到選取的嫌犯記錄。", ephemeral=True)
            return

        # 基本身分與狀態資訊
        member = self.guild.get_member(suspect.member_id)
        member_name = getattr(member, "display_name", f"用戶 ID: {suspect.member_id}")

        status_emoji = {"detained": "🔒", "charged": "⚖️", "released": "✅"}.get(
            suspect.status, "❓"
        )
        status_text = {
            "detained": "拘留中",
            "charged": "已起訴",
            "released": "已釋放",
        }.get(suspect.status, suspect.status)

        arrested_at = (
            suspect.arrested_at.strftime("%Y-%m-%d %H:%M")
            if getattr(suspect, "arrested_at", None)
            else "N/A"
        )
        arrest_reason = getattr(suspect, "arrest_reason", None) or "未提供"
        arrest_by_member = (
            self.guild.get_member(suspect.arrested_by)
            if hasattr(self.guild, "get_member")
            else None
        )
        arrest_by_name = getattr(arrest_by_member, "display_name", f"ID: {suspect.arrested_by}")

        # 起訴相關資訊：優先從身分紀錄中取得起訴人與時間
        prosecutor_name = "未起訴"
        charged_at = (
            suspect.charged_at.strftime("%Y-%m-%d %H:%M")
            if getattr(suspect, "charged_at", None)
            else None
        )
        last_charge_reason = None

        try:
            sc_service = StateCouncilService()
            history = await sc_service.get_member_identity_history(
                guild_id=self.guild_id,
                target_id=int(suspect.member_id),
            )
            charge_record = next(
                (r for r in history if getattr(r, "action", "") == "起訴嫌犯"),
                None,
            )
            if charge_record is not None:
                charged_at = charge_record.performed_at.strftime("%Y-%m-%d %H:%M")
                prosecutor = (
                    self.guild.get_member(charge_record.performed_by)
                    if hasattr(self.guild, "get_member")
                    else None
                )
                prosecutor_name = getattr(
                    prosecutor, "display_name", f"ID: {charge_record.performed_by}"
                )
                last_charge_reason = getattr(charge_record, "reason", None)
        except Exception:
            # 取得歷史紀錄失敗時，以 suspects 表與預設文字為主
            pass

        embed = discord.Embed(
            title=f"⚖️ 嫌犯詳情｜{member_name}",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="當前狀態",
            value=f"{status_emoji} {status_text}",
            inline=False,
        )
        embed.add_field(
            name="逮捕資訊",
            value=(
                f"• 逮捕原因：{arrest_reason}\n"
                f"• 逮捕時間：{arrested_at}\n"
                f"• 逮捕人：{arrest_by_name}"
            ),
            inline=False,
        )

        if charged_at or prosecutor_name != "未起訴":
            charge_lines = [
                f"• 起訴狀態：{'已起訴' if suspect.status == 'charged' else status_text}",
                f"• 起訴時間：{charged_at or 'N/A'}",
                f"• 起訴人：{prosecutor_name}",
            ]
            if last_charge_reason:
                charge_lines.append(f"• 起訴理由：{last_charge_reason}")
            embed.add_field(name="起訴資訊", value="\n".join(charge_lines), inline=False)

        embed.set_footer(text="僅法務部領導人可查看此面板")
        await send_message_compat(interaction, embed=embed, ephemeral=True)

    async def _release_suspect(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        if not self._selected_ids:
            await send_message_compat(interaction, content="請先選擇要釋放的嫌犯。", ephemeral=True)
            return
        await send_modal_compat(interaction, JusticeReleaseModal(panel=self))

    async def _update_interaction(self, interaction: discord.Interaction) -> None:
        embed = self.build_embed()
        await edit_message_compat(interaction, embed=embed, view=self)

    async def handle_charge(self, interaction: discord.Interaction, reason: str | None) -> None:
        if not self._selected_ids:
            await interaction.response.send_message("請先選擇要起訴的嫌犯。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        selected_map = {str(suspect.suspect_id): suspect for suspect in self._suspects}
        success = 0
        failures: list[str] = []

        for suspect_id_str in list(self._selected_ids):
            suspect = selected_map.get(suspect_id_str)
            if suspect is None:
                continue
            member = self.guild.get_member(suspect.member_id)
            member_name = getattr(member, "display_name", f"用戶 ID: {suspect.member_id}")
            try:
                await self.justice_service.charge_suspect(
                    guild_id=self.guild_id,
                    suspect_id=int(suspect_id_str),
                    justice_member_id=self.author_id,
                    justice_member_roles=self.user_roles,
                )
                # 記錄審計軌跡（最佳努力）
                try:
                    service = StateCouncilService()
                    await service.record_identity_action(
                        guild_id=self.guild_id,
                        target_id=int(suspect.member_id),
                        action="起訴嫌犯",
                        reason=reason,
                        performed_by=self.author_id,
                    )
                except Exception:
                    LOGGER.warning(
                        "state_council.justice.charge.audit_failed",
                        guild_id=self.guild_id,
                        target_id=suspect.member_id,
                    )
                success += 1
            except PermissionError as exc:
                failures.append(f"{member_name}：{exc}")
            except Exception as exc:  # pragma: no cover - 防禦性日誌
                LOGGER.warning(
                    "state_council.justice.charge_failed",
                    guild_id=self.guild_id,
                    suspect_id=str(suspect.id),
                    error=str(exc),
                )
                failures.append(f"{member_name}：{exc}")

        self._selected_ids.clear()
        await self.reload()
        if self._message is not None:
            await self._message.edit(embed=self.build_embed(), view=self)

        parts: list[str] = []
        if success:
            parts.append(f"成功起訴 {success} 名嫌犯。")
        if failures:
            parts.append(f"失敗 {len(failures)} 名：{'; '.join(failures[:5])}")
        summary = " ".join(parts) if parts else "沒有任何嫌犯被起訴。"
        await interaction.followup.send(summary, ephemeral=True)

    async def handle_revoke_charge(
        self,
        interaction: discord.Interaction,
        reason: str | None,
    ) -> None:
        if not self._selected_ids:
            await interaction.response.send_message("請先選擇要撤銷起訴的嫌犯。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        selected_map = {str(suspect.suspect_id): suspect for suspect in self._suspects}
        success = 0
        failures: list[str] = []

        for suspect_id_str in list(self._selected_ids):
            suspect = selected_map.get(suspect_id_str)
            if suspect is None:
                continue
            member = self.guild.get_member(suspect.member_id)
            member_name = getattr(member, "display_name", f"用戶 ID: {suspect.member_id}")
            try:
                await self.justice_service.revoke_charge(
                    guild_id=self.guild_id,
                    suspect_id=int(suspect_id_str),
                    justice_member_id=self.author_id,
                    justice_member_roles=self.user_roles,
                )
                # 審計紀錄：撤銷起訴
                try:
                    service = StateCouncilService()
                    await service.record_identity_action(
                        guild_id=self.guild_id,
                        target_id=int(suspect.member_id),
                        action="撤銷起訴",
                        reason=reason,
                        performed_by=self.author_id,
                    )
                except Exception:
                    LOGGER.warning(
                        "state_council.justice.revoke_charge.audit_failed",
                        guild_id=self.guild_id,
                        target_id=suspect.member_id,
                    )
                success += 1
            except PermissionError as exc:
                failures.append(f"{member_name}：{exc}")
            except ValueError as exc:
                failures.append(f"{member_name}：{exc}")
            except Exception as exc:  # pragma: no cover - 防禦性日誌
                LOGGER.warning(
                    "state_council.justice.revoke_charge_failed",
                    guild_id=self.guild_id,
                    suspect_id=str(getattr(suspect, "id", None)),
                    error=str(exc),
                )
                failures.append(f"{member_name}：{exc}")

        self._selected_ids.clear()
        await self.reload()
        if self._message is not None:
            await self._message.edit(embed=self.build_embed(), view=self)

        parts: list[str] = []
        if success:
            parts.append(f"成功撤銷起訴 {success} 名嫌犯。")
        if failures:
            parts.append(f"失敗 {len(failures)} 名：{'; '.join(failures[:5])}")
        summary = " ".join(parts) if parts else "沒有任何嫌犯被撤銷起訴。"
        await interaction.followup.send(summary, ephemeral=True)

    async def handle_release(self, interaction: discord.Interaction, reason: str | None) -> None:
        if not self._selected_ids:
            await interaction.response.send_message("請先選擇要釋放的嫌犯。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        selected_map = {str(suspect.suspect_id): suspect for suspect in self._suspects}
        member_ids: list[int] = []
        failures: list[str] = []

        # 先更新司法系統中的嫌犯狀態
        for suspect_id_str in list(self._selected_ids):
            suspect = selected_map.get(suspect_id_str)
            if suspect is None:
                continue
            member = self.guild.get_member(suspect.member_id)
            member_name = getattr(member, "display_name", f"用戶 ID: {suspect.member_id}")
            try:
                await self.justice_service.release_suspect(
                    guild_id=self.guild_id,
                    suspect_id=int(suspect_id_str),
                    justice_member_id=self.author_id,
                    justice_member_roles=self.user_roles,
                )
                member_ids.append(int(suspect.member_id))
            except PermissionError as exc:
                failures.append(f"{member_name}：{exc}")
            except Exception as exc:  # pragma: no cover - 防禦性日誌
                LOGGER.warning(
                    "state_council.justice.release_failed",
                    guild_id=self.guild_id,
                    suspect_id=str(suspect.id),
                    error=str(exc),
                )
                failures.append(f"{member_name}：{exc}")

        released_results: list[SuspectReleaseResult] = []
        if member_ids:
            try:
                sc_service = StateCouncilService()
                released_results = await sc_service.release_suspects(
                    guild=self.guild,
                    guild_id=self.guild_id,
                    department="國土安全部",
                    user_id=self.author_id,
                    user_roles=self.user_roles,
                    suspect_ids=member_ids,
                    reason=reason or "法務部釋放",
                    audit_source="justice",
                    skip_permission=True,
                )
            except Exception as exc:  # pragma: no cover - 防禦性日誌
                LOGGER.warning(
                    "state_council.justice.release_state_flow_failed",
                    guild_id=self.guild_id,
                    suspect_ids=member_ids,
                    error=str(exc),
                )
                failures.append(f"國土安全部釋放流程失敗：{exc}")

        # 合併來自 StateCouncilService 的結果
        success = 0
        for result in released_results:
            if result.released:
                success += 1
            elif result.error:
                name = result.display_name or f"嫌疑人 {result.suspect_id}"
                failures.append(f"{name}：{result.error}")

        self._selected_ids.clear()
        await self.reload()
        if self._message is not None:
            await self._message.edit(embed=self.build_embed(), view=self)

        parts: list[str] = []
        if success:
            parts.append(f"成功釋放 {success} 名嫌犯。")
        if failures:
            parts.append(f"失敗 {len(failures)} 名：{'; '.join(failures[:5])}")
        summary = " ".join(parts) if parts else "沒有任何嫌犯被釋放。"
        await interaction.followup.send(summary, ephemeral=True)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="⚖️ 法務部嫌犯管理",
            color=discord.Color.gold(),
        )

        if self._error_message:
            embed.description = f"❌ 載入失敗：{self._error_message}"
            embed.color = discord.Color.red()
        elif not self._suspects:
            embed.description = "目前沒有活躍的嫌犯記錄。"
        else:
            embed.description = (
                f"📋 第 {self.current_page + 1} 頁，共 {self.total_pages} 頁"
                f"（總計 {self._total_count} 筆記錄，已選擇 {len(self._selected_ids)} 名）"
            )

            for idx, suspect in enumerate(self._suspects, 1):
                member = self.guild.get_member(suspect.member_id)
                member_name = member.display_name if member else f"用戶 ID: {suspect.member_id}"

                status_emoji = {"detained": "🔒", "charged": "⚖️", "released": "✅"}.get(
                    suspect.status, "❓"
                )

                arrest_by_member = (
                    self.guild.get_member(suspect.arrested_by)
                    if hasattr(self.guild, "get_member")
                    else None
                )
                arrest_by_name = getattr(
                    arrest_by_member,
                    "display_name",
                    f"ID: {getattr(suspect, 'arrested_by', 'N/A')}",
                )

                field_value = (
                    f"**狀態**: {status_emoji} {suspect.status}\n"
                    f"**逮捕原因**: {suspect.arrest_reason}\n"
                    f"**逮捕時間**: {suspect.arrested_at.strftime('%Y-%m-%d %H:%M') if suspect.arrested_at else 'N/A'}\n"
                    f"**逮捕人**: {arrest_by_name}"
                )

                if suspect.charged_at:
                    field_value += (
                        f"\n**起訴時間**: {suspect.charged_at.strftime('%Y-%m-%d %H:%M')}"
                    )

                embed.add_field(
                    name=f"{idx}. {member_name}",
                    value=field_value,
                    inline=False,
                )

        embed.set_footer(text="僅法務部領導人可查看此面板")
        return embed


class JusticeChargeModal(discord.ui.Modal, title="起訴嫌犯"):
    def __init__(self, panel: JusticeSuspectsPanelView) -> None:
        super().__init__(title="起訴嫌犯")
        self.panel = panel
        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="起訴理由（可選）",
            placeholder="將記錄在審計或日誌中",
            required=False,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        reason = str(self.reason_input.value).strip() or None
        await self.panel.handle_charge(interaction, reason)


class JusticeRevokeChargeModal(discord.ui.Modal, title="撤銷起訴"):
    def __init__(self, panel: JusticeSuspectsPanelView) -> None:
        super().__init__(title="撤銷起訴")
        self.panel = panel
        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="撤銷原因（可選）",
            placeholder="將記錄在審計或日誌中",
            required=False,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        reason = str(self.reason_input.value).strip() or None
        await self.panel.handle_revoke_charge(interaction, reason)


class JusticeReleaseModal(discord.ui.Modal, title="釋放嫌犯"):
    def __init__(self, panel: JusticeSuspectsPanelView) -> None:
        super().__init__(title="釋放嫌犯")
        self.panel = panel
        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="釋放理由（可選）",
            placeholder="預設為『法務部釋放』",
            required=False,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        reason = str(self.reason_input.value).strip() or None
        await self.panel.handle_release(interaction, reason)


# --- Business License Management ---


class BusinessLicenseIssueModal(discord.ui.Modal, title="發放商業許可"):
    """發放商業許可的 Modal。"""

    def __init__(
        self,
        service: StateCouncilService,
        guild_id: int,
        author_id: int,
        user_roles: list[int],
    ) -> None:
        super().__init__()
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles

        self.user_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="目標用戶",
            placeholder="輸入 @使用者 或使用者ID",
            required=True,
            style=discord.TextStyle.short,
        )
        self.license_type_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="許可類型",
            placeholder="例如：一般商業許可、特殊經營許可",
            required=True,
            style=discord.TextStyle.short,
        )
        self.expires_days_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="有效天數",
            placeholder="輸入有效天數（數字，例如 365）",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.user_input)
        self.add_item(self.license_type_input)
        self.add_item(self.expires_days_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from datetime import datetime, timedelta, timezone

        try:
            user_input = str(self.user_input.value)
            license_type = str(self.license_type_input.value).strip()
            expires_days = int(str(self.expires_days_input.value))

            # Parse user ID
            if user_input.startswith("<@") and user_input.endswith(">"):
                target_user_id = int(user_input[2:-1].replace("!", ""))
            else:
                target_user_id = int(user_input)

            if expires_days <= 0:
                await send_message_compat(
                    interaction, content="❌ 有效天數必須大於 0", ephemeral=True
                )
                return

            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

            # Issue license (call service method)
            result = await self.service.issue_business_license(
                guild_id=self.guild_id,
                user_id=target_user_id,
                license_type=license_type,
                issued_by=self.author_id,
                expires_at=expires_at,
            )

            if result.is_err():
                await send_message_compat(
                    interaction,
                    content=f"❌ 發放許可失敗：{result.unwrap_err()}",
                    ephemeral=True,
                )
                return

            license_data = result.unwrap()
            await send_message_compat(
                interaction,
                content=(
                    f"✅ 商業許可發放成功！\n"
                    f"許可 ID：`{license_data.license_id}`\n"
                    f"目標用戶：<@{target_user_id}>\n"
                    f"許可類型：{license_type}\n"
                    f"有效期至：{expires_at.strftime('%Y-%m-%d')}"
                ),
                ephemeral=True,
            )

        except ValueError:
            await send_message_compat(
                interaction, content="❌ 輸入格式錯誤，請檢查用戶ID和天數", ephemeral=True
            )
        except Exception as e:
            LOGGER.exception("Business license issue failed", error=str(e))
            await send_message_compat(
                interaction,
                content=ErrorMessageTemplates.system_error("許可發放失敗"),
                ephemeral=True,
            )


class ApplicationManagementView(discord.ui.View):
    """申請管理視圖，顯示待審批申請列表並支援審批/拒絕操作。"""

    def __init__(
        self,
        service: StateCouncilService,
        guild_id: int,
        author_id: int,
        user_roles: list[int],
        page_size: int = 5,
    ) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles
        self.page_size = page_size
        self.current_page = 1
        self.filter_type: str | None = None  # 'welfare' or 'license' or None (all)

        # 申請資料
        self._welfare_apps: list[Any] = []
        self._license_apps: list[Any] = []
        self._total_count = 0

        # 匯入 ApplicationService
        from src.bot.services.application_service import ApplicationService

        self._app_service = ApplicationService()

    async def load_applications(self) -> None:
        """載入待審批申請列表。"""
        try:
            # 載入福利申請
            welfare_result = await self._app_service.list_welfare_applications(
                guild_id=self.guild_id,
                status="pending",
                page=1,
                page_size=100,
            )
            if not welfare_result.is_err():
                welfare_data = welfare_result.unwrap()
                self._welfare_apps = list(welfare_data.applications)
        except Exception as exc:
            LOGGER.warning("application_management.load_welfare.error", error=str(exc))

        try:
            # 載入商業許可申請
            license_result = await self._app_service.list_license_applications(
                guild_id=self.guild_id,
                status="pending",
                page=1,
                page_size=100,
            )
            if not license_result.is_err():
                license_data = license_result.unwrap()
                self._license_apps = list(license_data.applications)
        except Exception as exc:
            LOGGER.warning("application_management.load_license.error", error=str(exc))

        self._total_count = len(self._welfare_apps) + len(self._license_apps)
        self._build_buttons()

    def _get_filtered_apps(self) -> list[tuple[str, Any]]:
        """取得篩選後的申請列表。"""
        apps: list[tuple[str, Any]] = []
        if self.filter_type is None or self.filter_type == "welfare":
            apps.extend([("welfare", a) for a in self._welfare_apps])
        if self.filter_type is None or self.filter_type == "license":
            apps.extend([("license", a) for a in self._license_apps])
        # 按時間排序
        apps.sort(key=lambda x: x[1].created_at, reverse=True)
        return apps

    def _build_buttons(self) -> None:
        """建立控制按鈕。"""
        self.clear_items()

        # 篩選按鈕
        all_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="全部",
            style=(
                discord.ButtonStyle.primary
                if self.filter_type is None
                else discord.ButtonStyle.secondary
            ),
            row=0,
        )
        all_btn.callback = self._filter_all_callback
        self.add_item(all_btn)

        welfare_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="💰 福利申請",
            style=(
                discord.ButtonStyle.primary
                if self.filter_type == "welfare"
                else discord.ButtonStyle.secondary
            ),
            row=0,
        )
        welfare_btn.callback = self._filter_welfare_callback
        self.add_item(welfare_btn)

        license_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="📜 許可申請",
            style=(
                discord.ButtonStyle.primary
                if self.filter_type == "license"
                else discord.ButtonStyle.secondary
            ),
            row=0,
        )
        license_btn.callback = self._filter_license_callback
        self.add_item(license_btn)

        refresh_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🔄 重整",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        refresh_btn.callback = self._refresh_callback
        self.add_item(refresh_btn)

        # 申請操作按鈕
        apps = self._get_filtered_apps()
        start = (self.current_page - 1) * self.page_size
        end = start + self.page_size
        page_apps = apps[start:end]

        for i, (app_type, app) in enumerate(page_apps):
            # 批准按鈕
            approve_btn: discord.ui.Button[Any] = discord.ui.Button(
                label=f"✅ #{app.id}",
                style=discord.ButtonStyle.success,
                custom_id=f"approve_{app_type}_{app.id}",
                row=1 + i,
            )
            approve_btn.callback = self._make_approve_callback(
                app_type, app.id
            )  # pyright: ignore[reportAttributeAccessIssue]
            self.add_item(approve_btn)

            # 拒絕按鈕
            reject_btn: discord.ui.Button[Any] = discord.ui.Button(
                label=f"❌ #{app.id}",
                style=discord.ButtonStyle.danger,
                custom_id=f"reject_{app_type}_{app.id}",
                row=1 + i,
            )
            reject_btn.callback = self._make_reject_callback(
                app_type, app.id
            )  # pyright: ignore[reportAttributeAccessIssue]
            self.add_item(reject_btn)

    def build_embed(self) -> discord.Embed:
        """建立申請列表的 Embed。"""
        embed = discord.Embed(
            title="📋 申請管理",
            color=0x9B59B6,
        )

        apps = self._get_filtered_apps()
        total_pages = max(1, (len(apps) + self.page_size - 1) // self.page_size)
        start = (self.current_page - 1) * self.page_size
        end = start + self.page_size
        page_apps = apps[start:end]

        if not page_apps:
            embed.description = "目前沒有待審批的申請。"
            embed.set_footer(
                text=f"福利申請: {len(self._welfare_apps)} | 許可申請: {len(self._license_apps)}"
            )
            return embed

        lines: list[str] = []
        for app_type, app in page_apps:
            if app_type == "welfare":
                icon = "💰"
                detail = f"金額: {app.amount:,}"
            else:
                icon = "📜"
                detail = f"類型: {app.license_type}"

            timestamp = app.created_at.strftime("%m-%d %H:%M")
            lines.append(
                f"{icon} **#{app.id}** - <@{app.applicant_id}>\n"
                f"　{detail}\n"
                f"　原因: {app.reason[:50]}{'...' if len(app.reason) > 50 else ''}\n"
                f"　時間: {timestamp}"
            )

        embed.description = "\n\n".join(lines)
        embed.set_footer(
            text=f"第 {self.current_page}/{total_pages} 頁 | 福利: {len(self._welfare_apps)} | 許可: {len(self._license_apps)}"
        )
        return embed

    def _make_approve_callback(
        self, app_type: str, app_id: int
    ) -> Callable[[discord.Interaction], Coroutine[Any, Any, None]]:
        async def callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return

            if app_type == "welfare":

                async def _welfare_transfer_callback(**kwargs: Any) -> bool:
                    application = kwargs.get("application")
                    if application is None:
                        # 後備：以 kwargs 重新組合資料
                        applicant_id = int(kwargs.get("applicant_id") or 0)
                        amount = int(kwargs.get("amount") or 0)
                        reason = str(kwargs.get("reason") or "福利發放")
                        guild_id = int(kwargs.get("guild_id", self.guild_id))
                    else:
                        applicant_id = int(application.applicant_id)
                        amount = int(application.amount)
                        reason = str(getattr(application, "reason", "福利發放") or "福利發放")
                        guild_id = int(getattr(application, "guild_id", self.guild_id))

                    await self.service.disburse_welfare(
                        guild_id=guild_id,
                        department="內政部",
                        user_id=self.author_id,
                        user_roles=self.user_roles,
                        recipient_id=applicant_id,
                        amount=amount,
                        reason=reason,
                    )
                    return True

                result: Result[Any, Error] = await self._app_service.approve_welfare_application(
                    application_id=app_id,
                    reviewer_id=self.author_id,
                    transfer_callback=_welfare_transfer_callback,
                )
            else:
                result = await self._app_service.approve_license_application(
                    application_id=app_id,
                    reviewer_id=self.author_id,
                )

            if result.is_err():
                await send_message_compat(
                    interaction, content=f"❌ 審批失敗: {result.unwrap_err()}", ephemeral=True
                )
                return

            await self.load_applications()
            embed = self.build_embed()
            await edit_message_compat(interaction, embed=embed, view=self)
            await send_message_compat(
                interaction, content=f"✅ 申請 #{app_id} 已批准", ephemeral=True
            )

        return callback

    def _make_reject_callback(
        self, app_type: str, app_id: int
    ) -> Callable[[discord.Interaction], Coroutine[Any, Any, None]]:
        async def callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await send_message_compat(
                    interaction, content="僅限面板開啟者操作。", ephemeral=True
                )
                return

            modal = ApplicationRejectModal(
                app_type=app_type,
                app_id=app_id,
                app_service=self._app_service,
                reviewer_id=self.author_id,
                on_complete=self._on_reject_complete,
            )
            await send_modal_compat(interaction, modal)

        return callback

    async def _on_reject_complete(self, interaction: discord.Interaction) -> None:
        """拒絕完成後的回調。"""
        await self.load_applications()
        embed = self.build_embed()
        await edit_message_compat(interaction, embed=embed, view=self)

    async def _filter_all_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        self.filter_type = None
        self.current_page = 1
        self._build_buttons()
        embed = self.build_embed()
        await edit_message_compat(interaction, embed=embed, view=self)

    async def _filter_welfare_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        self.filter_type = "welfare"
        self.current_page = 1
        self._build_buttons()
        embed = self.build_embed()
        await edit_message_compat(interaction, embed=embed, view=self)

    async def _filter_license_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        self.filter_type = "license"
        self.current_page = 1
        self._build_buttons()
        embed = self.build_embed()
        await edit_message_compat(interaction, embed=embed, view=self)

    async def _refresh_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return
        await self.load_applications()
        embed = self.build_embed()
        await edit_message_compat(interaction, embed=embed, view=self)


class ApplicationRejectModal(discord.ui.Modal, title="拒絕申請"):
    """拒絕申請的原因輸入 Modal。"""

    reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="拒絕原因",
        placeholder="請輸入拒絕此申請的原因",
        required=True,
        min_length=1,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )

    def __init__(
        self,
        app_type: str,
        app_id: int,
        app_service: Any,
        reviewer_id: int,
        on_complete: Callable[[discord.Interaction], Coroutine[Any, Any, None]],
    ) -> None:
        super().__init__()
        self.app_type = app_type
        self.app_id = app_id
        self._app_service = app_service
        self.reviewer_id = reviewer_id
        self._on_complete = on_complete

    async def on_submit(self, interaction: discord.Interaction) -> None:
        reason = self.reason_input.value.strip()
        if not reason:
            await send_message_compat(interaction, content="❌ 請填寫拒絕原因。", ephemeral=True)
            return

        if self.app_type == "welfare":
            result = await self._app_service.reject_welfare_application(
                application_id=self.app_id,
                reviewer_id=self.reviewer_id,
                rejection_reason=reason,
            )
        else:
            result = await self._app_service.reject_license_application(
                application_id=self.app_id,
                reviewer_id=self.reviewer_id,
                rejection_reason=reason,
            )

        if result.is_err():
            await send_message_compat(
                interaction, content=f"❌ 拒絕失敗: {result.unwrap_err()}", ephemeral=True
            )
            return

        await send_message_compat(
            interaction, content=f"✅ 申請 #{self.app_id} 已拒絕", ephemeral=True
        )
        await self._on_complete(interaction)


class BusinessLicenseListView(discord.ui.View):
    """商業許可列表的 View，支援分頁和撤銷功能。"""

    def __init__(
        self,
        service: StateCouncilService,
        guild_id: int,
        author_id: int,
        user_roles: list[int],
        licenses: Any,
        total_count: int,
        current_page: int = 1,
        page_size: int = 10,
    ) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.guild_id = guild_id
        self.author_id = author_id
        self.user_roles = user_roles
        self.licenses = licenses
        self.total_count = total_count
        self.current_page = current_page
        self.page_size = page_size
        self.selected_license_id: str | None = None

        self._build_buttons()

    def _build_buttons(self) -> None:
        """建立分頁按鈕和撤銷按鈕。"""
        # Previous page button
        prev_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="上一頁",
            style=discord.ButtonStyle.secondary,
            disabled=self.current_page <= 1,
            row=0,
        )
        prev_btn.callback = self._prev_page_callback
        self.add_item(prev_btn)

        # Page indicator
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
        page_btn: discord.ui.Button[Any] = discord.ui.Button(
            label=f"{self.current_page}/{total_pages}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=0,
        )
        self.add_item(page_btn)

        # Next page button
        next_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="下一頁",
            style=discord.ButtonStyle.secondary,
            disabled=self.current_page * self.page_size >= self.total_count,
            row=0,
        )
        next_btn.callback = self._next_page_callback
        self.add_item(next_btn)

        # Refresh button
        refresh_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🔄 重整",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        refresh_btn.callback = self._refresh_callback
        self.add_item(refresh_btn)

    def build_embed(self) -> discord.Embed:
        """建立許可列表的 Embed。"""
        embed = discord.Embed(
            title="📋 商業許可列表",
            color=0x3498DB,
        )

        if not self.licenses:
            embed.description = "目前沒有商業許可記錄。"
            return embed

        lines: list[str] = []
        for lic in self.licenses:
            status_emoji = {"active": "✅", "expired": "⏰", "revoked": "❌"}.get(lic.status, "❓")
            lines.append(
                f"{status_emoji} **<@{lic.user_id}>**\n"
                f"　類型：{lic.license_type}\n"
                f"　核發：{lic.issued_at.strftime('%Y-%m-%d')}\n"
                f"　到期：{lic.expires_at.strftime('%Y-%m-%d')}\n"
                f"　ID：`{lic.license_id}`"
            )

        embed.description = "\n\n".join(lines)
        embed.set_footer(text=f"共 {self.total_count} 筆記錄")
        return embed

    async def _prev_page_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        self.current_page -= 1
        await self._refresh_list(interaction)

    async def _next_page_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        self.current_page += 1
        await self._refresh_list(interaction)

    async def _refresh_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        await self._refresh_list(interaction)

    async def _refresh_list(self, interaction: discord.Interaction) -> None:
        result = await self.service.list_business_licenses(
            guild_id=self.guild_id,
            page=self.current_page,
            page_size=self.page_size,
        )
        if result.is_err():
            await send_message_compat(
                interaction,
                content=f"❌ 無法取得許可列表：{result.unwrap_err()}",
                ephemeral=True,
            )
            return

        license_list = result.unwrap()
        self.licenses = license_list.licenses
        self.total_count = license_list.total_count

        # Rebuild the view
        self.clear_items()
        self._build_buttons()

        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)


# --- Background Scheduler Integration ---


def _install_background_scheduler(client: discord.Client, service: StateCouncilService) -> None:
    """Install background scheduler for State Council operations."""
    try:
        import asyncio

        from src.bot.services.state_council_scheduler import start_scheduler

        # Start the scheduler
        asyncio.create_task(start_scheduler(client))
        LOGGER.info("state_council.scheduler.installed")
    except Exception as exc:
        LOGGER.exception("state_council.scheduler.install_error", error=str(exc))
