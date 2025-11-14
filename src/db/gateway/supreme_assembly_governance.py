from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence, cast
from uuid import UUID

from src.cython_ext.supreme_assembly_models import (
    Proposal,
    Summon,
    SupremeAssemblyConfig,
    Tally,
)

# 與專案其他 gateway 一致，改用統一的資料庫連線協定，
# 以避免 asyncpg.Connection 與自定義 Protocol 在關鍵字參數上出現不相容警告。
from src.infra.types.db import ConnectionProtocol as AsyncPGConnectionProto


def _config_from_row(row: Mapping[str, Any]) -> SupremeAssemblyConfig:
    return SupremeAssemblyConfig(
        guild_id=int(row["guild_id"]),
        speaker_role_id=int(row["speaker_role_id"]),
        member_role_id=int(row["member_role_id"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _proposal_from_row(row: Mapping[str, Any]) -> Proposal:
    return Proposal(
        proposal_id=cast(UUID, row["proposal_id"]),
        guild_id=int(row["guild_id"]),
        proposer_id=int(row["proposer_id"]),
        title=cast(str | None, row["title"]),
        description=cast(str | None, row["description"]),
        snapshot_n=int(row["snapshot_n"]),
        threshold_t=int(row["threshold_t"]),
        deadline_at=cast(datetime, row["deadline_at"]),
        status=cast(str, row["status"]),
        reminder_sent=bool(row["reminder_sent"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _tally_from_row(row: Mapping[str, Any]) -> Tally:
    return Tally(
        approve=int(row["approve"]),
        reject=int(row["reject"]),
        abstain=int(row["abstain"]),
        total_voted=int(row["total_voted"]),
    )


def _summon_from_row(row: Mapping[str, Any]) -> Summon:
    return Summon(
        summon_id=cast(UUID, row["summon_id"]),
        guild_id=int(row["guild_id"]),
        invoked_by=int(row["invoked_by"]),
        target_id=int(row["target_id"]),
        target_kind=str(row["target_kind"]),
        note=cast(str | None, row["note"]),
        delivered=bool(row["delivered"]),
        delivered_at=cast(datetime | None, row["delivered_at"]),
        created_at=cast(datetime, row["created_at"]),
    )


class SupremeAssemblyGovernanceGateway:
    """Encapsulate CRUD ops for supreme assembly governance tables."""

    def __init__(self, *, schema: str = "governance") -> None:
        self._schema = schema

    # --- Config ---
    async def upsert_config(
        self,
        connection: AsyncPGConnectionProto,
        *,
        guild_id: int,
        speaker_role_id: int,
        member_role_id: int,
    ) -> SupremeAssemblyConfig:
        sql = f"SELECT * FROM {self._schema}.fn_upsert_supreme_assembly_config($1,$2,$3)"
        row: Mapping[str, Any] | None = await connection.fetchrow(
            sql, guild_id, speaker_role_id, member_role_id
        )
        assert row is not None
        return _config_from_row(row)

    async def fetch_config(
        self, connection: AsyncPGConnectionProto, *, guild_id: int
    ) -> SupremeAssemblyConfig | None:
        sql = f"SELECT * FROM {self._schema}.fn_get_supreme_assembly_config($1)"
        row: Mapping[str, Any] | None = await connection.fetchrow(sql, guild_id)
        if row is None:
            return None
        return _config_from_row(row)

    # --- Accounts ---
    async def fetch_account(
        self, connection: AsyncPGConnectionProto, *, guild_id: int
    ) -> tuple[int, int] | None:
        """Fetch account_id and balance for a guild."""
        sql = f"""
            SELECT account_id, balance
            FROM {self._schema}.supreme_assembly_accounts
            WHERE guild_id = $1
        """
        row: Mapping[str, Any] | None = await connection.fetchrow(sql, guild_id)
        if row is None:
            return None
        return (int(row["account_id"]), int(row["balance"]))

    async def ensure_account(
        self, connection: AsyncPGConnectionProto, *, guild_id: int, account_id: int
    ) -> None:
        """Ensure account exists, create if missing."""
        sql = f"""
            INSERT INTO {self._schema}.supreme_assembly_accounts (account_id, guild_id, balance)
            VALUES ($1, $2, 0)
            ON CONFLICT (account_id) DO NOTHING
        """
        await connection.execute(sql, account_id, guild_id)

    # --- Proposals ---
    async def create_proposal(
        self,
        connection: AsyncPGConnectionProto,
        *,
        guild_id: int,
        proposer_id: int,
        title: str | None,
        description: str | None,
        snapshot_member_ids: Sequence[int],
        deadline_hours: int = 72,
    ) -> Proposal:
        # Note: This will need a SQL function similar to fn_create_proposal
        # For now, we'll implement it directly, but ideally should use a function
        async with connection.transaction():
            # Check concurrency limit (max 5 active per guild)
            count_sql = f"""
                SELECT COUNT(*) FROM {self._schema}.supreme_assembly_proposals
                WHERE guild_id = $1 AND status = '進行中'
            """
            active_count_obj = cast(int | None, await connection.fetchval(count_sql, guild_id))
            active_count = 0 if active_count_obj is None else active_count_obj
            if active_count >= 5:
                raise RuntimeError(f"Active proposal limit reached for guild {guild_id}")

            # Calculate snapshot_n and threshold_t
            snapshot_n = len(list(dict.fromkeys(int(x) for x in snapshot_member_ids)))
            threshold_t = snapshot_n // 2 + 1

            # Calculate deadline
            from datetime import timedelta, timezone

            deadline_at = datetime.now(timezone.utc) + timedelta(hours=deadline_hours)

            # Insert proposal
            insert_sql = f"""
                INSERT INTO {self._schema}.supreme_assembly_proposals (
                    guild_id, proposer_id, title, description, snapshot_n, threshold_t,
                    deadline_at, status, reminder_sent
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, '進行中', false)
                RETURNING proposal_id, guild_id, proposer_id, title, description,
                          snapshot_n, threshold_t, deadline_at, status, reminder_sent,
                          created_at, updated_at
            """
            row: Mapping[str, Any] | None = await connection.fetchrow(
                insert_sql,
                guild_id,
                proposer_id,
                title,
                description,
                snapshot_n,
                threshold_t,
                deadline_at,
            )
            assert row is not None
            proposal_id = cast(UUID, row["proposal_id"])

            # Insert snapshot members
            if snapshot_n > 0:
                snapshot_sql = f"""
                    INSERT INTO {self._schema}.supreme_assembly_proposal_snapshots
                        (proposal_id, member_id)
                    SELECT $1, unnest($2::bigint[])
                    ON CONFLICT DO NOTHING
                """
                await connection.execute(snapshot_sql, proposal_id, list(snapshot_member_ids))

        return _proposal_from_row(row)

    async def fetch_proposal(
        self,
        connection: AsyncPGConnectionProto,
        *,
        proposal_id: UUID,
    ) -> Proposal | None:
        sql = f"""
            SELECT proposal_id, guild_id, proposer_id, title, description,
                   snapshot_n, threshold_t, deadline_at, status, reminder_sent,
                   created_at, updated_at
            FROM {self._schema}.supreme_assembly_proposals
            WHERE proposal_id = $1
        """
        row: Mapping[str, Any] | None = await connection.fetchrow(sql, proposal_id)
        if row is None:
            return None
        return _proposal_from_row(row)

    async def fetch_snapshot(
        self,
        connection: AsyncPGConnectionProto,
        *,
        proposal_id: UUID,
    ) -> Sequence[int]:
        sql = f"""
            SELECT member_id
            FROM {self._schema}.supreme_assembly_proposal_snapshots
            WHERE proposal_id = $1
        """
        rows: Sequence[Mapping[str, Any]] = await connection.fetch(sql, proposal_id)
        return [int(r["member_id"]) for r in rows]

    async def count_active_by_guild(
        self, connection: AsyncPGConnectionProto, *, guild_id: int
    ) -> int:
        sql = f"""
            SELECT COUNT(*) FROM {self._schema}.supreme_assembly_proposals
            WHERE guild_id = $1 AND status = '進行中'
        """
        val_obj = cast(int | None, await connection.fetchval(sql, guild_id))
        return 0 if val_obj is None else val_obj

    async def cancel_proposal(
        self, connection: AsyncPGConnectionProto, *, proposal_id: UUID
    ) -> bool:
        # Check if any votes exist
        vote_count_sql = f"""
            SELECT COUNT(*) FROM {self._schema}.supreme_assembly_votes
            WHERE proposal_id = $1
        """
        vote_count_obj = cast(int | None, await connection.fetchval(vote_count_sql, proposal_id))
        if vote_count_obj is not None and vote_count_obj > 0:
            return False

        # Cancel if no votes
        cancel_sql = f"""
            UPDATE {self._schema}.supreme_assembly_proposals
            SET status = '已撤案', updated_at = timezone('utc', clock_timestamp())
            WHERE proposal_id = $1 AND status = '進行中'
        """
        res: str = await connection.execute(cancel_sql, proposal_id)
        return res == "UPDATE 1"

    async def mark_status(
        self,
        connection: AsyncPGConnectionProto,
        *,
        proposal_id: UUID,
        status: str,
    ) -> None:
        sql = f"""
            UPDATE {self._schema}.supreme_assembly_proposals
            SET status = $2, updated_at = timezone('utc', clock_timestamp())
            WHERE proposal_id = $1
        """
        await connection.execute(sql, proposal_id, status)

    # --- Voting ---
    async def upsert_vote(
        self,
        connection: AsyncPGConnectionProto,
        *,
        proposal_id: UUID,
        voter_id: int,
        choice: str,
    ) -> None:
        # Note: For supreme assembly, votes are immutable - if vote exists, raise error
        # Check if vote already exists
        check_sql = f"""
            SELECT 1 FROM {self._schema}.supreme_assembly_votes
            WHERE proposal_id = $1 AND voter_id = $2
        """
        exists: bool = (await connection.fetchval(check_sql, proposal_id, voter_id)) is not None
        if exists:
            raise RuntimeError("Vote already exists and cannot be changed")

        insert_sql = f"""
            INSERT INTO {self._schema}.supreme_assembly_votes (proposal_id, voter_id, choice)
            VALUES ($1, $2, $3)
        """
        await connection.execute(insert_sql, proposal_id, voter_id, choice)

    async def fetch_tally(self, connection: AsyncPGConnectionProto, *, proposal_id: UUID) -> Tally:
        sql = f"""
            WITH counts AS (
                SELECT choice, COUNT(*)::int AS c
                FROM {self._schema}.supreme_assembly_votes
                WHERE proposal_id = $1
                GROUP BY choice
            )
            SELECT
                COALESCE(MAX(CASE WHEN choice = 'approve' THEN c END), 0) AS approve,
                COALESCE(MAX(CASE WHEN choice = 'reject' THEN c END), 0) AS reject,
                COALESCE(MAX(CASE WHEN choice = 'abstain' THEN c END), 0) AS abstain,
                COALESCE(SUM(c)::int, 0) AS total_voted
            FROM counts
        """
        row: Mapping[str, Any] | None = await connection.fetchrow(sql, proposal_id)
        assert row is not None
        return _tally_from_row(row)

    async def fetch_votes_detail(
        self, connection: AsyncPGConnectionProto, *, proposal_id: UUID
    ) -> Sequence[tuple[int, str]]:
        sql = f"""
            SELECT voter_id, choice
            FROM {self._schema}.supreme_assembly_votes
            WHERE proposal_id = $1
            ORDER BY created_at
        """
        rows: Sequence[Mapping[str, Any]] = await connection.fetch(sql, proposal_id)
        return [(int(r["voter_id"]), str(r["choice"])) for r in rows]

    # --- Queries for scheduler ---
    async def list_due_proposals(self, connection: AsyncPGConnectionProto) -> Sequence[Proposal]:
        sql = f"""
            SELECT proposal_id, guild_id, proposer_id, title, description,
                   snapshot_n, threshold_t, deadline_at, status, reminder_sent,
                   created_at, updated_at
            FROM {self._schema}.supreme_assembly_proposals
            WHERE status = '進行中' AND deadline_at <= timezone('utc', clock_timestamp())
        """
        rows: Sequence[Mapping[str, Any]] = await connection.fetch(sql)
        return [_proposal_from_row(r) for r in rows]

    async def list_reminder_candidates(
        self, connection: AsyncPGConnectionProto
    ) -> Sequence[Proposal]:
        sql = f"""
            SELECT proposal_id, guild_id, proposer_id, title, description,
                   snapshot_n, threshold_t, deadline_at, status, reminder_sent,
                   created_at, updated_at
            FROM {self._schema}.supreme_assembly_proposals
            WHERE status = '進行中'
              AND reminder_sent = false
              AND deadline_at - interval '24 hours' <= timezone('utc', clock_timestamp())
        """
        rows: Sequence[Mapping[str, Any]] = await connection.fetch(sql)
        return [_proposal_from_row(r) for r in rows]

    async def list_active_proposals(self, connection: AsyncPGConnectionProto) -> Sequence[Proposal]:
        sql = f"""
            SELECT proposal_id, guild_id, proposer_id, title, description,
                   snapshot_n, threshold_t, deadline_at, status, reminder_sent,
                   created_at, updated_at
            FROM {self._schema}.supreme_assembly_proposals
            WHERE status = '進行中'
            ORDER BY created_at
        """
        rows: Sequence[Mapping[str, Any]] = await connection.fetch(sql)
        return [_proposal_from_row(r) for r in rows]

    async def mark_reminded(self, connection: AsyncPGConnectionProto, *, proposal_id: UUID) -> None:
        sql = f"""
            UPDATE {self._schema}.supreme_assembly_proposals
            SET reminder_sent = true, updated_at = timezone('utc', clock_timestamp())
            WHERE proposal_id = $1
        """
        await connection.execute(sql, proposal_id)

    # --- Export ---
    async def export_interval(
        self,
        connection: AsyncPGConnectionProto,
        *,
        guild_id: int,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, object]]:
        sql = f"""
            SELECT p.proposal_id, p.guild_id, p.proposer_id, p.title, p.description,
                   p.snapshot_n, p.threshold_t, p.deadline_at, p.status,
                   p.created_at, p.updated_at,
                   COALESCE(v.votes, '[]'::json) AS votes,
                   COALESCE(s.snapshot, '[]'::json) AS snapshot
            FROM {self._schema}.supreme_assembly_proposals p
            LEFT JOIN LATERAL (
                SELECT json_agg(
                           json_build_object(
                               'voter_id', v.voter_id,
                               'choice', v.choice,
                               'created_at', v.created_at
                           ) ORDER BY v.created_at
                       ) AS votes
                FROM {self._schema}.supreme_assembly_votes v
                WHERE v.proposal_id = p.proposal_id
            ) v ON TRUE
            LEFT JOIN LATERAL (
                SELECT json_agg(ps.member_id) AS snapshot
                FROM {self._schema}.supreme_assembly_proposal_snapshots ps
                WHERE ps.proposal_id = p.proposal_id
            ) s ON TRUE
            WHERE p.guild_id = $1 AND p.created_at >= $2 AND p.created_at < $3
            ORDER BY p.created_at
        """
        rows: Sequence[Mapping[str, Any]] = await connection.fetch(sql, guild_id, start, end)
        return [dict(r) for r in rows]

    async def list_unvoted_members(
        self, connection: AsyncPGConnectionProto, *, proposal_id: UUID
    ) -> Sequence[int]:
        sql = f"""
            SELECT ps.member_id
            FROM {self._schema}.supreme_assembly_proposal_snapshots ps
            WHERE ps.proposal_id = $1
              AND NOT EXISTS (
                  SELECT 1 FROM {self._schema}.supreme_assembly_votes v
                  WHERE v.proposal_id = ps.proposal_id AND v.voter_id = ps.member_id
              )
            ORDER BY ps.member_id
        """
        rows: Sequence[Mapping[str, Any]] = await connection.fetch(sql, proposal_id)
        return [int(r["member_id"]) for r in rows]

    # --- Summons ---
    async def create_summon(
        self,
        connection: AsyncPGConnectionProto,
        *,
        guild_id: int,
        invoked_by: int,
        target_id: int,
        target_kind: str,
        note: str | None = None,
    ) -> Summon:
        sql = f"""
            INSERT INTO {self._schema}.supreme_assembly_summons (
                guild_id, invoked_by, target_id, target_kind, note, delivered
            ) VALUES ($1, $2, $3, $4, $5, false)
            RETURNING summon_id, guild_id, invoked_by, target_id, target_kind, note,
                      delivered, delivered_at, created_at
        """
        row: Mapping[str, Any] | None = await connection.fetchrow(
            sql, guild_id, invoked_by, target_id, target_kind, note
        )
        assert row is not None
        return _summon_from_row(row)

    async def mark_summon_delivered(
        self, connection: AsyncPGConnectionProto, *, summon_id: UUID
    ) -> None:
        sql = f"""
            UPDATE {self._schema}.supreme_assembly_summons
            SET delivered = true, delivered_at = timezone('utc', clock_timestamp())
            WHERE summon_id = $1
        """
        await connection.execute(sql, summon_id)

    async def list_summons(
        self, connection: AsyncPGConnectionProto, *, guild_id: int, limit: int = 50
    ) -> Sequence[Summon]:
        sql = f"""
            SELECT summon_id, guild_id, invoked_by, target_id, target_kind, note,
                   delivered, delivered_at, created_at
            FROM {self._schema}.supreme_assembly_summons
            WHERE guild_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        rows: Sequence[Mapping[str, Any]] = await connection.fetch(sql, guild_id, limit)
        return [_summon_from_row(r) for r in rows]


__all__ = [
    "SupremeAssemblyConfig",
    "SupremeAssemblyGovernanceGateway",
    "Proposal",
    "Tally",
    "Summon",
]
