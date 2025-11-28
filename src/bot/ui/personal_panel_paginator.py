"""個人面板分頁元件，提供用戶的個人經濟管理介面。"""

from __future__ import annotations

from datetime import timezone
from typing import TYPE_CHECKING, Any, Callable, Coroutine, cast

import discord
import structlog

from src.bot.interaction_compat import (
    edit_message_compat,
    send_message_compat,
    send_modal_compat,
)
from src.bot.services.application_service import ApplicationService
from src.bot.services.council_service import CouncilService
from src.bot.services.currency_config_service import CurrencyConfigResult
from src.bot.services.department_registry import Department, get_registry
from src.bot.services.state_council_service import (
    StateCouncilNotConfiguredError,
    StateCouncilService,
)
from src.bot.ui.base import PersistentPanelView
from src.bot.ui.paginator import EmbedPaginator
from src.cython_ext.state_council_models import (
    LicenseApplication,
    WelfareApplication,
)

if TYPE_CHECKING:
    from src.bot.services.balance_service import BalanceSnapshot, HistoryEntry

LOGGER = structlog.get_logger(__name__)


class PersonalPanelView(PersistentPanelView):
    """
    個人面板主檢視。

    提供四個分頁：首頁、財產、轉帳、政府服務。
    """

    panel_type = "personal"

    def __init__(
        self,
        *,
        author_id: int,
        guild_id: int,
        balance_snapshot: "BalanceSnapshot",
        history_entries: list["HistoryEntry"],
        currency_config: CurrencyConfigResult,
        transfer_callback: Callable[
            [int, int, int, str | None, int],
            Coroutine[Any, Any, tuple[bool, str]],
        ],
        refresh_callback: Callable[
            [],
            Coroutine[Any, Any, tuple["BalanceSnapshot", list["HistoryEntry"]]],
        ],
        state_council_service: StateCouncilService | None = None,
        timeout: float = 600.0,
    ) -> None:
        """
        初始化個人面板檢視。

        Args:
            author_id: 面板擁有者的使用者 ID
            guild_id: 伺服器 ID
            balance_snapshot: 餘額快照
            history_entries: 交易歷史記錄
            currency_config: 貨幣配置
            transfer_callback: 轉帳回調函數
                (guild_id, initiator_id, target_id, reason, amount) -> (success, message)
            refresh_callback: 刷新數據回調函數
            state_council_service: 國務院服務，用於解析政府帳戶（可選）
            timeout: 超時時間（秒）
        """
        super().__init__(author_id=author_id, timeout=timeout)
        self._author_id: int = author_id  # Store non-optional copy for type safety
        self.guild_id = guild_id
        self.balance_snapshot = balance_snapshot
        self.history_entries = history_entries
        self.currency_config = currency_config
        self.transfer_callback = transfer_callback
        self.refresh_callback = refresh_callback
        self.state_council_service = state_council_service
        self.application_service = ApplicationService()

        # 當前分頁：home, property, transfer, government
        self.current_tab = "home"

        # 交易歷史分頁器
        self.history_paginator: EmbedPaginator | None = None
        self.history_page = 0

        # 暫存轉帳資訊
        self._pending_transfer_target_id: int | None = None
        self._pending_transfer_target_name: str | None = None

        # 政府服務分頁狀態
        self._welfare_applications: list[WelfareApplication] = []
        self._license_applications: list[LicenseApplication] = []
        self._gov_page = 0
        self._gov_page_size = 5

        # 初始化視圖
        self._update_view_items()

    def _get_currency_display(self) -> str:
        """取得貨幣顯示字串。"""
        if self.currency_config.currency_icon:
            return (
                f"{self.currency_config.currency_name} {self.currency_config.currency_icon}".strip()
            )
        return self.currency_config.currency_name

    def create_home_embed(self) -> discord.Embed:
        """創建首頁嵌入訊息。"""
        currency_display = self._get_currency_display()
        embed = discord.Embed(
            title="👤 個人面板",
            color=0x3498DB,
            description="歡迎使用個人面板，您可以在此查看餘額、交易歷史和進行轉帳。",
        )
        embed.add_field(
            name="💰 目前餘額",
            value=f"**{self.balance_snapshot.balance:,}** {currency_display}",
            inline=False,
        )
        timestamp = self.balance_snapshot.last_modified_at.astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        embed.add_field(
            name="🕒 最後更新",
            value=timestamp,
            inline=False,
        )
        if self.balance_snapshot.is_throttled and self.balance_snapshot.throttled_until:
            cooldown = self.balance_snapshot.throttled_until.astimezone(timezone.utc).strftime(
                "%Y-%m-%d %H:%M UTC"
            )
            embed.add_field(
                name="⏳ 轉帳冷卻中",
                value=f"預計至：{cooldown}",
                inline=False,
            )
        embed.set_footer(text="使用下方按鈕切換分頁")
        return embed

    def create_property_embed(
        self, page_items: list[Any], page_num: int, total_pages: int
    ) -> discord.Embed:
        """創建財產分頁嵌入訊息。"""
        currency_display = self._get_currency_display()
        embed = discord.Embed(
            title="📊 財產 - 交易歷史",
            color=0x2ECC71,
        )
        embed.add_field(
            name="💰 目前餘額",
            value=f"**{self.balance_snapshot.balance:,}** {currency_display}",
            inline=False,
        )

        if not page_items:
            embed.add_field(
                name="📭 無交易記錄",
                value="目前沒有可顯示的交易記錄。",
                inline=False,
            )
        else:
            lines: list[str] = []
            for entry in page_items:
                timestamp = entry.created_at.astimezone(timezone.utc).strftime("%m-%d %H:%M")
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
                line = f"`{timestamp}` {verb} **{sign}{entry.amount:,}** {currency_display}"
                if entry.reason:
                    reason_short = (
                        entry.reason[:20] + "..." if len(entry.reason) > 20 else entry.reason
                    )
                    line += f"\n└─ {counterpart_display} | {reason_short}"
                else:
                    line += f"\n└─ {counterpart_display}"
                lines.append(line)

            embed.add_field(
                name=f"📜 交易記錄（第 {page_num} 頁，共 {total_pages} 頁）",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text="使用下方按鈕切換分頁或翻頁")
        return embed

    def create_transfer_embed(self) -> discord.Embed:
        """創建轉帳分頁嵌入訊息。"""
        currency_display = self._get_currency_display()
        embed = discord.Embed(
            title="💸 轉帳",
            color=0xE74C3C,
            description="點擊下方按鈕發起轉帳。",
        )
        embed.add_field(
            name="💰 可用餘額",
            value=f"**{self.balance_snapshot.balance:,}** {currency_display}",
            inline=False,
        )
        if self.balance_snapshot.is_throttled and self.balance_snapshot.throttled_until:
            cooldown = self.balance_snapshot.throttled_until.astimezone(timezone.utc).strftime(
                "%Y-%m-%d %H:%M UTC"
            )
            embed.add_field(
                name="⚠️ 注意",
                value=f"您目前處於轉帳冷卻中，預計至：{cooldown}",
                inline=False,
            )
        embed.add_field(
            name="📋 操作說明",
            value=(
                "1️⃣ 點擊「💸 轉帳」按鈕\n"
                "2️⃣ 選擇轉帳類型（使用者/政府部門/公司）\n"
                "3️⃣ 選擇收款對象\n"
                "4️⃣ 在彈出的視窗中輸入金額和備註"
            ),
            inline=False,
        )
        embed.set_footer(text="使用下方按鈕切換分頁")
        return embed

    def _update_view_items(self) -> None:
        """更新視圖中的按鈕和選單。"""
        self.clear_items()

        # 分頁切換按鈕
        home_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🏠 首頁",
            style=(
                discord.ButtonStyle.primary
                if self.current_tab == "home"
                else discord.ButtonStyle.secondary
            ),
            custom_id="personal_panel_home",
            row=0,
        )
        home_btn.callback = self._on_home_tab
        self.add_item(home_btn)

        property_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="📊 財產",
            style=(
                discord.ButtonStyle.primary
                if self.current_tab == "property"
                else discord.ButtonStyle.secondary
            ),
            custom_id="personal_panel_property",
            row=0,
        )
        property_btn.callback = self._on_property_tab
        self.add_item(property_btn)

        transfer_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="💸 轉帳",
            style=(
                discord.ButtonStyle.primary
                if self.current_tab == "transfer"
                else discord.ButtonStyle.secondary
            ),
            custom_id="personal_panel_transfer",
            row=0,
        )
        transfer_btn.callback = self._on_transfer_tab
        self.add_item(transfer_btn)

        # 政府服務按鈕
        gov_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🏛️ 政府服務",
            style=(
                discord.ButtonStyle.primary
                if self.current_tab == "government"
                else discord.ButtonStyle.secondary
            ),
            custom_id="personal_panel_government",
            row=0,
        )
        gov_btn.callback = self._on_government_tab
        self.add_item(gov_btn)

        # 刷新按鈕 - 移到 row=1 因為 row=0 已滿
        refresh_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🔄 刷新",
            style=discord.ButtonStyle.secondary,
            custom_id="personal_panel_refresh",
            row=1,
        )
        refresh_btn.callback = self._on_refresh
        self.add_item(refresh_btn)

        # 根據當前分頁添加額外的控制項
        if self.current_tab == "property":
            self._add_property_controls()
        elif self.current_tab == "transfer":
            self._add_transfer_controls()
        elif self.current_tab == "government":
            self._add_government_controls()

    def _add_property_controls(self) -> None:
        """添加財產分頁的分頁控制按鈕。"""
        if not self.history_paginator or self.history_paginator.total_pages <= 1:
            return

        # 上一頁
        prev_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="◀️ 上一頁",
            style=discord.ButtonStyle.secondary,
            custom_id="personal_panel_property_prev",
            disabled=self.history_page <= 0,
            row=1,
        )
        prev_btn.callback = self._on_property_prev
        self.add_item(prev_btn)

        # 頁碼指示器
        indicator_btn: discord.ui.Button[Any] = discord.ui.Button(
            label=f"{self.history_page + 1}/{self.history_paginator.total_pages}",
            style=discord.ButtonStyle.secondary,
            custom_id="personal_panel_property_indicator",
            disabled=True,
            row=1,
        )
        self.add_item(indicator_btn)

        # 下一頁
        next_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="下一頁 ▶️",
            style=discord.ButtonStyle.secondary,
            custom_id="personal_panel_property_next",
            disabled=self.history_page >= self.history_paginator.total_pages - 1,
            row=1,
        )
        next_btn.callback = self._on_property_next
        self.add_item(next_btn)

    def _add_transfer_controls(self) -> None:
        """添加轉帳分頁的控制項：單一轉帳按鈕。"""
        # 轉帳按鈕 - 點擊後發送類型選擇面板
        transfer_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="💸 轉帳",
            style=discord.ButtonStyle.primary,
            custom_id="personal_panel_transfer_action",
            row=2,
        )
        transfer_btn.callback = self._on_transfer_button
        self.add_item(transfer_btn)

    async def _on_transfer_button(self, interaction: discord.Interaction) -> None:
        """處理轉帳按鈕點擊，發送類型選擇面板。"""
        if not await self._check_author(interaction):
            return

        view = PersonalTransferTypeSelectionView(
            guild_id=self.guild_id,
            author_id=self._author_id,
            balance=self.balance_snapshot.balance,
            currency_display=self._get_currency_display(),
            transfer_callback=self.transfer_callback,
            refresh_callback=self.refresh_callback,
            state_council_service=self.state_council_service,
        )
        embed = discord.Embed(
            title="💸 選擇轉帳類型",
            color=0xE74C3C,
            description="請選擇您要轉帳的對象類型：",
        )
        embed.add_field(
            name="💰 可用餘額",
            value=f"**{self.balance_snapshot.balance:,}** {self._get_currency_display()}",
            inline=False,
        )
        await send_message_compat(interaction, embed=embed, view=view, ephemeral=True)

    async def _check_author(self, interaction: discord.Interaction) -> bool:
        """檢查操作者是否為面板擁有者。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return False
        return True

    async def _on_home_tab(self, interaction: discord.Interaction) -> None:
        """切換到首頁分頁。"""
        if not await self._check_author(interaction):
            return
        self.current_tab = "home"
        self._update_view_items()
        await edit_message_compat(interaction, embed=self.create_home_embed(), view=self)

    async def _on_property_tab(self, interaction: discord.Interaction) -> None:
        """切換到財產分頁。"""
        if not await self._check_author(interaction):
            return
        self.current_tab = "property"
        self.history_page = 0

        # 初始化分頁器
        self.history_paginator = EmbedPaginator(
            items=self.history_entries,
            page_size=5,
            embed_factory=self.create_property_embed,
            author_id=self.author_id,
        )

        self._update_view_items()
        page_items = self.history_paginator.get_page_items(self.history_page)
        embed = self.create_property_embed(
            page_items,
            self.history_page + 1,
            self.history_paginator.total_pages,
        )
        await edit_message_compat(interaction, embed=embed, view=self)

    async def _on_transfer_tab(self, interaction: discord.Interaction) -> None:
        """切換到轉帳分頁。"""
        if not await self._check_author(interaction):
            return
        self.current_tab = "transfer"
        self._update_view_items()
        await edit_message_compat(interaction, embed=self.create_transfer_embed(), view=self)

    async def _on_refresh(self, interaction: discord.Interaction) -> None:
        """刷新面板數據。"""
        if not await self._check_author(interaction):
            return

        try:
            self.balance_snapshot, self.history_entries = await self.refresh_callback()
        except Exception as exc:
            LOGGER.exception("personal_panel.refresh.error", error=str(exc))
            await send_message_compat(
                interaction, content="刷新數據失敗，請稍後再試。", ephemeral=True
            )
            return

        # 重新初始化分頁器（如果在財產分頁）
        if self.current_tab == "property":
            self.history_paginator = EmbedPaginator(
                items=self.history_entries,
                page_size=5,
                embed_factory=self.create_property_embed,
                author_id=self.author_id,
            )
            self.history_page = 0

        self._update_view_items()

        # 根據當前分頁更新顯示
        if self.current_tab == "home":
            embed = self.create_home_embed()
        elif self.current_tab == "property" and self.history_paginator:
            page_items = self.history_paginator.get_page_items(self.history_page)
            embed = self.create_property_embed(
                page_items,
                self.history_page + 1,
                self.history_paginator.total_pages,
            )
        else:
            embed = self.create_transfer_embed()

        await edit_message_compat(interaction, embed=embed, view=self)

    async def _on_property_prev(self, interaction: discord.Interaction) -> None:
        """財產分頁：上一頁。"""
        if not await self._check_author(interaction):
            return
        if self.history_paginator and self.history_page > 0:
            self.history_page -= 1
            self._update_view_items()
            page_items = self.history_paginator.get_page_items(self.history_page)
            embed = self.create_property_embed(
                page_items,
                self.history_page + 1,
                self.history_paginator.total_pages,
            )
            await edit_message_compat(interaction, embed=embed, view=self)

    async def _on_property_next(self, interaction: discord.Interaction) -> None:
        """財產分頁：下一頁。"""
        if not await self._check_author(interaction):
            return
        if self.history_paginator and self.history_page < self.history_paginator.total_pages - 1:
            self.history_page += 1
            self._update_view_items()
            page_items = self.history_paginator.get_page_items(self.history_page)
            embed = self.create_property_embed(
                page_items,
                self.history_page + 1,
                self.history_paginator.total_pages,
            )
            await edit_message_compat(interaction, embed=embed, view=self)

    async def _on_user_select(self, interaction: discord.Interaction) -> None:
        """處理使用者選擇。"""
        if not await self._check_author(interaction):
            return

        if not interaction.data:
            return

        # 取得選中的使用者
        data = cast(dict[str, Any] | None, interaction.data)
        values = cast(list[str] | None, data.get("values") if data else None)
        if not values:
            return

        user_id = int(values[0])
        if user_id == self.author_id:
            await send_message_compat(interaction, content="❌ 您不能轉帳給自己。", ephemeral=True)
            return

        # 嘗試從 guild 取得成員名稱
        member_name = f"<@{user_id}>"
        if interaction.guild:
            member = interaction.guild.get_member(user_id)
            if member:
                member_name = member.display_name

        self._pending_transfer_target_id = user_id
        self._pending_transfer_target_name = member_name

        # 彈出轉帳 Modal
        modal = TransferModal(
            target_name=member_name,
            currency_display=self._get_currency_display(),
            available_balance=self.balance_snapshot.balance,
            on_submit=self._handle_transfer_submit,
        )
        await send_modal_compat(interaction, modal)

    async def _on_govt_select(self, interaction: discord.Interaction) -> None:
        """處理政府機構選擇（包含常任理事會、最高人民會議、國務院及下屬部門）。"""
        if not await self._check_author(interaction):
            return

        if not interaction.data:
            return

        # 取得選中的機構
        data = cast(dict[str, Any] | None, interaction.data)
        values = cast(list[str] | None, data.get("values") if data else None)
        if not values:
            return

        selection = values[0]
        registry = get_registry()

        # 解析選擇類型
        if selection.startswith("institution:"):
            institution_id = selection.split(":", 1)[1]
            target_account_id = self._derive_institution_account_id(self.guild_id, institution_id)
            if target_account_id is None:
                await send_message_compat(
                    interaction, content="❌ 該伺服器尚未設定此政府機構。", ephemeral=True
                )
                return
            inst = registry.get_by_id(institution_id)
            if inst:
                self._pending_transfer_target_name = (
                    f"{inst.emoji} {inst.name}" if inst.emoji else inst.name
                )
            else:
                self._pending_transfer_target_name = institution_id
        elif selection.startswith("department:"):
            dept_id = selection.split(":", 1)[1]
            dept = registry.get_by_id(dept_id)
            if not dept:
                await send_message_compat(
                    interaction, content="❌ 找不到指定的部門。", ephemeral=True
                )
                return
            target_account_id = await self._resolve_department_account_id(self.guild_id, dept)
            self._pending_transfer_target_name = (
                f"{dept.emoji} {dept.name}" if dept.emoji else dept.name
            )
        else:
            await send_message_compat(interaction, content="❌ 無效的選擇。", ephemeral=True)
            return

        self._pending_transfer_target_id = target_account_id

        # 彈出轉帳 Modal
        modal = TransferModal(
            target_name=self._pending_transfer_target_name,
            currency_display=self._get_currency_display(),
            available_balance=self.balance_snapshot.balance,
            on_submit=self._handle_transfer_submit,
        )
        await send_modal_compat(interaction, modal)

    def _derive_institution_account_id(self, guild_id: int, institution_id: str) -> int | None:
        """計算政府機構帳戶 ID。

        帳戶 ID 映射：
        - 常任理事會: CouncilService.derive_council_account_id (9_0e15 + guild_id)
        - 最高人民會議: 9_500_000_000_000_000 + guild_id + code(200)
        - 國務院: 路由至財政部帳戶 (9_500_000_000_000_000 + guild_id + 2)

        Note: 外部向國務院轉帳時，資金自動入帳至財政部。
        """
        code = 0
        if institution_id in {"permanent_council", "supreme_assembly", "state_council"}:
            try:
                dept = get_registry().get_by_id(institution_id)
                code = dept.code if dept else 0
            except Exception:
                code = 0

        if institution_id == "permanent_council":
            return CouncilService.derive_council_account_id(guild_id)
        elif institution_id == "supreme_assembly":
            return 9_500_000_000_000_000 + guild_id + code
        elif institution_id == "state_council":
            # 外部向國務院轉帳自動路由至財政部 (dept_code=2)
            finance_dept_code = 2
            return 9_500_000_000_000_000 + guild_id + finance_dept_code
        return None

    async def _resolve_department_account_id(self, guild_id: int, dept: Department) -> int:
        """解析部門帳戶 ID，優先使用國務院配置，否則回退推導公式。"""
        if self.state_council_service is not None:
            try:
                account_id = await self.state_council_service.get_department_account_id(
                    guild_id=guild_id,
                    department=dept.name,
                )
                return int(account_id)
            except StateCouncilNotConfiguredError:
                LOGGER.debug(
                    "personal_panel.department_account.not_configured",
                    guild_id=guild_id,
                    department=dept.id,
                )
            except Exception as exc:  # pragma: no cover - logging path
                LOGGER.warning(
                    "personal_panel.department_account.resolve_failed",
                    guild_id=guild_id,
                    department=dept.id,
                    error=str(exc),
                )

        return self._derive_department_account_id(guild_id, dept)

    def _derive_department_account_id(self, guild_id: int, dept: Department) -> int:
        """計算部門帳戶 ID（與 StateCouncilService 保持一致）。

        公式：9_500_000_000_000_000 + guild_id + dept_code
        """
        base = 9_500_000_000_000_000
        return int(base + guild_id + dept.code)

    async def _handle_transfer_submit(
        self,
        interaction: discord.Interaction,
        amount: int,
        reason: str | None,
    ) -> None:
        """處理轉帳 Modal 提交。"""
        if self._pending_transfer_target_id is None:
            await send_message_compat(interaction, content="❌ 轉帳目標無效。", ephemeral=True)
            return

        if amount <= 0:
            await send_message_compat(
                interaction, content="❌ 轉帳金額必須大於 0。", ephemeral=True
            )
            return

        if amount > self.balance_snapshot.balance:
            await send_message_compat(interaction, content="❌ 餘額不足。", ephemeral=True)
            return

        try:
            success, message = await self.transfer_callback(
                self.guild_id,
                self._author_id,
                self._pending_transfer_target_id,
                reason,
                amount,
            )

            if success:
                # 刷新餘額
                try:
                    self.balance_snapshot, self.history_entries = await self.refresh_callback()
                except Exception as exc:
                    LOGGER.warning("personal_panel.refresh_after_transfer.error", error=str(exc))

                currency_display = self._get_currency_display()
                target = self._pending_transfer_target_name
                balance = self.balance_snapshot.balance
                result_msg = (
                    f"✅ 已成功將 **{amount:,}** {currency_display} 轉給 {target}。\n"
                    f"💰 目前餘額：**{balance:,}** {currency_display}"
                )
                if reason:
                    result_msg += f"\n📝 備註：{reason}"
                await send_message_compat(interaction, content=result_msg, ephemeral=True)
            else:
                await send_message_compat(interaction, content=f"❌ {message}", ephemeral=True)
        except Exception as exc:
            LOGGER.exception("personal_panel.transfer.error", error=str(exc))
            await send_message_compat(
                interaction, content="❌ 轉帳失敗，請稍後再試。", ephemeral=True
            )
        finally:
            self._pending_transfer_target_id = None
            self._pending_transfer_target_name = None

    # ========== 政府服務分頁方法 ==========

    def create_government_embed(self) -> discord.Embed:
        """創建政府服務分頁嵌入訊息。"""
        embed = discord.Embed(
            title="🏛️ 政府服務",
            color=0x9B59B6,
            description="透過此頁面向政府申請福利或商業許可。",
        )
        embed.add_field(
            name="📋 可申請服務",
            value=(
                "• **💰 申請福利** - 向內政部申請福利金\n"
                "• **📜 申請商業許可** - 申請商業經營許可證"
            ),
            inline=False,
        )

        # 顯示申請歷史摘要
        all_applications = self._get_combined_applications()
        if all_applications:
            pending = sum(1 for a in all_applications if a[1] == "pending")
            approved = sum(1 for a in all_applications if a[1] == "approved")
            rejected = sum(1 for a in all_applications if a[1] == "rejected")
            embed.add_field(
                name="📊 我的申請狀態",
                value=f"⏳ 待審批: {pending} | ✅ 已批准: {approved} | ❌ 已拒絕: {rejected}",
                inline=False,
            )
        else:
            embed.add_field(
                name="📊 我的申請狀態",
                value="目前沒有申請記錄",
                inline=False,
            )

        embed.set_footer(text="使用下方按鈕申請服務或查看申請歷史")
        return embed

    def _get_combined_applications(
        self,
    ) -> list[tuple[str, str, str, Any]]:
        """取得合併的申請列表 (type, status, summary, application)。"""
        combined: list[tuple[str, str, str, Any]] = []
        for welfare_app in self._welfare_applications:
            summary = f"福利申請 - {welfare_app.amount:,} 元"
            combined.append(("welfare", welfare_app.status, summary, welfare_app))
        for license_app in self._license_applications:
            summary = f"商業許可 - {license_app.license_type}"
            combined.append(("license", license_app.status, summary, license_app))
        # 按時間排序（最新在前）
        combined.sort(key=lambda x: x[3].created_at, reverse=True)
        return combined

    def create_application_history_embed(
        self, page_items: list[tuple[str, str, str, Any]], page_num: int, total_pages: int
    ) -> discord.Embed:
        """創建申請歷史嵌入訊息。"""
        embed = discord.Embed(
            title="📋 我的申請記錄",
            color=0x9B59B6,
        )

        if not page_items:
            embed.add_field(
                name="📭 無申請記錄",
                value="目前沒有任何申請記錄。",
                inline=False,
            )
        else:
            lines: list[str] = []
            for _, status, summary, app in page_items:
                timestamp = app.created_at.astimezone(timezone.utc).strftime("%m-%d %H:%M")
                if status == "pending":
                    status_icon = "⏳ 待審批"
                elif status == "approved":
                    status_icon = "✅ 已批准"
                else:
                    status_icon = "❌ 已拒絕"

                line = f"`{timestamp}` {summary}\n└─ {status_icon}"
                if status == "rejected" and app.rejection_reason:
                    reason_short = (
                        app.rejection_reason[:30] + "..."
                        if len(app.rejection_reason) > 30
                        else app.rejection_reason
                    )
                    line += f" | {reason_short}"
                lines.append(line)

            embed.add_field(
                name=f"申請記錄（第 {page_num} 頁，共 {total_pages} 頁）",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text="使用下方按鈕導航或返回政府服務")
        return embed

    def _add_government_controls(self) -> None:
        """添加政府服務分頁的控制項。"""
        # 申請福利按鈕
        welfare_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="💰 申請福利",
            style=discord.ButtonStyle.success,
            custom_id="personal_panel_apply_welfare",
            row=2,
        )
        welfare_btn.callback = self._on_apply_welfare
        self.add_item(welfare_btn)

        # 申請商業許可按鈕
        license_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="📜 申請商業許可",
            style=discord.ButtonStyle.success,
            custom_id="personal_panel_apply_license",
            row=2,
        )
        license_btn.callback = self._on_apply_license
        self.add_item(license_btn)

        # 查看申請歷史按鈕
        history_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="📋 申請歷史",
            style=discord.ButtonStyle.secondary,
            custom_id="personal_panel_application_history",
            row=2,
        )
        history_btn.callback = self._on_application_history
        self.add_item(history_btn)

    async def _on_government_tab(self, interaction: discord.Interaction) -> None:
        """切換到政府服務分頁。"""
        if not await self._check_author(interaction):
            return
        self.current_tab = "government"
        self._gov_page = 0

        # 載入申請記錄
        await self._load_applications()

        self._update_view_items()
        await edit_message_compat(interaction, embed=self.create_government_embed(), view=self)

    async def _load_applications(self) -> None:
        """載入用戶的申請記錄。"""
        try:
            welfare_result = await self.application_service.get_user_welfare_applications(
                guild_id=self.guild_id,
                applicant_id=self._author_id,
                limit=20,
            )
            if not welfare_result.is_err():
                self._welfare_applications = list(welfare_result.unwrap())
        except Exception as exc:
            LOGGER.warning("personal_panel.load_welfare_applications.error", error=str(exc))

        try:
            license_result = await self.application_service.get_user_license_applications(
                guild_id=self.guild_id,
                applicant_id=self._author_id,
                limit=20,
            )
            if not license_result.is_err():
                self._license_applications = list(license_result.unwrap())
        except Exception as exc:
            LOGGER.warning("personal_panel.load_license_applications.error", error=str(exc))

    async def _on_apply_welfare(self, interaction: discord.Interaction) -> None:
        """處理申請福利按鈕點擊。"""
        if not await self._check_author(interaction):
            return

        modal = WelfareApplicationModal(
            currency_display=self._get_currency_display(),
            on_submit=self._handle_welfare_submit,
        )
        await send_modal_compat(interaction, modal)

    async def _on_apply_license(self, interaction: discord.Interaction) -> None:
        """處理申請商業許可按鈕點擊。"""
        if not await self._check_author(interaction):
            return

        from src.config.settings import get_settings

        cfg = get_settings()
        license_types = list(cfg.license_types or [])
        if not license_types:
            license_types = [
                "餐飲業",
                "零售業",
                "製造業",
                "服務業",
                "建築業",
                "運輸業",
                "金融業",
            ]

        modal = LicenseApplicationModal(
            license_types=license_types,
            on_submit=self._handle_license_submit,
        )
        await send_modal_compat(interaction, modal)

    async def _on_application_history(self, interaction: discord.Interaction) -> None:
        """處理查看申請歷史按鈕點擊。"""
        if not await self._check_author(interaction):
            return

        all_applications = self._get_combined_applications()
        total_pages = max(
            1, (len(all_applications) + self._gov_page_size - 1) // self._gov_page_size
        )

        start = self._gov_page * self._gov_page_size
        end = start + self._gov_page_size
        page_items = all_applications[start:end]

        embed = self.create_application_history_embed(page_items, self._gov_page + 1, total_pages)
        await send_message_compat(interaction, embed=embed, ephemeral=True)

    async def _handle_welfare_submit(
        self,
        interaction: discord.Interaction,
        amount: int,
        reason: str,
    ) -> None:
        """處理福利申請提交。"""
        result = await self.application_service.submit_welfare_application(
            guild_id=self.guild_id,
            applicant_id=self._author_id,
            amount=amount,
            reason=reason,
        )

        if result.is_err():
            error = result.unwrap_err()
            await send_message_compat(interaction, content=f"❌ {error}", ephemeral=True)
            return

        # 重新載入申請記錄
        await self._load_applications()

        await send_message_compat(
            interaction,
            content="✅ 福利申請已提交，等待內政部審批。",
            ephemeral=True,
        )

    async def _handle_license_submit(
        self,
        interaction: discord.Interaction,
        license_type: str,
        reason: str,
    ) -> None:
        """處理商業許可申請提交。"""
        result = await self.application_service.submit_license_application(
            guild_id=self.guild_id,
            applicant_id=self._author_id,
            license_type=license_type,
            reason=reason,
        )

        if result.is_err():
            error = result.unwrap_err()
            error_msg = str(error)
            if "duplicate_pending_application" in error_msg:
                error_msg = "您已有相同類型的待審批申請"
            elif "already_has_license" in error_msg:
                error_msg = "您已持有相同類型的有效許可"
            await send_message_compat(interaction, content=f"❌ {error_msg}", ephemeral=True)
            return

        # 重新載入申請記錄
        await self._load_applications()

        await send_message_compat(
            interaction,
            content="✅ 商業許可申請已提交，等待內政部審批。",
            ephemeral=True,
        )


class WelfareApplicationModal(discord.ui.Modal):
    """福利申請 Modal。"""

    amount_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="申請金額",
        placeholder="請輸入正整數金額",
        required=True,
        min_length=1,
        max_length=15,
    )

    reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="申請原因",
        placeholder="請說明申請福利的原因",
        required=True,
        min_length=1,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )

    def __init__(
        self,
        *,
        currency_display: str,
        on_submit: Callable[[discord.Interaction, int, str], Coroutine[Any, Any, None]],
    ) -> None:
        super().__init__(title="申請福利")
        self.currency_display = currency_display
        self._on_submit = on_submit
        self.amount_input.placeholder = f"請輸入申請金額（{currency_display}）"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理 Modal 提交。"""
        try:
            amount = int(self.amount_input.value.strip())
            if amount <= 0:
                await send_message_compat(
                    interaction, content="❌ 申請金額必須為正整數。", ephemeral=True
                )
                return
        except ValueError:
            await send_message_compat(
                interaction, content="❌ 申請金額必須為正整數。", ephemeral=True
            )
            return

        reason = self.reason_input.value.strip()
        if not reason:
            await send_message_compat(interaction, content="❌ 請填寫申請原因。", ephemeral=True)
            return

        await self._on_submit(interaction, amount, reason)


class LicenseApplicationModal(discord.ui.Modal):
    """商業許可申請 Modal。"""

    license_type_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="許可類型",
        placeholder="請輸入許可類型（例如：餐飲業、零售業）",
        required=True,
        min_length=1,
        max_length=50,
    )

    reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="申請原因",
        placeholder="請說明申請商業許可的原因",
        required=True,
        min_length=1,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )

    def __init__(
        self,
        *,
        license_types: list[str],
        on_submit: Callable[[discord.Interaction, str, str], Coroutine[Any, Any, None]],
    ) -> None:
        super().__init__(title="申請商業許可")
        self.license_types = license_types
        self._on_submit = on_submit
        if license_types:
            self.license_type_input.placeholder = f"可選類型：{', '.join(license_types[:5])}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理 Modal 提交。"""
        license_type = self.license_type_input.value.strip()
        if not license_type:
            await send_message_compat(interaction, content="❌ 請填寫許可類型。", ephemeral=True)
            return

        reason = self.reason_input.value.strip()
        if not reason:
            await send_message_compat(interaction, content="❌ 請填寫申請原因。", ephemeral=True)
            return

        await self._on_submit(interaction, license_type, reason)


class TransferModal(discord.ui.Modal):
    """轉帳金額輸入 Modal。"""

    amount_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="轉帳金額",
        placeholder="請輸入正整數金額",
        required=True,
        min_length=1,
        max_length=15,
    )

    reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="備註（選填）",
        placeholder="轉帳備註",
        required=False,
        max_length=200,
        style=discord.TextStyle.paragraph,
    )

    def __init__(
        self,
        *,
        target_name: str,
        currency_display: str,
        available_balance: int,
        on_submit: Callable[[discord.Interaction, int, str | None], Coroutine[Any, Any, None]],
    ) -> None:
        super().__init__(title=f"轉帳給 {target_name}")
        self.target_name = target_name
        self.currency_display = currency_display
        self.available_balance = available_balance
        self._on_submit = on_submit

        # 更新輸入欄位的提示
        self.amount_input.placeholder = f"可用餘額：{available_balance:,} {currency_display}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理 Modal 提交。"""
        try:
            amount = int(self.amount_input.value.strip())
        except ValueError:
            await send_message_compat(interaction, content="❌ 金額必須是正整數。", ephemeral=True)
            return

        reason = self.reason_input.value.strip() if self.reason_input.value else None
        await self._on_submit(interaction, amount, reason)


# --- Personal Transfer Type Selection UI ---


class PersonalTransferTypeSelectionView(discord.ui.View):
    """個人面板轉帳類型選擇視圖。

    提供三種轉帳對象選擇：使用者、政府部門、公司。
    """

    def __init__(
        self,
        *,
        guild_id: int,
        author_id: int,
        balance: int,
        currency_display: str,
        transfer_callback: Callable[
            [int, int, int, str | None, int],
            Coroutine[Any, Any, tuple[bool, str]],
        ],
        refresh_callback: Callable[[], Coroutine[Any, Any, tuple[Any, Any]]],
        state_council_service: "StateCouncilService | None" = None,
        timeout: float = 300.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.guild_id = guild_id
        self.author_id = author_id
        self.balance = balance
        self.currency_display = currency_display
        self.transfer_callback = transfer_callback
        self.refresh_callback = refresh_callback
        self.state_council_service = state_council_service

        # 類型選擇按鈕
        user_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="👤 使用者",
            style=discord.ButtonStyle.primary,
            custom_id="personal_transfer_type_user",
            row=0,
        )
        user_btn.callback = self._on_user_type
        self.add_item(user_btn)

        govt_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🏛️ 政府部門",
            style=discord.ButtonStyle.primary,
            custom_id="personal_transfer_type_govt",
            row=0,
        )
        govt_btn.callback = self._on_govt_type
        self.add_item(govt_btn)

        company_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="🏢 公司",
            style=discord.ButtonStyle.primary,
            custom_id="personal_transfer_type_company",
            row=0,
        )
        company_btn.callback = self._on_company_type
        self.add_item(company_btn)

    async def _check_author(self, interaction: discord.Interaction) -> bool:
        """檢查操作者是否為面板擁有者。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return False
        return True

    async def _on_user_type(self, interaction: discord.Interaction) -> None:
        """選擇使用者類型後，顯示使用者選擇器。"""
        if not await self._check_author(interaction):
            return

        view = PersonalUserSelectView(
            guild_id=self.guild_id,
            author_id=self.author_id,
            balance=self.balance,
            currency_display=self.currency_display,
            transfer_callback=self.transfer_callback,
            refresh_callback=self.refresh_callback,
        )
        await send_message_compat(
            interaction,
            content="請選擇要轉帳的使用者：",
            view=view,
            ephemeral=True,
        )

    async def _on_govt_type(self, interaction: discord.Interaction) -> None:
        """選擇政府部門類型後，顯示部門選擇器。"""
        if not await self._check_author(interaction):
            return

        view = PersonalGovtSelectView(
            guild_id=self.guild_id,
            author_id=self.author_id,
            balance=self.balance,
            currency_display=self.currency_display,
            transfer_callback=self.transfer_callback,
            refresh_callback=self.refresh_callback,
            state_council_service=self.state_council_service,
        )
        await send_message_compat(
            interaction,
            content="請選擇要轉帳的政府機構：",
            view=view,
            ephemeral=True,
        )

    async def _on_company_type(self, interaction: discord.Interaction) -> None:
        """選擇公司類型後，顯示公司選擇器。"""
        if not await self._check_author(interaction):
            return

        from src.bot.ui.company_select import CompanySelectView

        async def on_company_selected(
            select_interaction: discord.Interaction, company: Any
        ) -> None:
            """處理公司選擇。"""
            modal = TransferModal(
                target_name=f"🏢 {company.name}",
                currency_display=self.currency_display,
                available_balance=self.balance,
                on_submit=lambda i, amount, reason: self._handle_company_transfer(
                    i, amount, reason, company.account_id, company.name
                ),
            )
            await send_modal_compat(select_interaction, modal)

        view = CompanySelectView(
            guild_id=self.guild_id,
            on_company_selected=on_company_selected,
        )
        has_companies = await view.setup()

        if not has_companies:
            await send_message_compat(
                interaction,
                content="❌ 此伺服器目前沒有已登記的公司。",
                ephemeral=True,
            )
            return

        await send_message_compat(
            interaction,
            content="請選擇要轉帳的公司：",
            view=view,
            ephemeral=True,
        )

    async def _handle_company_transfer(
        self,
        interaction: discord.Interaction,
        amount: int,
        reason: str | None,
        account_id: int,
        company_name: str,
    ) -> None:
        """處理公司轉帳提交。"""
        if amount <= 0:
            await send_message_compat(
                interaction, content="❌ 轉帳金額必須大於 0。", ephemeral=True
            )
            return

        if amount > self.balance:
            await send_message_compat(interaction, content="❌ 餘額不足。", ephemeral=True)
            return

        try:
            success, message = await self.transfer_callback(
                self.guild_id,
                self.author_id,
                account_id,
                reason,
                amount,
            )

            if success:
                result_msg = (
                    f"✅ 已成功將 **{amount:,}** {self.currency_display} 轉給 🏢 {company_name}。"
                )
                if reason:
                    result_msg += f"\n📝 備註：{reason}"
                await send_message_compat(interaction, content=result_msg, ephemeral=True)
            else:
                await send_message_compat(interaction, content=f"❌ {message}", ephemeral=True)
        except Exception as exc:
            LOGGER.exception("personal_panel.company_transfer.error", error=str(exc))
            await send_message_compat(
                interaction, content="❌ 轉帳失敗，請稍後再試。", ephemeral=True
            )


class PersonalUserSelectView(discord.ui.View):
    """個人面板使用者選擇視圖。"""

    def __init__(
        self,
        *,
        guild_id: int,
        author_id: int,
        balance: int,
        currency_display: str,
        transfer_callback: Callable[
            [int, int, int, str | None, int],
            Coroutine[Any, Any, tuple[bool, str]],
        ],
        refresh_callback: Callable[[], Coroutine[Any, Any, tuple[Any, Any]]],
        timeout: float = 300.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.guild_id = guild_id
        self.author_id = author_id
        self.balance = balance
        self.currency_display = currency_display
        self.transfer_callback = transfer_callback
        self.refresh_callback = refresh_callback

        # 使用者選擇器
        user_select: discord.ui.UserSelect[Any] = discord.ui.UserSelect(
            placeholder="👤 選擇要轉帳的使用者...",
            custom_id="personal_user_select",
            min_values=1,
            max_values=1,
        )
        user_select.callback = self._on_user_select
        self.add_item(user_select)

    async def _on_user_select(self, interaction: discord.Interaction) -> None:
        """處理使用者選擇。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        if not interaction.data:
            return

        data = cast(dict[str, Any] | None, interaction.data)
        values = cast(list[str] | None, data.get("values") if data else None)
        if not values:
            return

        user_id = int(values[0])
        if user_id == self.author_id:
            await send_message_compat(interaction, content="❌ 您不能轉帳給自己。", ephemeral=True)
            return

        # 取得成員名稱
        member_name = f"<@{user_id}>"
        if interaction.guild:
            member = interaction.guild.get_member(user_id)
            if member:
                member_name = member.display_name

        # 彈出轉帳 Modal
        modal = TransferModal(
            target_name=f"👤 {member_name}",
            currency_display=self.currency_display,
            available_balance=self.balance,
            on_submit=lambda i, amount, reason: self._handle_transfer(
                i, amount, reason, user_id, member_name
            ),
        )
        await send_modal_compat(interaction, modal)

    async def _handle_transfer(
        self,
        interaction: discord.Interaction,
        amount: int,
        reason: str | None,
        target_id: int,
        target_name: str,
    ) -> None:
        """處理轉帳提交。"""
        if amount <= 0:
            await send_message_compat(
                interaction, content="❌ 轉帳金額必須大於 0。", ephemeral=True
            )
            return

        if amount > self.balance:
            await send_message_compat(interaction, content="❌ 餘額不足。", ephemeral=True)
            return

        try:
            success, message = await self.transfer_callback(
                self.guild_id,
                self.author_id,
                target_id,
                reason,
                amount,
            )

            if success:
                result_msg = (
                    f"✅ 已成功將 **{amount:,}** {self.currency_display} 轉給 👤 {target_name}。"
                )
                if reason:
                    result_msg += f"\n📝 備註：{reason}"
                await send_message_compat(interaction, content=result_msg, ephemeral=True)
            else:
                await send_message_compat(interaction, content=f"❌ {message}", ephemeral=True)
        except Exception as exc:
            LOGGER.exception("personal_panel.user_transfer.error", error=str(exc))
            await send_message_compat(
                interaction, content="❌ 轉帳失敗，請稍後再試。", ephemeral=True
            )


class PersonalGovtSelectView(discord.ui.View):
    """個人面板政府機構選擇視圖。"""

    def __init__(
        self,
        *,
        guild_id: int,
        author_id: int,
        balance: int,
        currency_display: str,
        transfer_callback: Callable[
            [int, int, int, str | None, int],
            Coroutine[Any, Any, tuple[bool, str]],
        ],
        refresh_callback: Callable[[], Coroutine[Any, Any, tuple[Any, Any]]],
        state_council_service: "StateCouncilService | None" = None,
        timeout: float = 300.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.guild_id = guild_id
        self.author_id = author_id
        self.balance = balance
        self.currency_display = currency_display
        self.transfer_callback = transfer_callback
        self.refresh_callback = refresh_callback
        self.state_council_service = state_council_service

        # 政府機構選擇器
        registry = get_registry()
        departments = list(registry.list_all())

        options: list[discord.SelectOption] = []

        # 常任理事會
        council = registry.get_by_id("permanent_council")
        if council:
            options.append(
                discord.SelectOption(
                    label=council.name,
                    value="institution:permanent_council",
                    emoji=council.emoji or "👑",
                    description="最高決策機構",
                )
            )

        # 最高人民會議
        assembly = registry.get_by_id("supreme_assembly")
        if assembly:
            options.append(
                discord.SelectOption(
                    label=assembly.name,
                    value="institution:supreme_assembly",
                    emoji=assembly.emoji or "🏛️",
                    description="最高立法機構",
                )
            )

        # 國務院
        state_council = registry.get_by_id("state_council")
        if state_council:
            options.append(
                discord.SelectOption(
                    label=state_council.name,
                    value="institution:state_council",
                    emoji=state_council.emoji or "🏛️",
                    description="國家治理執行機構",
                )
            )

        # 國務院下屬部門
        transferable_depts = [d for d in departments if d.level == "department"][:20]
        for dept in transferable_depts:
            options.append(
                discord.SelectOption(
                    label=dept.name,
                    value=f"department:{dept.id}",
                    emoji=dept.emoji if dept.emoji else "🏛️",
                    description=dept.description[:50] if dept.description else None,
                )
            )

        if options:
            govt_select: discord.ui.Select[Any] = discord.ui.Select(
                placeholder="🏛️ 選擇要轉帳的政府機構...",
                options=options[:25],
                custom_id="personal_govt_select",
                min_values=1,
                max_values=1,
            )
            govt_select.callback = self._on_govt_select
            self.add_item(govt_select)

    async def _on_govt_select(self, interaction: discord.Interaction) -> None:
        """處理政府機構選擇。"""
        if interaction.user.id != self.author_id:
            await send_message_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        if not interaction.data:
            return

        data = cast(dict[str, Any] | None, interaction.data)
        values = cast(list[str] | None, data.get("values") if data else None)
        if not values:
            return

        selection = values[0]
        registry = get_registry()

        target_account_id: int | None = None
        target_name: str = ""

        if selection.startswith("institution:"):
            institution_id = selection.split(":", 1)[1]
            target_account_id = self._derive_institution_account_id(institution_id)
            if target_account_id is None:
                await send_message_compat(
                    interaction, content="❌ 該伺服器尚未設定此政府機構。", ephemeral=True
                )
                return
            inst = registry.get_by_id(institution_id)
            if inst:
                target_name = f"{inst.emoji} {inst.name}" if inst.emoji else inst.name
            else:
                target_name = institution_id
        elif selection.startswith("department:"):
            dept_id = selection.split(":", 1)[1]
            dept = registry.get_by_id(dept_id)
            if not dept:
                await send_message_compat(
                    interaction, content="❌ 找不到指定的部門。", ephemeral=True
                )
                return
            target_account_id = await self._resolve_department_account_id(dept)
            target_name = f"{dept.emoji} {dept.name}" if dept.emoji else dept.name
        else:
            await send_message_compat(interaction, content="❌ 無效的選擇。", ephemeral=True)
            return

        # 彈出轉帳 Modal
        modal = TransferModal(
            target_name=target_name,
            currency_display=self.currency_display,
            available_balance=self.balance,
            on_submit=lambda i, amount, reason: self._handle_transfer(
                i, amount, reason, target_account_id, target_name
            ),
        )
        await send_modal_compat(interaction, modal)

    def _derive_institution_account_id(self, institution_id: str) -> int | None:
        """計算政府機構帳戶 ID。

        Note: 外部向國務院轉帳時，資金自動入帳至財政部。
        """
        code = 0
        if institution_id in {"permanent_council", "supreme_assembly", "state_council"}:
            try:
                dept = get_registry().get_by_id(institution_id)
                code = dept.code if dept else 0
            except Exception:
                code = 0

        if institution_id == "permanent_council":
            return CouncilService.derive_council_account_id(self.guild_id)
        elif institution_id == "supreme_assembly":
            return 9_500_000_000_000_000 + self.guild_id + code
        elif institution_id == "state_council":
            # 外部向國務院轉帳自動路由至財政部 (dept_code=2)
            finance_dept_code = 2
            return 9_500_000_000_000_000 + self.guild_id + finance_dept_code
        return None

    async def _resolve_department_account_id(self, dept: Department) -> int:
        """解析部門帳戶 ID。"""
        if self.state_council_service is not None:
            try:
                account_id = await self.state_council_service.get_department_account_id(
                    guild_id=self.guild_id,
                    department=dept.name,
                )
                return int(account_id)
            except StateCouncilNotConfiguredError:
                pass
            except Exception as exc:
                LOGGER.warning(
                    "personal_panel.department_account.resolve_failed",
                    guild_id=self.guild_id,
                    department=dept.id,
                    error=str(exc),
                )

        # 回退推導公式
        base = 9_500_000_000_000_000
        return int(base + self.guild_id + dept.code)

    async def _handle_transfer(
        self,
        interaction: discord.Interaction,
        amount: int,
        reason: str | None,
        target_id: int | None,
        target_name: str,
    ) -> None:
        """處理轉帳提交。"""
        if target_id is None:
            await send_message_compat(interaction, content="❌ 轉帳目標無效。", ephemeral=True)
            return

        if amount <= 0:
            await send_message_compat(
                interaction, content="❌ 轉帳金額必須大於 0。", ephemeral=True
            )
            return

        if amount > self.balance:
            await send_message_compat(interaction, content="❌ 餘額不足。", ephemeral=True)
            return

        try:
            success, message = await self.transfer_callback(
                self.guild_id,
                self.author_id,
                target_id,
                reason,
                amount,
            )

            if success:
                result_msg = (
                    f"✅ 已成功將 **{amount:,}** {self.currency_display} 轉給 {target_name}。"
                )
                if reason:
                    result_msg += f"\n📝 備註：{reason}"
                await send_message_compat(interaction, content=result_msg, ephemeral=True)
            else:
                await send_message_compat(interaction, content=f"❌ {message}", ephemeral=True)
        except Exception as exc:
            LOGGER.exception("personal_panel.govt_transfer.error", error=str(exc))
            await send_message_compat(
                interaction, content="❌ 轉帳失敗，請稍後再試。", ephemeral=True
            )


__all__ = [
    "PersonalPanelView",
    "TransferModal",
    "WelfareApplicationModal",
    "LicenseApplicationModal",
    "PersonalTransferTypeSelectionView",
    "PersonalUserSelectView",
    "PersonalGovtSelectView",
]
