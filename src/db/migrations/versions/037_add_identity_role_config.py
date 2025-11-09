"""Add citizen_role_id and suspect_role_id to state_council_config.

Revision ID: 037_add_identity_role_config
Revises: 036_supreme_assembly_functions
Create Date: 2025-01-XX XX:XX:XX.XXXXXX
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "037_add_identity_role_config"
down_revision = "036_supreme_assembly_functions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add citizen_role_id and suspect_role_id columns to state_council_config
    op.add_column(
        "state_council_config",
        sa.Column("citizen_role_id", sa.BigInteger(), nullable=True),
        schema="governance",
    )
    op.add_column(
        "state_council_config",
        sa.Column("suspect_role_id", sa.BigInteger(), nullable=True),
        schema="governance",
    )

    # 由於 PostgreSQL 不允許直接以 CREATE OR REPLACE 更改 RETURNS TABLE 的欄位型態
    # 先刪除舊版函數，再重新建立（避免 InvalidFunctionDefinition: cannot change return type）
    op.execute("DROP FUNCTION IF EXISTS governance.fn_get_state_council_config(bigint)")
    op.execute(
        "DROP FUNCTION IF EXISTS governance.fn_upsert_state_council_config("
        "bigint,bigint,bigint,bigint,bigint,bigint,bigint)"
    )

    # Reload SQL functions to include new columns
    op.execute(_load_sql("governance/fn_state_council.sql"))

    # 提供向後相容的 7 參數包裝函數，轉呼叫 9 參數版本（最後兩個欄位以 NULL 帶入）
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
    # Reload SQL functions without new columns (previous version)
    # Note: This assumes the previous version of fn_state_council.sql doesn't reference these columns
    op.execute(_load_sql("governance/fn_state_council.sql"))

    # Drop columns
    op.drop_column("state_council_config", "suspect_role_id", schema="governance")
    op.drop_column("state_council_config", "citizen_role_id", schema="governance")


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
