"""Sync missing columns to production.

Revision ID: 045_fix_schema
Revises: 044_allow_justice_department
Create Date: 2025-11-22 10:00:00.000000

This migration ensures all columns in the suspects table exist in production,
creating any missing columns to synchronize with the local development schema.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "045_fix_schema"
down_revision = "044_allow_justice_department"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing columns to suspects table to match local development schema."""
    schema = "governance"
    table = "suspects"

    # Use raw SQL to add columns if they don't exist (idempotent)
    # We need to check if each column exists first
    connection = op.get_bind()

    # Check if suspect_id column exists
    result = connection.execute(
        sa.text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = :schema
            AND table_name = :table
            AND column_name = 'suspect_id'
        """
        ),
        {"schema": schema, "table": table},
    )
    if not result.fetchone():
        op.add_column(
            table,
            sa.Column(
                "suspect_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            schema=schema,
        )

    # Check each column and add if missing
    columns_to_check = ["guild_id", "member_id", "arrested_by", "arrest_reason"]
    for col_name in columns_to_check:
        result = connection.execute(
            sa.text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = :schema
                AND table_name = :table
                AND column_name = :col_name
            """
            ),
            {"schema": schema, "table": table, "col_name": col_name},
        )
        if not result.fetchone():
            op.add_column(
                table,
                sa.Column(
                    col_name,
                    sa.BigInteger() if col_name != "arrest_reason" else sa.Text(),
                    nullable=False,
                ),
                schema=schema,
            )

    # Add status column with default
    result = connection.execute(
        sa.text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = :schema
            AND table_name = :table
            AND column_name = 'status'
        """
        ),
        {"schema": schema, "table": table},
    )
    if not result.fetchone():
        op.add_column(
            table,
            sa.Column(
                "status",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'detained'"),
            ),
            schema=schema,
        )

    # Add timestamp columns
    timestamp_columns = ["arrested_at", "charged_at", "released_at", "created_at", "updated_at"]
    for col_name in timestamp_columns:
        result = connection.execute(
            sa.text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = :schema
                AND table_name = :table
                AND column_name = :col_name
            """
            ),
            {"schema": schema, "table": table, "col_name": col_name},
        )
        if not result.fetchone():
            nullable = col_name in ["charged_at", "released_at"]
            server_default = (
                sa.text("timezone('utc', now())")
                if col_name in ["arrested_at", "created_at", "updated_at"]
                else None
            )
            op.add_column(
                table,
                sa.Column(
                    col_name,
                    postgresql.TIMESTAMP(timezone=True),
                    nullable=nullable,
                    server_default=server_default,
                ),
                schema=schema,
            )

    # Note: We skip primary key management in this migration
    # The suspects table should already have a primary key from the original 042 migration
    # Changing primary keys on existing tables with data is risky
    # If you need to modify the primary key, do it in a separate migration after checking data

    # Ensure indexes exist
    indexes = [
        {
            "name": "ix_governance_suspects_guild_status",
            "columns": ["guild_id", "status"],
            "unique": False,
            "where": None,
        },
        {
            "name": "ix_governance_suspects_member",
            "columns": ["member_id"],
            "unique": False,
            "where": None,
        },
        {
            "name": "ix_governance_suspects_guild_member_active",
            "columns": ["guild_id", "member_id"],
            "unique": False,
            "where": "status IN ('detained', 'charged')",
        },
    ]

    for idx in indexes:
        # Check if index exists
        result = connection.execute(
            sa.text(
                """
                SELECT 1 FROM pg_indexes
                WHERE schemaname = :schema
                AND tablename = :table
                AND indexname = :index_name
            """
            ),
            {"schema": schema, "table": table, "index_name": idx["name"]},
        )
        if not result.fetchone():
            # Create index
            if idx["where"]:
                # For partial indexes, we need to use raw SQL
                connection.execute(
                    sa.text(
                        f"""
                        CREATE INDEX {idx["name"]}
                        ON {schema}.{table} ({', '.join(idx["columns"])})
                        WHERE {idx["where"]}
                    """
                    )
                )
            else:
                op.create_index(
                    idx["name"],
                    table,
                    idx["columns"],
                    unique=idx["unique"],
                    schema=schema,
                )


def downgrade() -> None:
    """Revert the schema changes."""
    schema = "governance"
    table = "suspects"

    connection = op.get_bind()

    # Drop indexes if they exist
    indexes_to_drop = [
        "ix_governance_suspects_guild_member_active",
        "ix_governance_suspects_member",
        "ix_governance_suspects_guild_status",
    ]

    for idx_name in indexes_to_drop:
        result = connection.execute(
            sa.text(
                """
                SELECT 1 FROM pg_indexes
                WHERE schemaname = :schema
                AND tablename = :table
                AND indexname = :index_name
            """
            ),
            {"schema": schema, "table": table, "index_name": idx_name},
        )
        if result.fetchone():
            op.drop_index(idx_name, table_name=table, schema=schema)

    # For safety, we don't drop columns in downgrade
    # This prevents accidental data loss
    # If you need to remove columns, create a separate migration
