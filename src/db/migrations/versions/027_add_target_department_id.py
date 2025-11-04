"""Add target_department_id to governance.proposals.

Revision adds:
- target_department_id column (TEXT, nullable) to governance.proposals
- Updated fn_create_proposal to support p_target_department_id parameter
- Updated fn_get_proposal and related functions to return target_department_id

"""

from __future__ import annotations

from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = "027_add_target_department_id"
down_revision = "026_transfer_limit_guc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add target_department_id column to proposals table
    op.add_column(
        "proposals",
        sa.Column("target_department_id", sa.Text(), nullable=True),
        schema="governance",
    )

    # Reload governance functions to support target_department_id
    # 注意：PostgreSQL 不允許以 CREATE OR REPLACE 變更函式的回傳型別（包含 RETURNS TABLE 欄位）。
    # 因本次調整新增 target_department_id 至多個 RETURNS TABLE，因此需先 DROP 舊版函式再重建。
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_create_proposal("
        "bigint, bigint, bigint, bigint, text, text, bigint[], integer)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_proposal(uuid)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_due_proposals()")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_reminder_candidates()")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_active_proposals()")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_export_interval(bigint, timestamptz, timestamptz)"
    )
    op.execute(_load_sql("governance/fn_council.sql"))


def downgrade() -> None:
    # Reload governance functions without target_department_id support
    # Note: This assumes the previous version of fn_council.sql doesn't use target_department_id
    op.execute(_load_sql("governance/fn_council.sql"))

    # Remove target_department_id column
    op.drop_column("proposals", "target_department_id", schema="governance")


def _load_sql(filename: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / filename
    return sql_path.read_text(encoding="utf-8")
