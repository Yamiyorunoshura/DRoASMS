"""Add unique constraint on (guild_id, department) for department_configs.

Ensures UPSERT in code using ON CONFLICT (guild_id, department) works.

Revision ID: 009_dept_cfg_unique
Down Revision: 008_sc_leader_nullable
"""

from __future__ import annotations

from alembic import op

revision = "009_dept_cfg_unique"
down_revision = "008_sc_leader_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_governance_department_configs_guild_dept",
        "department_configs",
        ["guild_id", "department"],
        schema="governance",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_governance_department_configs_guild_dept",
        "department_configs",
        type_="unique",
        schema="governance",
    )
