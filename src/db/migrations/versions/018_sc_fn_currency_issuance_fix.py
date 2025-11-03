"""Fix fn_create_currency_issuance ambiguity by qualifying RETURNING columns.

Revision ID: 018_sc_fn_currency_issuance_fix
Down Revision: 017_tax_basis_bigint
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "018_sc_fn_currency_issuance_fix"
down_revision = "017_tax_basis_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reload consolidated governance functions so that
    # governance.fn_create_currency_issuance uses
    #   INSERT ... AS ci RETURNING ci.*
    # to avoid PL/pgSQL ambiguous column/variable names.
    op.execute(_load_sql("governance/fn_state_council.sql"))


def downgrade() -> None:
    # No-op; rolling back to previous revision will restore the old definition.
    pass


def _load_sql(relative_path: str) -> str:
    base_path = Path(__file__).resolve().parents[2]
    sql_path = base_path / "functions" / relative_path
    return sql_path.read_text(encoding="utf-8")
