"""Update state council config to use role-based leadership instead of user-based.

Revision adds:
- Add leader_role_id column to governance.state_council_config
- Keep leader_id for backward compatibility during transition
- Update constraints and indexes

Revision ID: 007_state_council_role_leadership
Down Revision: 006_state_council_governance
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "007_state_council_role"
down_revision = "006_state_council_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add leader_role_id column to state_council_config
    op.add_column(
        "state_council_config",
        sa.Column("leader_role_id", sa.BigInteger(), nullable=True),
        schema="governance",
    )

    # Create a unique constraint on leader_role_id to ensure only one guild uses the same role for leadership
    op.create_index(
        "ix_governance_state_council_config_leader_role",
        "state_council_config",
        ["leader_role_id"],
        unique=False,
        schema="governance",
    )

    # Add comment to explain the transition
    op.execute(
        "COMMENT ON COLUMN governance.state_council_config.leader_role_id IS 'Role ID that can access state council leadership functions. Replaces leader_id for role-based access.'"
    )

    op.execute(
        "COMMENT ON COLUMN governance.state_council_config.leader_id IS 'Legacy user ID for leadership. Kept for backward compatibility during transition to role-based leadership.'"
    )


def downgrade() -> None:
    # Remove the index and column
    op.drop_index(
        "ix_governance_state_council_config_leader_role",
        table_name="state_council_config",
        schema="governance",
    )

    op.drop_column("state_council_config", "leader_role_id", schema="governance")
