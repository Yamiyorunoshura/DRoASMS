from __future__ import annotations

import inspect

from src.infra.di.container import DependencyContainer
from src.infra.di.result_container import ResultContainer


def test_result_container_does_not_register_supreme_result() -> None:
    base = DependencyContainer()
    rc = ResultContainer(base)
    # Act: register result-based services
    rc.register_result_services()

    # Assert: after整併，SupremeAssemblyServiceResult 不應再註冊於 DI
    try:
        from src.bot.services.supreme_assembly_service_result import SupremeAssemblyServiceResult
    except Exception:
        SupremeAssemblyServiceResult = None  # type: ignore

    # 若模組仍存在，至少不應在 DI 註冊；若模組已移除，此處以 None 表示
    if SupremeAssemblyServiceResult is not None:
        assert not base.is_registered(SupremeAssemblyServiceResult)
    else:
        # 模組已移除視為通過
        assert True


def test_container_api_stable() -> None:
    # 介面檢查：DependencyContainer 仍提供 is_registered/resolve 等方法
    base = DependencyContainer()
    assert hasattr(base, "is_registered")
    assert callable(base.is_registered)
    assert hasattr(base, "register")
    assert hasattr(base, "register_instance")
    assert inspect.isclass(ResultContainer)
