"""Install Supreme Assembly SQL functions.

Revision ID: 036_supreme_assembly_functions
Revises: 035_supreme_assembly
Create Date: 2025-11-08 18:06:00.000000
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "036_supreme_assembly_functions"
down_revision = "035_supreme_assembly"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("governance/fn_supreme_assembly.sql"))


def downgrade() -> None:
    # Drop functions (defensive: IF EXISTS)
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_supreme_assembly_config(bigint)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_upsert_supreme_assembly_config(bigint, bigint, bigint)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_is_sa_account(bigint)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_sa_account_id(bigint)")


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
