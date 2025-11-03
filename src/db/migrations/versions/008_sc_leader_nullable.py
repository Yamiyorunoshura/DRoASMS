"""Make leader_id nullable and add check that either leader_id or leader_role_id present.

Revision adds:
- Alter governance.state_council_config.leader_id to nullable
- Add CHECK (leader_id IS NOT NULL OR leader_role_id IS NOT NULL)

Revision ID: 008_sc_leader_nullable
Down Revision: 007_state_council_role
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "008_sc_leader_nullable"
down_revision = "007_state_council_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make leader_id nullable to support role-based leadership only
    op.alter_column(
        "state_council_config",
        "leader_id",
        existing_type=sa.BigInteger(),
        nullable=True,
        schema="governance",
    )

    # Add check constraint to ensure at least one leadership identifier is present
    op.create_check_constraint(
        "ck_governance_state_council_config_leader_present",
        "state_council_config",
        "(leader_id IS NOT NULL) OR (leader_role_id IS NOT NULL)",
        schema="governance",
    )


def downgrade() -> None:
    # Drop the check constraint first
    op.drop_constraint(
        "ck_governance_state_council_config_leader_present",
        "state_council_config",
        type_="check",
        schema="governance",
    )

    # Revert leader_id back to NOT NULL
    op.alter_column(
        "state_council_config",
        "leader_id",
        existing_type=sa.BigInteger(),
        nullable=False,
        schema="governance",
    )
