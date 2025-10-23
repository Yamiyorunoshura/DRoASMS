"""Add balance/history query functions and supporting indexes."""

from __future__ import annotations

from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "002_economy_balances"
down_revision = "001_economy_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_currency_transactions_guild_target_created",
        "currency_transactions",
        ["guild_id", "target_id", "created_at"],
        unique=False,
        schema="economy",
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW economy.active_throttles AS
        SELECT
            guild_id,
            member_id,
            throttled_until
        FROM economy.guild_member_balances
        WHERE throttled_until IS NOT NULL
          AND throttled_until > timezone('utc', now());
        """
    )

    op.execute(_load_sql("fn_get_balance.sql"))
    op.execute(_load_sql("fn_get_history.sql"))


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS economy.active_throttles")

    op.execute(
        "DROP FUNCTION IF EXISTS economy.fn_get_history(bigint, bigint, integer, timestamptz)"
    )
    op.execute("DROP FUNCTION IF EXISTS economy.fn_get_balance(bigint, bigint)")

    op.drop_index(
        "ix_currency_transactions_guild_target_created",
        table_name="currency_transactions",
        schema="economy",
    )


def _load_sql(filename: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / filename
    return sql_path.read_text(encoding="utf-8")
