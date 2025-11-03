"""Reload functions to fix pending_transfers.status return type cast.

This migration re-creates the following functions with an explicit cast of
`pending_transfers.status` to `text` to match the RETURNS TABLE signature:

- economy.fn_get_pending_transfer(uuid)
- economy.fn_list_pending_transfers(bigint, text, integer, integer)

Without this, PostgreSQL raises:
  "structure of query does not match function result type\n
   DETAIL: Returned type character varying(20) does not match expected type text in column 6."

Revision ID: 023_fix_pt_status_cast
Down Revision: 022_pending_transfers
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "023_fix_pt_status_cast"
down_revision = "022_pending_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("fn_get_pending_transfer.sql"))
    op.execute(_load_sql("fn_list_pending_transfers.sql"))


def downgrade() -> None:
    # Idempotent: re-apply the same definitions is safe.
    # If you need to revert to older definitions, use Alembic history to checkout 022 and re-apply.
    op.execute(_load_sql("fn_get_pending_transfer.sql"))
    op.execute(_load_sql("fn_list_pending_transfers.sql"))


def _load_sql(filename: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / filename
    return sql_path.read_text(encoding="utf-8")
