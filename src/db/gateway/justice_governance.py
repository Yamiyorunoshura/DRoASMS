from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from src.cython_ext.state_council_models import Suspect
from src.infra.types.db import ConnectionProtocol


class JusticeGovernanceGateway:
    """Encapsulate CRUD ops for justice department suspects table."""

    def __init__(self, *, schema: str = "governance") -> None:
        self._schema = schema

    # --- Suspects Management ---
    async def create_suspect(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        member_id: int,
        arrested_by: int,
        arrest_reason: str,
    ) -> Suspect:
        """Create a new suspect record."""
        now = datetime.now(timezone.utc)

        query = f"""
            INSERT INTO {self._schema}.suspects (
                guild_id, member_id, arrested_by, arrest_reason, status,
                arrested_at, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, 'detained', $5, $6, $7)
            RETURNING
                suspect_id, guild_id, member_id, arrested_by, arrest_reason,
                status, arrested_at, charged_at, released_at, created_at, updated_at
        """

        row = await connection.fetchrow(
            query,
            guild_id,
            member_id,
            arrested_by,
            arrest_reason,
            now,
            now,
            now,
        )

        return Suspect(
            suspect_id=int(row["suspect_id"]),
            guild_id=int(row["guild_id"]),
            member_id=int(row["member_id"]),
            arrested_by=int(row["arrested_by"]),
            arrest_reason=str(row["arrest_reason"]),
            status=str(row["status"]),
            arrested_at=row["arrested_at"],
            charged_at=row["charged_at"],
            released_at=row["released_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_active_suspects(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        statuses: Sequence[str] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Sequence[Suspect]:
        """Get suspects with pagination.

        Args:
            guild_id: Guild identifier
            statuses: Optional statuses filter, defaults to ("detained", "charged").
            limit: Page size
            offset: Offset for pagination
        """
        effective_statuses: Sequence[str] = statuses or ("detained", "charged")

        query = f"""
            SELECT
                suspect_id, guild_id, member_id, arrested_by, arrest_reason,
                status, arrested_at, charged_at, released_at, created_at, updated_at
            FROM {self._schema}.suspects
            WHERE guild_id = $1 AND status = ANY($2::text[])
            ORDER BY arrested_at DESC
            LIMIT $3 OFFSET $4
        """

        rows = await connection.fetch(query, guild_id, list(effective_statuses), limit, offset)

        return [
            Suspect(
                suspect_id=int(row["suspect_id"]),
                guild_id=int(row["guild_id"]),
                member_id=int(row["member_id"]),
                arrested_by=int(row["arrested_by"]),
                arrest_reason=str(row["arrest_reason"]),
                status=str(row["status"]),
                arrested_at=row["arrested_at"],
                charged_at=row["charged_at"],
                released_at=row["released_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def get_suspect_by_member(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        member_id: int,
    ) -> Suspect | None:
        """Get the active suspect record for a member."""
        query = f"""
            SELECT
                suspect_id, guild_id, member_id, arrested_by, arrest_reason,
                status, arrested_at, charged_at, released_at, created_at, updated_at
            FROM {self._schema}.suspects
            WHERE guild_id = $1 AND member_id = $2 AND status IN ('detained', 'charged')
            ORDER BY arrested_at DESC
            LIMIT 1
        """

        row = await connection.fetchrow(query, guild_id, member_id)

        if not row:
            return None

        return Suspect(
            suspect_id=int(row["suspect_id"]),
            guild_id=int(row["guild_id"]),
            member_id=int(row["member_id"]),
            arrested_by=int(row["arrested_by"]),
            arrest_reason=str(row["arrest_reason"]),
            status=str(row["status"]),
            arrested_at=row["arrested_at"],
            charged_at=row["charged_at"],
            released_at=row["released_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_latest_suspect_record(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        member_id: int,
    ) -> Suspect | None:
        """Get the latest suspect record for a member (regardless of status)."""
        query = f"""
            SELECT
                suspect_id, guild_id, member_id, arrested_by, arrest_reason,
                status, arrested_at, charged_at, released_at, created_at, updated_at
            FROM {self._schema}.suspects
            WHERE guild_id = $1 AND member_id = $2
            ORDER BY arrested_at DESC
            LIMIT 1
        """

        row = await connection.fetchrow(query, guild_id, member_id)

        if not row:
            return None

        return Suspect(
            suspect_id=int(row["suspect_id"]),
            guild_id=int(row["guild_id"]),
            member_id=int(row["member_id"]),
            arrested_by=int(row["arrested_by"]),
            arrest_reason=str(row["arrest_reason"]),
            status=str(row["status"]),
            arrested_at=row["arrested_at"],
            charged_at=row["charged_at"],
            released_at=row["released_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def charge_suspect(
        self,
        connection: ConnectionProtocol,
        *,
        suspect_id: int,
    ) -> Suspect:
        """Charge a suspect (change status from detained to charged)."""
        now = datetime.now(timezone.utc)

        query = f"""
            UPDATE {self._schema}.suspects
            SET status = 'charged', charged_at = $1, updated_at = $2
            WHERE suspect_id = $3 AND status = 'detained'
            RETURNING
                suspect_id, guild_id, member_id, arrested_by, arrest_reason,
                status, arrested_at, charged_at, released_at, created_at, updated_at
        """

        row = await connection.fetchrow(query, now, now, suspect_id)

        if not row:
            raise ValueError("Suspect not found or already charged")

        return Suspect(
            suspect_id=int(row["suspect_id"]),
            guild_id=int(row["guild_id"]),
            member_id=int(row["member_id"]),
            arrested_by=int(row["arrested_by"]),
            arrest_reason=str(row["arrest_reason"]),
            status=str(row["status"]),
            arrested_at=row["arrested_at"],
            charged_at=row["charged_at"],
            released_at=row["released_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def revoke_charge(
        self,
        connection: ConnectionProtocol,
        *,
        suspect_id: int,
    ) -> Suspect:
        """Revoke a charge (change status from charged back to detained).

        起訴相關欄位（charged_at）會被清空，以符合「撤銷起訴」後回到拘留狀態的要求。
        """
        now = datetime.now(timezone.utc)

        query = f"""
            UPDATE {self._schema}.suspects
            SET status = 'detained', charged_at = NULL, updated_at = $1
            WHERE suspect_id = $2 AND status = 'charged'
            RETURNING
                suspect_id, guild_id, member_id, arrested_by, arrest_reason,
                status, arrested_at, charged_at, released_at, created_at, updated_at
        """

        row = await connection.fetchrow(query, now, suspect_id)

        if not row:
            raise ValueError("Suspect not found or not charged")

        return Suspect(
            suspect_id=int(row["suspect_id"]),
            guild_id=int(row["guild_id"]),
            member_id=int(row["member_id"]),
            arrested_by=int(row["arrested_by"]),
            arrest_reason=str(row["arrest_reason"]),
            status=str(row["status"]),
            arrested_at=row["arrested_at"],
            charged_at=row["charged_at"],
            released_at=row["released_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def release_suspect(
        self,
        connection: ConnectionProtocol,
        *,
        suspect_id: int,
    ) -> Suspect:
        """Release a suspect (change status to released)."""
        now = datetime.now(timezone.utc)

        query = f"""
            UPDATE {self._schema}.suspects
            SET status = 'released', released_at = $1, updated_at = $2
            WHERE suspect_id = $3 AND status IN ('detained', 'charged')
            RETURNING
                suspect_id, guild_id, member_id, arrested_by, arrest_reason,
                status, arrested_at, charged_at, released_at, created_at, updated_at
        """

        row = await connection.fetchrow(query, now, now, suspect_id)

        if not row:
            raise ValueError("Suspect not found or already released")

        return Suspect(
            suspect_id=int(row["suspect_id"]),
            guild_id=int(row["guild_id"]),
            member_id=int(row["member_id"]),
            arrested_by=int(row["arrested_by"]),
            arrest_reason=str(row["arrest_reason"]),
            status=str(row["status"]),
            arrested_at=row["arrested_at"],
            charged_at=row["charged_at"],
            released_at=row["released_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
