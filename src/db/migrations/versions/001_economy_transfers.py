"""Create economy schema with ledger and transaction tables for transfers."""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_economy_transfers"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS economy")

    transaction_direction = sa.Enum(
        "transfer",
        "adjustment_grant",
        "adjustment_deduct",
        "throttle_block",
        name="transaction_direction",
        schema="economy",
    )

    op.create_table(
        "guild_member_balances",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("member_id", sa.BigInteger(), nullable=False),
        sa.Column("current_balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "last_modified_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "throttled_until",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.PrimaryKeyConstraint("guild_id", "member_id", name="pk_guild_member_balances"),
        sa.CheckConstraint("current_balance >= 0", name="ck_guild_member_balances_positive"),
        schema="economy",
    )

    op.create_index(
        "ix_guild_member_balances_throttled_until",
        "guild_member_balances",
        ["throttled_until"],
        unique=False,
        schema="economy",
        postgresql_where=sa.text("throttled_until IS NOT NULL"),
    )

    op.create_table(
        "currency_transactions",
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("initiator_id", sa.BigInteger(), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("direction", transaction_direction, nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("balance_after_initiator", sa.BigInteger(), nullable=False),
        sa.Column("balance_after_target", sa.BigInteger(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.ForeignKeyConstraint(
            ["guild_id", "initiator_id"],
            ["economy.guild_member_balances.guild_id", "economy.guild_member_balances.member_id"],
            name="fk_currency_transactions_initiator",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["guild_id", "target_id"],
            ["economy.guild_member_balances.guild_id", "economy.guild_member_balances.member_id"],
            name="fk_currency_transactions_target",
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "amount > 0 OR direction = 'throttle_block'", name="ck_currency_transactions_amount"
        ),
        schema="economy",
    )

    op.create_index(
        "ix_currency_transactions_guild_initiator_created",
        "currency_transactions",
        ["guild_id", "initiator_id", "created_at"],
        unique=False,
        schema="economy",
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type
                JOIN pg_namespace ON pg_namespace.oid = pg_type.typnamespace
                WHERE pg_type.typname = 'transfer_result'
                  AND pg_namespace.nspname = 'economy'
            ) THEN
                CREATE TYPE economy.transfer_result AS (
                    transaction_id uuid,
                    guild_id bigint,
                    initiator_id bigint,
                    target_id bigint,
                    amount bigint,
                    direction economy.transaction_direction,
                    created_at timestamptz,
                    initiator_balance bigint,
                    target_balance bigint,
                    throttled_until timestamptz,
                    metadata jsonb
                );
            END IF;
        END$$;
        """
    )

    op.execute(_load_sql("fn_transfer_currency.sql"))


def downgrade() -> None:
    op.drop_index(
        "ix_currency_transactions_guild_initiator_created",
        table_name="currency_transactions",
        schema="economy",
    )
    op.drop_table("currency_transactions", schema="economy")
    op.drop_index(
        "ix_guild_member_balances_throttled_until",
        table_name="guild_member_balances",
        schema="economy",
    )
    op.drop_table("guild_member_balances", schema="economy")

    op.execute(
        "DROP FUNCTION IF EXISTS economy.fn_transfer_currency(bigint, bigint, bigint, bigint, jsonb)"
    )
    op.execute("DROP FUNCTION IF EXISTS economy.fn_record_throttle(bigint, bigint, jsonb)")

    op.execute(
        """
        DROP TYPE IF EXISTS economy.transfer_result
        """
    )

    transaction_direction = sa.Enum(
        "transfer",
        "adjustment_grant",
        "adjustment_deduct",
        "throttle_block",
        name="transaction_direction",
        schema="economy",
    )
    transaction_direction.drop(op.get_bind(), checkfirst=True)

    op.execute("DROP SCHEMA IF EXISTS economy CASCADE")


def _load_sql(filename: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / filename
    return sql_path.read_text(encoding="utf-8")
