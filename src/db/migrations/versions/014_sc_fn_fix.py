"""Reload state council functions to fix fn_get_state_council_config ambiguity.

Revision ID: 014_sc_fn_fix
Down Revision: 013_gov_fn_reload
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "014_sc_fn_fix"
down_revision = "013_gov_fn_reload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("governance/fn_state_council.sql"))


def downgrade() -> None:
    # No-op; older definition will be restored by downgrading to previous revision.
    pass


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
