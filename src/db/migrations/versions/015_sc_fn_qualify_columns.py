"""Reload state council functions with fully-qualified columns.

Revision ID: 015_sc_fn_qualify_columns
Down Revision: 014_sc_fn_fix
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "015_sc_fn_qualify_columns"
down_revision = "014_sc_fn_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("governance/fn_state_council.sql"))


def downgrade() -> None:
    # No-op; rolling back to 014 will restore the previous definition.
    pass


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
