"""Fix ambiguous column references in governance functions and reload.

Revision ID: 012_gov_fn_fix
Down Revision: 011_governance_functions_round2
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "012_gov_fn_fix"
down_revision = "011_governance_functions_round2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("governance/fn_council.sql"))
    op.execute(_load_sql("governance/fn_state_council.sql"))


def downgrade() -> None:
    # No-op: newer definitions replaced older ones; roll back to previous
    # migration to drop functions if needed.
    pass


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
