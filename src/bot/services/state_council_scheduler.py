"""Background scheduler for State Council operations.

This module handles automated tasks such as:
- Periodic welfare disbursements
- Monthly issuance limit tracking
- Scheduled operations maintenance
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Set, cast

import structlog

from src.bot.services.state_council_service import StateCouncilService
from src.db.gateway.state_council_governance import StateCouncilGovernanceGateway
from src.db.pool import get_pool
from src.infra.types.db import ConnectionProtocol, PoolProtocol

LOGGER = structlog.get_logger(__name__)

# Global scheduler task reference
_scheduler_task: asyncio.Task[None] | None = None


@dataclass(slots=True)
class AutoReleaseJob:
    guild_id: int
    suspect_id: int
    release_at: datetime
    hours: int
    scheduled_by: int
    scheduled_at: datetime


# In-memory storage for auto-release settings (minimal viable implementation)
# Format: {guild_id: {suspect_id: AutoReleaseJob}}
_auto_release_settings: dict[int, dict[int, AutoReleaseJob]] = {}


def get_auto_release_jobs_for_guild(guild_id: int) -> dict[int, AutoReleaseJob]:
    """Return a shallow copy of scheduled auto-release jobs for a guild."""

    return dict(_auto_release_settings.get(guild_id, {}))


def get_all_auto_release_jobs() -> dict[int, dict[int, AutoReleaseJob]]:
    """Return copy of all scheduled jobs (primarily for diagnostics/tests)."""

    return {gid: dict(jobs) for gid, jobs in _auto_release_settings.items()}


def _cleanup_empty_guild_entries() -> None:
    global _auto_release_settings
    _auto_release_settings = {gid: jobs for gid, jobs in _auto_release_settings.items() if jobs}


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
                pool: PoolProtocol = cast(PoolProtocol, get_pool())
                current_time = datetime.now(tz=timezone.utc)

                async with pool.acquire() as conn:
                    gateway = StateCouncilGovernanceGateway()
                    service = StateCouncilService(gateway=gateway)

                    # Process periodic welfare disbursements
                    await _process_welfare_disbursements(
                        conn, gateway, service, current_time, processed_welfare
                    )

                    # Check monthly issuance limits
                    await _check_monthly_issuance_limits(
                        conn, gateway, current_time, processed_issuance
                    )

                    # Cleanup old records (optional)
                    await _cleanup_old_records(conn, gateway)

                    # Process auto-release for suspects
                    await _process_auto_release(conn, service, current_time, client)

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
    conn: ConnectionProtocol,
    gateway: StateCouncilGovernanceGateway,
    service: StateCouncilService,
    current_time: datetime,
    processed_welfare: Set[int],
) -> None:
    """Process automatic welfare disbursements based on department configurations."""
    try:
        # Get all guilds with Internal Affairs department configuration
        configs = await gateway.fetch_all_department_configs_with_welfare(conn)

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
    conn: ConnectionProtocol,
    gateway: StateCouncilGovernanceGateway,
    current_time: datetime,
    processed_issuance: Set[str],
) -> None:
    """Check and log monthly currency issuance status."""
    try:
        current_month = current_time.strftime("%Y-%m")

        if current_month in processed_issuance:
            return

        # Get all guilds with Central Bank configurations
        configs = await gateway.fetch_all_department_configs_for_issuance(conn)

        for config in configs:
            if config.get("max_issuance_per_month", 0) <= 0:
                continue

            # Get current month's total issuance
            current_total = await gateway.sum_monthly_issuance(
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
    conn: ConnectionProtocol, gateway: StateCouncilGovernanceGateway
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


async def _process_auto_release(
    conn: ConnectionProtocol, service: StateCouncilService, current_time: datetime, client: Any
) -> None:
    """Process automatic release of suspects based on in-memory settings."""
    try:
        global _auto_release_settings

        # Check each guild's auto-release settings
        for guild_id, jobs in list(_auto_release_settings.items()):
            if not jobs:
                continue

            ready_jobs = [job for job in jobs.values() if job.release_at <= current_time]
            if not ready_jobs:
                continue

            guild = client.get_guild(guild_id)
            if not guild:
                for job in ready_jobs:
                    jobs.pop(job.suspect_id, None)
                continue

            suspect_ids = [job.suspect_id for job in ready_jobs]
            operator_id = ready_jobs[0].scheduled_by
            if not operator_id:
                try:
                    operator_id = getattr(getattr(client, "user", None), "id", 0)
                except Exception:
                    operator_id = 0

            try:
                results = await service.release_suspects(
                    guild=guild,
                    guild_id=guild_id,
                    department="國土安全部",
                    user_id=operator_id,
                    user_roles=[],
                    suspect_ids=suspect_ids,
                    reason="達到自動釋放時間",
                    audit_source="auto-release",
                    skip_permission=True,
                )
            except Exception as exc:
                LOGGER.warning(
                    "state_council.scheduler.auto_release.failed_batch",
                    guild_id=guild_id,
                    suspect_ids=suspect_ids,
                    error=str(exc),
                )
                for job in ready_jobs:
                    jobs.pop(job.suspect_id, None)
                continue

            for job in ready_jobs:
                jobs.pop(job.suspect_id, None)

            # Log per-result outcomes for observability
            for result in results:
                suspect_id = getattr(result, "suspect_id", None)
                released = bool(getattr(result, "released", False))
                display_name = getattr(result, "display_name", None)
                if released:
                    LOGGER.info(
                        "state_council.scheduler.auto_release.completed",
                        guild_id=guild_id,
                        suspect_id=suspect_id,
                        member_name=display_name,
                    )
                else:
                    LOGGER.warning(
                        "state_council.scheduler.auto_release.failed",
                        guild_id=guild_id,
                        suspect_id=suspect_id,
                        error=getattr(result, "error", "unknown"),
                    )

        _cleanup_empty_guild_entries()

        LOGGER.debug(
            "state_council.scheduler.auto_release.checked",
            total_guilds=len(_auto_release_settings),
            total_suspects=sum(len(suspects) for suspects in _auto_release_settings.values()),
        )

    except Exception as exc:
        LOGGER.exception("state_council.scheduler.auto_release_error", error=str(exc))


def set_auto_release(
    guild_id: int, suspect_id: int, hours: int, *, scheduled_by: int
) -> AutoReleaseJob:
    """Set auto-release time for a suspect (in-memory only)."""

    global _auto_release_settings

    normalized_hours = max(1, min(168, int(hours)))
    now = datetime.now(tz=timezone.utc)
    release_time = now + timedelta(hours=normalized_hours)

    job = AutoReleaseJob(
        guild_id=guild_id,
        suspect_id=suspect_id,
        release_at=release_time,
        hours=normalized_hours,
        scheduled_by=scheduled_by,
        scheduled_at=now,
    )

    if guild_id not in _auto_release_settings:
        _auto_release_settings[guild_id] = {}

    _auto_release_settings[guild_id][suspect_id] = job

    LOGGER.info(
        "state_council.scheduler.auto_release.set",
        guild_id=guild_id,
        suspect_id=suspect_id,
        hours=normalized_hours,
        release_time=release_time,
        scheduled_by=scheduled_by,
    )

    return job


def cancel_auto_release(guild_id: int, suspect_id: int) -> None:
    """Cancel auto-release for a suspect."""

    global _auto_release_settings

    jobs = _auto_release_settings.get(guild_id)
    if not jobs or suspect_id not in jobs:
        return

    del jobs[suspect_id]
    if not jobs:
        del _auto_release_settings[guild_id]

    LOGGER.info(
        "state_council.scheduler.auto_release.cancelled",
        guild_id=guild_id,
        suspect_id=suspect_id,
    )
