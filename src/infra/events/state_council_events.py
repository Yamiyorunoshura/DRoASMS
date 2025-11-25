from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal

import structlog

LOGGER = structlog.get_logger(__name__)

# 事件種類：部門餘額變動、部門配置變更
StateCouncilEventKind = Literal["department_balance_changed", "department_config_updated"]


@dataclass(frozen=True, slots=True)
class StateCouncilEvent:
    guild_id: int
    kind: StateCouncilEventKind
    # 受影響之部門名稱清單（例如：["財政部", "中央銀行"]），僅供記錄/除錯
    departments: tuple[str, ...] = ()
    # 來源事件型別（例如：transaction_success / adjustment_success）
    cause: str | None = None


Subscriber = Callable[[StateCouncilEvent], Awaitable[None]]
UnsubscribeCallback = Callable[[], Awaitable[None]]

_subscribers: dict[int, set[Subscriber]] = {}
_lock = asyncio.Lock()


async def subscribe(guild_id: int, callback: Subscriber) -> UnsubscribeCallback:
    """訂閱指定 guild 的國務院事件，回傳取消訂閱協程。"""
    async with _lock:
        listeners = _subscribers.setdefault(guild_id, set())
        listeners.add(callback)
        listener_count = len(listeners)
    LOGGER.debug("state_council.events.subscribe", guild_id=guild_id, listeners=listener_count)

    async def _unsubscribe() -> None:
        remaining = 0
        async with _lock:
            listeners = _subscribers.get(guild_id)
            if not listeners:
                return
            listeners.discard(callback)
            remaining = len(listeners)
            if not listeners:
                _subscribers.pop(guild_id, None)
        LOGGER.debug("state_council.events.unsubscribe", guild_id=guild_id, listeners=remaining)

    return _unsubscribe


async def publish(event: StateCouncilEvent) -> None:
    """對 guild 全體訂閱者發布事件。"""
    async with _lock:
        listeners = list(_subscribers.get(event.guild_id, ()))
    if not listeners:
        return

    LOGGER.debug(
        "state_council.events.publish",
        guild_id=event.guild_id,
        kind=event.kind,
        departments=list(event.departments),
        cause=event.cause,
    )
    for callback in listeners:
        try:
            asyncio.create_task(_invoke(callback, event))
        except RuntimeError:
            await _invoke(callback, event)


async def _invoke(callback: Subscriber, event: StateCouncilEvent) -> None:
    try:
        await callback(event)
    except Exception as exc:  # pragma: no cover - 防禦性日誌
        LOGGER.warning(
            "state_council.events.callback_error",
            error=str(exc),
            guild_id=event.guild_id,
            kind=event.kind,
        )


__all__ = [
    "StateCouncilEvent",
    "StateCouncilEventKind",
    "subscribe",
    "publish",
]
