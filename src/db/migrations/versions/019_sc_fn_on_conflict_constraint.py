"""Reload state council functions to use ON CONFLICT ON CONSTRAINT.

Fixes ambiguous column references caused by RETURNS TABLE OUT params
sharing names with columns used in ON CONFLICT (...).

Revision ID: 019_sc_fn_on_conflict_constraint
Down Revision: 018_sc_fn_currency_issuance_fix
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "019_sc_fn_on_conflict_constraint"
down_revision = "018_sc_fn_currency_issuance_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("governance/fn_state_council.sql"))


def downgrade() -> None:
    # No-op; downgrading to the previous revision restores the older definition.
    pass


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
