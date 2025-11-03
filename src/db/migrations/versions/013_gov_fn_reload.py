"""Reload council functions to apply column qualification fixes.

Revision ID: 013_gov_fn_reload
Down Revision: 012_gov_fn_fix
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "013_gov_fn_reload"
down_revision = "012_gov_fn_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("governance/fn_council.sql"))


def downgrade() -> None:
    # No-op; older definition will be restored by downgrading to previous revision.
    pass


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
