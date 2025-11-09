"""Add '逮捕' / 'arrest' to identity action enum.

Revision ID: 039_add_arrest_action
Revises: 038_backcompat_upsert_sc_wrapper
Create Date: 2025-11-09 00:00:00.000000
"""

from alembic import op

revision = "039_add_arrest_action"
down_revision = "038_backcompat_upsert_sc_wrapper"
branch_labels = None
depends_on = None


IDENTITY_ACTIONS_WITH_ARREST = (
    # Existing Chinese values
    "'移除公民身分'",
    "'標記疑犯'",
    "'移除疑犯標記'",
    # Existing English values
    "'register'",
    "'verify'",
    "'update'",
    "'delete'",
    "'suspend'",
    # New additions
    "'逮捕'",
    "'arrest'",
)

IDENTITY_ACTIONS_PREVIOUS = (
    # Previous set from 032_relax_governance_constraints
    "'移除公民身分'",
    "'標記疑犯'",
    "'移除疑犯標記'",
    "'register'",
    "'verify'",
    "'update'",
    "'delete'",
    "'suspend'",
)


def upgrade() -> None:
    schema = "governance"
    # Replace check constraint to include arrest actions
    op.drop_constraint(
        "ck_governance_identity_records_action",
        "identity_records",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_identity_records_action",
        "identity_records",
        f"action IN ({', '.join(IDENTITY_ACTIONS_WITH_ARREST)})",
        schema=schema,
    )


def downgrade() -> None:
    schema = "governance"
    # Revert to previous constraint (without arrest)
    op.drop_constraint(
        "ck_governance_identity_records_action",
        "identity_records",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_identity_records_action",
        "identity_records",
        f"action IN ({', '.join(IDENTITY_ACTIONS_PREVIOUS)})",
        schema=schema,
    )
