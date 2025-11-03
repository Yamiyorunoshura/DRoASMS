"""Alter governance.department_configs.tax_rate_basis to bigint.

Revision ID: 017_tax_basis_bigint
Down Revision: 016_sc_fn_get_dept_cfg_fix
"""

from __future__ import annotations

from alembic import op

revision = "017_tax_basis_bigint"
down_revision = "016_sc_fn_get_dept_cfg_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # integer -> bigint；直接使用 USING 明確轉型，避免型別不匹配
    op.execute(
        "ALTER TABLE governance.department_configs "
        "ALTER COLUMN tax_rate_basis TYPE bigint USING tax_rate_basis::bigint"
    )

    # 重新載入函式，確保與型別一致（亦已在 SQL 中加入 ::bigint 保險轉型）
    _reload_functions()


def downgrade() -> None:
    # 還原為 integer（保留 USING 明確轉型）
    op.execute(
        "ALTER TABLE governance.department_configs "
        "ALTER COLUMN tax_rate_basis TYPE integer USING tax_rate_basis::integer"
    )
    _reload_functions()


def _reload_functions() -> None:
    from pathlib import Path

    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / "governance" / "fn_state_council.sql"
    op.execute(sql_path.read_text(encoding="utf-8"))
