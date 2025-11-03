"""Create pending_transfers table and related functions for event pool architecture.

This migration creates the economy.pending_transfers table to support
asynchronous transfer processing with automatic retry and check coordination
via PostgreSQL NOTIFY/LISTEN events.

Revision ID: 022_pending_transfers
Down Revision: 021_government_exempt_transfers
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "022_pending_transfers"
down_revision = "021_government_exempt_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pending_transfers table
    op.create_table(
        "pending_transfers",
        sa.Column(
            "transfer_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("initiator_id", sa.BigInteger(), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "checks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "expires_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
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
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint("amount > 0", name="ck_pending_transfers_amount_positive"),
        sa.CheckConstraint(
            "status IN ('pending', 'checking', 'approved', 'completed', 'rejected')",
            name="ck_pending_transfers_status",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_pending_transfers_retry_count"),
        schema="economy",
    )

    # Create indexes
    op.create_index(
        "ix_pending_transfers_guild_status",
        "pending_transfers",
        ["guild_id", "status"],
        unique=False,
        schema="economy",
    )

    op.create_index(
        "ix_pending_transfers_expires_at",
        "pending_transfers",
        ["expires_at"],
        unique=False,
        schema="economy",
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )

    op.create_index(
        "ix_pending_transfers_status_updated",
        "pending_transfers",
        ["status", "updated_at"],
        unique=False,
        schema="economy",
    )

    # Load SQL functions (helper function first, then functions that use it)
    op.execute(_load_sql("fn_check_and_approve_transfer.sql"))
    op.execute(_load_sql("fn_create_pending_transfer.sql"))
    op.execute(_load_sql("fn_check_transfer_balance.sql"))
    op.execute(_load_sql("fn_check_transfer_cooldown.sql"))
    op.execute(_load_sql("fn_check_transfer_daily_limit.sql"))
    op.execute(_load_sql("fn_get_pending_transfer.sql"))
    op.execute(_load_sql("fn_list_pending_transfers.sql"))
    op.execute(_load_sql("fn_update_pending_transfer_status.sql"))
    op.execute(_load_sql("trigger_pending_transfer_check.sql"))


def downgrade() -> None:
    op.drop_index(
        "ix_pending_transfers_status_updated",
        table_name="pending_transfers",
        schema="economy",
    )
    op.drop_index(
        "ix_pending_transfers_expires_at",
        table_name="pending_transfers",
        schema="economy",
    )
    op.drop_index(
        "ix_pending_transfers_guild_status",
        table_name="pending_transfers",
        schema="economy",
    )
    op.drop_table("pending_transfers", schema="economy")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS economy.trigger_pending_transfer_check() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS economy.fn_update_pending_transfer_status(uuid, text)")
    op.execute(
        "DROP FUNCTION IF EXISTS economy.fn_list_pending_transfers(bigint, text, integer, integer)"
    )
    op.execute("DROP FUNCTION IF EXISTS economy.fn_get_pending_transfer(uuid)")
    op.execute("DROP FUNCTION IF EXISTS economy.fn_check_transfer_daily_limit(uuid)")
    op.execute("DROP FUNCTION IF EXISTS economy.fn_check_transfer_cooldown(uuid)")
    op.execute("DROP FUNCTION IF EXISTS economy.fn_check_transfer_balance(uuid)")
    op.execute(
        "DROP FUNCTION IF EXISTS economy.fn_create_pending_transfer(bigint, bigint, bigint, bigint, jsonb, timestamptz)"
    )
    op.execute("DROP FUNCTION IF EXISTS economy._check_and_approve_transfer(uuid)")


def _load_sql(filename: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / filename
    return sql_path.read_text(encoding="utf-8")
