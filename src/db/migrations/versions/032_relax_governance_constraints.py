"""Allow english governance enum values.

Revision ID: 032_relax_governance_constraints
Revises: 031_add_currency_configuration
Create Date: 2025-11-07 00:00:00.000000
"""

from alembic import op

revision = "032_relax_governance_constraints"
down_revision = "031_add_currency_configuration"
branch_labels = None
depends_on = None


DEPARTMENT_VALUES = (
    "'內政部'",
    "'財政部'",
    "'國土安全部'",
    "'中央銀行'",
    "'internal_affairs'",
    "'finance'",
    "'security'",
    "'central_bank'",
)

WELFARE_TYPES = (
    "'定期福利'",
    "'特殊福利'",
    "'monthly'",
    "'one-time'",
    "'emergency'",
    "'bonus'",
)

TAX_TYPES = (
    "'所得稅'",
    "'資本利得稅'",
    "'income'",
    "'property'",
    "'sales'",
    "'luxury'",
    "'exempt'",
)

IDENTITY_ACTIONS = (
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

    op.drop_constraint(
        "ck_governance_department_configs_department",
        "department_configs",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_department_configs_department",
        "department_configs",
        f"department IN ({', '.join(DEPARTMENT_VALUES)})",
        schema=schema,
    )

    op.drop_constraint(
        "ck_governance_government_accounts_department",
        "government_accounts",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_government_accounts_department",
        "government_accounts",
        f"department IN ({', '.join(DEPARTMENT_VALUES)})",
        schema=schema,
    )

    op.drop_constraint(
        "ck_governance_welfare_disbursements_type",
        "welfare_disbursements",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_welfare_disbursements_type",
        "welfare_disbursements",
        f"disbursement_type IN ({', '.join(WELFARE_TYPES)})",
        schema=schema,
    )

    op.drop_constraint(
        "ck_governance_tax_records_type",
        "tax_records",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_tax_records_type",
        "tax_records",
        f"tax_type IN ({', '.join(TAX_TYPES)})",
        schema=schema,
    )

    op.drop_constraint(
        "ck_governance_identity_records_action",
        "identity_records",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_identity_records_action",
        "identity_records",
        f"action IN ({', '.join(IDENTITY_ACTIONS)})",
        schema=schema,
    )

    op.drop_constraint(
        "ck_governance_interdepartment_transfers_from_department",
        "interdepartment_transfers",
        schema=schema,
        type_="check",
    )
    op.drop_constraint(
        "ck_governance_interdepartment_transfers_to_department",
        "interdepartment_transfers",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_interdepartment_transfers_from_department",
        "interdepartment_transfers",
        f"from_department IN ({', '.join(DEPARTMENT_VALUES)})",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_governance_interdepartment_transfers_to_department",
        "interdepartment_transfers",
        f"to_department IN ({', '.join(DEPARTMENT_VALUES)})",
        schema=schema,
    )


def downgrade() -> None:
    schema = "governance"

    op.drop_constraint(
        "ck_governance_interdepartment_transfers_to_department",
        "interdepartment_transfers",
        schema=schema,
        type_="check",
    )
    op.drop_constraint(
        "ck_governance_interdepartment_transfers_from_department",
        "interdepartment_transfers",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_interdepartment_transfers_from_department",
        "interdepartment_transfers",
        "from_department IN ('內政部', '財政部', '國土安全部', '中央銀行')",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_governance_interdepartment_transfers_to_department",
        "interdepartment_transfers",
        "to_department IN ('內政部', '財政部', '國土安全部', '中央銀行')",
        schema=schema,
    )

    op.drop_constraint(
        "ck_governance_identity_records_action",
        "identity_records",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_identity_records_action",
        "identity_records",
        "action IN ('移除公民身分', '標記疑犯', '移除疑犯標記')",
        schema=schema,
    )

    op.drop_constraint(
        "ck_governance_tax_records_type",
        "tax_records",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_tax_records_type",
        "tax_records",
        "tax_type IN ('所得稅', '資本利得稅')",
        schema=schema,
    )

    op.drop_constraint(
        "ck_governance_welfare_disbursements_type",
        "welfare_disbursements",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_welfare_disbursements_type",
        "welfare_disbursements",
        "disbursement_type IN ('定期福利', '特殊福利')",
        schema=schema,
    )

    op.drop_constraint(
        "ck_governance_government_accounts_department",
        "government_accounts",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_government_accounts_department",
        "government_accounts",
        "department IN ('內政部', '財政部', '國土安全部', '中央銀行')",
        schema=schema,
    )

    op.drop_constraint(
        "ck_governance_department_configs_department",
        "department_configs",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_department_configs_department",
        "department_configs",
        "department IN ('內政部', '財政部', '國土安全部', '中央銀行')",
        schema=schema,
    )
