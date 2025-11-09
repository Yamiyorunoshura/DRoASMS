"""Add 7-arg wrapper for fn_upsert_state_council_config (back-compat).

Revision ID: 038_backcompat_upsert_sc_wrapper
Revises: 037_add_identity_role_config
Create Date: 2025-11-08
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "038_backcompat_upsert_sc_wrapper"
down_revision = "037_add_identity_role_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure 9-arg function has no DEFAULT parameters (drop and recreate)
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_upsert_state_council_config("
        "bigint,bigint,bigint,bigint,bigint,bigint,bigint,bigint,bigint)"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION governance.fn_upsert_state_council_config(
            p_guild_id bigint,
            p_leader_id bigint,
            p_leader_role_id bigint,
            p_internal_affairs_account_id bigint,
            p_finance_account_id bigint,
            p_security_account_id bigint,
            p_central_bank_account_id bigint,
            p_citizen_role_id bigint,
            p_suspect_role_id bigint
        )
        RETURNS TABLE (
            guild_id bigint,
            leader_id bigint,
            leader_role_id bigint,
            internal_affairs_account_id bigint,
            finance_account_id bigint,
            security_account_id bigint,
            central_bank_account_id bigint,
            citizen_role_id bigint,
            suspect_role_id bigint,
            created_at timestamptz,
            updated_at timestamptz
        ) LANGUAGE plpgsql AS $$
        BEGIN
            RETURN QUERY
            INSERT INTO governance.state_council_config AS c (
                guild_id, leader_id, leader_role_id, internal_affairs_account_id,
                finance_account_id, security_account_id, central_bank_account_id,
                citizen_role_id, suspect_role_id
            ) VALUES (
                p_guild_id, p_leader_id, p_leader_role_id, p_internal_affairs_account_id,
                p_finance_account_id, p_security_account_id, p_central_bank_account_id,
                p_citizen_role_id, p_suspect_role_id
            )
            ON CONFLICT ON CONSTRAINT state_council_config_pkey
            DO UPDATE SET leader_id = EXCLUDED.leader_id,
                          leader_role_id = EXCLUDED.leader_role_id,
                          internal_affairs_account_id = EXCLUDED.internal_affairs_account_id,
                          finance_account_id = EXCLUDED.finance_account_id,
                          security_account_id = EXCLUDED.security_account_id,
                          central_bank_account_id = EXCLUDED.central_bank_account_id,
                          citizen_role_id = EXCLUDED.citizen_role_id,
                          suspect_role_id = EXCLUDED.suspect_role_id,
                          updated_at = timezone('utc', clock_timestamp())
            RETURNING c.guild_id, c.leader_id, c.leader_role_id, c.internal_affairs_account_id,
                      c.finance_account_id, c.security_account_id, c.central_bank_account_id,
                      c.citizen_role_id, c.suspect_role_id,
                      c.created_at, c.updated_at;
        END; $$;
        """
    )

    # Create 7-argument wrapper to preserve legacy callers/tests
    op.execute(
        """
        CREATE OR REPLACE FUNCTION governance.fn_upsert_state_council_config(
            p_guild_id bigint,
            p_leader_id bigint,
            p_leader_role_id bigint,
            p_internal_affairs_account_id bigint,
            p_finance_account_id bigint,
            p_security_account_id bigint,
            p_central_bank_account_id bigint
        )
        RETURNS TABLE (
            guild_id bigint,
            leader_id bigint,
            leader_role_id bigint,
            internal_affairs_account_id bigint,
            finance_account_id bigint,
            security_account_id bigint,
            central_bank_account_id bigint,
            citizen_role_id bigint,
            suspect_role_id bigint,
            created_at timestamptz,
            updated_at timestamptz
        ) LANGUAGE plpgsql AS $$
        BEGIN
            RETURN QUERY
            SELECT * FROM governance.fn_upsert_state_council_config(
                p_guild_id,
                p_leader_id,
                p_leader_role_id,
                p_internal_affairs_account_id,
                p_finance_account_id,
                p_security_account_id,
                p_central_bank_account_id,
                NULL::bigint,
                NULL::bigint
            );
        END; $$;
        """
    )


def downgrade() -> None:
    # The 7-arg wrapper can be dropped safely.
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_upsert_state_council_config("
        "bigint,bigint,bigint,bigint,bigint,bigint,bigint)"
    )
