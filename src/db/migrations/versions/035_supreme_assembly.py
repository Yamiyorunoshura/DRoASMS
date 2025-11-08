"""Create Supreme Assembly base tables.

Revision ID: 035_supreme_assembly
Revises: 034_zero_interdept_transfer
Create Date: 2025-11-08 18:05:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "035_supreme_assembly"
down_revision = "034_zero_interdept_transfer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure governance schema exists
    op.execute("CREATE SCHEMA IF NOT EXISTS governance")

    # 1) Config: per guild speaker/member role mapping
    op.create_table(
        "supreme_assembly_configurations",
        sa.Column("guild_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("speaker_role_id", sa.BigInteger(), nullable=False),
        sa.Column("member_role_id", sa.BigInteger(), nullable=False),
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

    # 2) Accounts: deterministic account id with shadow balance for reporting
    op.create_table(
        "supreme_assembly_accounts",
        sa.Column("account_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
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
        sa.CheckConstraint("balance >= 0", name="ck_governance_sa_accounts_balance_non_negative"),
        schema="governance",
    )
    op.create_index(
        "ix_governance_sa_accounts_guild",
        "supreme_assembly_accounts",
        ["guild_id"],
        unique=True,  # 單一公會一個最高人民會議帳戶
        schema="governance",
    )

    # 3) Proposals: minimal structure for voting-only proposals
    op.create_table(
        "supreme_assembly_proposals",
        sa.Column(
            "proposal_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("proposer_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("snapshot_n", sa.Integer(), nullable=False),
        sa.Column("threshold_t", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'進行中'")),
        sa.Column(
            "deadline_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column("reminder_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.CheckConstraint(
            "status IN ('進行中','已通過','已否決','已逾時','已撤案')",
            name="ck_governance_sa_proposals_status",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_governance_sa_proposals_guild_status",
        "supreme_assembly_proposals",
        ["guild_id", "status"],
        unique=False,
        schema="governance",
    )

    # 3.1) Snapshot of members at proposal creation time
    op.create_table(
        "supreme_assembly_proposal_snapshots",
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint(
            "proposal_id", "member_id", name="pk_governance_sa_proposal_snapshots"
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["governance.supreme_assembly_proposals.proposal_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_governance_sa_snapshots_proposal",
        ),
        schema="governance",
    )

    # 4) Votes: immutable per (proposal, voter)
    op.create_table(
        "supreme_assembly_votes",
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voter_id", sa.BigInteger(), nullable=False),
        sa.Column("choice", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.PrimaryKeyConstraint("proposal_id", "voter_id", name="pk_governance_sa_votes"),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["governance.supreme_assembly_proposals.proposal_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk_governance_sa_votes_proposal",
        ),
        sa.CheckConstraint(
            "choice IN ('approve','reject','abstain')",
            name="ck_governance_sa_votes_choice",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_governance_sa_votes_proposal",
        "supreme_assembly_votes",
        ["proposal_id"],
        unique=False,
        schema="governance",
    )

    # 5) Summons: record notifications issued by speaker
    op.create_table(
        "supreme_assembly_summons",
        sa.Column(
            "summon_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("invoked_by", sa.BigInteger(), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("target_kind", sa.Text(), nullable=False),  # 'member' | 'official'
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "delivered_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint(
            "target_kind IN ('member','official')",
            name="ck_governance_sa_summons_target_kind",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_governance_sa_summons_guild",
        "supreme_assembly_summons",
        ["guild_id"],
        unique=False,
        schema="governance",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_governance_sa_summons_guild",
        table_name="supreme_assembly_summons",
        schema="governance",
    )
    op.drop_table("supreme_assembly_summons", schema="governance")

    op.drop_index(
        "ix_governance_sa_votes_proposal",
        table_name="supreme_assembly_votes",
        schema="governance",
    )
    op.drop_table("supreme_assembly_votes", schema="governance")

    op.drop_table("supreme_assembly_proposal_snapshots", schema="governance")

    op.drop_index(
        "ix_governance_sa_proposals_guild_status",
        table_name="supreme_assembly_proposals",
        schema="governance",
    )
    op.drop_table("supreme_assembly_proposals", schema="governance")

    op.drop_index(
        "ix_governance_sa_accounts_guild",
        table_name="supreme_assembly_accounts",
        schema="governance",
    )
    op.drop_table("supreme_assembly_accounts", schema="governance")

    op.drop_table("supreme_assembly_configurations", schema="governance")
