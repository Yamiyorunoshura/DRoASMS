"""Merge Alembic heads and reload governance SQL functions (round 4).

This migration merges the two divergent heads produced by earlier
governance function updates:

  - 019_sc_fn_on_conflict_constraint (state council path)
  - 012_governance_functions_round3 (council path)

By merging them, `alembic upgrade head` will once again have a single
linear head. We also reload both consolidated SQL files to ensure the
database has the latest function definitions.

Revision ID: 020_merge_heads
Down Revision: 019_sc_fn_on_conflict_constraint, 012_governance_functions_round3
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "020_merge_heads"
down_revision = (
    "019_sc_fn_on_conflict_constraint",
    "012_governance_functions_round3",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure both sets of governance functions are (re)installed with the
    # most recent definitions.
    op.execute(_load_sql("governance/fn_council.sql"))
    op.execute(_load_sql("governance/fn_state_council.sql"))


def downgrade() -> None:
    # No-op merge point; downgrading will follow back down either branch.
    pass


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
