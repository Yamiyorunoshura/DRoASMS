"""共用分頁元件，基於 dpy-paginator 實現。"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Sequence, cast

import discord
import structlog

LOGGER = structlog.get_logger(__name__)


class EmbedPaginator:
    """
    基於 dpy-paginator 的嵌入訊息分頁器。

    提供統一的分頁介面，支援按鈕和下拉選單導航。
    設計用於取代理事會面板和最高人民會議面板中的手動分頁邏輯。
    """

    def __init__(
        self,
        *,
        items: Sequence[Any],
        page_size: int = 10,
        embed_factory: Callable[[list[Any], int, int], discord.Embed],
        author_id: int | None = None,
        timeout: float = 600.0,
        show_page_numbers: bool = True,
        show_indicator: bool = True,
    ) -> None:
        """
        初始化分頁器。

        Args:
            items: 要分頁的項目序列
            page_size: 每頁顯示的項目數量（預設 10，保持與現有實作一致）
            embed_factory: 創建頁面嵌入訊息的工廠函數
            author_id: 限制使用者ID，如果指定則只有該使用者可以操作分頁
            timeout: 分頁器超時時間（秒）
            show_page_numbers: 是否顯示頁碼資訊
            show_indicator: 是否顯示分頁指示器
        """
        self.items = items
        self.page_size = page_size
        self.embed_factory = embed_factory
        self.author_id = author_id
        self.timeout = timeout
        self.show_page_numbers = show_page_numbers
        self.show_indicator = show_indicator

        # 計算總頁數
        self.total_pages = max(1, (len(items) + page_size - 1) // page_size)
        self.current_page = 0

        # 即時更新相關
        self._update_callback: Callable[[], Awaitable[None]] | None = None
        self._update_lock = asyncio.Lock()

    def get_page_items(self, page_number: int) -> list[Any]:
        """
        取得指定頁面的項目。

        Args:
            page_number: 頁碼（從 0 開始）

        Returns:
            該頁面的項目列表
        """
        if page_number < 0 or page_number >= self.total_pages:
            return []

        start_idx = page_number * self.page_size
        end_idx = start_idx + self.page_size
        return list(self.items[start_idx:end_idx])

    def create_embed(self, page_number: int) -> discord.Embed:
        """
        創建指定頁面的嵌入訊息。

        Args:
            page_number: 頁碼（從 0 開始）

        Returns:
            該頁面的嵌入訊息
        """
        page_items = self.get_page_items(page_number)
        embed = self.embed_factory(page_items, page_number + 1, self.total_pages)

        # 添加分頁資訊到頁腳
        if self.show_page_numbers and self.total_pages > 1:
            footer_text = embed.footer.text if embed.footer.text else ""
            if footer_text:
                footer_text += f" | 第 {page_number + 1} 頁，共 {self.total_pages} 頁"
            else:
                footer_text = f"第 {page_number + 1} 頁，共 {self.total_pages} 頁"
            embed.set_footer(text=footer_text)

        return embed

    def create_view(self) -> discord.ui.View:
        """
        創建分頁檢視。

        Returns:
            配置好的 discord.ui.View
        """
        if self.total_pages <= 1:
            # 只有一頁時不需要分頁按鈕
            return discord.ui.View(timeout=self.timeout)

        view = discord.ui.View(timeout=self.timeout)

        # 上一頁按鈕
        prev_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="◀️ 上一頁",
            style=discord.ButtonStyle.secondary,
            custom_id="paginator_prev",
            disabled=self.current_page <= 0,
        )
        prev_btn.callback = self._on_prev_page
        view.add_item(prev_btn)

        # 頁碼指示器
        if self.show_indicator:
            page_indicator: discord.ui.Button[Any] = discord.ui.Button(
                label=f"{self.current_page + 1}/{self.total_pages}",
                style=discord.ButtonStyle.secondary,
                custom_id="paginator_indicator",
                disabled=True,
            )
            view.add_item(page_indicator)

        # 下一頁按鈕
        next_btn: discord.ui.Button[Any] = discord.ui.Button(
            label="下一頁 ▶️",
            style=discord.ButtonStyle.secondary,
            custom_id="paginator_next",
            disabled=self.current_page >= self.total_pages - 1,
        )
        next_btn.callback = self._on_next_page
        view.add_item(next_btn)

        # 如果需要，可以添加跳轉到特定頁面的下拉選單
        if self.total_pages > 5:
            page_options = [
                discord.SelectOption(
                    label=f"第 {i} 頁",
                    value=str(i),
                )
                for i in range(1, min(self.total_pages + 1, 21))  # 限制選項數量
            ]

            if self.total_pages > 20:
                page_options.append(
                    discord.SelectOption(
                        label="更多頁面...",
                        value="more",
                        description="使用按鈕導航到更多頁面",
                    )
                )

            page_select: discord.ui.Select[Any] = discord.ui.Select(
                placeholder="跳轉到頁面...",
                options=page_options,
                min_values=1,
                max_values=1,
                custom_id="paginator_jump",
            )
            page_select.callback = self._on_jump_page
            view.add_item(page_select)

        return view

    async def _on_prev_page(self, interaction: discord.Interaction) -> None:
        """處理上一頁按鈕點擊。"""
        if self.author_id and interaction.user.id != self.author_id:
            await interaction.response.send_message("僅限面板開啟者操作。", ephemeral=True)
            return

        if self.current_page > 0:
            self.current_page -= 1
            await self._update_page(interaction)

    async def _on_next_page(self, interaction: discord.Interaction) -> None:
        """處理下一頁按鈕點擊。"""
        if self.author_id and interaction.user.id != self.author_id:
            await interaction.response.send_message("僅限面板開啟者操作。", ephemeral=True)
            return

        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self._update_page(interaction)

    async def _on_jump_page(self, interaction: discord.Interaction) -> None:
        """處理頁面跳轉選擇。"""
        if self.author_id and interaction.user.id != self.author_id:
            await interaction.response.send_message("僅限面板開啟者操作。", ephemeral=True)
            return

        if not interaction.data:
            return

        # 安全地取得 values 數據
        values = cast(Sequence[str] | None, getattr(interaction.data, "values", None))
        if not values or len(values) == 0:
            return

        selected_value: str = values[0]
        if selected_value == "more":
            await interaction.response.send_message(
                "請使用上一頁/下一頁按鈕導航到更多頁面。",
                ephemeral=True,
            )
            return

        try:
            page_num = int(selected_value) - 1  # 轉換為 0-based 索引
            if 0 <= page_num < self.total_pages:
                self.current_page = page_num
                await self._update_page(interaction)
        except (ValueError, IndexError):
            await interaction.response.send_message("無效的頁面選擇。", ephemeral=True)

    async def _update_page(self, interaction: discord.Interaction) -> None:
        """更新當前頁面顯示。"""
        async with self._update_lock:
            try:
                # 創建新的嵌入訊息和檢視
                new_embed = self.create_embed(self.current_page)
                new_view = self.create_view()

                # 更新訊息
                await interaction.response.edit_message(embed=new_embed, view=new_view)

                # 執行更新回調
                if self._update_callback:
                    try:
                        await self._update_callback()
                    except Exception as exc:
                        LOGGER.warning("paginator.update_callback.error", error=str(exc))

            except Exception as exc:
                LOGGER.exception("paginator.update_page.error", error=str(exc))
                await interaction.response.send_message(
                    "分頁更新失敗，請稍後再試。",
                    ephemeral=True,
                )

    def set_update_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """
        設置即時更新回調函數。

        當分頁器需要即時更新時（例如新增項目、刪除項目），
        會調用此回調來刷新數據。
        """
        self._update_callback = callback

    async def refresh_items(self, new_items: Sequence[Any]) -> None:
        """
        刷新分頁器的項目列表。

        Args:
            new_items: 新的項目序列
        """
        async with self._update_lock:
            self.items = new_items
            self.total_pages = max(1, (len(new_items) + self.page_size - 1) // self.page_size)

            # 確保當前頁面仍然有效
            if self.current_page >= self.total_pages:
                self.current_page = max(0, self.total_pages - 1)

    def get_current_page_info(self) -> dict[str, Any]:
        """
        獲取當前頁面資訊。

        Returns:
            包含當前頁面資訊的字典
        """
        return {
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "page_size": self.page_size,
            "total_items": len(self.items),
            "current_items": len(self.get_page_items(self.current_page)),
        }


class ProposalPaginator(EmbedPaginator):
    """
    專門用於提案列表的分頁器。

    繼承自 EmbedPaginator，提供提案特定的功能。
    """

    def __init__(
        self,
        *,
        proposals: Sequence[Any],
        author_id: int | None = None,
        timeout: float = 600.0,
        show_status: bool = True,
        show_deadline: bool = True,
    ) -> None:
        """
        初始化提案分頁器。

        Args:
            proposals: 提案序列
            author_id: 限制使用者ID
            timeout: 超時時間
            show_status: 是否顯示提案狀態
            show_deadline: 是否顯示截止時間
        """
        self.show_status = show_status
        self.show_deadline = show_deadline

        super().__init__(
            items=proposals,
            page_size=10,  # 保持與現有實作一致
            embed_factory=self._create_proposal_embed,
            author_id=author_id,
            timeout=timeout,
        )

    def _create_proposal_embed(
        self, proposals: list[Any], page_num: int, total_pages: int
    ) -> discord.Embed:
        """
        創建提案列表的嵌入訊息。

        Args:
            proposals: 當前頁面的提案列表
            page_num: 當前頁碼
            total_pages: 總頁數

        Returns:
            配置好的嵌入訊息
        """
        embed = discord.Embed(
            title="📋 提案列表",
            color=0x3498DB,
            description=f"第 {page_num} 頁，共 {total_pages} 頁",
        )

        if not proposals:
            embed.add_field(
                name="📭 無提案",
                value="目前沒有符合條件的提案。",
                inline=False,
            )
            return embed

        for i, proposal in enumerate(proposals, 1):
            # 格式化提案標題和描述
            title = self._format_proposal_title(proposal)
            description = self._format_proposal_description(proposal)

            # 添加到嵌入訊息
            embed.add_field(
                name=f"{i}. {title}",
                value=description,
                inline=False,
            )

        return embed

    def _format_proposal_title(self, proposal: Any) -> str:
        """
        格式化提案標題。

        Args:
            proposal: 提案對象

        Returns:
            格式化後的標題
        """
        short_id = str(proposal.proposal_id)[:8]

        # 根據提案類型顯示不同的受款人資訊
        if hasattr(proposal, "target_department_id") and proposal.target_department_id:
            from src.bot.services.department_registry import get_registry

            registry = get_registry()
            dept = registry.get_by_id(proposal.target_department_id)
            target_str = dept.name if dept else proposal.target_department_id
        else:
            target_str = f"<@{proposal.target_id}>"

        return f"#{short_id} → {target_str} {proposal.amount}"

    def _format_proposal_description(self, proposal: Any) -> str:
        """
        格式化提案描述。

        Args:
            proposal: 提案對象

        Returns:
            格式化後的描述
        """
        parts: list[str] = []

        # 狀態
        if self.show_status:
            parts.append(f"📊 狀態：{proposal.status}")

        # 截止時間
        if self.show_deadline and hasattr(proposal, "deadline_at"):
            deadline = proposal.deadline_at.strftime("%Y-%m-%d %H:%M UTC")
            parts.append(f"⏰ 截止：{deadline}")

        # 投票門檻
        if hasattr(proposal, "threshold_t"):
            parts.append(f"🎯 門檻 T：{proposal.threshold_t}")

        # 描述
        if proposal.description:
            desc = proposal.description.strip()[:50]
            if len(proposal.description) > 50:
                desc += "..."
            parts.append(f"📝 用途：{desc}")
        else:
            parts.append("📝 用途：無描述")

        return " | ".join(parts)
