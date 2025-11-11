"""Background scheduler for State Council operations.

This module handles automated tasks such as:
- Periodic welfare disbursements
- Monthly issuance limit tracking
- Scheduled operations maintenance
"""

from __future__ import annotations

import asyncio
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

# In-memory storage for auto-release settings (minimal viable implementation)
# Format: {guild_id: {suspect_id: release_time}}
_auto_release_settings: dict[int, dict[int, datetime]] = {}


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
        for guild_id, suspects in list(_auto_release_settings.items()):
            if not suspects:
                continue

            # Get guild config to check role IDs
            try:
                cfg = await service.get_config(guild_id=guild_id)
                if not cfg.suspect_role_id or not cfg.citizen_role_id:
                    continue
            except Exception:
                # Guild not configured, skip
                continue

            # Check each suspect's release time
            for suspect_id, release_time in list(suspects.items()):
                if release_time > current_time:
                    continue  # Not time yet

                # Time to release this suspect
                try:
                    # Get guild and member
                    guild = client.get_guild(guild_id)
                    if not guild:
                        # Guild not found, remove from settings
                        del suspects[suspect_id]
                        continue

                    member = guild.get_member(suspect_id)
                    if not member:
                        # Member not found, remove from settings
                        del suspects[suspect_id]
                        continue

                    # Remove suspect role and add citizen role
                    suspect_role = guild.get_role(cfg.suspect_role_id)
                    citizen_role = guild.get_role(cfg.citizen_role_id)

                    if suspect_role and suspect_role in member.roles:
                        await member.remove_roles(suspect_role, reason="自動釋放")

                    if citizen_role and citizen_role not in member.roles:
                        await member.add_roles(citizen_role, reason="自動釋放")

                    # Record identity action
                    await service.record_identity_action(
                        guild_id=guild_id,
                        target_id=suspect_id,
                        action="移除疑犯標記",
                        reason="達到自動釋放時間",
                        performed_by=0,  # System user
                    )

                    # Remove from auto-release settings
                    del suspects[suspect_id]

                    LOGGER.info(
                        "state_council.scheduler.auto_release.completed",
                        guild_id=guild_id,
                        suspect_id=suspect_id,
                        member_name=member.display_name,
                    )

                except Exception as exc:
                    LOGGER.warning(
                        "state_council.scheduler.auto_release.failed",
                        guild_id=guild_id,
                        suspect_id=suspect_id,
                        error=str(exc),
                    )
                    # Remove from settings to avoid repeated failures
                    del suspects[suspect_id]

        # Clean up empty guild entries
        _auto_release_settings = {
            gid: suspects for gid, suspects in _auto_release_settings.items() if suspects
        }

        LOGGER.debug(
            "state_council.scheduler.auto_release.checked",
            total_guilds=len(_auto_release_settings),
            total_suspects=sum(len(suspects) for suspects in _auto_release_settings.values()),
        )

    except Exception as exc:
        LOGGER.exception("state_council.scheduler.auto_release_error", error=str(exc))


def set_auto_release(guild_id: int, suspect_id: int, hours: int) -> None:
    """Set auto-release time for a suspect (in-memory only)."""
    global _auto_release_settings

    release_time = datetime.now(tz=timezone.utc) + timedelta(hours=hours)

    if guild_id not in _auto_release_settings:
        _auto_release_settings[guild_id] = {}

    _auto_release_settings[guild_id][suspect_id] = release_time

    LOGGER.info(
        "state_council.scheduler.auto_release.set",
        guild_id=guild_id,
        suspect_id=suspect_id,
        hours=hours,
        release_time=release_time,
    )


def cancel_auto_release(guild_id: int, suspect_id: int) -> None:
    """Cancel auto-release for a suspect."""
    global _auto_release_settings

    if guild_id in _auto_release_settings and suspect_id in _auto_release_settings[guild_id]:
        del _auto_release_settings[guild_id][suspect_id]

        # Clean up empty guild entry
        if not _auto_release_settings[guild_id]:
            del _auto_release_settings[guild_id]

        LOGGER.info(
            "state_council.scheduler.auto_release.cancelled",
            guild_id=guild_id,
            suspect_id=suspect_id,
        )
