"""Create governance schema for Council proposals, votes, and config.

Revision adds:
- governance.council_config
- governance.proposals
- governance.proposal_snapshots
- governance.votes

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "005_governance_council"
down_revision = "004_economy_archival"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS governance")

    # Frozen dictionaries from spec
    # Status: 進行中, 已通過, 已否決, 已逾時, 已撤案, 執行失敗, 已執行
    # Vote choice: approve, reject, abstain

    # Config table per guild
    op.create_table(
        "council_config",
        sa.Column("guild_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("council_role_id", sa.BigInteger(), nullable=False),
        sa.Column("council_account_member_id", sa.BigInteger(), nullable=False),
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
        schema="governance",
    )

    # Proposals
    op.create_table(
        "proposals",
        sa.Column(
            "proposal_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("proposer_id", sa.BigInteger(), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("attachment_url", sa.Text(), nullable=True),
        sa.Column("snapshot_n", sa.Integer(), nullable=False),
        sa.Column("threshold_t", sa.Integer(), nullable=False),
        sa.Column(
            "deadline_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reminder_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("execution_tx_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_error", sa.Text(), nullable=True),
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
        sa.CheckConstraint("amount > 0", name="ck_governance_proposals_amount_positive"),
        sa.CheckConstraint(
            "status IN (\n                '進行中','已通過','已否決','已逾時','已撤案','執行失敗','已執行'\n            )",
            name="ck_governance_proposals_status",
        ),
        schema="governance",
    )

    op.create_index(
        "ix_governance_proposals_guild_status",
        "proposals",
        ["guild_id", "status"],
        unique=False,
        schema="governance",
    )
    op.create_index(
        "ix_governance_proposals_deadline",
        "proposals",
        ["deadline_at"],
        unique=False,
        schema="governance",
    )

    # Snapshot of council at creation time
    op.create_table(
        "proposal_snapshots",
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint(
            "proposal_id", "member_id", name="pk_governance_proposal_snapshots"
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["governance.proposals.proposal_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_governance_snapshots_proposal",
        ),
        schema="governance",
    )

    # Last-vote-wins per voter per proposal
    op.create_table(
        "votes",
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voter_id", sa.BigInteger(), nullable=False),
        sa.Column("choice", sa.Text(), nullable=False),
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
        sa.PrimaryKeyConstraint("proposal_id", "voter_id", name="pk_governance_votes"),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["governance.proposals.proposal_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_governance_votes_proposal",
        ),
        sa.CheckConstraint(
            "choice IN ('approve','reject','abstain')",
            name="ck_governance_votes_choice",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_governance_votes_proposal",
        "votes",
        ["proposal_id"],
        unique=False,
        schema="governance",
    )


def downgrade() -> None:
    op.drop_index("ix_governance_votes_proposal", table_name="votes", schema="governance")
    op.drop_table("votes", schema="governance")
    op.drop_table("proposal_snapshots", schema="governance")
    op.drop_index(
        "ix_governance_proposals_deadline",
        table_name="proposals",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_proposals_guild_status",
        table_name="proposals",
        schema="governance",
    )
    op.drop_table("proposals", schema="governance")
    op.drop_table("council_config", schema="governance")
    op.execute("DROP SCHEMA IF EXISTS governance CASCADE")
