from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence, SupportsInt, cast
from uuid import UUID

from src.cython_ext.council_governance_models import (
    CouncilConfig,
    CouncilRoleConfig,
    Proposal,
    Tally,
)
from src.infra.result import DatabaseError, async_returns_result
from src.infra.types.db import ConnectionProtocol


def _council_config_from_row(row: Mapping[str, Any]) -> CouncilConfig:
    return CouncilConfig(
        guild_id=int(row["guild_id"]),
        council_role_id=int(row["council_role_id"]),
        council_account_member_id=int(row["council_account_member_id"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _council_role_config_from_row(row: Mapping[str, Any]) -> CouncilRoleConfig:
    return CouncilRoleConfig(
        guild_id=int(row["guild_id"]),
        role_id=int(row["role_id"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        id=cast(int | None, row.get("id")),
    )


def _proposal_from_row(row: Mapping[str, Any]) -> Proposal:
    return Proposal(
        proposal_id=cast(UUID, row["proposal_id"]),
        guild_id=int(row["guild_id"]),
        proposer_id=int(row["proposer_id"]),
        target_id=int(row["target_id"]),
        amount=int(row["amount"]),
        description=cast(str | None, row["description"]),
        attachment_url=cast(str | None, row["attachment_url"]),
        snapshot_n=int(row["snapshot_n"]),
        threshold_t=int(row["threshold_t"]),
        deadline_at=row["deadline_at"],
        status=str(row["status"]),
        reminder_sent=bool(row["reminder_sent"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        target_department_id=cast(str | None, row.get("target_department_id")),
    )


def _tally_from_row(row: Mapping[str, Any]) -> Tally:
    return Tally(
        approve=int(row["approve"]),
        reject=int(row["reject"]),
        abstain=int(row["abstain"]),
        total_voted=int(row["total_voted"]),
    )


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
        return _council_config_from_row(row)

    async def fetch_config(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> CouncilConfig | None:
        sql = f"SELECT * FROM {self._schema}.fn_get_council_config($1)"
        row = await connection.fetchrow(sql, guild_id)
        if row is None:
            return None
        return _council_config_from_row(row)

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
            configs.append(_council_role_config_from_row(row))

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

        return _proposal_from_row(row)

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
        return [int(r["member_id"]) for r in rows]

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
        return _tally_from_row(row)

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
        return [_proposal_from_row(r) for r in rows]

    async def list_reminder_candidates(self, connection: ConnectionProtocol) -> Sequence[Proposal]:
        rows = await connection.fetch(f"SELECT * FROM {self._schema}.fn_list_reminder_candidates()")
        return [_proposal_from_row(r) for r in rows]

    async def list_active_proposals(self, connection: ConnectionProtocol) -> Sequence[Proposal]:
        rows = await connection.fetch(f"SELECT * FROM {self._schema}.fn_list_active_proposals()")
        return [_proposal_from_row(r) for r in rows]

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
        return [int(r["member_id"]) for r in rows]

    # --- Result-based wrapper methods ---
    @async_returns_result(DatabaseError)
    async def fetch_config_result(
        self, connection: ConnectionProtocol, *, guild_id: int
    ) -> CouncilConfig | None:
        """Result-based wrapper for fetch_config."""
        return await self.fetch_config(connection, guild_id=guild_id)

    @async_returns_result(DatabaseError)
    async def upsert_config_result(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        council_role_id: int,
        council_account_member_id: int,
    ) -> CouncilConfig:
        """Result-based wrapper for upsert_config."""
        return await self.upsert_config(
            connection,
            guild_id=guild_id,
            council_role_id=council_role_id,
            council_account_member_id=council_account_member_id,
        )

    @async_returns_result(DatabaseError)
    async def create_proposal_result(
        self,
        connection: ConnectionProtocol,
        *,
        guild_id: int,
        proposer_id: int,
        target_id: int,
        amount: int,
        description: str | None = None,
        attachment_url: str | None = None,
        snapshot_member_ids: Sequence[int],
        deadline_hours: int = 72,
        target_department_id: str | None = None,
    ) -> Proposal:
        """Result-based wrapper for create_proposal."""
        return await self.create_proposal(
            connection,
            guild_id=guild_id,
            proposer_id=proposer_id,
            target_id=target_id,
            amount=amount,
            description=description,
            attachment_url=attachment_url,
            snapshot_member_ids=snapshot_member_ids,
            deadline_hours=deadline_hours,
            target_department_id=target_department_id,
        )

    @async_returns_result(DatabaseError)
    async def fetch_proposal_result(
        self, connection: ConnectionProtocol, *, proposal_id: UUID
    ) -> Proposal | None:
        """Result-based wrapper for fetch_proposal."""
        return await self.fetch_proposal(connection, proposal_id=proposal_id)

    @async_returns_result(DatabaseError)
    async def fetch_tally_result(
        self, connection: ConnectionProtocol, *, proposal_id: UUID
    ) -> Tally:
        """Result-based wrapper for fetch_tally."""
        return await self.fetch_tally(connection, proposal_id=proposal_id)


__all__ = [
    "CouncilConfig",
    "CouncilRoleConfig",
    "CouncilGovernanceGateway",
    "Proposal",
    "Tally",
]
