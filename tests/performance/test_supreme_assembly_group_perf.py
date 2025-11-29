from __future__ import annotations

import time

from discord import app_commands

from src.bot.commands.supreme_assembly import build_supreme_assembly_group
from src.bot.services.council_service import CouncilService
from src.bot.services.permission_service import PermissionService
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.supreme_assembly_service import SupremeAssemblyService


def test_build_group_perf_p95_budget() -> None:
    service = SupremeAssemblyService()

    # 減少依賴：以無副作用 Stub 類型避免初始化資料庫連線
    class _StubCouncil(CouncilService):
        def __init__(self) -> None:
            pass

    class _StubStateCouncil(StateCouncilService):
        def __init__(self) -> None:
            pass

    perm = PermissionService(
        council_service=_StubCouncil(),
        state_council_service=_StubStateCouncil(),
        supreme_assembly_service=service,
    )

    samples: list[float] = []
    for _ in range(100):
        t0 = time.perf_counter()
        group: app_commands.Group = build_supreme_assembly_group(service, permission_service=perm)
        assert isinstance(group, app_commands.Group)
        samples.append(time.perf_counter() - t0)

    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    assert p95 < 0.05  # 50ms 預算
