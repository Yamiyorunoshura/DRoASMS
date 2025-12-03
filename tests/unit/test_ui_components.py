"""測試 UI 組件 (base.py, paginator.py, council_paginator.py) 的單元測試。

此測試套件針對 Discord UI 組件提供全面覆蓋，包括：
- base.py: 持久化面板基礎架構
- paginator.py: 共用分頁元件
- council_paginator.py: 理事會專用分頁元件

測試策略：
- 使用 mock 來測試 Discord UI 邏輯，避免依賴 Discord 框架
- 專注於業務邏輯而非 Discord 框架細節
- 達到 50%+ 覆蓋率目標
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import discord
import pytest

from src.bot.ui.base import (
    generate_custom_id,
)
from src.bot.ui.council_paginator import CouncilProposalPaginator
from src.bot.ui.paginator import EmbedPaginator, ProposalPaginator

# ============================================================================
# 測試 base.py - 持久化面板基礎架構
# ============================================================================


@pytest.mark.unit
class TestGenerateCustomId:
    """測試 custom_id 產生器函數。"""

    def test_generate_custom_id_with_identifier(self) -> None:
        """測試帶識別符的 custom_id 產生。"""
        result = generate_custom_id("council", "btn", "vote_approve")
        assert result == "council:btn:vote_approve"

    def test_generate_custom_id_without_identifier(self) -> None:
        """測試不帶識別符的 custom_id 產生。"""
        result = generate_custom_id("council", "select")
        assert result == "council:select"

    def test_generate_custom_id_different_panel_types(self) -> None:
        """測試不同面板類型的 custom_id 產生。"""
        panel_types = ["council", "state_council", "personal", "supreme_assembly"]
        for panel_type in panel_types:
            result = generate_custom_id(panel_type, "btn", "test")
            assert result.startswith(f"{panel_type}:")


# ============================================================================
# 測試 paginator.py - 共用分頁元件
# ============================================================================


@pytest.mark.unit
class TestEmbedPaginatorBasic:
    """測試 EmbedPaginator 基本功能。"""

    def test_init_default_parameters(self) -> None:
        """測試預設參數初始化。"""
        items = ["item1", "item2", "item3"]

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        paginator = EmbedPaginator(
            items=items,
            page_size=10,
            embed_factory=embed_factory,
        )

        assert paginator.items == items
        assert paginator.page_size == 10
        assert paginator.total_pages == 1
        assert paginator.current_page == 0
        assert paginator.author_id is None
        assert paginator.timeout == 600.0
        assert paginator.show_page_numbers is True
        assert paginator.show_indicator is True

    def test_init_with_author_id(self) -> None:
        """測試帶作者 ID 的初始化。"""

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        paginator = EmbedPaginator(
            items=["item"],
            page_size=10,
            embed_factory=embed_factory,
            author_id=12345,
        )

        assert paginator.author_id == 12345

    def test_init_with_custom_timeout(self) -> None:
        """測試自訂超時時間的初始化。"""

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        paginator = EmbedPaginator(
            items=["item"],
            page_size=10,
            embed_factory=embed_factory,
            timeout=300.0,
        )

        assert paginator.timeout == 300.0

    def test_init_empty_items(self) -> None:
        """測試空項目列表的初始化。"""

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        paginator = EmbedPaginator(
            items=[],
            page_size=10,
            embed_factory=embed_factory,
        )

        assert paginator.items == []
        assert paginator.total_pages == 1  # 空列表仍有 1 頁
        assert paginator.current_page == 0

    def test_total_pages_calculation(self) -> None:
        """測試總頁數計算。"""

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        test_cases = [
            ([], 10, 1),  # 空列表
            ([1], 10, 1),  # 少於一頁
            ([1] * 10, 10, 1),  # 剛好一頁
            ([1] * 11, 10, 2),  # 超過一頁
            ([1] * 25, 10, 3),  # 多頁
        ]

        for items, page_size, expected_pages in test_cases:
            paginator = EmbedPaginator(
                items=items,
                page_size=page_size,
                embed_factory=embed_factory,
            )
            assert (
                paginator.total_pages == expected_pages
            ), f"Items: {len(items)}, Expected: {expected_pages}, Got: {paginator.total_pages}"

    def test_get_page_items(self) -> None:
        """測試取得頁面項目。"""
        items = ["a", "b", "c", "d", "e"]

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        paginator = EmbedPaginator(
            items=items,
            page_size=2,
            embed_factory=embed_factory,
        )

        # 第一頁
        page_0 = paginator.get_page_items(0)
        assert page_0 == ["a", "b"]

        # 第二頁
        page_1 = paginator.get_page_items(1)
        assert page_1 == ["c", "d"]

        # 第三頁（不足一頁）
        page_2 = paginator.get_page_items(2)
        assert page_2 == ["e"]

        # 無效頁碼
        page_invalid = paginator.get_page_items(10)
        assert page_invalid == []

        # 負數頁碼
        page_negative = paginator.get_page_items(-1)
        assert page_negative == []

    def test_create_embed_adds_footer(self) -> None:
        """測試創建嵌入訊息時添加頁腳。"""

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        paginator = EmbedPaginator(
            items=["a", "b", "c", "d", "e"],
            page_size=2,
            embed_factory=embed_factory,
        )

        embed = paginator.create_embed(0)

        assert embed.title == "Page 1"
        assert "第 1 頁，共 3 頁" in embed.footer.text

    def test_create_embed_single_page_no_footer(self) -> None:
        """測試單頁不顯示頁腳。"""

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        paginator = EmbedPaginator(
            items=["a"],
            page_size=10,
            embed_factory=embed_factory,
        )

        embed = paginator.create_embed(0)

        # 單頁不應該有頁碼資訊
        assert embed.footer.text is None or "第 1 頁，共 1 頁" not in (embed.footer.text or "")

    def test_get_current_page_info(self) -> None:
        """測試獲取當前頁面資訊。"""
        items = ["a", "b", "c", "d", "e"]

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        paginator = EmbedPaginator(
            items=items,
            page_size=2,
            embed_factory=embed_factory,
        )

        info = paginator.get_current_page_info()
        expected = {
            "current_page": 0,
            "total_pages": 3,
            "page_size": 2,
            "total_items": 5,
            "current_items": 2,
        }
        assert info == expected

    @pytest.mark.asyncio
    async def test_refresh_items(self) -> None:
        """測試刷新項目列表。"""

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        paginator = EmbedPaginator(
            items=["a", "b", "c"],
            page_size=2,
            embed_factory=embed_factory,
        )

        # 初始狀態
        assert paginator.total_pages == 2
        assert paginator.current_page == 0

        # 刷新為更少的項目
        new_items = ["x"]
        await paginator.refresh_items(new_items)

        assert paginator.items == new_items
        assert paginator.total_pages == 1
        assert paginator.current_page == 0

    @pytest.mark.asyncio
    async def test_refresh_items_adjusts_current_page(self) -> None:
        """測試刷新項目後調整當前頁面。"""

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        paginator = EmbedPaginator(
            items=["a", "b", "c", "d", "e"],
            page_size=2,
            embed_factory=embed_factory,
        )

        # 跳到最後一頁
        paginator.current_page = 2

        # 刷新為更少的項目
        await paginator.refresh_items(["x", "y"])

        # 當前頁面應該調整到有效範圍內
        assert paginator.current_page == 0
        assert paginator.total_pages == 1

    def test_set_update_callback(self) -> None:
        """測試設置更新回調。"""

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}")

        paginator = EmbedPaginator(
            items=["a"],
            page_size=10,
            embed_factory=embed_factory,
        )

        async def test_callback() -> None:
            pass

        paginator.set_update_callback(test_callback)

        assert paginator._update_callback is not None


# ============================================================================
# 測試 ProposalPaginator - 提案分頁器
# ============================================================================


class MockProposal:
    """模擬提案對象。"""

    def __init__(
        self,
        proposal_id: str,
        target_id: int,
        amount: int,
        status: str = "進行中",
        description: str | None = None,
        deadline_at: datetime | None = None,
        threshold_t: int = 3,
        target_department_id: str | None = None,
    ) -> None:
        self.proposal_id = proposal_id
        self.target_id = target_id
        self.amount = amount
        self.status = status
        self.description = description
        self.deadline_at = deadline_at or datetime.now(timezone.utc)
        self.threshold_t = threshold_t
        self.target_department_id = target_department_id


@pytest.mark.unit
class TestProposalPaginatorBasic:
    """測試 ProposalPaginator 基本功能。"""

    def test_init_default_parameters(self) -> None:
        """測試預設參數初始化。"""
        proposals = [
            MockProposal(
                proposal_id="proposal-1",
                target_id=123,
                amount=1000,
            )
        ]
        paginator = ProposalPaginator(proposals=proposals)

        assert paginator.items == proposals
        assert paginator.page_size == 10
        assert paginator.show_status is True
        assert paginator.show_deadline is True

    def test_init_with_custom_flags(self) -> None:
        """測試自訂標記的初始化。"""
        proposals = [
            MockProposal(
                proposal_id="proposal-1",
                target_id=123,
                amount=1000,
            )
        ]
        paginator = ProposalPaginator(
            proposals=proposals,
            show_status=False,
            show_deadline=False,
        )

        assert paginator.show_status is False
        assert paginator.show_deadline is False

    def test_format_proposal_title_user_target(self) -> None:
        """測試格式化用戶目標的提案標題。"""
        proposal = MockProposal(
            proposal_id="12345678-abcd-efgh-ijkl-mnopqrstuvwx",
            target_id=123456789,
            amount=1000,
        )
        paginator = ProposalPaginator(proposals=[proposal])

        title = paginator._format_proposal_title(proposal)

        assert "12345678" in title  # 短 ID
        assert "<@123456789>" in title  # 受款人
        assert "1000" in title  # 金額

    def test_format_proposal_description_basic(self) -> None:
        """測試基本提案描述格式化。"""
        proposal = MockProposal(
            proposal_id="test-id",
            target_id=123,
            amount=1000,
            status="進行中",
            description="測試提案",
            threshold_t=3,
        )
        paginator = ProposalPaginator(proposals=[proposal])

        description = paginator._format_proposal_description(proposal)

        assert "📊 狀態：進行中" in description
        assert "🎯 門檻 T：3" in description
        assert "📝 用途：測試提案" in description

    def test_format_proposal_description_long_description(self) -> None:
        """測試長描述的截斷處理。"""
        long_desc = "這是一個很長的描述，" * 20
        proposal = MockProposal(
            proposal_id="test-id",
            target_id=123,
            amount=1000,
            description=long_desc,
        )
        paginator = ProposalPaginator(proposals=[proposal])

        description = paginator._format_proposal_description(proposal)

        assert "..." in description

    def test_format_proposal_description_no_description(self) -> None:
        """測試無描述的提案。"""
        proposal = MockProposal(
            proposal_id="test-id",
            target_id=123,
            amount=1000,
            description=None,
        )
        paginator = ProposalPaginator(proposals=[proposal])

        description = paginator._format_proposal_description(proposal)

        assert "📝 用途：無描述" in description

    def test_create_proposal_embed_empty(self) -> None:
        """測試創建空提案列表的嵌入訊息。"""
        paginator = ProposalPaginator(proposals=[])

        embed = paginator._create_proposal_embed([], 1, 1)

        assert embed.title == "📋 提案列表"
        assert "第 1 頁，共 1 頁" in embed.description
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "📭 無提案"

    def test_create_proposal_embed_with_items(self) -> None:
        """測試創建包含提案的嵌入訊息。"""
        proposals = [
            MockProposal(
                proposal_id=f"proposal-{i}",
                target_id=100 + i,
                amount=1000 * i,
            )
            for i in range(1, 4)
        ]
        paginator = ProposalPaginator(proposals=proposals)

        embed = paginator._create_proposal_embed(proposals, 1, 1)

        assert embed.title == "📋 提案列表"
        assert len(embed.fields) == len(proposals)


# ============================================================================
# 測試 CouncilProposalPaginator - 理事會專用分頁器
# ============================================================================


@pytest.mark.unit
class TestCouncilProposalPaginatorBasic:
    """測試 CouncilProposalPaginator 基本功能。"""

    def test_init_default_parameters(self) -> None:
        """測試預設參數初始化。"""
        proposals = [
            MockProposal(
                proposal_id="council-proposal-1",
                target_id=123,
                amount=1000,
            )
        ]
        paginator = CouncilProposalPaginator(proposals=proposals)

        assert paginator.items == proposals
        assert paginator.page_size == 10
        assert paginator.guild is None

    def test_init_with_guild(self) -> None:
        """測試帶 guild 參數的初始化。"""
        proposals = [
            MockProposal(
                proposal_id="council-proposal-1",
                target_id=123,
                amount=1000,
            )
        ]
        mock_guild = MagicMock(spec=discord.Guild)
        paginator = CouncilProposalPaginator(
            proposals=proposals,
            guild=mock_guild,
        )

        assert paginator.guild == mock_guild

    def test_format_council_proposal_title_user_target(self) -> None:
        """測試格式化用戶目標的理事會提案標題。"""
        proposal = MockProposal(
            proposal_id="council-proposal-001",
            target_id=123456789,
            amount=10000,
        )
        paginator = CouncilProposalPaginator(proposals=[proposal])

        title = paginator._format_council_proposal_title(proposal)

        assert "council-p" in title or "#council-" in title.lower()
        assert "<@123456789>" in title
        assert "10,000" in title  # 帶千位分隔符

    def test_format_council_proposal_description_status_emojis(self) -> None:
        """測試各種狀態的表情符號。"""
        statuses = {
            "進行中": "🔄",
            "已執行": "✅",
            "已否決": "❌",
            "已逾時": "⏰",
            "已撤案": "🚫",
            "未知": "📋",
        }

        for status, expected_emoji in statuses.items():
            proposal = MockProposal(
                proposal_id="test-id",
                target_id=123,
                amount=1000,
                status=status,
            )
            paginator = CouncilProposalPaginator(proposals=[proposal])
            description = paginator._format_council_proposal_description(proposal)

            assert f"{expected_emoji} 狀態：{status}" in description

    def test_create_council_proposal_embed_empty(self) -> None:
        """測試創建空提案列表的嵌入訊息。"""
        paginator = CouncilProposalPaginator(proposals=[])

        embed = paginator._create_council_proposal_embed([], 1, 1)

        assert embed.title == "🏛️ 理事會提案列表"
        assert embed.color.value == 0x95A5A6
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "📭 無進行中提案"

    def test_create_council_proposal_embed_with_items(self) -> None:
        """測試創建包含提案的嵌入訊息。"""
        proposals = [
            MockProposal(
                proposal_id=f"council-proposal-{i}",
                target_id=100 + i,
                amount=1000 * i,
            )
            for i in range(1, 4)
        ]
        paginator = CouncilProposalPaginator(proposals=proposals)

        embed = paginator._create_council_proposal_embed(proposals, 1, 1)

        assert embed.title == "🏛️ 理事會提案列表"
        assert len(embed.fields) == len(proposals)

    def test_create_embed_footer_first_page(self) -> None:
        """測試第一頁的頁腳提示。"""
        proposals = [
            MockProposal(
                proposal_id=f"footer-test-{i}",
                target_id=i,
                amount=1000 * i,
            )
            for i in range(1, 26)  # 25 個提案，3 頁
        ]
        paginator = CouncilProposalPaginator(proposals=proposals)

        embed = paginator.create_embed(0)

        assert "第 1 頁，共 3 頁" in embed.footer.text
        assert "使用下方按鈕導航" in embed.footer.text

    def test_create_embed_footer_middle_page(self) -> None:
        """測試中間頁的頁腳（無導航提示）。"""
        proposals = [
            MockProposal(
                proposal_id=f"footer-test-{i}",
                target_id=i,
                amount=1000 * i,
            )
            for i in range(1, 26)  # 25 個提案，3 頁
        ]
        paginator = CouncilProposalPaginator(proposals=proposals)

        embed = paginator.create_embed(1)

        assert "第 2 頁，共 3 頁" in embed.footer.text
        assert "使用下方按鈕導航" not in embed.footer.text


if __name__ == "__main__":
    pytest.main([__file__])
