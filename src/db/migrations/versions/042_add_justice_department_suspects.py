"""Add justice department suspects table.

Revision adds:
- governance.suspects - for managing suspects and their status

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "042_add_justice_department_suspects"
down_revision = "041_sc_department_multi_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Suspects table for justice department
    op.create_table(
        "suspects",
        sa.Column(
            "suspect_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("member_id", sa.BigInteger(), nullable=False),
        sa.Column("arrested_by", sa.BigInteger(), nullable=False),
        sa.Column("arrest_reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'detained'"),
        ),
        sa.Column(
            "arrested_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "charged_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "released_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
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
            "status IN ('detained', 'charged', 'released')",
            name="ck_governance_suspects_status",
        ),
        schema="governance",
    )

    # Indexes for performance
    op.create_index(
        "ix_governance_suspects_guild_status",
        "suspects",
        ["guild_id", "status"],
        unique=False,
        schema="governance",
    )
    op.create_index(
        "ix_governance_suspects_member",
        "suspects",
        ["member_id"],
        unique=False,
        schema="governance",
    )

    # Unique constraint: one active suspect record per member per guild
    op.create_index(
        "ix_governance_suspects_guild_member_active",
        "suspects",
        ["guild_id", "member_id"],
        unique=False,
        schema="governance",
        postgresql_where=sa.text("status IN ('detained', 'charged')"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_governance_suspects_guild_member_active",
        table_name="suspects",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_suspects_member",
        table_name="suspects",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_suspects_guild_status",
        table_name="suspects",
        schema="governance",
    )
    op.drop_table("suspects", schema="governance")
