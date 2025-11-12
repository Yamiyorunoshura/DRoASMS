"""理事會專用的分頁元件。"""

from __future__ import annotations

from typing import Any, Sequence

import discord

from src.bot.commands.state_council import _send_message_compat as _send_msg_compat
from src.bot.services.department_registry import get_registry
from src.bot.ui.paginator import EmbedPaginator


class CouncilProposalPaginator(EmbedPaginator):
    """
    專門用於理事會提案列表的分頁器。

    繼承自 EmbedPaginator，提供理事會提案特定的格式化和功能。
    """

    def __init__(
        self,
        *,
        proposals: Sequence[Any],
        author_id: int | None = None,
        timeout: float = 600.0,
        guild: discord.Guild | None = None,
    ) -> None:
        """
        初始化理事會提案分頁器。

        Args:
            proposals: 理事會提案序列
            author_id: 限制使用者ID
            timeout: 超時時間
            guild: Discord 伺服器對象，用於解析部門資訊
        """
        self.guild = guild

        super().__init__(
            items=proposals,
            page_size=10,  # 保持與現有實作一致
            embed_factory=self._create_council_proposal_embed,
            author_id=author_id,
            timeout=timeout,
        )

    def _create_council_proposal_embed(
        self, proposals: list[Any], page_num: int, total_pages: int
    ) -> discord.Embed:
        """
        創建理事會提案列表的嵌入訊息。

        Args:
            proposals: 當前頁面的提案列表
            page_num: 當前頁碼
            total_pages: 總頁數

        Returns:
            配置好的嵌入訊息
        """
        embed = discord.Embed(
            title="🏛️ 理事會提案列表",
            color=0x95A5A6,
            description=f"第 {page_num} 頁，共 {total_pages} 頁",
        )

        if not proposals:
            embed.add_field(
                name="📭 無進行中提案",
                value="目前沒有進行中的理事會提案。",
                inline=False,
            )
            return embed

        for i, proposal in enumerate(proposals, 1):
            # 格式化提案標題和描述
            title = self._format_council_proposal_title(proposal)
            description = self._format_council_proposal_description(proposal)

            # 添加到嵌入訊息
            embed.add_field(
                name=f"{i}. {title}",
                value=description,
                inline=False,
            )

        return embed

    def _format_council_proposal_title(self, proposal: Any) -> str:
        """
        格式化理事會提案標題。

        Args:
            proposal: 提案對象

        Returns:
            格式化後的標題
        """
        short_id = str(proposal.proposal_id)[:8]

        # 根據提案類型顯示不同的受款人資訊
        if hasattr(proposal, "target_department_id") and proposal.target_department_id:
            registry = get_registry()
            dept = registry.get_by_id(proposal.target_department_id)
            target_str = dept.name if dept else f"部門 {proposal.target_department_id}"
        else:
            target_str = f"<@{proposal.target_id}>"

        return f"#{short_id} → {target_str} 💰{proposal.amount:,}"

    def _format_council_proposal_description(self, proposal: Any) -> str:
        """
        格式化理事會提案描述。

        Args:
            proposal: 提案對象

        Returns:
            格式化後的描述
        """
        parts: list[str] = []

        # 狀態
        status_emoji = {
            "進行中": "🔄",
            "已執行": "✅",
            "已否決": "❌",
            "已逾時": "⏰",
            "已撤案": "🚫",
        }
        emoji = status_emoji.get(proposal.status, "📋")
        parts.append(f"{emoji} 狀態：{proposal.status}")

        # 截止時間
        if hasattr(proposal, "deadline_at") and proposal.deadline_at:
            deadline = proposal.deadline_at.strftime("%m-%d %H:%M UTC")
            parts.append(f"⏰ 截止：{deadline}")

        # 投票門檻
        if hasattr(proposal, "threshold_t"):
            parts.append(f"🎯 門檻 T：{proposal.threshold_t}")

        # 描述
        if proposal.description:
            desc = proposal.description.strip()[:60]
            if len(proposal.description) > 60:
                desc += "..."
            parts.append(f"📝 用途：{desc}")
        else:
            parts.append("📝 用途：無描述")

        return " | ".join(parts)

    def create_embed(self, page_number: int) -> discord.Embed:
        """
        創建指定頁面的嵌入訊息，加入理事會特定的頁腳資訊。

        Args:
            page_number: 頁碼（從 0 開始）

        Returns:
            該頁面的嵌入訊息
        """
        page_items = self.get_page_items(page_number)
        embed = self.embed_factory(page_items, page_number + 1, self.total_pages)

        # 添加理事會特定的頁腳資訊
        if self.show_page_numbers and self.total_pages > 1:
            footer_text = embed.footer.text if embed.footer.text else ""
            if footer_text:
                footer_text += f" | 第 {page_number + 1} 頁，共 {self.total_pages} 頁"
            else:
                footer_text = f"第 {page_number + 1} 頁，共 {self.total_pages} 頁"

            # 添加理事會特定的提示
            if page_number == 0:
                footer_text += " | 使用下方按鈕導航"

            embed.set_footer(text=footer_text)

        return embed

    def create_view(self) -> discord.ui.View:
        """
        創建理事會專用的分頁檢視。

        Returns:
            配置好的 discord.ui.View
        """
        if self.total_pages <= 1:
            # 只有一頁時不需要分頁按鈕
            return discord.ui.View(timeout=self.timeout)

        view = discord.ui.View(timeout=self.timeout)

        # 第一頁按鈕
        first_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="⏮️",
            style=discord.ButtonStyle.secondary,
            custom_id="council_paginator_first",
            disabled=self.current_page <= 0,
        )
        first_btn.callback = self._on_first_page
        view.add_item(first_btn)

        # 上一頁按鈕
        prev_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="◀️",
            style=discord.ButtonStyle.secondary,
            custom_id="council_paginator_prev",
            disabled=self.current_page <= 0,
        )
        prev_btn.callback = self._on_prev_page
        view.add_item(prev_btn)

        # 頁碼指示器
        if self.show_indicator:
            page_indicator: discord.ui.Button[Any] = discord.ui.Button(
                label=f"{self.current_page + 1}/{self.total_pages}",
                style=discord.ButtonStyle.secondary,
                custom_id="council_paginator_indicator",
                disabled=True,
            )
            view.add_item(page_indicator)

        # 下一頁按鈕
        next_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="▶️",
            style=discord.ButtonStyle.secondary,
            custom_id="council_paginator_next",
            disabled=self.current_page >= self.total_pages - 1,
        )
        next_btn.callback = self._on_next_page
        view.add_item(next_btn)

        # 最後一頁按鈕
        last_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="⏭️",
            style=discord.ButtonStyle.secondary,
            custom_id="council_paginator_last",
            disabled=self.current_page >= self.total_pages - 1,
        )
        last_btn.callback = self._on_last_page
        view.add_item(last_btn)

        # 如果頁數很多，添加跳轉選單
        if self.total_pages > 5:
            page_options: list[discord.SelectOption] = [
                discord.SelectOption(
                    label=f"第 {i} 頁",
                    value=str(i - 1),  # 轉換為 0-based
                )
                for i in range(1, min(self.total_pages + 1, 21))  # 限制選項數量
            ]

            if self.total_pages > 20:
                page_options.append(
                    discord.SelectOption(
                        label="更多頁面...",
                        value="more",
                        description="使用導航按鈕瀏覽所有頁面",
                    )
                )

            page_select: discord.ui.Select[Any] = discord.ui.Select(
                placeholder="跳轉到頁面...",
                options=page_options,
                min_values=1,
                max_values=1,
                custom_id="council_paginator_jump",
            )
            page_select.callback = self._on_jump_page
            view.add_item(page_select)

        return view

    async def _on_first_page(self, interaction: discord.Interaction) -> None:
        """處理第一頁按鈕點擊。"""
        if self.author_id and interaction.user.id != self.author_id:
            await _send_msg_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        if self.current_page != 0:
            self.current_page = 0
            await self._update_page(interaction)

    async def _on_last_page(self, interaction: discord.Interaction) -> None:
        """處理最後一頁按鈕點擊。"""
        if self.author_id and interaction.user.id != self.author_id:
            await _send_msg_compat(interaction, content="僅限面板開啟者操作。", ephemeral=True)
            return

        if self.current_page != self.total_pages - 1:
            self.current_page = self.total_pages - 1
            await self._update_page(interaction)
