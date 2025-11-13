"""Add state council department multiple roles support

Revision ID: 041_sc_department_multi_roles
Revises: 040_council_multiple_roles
Create Date: 2025-01-12 15:30:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "041_sc_department_multi_roles"
down_revision: Union[str, None] = "040_council_multiple_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create governance.state_council_department_role_ids table
    op.execute(
        """
        CREATE TABLE governance.state_council_department_role_ids (
            id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            guild_id BIGINT NOT NULL,
            department VARCHAR(50) NOT NULL,
            role_id BIGINT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
            UNIQUE(guild_id, department, role_id)
        );
        """
    )

    # Create indexes for performance
    op.execute(
        """
        CREATE INDEX idx_state_council_department_role_ids_guild_dept
        ON governance.state_council_department_role_ids(guild_id, department);
        """
    )

    op.execute(
        """
        CREATE INDEX idx_state_council_department_role_ids_role
        ON governance.state_council_department_role_ids(role_id);
        """
    )

    # Create management functions
    op.execute(
        """
        CREATE OR REPLACE FUNCTION governance.add_state_council_department_role(
            p_guild_id BIGINT,
            p_department VARCHAR(50),
            p_role_id BIGINT
        ) RETURNS BOOLEAN
        LANGUAGE plpgsql
        AS $$
        DECLARE
            existing_count INTEGER;
        BEGIN
            -- Check if role already exists
            SELECT COUNT(*) INTO existing_count
            FROM governance.state_council_department_role_ids
            WHERE guild_id = p_guild_id
              AND department = p_department
              AND role_id = p_role_id;

            IF existing_count > 0 THEN
                RETURN FALSE;  -- Role already exists
            END IF;

            -- Insert new role
            INSERT INTO governance.state_council_department_role_ids
                (guild_id, department, role_id)
            VALUES (p_guild_id, p_department, p_role_id);

            RETURN TRUE;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION governance.remove_state_council_department_role(
            p_guild_id BIGINT,
            p_department VARCHAR(50),
            p_role_id BIGINT
        ) RETURNS BOOLEAN
        LANGUAGE plpgsql
        AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM governance.state_council_department_role_ids
            WHERE guild_id = p_guild_id
              AND department = p_department
              AND role_id = p_role_id;

            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count > 0;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION governance.get_state_council_department_role_ids(
            p_guild_id BIGINT,
            p_department VARCHAR(50)
        ) RETURNS BIGINT[]
        LANGUAGE plpgsql
        AS $$
        DECLARE
            role_ids BIGINT[];
        BEGIN
            SELECT ARRAY_AGG(role_id) INTO role_ids
            FROM governance.state_council_department_role_ids
            WHERE guild_id = p_guild_id
              AND department = p_department;

            RETURN COALESCE(role_ids, ARRAY[]::BIGINT[]);
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION governance.list_state_council_department_role_configs(
            p_guild_id BIGINT
        ) RETURNS TABLE (
            id BIGINT,
            guild_id BIGINT,
            department VARCHAR(50),
            role_id BIGINT,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT
                id,
                guild_id,
                department,
                role_id,
                created_at,
                updated_at
            FROM governance.state_council_department_role_ids
            WHERE guild_id = p_guild_id
            ORDER BY department, created_at ASC;
        END;
        $$;
        """
    )


def downgrade() -> None:
    # Drop functions
    op.execute(
        "DROP FUNCTION IF EXISTS governance.list_state_council_department_role_configs(BIGINT);"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS governance.get_state_council_department_role_ids(BIGINT, VARCHAR(50));"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS governance.remove_state_council_department_role(BIGINT, VARCHAR(50), BIGINT);"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS governance.add_state_council_department_role(BIGINT, VARCHAR(50), BIGINT);"
    )

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS governance.idx_state_council_department_role_ids_role;")
    op.execute("DROP INDEX IF EXISTS governance.idx_state_council_department_role_ids_guild_dept;")

    # Drop table
    op.execute("DROP TABLE IF EXISTS governance.state_council_department_role_ids;")
