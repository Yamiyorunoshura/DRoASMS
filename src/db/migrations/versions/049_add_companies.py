"""Add companies table for business entity management.

Revision adds:
- governance.companies - for managing companies owned by business license holders

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "049_add_companies"
down_revision = "048_add_government_applications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Companies table - one company per valid business license
    op.create_table(
        "companies",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "license_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.VARCHAR(100), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["license_id"],
            ["governance.business_licenses.license_id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
            name="fk_governance_companies_license",
        ),
        # Each license can only have one company
        sa.UniqueConstraint("guild_id", "license_id", name="uq_governance_companies_guild_license"),
        # Account ID must be unique
        sa.UniqueConstraint("account_id", name="uq_governance_companies_account_id"),
        schema="governance",
    )

    # Index for faster lookups by guild
    op.create_index(
        "ix_governance_companies_guild",
        "companies",
        ["guild_id"],
        unique=False,
        schema="governance",
    )

    # Index for owner lookups
    op.create_index(
        "ix_governance_companies_owner",
        "companies",
        ["guild_id", "owner_id"],
        unique=False,
        schema="governance",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_governance_companies_owner",
        table_name="companies",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_companies_guild",
        table_name="companies",
        schema="governance",
    )
    op.drop_table("companies", schema="governance")
