"""Install Business License SQL functions.

Revision ID: 047_business_license_functions
Revises: 046_add_business_licenses
Create Date: 2025-11-25 10:00:00.000000
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "047_business_license_functions"
down_revision = "046_add_business_licenses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("governance/fn_business_licenses.sql"))


def downgrade() -> None:
    # Drop functions (defensive: IF EXISTS)
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_issue_business_license(bigint, bigint, text, bigint, timestamptz)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_revoke_business_license(uuid, bigint, text)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_business_license(uuid)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_list_business_licenses(bigint, text, text, integer, integer)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_user_licenses(bigint, bigint)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_check_active_license(bigint, bigint, text)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_expire_business_licenses()")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_count_business_licenses_by_status(bigint)")


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
