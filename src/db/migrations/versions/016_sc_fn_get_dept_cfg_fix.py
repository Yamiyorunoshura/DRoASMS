"""Reload fn_state_council.sql to fix ambiguity in fn_get_department_config.

Revision ID: 016_sc_fn_get_dept_cfg_fix
Down Revision: 015_sc_fn_qualify_columns
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "016_sc_fn_get_dept_cfg_fix"
down_revision = "015_sc_fn_qualify_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reload consolidated governance functions. This includes fully qualifying
    # columns in fn_get_department_config to avoid PL/pgSQL ambiguous "id" errors.
    op.execute(_load_sql("governance/fn_state_council.sql"))


def downgrade() -> None:
    # No-op; revert to previous revision to restore the old definition if needed.
    pass


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
