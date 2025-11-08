from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal
from uuid import UUID

import structlog

LOGGER = structlog.get_logger(__name__)

SupremeAssemblyEventKind = Literal[
    "proposal_created",
    "proposal_updated",
    "proposal_status_changed",
    "vote_cast",
]


@dataclass(frozen=True, slots=True)
class SupremeAssemblyEvent:
    guild_id: int
    proposal_id: UUID | None
    kind: SupremeAssemblyEventKind
    status: str | None = None


Subscriber = Callable[[SupremeAssemblyEvent], Awaitable[None]]
UnsubscribeCallback = Callable[[], Awaitable[None]]

_subscribers: dict[int, set[Subscriber]] = {}
_lock = asyncio.Lock()


async def subscribe(guild_id: int, callback: Subscriber) -> UnsubscribeCallback:
    """Register a subscriber for a guild and return an unsubscribe coroutine."""
    async with _lock:
        listeners = _subscribers.setdefault(guild_id, set())
        listeners.add(callback)
        listener_count = len(listeners)
    LOGGER.debug(
        "supreme_assembly.events.subscribe",
        guild_id=guild_id,
        listeners=listener_count,
    )

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
        LOGGER.debug(
            "supreme_assembly.events.unsubscribe",
            guild_id=guild_id,
            listeners=remaining,
        )

    return _unsubscribe


async def publish(event: SupremeAssemblyEvent) -> None:
    """Publish an event to all subscribers of the guild."""
    async with _lock:
        listeners = list(_subscribers.get(event.guild_id, ()))
    if not listeners:
        return

    LOGGER.debug(
        "supreme_assembly.events.publish",
        guild_id=event.guild_id,
        kind=event.kind,
        proposal_id=str(event.proposal_id) if event.proposal_id else None,
    )
    for callback in listeners:
        try:
            asyncio.create_task(_invoke(callback, event))
        except RuntimeError:
            await _invoke(callback, event)


async def _invoke(callback: Subscriber, event: SupremeAssemblyEvent) -> None:
    try:
        await callback(event)
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.warning(
            "supreme_assembly.events.callback_error",
            error=str(exc),
            guild_id=event.guild_id,
            kind=event.kind,
        )


__all__ = [
    "SupremeAssemblyEvent",
    "SupremeAssemblyEventKind",
    "publish",
    "subscribe",
]
