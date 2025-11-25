"""測試共用分頁元件。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import discord
import pytest

from src.bot.ui.paginator import EmbedPaginator, ProposalPaginator
from src.bot.ui.supreme_assembly_paginator import SupremeAssemblyProposalPaginator


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
    ) -> None:
        self.proposal_id = proposal_id
        self.target_id = target_id
        self.amount = amount
        self.status = status
        self.description = description
        self.deadline_at = deadline_at or datetime.now(timezone.utc)
        self.threshold_t = threshold_t


class MockSupremeAssemblyProposal:
    """模擬最高人民會議提案對象。"""

    def __init__(
        self,
        proposal_id: str,
        title: str | None = None,
        amount: int | None = None,
        status: str = "進行中",
        description: str | None = None,
        deadline_at: datetime | None = None,
        threshold_t: int = 3,
        agree_count: int = 0,
        against_count: int = 0,
        abstain_count: int = 0,
    ) -> None:
        self.proposal_id = proposal_id
        self.title = title
        self.amount = amount
        self.status = status
        self.description = description
        self.deadline_at = deadline_at or datetime.now(timezone.utc)
        self.threshold_t = threshold_t
        self.agree_count = agree_count
        self.against_count = against_count
        self.abstain_count = abstain_count


@pytest.fixture
def sample_proposals() -> list[MockProposal]:
    """提供範例提案列表。"""
    return [
        MockProposal(
            proposal_id="12345678-1234-5678-9abc-123456789000",
            target_id=123456789,
            amount=1000,
            status="進行中",
            description="測試提案 1",
        ),
        MockProposal(
            proposal_id="12345678-1234-5678-9abc-123456789001",
            target_id=987654321,
            amount=2000,
            status="進行中",
            description="測試提案 2",
        ),
        MockProposal(
            proposal_id="12345678-1234-5678-9abc-123456789002",
            target_id=555666777,
            amount=1500,
            status="已執行",
            description="測試提案 3",
        ),
    ]


@pytest.fixture
def sample_supreme_assembly_proposals() -> list[MockSupremeAssemblyProposal]:
    """提供範例最高人民會議提案列表。"""
    return [
        MockSupremeAssemblyProposal(
            proposal_id="87654321-4321-8765-cba9-876543210000",
            title="預算分配提案",
            amount=5000,
            status="進行中",
            description="分配下季度各部門預算",
            agree_count=5,
            against_count=2,
            abstain_count=1,
        ),
        MockSupremeAssemblyProposal(
            proposal_id="87654321-4321-8765-cba9-876543210001",
            title="政策改革提案",
            amount=0,
            status="進行中",
            description="修改投票門檻規則",
            agree_count=3,
            against_count=3,
            abstain_count=2,
        ),
        MockSupremeAssemblyProposal(
            proposal_id="87654321-4321-8765-cba9-876543210002",
            title="緊急援助提案",
            amount=3000,
            status="已通過",
            description="為受災地區提供緊急援助",
            agree_count=8,
            against_count=1,
            abstain_count=0,
        ),
    ]


class TestEmbedPaginator:
    """測試 EmbedPaginator 類別。"""

    def test_init_basic(self) -> None:
        """測試基本初始化。"""
        items = ["item1", "item2", "item3"]
        paginator = EmbedPaginator(
            items=items,
            page_size=2,
            embed_factory=lambda x, p, t: discord.Embed(title="Test"),
        )

        assert paginator.items == items
        assert paginator.page_size == 2
        assert paginator.total_pages == 2  # 3 items / 2 per page = 2 pages
        assert paginator.current_page == 0

    def test_init_empty_items(self) -> None:
        """測試空項目列表的初始化。"""
        paginator = EmbedPaginator(
            items=[],
            page_size=10,
            embed_factory=lambda x, p, t: discord.Embed(title="Test"),
        )

        assert paginator.items == []
        assert paginator.total_pages == 1  # 空列表仍然有 1 頁
        assert paginator.current_page == 0

    def test_get_page_items(self) -> None:
        """測試取得頁面項目。"""
        items = ["a", "b", "c", "d", "e"]
        paginator = EmbedPaginator(
            items=items,
            page_size=2,
            embed_factory=lambda x, p, t: discord.Embed(title="Test"),
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

    def test_create_embed(self) -> None:
        """測試創建嵌入訊息。"""
        items = ["item1", "item2", "item3"]

        def embed_factory(items, page, total):
            return discord.Embed(title=f"Page {page}", description=f"Items: {', '.join(items)}")

        paginator = EmbedPaginator(
            items=items,
            page_size=2,
            embed_factory=embed_factory,
        )

        embed = paginator.create_embed(0)
        assert embed.title == "Page 1"
        assert "Items: item1, item2" in embed.description

        # 檢查頁腳是否包含頁碼資訊
        assert "第 1 頁，共 2 頁" in embed.footer.text

    @pytest.mark.asyncio
    async def test_create_view_single_page(self) -> None:
        """測試創建單頁檢視。"""
        paginator = EmbedPaginator(
            items=["single"],
            page_size=10,
            embed_factory=lambda x, p, t: discord.Embed(title="Test"),
        )

        view = paginator.create_view()
        assert len(view.children) == 0  # 單頁不應該有按鈕

    @pytest.mark.asyncio
    async def test_create_view_multiple_pages(self) -> None:
        """測試創建多頁檢視。"""
        items = ["a", "b", "c", "d", "e", "f"]
        paginator = EmbedPaginator(
            items=items,
            page_size=2,
            embed_factory=lambda x, p, t: discord.Embed(title="Test"),
        )

        view = paginator.create_view()
        assert len(view.children) >= 3  # 至少應該有 prev、indicator、next 按鈕

        # 檢查按鈕狀態
        prev_btn = None
        next_btn = None
        for child in view.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "paginator_prev":
                    prev_btn = child
                elif child.custom_id == "paginator_next":
                    next_btn = child

        assert prev_btn is not None
        assert next_btn is not None
        assert prev_btn.disabled  # 第一頁時上一頁按鈕應該禁用
        assert not next_btn.disabled  # 第一頁時下一頁按鈕應該啟用

    def test_refresh_items(self) -> None:
        """測試刷新項目列表。"""
        original_items = ["a", "b", "c"]
        paginator = EmbedPaginator(
            items=original_items,
            page_size=2,
            embed_factory=lambda x, p, t: discord.Embed(title="Test"),
        )

        # 初始狀態
        assert paginator.total_pages == 2
        assert paginator.current_page == 0

        # 刷新為更少的項目
        new_items = ["x"]

        async def test_refresh():
            await paginator.refresh_items(new_items)
            assert paginator.items == new_items
            assert paginator.total_pages == 1
            assert paginator.current_page == 0  # 當前頁面超出範圍時應該調整

        asyncio.run(test_refresh())

    def test_get_current_page_info(self) -> None:
        """測試獲取當前頁面資訊。"""
        items = ["a", "b", "c", "d", "e"]
        paginator = EmbedPaginator(
            items=items,
            page_size=2,
            embed_factory=lambda x, p, t: discord.Embed(title="Test"),
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
    async def test_on_jump_page_handles_dict_values(self) -> None:
        """確保 component interaction 的字典資料可正確讀取。"""
        paginator = EmbedPaginator(
            items=["a", "b", "c"],
            page_size=1,
            embed_factory=lambda x, p, t: discord.Embed(title="Test"),
        )

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 555
        mock_interaction.data = {"values": ["2"]}

        update_mock = AsyncMock()
        paginator._update_page = update_mock  # type: ignore[assignment]

        await paginator._on_jump_page(mock_interaction)

        assert paginator.current_page == 1  # 選擇第 2 頁（0-based = 1）
        update_mock.assert_awaited_once_with(mock_interaction)


class TestProposalPaginator:
    """測試 ProposalPaginator 類別。"""

    def test_init_basic(self, sample_proposals: list[MockProposal]) -> None:
        """測試基本初始化。"""
        paginator = ProposalPaginator(proposals=sample_proposals)

        assert paginator.items == sample_proposals
        assert paginator.page_size == 10  # 預設頁面大小
        assert paginator.show_status
        assert paginator.show_deadline

    def test_format_proposal_title(self, sample_proposals: list[MockProposal]) -> None:
        """測試格式化提案標題。"""
        paginator = ProposalPaginator(proposals=sample_proposals)
        proposal = sample_proposals[0]

        title = paginator._format_proposal_title(proposal)
        assert "12345678" in title  # 短 ID
        assert "<@123456789>" in title  # 受款人
        assert "1000" in title  # 金額

    @pytest.mark.asyncio
    async def test_format_proposal_description(self, sample_proposals: list[MockProposal]) -> None:
        """測試格式化提案描述。"""
        paginator = ProposalPaginator(proposals=sample_proposals)
        proposal = sample_proposals[0]

        description = paginator._format_proposal_description(proposal)
        assert "📊 狀態：進行中" in description
        assert "🎯 門檻 T：3" in description
        assert "📝 用途：測試提案 1" in description

    @pytest.mark.asyncio
    async def test_format_proposal_description_long(self) -> None:
        """測試格式化長描述的提案。"""
        long_desc = "這是一個很長的描述，" * 10  # 超過 50 字符
        proposal = MockProposal(
            proposal_id="test-id",
            target_id=123,
            amount=100,
            description=long_desc,
        )
        paginator = ProposalPaginator(proposals=[proposal])

        description = paginator._format_proposal_description(proposal)
        assert "..." in description  # 應該被截斷
        assert len(description) < len(long_desc) + 50  # 總長度應該合理

    @pytest.mark.asyncio
    async def test_create_proposal_embed_empty(self) -> None:
        """測試創建空提案列表的嵌入訊息。"""
        paginator = ProposalPaginator(proposals=[])

        embed = paginator._create_proposal_embed([], 1, 1)
        assert embed.title == "📋 提案列表"
        assert "第 1 頁，共 1 頁" in embed.description
        # 檢查是否有空提案的字段
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "📭 無提案"

    @pytest.mark.asyncio
    async def test_create_proposal_embed_with_items(
        self, sample_proposals: list[MockProposal]
    ) -> None:
        """測試創建包含提案的嵌入訊息。"""
        paginator = ProposalPaginator(proposals=sample_proposals)

        embed = paginator._create_proposal_embed(sample_proposals, 1, 1)
        assert embed.title == "📋 提案列表"
        assert len(embed.fields) == len(sample_proposals)

        # 檢查每個提案都有一個字段
        for i, proposal in enumerate(sample_proposals):
            field = embed.fields[i]
            assert "12345678" in field.name  # 短 ID
            assert proposal.description in field.value

    @pytest.mark.asyncio
    async def test_pagination_navigation(self, sample_proposals: list[MockProposal]) -> None:
        """測試分頁導航功能。"""
        # 創建足夠多的提案來測試分頁
        many_proposals = []
        for i in range(25):
            many_proposals.append(
                MockProposal(
                    proposal_id=f"proposal-{i}",
                    target_id=123 + i,
                    amount=100 + i,
                    description=f"提案 {i}",
                )
            )

        paginator = ProposalPaginator(proposals=many_proposals)

        # 檢查初始狀態
        assert paginator.current_page == 0
        assert paginator.total_pages == 3  # 25 items / 10 per page = 3 pages

        # 模擬下一頁操作
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123
        mock_interaction.response.edit_message = AsyncMock()

        # 設置不檢查 author_id 以簡化測試
        paginator.author_id = None

        await paginator._on_next_page(mock_interaction)
        assert paginator.current_page == 1
        mock_interaction.response.edit_message.assert_called_once()

        # 重置 mock
        mock_interaction.reset_mock()

        # 模擬上一頁操作
        await paginator._on_prev_page(mock_interaction)
        assert paginator.current_page == 0
        mock_interaction.response.edit_message.assert_called_once()

    def test_update_callback(self) -> None:
        """測試更新回調功能。"""
        paginator = EmbedPaginator(
            items=["a", "b", "c"],
            page_size=2,
            embed_factory=lambda x, p, t: discord.Embed(title="Test"),
        )

        callback_called = False

        async def test_callback() -> None:
            nonlocal callback_called
            callback_called = True

        paginator.set_update_callback(test_callback)
        assert paginator._update_callback is not None

        # 注意：這裡只能測試回調的設置，實際調用需要在異步環境中
        # 實際的回調調用在 _update_page 方法中測試


class TestSupremeAssemblyProposalPaginator:
    """測試 SupremeAssemblyProposalPaginator 類別。"""

    def test_init_basic(
        self, sample_supreme_assembly_proposals: list[MockSupremeAssemblyProposal]
    ) -> None:
        """測試基本初始化。"""
        paginator = SupremeAssemblyProposalPaginator(proposals=sample_supreme_assembly_proposals)

        assert paginator.items == sample_supreme_assembly_proposals
        assert paginator.page_size == 10  # 預設頁面大小

    def test_format_supreme_assembly_proposal_title(
        self, sample_supreme_assembly_proposals: list[MockSupremeAssemblyProposal]
    ) -> None:
        """測試格式化最高人民會議提案標題。"""
        paginator = SupremeAssemblyProposalPaginator(proposals=sample_supreme_assembly_proposals)
        proposal = sample_supreme_assembly_proposals[0]

        title = paginator._format_supreme_assembly_proposal_title(proposal)
        assert "87654321" in title  # 短 ID
        assert "預算分配提案" in title  # 提案標題
        assert "5,000" in title  # 金額（有千位分隔符）

    def test_format_supreme_assembly_proposal_title_long(self) -> None:
        """測試格式化長標題的提案。"""
        long_title = "這是一個非常長的提案標題，用來測試截斷功能是否正常運作" * 2
        proposal = MockSupremeAssemblyProposal(
            proposal_id="test-id",
            title=long_title,
            amount=1000,
        )
        paginator = SupremeAssemblyProposalPaginator(proposals=[proposal])

        title = paginator._format_supreme_assembly_proposal_title(proposal)
        assert "..." in title  # 應該被截斷
        assert len(title) < len(long_title) + 20  # 總長度應該合理

    @pytest.mark.asyncio
    async def test_format_supreme_assembly_proposal_description(
        self, sample_supreme_assembly_proposals: list[MockSupremeAssemblyProposal]
    ) -> None:
        """測試格式化最高人民會議提案描述。"""
        paginator = SupremeAssemblyProposalPaginator(proposals=sample_supreme_assembly_proposals)
        proposal = sample_supreme_assembly_proposals[0]

        description = paginator._format_supreme_assembly_proposal_description(proposal)
        assert "🔄 狀態：進行中" in description
        assert "⏰ 截止" in description
        assert "🎯 T=3" in description  # threshold_t 預設值是 3
        assert "🗳️ 投票：8 票" in description  # 5 + 2 + 1 = 8
        assert "📝 分配下季度各部門預算" in description

    @pytest.mark.asyncio
    async def test_format_supreme_assembly_proposal_description_no_amount(self) -> None:
        """測試格式化沒有金額的提案描述。"""
        proposal = MockSupremeAssemblyProposal(
            proposal_id="test-id",
            title="政策改革提案",
            amount=None,  # 沒有金額
            description="修改投票門檻規則",
        )
        paginator = SupremeAssemblyProposalPaginator(proposals=[proposal])

        title = paginator._format_supreme_assembly_proposal_title(proposal)
        description = paginator._format_supreme_assembly_proposal_description(proposal)

        assert "💰" not in title  # 不應該包含金額
        assert "📝 修改投票門檻規則" in description

    @pytest.mark.asyncio
    async def test_create_supreme_assembly_proposal_embed_empty(self) -> None:
        """測試創建空提案列表的嵌入訊息。"""
        paginator = SupremeAssemblyProposalPaginator(proposals=[])

        embed = paginator._create_supreme_assembly_proposal_embed([], 1, 1)
        assert embed.title == "🏛️ 最高人民會議提案列表"
        assert "第 1 頁，共 1 頁" in embed.description
        # 檢查是否有空提案的字段
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "📭 無進行中提案"

    @pytest.mark.asyncio
    async def test_create_supreme_assembly_proposal_embed_with_items(
        self, sample_supreme_assembly_proposals: list[MockSupremeAssemblyProposal]
    ) -> None:
        """測試創建包含提案的嵌入訊息。"""
        paginator = SupremeAssemblyProposalPaginator(proposals=sample_supreme_assembly_proposals)

        embed = paginator._create_supreme_assembly_proposal_embed(
            sample_supreme_assembly_proposals, 1, 1
        )
        assert embed.title == "🏛️ 最高人民會議提案列表"
        assert embed.color.value == 0xE74C3C  # 紅色主題
        assert len(embed.fields) == len(sample_supreme_assembly_proposals)

        # 檢查每個提案都有一個字段
        for i, proposal in enumerate(sample_supreme_assembly_proposals):
            field = embed.fields[i]
            assert "87654321" in field.name  # 短 ID
            assert proposal.title in field.name
            assert proposal.description in field.value

    @pytest.mark.asyncio
    async def test_supreme_assembly_pagination_navigation(
        self, sample_supreme_assembly_proposals: list[MockSupremeAssemblyProposal]
    ) -> None:
        """測試最高人民會議分頁導航功能。"""
        # 創建足夠多的提案來測試分頁
        many_proposals = []
        for i in range(25):
            many_proposals.append(
                MockSupremeAssemblyProposal(
                    proposal_id=f"supreme-proposal-{i}",
                    title=f"最高人民會議提案 {i}",
                    amount=100 + i,
                    description=f"最高人民會議提案描述 {i}",
                )
            )

        paginator = SupremeAssemblyProposalPaginator(proposals=many_proposals)

        # 檢查初始狀態
        assert paginator.current_page == 0
        assert paginator.total_pages == 3  # 25 items / 10 per page = 3 pages

        # 模擬下一頁操作
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 123
        mock_interaction.response.edit_message = AsyncMock()

        # 設置不檢查 author_id 以簡化測試
        paginator.author_id = None

        await paginator._on_next_page(mock_interaction)
        assert paginator.current_page == 1
        mock_interaction.response.edit_message.assert_called_once()

        # 重置 mock
        mock_interaction.reset_mock()

        # 模擬上一頁操作
        await paginator._on_prev_page(mock_interaction)
        assert paginator.current_page == 0
        mock_interaction.response.edit_message.assert_called_once()

        # 測試第一頁和最後一頁按鈕
        mock_interaction.reset_mock()

        # 跳到最後一頁
        await paginator._on_last_page(mock_interaction)
        assert paginator.current_page == 2  # 最後一頁

        mock_interaction.reset_mock()

        # 跳回第一頁
        await paginator._on_first_page(mock_interaction)
        assert paginator.current_page == 0  # 第一頁

    def test_embed_color_consistency(
        self, sample_supreme_assembly_proposals: list[MockSupremeAssemblyProposal]
    ) -> None:
        """測試嵌入訊息顏色的一致性。"""
        paginator = SupremeAssemblyProposalPaginator(proposals=sample_supreme_assembly_proposals)

        embed = paginator._create_supreme_assembly_proposal_embed(
            sample_supreme_assembly_proposals, 1, 1
        )
        assert embed.color.value == 0xE74C3C  # 與 SupremeAssemblyPanelView 一致的紅色

    @pytest.mark.asyncio
    async def test_jump_page_functionality(
        self, sample_supreme_assembly_proposals: list[MockSupremeAssemblyProposal]
    ) -> None:
        """測試頁面跳轉功能。"""
        # 創建足夠多的提案以啟用跳轉選單
        many_proposals = []
        for i in range(15):  # 2 頁
            many_proposals.append(
                MockSupremeAssemblyProposal(
                    proposal_id=f"jump-proposal-{i}",
                    title=f"跳轉測試提案 {i}",
                    amount=100 + i,
                )
            )

        paginator = SupremeAssemblyProposalPaginator(proposals=many_proposals)

        # 創建檢視以測試跳轉選單
        view = paginator.create_view()

        # 應該有跳轉選單（因為 > 5 頁時才會顯示，但這裡只有 2 頁，所以不會有）
        # 測試基本按鈕存在
        has_first = any(
            child.custom_id == "supreme_paginator_first"
            for child in view.children
            if hasattr(child, "custom_id")
        )
        has_last = any(
            child.custom_id == "supreme_paginator_last"
            for child in view.children
            if hasattr(child, "custom_id")
        )

        assert has_first
        assert has_last


if __name__ == "__main__":
    pytest.main([__file__])
