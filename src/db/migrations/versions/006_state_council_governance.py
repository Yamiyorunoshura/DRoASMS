"""Create state council governance schema for state council, departments, and operations.

Revision adds:
- governance.state_council_config
- governance.department_configs
- governance.government_accounts
- governance.welfare_disbursements
- governance.tax_records
- governance.identity_records
- governance.currency_issuances
- governance.interdepartment_transfers

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "006_state_council_governance"
down_revision = "005_governance_council"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tables in existing governance schema

    # State council config table per guild
    op.create_table(
        "state_council_config",
        sa.Column("guild_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("leader_id", sa.BigInteger(), nullable=False),
        sa.Column("internal_affairs_account_id", sa.BigInteger(), nullable=False),
        sa.Column("finance_account_id", sa.BigInteger(), nullable=False),
        sa.Column("security_account_id", sa.BigInteger(), nullable=False),
        sa.Column("central_bank_account_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        schema="governance",
    )

    # Department configurations
    op.create_table(
        "department_configs",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("department", sa.Text(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=True),
        sa.Column("welfare_amount", sa.BigInteger(), nullable=True, server_default=sa.text("0")),
        sa.Column(
            "welfare_interval_hours", sa.Integer(), nullable=True, server_default=sa.text("24")
        ),
        sa.Column("tax_rate_basis", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("tax_rate_percent", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column(
            "max_issuance_per_month", sa.BigInteger(), nullable=True, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint(
            "department IN ('內政部', '財政部', '國土安全部', '中央銀行')",
            name="ck_governance_department_configs_department",
        ),
        sa.CheckConstraint(
            "welfare_amount >= 0", name="ck_governance_department_configs_welfare_positive"
        ),
        sa.CheckConstraint(
            "welfare_interval_hours > 0", name="ck_governance_department_configs_interval_positive"
        ),
        sa.CheckConstraint(
            "tax_rate_basis >= 0", name="ck_governance_department_configs_tax_basis_positive"
        ),
        sa.CheckConstraint(
            "tax_rate_percent >= 0 AND tax_rate_percent <= 100",
            name="ck_governance_department_configs_tax_percent_range",
        ),
        sa.CheckConstraint(
            "max_issuance_per_month >= 0", name="ck_governance_department_configs_issuance_positive"
        ),
        schema="governance",
    )

    op.create_index(
        "ix_governance_department_configs_guild",
        "department_configs",
        ["guild_id"],
        unique=False,
        schema="governance",
    )

    # Government accounts for each department
    op.create_table(
        "government_accounts",
        sa.Column("account_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("department", sa.Text(), nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint(
            "department IN ('內政部', '財政部', '國土安全部', '中央銀行')",
            name="ck_governance_government_accounts_department",
        ),
        sa.CheckConstraint(
            "balance >= 0", name="ck_governance_government_accounts_balance_non_negative"
        ),
        schema="governance",
    )

    op.create_index(
        "ix_governance_government_accounts_guild",
        "government_accounts",
        ["guild_id"],
        unique=False,
        schema="governance",
    )

    # Welfare disbursement records
    op.create_table(
        "welfare_disbursements",
        sa.Column(
            "disbursement_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("disbursement_type", sa.Text(), nullable=False),
        sa.Column("reference_id", sa.Text(), nullable=True),
        sa.Column(
            "disbursed_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint(
            "amount > 0", name="ck_governance_welfare_disbursements_amount_positive"
        ),
        sa.CheckConstraint(
            "disbursement_type IN ('定期福利', '特殊福利')",
            name="ck_governance_welfare_disbursements_type",
        ),
        schema="governance",
    )

    op.create_index(
        "ix_governance_welfare_disbursements_guild",
        "welfare_disbursements",
        ["guild_id"],
        unique=False,
        schema="governance",
    )

    op.create_index(
        "ix_governance_welfare_disbursements_recipient",
        "welfare_disbursements",
        ["recipient_id"],
        unique=False,
        schema="governance",
    )

    # Tax records
    op.create_table(
        "tax_records",
        sa.Column(
            "tax_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("taxpayer_id", sa.BigInteger(), nullable=False),
        sa.Column("taxable_amount", sa.BigInteger(), nullable=False),
        sa.Column("tax_rate_percent", sa.Integer(), nullable=False),
        sa.Column("tax_amount", sa.BigInteger(), nullable=False),
        sa.Column("tax_type", sa.Text(), nullable=False),
        sa.Column("assessment_period", sa.Text(), nullable=False),
        sa.Column(
            "collected_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint(
            "taxable_amount >= 0", name="ck_governance_tax_records_taxable_positive"
        ),
        sa.CheckConstraint("tax_amount >= 0", name="ck_governance_tax_records_amount_positive"),
        sa.CheckConstraint("tax_rate_percent >= 0", name="ck_governance_tax_records_rate_positive"),
        sa.CheckConstraint(
            "tax_type IN ('所得稅', '資本利得稅')",
            name="ck_governance_tax_records_type",
        ),
        schema="governance",
    )

    op.create_index(
        "ix_governance_tax_records_guild",
        "tax_records",
        ["guild_id"],
        unique=False,
        schema="governance",
    )

    op.create_index(
        "ix_governance_tax_records_taxpayer",
        "tax_records",
        ["taxpayer_id"],
        unique=False,
        schema="governance",
    )

    # Identity management records
    op.create_table(
        "identity_records",
        sa.Column(
            "record_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("performed_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "performed_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint(
            "action IN ('移除公民身分', '標記疑犯', '移除疑犯標記')",
            name="ck_governance_identity_records_action",
        ),
        schema="governance",
    )

    op.create_index(
        "ix_governance_identity_records_guild",
        "identity_records",
        ["guild_id"],
        unique=False,
        schema="governance",
    )

    op.create_index(
        "ix_governance_identity_records_target",
        "identity_records",
        ["target_id"],
        unique=False,
        schema="governance",
    )

    # Currency issuance records
    op.create_table(
        "currency_issuances",
        sa.Column(
            "issuance_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("performed_by", sa.BigInteger(), nullable=False),
        sa.Column("month_period", sa.Text(), nullable=False),
        sa.Column(
            "issued_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint("amount > 0", name="ck_governance_currency_issuances_amount_positive"),
        schema="governance",
    )

    op.create_index(
        "ix_governance_currency_issuances_guild",
        "currency_issuances",
        ["guild_id"],
        unique=False,
        schema="governance",
    )

    op.create_index(
        "ix_governance_currency_issuances_month",
        "currency_issuances",
        ["month_period"],
        unique=False,
        schema="governance",
    )

    # Inter-department transfer records
    op.create_table(
        "interdepartment_transfers",
        sa.Column(
            "transfer_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("from_department", sa.Text(), nullable=False),
        sa.Column("to_department", sa.Text(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("performed_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "transferred_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint(
            "amount > 0", name="ck_governance_interdepartment_transfers_amount_positive"
        ),
        sa.CheckConstraint(
            "from_department IN ('內政部', '財政部', '國土安全部', '中央銀行')",
            name="ck_governance_interdepartment_transfers_from_department",
        ),
        sa.CheckConstraint(
            "to_department IN ('內政部', '財政部', '國土安全部', '中央銀行')",
            name="ck_governance_interdepartment_transfers_to_department",
        ),
        sa.CheckConstraint(
            "from_department != to_department",
            name="ck_governance_interdepartment_transfers_different_departments",
        ),
        schema="governance",
    )

    op.create_index(
        "ix_governance_interdepartment_transfers_guild",
        "interdepartment_transfers",
        ["guild_id"],
        unique=False,
        schema="governance",
    )


def downgrade() -> None:
    # Drop indexes and tables in reverse order
    op.drop_index(
        "ix_governance_interdepartment_transfers_guild",
        table_name="interdepartment_transfers",
        schema="governance",
    )
    op.drop_table("interdepartment_transfers", schema="governance")

    op.drop_index(
        "ix_governance_currency_issuances_month",
        table_name="currency_issuances",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_currency_issuances_guild",
        table_name="currency_issuances",
        schema="governance",
    )
    op.drop_table("currency_issuances", schema="governance")

    op.drop_index(
        "ix_governance_identity_records_target", table_name="identity_records", schema="governance"
    )
    op.drop_index(
        "ix_governance_identity_records_guild", table_name="identity_records", schema="governance"
    )
    op.drop_table("identity_records", schema="governance")

    op.drop_index(
        "ix_governance_tax_records_taxpayer", table_name="tax_records", schema="governance"
    )
    op.drop_index("ix_governance_tax_records_guild", table_name="tax_records", schema="governance")
    op.drop_table("tax_records", schema="governance")

    op.drop_index(
        "ix_governance_welfare_disbursements_recipient",
        table_name="welfare_disbursements",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_welfare_disbursements_guild",
        table_name="welfare_disbursements",
        schema="governance",
    )
    op.drop_table("welfare_disbursements", schema="governance")

    op.drop_index(
        "ix_governance_government_accounts_guild",
        table_name="government_accounts",
        schema="governance",
    )
    op.drop_table("government_accounts", schema="governance")

    op.drop_index(
        "ix_governance_department_configs_guild",
        table_name="department_configs",
        schema="governance",
    )
    op.drop_table("department_configs", schema="governance")

    op.drop_table("state_council_config", schema="governance")
