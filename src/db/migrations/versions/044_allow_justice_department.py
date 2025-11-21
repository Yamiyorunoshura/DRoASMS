"""Allow justice department in governance department enums.

Revision ID: 044_allow_justice_department
Revises: 043_add_charge_actions
Create Date: 2025-11-21 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

# 注意：revision ID 長度必須在 alembic_version.version_num 欄位限制（目前為 VARCHAR(32)）以內
revision = "044_allow_justice_department"
down_revision = "043_add_charge_actions"
branch_labels = None
depends_on = None


# 將「法務部 / justice_department」加入治理層部門可接受值
DEPARTMENT_VALUES_WITH_JUSTICE = (
    # 現有中文部門
    "'內政部'",
    "'財政部'",
    "'國土安全部'",
    "'中央銀行'",
    "'法務部'",
    # 現有英文/代碼部門（與 032_relax_governance_constraints 一致）
    "'internal_affairs'",
    "'finance'",
    "'security'",
    "'central_bank'",
    "'justice_department'",
)

DEPARTMENT_VALUES_PREVIOUS = (
    # 032_relax_governance_constraints 中既有值
    "'內政部'",
    "'財政部'",
    "'國土安全部'",
    "'中央銀行'",
    "'internal_affairs'",
    "'finance'",
    "'security'",
    "'central_bank'",
)


def upgrade() -> None:
    schema = "governance"

    # department_configs.department
    op.drop_constraint(
        "ck_governance_department_configs_department",
        "department_configs",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_department_configs_department",
        "department_configs",
        f"department IN ({', '.join(DEPARTMENT_VALUES_WITH_JUSTICE)})",
        schema=schema,
    )

    # government_accounts.department
    op.drop_constraint(
        "ck_governance_government_accounts_department",
        "government_accounts",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_government_accounts_department",
        "government_accounts",
        f"department IN ({', '.join(DEPARTMENT_VALUES_WITH_JUSTICE)})",
        schema=schema,
    )

    # interdepartment_transfers.from_department / to_department
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
        f"from_department IN ({', '.join(DEPARTMENT_VALUES_WITH_JUSTICE)})",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_governance_interdepartment_transfers_to_department",
        "interdepartment_transfers",
        f"to_department IN ({', '.join(DEPARTMENT_VALUES_WITH_JUSTICE)})",
        schema=schema,
    )


def downgrade() -> None:
    schema = "governance"

    # interdepartment_transfers 回復為僅 4 個核心部門＋英文別名
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
        f"from_department IN ({', '.join(DEPARTMENT_VALUES_PREVIOUS)})",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_governance_interdepartment_transfers_to_department",
        "interdepartment_transfers",
        f"to_department IN ({', '.join(DEPARTMENT_VALUES_PREVIOUS)})",
        schema=schema,
    )

    # government_accounts.department
    op.drop_constraint(
        "ck_governance_government_accounts_department",
        "government_accounts",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_government_accounts_department",
        "government_accounts",
        f"department IN ({', '.join(DEPARTMENT_VALUES_PREVIOUS)})",
        schema=schema,
    )

    # department_configs.department
    op.drop_constraint(
        "ck_governance_department_configs_department",
        "department_configs",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_department_configs_department",
        "department_configs",
        f"department IN ({', '.join(DEPARTMENT_VALUES_PREVIOUS)})",
        schema=schema,
    )
