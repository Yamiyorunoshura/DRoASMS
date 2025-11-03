"""Reload governance SQL functions (council + state council).

Ensures both sets are installed and updates definitions to fix ambiguity
in RETURNS TABLE column references.

Revision ID: 011_governance_functions_round2
Down Revision: 010_governance_functions
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "011_governance_functions_round2"
down_revision = "010_governance_functions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reinstall/refresh governance function definitions
    op.execute(_load_sql("governance/fn_council.sql"))
    op.execute(_load_sql("governance/fn_state_council.sql"))


def downgrade() -> None:
    # Drop functions defined across both SQL files (defensive: IF EXISTS)
    # From fn_council.sql
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_upsert_council_config(bigint, bigint, bigint)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_council_config(bigint)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_create_proposal("
        "bigint, bigint, bigint, bigint, text, text, bigint[], integer)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_proposal(uuid)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_list_proposals(bigint, text, integer, integer)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_cast_vote(uuid, bigint, text)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_count_votes(uuid)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_mark_reminded(uuid)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_update_proposal_status(uuid, text, uuid, text)"
    )
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_due_proposals()")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_reminder_candidates()")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_active_proposals()")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_export_interval(bigint, timestamptz, timestamptz)"
    )

    # From fn_state_council.sql
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_upsert_state_council_config("
        "bigint, bigint, bigint, bigint, bigint, bigint, bigint)"
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
    op.execute("DROP FUNCTION IF EXISTS governance.fn_list_all_department_configs_for_issuance()")


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
