"""Add government service applications tables.

Revision adds:
- governance.welfare_applications - for welfare applications from personal panel
- governance.license_applications - for business license applications from personal panel

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "048_add_government_applications"
down_revision = "047_business_license_functions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Welfare applications table
    op.create_table(
        "welfare_applications",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("applicant_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_governance_welfare_applications_status",
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_governance_welfare_applications_amount_positive",
        ),
        schema="governance",
    )

    # Indexes for welfare applications
    op.create_index(
        "ix_governance_welfare_applications_guild_status",
        "welfare_applications",
        ["guild_id", "status"],
        unique=False,
        schema="governance",
    )
    op.create_index(
        "ix_governance_welfare_applications_applicant",
        "welfare_applications",
        ["guild_id", "applicant_id"],
        unique=False,
        schema="governance",
    )

    # License applications table
    op.create_table(
        "license_applications",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("applicant_id", sa.BigInteger(), nullable=False),
        sa.Column("license_type", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_governance_license_applications_status",
        ),
        schema="governance",
    )

    # Indexes for license applications
    op.create_index(
        "ix_governance_license_applications_guild_status",
        "license_applications",
        ["guild_id", "status"],
        unique=False,
        schema="governance",
    )
    op.create_index(
        "ix_governance_license_applications_applicant",
        "license_applications",
        ["guild_id", "applicant_id"],
        unique=False,
        schema="governance",
    )
    op.create_index(
        "ix_governance_license_applications_type",
        "license_applications",
        ["guild_id", "license_type"],
        unique=False,
        schema="governance",
    )


def downgrade() -> None:
    # Drop license applications indexes and table
    op.drop_index(
        "ix_governance_license_applications_type",
        table_name="license_applications",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_license_applications_applicant",
        table_name="license_applications",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_license_applications_guild_status",
        table_name="license_applications",
        schema="governance",
    )
    op.drop_table("license_applications", schema="governance")

    # Drop welfare applications indexes and table
    op.drop_index(
        "ix_governance_welfare_applications_applicant",
        table_name="welfare_applications",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_welfare_applications_guild_status",
        table_name="welfare_applications",
        schema="governance",
    )
    op.drop_table("welfare_applications", schema="governance")
