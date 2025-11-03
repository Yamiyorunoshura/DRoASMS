"""Install governance SQL functions (state council, departments, welfare).

Loads consolidated SQL from src/db/functions/governance/fn_state_council.sql
so that application gateway calls (e.g. fn_list_all_department_configs_with_welfare)
are available after schema tables are created.

Revision ID: 010_governance_functions
Down Revision: 009_dept_cfg_unique
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "010_governance_functions"
down_revision = "009_dept_cfg_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Install/replace governance functions used by the bot services
    op.execute(_load_sql("governance/fn_state_council.sql"))


def downgrade() -> None:
    # Drop functions created by fn_state_council.sql (defensive: IF EXISTS)
    # Keep in sync with definitions inside the SQL file.
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_upsert_state_council_config(bigint, bigint, bigint, bigint, bigint, bigint, bigint)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_state_council_config(bigint)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_upsert_department_config("
        "bigint, text, bigint, bigint, integer, bigint, integer, bigint)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_department_configs(bigint)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_department_config(bigint, text)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_upsert_government_account(bigint, bigint, text, bigint)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_government_accounts(bigint)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_update_government_account_balance(bigint, bigint)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_create_welfare_disbursement("
        "bigint, bigint, bigint, text, text)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_list_welfare_disbursements(" "bigint, int, int)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_all_department_configs_with_welfare()")


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
