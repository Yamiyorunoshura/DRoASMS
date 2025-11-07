"""Add helper functions for paginated history queries.

Loads the refreshed `fn_get_history` definition
and installs the new `fn_has_more_history` helper
used by the application service for cursor-based
pagination.

Revision ID: 030_history_pagination_helpers
Down Revision: 029_fix_tally_cast
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "030_history_pagination_helpers"
down_revision = "029_fix_tally_cast"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("fn_get_history.sql"))
    op.execute(_load_sql("fn_has_more_history.sql"))


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS economy.fn_has_more_history(bigint, bigint, timestamptz)")
    op.execute(_load_sql("fn_get_history.sql"))


def _load_sql(filename: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / filename
    return sql_path.read_text(encoding="utf-8")
