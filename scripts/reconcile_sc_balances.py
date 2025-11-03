from __future__ import annotations

import argparse
import asyncio

from src.bot.services.state_council_service import StateCouncilService
from src.db.pool import close_pool, init_pool


async def _amain(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="reconcile_sc_balances",
        description=(
            "以治理層（國務院）餘額為準，將經濟帳本餘額同步對齊。"
        ),
    )
    parser.add_argument("--guild", type=int, required=True, help="Guild ID")
    parser.add_argument(
        "--admin", type=int, required=True, help="用於記錄調整的管理者 ID"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="嚴格模式：雙向調整（經濟大於治理時會扣回）",
    )
    args = parser.parse_args(argv)

    await init_pool()
    try:
        svc = StateCouncilService()
        changes = await svc.reconcile_government_balances(
            guild_id=args.guild, admin_id=args.admin, strict=bool(args.strict)
        )
        print("Reconciled changes (department -> delta):")
        for k, v in changes.items():
            print(f"- {k}: {v}")
        if not changes:
            print("No changes were necessary.")
        return 0
    finally:
        await close_pool()


def main() -> None:  # pragma: no cover - 腳本入口
    raise SystemExit(asyncio.run(_amain([])))


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(asyncio.run(_amain(sys.argv[1:])))
