"""Add support for multiple council role IDs.

This revision:
- Adds council_role_ids table to store multiple council role configurations
- Updates CouncilConfig to support role array
- Maintains backward compatibility with existing single council_role_id

Revision ID: 040_council_multiple_roles
Revises: 039_add_arrest_action
Create Date: 2025-11-12 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "040_council_multiple_roles"
down_revision = "039_add_arrest_action"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create table for multiple council role configurations
    op.create_table(
        "council_role_ids",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
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
        sa.UniqueConstraint("guild_id", "role_id", name="uq_council_role_ids_guild_role"),
        schema="governance",
    )

    # Create index for faster lookups
    op.create_index(
        "ix_governance_council_role_ids_guild",
        "council_role_ids",
        ["guild_id"],
        unique=False,
        schema="governance",
    )

    # Migrate existing council_role_id to the new table
    op.execute(
        """
        INSERT INTO governance.council_role_ids (guild_id, role_id, created_at, updated_at)
        SELECT
            guild_id,
            council_role_id as role_id,
            created_at,
            updated_at
        FROM governance.council_config
        WHERE council_role_id IS NOT NULL
        ON CONFLICT (guild_id, role_id) DO NOTHING
    """
    )

    # Create function to get all council role IDs for a guild
    op.execute(
        """
        CREATE OR REPLACE FUNCTION governance.fn_get_council_role_ids(p_guild_id BIGINT)
        RETURNS BIGINT[]
        LANGUAGE sql
        SECURITY DEFINER
        AS $$
            SELECT COALESCE(ARRAY_AGG(role_id), ARRAY[]::BIGINT[])
            FROM governance.council_role_ids
            WHERE guild_id = p_guild_id;
        $$;
    """
    )

    # Create function to add council role
    op.execute(
        """
        CREATE OR REPLACE FUNCTION governance.fn_add_council_role(
            p_guild_id BIGINT,
            p_role_id BIGINT
        )
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        DECLARE
            v_exists BOOLEAN;
        BEGIN
            -- Check if role already exists for this guild
            SELECT EXISTS(
                SELECT 1 FROM governance.council_role_ids
                WHERE guild_id = p_guild_id AND role_id = p_role_id
            ) INTO v_exists;

            IF v_exists THEN
                RETURN FALSE;
            END IF;

            -- Add the new role
            INSERT INTO governance.council_role_ids (guild_id, role_id)
            VALUES (p_guild_id, p_role_id)
            ON CONFLICT (guild_id, role_id) DO NOTHING;

            RETURN TRUE;
        END;
        $$;
    """
    )

    # Create function to remove council role
    op.execute(
        """
        CREATE OR REPLACE FUNCTION governance.fn_remove_council_role(
            p_guild_id BIGINT,
            p_role_id BIGINT
        )
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        DECLARE
            v_deleted INTEGER;
        BEGIN
            DELETE FROM governance.council_role_ids
            WHERE guild_id = p_guild_id AND role_id = p_role_id;

            GET DIAGNOSTICS v_deleted = ROW_COUNT;
            RETURN v_deleted > 0;
        END;
        $$;
    """
    )


def downgrade() -> None:
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS governance.fn_remove_council_role(BIGINT, BIGINT)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_add_council_role(BIGINT, BIGINT)")
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_council_role_ids(BIGINT)")

    # Drop index and table
    op.drop_index(
        "ix_governance_council_role_ids_guild", table_name="council_role_ids", schema="governance"
    )
    op.drop_table("council_role_ids", schema="governance")
