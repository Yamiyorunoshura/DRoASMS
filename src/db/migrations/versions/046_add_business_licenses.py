"""Add business licenses table for Interior Affairs.

Revision adds:
- governance.business_licenses - for managing business licenses issued by Interior Affairs

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "046_add_business_licenses"
down_revision = "045_fix_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Business licenses table
    op.create_table(
        "business_licenses",
        sa.Column(
            "license_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("license_type", sa.Text(), nullable=False),
        sa.Column("issued_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "issued_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "expires_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("revoked_by", sa.BigInteger(), nullable=True),
        sa.Column("revoked_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
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
            "status IN ('active', 'expired', 'revoked')",
            name="ck_governance_business_licenses_status",
        ),
        schema="governance",
    )

    # Indexes for performance
    op.create_index(
        "ix_governance_business_licenses_guild_status",
        "business_licenses",
        ["guild_id", "status"],
        unique=False,
        schema="governance",
    )
    op.create_index(
        "ix_governance_business_licenses_user",
        "business_licenses",
        ["user_id"],
        unique=False,
        schema="governance",
    )
    op.create_index(
        "ix_governance_business_licenses_license_type",
        "business_licenses",
        ["guild_id", "license_type"],
        unique=False,
        schema="governance",
    )

    # Unique constraint: one active license per user per guild per type
    op.create_index(
        "ix_governance_business_licenses_unique_active",
        "business_licenses",
        ["guild_id", "user_id", "license_type"],
        unique=True,
        schema="governance",
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_governance_business_licenses_unique_active",
        table_name="business_licenses",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_business_licenses_license_type",
        table_name="business_licenses",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_business_licenses_user",
        table_name="business_licenses",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_business_licenses_guild_status",
        table_name="business_licenses",
        schema="governance",
    )
    op.drop_table("business_licenses", schema="governance")
