"""Disable daily transfer limit by default.

Reloads fn_check_transfer_daily_limit: when the GUC
`app.transfer_daily_limit` is unset or <= 0, the check always passes.

Revision ID: 025_unlimited_daily_default
Down Revision: 024_configurable_daily_limit
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "025_unlimited_daily_default"
down_revision = "024_configurable_daily_limit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("fn_check_transfer_daily_limit.sql"))


def downgrade() -> None:
    # 冪等：覆蓋同名函式不影響 schema；如需還原，請檢出前一版 SQL。
    op.execute(_load_sql("fn_check_transfer_daily_limit.sql"))


def _load_sql(filename: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / filename
    return sql_path.read_text(encoding="utf-8")
