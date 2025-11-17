"""Add charge / revoke_charge actions to identity action enum.

Revision ID: 043_add_charge_actions_to_identity_records
Revises: 042_add_justice_department_suspects
Create Date: 2025-11-17 00:00:00.000000
"""

from alembic import op

revision = "043_add_charge_actions_to_identity_records"
down_revision = "042_add_justice_department_suspects"
branch_labels = None
depends_on = None


IDENTITY_ACTIONS_WITH_CHARGES = (
    # Existing Chinese values
    "'移除公民身分'",
    "'標記疑犯'",
    "'移除疑犯標記'",
    "'逮捕'",
    # Existing English values
    "'register'",
    "'verify'",
    "'update'",
    "'delete'",
    "'suspend'",
    "'arrest'",
    # New additions for justice flows
    "'起訴嫌犯'",
    "'撤銷起訴'",
)

IDENTITY_ACTIONS_PREVIOUS = (
    # Previous set from 039_add_arrest_action
    "'移除公民身分'",
    "'標記疑犯'",
    "'移除疑犯標記'",
    # Existing English values
    "'register'",
    "'verify'",
    "'update'",
    "'delete'",
    "'suspend'",
    # Arrest actions
    "'逮捕'",
    "'arrest'",
)


def upgrade() -> None:
    schema = "governance"
    op.drop_constraint(
        "ck_governance_identity_records_action",
        "identity_records",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_identity_records_action",
        "identity_records",
        f"action IN ({', '.join(IDENTITY_ACTIONS_WITH_CHARGES)})",
        schema=schema,
    )


def downgrade() -> None:
    schema = "governance"
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
