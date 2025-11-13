from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, SupportsInt, cast
from uuid import UUID

from src.infra.types.db import ConnectionProtocol

# --- Data Models ---


@dataclass(frozen=True, slots=True)
class CouncilConfig:
    guild_id: int
    council_role_id: int  # 保持向下相容，主要使用 council_role_ids
    council_account_member_id: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CouncilRoleConfig:
    """常任理事身分組配置"""

    guild_id: int
    role_id: int
    created_at: datetime
    updated_at: datetime
    id: int | None = None


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
    target_department_id: str | None = None


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
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        council_role_id: int,
        council_account_member_id: int,
    ) -> CouncilConfig:
        sql = f"SELECT * FROM {self._schema}.fn_upsert_council_config($1,$2,$3)"
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
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> CouncilConfig | None:
        sql = f"SELECT * FROM {self._schema}.fn_get_council_config($1)"
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

    # --- Council Role Management ---
    async def get_council_role_ids(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> Sequence[int]:
        """獲取所有常任理事身分組 ID"""
        sql = f"SELECT {self._schema}.fn_get_council_role_ids($1)"
        result = await connection.fetchval(sql, guild_id)
        if result is None:
            return []
        if isinstance(result, list):
            typed_result = cast(list[SupportsInt], result)
            return [int(role_id) for role_id in typed_result]
        return []

    async def add_council_role(
        self, connection: ConnectionProtocol, *, guild_id: int, role_id: int
    ) -> bool:
        """添加常任理事身分組"""
        sql = f"SELECT {self._schema}.fn_add_council_role($1, $2)"
        result = await connection.fetchval(sql, guild_id, role_id)
        return bool(result)

    async def remove_council_role(
        self, connection: ConnectionProtocol, *, guild_id: int, role_id: int
    ) -> bool:
        """移除常任理事身分組"""
        sql = f"SELECT {self._schema}.fn_remove_council_role($1, $2)"
        result = await connection.fetchval(sql, guild_id, role_id)
        return bool(result)

    async def list_council_role_configs(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> Sequence[CouncilRoleConfig]:
        """列出所有常任理事身分組配置（含舊版單一身分組）。"""
        configs: list[CouncilRoleConfig] = []

        config = await self.fetch_config(connection, guild_id=guild_id)
        if config and config.council_role_id:
            configs.append(
                CouncilRoleConfig(
                    guild_id=guild_id,
                    role_id=config.council_role_id,
                    created_at=config.created_at,
                    updated_at=config.updated_at,
                )
            )

        rows = await connection.fetch(
            f"""
                SELECT id, guild_id, role_id, created_at, updated_at
                FROM {self._schema}.council_role_ids
                WHERE guild_id = $1
                ORDER BY created_at
            """,
            guild_id,
        )

        for row in rows:
            configs.append(
                CouncilRoleConfig(
                    id=row["id"],
                    guild_id=row["guild_id"],
                    role_id=row["role_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )

        return configs

    # --- Proposals ---
    async def create_proposal(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        proposer_id: int,
        target_id: int,
        amount: int,
        description: str | None,
        attachment_url: str | None,
        snapshot_member_ids: Sequence[int],
        deadline_hours: int = 72,
        target_department_id: str | None = None,
    ) -> Proposal:
        # 票數門檻與截止時間由資料庫端函式計算並回傳，這裡不重複計算。

        async with connection.transaction():
            sql = f"SELECT * FROM {self._schema}.fn_create_proposal($1,$2,$3,$4,$5,$6,$7,$8,$9)"
            row = await connection.fetchrow(
                sql,
                guild_id,
                proposer_id,
                target_id,
                amount,
                description,
                attachment_url,
                list(dict.fromkeys(int(x) for x in snapshot_member_ids)),
                deadline_hours,
                target_department_id,
            )
            assert row is not None

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
            target_department_id=row.get("target_department_id"),
        )

    async def fetch_proposal(
        self,
        connection: ConnectionProtocol,
        *,
        proposal_id: UUID,
    ) -> Proposal | None:
        sql = f"SELECT * FROM {self._schema}.fn_get_proposal($1)"
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
            target_department_id=row.get("target_department_id"),
        )

    async def fetch_snapshot(
        self,
        connection: ConnectionProtocol,
        *,
        proposal_id: UUID,
    ) -> Sequence[int]:
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.fn_get_snapshot_members($1)", proposal_id
        )
        return [int(r["fn_get_snapshot_members"]) for r in rows]

    async def count_active_by_guild(self, connection: ConnectionProtocol, *, guild_id: int) -> int:
        val = await connection.fetchval(
            f"SELECT {self._schema}.fn_count_active_proposals($1)", guild_id
        )
        return int(val or 0)

    async def cancel_proposal(self, connection: ConnectionProtocol, *, proposal_id: UUID) -> bool:
        ok = await connection.fetchval(
            f"SELECT {self._schema}.fn_attempt_cancel_proposal($1)", proposal_id
        )
        return bool(ok)

    async def mark_status(
        self,
        connection: ConnectionProtocol,
        *,
        proposal_id: UUID,
        status: str,
        execution_tx_id: UUID | None = None,
        execution_error: str | None = None,
    ) -> None:
        await connection.execute(
            f"SELECT {self._schema}.fn_mark_status($1,$2,$3,$4)",
            proposal_id,
            status,
            execution_tx_id,
            execution_error,
        )

    # --- Voting ---
    async def upsert_vote(
        self,
        connection: ConnectionProtocol,
        *,
        proposal_id: UUID,
        voter_id: int,
        choice: str,
    ) -> None:
        await connection.execute(
            f"SELECT {self._schema}.fn_upsert_vote($1,$2,$3)", proposal_id, voter_id, choice
        )

    async def fetch_tally(self, connection: ConnectionProtocol, *, proposal_id: UUID) -> Tally:
        row = await connection.fetchrow(
            f"SELECT * FROM {self._schema}.fn_fetch_tally($1)", proposal_id
        )
        assert row is not None
        return Tally(
            approve=int(row["approve"]),
            reject=int(row["reject"]),
            abstain=int(row["abstain"]),
            total_voted=int(row["total_voted"]),
        )

    async def fetch_votes_detail(
        self, connection: ConnectionProtocol, *, proposal_id: UUID
    ) -> Sequence[tuple[int, str]]:
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.fn_list_votes_detail($1)", proposal_id
        )
        return [(int(r["voter_id"]), str(r["choice"])) for r in rows]

    # --- Queries for scheduler ---
    async def list_due_proposals(self, connection: ConnectionProtocol) -> Sequence[Proposal]:
        rows = await connection.fetch(f"SELECT * FROM {self._schema}.fn_list_due_proposals()")
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

    async def list_reminder_candidates(self, connection: ConnectionProtocol) -> Sequence[Proposal]:
        rows = await connection.fetch(f"SELECT * FROM {self._schema}.fn_list_reminder_candidates()")
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

    async def list_active_proposals(self, connection: ConnectionProtocol) -> Sequence[Proposal]:
        rows = await connection.fetch(f"SELECT * FROM {self._schema}.fn_list_active_proposals()")
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

    async def mark_reminded(self, connection: ConnectionProtocol, *, proposal_id: UUID) -> None:
        await connection.execute(f"SELECT {self._schema}.fn_mark_reminded($1)", proposal_id)

    # --- Export ---
    async def export_interval(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, object]]:
        # 使用兩個 LATERAL 子查詢避免 votes × snapshot 交叉乘積重複
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.fn_export_interval($1,$2,$3)",
            guild_id,
            start,
            end,
        )
        return [dict(r) for r in rows]

    async def list_unvoted_members(
        self, connection: ConnectionProtocol, *, proposal_id: UUID
    ) -> Sequence[int]:
        rows = await connection.fetch(
            f"SELECT * FROM {self._schema}.fn_list_unvoted_members($1)", proposal_id
        )
        return [int(r["fn_list_unvoted_members"]) for r in rows]


__all__ = [
    "CouncilConfig",
    "CouncilRoleConfig",
    "CouncilGovernanceGateway",
    "Proposal",
    "Tally",
]
