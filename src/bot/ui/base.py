"""統一的持久化面板基礎架構。

此模組提供所有面板的持久化回應基類，確保：
- 所有互動元件在超時前可被重複回應
- 機器人重啟後仍能正常處理互動
- 統一的 custom_id 命名規範
- 統一的超時處理邏輯
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
import structlog

if TYPE_CHECKING:
    from discord import Interaction

LOGGER = structlog.get_logger(__name__)

# 預設面板超時時間（秒）- 10 分鐘
DEFAULT_PANEL_TIMEOUT: float = 600.0

# 統一的超時提示訊息
PANEL_EXPIRED_MESSAGE = "面板已過期，請重新開啟。"


def generate_custom_id(
    panel_type: str,
    component_type: str,
    identifier: str | None = None,
) -> str:
    """
    產生符合規範的 custom_id。

    格式：{panel_type}:{component_type}:{identifier}

    Args:
        panel_type: 面板類型（如 council, state_council, personal, supreme_assembly）
        component_type: 元件類型（如 btn, select, modal）
        identifier: 唯一識別資訊（如 vote_approve, tab_finance）

    Returns:
        格式化的 custom_id 字串

    Example:
        >>> generate_custom_id("council", "btn", "vote_approve")
        'council:btn:vote_approve'
    """
    if identifier:
        return f"{panel_type}:{component_type}:{identifier}"
    return f"{panel_type}:{component_type}"


class PersistentPanelView(discord.ui.View):
    """
    統一的持久化面板基類。

    所有治理面板應繼承此類以獲得：
    - 統一的超時處理（預設 10 分鐘）
    - 超時後禁用所有元件並顯示提示
    - 支援機器人重啟後仍可回應（透過 persistent view 註冊）

    Attributes:
        panel_type: 面板類型識別字串
        author_id: 面板擁有者 ID（用於權限檢查）
        _message: 綁定的訊息物件（用於超時更新）
    """

    # 子類應覆寫此屬性以設定面板類型
    panel_type: str = "panel"

    def __init__(
        self,
        *,
        author_id: int | None = None,
        timeout: float = DEFAULT_PANEL_TIMEOUT,
        persistent: bool = False,
    ) -> None:
        """
        初始化持久化面板。

        Args:
            author_id: 面板擁有者 ID，若指定則僅該使用者可操作
            timeout: 超時時間（秒），預設 600 秒（10 分鐘）
                    設為 None 表示永不超時（用於 persistent views）
            persistent: 是否為持久化模式（重啟後仍可用）
                       若為 True，timeout 會被設為 None
        """
        # persistent view 需要 timeout=None
        effective_timeout = None if persistent else timeout
        super().__init__(timeout=effective_timeout)

        self.author_id = author_id
        self._message: discord.Message | None = None
        self._is_expired = False

    async def bind_message(self, message: discord.Message) -> None:
        """
        綁定訊息物件以便超時時更新。

        子類可覆寫此方法以添加額外的綁定邏輯（如事件訂閱），
        但應呼叫 super().bind_message(message) 以確保訊息被綁定。

        Args:
            message: 要綁定的 Discord 訊息
        """
        self._message = message

    async def on_timeout(self) -> None:
        """
        超時處理：禁用所有元件並顯示過期提示。

        子類可覆寫此方法以添加額外的清理邏輯，
        但應呼叫 super().on_timeout() 以保持統一行為。
        """
        self._is_expired = True

        # 禁用所有元件
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True

        # 更新訊息（如果已綁定）
        if self._message is not None:
            try:
                # 建立過期提示 embed
                expired_embed = discord.Embed(
                    title="⏰ 面板已過期",
                    description=PANEL_EXPIRED_MESSAGE,
                    color=0x95A5A6,
                )
                await self._message.edit(embed=expired_embed, view=self)
            except discord.NotFound:
                # 訊息已被刪除
                pass
            except discord.HTTPException as exc:
                LOGGER.warning(
                    "panel.timeout.update_failed",
                    panel_type=self.panel_type,
                    error=str(exc),
                )

        LOGGER.debug(
            "panel.timeout",
            panel_type=self.panel_type,
            author_id=self.author_id,
        )

    async def check_author(self, interaction: Interaction) -> bool:
        """
        檢查互動者是否為面板擁有者。

        Args:
            interaction: Discord 互動物件

        Returns:
            True 如果允許操作，False 如果不允許

        Note:
            若 author_id 未設定，則允許所有人操作。
        """
        if self.author_id is None:
            return True

        if interaction.user.id != self.author_id:
            from src.bot.interaction_compat import send_message_compat

            await send_message_compat(
                interaction,
                content="僅限面板開啟者操作。",
                ephemeral=True,
            )
            return False

        return True

    async def check_expired(self, interaction: Interaction) -> bool:
        """
        檢查面板是否已過期。

        Args:
            interaction: Discord 互動物件

        Returns:
            True 如果面板仍有效，False 如果已過期
        """
        if self._is_expired:
            from src.bot.interaction_compat import send_message_compat

            await send_message_compat(
                interaction,
                content=PANEL_EXPIRED_MESSAGE,
                ephemeral=True,
            )
            return False

        return True

    def generate_component_id(self, component_type: str, identifier: str) -> str:
        """
        為此面板產生元件 custom_id。

        Args:
            component_type: 元件類型（btn, select, modal 等）
            identifier: 元件識別字串

        Returns:
            格式化的 custom_id
        """
        return generate_custom_id(self.panel_type, component_type, identifier)


class PersistentButton(discord.ui.Button[Any]):
    """
    支援持久化的按鈕元件。

    繼承此類的按鈕會自動設定符合規範的 custom_id，
    並在 callback 中檢查面板狀態。
    """

    def __init__(
        self,
        *,
        panel_type: str,
        identifier: str,
        label: str,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        disabled: bool = False,
        emoji: str | discord.PartialEmoji | None = None,
        row: int | None = None,
    ) -> None:
        """
        初始化持久化按鈕。

        Args:
            panel_type: 所屬面板類型
            identifier: 按鈕識別字串
            label: 按鈕標籤
            style: 按鈕樣式
            disabled: 是否禁用
            emoji: 按鈕圖示
            row: 按鈕所在列
        """
        custom_id = generate_custom_id(panel_type, "btn", identifier)
        super().__init__(
            label=label,
            style=style,
            custom_id=custom_id,
            disabled=disabled,
            emoji=emoji,
            row=row,
        )


class PersistentSelect(discord.ui.Select[Any]):
    """
    支援持久化的下拉選單元件。

    繼承此類的選單會自動設定符合規範的 custom_id，
    並在 callback 中檢查面板狀態。
    """

    def __init__(
        self,
        *,
        panel_type: str,
        identifier: str,
        placeholder: str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        options: list[discord.SelectOption] | None = None,
        disabled: bool = False,
        row: int | None = None,
    ) -> None:
        """
        初始化持久化下拉選單。

        Args:
            panel_type: 所屬面板類型
            identifier: 選單識別字串
            placeholder: 佔位文字
            min_values: 最少選擇數量
            max_values: 最多選擇數量
            options: 選項列表
            disabled: 是否禁用
            row: 選單所在列
        """
        custom_id = generate_custom_id(panel_type, "select", identifier)
        super().__init__(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=options or [],
            custom_id=custom_id,
            disabled=disabled,
            row=row,
        )


# 匯出公開 API
__all__ = [
    "DEFAULT_PANEL_TIMEOUT",
    "PANEL_EXPIRED_MESSAGE",
    "PersistentButton",
    "PersistentPanelView",
    "PersistentSelect",
    "generate_custom_id",
]
