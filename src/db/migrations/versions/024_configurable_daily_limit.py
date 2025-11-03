"""Make daily limit configurable via session GUC.

Reloads fn_check_transfer_daily_limit to read
`current_setting('app.transfer_daily_limit', true)` with a default of 500.

Revision ID: 024_configurable_daily_limit
Down Revision: 023_fix_pt_status_cast
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "024_configurable_daily_limit"
down_revision = "023_fix_pt_status_cast"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("fn_check_transfer_daily_limit.sql"))


def downgrade() -> None:
    # 同內容覆蓋是冪等的；若需還原，請檢出上一版 SQL。
    op.execute(_load_sql("fn_check_transfer_daily_limit.sql"))


def _load_sql(filename: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / filename
    return sql_path.read_text(encoding="utf-8")
