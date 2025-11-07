"""Add currency_name and currency_icon columns to economy_configurations.

Revision ID: 031_add_currency_configuration
Down Revision: 030_history_pagination_helpers
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "031_add_currency_configuration"
down_revision = "030_history_pagination_helpers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add currency_name and currency_icon columns
    op.add_column(
        "economy_configurations",
        sa.Column("currency_name", sa.String(length=20), nullable=False, server_default="點"),
        schema="economy",
    )
    op.add_column(
        "economy_configurations",
        sa.Column("currency_icon", sa.String(length=10), nullable=False, server_default=""),
        schema="economy",
    )

    # Update existing records with default values
    op.execute(
        """
        UPDATE economy.economy_configurations
        SET currency_name = '點', currency_icon = ''
        WHERE currency_name IS NULL OR currency_icon IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("economy_configurations", "currency_icon", schema="economy")
    op.drop_column("economy_configurations", "currency_name", schema="economy")
