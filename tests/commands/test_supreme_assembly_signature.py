from __future__ import annotations

import inspect

from src.bot.commands.supreme_assembly import build_supreme_assembly_group


def test_build_supreme_assembly_group_signature_removed_service_result() -> None:
    sig = inspect.signature(build_supreme_assembly_group)
    params = list(sig.parameters.keys())
    # 期望僅有 service 與可選的 permission_service，且不再包含 service_result
    assert "service_result" not in params
