from __future__ import annotations

from typing import Any, cast

import pytest
from faker import Faker

from src.bot.commands.state_council import (
    InterdepartmentTransferPanelView,
)


class _StubService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def transfer_between_departments(
        self,
        *,
        guild_id: int,
        user_id: int,
        user_roles: list[int],
        from_department: str,
        to_department: str,
        amount: int,
        reason: str,
    ) -> dict[str, Any]:
        payload = {
            "guild_id": guild_id,
            "user_id": user_id,
            "user_roles": user_roles,
            "from_department": from_department,
            "to_department": to_department,
            "amount": amount,
            "reason": reason,
        }
        self.calls.append(payload)
        return payload


class _User:
    def __init__(self, uid: int) -> None:
        self.id = uid


class _StubInteraction:
    def __init__(self, uid: int) -> None:
        self.user = _User(uid)

    async def response_send_message(self, content: str, ephemeral: bool) -> None:
        # test stub: do nothing
        return None

    async def response_edit_message(self, **kwargs: Any) -> None:
        # test stub: do nothing
        return None


@pytest.mark.asyncio
async def test_target_options_exclude_source() -> None:
    service = _StubService()
    view = InterdepartmentTransferPanelView(
        service=service,
        guild_id=1,
        author_id=10,
        user_roles=[],
        source_department="內政部",
        departments=["內政部", "財政部", "國土安全部", "中央銀行"],
    )

    # 第一個元件應為目標部門下拉（當來源已給定）
    selects = [c for c in view.children if c.__class__.__name__.endswith("Select")]
    assert selects, "應存在目標部門下拉"
    to_select = selects[0]
    labels = [opt.label for opt in getattr(to_select, "options", [])]
    assert "內政部" not in labels, "目標部門選項不應包含來源部門"


@pytest.mark.asyncio
async def test_can_submit_validation(faker: Faker) -> None:
    service = _StubService()
    guild_id = faker.random_int(min=1, max=1000000)
    author_id = faker.random_int(min=1, max=1000000)
    view = InterdepartmentTransferPanelView(
        service=service,
        guild_id=guild_id,
        author_id=author_id,
        user_roles=[],
        source_department="財政部",
        departments=["內政部", "財政部", "國土安全部", "中央銀行"],
    )
    view.to_department = "內政部"
    view.amount = faker.random_int(min=1, max=10000)
    view.reason = faker.text(max_nb_chars=100)

    # 私有方法：直接檢查提交條件
    assert view._can_submit() is True


@pytest.mark.asyncio
async def test_submit_triggers_service_call(faker: Faker) -> None:
    service = _StubService()
    author_id = faker.random_int(min=1, max=1000000)
    guild_id = faker.random_int(min=1, max=1000000)
    user_roles = [faker.random_int(min=1, max=1000000) for _ in range(2)]
    amount = faker.random_int(min=1, max=10000)
    reason = faker.text(max_nb_chars=100)

    view = InterdepartmentTransferPanelView(
        service=service,
        guild_id=guild_id,
        author_id=author_id,
        user_roles=user_roles,
        source_department="內政部",
        departments=["內政部", "財政部", "國土安全部", "中央銀行"],
    )
    # 構造完成可提交狀態
    view.to_department = "財政部"
    view.amount = amount
    view.reason = reason
    view.refresh_controls()

    # 取得送出按鈕並執行 callback
    buttons = [c for c in view.children if c.__class__.__name__ == "Button"]
    assert buttons, "應存在按鈕元件"
    submit_btn = None
    for b in buttons:
        if getattr(b, "label", "") == "送出轉帳":
            submit_btn = b
            break
    assert submit_btn is not None, "找不到送出按鈕"

    inter = _StubInteraction(uid=author_id)
    await submit_btn.callback(cast(Any, inter))

    assert len(service.calls) == 1
    call = service.calls[0]
    assert call["guild_id"] == guild_id
    assert call["user_id"] == author_id
    assert call["from_department"] == "內政部"
    assert call["to_department"] == "財政部"
    assert call["amount"] == amount
    assert call["reason"] == reason
