"""Add admin adjustments function, notify trigger, and configurations table."""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "003_economy_adjustments"
down_revision = "002_economy_balances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "economy_configurations",
        sa.Column("guild_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column(
            "admin_role_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
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
        schema="economy",
    )

    # Functions
    op.execute(_load_sql("fn_adjust_balance.sql"))
    op.execute(_load_sql("fn_notify_adjustment.sql"))

    # Trigger for audit notifications on adjustments
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger WHERE tgname = 'trg_notify_adjustment'
            ) THEN
                CREATE TRIGGER trg_notify_adjustment
                AFTER INSERT ON economy.currency_transactions
                FOR EACH ROW
                EXECUTE FUNCTION economy.fn_notify_adjustment();
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # Drop trigger and function
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_notify_adjustment ON economy.currency_transactions;
        """
    )
    op.execute("DROP FUNCTION IF EXISTS economy.fn_notify_adjustment()")
    op.execute(
        "DROP FUNCTION IF EXISTS economy.fn_adjust_balance(bigint,bigint,bigint,bigint,text,jsonb)"
    )

    op.drop_table("economy_configurations", schema="economy")


def _load_sql(filename: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / filename
    return sql_path.read_text(encoding="utf-8")
