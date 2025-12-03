"""測試理事會專用分頁元件 (council_paginator.py)。

涵蓋範圍：
- 分頁 embed 格式化
- 頁腳頁碼顯示
- 作者權限限制
- 空列表顯示
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.council_paginator import CouncilProposalPaginator


class MockCouncilProposal:
    """模擬理事會提案對象。"""

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


@pytest.fixture
def sample_council_proposals() -> list[MockCouncilProposal]:
    """提供範例理事會提案列表。"""
    return [
        MockCouncilProposal(
            proposal_id="council-proposal-001",
            target_id=123456789,
            amount=10000,
            status="進行中",
            description="測試理事會提案 1",
        ),
        MockCouncilProposal(
            proposal_id="council-proposal-002",
            target_id=987654321,
            amount=25000,
            status="已執行",
            description="測試理事會提案 2",
        ),
        MockCouncilProposal(
            proposal_id="council-proposal-003",
            target_id=555666777,
            amount=15000,
            status="已否決",
            description="測試理事會提案 3",
        ),
    ]


class TestCouncilProposalPaginator:
    """測試 CouncilProposalPaginator 類別。"""

    def test_init_basic(self, sample_council_proposals: list[MockCouncilProposal]) -> None:
        """測試基本初始化。"""
        paginator = CouncilProposalPaginator(proposals=sample_council_proposals)

        assert paginator.items == sample_council_proposals
        assert paginator.page_size == 10  # 預設頁面大小
        assert paginator.total_pages == 1
        assert paginator.current_page == 0
        assert paginator.guild is None

    def test_init_with_guild(self, sample_council_proposals: list[MockCouncilProposal]) -> None:
        """測試帶 guild 參數初始化。"""
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = 12345

        paginator = CouncilProposalPaginator(
            proposals=sample_council_proposals,
            guild=mock_guild,
        )

        assert paginator.guild == mock_guild

    def test_init_with_author_id(self, sample_council_proposals: list[MockCouncilProposal]) -> None:
        """測試帶作者 ID 限制的初始化。"""
        paginator = CouncilProposalPaginator(
            proposals=sample_council_proposals,
            author_id=67890,
        )

        assert paginator.author_id == 67890

    def test_init_empty_proposals(self) -> None:
        """測試空提案列表的初始化。"""
        paginator = CouncilProposalPaginator(proposals=[])

        assert paginator.items == []
        assert paginator.total_pages == 1  # 空列表仍有 1 頁
        assert paginator.current_page == 0


class TestCouncilPaginatorEmbedFormatting:
    """測試 Embed 格式化功能。"""

    def test_create_council_proposal_embed_with_items(
        self, sample_council_proposals: list[MockCouncilProposal]
    ) -> None:
        """測試創建包含提案的嵌入訊息。"""
        paginator = CouncilProposalPaginator(proposals=sample_council_proposals)

        embed = paginator._create_council_proposal_embed(sample_council_proposals, 1, 1)

        assert embed.title == "🏛️ 理事會提案列表"
        assert embed.color.value == 0x95A5A6
        assert "第 1 頁，共 1 頁" in embed.description
        assert len(embed.fields) == len(sample_council_proposals)

    def test_create_council_proposal_embed_empty(self) -> None:
        """測試創建空提案列表的嵌入訊息。"""
        paginator = CouncilProposalPaginator(proposals=[])

        embed = paginator._create_council_proposal_embed([], 1, 1)

        assert embed.title == "🏛️ 理事會提案列表"
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "📭 無進行中提案"
        assert "目前沒有進行中的理事會提案" in embed.fields[0].value

    def test_format_council_proposal_title_user_target(
        self, sample_council_proposals: list[MockCouncilProposal]
    ) -> None:
        """測試格式化用戶目標的提案標題。"""
        paginator = CouncilProposalPaginator(proposals=sample_council_proposals)
        proposal = sample_council_proposals[0]

        title = paginator._format_council_proposal_title(proposal)

        # 短 ID 只取前 8 個字元
        assert "#council-" in title or "council-p" in title.lower()
        assert "<@123456789>" in title  # 受款人
        assert "10,000" in title  # 金額（帶千位分隔符）

    def test_format_council_proposal_title_department_target(self) -> None:
        """測試格式化部門目標的提案標題。"""
        proposal = MockCouncilProposal(
            proposal_id="dept-proposal-001",
            target_id=0,
            amount=50000,
            target_department_id="finance_dept",
        )
        paginator = CouncilProposalPaginator(proposals=[proposal])

        # Mock department registry
        with patch("src.bot.ui.council_paginator.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_dept = MagicMock()
            mock_dept.name = "財政部"
            mock_registry.get_by_id.return_value = mock_dept
            mock_get_registry.return_value = mock_registry

            title = paginator._format_council_proposal_title(proposal)

            assert "財政部" in title
            assert "50,000" in title

    def test_format_council_proposal_title_unknown_department(self) -> None:
        """測試格式化未知部門的提案標題。"""
        proposal = MockCouncilProposal(
            proposal_id="unknown-dept-001",
            target_id=0,
            amount=30000,
            target_department_id="unknown_dept",
        )
        paginator = CouncilProposalPaginator(proposals=[proposal])

        # Mock department registry returning None
        with patch("src.bot.ui.council_paginator.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_by_id.return_value = None
            mock_get_registry.return_value = mock_registry

            title = paginator._format_council_proposal_title(proposal)

            assert "部門 unknown_dept" in title

    def test_format_council_proposal_description_all_statuses(self) -> None:
        """測試所有狀態的提案描述格式化。"""
        statuses = ["進行中", "已執行", "已否決", "已逾時", "已撤案", "未知狀態"]
        expected_emojis = ["🔄", "✅", "❌", "⏰", "🚫", "📋"]

        for status, expected_emoji in zip(statuses, expected_emojis, strict=False):
            proposal = MockCouncilProposal(
                proposal_id="status-test",
                target_id=123,
                amount=1000,
                status=status,
                description="測試描述",
            )
            paginator = CouncilProposalPaginator(proposals=[proposal])
            description = paginator._format_council_proposal_description(proposal)

            assert f"{expected_emoji} 狀態：{status}" in description

    def test_format_council_proposal_description_with_deadline(self) -> None:
        """測試帶截止時間的提案描述。"""
        deadline = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)
        proposal = MockCouncilProposal(
            proposal_id="deadline-test",
            target_id=123,
            amount=1000,
            description="測試截止時間",
            deadline_at=deadline,
        )
        paginator = CouncilProposalPaginator(proposals=[proposal])

        description = paginator._format_council_proposal_description(proposal)

        assert "⏰ 截止：12-31 23:59 UTC" in description

    def test_format_council_proposal_description_with_threshold(self) -> None:
        """測試帶投票門檻的提案描述。"""
        proposal = MockCouncilProposal(
            proposal_id="threshold-test",
            target_id=123,
            amount=1000,
            threshold_t=5,
        )
        paginator = CouncilProposalPaginator(proposals=[proposal])

        description = paginator._format_council_proposal_description(proposal)

        assert "🎯 門檻 T：5" in description

    def test_format_council_proposal_description_long_description(self) -> None:
        """測試長描述的截斷處理。"""
        long_desc = "這是一個非常長的描述，" * 10  # 超過 60 字符
        proposal = MockCouncilProposal(
            proposal_id="long-desc-test",
            target_id=123,
            amount=1000,
            description=long_desc,
        )
        paginator = CouncilProposalPaginator(proposals=[proposal])

        description = paginator._format_council_proposal_description(proposal)

        assert "..." in description
        # 確認描述被截斷
        assert len(description) < len(long_desc) + 100

    def test_format_council_proposal_description_no_description(self) -> None:
        """測試無描述的提案。"""
        proposal = MockCouncilProposal(
            proposal_id="no-desc-test",
            target_id=123,
            amount=1000,
            description=None,
        )
        paginator = CouncilProposalPaginator(proposals=[proposal])

        description = paginator._format_council_proposal_description(proposal)

        assert "📝 用途：無描述" in description


class TestCouncilPaginatorFooter:
    """測試頁腳頁碼顯示功能。"""

    def test_create_embed_footer_first_page(self) -> None:
        """測試第一頁的頁腳顯示。"""
        proposals = [
            MockCouncilProposal(
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
        """測試中間頁的頁腳顯示。"""
        proposals = [
            MockCouncilProposal(
                proposal_id=f"footer-test-{i}",
                target_id=i,
                amount=1000 * i,
            )
            for i in range(1, 26)  # 25 個提案，3 頁
        ]
        paginator = CouncilProposalPaginator(proposals=proposals)

        embed = paginator.create_embed(1)

        assert "第 2 頁，共 3 頁" in embed.footer.text
        # 中間頁不應該有導航提示
        assert "使用下方按鈕導航" not in embed.footer.text

    def test_create_embed_footer_single_page(self) -> None:
        """測試單頁不顯示頁腳。"""
        proposals = [
            MockCouncilProposal(
                proposal_id="single-page-test",
                target_id=123,
                amount=1000,
            )
        ]
        paginator = CouncilProposalPaginator(proposals=proposals)

        embed = paginator.create_embed(0)

        # 單頁不需要頁碼資訊
        if embed.footer.text:
            assert "第 1 頁，共 1 頁" not in embed.footer.text


class TestCouncilPaginatorView:
    """測試分頁檢視功能。"""

    @pytest.mark.asyncio
    async def test_create_view_single_page(self) -> None:
        """測試單頁不創建分頁按鈕。"""
        proposals = [
            MockCouncilProposal(
                proposal_id="single-view-test",
                target_id=123,
                amount=1000,
            )
        ]
        paginator = CouncilProposalPaginator(proposals=proposals)

        view = paginator.create_view()

        assert len(view.children) == 0

    @pytest.mark.asyncio
    async def test_create_view_multiple_pages(self) -> None:
        """測試多頁創建完整分頁按鈕。"""
        proposals = [
            MockCouncilProposal(
                proposal_id=f"multi-view-test-{i}",
                target_id=i,
                amount=1000 * i,
            )
            for i in range(1, 26)  # 25 個提案，3 頁
        ]
        paginator = CouncilProposalPaginator(proposals=proposals)

        view = paginator.create_view()

        # 應該有第一頁、上一頁、指示器、下一頁、最後一頁按鈕
        custom_ids = [child.custom_id for child in view.children if hasattr(child, "custom_id")]
        assert "council_paginator_first" in custom_ids
        assert "council_paginator_prev" in custom_ids
        assert "council_paginator_indicator" in custom_ids
        assert "council_paginator_next" in custom_ids
        assert "council_paginator_last" in custom_ids

    @pytest.mark.asyncio
    async def test_create_view_buttons_disabled_on_first_page(self) -> None:
        """測試第一頁時按鈕禁用狀態。"""
        proposals = [
            MockCouncilProposal(
                proposal_id=f"btn-disabled-test-{i}",
                target_id=i,
                amount=1000 * i,
            )
            for i in range(1, 26)
        ]
        paginator = CouncilProposalPaginator(proposals=proposals)

        view = paginator.create_view()

        for child in view.children:
            if hasattr(child, "custom_id"):
                if child.custom_id in ["council_paginator_first", "council_paginator_prev"]:
                    assert child.disabled, f"{child.custom_id} should be disabled on first page"
                elif child.custom_id in ["council_paginator_next", "council_paginator_last"]:
                    assert not child.disabled, f"{child.custom_id} should be enabled on first page"

    @pytest.mark.asyncio
    async def test_create_view_with_jump_menu(self) -> None:
        """測試超過 5 頁時顯示跳轉選單。"""
        proposals = [
            MockCouncilProposal(
                proposal_id=f"jump-menu-test-{i}",
                target_id=i,
                amount=1000 * i,
            )
            for i in range(1, 61)  # 60 個提案，6 頁
        ]
        paginator = CouncilProposalPaginator(proposals=proposals)

        view = paginator.create_view()

        has_select = any(
            child.custom_id == "council_paginator_jump"
            for child in view.children
            if hasattr(child, "custom_id")
        )
        assert has_select


class TestCouncilPaginatorAuthorRestriction:
    """測試作者權限限制功能。"""

    @pytest.mark.asyncio
    async def test_on_first_page_author_restriction(self) -> None:
        """測試第一頁按鈕的作者限制。"""
        proposals = [
            MockCouncilProposal(
                proposal_id=f"author-test-{i}",
                target_id=i,
                amount=1000 * i,
            )
            for i in range(1, 26)
        ]
        paginator = CouncilProposalPaginator(
            proposals=proposals,
            author_id=12345,
        )
        paginator.current_page = 2  # 設置為非第一頁

        mock_interaction = MagicMock()
        mock_interaction.user.id = 99999  # 非作者

        with patch("src.bot.ui.council_paginator._send_msg_compat") as mock_send:
            mock_send.return_value = None
            await paginator._on_first_page(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "僅限面板開啟者操作" in kwargs.get("content", args[1] if len(args) > 1 else "")

    @pytest.mark.asyncio
    async def test_on_last_page_author_restriction(self) -> None:
        """測試最後一頁按鈕的作者限制。"""
        proposals = [
            MockCouncilProposal(
                proposal_id=f"author-last-test-{i}",
                target_id=i,
                amount=1000 * i,
            )
            for i in range(1, 26)
        ]
        paginator = CouncilProposalPaginator(
            proposals=proposals,
            author_id=12345,
        )

        mock_interaction = MagicMock()
        mock_interaction.user.id = 99999  # 非作者

        with patch("src.bot.ui.council_paginator._send_msg_compat") as mock_send:
            mock_send.return_value = None
            await paginator._on_last_page(mock_interaction)

            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert "僅限面板開啟者操作" in kwargs.get("content", args[1] if len(args) > 1 else "")

    @pytest.mark.asyncio
    async def test_on_first_page_author_allowed(self) -> None:
        """測試作者可以操作第一頁按鈕。"""
        proposals = [
            MockCouncilProposal(
                proposal_id=f"author-allowed-test-{i}",
                target_id=i,
                amount=1000 * i,
            )
            for i in range(1, 26)
        ]
        paginator = CouncilProposalPaginator(
            proposals=proposals,
            author_id=12345,
        )
        paginator.current_page = 2

        mock_interaction = MagicMock()
        mock_interaction.user.id = 12345  # 作者

        with patch.object(paginator, "_update_page", new_callable=AsyncMock) as mock_update:
            await paginator._on_first_page(mock_interaction)

            assert paginator.current_page == 0
            mock_update.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_on_last_page_author_allowed(self) -> None:
        """測試作者可以操作最後一頁按鈕。"""
        proposals = [
            MockCouncilProposal(
                proposal_id=f"author-last-allowed-test-{i}",
                target_id=i,
                amount=1000 * i,
            )
            for i in range(1, 26)  # 3 頁
        ]
        paginator = CouncilProposalPaginator(
            proposals=proposals,
            author_id=12345,
        )

        mock_interaction = MagicMock()
        mock_interaction.user.id = 12345  # 作者

        with patch.object(paginator, "_update_page", new_callable=AsyncMock) as mock_update:
            await paginator._on_last_page(mock_interaction)

            assert paginator.current_page == 2  # 最後一頁
            mock_update.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_no_author_restriction_when_none(self) -> None:
        """測試無作者限制時任何人都可操作。"""
        proposals = [
            MockCouncilProposal(
                proposal_id=f"no-author-test-{i}",
                target_id=i,
                amount=1000 * i,
            )
            for i in range(1, 26)
        ]
        paginator = CouncilProposalPaginator(
            proposals=proposals,
            author_id=None,
        )
        paginator.current_page = 1

        mock_interaction = MagicMock()
        mock_interaction.user.id = 99999  # 任何用戶

        with patch.object(paginator, "_update_page", new_callable=AsyncMock) as mock_update:
            await paginator._on_first_page(mock_interaction)

            assert paginator.current_page == 0
            mock_update.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
