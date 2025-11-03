"""Exempt government accounts from daily transfer cap and throttle.

This migration reloads economy.fn_transfer_currency to skip the daily
limit and cooldown checks when the initiator is a government account in
governance.government_accounts for the same guild.

Revision ID: 021_government_exempt_transfers
Down Revision: 020_merge_heads
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "021_government_exempt_transfers"
# 修正 down_revision：上一版合併頭的實際 revision id 為
# "020_merge_heads"（見 020_governance_functions_round4_merge_heads.py），
# 先前誤填為檔名字串，導致 Alembic 找不到父修訂而升級失敗。
down_revision = "020_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(_load_sql("fn_transfer_currency.sql"))


def downgrade() -> None:
    # No-op downgrade: keep the safer behavior. If needed, a prior
    # version could be reintroduced here.
    pass


def _load_sql(filename: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / filename
    return sql_path.read_text(encoding="utf-8")
