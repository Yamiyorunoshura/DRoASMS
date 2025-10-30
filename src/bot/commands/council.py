from __future__ import annotations

import asyncio
import csv
import io
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import UUID

import discord
import structlog
from discord import app_commands

from src.bot.services.balance_service import BalanceService
from src.bot.services.council_service import (
    CouncilService,
    GovernanceNotConfiguredError,
    PermissionDeniedError,
)
from src.db.pool import get_pool
from src.infra.events.council_events import CouncilEvent
from src.infra.events.council_events import subscribe as subscribe_council_events

LOGGER = structlog.get_logger(__name__)


def register(tree: app_commands.CommandTree) -> None:
    service = CouncilService()

    tree.add_command(build_council_group(service))
    _install_background_scheduler(tree.client, service)

    LOGGER.debug("bot.command.council.registered")


def build_council_group(service: CouncilService) -> app_commands.Group:
    council = app_commands.Group(name="council", description="Council governance commands")

    @council.command(name="config_role", description="設定常任理事身分組（角色）")
    @app_commands.describe(role="Discord 角色，將作為理事名冊來源")
    async def config_role(interaction: discord.Interaction, role: discord.Role) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await interaction.response.send_message("本指令需在伺服器中執行。", ephemeral=True)
            return
        # Require admin/manage_guild
        perms = getattr(interaction.user, "guild_permissions", None)
        if not perms or not (perms.administrator or perms.manage_guild):
            await interaction.response.send_message("需要管理員或管理伺服器權限。", ephemeral=True)
            return
        try:
            cfg = await service.set_config(guild_id=interaction.guild_id, council_role_id=role.id)
            await interaction.response.send_message(
                f"已設定理事角色：{role.mention}（帳戶ID {cfg.council_account_member_id}）",
                ephemeral=True,
            )
        except Exception as exc:  # pragma: no cover - unexpected
            LOGGER.exception("council.config_role.error", error=str(exc))
            await interaction.response.send_message("設定失敗，請稍後再試。", ephemeral=True)

    # 依規範：移除與面板重疊之撤案/建案/匯出斜線指令（保留 panel/config_role）

    @council.command(name="panel", description="開啟理事會面板（建案/投票/撤案/匯出）")
    async def panel(interaction: discord.Interaction) -> None:
        # 僅允許在伺服器使用
        if interaction.guild_id is None or interaction.guild is None:
            await interaction.response.send_message("本指令需在伺服器中執行。", ephemeral=True)
            return
        # 檢查是否完成治理設定
        try:
            cfg = await service.get_config(guild_id=interaction.guild_id)
        except GovernanceNotConfiguredError:
            await interaction.response.send_message(
                "尚未完成治理設定，請先執行 /council config_role。",
                ephemeral=True,
            )
            return
        # 檢查理事資格
        role = interaction.guild.get_role(cfg.council_role_id)
        if role is None or (
            isinstance(interaction.user, discord.Member) and role not in interaction.user.roles
        ):
            await interaction.response.send_message("僅限理事可開啟面板。", ephemeral=True)
            return

        view = CouncilPanelView(
            service=service,
            guild=interaction.guild,
            author_id=interaction.user.id,
            council_role_id=cfg.council_role_id,
        )
        await view.refresh_options()
        embed = await view.build_summary_embed()
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )
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

    return council


# --- Voting UI ---


class VotingView(discord.ui.View):
    def __init__(self, *, proposal_id: UUID, service: CouncilService) -> None:
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
    service: CouncilService,
    proposal_id: UUID,
    choice: str,
) -> None:
    try:
        totals, status = await service.vote(
            proposal_id=proposal_id,
            voter_id=interaction.user.id,
            choice=choice,
        )
    except PermissionDeniedError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("council.vote.error", error=str(exc))
        await interaction.response.send_message("投票失敗。", ephemeral=True)
        return

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
    proposal: Any,
) -> None:
    service = CouncilService()
    view = VotingView(proposal_id=proposal.proposal_id, service=service)
    # Anonymous in-progress: only aggregated counts are shown in the button acknowledgment
    role = guild.get_role((await service.get_config(guild_id=guild.id)).council_role_id)
    members: list[discord.Member] = list(role.members) if role is not None else []

    embed = discord.Embed(title="理事會轉帳提案（請投票）", color=0x3498DB)
    embed.add_field(name="提案編號", value=str(proposal.proposal_id), inline=False)
    embed.add_field(name="受款人", value=f"<@{proposal.target_id}>")
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


def _install_background_scheduler(client: discord.Client, service: CouncilService) -> None:
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
                pool = get_pool()
                due_before: list[UUID] = []
                async with pool.acquire() as conn:
                    from src.db.gateway.council_governance import CouncilGovernanceGateway

                    gw = CouncilGovernanceGateway()
                    for p in await gw.list_due_proposals(conn):
                        due_before.append(p.proposal_id)

                # Expire due proposals (timeout or execute if reached threshold unseen)
                changed = await service.expire_due_proposals()
                if changed:
                    LOGGER.info("council.scheduler.expire", changed=changed)

                # Send T-24h reminders to non-voters
                async with pool.acquire() as conn:
                    from src.db.gateway.council_governance import CouncilGovernanceGateway

                    gw = CouncilGovernanceGateway()
                    for p in await gw.list_reminder_candidates(conn):
                        unvoted = await service.list_unvoted_members(proposal_id=p.proposal_id)
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
                        await gw.mark_reminded(conn, proposal_id=p.proposal_id)

                # 廣播剛結束的提案結果（逾時或已執行/失敗），避免重複
                for pid in due_before:
                    if pid in broadcasted:
                        continue
                    # 嘗試抓 guild 與最新狀態
                    try:
                        # 透過 service 取回提案，若已結束則廣播
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
                LOGGER.exception("council.scheduler.error", error=str(exc))
            await asyncio.sleep(60)

    _scheduler_task = asyncio.create_task(_runner(), name="council-scheduler")


__all__ = ["register"]


# --- Panel UI ---


class CouncilPanelView(discord.ui.View):
    """理事會面板容器（ephemeral）。"""

    def __init__(
        self,
        *,
        service: CouncilService,
        guild: discord.Guild,
        author_id: int,
        council_role_id: int,
    ) -> None:
        super().__init__(timeout=600)
        self.service = service
        self.guild = guild
        self.author_id = author_id
        self.council_role_id = council_role_id
        self._message: discord.Message | None = None
        self._unsubscribe: Callable[[], Awaitable[None]] | None = None
        self._update_lock = asyncio.Lock()

        # 元件：建案、提案選擇、匯出
        self._propose_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="建立轉帳提案",
            style=discord.ButtonStyle.primary,
        )
        self._propose_btn.callback = self._on_click_propose  # type: ignore[method-assign]
        self.add_item(self._propose_btn)

        self._export_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="匯出資料",
            style=discord.ButtonStyle.secondary,
        )
        self._export_btn.callback = self._on_click_export  # type: ignore[method-assign]
        self.add_item(self._export_btn)

        self._select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder="選擇進行中提案以投票/撤案",
            min_values=1,
            max_values=1,
            options=[],
        )
        self._select.callback = self._on_select_proposal  # type: ignore[method-assign]
        self.add_item(self._select)

    async def bind_message(self, message: discord.Message) -> None:
        """綁定訊息並訂閱治理事件，以便即時更新。"""
        if self._message is not None:
            return
        self._message = message
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
            balance_service = BalanceService(get_pool())
            council_account_id = CouncilService.derive_council_account_id(self.guild.id)
            snap = await balance_service.get_balance_snapshot(
                guild_id=self.guild.id,
                requester_id=self.author_id,
                target_member_id=council_account_id,
                can_view_others=True,
            )
            balance_str = f"{snap.balance:,}"
        except Exception as exc:  # pragma: no cover - best effort
            LOGGER.warning(
                "council.panel.summary.balance_error",
                guild_id=self.guild.id,
                error=str(exc),
            )

        role = self.guild.get_role(self.council_role_id)
        members = role.members if role is not None else []
        N = 10
        top_mentions = ", ".join(m.mention for m in members[:N]) if members else "(無)"
        summary = f"餘額：{balance_str}｜理事（{len(members)}）: {top_mentions}"
        embed.add_field(name="Council 摘要", value=summary, inline=False)
        embed.description = "在此可：建立提案、檢視進行中提案並投票、撤案與匯出。"
        return embed

    async def refresh_options(self) -> None:
        """以最近 N=10 筆進行中提案刷新選單。"""
        try:
            active = await self.service.list_active_proposals()
            # 僅顯示本 guild，最近 10 筆（依 created_at 降冪）
            items = [p for p in active if p.guild_id == self.guild.id and p.status == "進行中"]
            items.sort(key=lambda p: p.created_at, reverse=True)
            items = items[:10]
            options: list[discord.SelectOption] = []
            for p in items:
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
        try:
            cfg = await self.service.get_config(guild_id=self.guild.id)
        except GovernanceNotConfiguredError:
            await interaction.response.send_message("尚未完成治理設定。", ephemeral=True)
            return
        role = self.guild.get_role(cfg.council_role_id)
        if role is None or (
            isinstance(interaction.user, discord.Member) and role not in interaction.user.roles
        ):
            await interaction.response.send_message("僅限理事可建立提案。", ephemeral=True)
            return
        await interaction.response.send_modal(
            ProposeTransferModal(service=self.service, guild=self.guild)
        )

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
        proposal = await self.service.get_proposal(proposal_id=pid)
        if proposal is None or proposal.guild_id != self.guild.id:
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


class ProposeTransferModal(discord.ui.Modal, title="建立轉帳提案"):
    def __init__(self, *, service: CouncilService, guild: discord.Guild) -> None:
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

        # 快照名冊
        try:
            cfg = await self.service.get_config(guild_id=self.guild.id)
        except GovernanceNotConfiguredError:
            await interaction.response.send_message("尚未完成治理設定。", ephemeral=True)
            return
        role = self.guild.get_role(cfg.council_role_id)
        snapshot_ids = [m.id for m in role.members] if role is not None else []
        if not snapshot_ids:
            await interaction.response.send_message(
                "理事名冊為空，請先確認角色有成員。",
                ephemeral=True,
            )
            return

        try:
            proposal = await self.service.create_transfer_proposal(
                guild_id=self.guild.id,
                proposer_id=interaction.user.id,
                target_id=member.id,
                amount=amt,
                description=str(self.description.value or "").strip() or None,
                attachment_url=str(self.attachment_url.value or "").strip() or None,
                snapshot_member_ids=snapshot_ids,
            )
        except Exception as exc:
            LOGGER.exception("council.panel.propose.error", error=str(exc))
            await interaction.response.send_message("建案失敗：" + str(exc), ephemeral=True)
            return

        await interaction.response.send_message(
            f"已建立提案 {proposal.proposal_id}，並將以 DM 通知理事。",
            ephemeral=True,
        )
        try:
            await _dm_council_for_voting(interaction.client, self.guild, proposal)
        except Exception:
            pass
        LOGGER.info(
            "council.panel.propose",
            guild_id=self.guild.id,
            user_id=interaction.user.id,
            proposal_id=str(proposal.proposal_id),
        )


class ExportModal(discord.ui.Modal, title="匯出治理資料"):
    def __init__(self, *, service: CouncilService, guild: discord.Guild) -> None:
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
        try:
            data = await self.service.export_interval(
                guild_id=interaction.guild_id,
                start=start_utc,
                end=end_utc,
            )
        except Exception as exc:  # pragma: no cover - 防禦
            LOGGER.exception("council.panel.export.error", error=str(exc))
            await interaction.response.send_message("匯出失敗：" + str(exc), ephemeral=True)
            return

        if fmt == "json":
            buf = io.BytesIO()
            import json

            buf.write(json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
            buf.seek(0)
            await interaction.response.send_message(
                content=f"共 {len(data)} 筆。",
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
                    "amount",
                    "status",
                    "created_at",
                    "updated_at",
                    "deadline_at",
                    "snapshot_n",
                    "threshold_t",
                ]
            )
            for row in data:
                writer.writerow(
                    [
                        row.get("proposal_id"),
                        row.get("guild_id"),
                        row.get("proposer_id"),
                        row.get("target_id"),
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
                content=f"共 {len(data)} 筆。",
                file=discord.File(buf, filename="council_export.csv"),
                ephemeral=True,
            )

        LOGGER.info(
            "council.panel.export",
            guild_id=self.guild.id,
            user_id=interaction.user.id,
            count=len(data),
            format=fmt,
        )


class ProposalActionView(discord.ui.View):
    def __init__(self, *, service: CouncilService, proposal_id: UUID, can_cancel: bool) -> None:
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
        ok = await self.service.cancel_proposal(proposal_id=self.proposal_id)
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
    return f"#{short} → <@{p.target_id}> {p.amount}"


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
    service: CouncilService,
    proposal_id: UUID,
    status: str,
) -> None:
    """向提案人與全體理事廣播最終結果（揭露個別票）。"""
    snapshot = await service.get_snapshot(proposal_id=proposal_id)
    votes = await service.get_votes_detail(proposal_id=proposal_id)
    vote_map = dict(votes)
    lines = []
    for uid in snapshot:
        choice_str = vote_map.get(uid, "未投")
        lines.append(f"<@{uid}> → {choice_str}")
    text = "\n".join(lines)
    color = 0x2ECC71 if status == "已執行" else 0xF1C40F
    result_embed = discord.Embed(title="提案結果", color=color)
    result_embed.add_field(name="最終狀態", value=status, inline=False)
    result_embed.add_field(name="個別投票", value=text or "(無)", inline=False)

    cfg = await service.get_config(guild_id=guild.id)
    role = guild.get_role(cfg.council_role_id)
    members = role.members if role is not None else []

    # 確認提案人
    proposal = await service.get_proposal(proposal_id=proposal_id)
    proposer_user: discord.abc.Messageable | None = None
    if proposal is not None:
        proposer_user = guild.get_member(proposal.proposer_id) or await _safe_fetch_user(
            client, proposal.proposer_id
        )

    recipients: list[discord.abc.Messageable] = []
    recipients.extend(members)
    if proposer_user is not None and proposer_user.id not in [m.id for m in members]:  # type: ignore[attr-defined]
        recipients.append(proposer_user)
    for m in recipients:
        try:
            await m.send(embed=result_embed)
        except Exception:
            pass


async def _register_persistent_views(client: discord.Client, service: CouncilService) -> None:
    """在啟動後註冊所有進行中提案的 persistent VotingView。"""
    pool = get_pool()
    async with pool.acquire() as conn:
        from src.db.gateway.council_governance import CouncilGovernanceGateway

        gw = CouncilGovernanceGateway()
        active = await gw.list_active_proposals(conn)
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
