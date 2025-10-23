from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
import structlog

from src.db import pool as db_pool

LOGGER = structlog.get_logger(__name__)
NotificationHandler = Callable[[str], Awaitable[None] | None]


class TelemetryListener:
    """Background listener for PostgreSQL NOTIFY events."""

    def __init__(
        self,
        *,
        channel: str = "economy_events",
        handler: NotificationHandler | None = None,
    ) -> None:
        self._channel = channel
        self._handler = handler or self._default_handler
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None

    async def start(self) -> None:
        """Begin listening for NOTIFY events."""
        if self._task is not None and not self._task.done():
            return

        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="telemetry-listener")
        LOGGER.info("telemetry.listener.started", channel=self._channel)

    async def stop(self) -> None:
        """Signal the listener to stop and wait for shutdown."""
        if self._task is None:
            return

        if self._stop_event is not None:
            self._stop_event.set()

        try:
            await self._task
        finally:
            self._task = None
            self._stop_event = None
            LOGGER.info("telemetry.listener.stopped", channel=self._channel)

    async def _run(self) -> None:
        try:
            pool = await db_pool.init_pool()
            async with pool.acquire() as connection:
                await connection.add_listener(self._channel, self._dispatch)

                try:
                    if self._stop_event is None:
                        self._stop_event = asyncio.Event()

                    await self._stop_event.wait()
                finally:
                    await connection.remove_listener(self._channel, self._dispatch)
        except Exception:
            LOGGER.exception("telemetry.listener.error")
            raise

    async def _dispatch(
        self,
        connection: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        del connection, pid, channel
        result = self._handler(payload)
        if asyncio.iscoroutine(result):
            await result

    async def _default_handler(self, payload: str) -> None:
        """Default observer: parse JSON payloads and emit structured logs."""
        try:
            parsed: Any = json.loads(payload)
        except json.JSONDecodeError:
            LOGGER.warning(
                "telemetry.listener.payload.unparseable",
                payload=payload,
            )
            return

        if not isinstance(parsed, dict):
            LOGGER.info(
                "telemetry.listener.payload.raw",
                payload=payload,
            )
            return

        event_type = parsed.get("event_type", "unknown")
        if event_type == "transaction_success":
            LOGGER.info(
                "telemetry.transfer.success",
                guild_id=parsed.get("guild_id"),
                initiator_id=parsed.get("initiator_id"),
                target_id=parsed.get("target_id"),
                amount=parsed.get("amount"),
                metadata=parsed.get("metadata", {}),
            )
        elif event_type == "transaction_denied":
            LOGGER.warning(
                "telemetry.transfer.denied",
                guild_id=parsed.get("guild_id"),
                initiator_id=parsed.get("initiator_id"),
                reason=parsed.get("reason"),
                metadata=parsed.get("metadata", {}),
            )
        elif event_type == "adjustment_success":
            LOGGER.info(
                "telemetry.adjustment.success",
                guild_id=parsed.get("guild_id"),
                admin_id=parsed.get("admin_id"),
                target_id=parsed.get("target_id"),
                amount=parsed.get("amount"),
                direction=parsed.get("direction"),
                reason=parsed.get("reason"),
                metadata=parsed.get("metadata", {}),
            )
        else:
            LOGGER.info("telemetry.listener.payload.received", payload=parsed)
