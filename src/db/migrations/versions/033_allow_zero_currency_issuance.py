"""Allow zero-amount currency issuances.

Revision ID: 033_allow_zero_currency_issuance
Revises: 032_relax_governance_constraints
Create Date: 2025-11-07 05:10:00.000000
"""

from alembic import op

revision = "033_allow_zero_currency_issuance"
down_revision = "032_relax_governance_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_governance_currency_issuances_amount_positive",
        "currency_issuances",
        schema="governance",
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_currency_issuances_amount_positive",
        "currency_issuances",
        "amount >= 0",
        schema="governance",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_governance_currency_issuances_amount_positive",
        "currency_issuances",
        schema="governance",
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_currency_issuances_amount_positive",
        "currency_issuances",
        "amount > 0",
        schema="governance",
    )
