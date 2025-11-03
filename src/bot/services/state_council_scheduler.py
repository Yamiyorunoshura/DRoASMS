"""Background scheduler for State Council operations.

This module handles automated tasks such as:
- Periodic welfare disbursements
- Monthly issuance limit tracking
- Scheduled operations maintenance
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Set

import asyncpg
import structlog

from src.bot.services.state_council_service import StateCouncilService
from src.db.gateway.state_council_governance import StateCouncilGovernanceGateway
from src.db.pool import get_pool

LOGGER = structlog.get_logger(__name__)

# Global scheduler task reference
_scheduler_task: asyncio.Task[None] | None = None


async def start_scheduler(client: Any) -> None:
    """Start the State Council background scheduler."""
    global _scheduler_task
    if _scheduler_task is not None:
        return

    async def _runner() -> None:
        await client.wait_until_ready()
        LOGGER.info("state_council.scheduler.started")

        # Track processed items to avoid duplicates
        processed_welfare: Set[int] = set()
        processed_issuance: Set[str] = set()

        while not client.is_closed():
            try:
                pool = get_pool()
                current_time = datetime.now(tz=timezone.utc)

                async with pool.acquire() as conn:
                    gateway = StateCouncilGovernanceGateway()
                    service = StateCouncilService(gateway=gateway)

                    # Process periodic welfare disbursements
                    await _process_welfare_disbursements(
                        conn, service, current_time, processed_welfare
                    )

                    # Check monthly issuance limits
                    await _check_monthly_issuance_limits(
                        conn, service, current_time, processed_issuance
                    )

                    # Cleanup old records (optional)
                    await _cleanup_old_records(conn, gateway)

                # Sleep for 5 minutes before next check
                await asyncio.sleep(300)

            except Exception as exc:
                LOGGER.exception("state_council.scheduler.error", error=str(exc))
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    _scheduler_task = asyncio.create_task(_runner())


async def stop_scheduler() -> None:
    """Stop the State Council background scheduler."""
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
        LOGGER.info("state_council.scheduler.stopped")


async def _process_welfare_disbursements(
    conn: asyncpg.Connection,
    service: StateCouncilService,
    current_time: datetime,
    processed_welfare: Set[int],
) -> None:
    """Process automatic welfare disbursements based on department configurations."""
    try:
        # Get all guilds with Internal Affairs department configuration
        configs = await service._gateway.fetch_all_department_configs_with_welfare(conn)

        for config in configs:
            if config.get("welfare_amount", 0) <= 0 or config.get("welfare_interval_hours", 0) <= 0:
                continue

            # Check if this guild's welfare needs processing
            guild_key = config["guild_id"]
            if guild_key in processed_welfare:
                continue

            # Check if it's time to disburse (this is simplified)
            # In a real implementation, you'd track last disbursement time
            # For now, we'll just log the capability
            LOGGER.info(
                "state_council.scheduler.welfare_check",
                guild_id=config["guild_id"],
                welfare_amount=config.get("welfare_amount", 0),
                interval_hours=config.get("welfare_interval_hours", 0),
            )

            # Mark as processed to avoid repeated checks
            processed_welfare.add(guild_key)

    except Exception as exc:
        LOGGER.exception("state_council.scheduler.welfare_error", error=str(exc))


async def _check_monthly_issuance_limits(
    conn: asyncpg.Connection,
    service: StateCouncilService,
    current_time: datetime,
    processed_issuance: Set[str],
) -> None:
    """Check and log monthly currency issuance status."""
    try:
        current_month = current_time.strftime("%Y-%m")

        if current_month in processed_issuance:
            return

        # Get all guilds with Central Bank configurations
        configs = await service._gateway.fetch_all_department_configs_for_issuance(conn)

        for config in configs:
            if config.get("max_issuance_per_month", 0) <= 0:
                continue

            # Get current month's total issuance
            current_total = await service._gateway.sum_monthly_issuance(
                conn, guild_id=config["guild_id"], month_period=current_month
            )

            # Log status
            LOGGER.info(
                "state_council.scheduler.issuance_check",
                guild_id=config["guild_id"],
                month=current_month,
                issued=current_total,
                limit=config.get("max_issuance_per_month", 0),
                remaining=max(0, config.get("max_issuance_per_month", 0) - current_total),
            )

        processed_issuance.add(current_month)

    except Exception as exc:
        LOGGER.exception("state_council.scheduler.issuance_error", error=str(exc))


async def _cleanup_old_records(
    conn: asyncpg.Connection, gateway: StateCouncilGovernanceGateway
) -> None:
    """Clean up old records to prevent database bloat (optional)."""
    try:
        # This is a placeholder for record cleanup
        # In a real implementation, you might delete records older than 1 year
        cutoff_date = datetime.now(tz=timezone.utc) - timedelta(days=365)

        # Example: Clean up old welfare disbursement records
        # await gateway.cleanup_old_welfare_records(conn, cutoff_date)

        LOGGER.debug("state_council.scheduler.cleanup_checked", cutoff_date=cutoff_date)

    except Exception as exc:
        LOGGER.exception("state_council.scheduler.cleanup_error", error=str(exc))
