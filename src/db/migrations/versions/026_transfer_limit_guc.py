"""Read daily limit from GUC in fn_transfer_currency.

Reloads fn_transfer_currency to use session GUC `app.transfer_daily_limit`.
If the GUC is unset or <= 0, no daily cap is enforced. This aligns runtime
behaviour with `fn_check_transfer_daily_limit` and removes the hard-coded
default of 500 that caused false throttling.

Revision ID: 026_transfer_limit_guc
Down Revision: 025_unlimited_daily_default
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "026_transfer_limit_guc"
down_revision = "025_unlimited_daily_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("fn_transfer_currency.sql"))


def downgrade() -> None:
    # 冪等：如需還原，請檢出前一版 SQL 覆寫。
    op.execute(_load_sql("fn_transfer_currency.sql"))


def _load_sql(filename: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / filename
    return sql_path.read_text(encoding="utf-8")
