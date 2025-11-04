"""Fix ambiguous column refs in fn_create_proposal (qualify guild_id/status).

Also qualifies columns in fn_count_active_proposals for consistency.

Revision ID: 028_fix_guild_id_ambiguity
Down Revision: 027_add_target_department_id
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "028_fix_guild_id_ambiguity"
down_revision = "027_add_target_department_id"
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
