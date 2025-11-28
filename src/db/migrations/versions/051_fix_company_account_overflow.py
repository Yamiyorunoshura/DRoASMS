"""Fix company account id derivation overflow.

Revision applies updated governance.fn_derive_company_account_id to avoid
BIGINT 溢位，改用 company_id 偏移。
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "051_fix_company_account_overflow"
down_revision = "050_company_functions"
branch_labels = None
depends_on = None


def _load_sql(filename: str) -> str:
    sql_path = Path(__file__).parent.parent.parent / "functions" / "governance" / filename
    return sql_path.read_text(encoding="utf-8")


def upgrade() -> None:
    # Re-apply company functions with safe account_id derivation (no int64 overflow)
    op.execute(_load_sql("fn_companies.sql"))


def downgrade() -> None:
    # Restore pre-fix derivation that used guild_id * 1000 (may overflow on large IDs)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION governance.fn_derive_company_account_id(
            p_guild_id bigint,
            p_company_id bigint
        )
        RETURNS bigint LANGUAGE plpgsql AS $$
        BEGIN
            RETURN 9600000000000000 + p_guild_id * 1000 + p_company_id;
        END; $$;
        """
    )
