from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

import asyncpg
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.db import pool as db_pool
from src.db.gateway.economy_pending_transfers import (
    PendingTransferGateway,
)
from src.db.gateway.economy_transfers import EconomyTransferGateway

LOGGER = structlog.get_logger(__name__)


class TransferEventPoolCoordinator:
    """Coordinates pending transfer checks and execution via event-driven architecture."""

    def __init__(
        self,
        *,
        pool: asyncpg.Pool | None = None,
        pending_gateway: PendingTransferGateway | None = None,
        transfer_gateway: EconomyTransferGateway | None = None,
    ) -> None:
        self._pool = pool
        self._pending_gateway = pending_gateway or PendingTransferGateway()
        self._transfer_gateway = transfer_gateway or EconomyTransferGateway()
        # Track check states: transfer_id -> {check_type: result}
        self._check_states: dict[UUID, dict[str, int]] = defaultdict(dict)
        # Track retry tasks: transfer_id -> asyncio.Task
        self._retry_tasks: dict[UUID, asyncio.Task[None]] = {}
        self._cleanup_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the coordinator and begin periodic cleanup."""
        if self._running:
            return

        if self._pool is None:
            try:
                self._pool = await db_pool.init_pool()
            except (RuntimeError, ValueError):
                # In unit tests, pool may not be available
                # Skip initialization if DATABASE_URL is not set or invalid
                # ValueError is raised by Pydantic when DATABASE_URL is missing/invalid
                pass

        self._running = True
        if self._pool is not None:
            self._cleanup_task = asyncio.create_task(
                self._periodic_cleanup(), name="transfer-pool-cleanup"
            )
        LOGGER.info("transfer_event_pool.coordinator.started")

    async def stop(self) -> None:
        """Stop the coordinator and cancel all tasks."""
        if not self._running:
            return

        self._running = False

        # Cancel retry tasks
        for task in self._retry_tasks.values():
            if not task.done():
                task.cancel()
        self._retry_tasks.clear()

        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        self._check_states.clear()
        LOGGER.info("transfer_event_pool.coordinator.stopped")

    async def handle_check_result(
        self,
        *,
        transfer_id: UUID,
        check_type: str,
        result: int,
    ) -> None:
        """Handle a check result event."""
        if not self._running:
            return

        # Update check state
        self._check_states[transfer_id][check_type] = result

        # Check if all checks are complete
        check_state = self._check_states[transfer_id]
        required_checks = {"balance", "cooldown", "daily_limit"}

        if not required_checks.issubset(check_state.keys()):
            # Not all checks received yet
            return

        # All checks received, check if all passed
        all_passed = all(check_state[check] == 1 for check in required_checks)

        if all_passed:
            # 等待資料庫層發出的 transfer_check_approved 事件再觸發執行，
            # 這裡不直接執行以避免與核准事件重入造成重複轉帳。
            return
        else:
            # Some checks failed, schedule retry
            await self._schedule_retry(transfer_id)

    async def handle_check_approved(
        self,
        *,
        transfer_id: UUID,
    ) -> None:
        """Handle transfer check approved event."""
        if not self._running:
            return

        await self._execute_transfer(transfer_id)

    async def _execute_transfer(self, transfer_id: UUID) -> None:
        """Execute the approved transfer."""
        if self._pool is None:
            LOGGER.error("transfer_event_pool.execute.no_pool", transfer_id=transfer_id)
            return

        try:
            async with self._pool.acquire() as conn:
                # 以行鎖定的方式原子領取核准中的轉帳，避免並行重複執行
                try:
                    async with conn.transaction():
                        row = await conn.fetchrow(
                            """
                            SELECT transfer_id, guild_id, initiator_id, target_id,
                                   amount, metadata, status
                            FROM economy.pending_transfers
                            WHERE transfer_id = $1 AND status = 'approved'
                            FOR UPDATE
                            """,
                            transfer_id,
                        )

                        if row is None:
                            LOGGER.debug(
                                "transfer_event_pool.execute.skip",
                                transfer_id=transfer_id,
                                status="not_approved_or_already_processed",
                            )
                            return

                        result = await self._transfer_gateway.transfer_currency(
                            conn,
                            guild_id=row["guild_id"],
                            initiator_id=row["initiator_id"],
                            target_id=row["target_id"],
                            amount=row["amount"],
                            metadata=dict(row["metadata"] or {}),
                        )

                        # 標記完成
                        await self._pending_gateway.update_status(
                            conn, transfer_id=transfer_id, new_status="completed"
                        )

                        LOGGER.info(
                            "transfer_event_pool.execute.success",
                            transfer_id=transfer_id,
                            transaction_id=result.transaction_id,
                        )
                except Exception as exc:
                    LOGGER.exception(
                        "transfer_event_pool.execute.failed",
                        transfer_id=transfer_id,
                        error=str(exc),
                    )
                    # 失敗時標記為 rejected（在事務外最佳努力）
                    try:
                        await self._pending_gateway.update_status(
                            conn, transfer_id=transfer_id, new_status="rejected"
                        )
                    except Exception:
                        LOGGER.exception(
                            "transfer_event_pool.execute.status_update_failed",
                            transfer_id=transfer_id,
                        )
        except Exception:
            LOGGER.exception("transfer_event_pool.execute.error", transfer_id=transfer_id)

    async def _schedule_retry(self, transfer_id: UUID) -> None:
        """Schedule a retry for a failed transfer."""
        if self._pool is None:
            return

        # Cancel existing retry task if any
        if transfer_id in self._retry_tasks:
            task = self._retry_tasks[transfer_id]
            if not task.done():
                task.cancel()

        try:
            async with self._pool.acquire() as conn:
                pending = await self._pending_gateway.get_pending_transfer(
                    conn, transfer_id=transfer_id
                )
                if pending is None:
                    return

                # Check retry count
                if pending.retry_count >= 10:
                    LOGGER.info(
                        "transfer_event_pool.retry.max_reached",
                        transfer_id=transfer_id,
                        retry_count=pending.retry_count,
                    )
                    await self._pending_gateway.update_status(
                        conn, transfer_id=transfer_id, new_status="rejected"
                    )
                    # 發送交易拒絕事件，供上層通知使用者
                    try:
                        # 明確型別轉型，避免 asyncpg 在 jsonb_build_object 參數型別推斷失敗
                        await conn.execute(
                            """
                            SELECT pg_notify(
                                'economy_events',
                                jsonb_build_object(
                                    'event_type', 'transaction_denied',
                                    'reason', 'transfer_checks_failed',
                                    'transfer_id', $1::uuid,
                                    'guild_id', $2::bigint,
                                    'initiator_id', $3::bigint,
                                    'target_id', $4::bigint,
                                    'amount', $5::bigint
                                )::text
                            )
                            """,
                            transfer_id,
                            pending.guild_id,
                            pending.initiator_id,
                            pending.target_id,
                            pending.amount,
                        )
                    except Exception:
                        LOGGER.exception(
                            "transfer_event_pool.retry.notify_denied_failed",
                            transfer_id=transfer_id,
                        )
                    return

                # Calculate retry delay using exponential backoff: 2^retry_count seconds,
                # max 300 seconds. This matches Tenacity's exponential backoff pattern
                delay_seconds = min(2**pending.retry_count, 300)

                # Increment retry count
                async with conn.transaction():
                    await conn.execute(
                        """
                        UPDATE economy.pending_transfers
                        SET retry_count = retry_count + 1,
                            updated_at = timezone('utc', now())
                        WHERE transfer_id = $1
                        """,
                        transfer_id,
                    )

                # Schedule retry
                async def retry_task() -> None:
                    await asyncio.sleep(delay_seconds)
                    await self._retry_checks(transfer_id)

                self._retry_tasks[transfer_id] = asyncio.create_task(
                    retry_task(), name=f"transfer-retry-{transfer_id}"
                )

                LOGGER.info(
                    "transfer_event_pool.retry.scheduled",
                    transfer_id=transfer_id,
                    delay_seconds=delay_seconds,
                    retry_count=pending.retry_count + 1,
                )
        except Exception:
            LOGGER.exception("transfer_event_pool.retry.error", transfer_id=transfer_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((asyncpg.PostgresError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def _retry_checks(self, transfer_id: UUID) -> None:
        """Retry all checks for a transfer with automatic retry on database errors."""
        if self._pool is None:
            return

        try:
            async with self._pool.acquire() as conn:
                # Reset status to checking to allow checks to run
                await self._pending_gateway.update_status(
                    conn, transfer_id=transfer_id, new_status="checking"
                )

                # Re-trigger all checks (each function returns void, so we use execute)
                await conn.execute("SELECT economy.fn_check_transfer_balance($1)", transfer_id)
                await conn.execute("SELECT economy.fn_check_transfer_cooldown($1)", transfer_id)
                await conn.execute("SELECT economy.fn_check_transfer_daily_limit($1)", transfer_id)

                # Clear check state to allow fresh evaluation
                if transfer_id in self._check_states:
                    del self._check_states[transfer_id]

                LOGGER.debug("transfer_event_pool.retry.checks_triggered", transfer_id=transfer_id)
        except Exception:
            LOGGER.exception("transfer_event_pool.retry.checks_error", transfer_id=transfer_id)
            raise
        finally:
            # Remove retry task
            if transfer_id in self._retry_tasks:
                del self._retry_tasks[transfer_id]

    async def _periodic_cleanup(self) -> None:
        """Periodically clean up expired pending transfers."""
        if self._pool is None:
            return

        while self._running:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                LOGGER.exception("transfer_event_pool.cleanup.error")

    async def _cleanup_expired(self) -> None:
        """Clean up expired pending transfers."""
        if self._pool is None:
            return

        try:
            async with self._pool.acquire() as conn:
                now = datetime.now(timezone.utc)
                async with conn.transaction():
                    # 先以固定的 now 值更新，確保後續可用 updated_at 精準挑出本次處理的列
                    await conn.execute(
                        """
                        UPDATE economy.pending_transfers
                        SET status = 'rejected',
                            updated_at = $2
                        WHERE expires_at IS NOT NULL
                          AND expires_at < $1
                          AND status IN ('pending', 'checking')
                        """,
                        now,
                        now,
                    )

                    # 精準撈出剛才更新過的列以逐筆通知
                    rows = await conn.fetch(
                        """
                        SELECT transfer_id, guild_id, initiator_id, target_id, amount
                        FROM economy.pending_transfers
                        WHERE expires_at IS NOT NULL
                          AND expires_at < $1
                          AND status = 'rejected'
                          AND updated_at = $2
                        """,
                        now,
                        now,
                    )

                    for r in rows:
                        try:
                            await conn.execute(
                                """
                                SELECT pg_notify(
                                    'economy_events',
                                    jsonb_build_object(
                                        'event_type', 'transaction_denied',
                                        'reason', 'transfer_checks_expired',
                                        'transfer_id', $1::uuid,
                                        'guild_id', $2::bigint,
                                        'initiator_id', $3::bigint,
                                        'target_id', $4::bigint,
                                        'amount', $5::bigint
                                    )::text
                                )
                                """,
                                r["transfer_id"],
                                r["guild_id"],
                                r["initiator_id"],
                                r["target_id"],
                                r["amount"],
                            )
                        except Exception:
                            LOGGER.exception(
                                "transfer_event_pool.cleanup.notify_denied_failed",
                                transfer_id=r["transfer_id"],
                            )

                    if rows:
                        LOGGER.info(
                            "transfer_event_pool.cleanup.expired",
                            count=len(rows),
                        )
        except Exception:
            LOGGER.exception("transfer_event_pool.cleanup.error")
