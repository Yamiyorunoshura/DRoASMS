from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence, cast
from uuid import UUID

import asyncpg

# --- Data Models ---


@dataclass(frozen=True, slots=True)
class CouncilConfig:
    guild_id: int
    council_role_id: int
    council_account_member_id: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Proposal:
    proposal_id: UUID
    guild_id: int
    proposer_id: int
    target_id: int
    amount: int
    description: str | None
    attachment_url: str | None
    snapshot_n: int
    threshold_t: int
    deadline_at: datetime
    status: str
    reminder_sent: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Tally:
    approve: int
    reject: int
    abstain: int
    total_voted: int


class CouncilGovernanceGateway:
    """Encapsulate CRUD ops for council governance tables."""

    def __init__(self, *, schema: str = "governance") -> None:
        self._schema = schema

    # --- Config ---
    async def upsert_config(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        council_role_id: int,
        council_account_member_id: int,
    ) -> CouncilConfig:
        sql = f"""
            INSERT INTO {self._schema}.council_config (
                guild_id, council_role_id, council_account_member_id
            )
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id)
            DO UPDATE SET council_role_id = EXCLUDED.council_role_id,
                          council_account_member_id = EXCLUDED.council_account_member_id,
                          updated_at = timezone('utc', now())
            RETURNING guild_id, council_role_id,
                      council_account_member_id, created_at, updated_at
        """
        row = await connection.fetchrow(sql, guild_id, council_role_id, council_account_member_id)
        assert row is not None
        return CouncilConfig(
            guild_id=row["guild_id"],
            council_role_id=row["council_role_id"],
            council_account_member_id=row["council_account_member_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def fetch_config(
        self, connection: asyncpg.Connection, *, guild_id: int
    ) -> CouncilConfig | None:
        sql = f"""
            SELECT guild_id, council_role_id, council_account_member_id, created_at, updated_at
            FROM {self._schema}.council_config
            WHERE guild_id = $1
        """
        row = await connection.fetchrow(sql, guild_id)
        if row is None:
            return None
        return CouncilConfig(
            guild_id=row["guild_id"],
            council_role_id=row["council_role_id"],
            council_account_member_id=row["council_account_member_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # --- Proposals ---
    async def create_proposal(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        proposer_id: int,
        target_id: int,
        amount: int,
        description: str | None,
        attachment_url: str | None,
        snapshot_member_ids: Sequence[int],
        deadline_hours: int = 72,
    ) -> Proposal:
        n = len(snapshot_member_ids)
        t = n // 2 + 1
        deadline = datetime.now(tz=timezone.utc) + timedelta(hours=deadline_hours)

        async with connection.transaction():
            # Enforce concurrency limit 5 per guild
            count_sql = (
                f"SELECT COUNT(*) AS c FROM {self._schema}.proposals "
                "WHERE guild_id=$1 AND status='進行中'"
            )
            count = await connection.fetchval(count_sql, guild_id)
            if int(count or 0) >= 5:
                raise RuntimeError("Concurrency limit reached for active proposals in this guild.")

            insert_sql = f"""
                INSERT INTO {self._schema}.proposals (
                    guild_id, proposer_id, target_id, amount, description, attachment_url,
                    snapshot_n, threshold_t, deadline_at, status
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'進行中')
                RETURNING proposal_id, guild_id, proposer_id, target_id, amount, description,
                          attachment_url, snapshot_n, threshold_t, deadline_at, status,
                          reminder_sent, created_at, updated_at
            """
            row = await connection.fetchrow(
                insert_sql,
                guild_id,
                proposer_id,
                target_id,
                amount,
                description,
                attachment_url,
                n,
                t,
                deadline,
            )
            assert row is not None
            pid: UUID = row["proposal_id"]

            if n:
                await connection.executemany(
                    (
                        f"INSERT INTO {self._schema}.proposal_snapshots (proposal_id, member_id) "
                        "VALUES ($1,$2) ON CONFLICT DO NOTHING"
                    ),
                    [(pid, mid) for mid in snapshot_member_ids],
                )

        return Proposal(
            proposal_id=row["proposal_id"],
            guild_id=row["guild_id"],
            proposer_id=row["proposer_id"],
            target_id=row["target_id"],
            amount=row["amount"],
            description=row["description"],
            attachment_url=row["attachment_url"],
            snapshot_n=row["snapshot_n"],
            threshold_t=row["threshold_t"],
            deadline_at=row["deadline_at"],
            status=row["status"],
            reminder_sent=row["reminder_sent"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def fetch_proposal(
        self,
        connection: asyncpg.Connection,
        *,
        proposal_id: UUID,
    ) -> Proposal | None:
        sql = f"""
            SELECT proposal_id, guild_id, proposer_id, target_id, amount, description,
                   attachment_url, snapshot_n, threshold_t, deadline_at, status,
                   reminder_sent, created_at, updated_at
            FROM {self._schema}.proposals WHERE proposal_id=$1
        """
        row = await connection.fetchrow(sql, proposal_id)
        if row is None:
            return None
        return Proposal(
            proposal_id=row["proposal_id"],
            guild_id=row["guild_id"],
            proposer_id=row["proposer_id"],
            target_id=row["target_id"],
            amount=row["amount"],
            description=row["description"],
            attachment_url=row["attachment_url"],
            snapshot_n=row["snapshot_n"],
            threshold_t=row["threshold_t"],
            deadline_at=row["deadline_at"],
            status=row["status"],
            reminder_sent=row["reminder_sent"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def fetch_snapshot(
        self,
        connection: asyncpg.Connection,
        *,
        proposal_id: UUID,
    ) -> Sequence[int]:
        rows = await connection.fetch(
            f"SELECT member_id FROM {self._schema}.proposal_snapshots WHERE proposal_id=$1",
            proposal_id,
        )
        return [int(r["member_id"]) for r in rows]

    async def count_active_by_guild(self, connection: asyncpg.Connection, *, guild_id: int) -> int:
        val = await connection.fetchval(
            f"SELECT COUNT(*) FROM {self._schema}.proposals WHERE guild_id=$1 AND status='進行中'",
            guild_id,
        )
        return int(val or 0)

    async def cancel_proposal(self, connection: asyncpg.Connection, *, proposal_id: UUID) -> bool:
        sql = f"""
            UPDATE {self._schema}.proposals
            SET status='已撤案', updated_at=timezone('utc', now())
            WHERE proposal_id=$1 AND status='進行中'
        """
        result = cast(str, await connection.execute(sql, proposal_id))
        return result.upper().startswith("UPDATE 1")

    async def mark_status(
        self,
        connection: asyncpg.Connection,
        *,
        proposal_id: UUID,
        status: str,
        execution_tx_id: UUID | None = None,
        execution_error: str | None = None,
    ) -> None:
        sql = f"""
            UPDATE {self._schema}.proposals
            SET status=$2,
                execution_tx_id=$3,
                execution_error=$4,
                updated_at=timezone('utc', now())
            WHERE proposal_id=$1
        """
        await connection.execute(sql, proposal_id, status, execution_tx_id, execution_error)

    # --- Voting ---
    async def upsert_vote(
        self,
        connection: asyncpg.Connection,
        *,
        proposal_id: UUID,
        voter_id: int,
        choice: str,
    ) -> None:
        sql = f"""
            INSERT INTO {self._schema}.votes (proposal_id, voter_id, choice)
            VALUES ($1,$2,$3)
            ON CONFLICT (proposal_id, voter_id)
            DO UPDATE SET choice=EXCLUDED.choice, updated_at=timezone('utc', now())
        """
        await connection.execute(sql, proposal_id, voter_id, choice)

    async def fetch_tally(self, connection: asyncpg.Connection, *, proposal_id: UUID) -> Tally:
        sql = f"""
            SELECT choice, COUNT(*) AS c
            FROM {self._schema}.votes
            WHERE proposal_id=$1
            GROUP BY choice
        """
        rows = await connection.fetch(sql, proposal_id)
        counts: dict[str, int] = {"approve": 0, "reject": 0, "abstain": 0}
        typed_rows = cast(Sequence[Mapping[str, Any]], rows)
        for r in typed_rows:
            choice_val = r["choice"]
            key = choice_val if isinstance(choice_val, str) else str(choice_val)
            counts[key] = int(r["c"])
        total = counts["approve"] + counts["reject"] + counts["abstain"]
        return Tally(
            approve=counts["approve"],
            reject=counts["reject"],
            abstain=counts["abstain"],
            total_voted=total,
        )

    async def fetch_votes_detail(
        self, connection: asyncpg.Connection, *, proposal_id: UUID
    ) -> Sequence[tuple[int, str]]:
        rows = await connection.fetch(
            (
                f"SELECT voter_id, choice FROM {self._schema}.votes "
                "WHERE proposal_id=$1 ORDER BY updated_at"
            ),
            proposal_id,
        )
        return [(int(r["voter_id"]), str(r["choice"])) for r in rows]

    # --- Queries for scheduler ---
    async def list_due_proposals(self, connection: asyncpg.Connection) -> Sequence[Proposal]:
        sql = f"""
            SELECT proposal_id, guild_id, proposer_id, target_id, amount, description,
                   attachment_url, snapshot_n, threshold_t, deadline_at, status,
                   reminder_sent, created_at, updated_at
            FROM {self._schema}.proposals
            WHERE status='進行中' AND deadline_at <= timezone('utc', now())
        """
        rows = await connection.fetch(sql)
        return [
            Proposal(
                proposal_id=r["proposal_id"],
                guild_id=r["guild_id"],
                proposer_id=r["proposer_id"],
                target_id=r["target_id"],
                amount=r["amount"],
                description=r["description"],
                attachment_url=r["attachment_url"],
                snapshot_n=r["snapshot_n"],
                threshold_t=r["threshold_t"],
                deadline_at=r["deadline_at"],
                status=r["status"],
                reminder_sent=r["reminder_sent"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    async def list_reminder_candidates(self, connection: asyncpg.Connection) -> Sequence[Proposal]:
        sql = f"""
            SELECT proposal_id, guild_id, proposer_id, target_id, amount, description,
                   attachment_url, snapshot_n, threshold_t, deadline_at, status,
                   reminder_sent, created_at, updated_at
            FROM {self._schema}.proposals
            WHERE status='進行中'
              AND reminder_sent = false
              AND deadline_at - interval '24 hours' <= timezone('utc', now())
        """
        rows = await connection.fetch(sql)
        return [
            Proposal(
                proposal_id=r["proposal_id"],
                guild_id=r["guild_id"],
                proposer_id=r["proposer_id"],
                target_id=r["target_id"],
                amount=r["amount"],
                description=r["description"],
                attachment_url=r["attachment_url"],
                snapshot_n=r["snapshot_n"],
                threshold_t=r["threshold_t"],
                deadline_at=r["deadline_at"],
                status=r["status"],
                reminder_sent=r["reminder_sent"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    async def list_active_proposals(self, connection: asyncpg.Connection) -> Sequence[Proposal]:
        sql = f"""
            SELECT proposal_id, guild_id, proposer_id, target_id, amount, description,
                   attachment_url, snapshot_n, threshold_t, deadline_at, status,
                   reminder_sent, created_at, updated_at
            FROM {self._schema}.proposals
            WHERE status='進行中'
            ORDER BY created_at
        """
        rows = await connection.fetch(sql)
        return [
            Proposal(
                proposal_id=r["proposal_id"],
                guild_id=r["guild_id"],
                proposer_id=r["proposer_id"],
                target_id=r["target_id"],
                amount=r["amount"],
                description=r["description"],
                attachment_url=r["attachment_url"],
                snapshot_n=r["snapshot_n"],
                threshold_t=r["threshold_t"],
                deadline_at=r["deadline_at"],
                status=r["status"],
                reminder_sent=r["reminder_sent"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    async def mark_reminded(self, connection: asyncpg.Connection, *, proposal_id: UUID) -> None:
        await connection.execute(
            (
                f"UPDATE {self._schema}.proposals SET reminder_sent = true, "
                "updated_at=timezone('utc', now()) WHERE proposal_id=$1"
            ),
            proposal_id,
        )

    # --- Export ---
    async def export_interval(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, object]]:
        # 使用兩個 LATERAL 子查詢避免 votes × snapshot 交叉乘積重複
        sql = f"""
            SELECT p.proposal_id, p.guild_id, p.proposer_id, p.target_id, p.amount, p.description,
                   p.attachment_url, p.snapshot_n, p.threshold_t, p.deadline_at, p.status,
                   p.execution_tx_id, p.execution_error, p.created_at, p.updated_at,
                   COALESCE(v.votes, '[]'::json) AS votes,
                   COALESCE(s.snapshot, '[]'::json) AS snapshot
            FROM {self._schema}.proposals p
            LEFT JOIN LATERAL (
                SELECT json_agg(
                           json_build_object(
                               'voter_id', v.voter_id,
                               'choice', v.choice,
                               'created_at', v.created_at,
                               'updated_at', v.updated_at
                           )
                           ORDER BY v.updated_at
                       ) AS votes
                FROM {self._schema}.votes v
                WHERE v.proposal_id = p.proposal_id
            ) v ON TRUE
            LEFT JOIN LATERAL (
                SELECT json_agg(ps.member_id) AS snapshot
                FROM {self._schema}.proposal_snapshots ps
                WHERE ps.proposal_id = p.proposal_id
            ) s ON TRUE
            WHERE p.guild_id=$1 AND p.created_at >= $2 AND p.created_at < $3
            ORDER BY p.created_at
        """
        rows = await connection.fetch(sql, guild_id, start, end)
        return [dict(r) for r in rows]


__all__ = [
    "CouncilConfig",
    "CouncilGovernanceGateway",
    "Proposal",
    "Tally",
]
