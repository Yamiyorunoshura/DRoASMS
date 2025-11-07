"""
簡易 micro-bench：比較經濟模組在純 Python 與 mypyc 編譯版的熱點邏輯表現。

用法範例：
  # 純 Python（不含 mypyc）
  PYTHONPATH=. uv run python scripts/bench_economy.py --loops 200000 --transfer 2000

  # 已編譯的 .so 優先
  PYTHONPATH=build/mypyc_out:. uv run python scripts/bench_economy.py --loops 200000 --transfer 2000

備註：此測試刻意避開資料庫 I/O，專注於 Python 邏輯與物件操作的開銷，
      以便觀察 mypyc 編譯後的 CPU 熱路徑改善幅度。
"""

from __future__ import annotations

import argparse
import asyncio
import time
from datetime import datetime, timedelta, timezone
from types import MethodType
from typing import Any
from uuid import uuid4


def _fmt(n: float) -> str:
    if n >= 1e6:
        return f"{n/1e6:.2f}M/s"
    if n >= 1e3:
        return f"{n/1e3:.2f}k/s"
    return f"{n:.1f}/s"


def bench_balance_snapshot_is_throttled(loops: int) -> float:
    from src.bot.services.balance_service import BalanceSnapshot

    # 準備兩個不同節流狀態的樣本，交替覆蓋 CPU 快取效應
    now = datetime.now(timezone.utc)
    hot = BalanceSnapshot(
        guild_id=1, member_id=1, balance=0, throttled_until=now + timedelta(seconds=5)
    )
    cold = BalanceSnapshot(
        guild_id=1, member_id=1, balance=0, throttled_until=now - timedelta(seconds=5)
    )

    acc = 0
    t0 = time.perf_counter()
    for i in range(loops):
        snap = hot if (i & 1) == 0 else cold
        acc += 1 if snap.is_throttled else 0
    t1 = time.perf_counter()
    # 防止被最佳化；理論值應約等於 loops/2
    assert acc >= 0
    return loops / (t1 - t0)


def bench_permission_assert(loops: int) -> float:
    from src.bot.services.balance_service import BalanceService

    svc = BalanceService(pool=None)  # type: ignore[arg-type]
    t0 = time.perf_counter()
    for _ in range(loops):
        svc._assert_permission(requester_id=1, target_id=1, can_view_others=False)
    t1 = time.perf_counter()
    return loops / (t1 - t0)


async def bench_transfer_validation(loops: int) -> float:
    from src.bot.services.transfer_service import TransferService

    svc = TransferService(pool=None, event_pool_enabled=True)  # type: ignore[arg-type]

    async def _fake_create_pending_transfer(self, conn: Any, **kwargs: Any):  # noqa: ANN401
        return uuid4()

    # 將 _create_pending_transfer 綁定為實例方法，避免觸發 DB 交互
    svc._create_pending_transfer = MethodType(_fake_create_pending_transfer, svc)

    t0 = time.perf_counter()
    for _ in range(loops):
        _ = await svc.transfer_currency(
            guild_id=1,
            initiator_id=1,
            target_id=2,
            amount=1,
            reason=None,
            connection=object(),  # 避免進入 pool.acquire()
        )
    t1 = time.perf_counter()
    return loops / (t1 - t0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--loops", type=int, default=200_000, help="迴圈次數（balance/permission 測試）"
    )
    ap.add_argument("--transfer", type=int, default=2_000, help="transfer 驗證迴圈次數（async）")
    args = ap.parse_args()

    r1 = bench_balance_snapshot_is_throttled(args.loops)
    r2 = bench_permission_assert(args.loops)
    r3 = asyncio.run(bench_transfer_validation(args.transfer))

    print("Micro-bench results (ops/sec):")
    print(f"  BalanceSnapshot.is_throttled: {_fmt(r1)}")
    print(f"  BalanceService._assert_permission: {_fmt(r2)}")
    print(f"  TransferService.transfer_currency (event pool, stubbed DB): {_fmt(r3)}")


if __name__ == "__main__":
    main()
