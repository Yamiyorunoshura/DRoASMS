"""Reload governance SQL functions (round 3) to fix ambiguous column refs.

Revision ID: 012_governance_functions_round3
Down Revision: 011_governance_functions_round2
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "012_governance_functions_round3"
down_revision = "011_governance_functions_round2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reinstall/refresh governance function definitions
    op.execute(_load_sql("governance/fn_council.sql"))
    op.execute(_load_sql("governance/fn_state_council.sql"))


def downgrade() -> None:
    # Drop only the functions we updated; defer full cleanup to previous revisions
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_upsert_council_config(bigint, bigint, bigint)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_council_config(bigint)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_create_proposal("
        "bigint, bigint, bigint, bigint, text, text, bigint[], integer)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_proposal(uuid)")


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
