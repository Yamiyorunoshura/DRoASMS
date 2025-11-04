"""Cast total_voted to int in fn_fetch_tally to match RETURNS TABLE.

Fixes asyncpg DatatypeMismatchError: SUM(int) yields bigint in Postgres.

Revision ID: 029_fix_tally_cast
Down Revision: 028_fix_guild_id_ambiguity
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "029_fix_tally_cast"
down_revision = "028_fix_guild_id_ambiguity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reload council governance functions after patching SQL body
    op.execute(_load_sql("governance/fn_council.sql"))


def downgrade() -> None:
    # Safe to re-run the same SQL since signatures unchanged; this acts as a no-op rollback.
    op.execute(_load_sql("governance/fn_council.sql"))


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
