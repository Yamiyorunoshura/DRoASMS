"""Allow council & assembly as transfer targets.

Revision ID: 052_allow_council_targets
Revises: 051_fix_company_account_overflow
Create Date: 2025-11-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "052_allow_council_targets"
down_revision = "051_fix_company_account_overflow"
branch_labels = None
depends_on = None


# 允許作為政府帳戶/跨部門轉帳紀錄的機構名稱（含中英文與司法部門）
INSTITUTION_VALUES = (
    "'內政部'",
    "'財政部'",
    "'國土安全部'",
    "'中央銀行'",
    "'法務部'",
    "'常任理事會'",
    "'最高人民會議'",
    "'國務院'",
    "'internal_affairs'",
    "'finance'",
    "'security'",
    "'central_bank'",
    "'justice_department'",
    "'permanent_council'",
    "'supreme_assembly'",
    "'state_council'",
)

# 回退時使用（等同 044_allow_justice_department 的集合）
DEPARTMENT_VALUES_WITH_JUSTICE = (
    "'內政部'",
    "'財政部'",
    "'國土安全部'",
    "'中央銀行'",
    "'法務部'",
    "'internal_affairs'",
    "'finance'",
    "'security'",
    "'central_bank'",
    "'justice_department'",
)


def upgrade() -> None:
    schema = "governance"

    # government_accounts.department 允許常任理事會/最高人民會議/國務院
    op.drop_constraint(
        "ck_governance_government_accounts_department",
        "government_accounts",
        schema=schema,
        type_="check",
    )
    op.create_check_constraint(
        "ck_governance_government_accounts_department",
        "government_accounts",
        f"department IN ({', '.join(INSTITUTION_VALUES)})",
        schema=schema,
    )

    # interdepartment_transfers.from_department / to_department 允許新的政府機構
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
        f"from_department IN ({', '.join(INSTITUTION_VALUES)})",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_governance_interdepartment_transfers_to_department",
        "interdepartment_transfers",
        f"to_department IN ({', '.join(INSTITUTION_VALUES)})",
        schema=schema,
    )


def downgrade() -> None:
    schema = "governance"

    # 還原 interdepartment_transfers 部門集合
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
        f"from_department IN ({', '.join(DEPARTMENT_VALUES_WITH_JUSTICE)})",
        schema=schema,
    )
    op.create_check_constraint(
        "ck_governance_interdepartment_transfers_to_department",
        "interdepartment_transfers",
        f"to_department IN ({', '.join(DEPARTMENT_VALUES_WITH_JUSTICE)})",
        schema=schema,
    )

    # 還原 government_accounts 部門集合
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
