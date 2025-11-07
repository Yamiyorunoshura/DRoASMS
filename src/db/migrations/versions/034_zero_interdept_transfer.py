"""Allow zero-amount interdepartment transfers.

Revision ID: 034_zero_interdept_transfer
Revises: 033_allow_zero_currency_issuance
Create Date: 2025-11-07 05:16:00.000000
"""

from alembic import op

revision = "034_zero_interdept_transfer"
down_revision = "033_allow_zero_currency_issuance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_governance_interdepartment_transfers_amount_positive",
        "interdepartment_transfers",
        schema="governance",
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_interdepartment_transfers_amount_positive",
        "interdepartment_transfers",
        "amount >= 0",
        schema="governance",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_governance_interdepartment_transfers_amount_positive",
        "interdepartment_transfers",
        schema="governance",
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_interdepartment_transfers_amount_positive",
        "interdepartment_transfers",
        "amount > 0",
        schema="governance",
    )
