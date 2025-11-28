"""Add company management SQL functions.

Revision adds:
- governance.fn_create_company
- governance.fn_get_company
- governance.fn_get_company_by_account
- governance.fn_list_user_companies
- governance.fn_list_guild_companies
- governance.fn_get_available_licenses_for_company
- governance.fn_check_company_ownership
- governance.fn_check_company_license_valid
- governance.fn_derive_company_account_id

"""

from __future__ import annotations

from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "050_company_functions"
down_revision = "049_add_companies"
branch_labels = None
depends_on = None


def _load_sql(filename: str) -> str:
    """Load SQL file from the functions directory."""
    sql_path = Path(__file__).parent.parent.parent / "functions" / "governance" / filename
    return sql_path.read_text(encoding="utf-8")


def upgrade() -> None:
    op.execute(_load_sql("fn_companies.sql"))


def downgrade() -> None:
    # Drop all company functions
    op.execute("DROP FUNCTION IF EXISTS governance.fn_derive_company_account_id(bigint, bigint)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_check_company_license_valid(bigint)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_check_company_ownership(bigint, bigint)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_get_available_licenses_for_company(bigint, bigint)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_guild_companies(bigint, int, int)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_user_companies(bigint, bigint)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_company_by_account(bigint)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_company(bigint)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_create_company(bigint, bigint, uuid, varchar, bigint)"
    )
