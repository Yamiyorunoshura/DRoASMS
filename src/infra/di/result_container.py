"""Result-aware dependency injection container utilities."""

from __future__ import annotations

from src.infra.di.container import DependencyContainer


class ResultContainer:
    """Wrapper around DependencyContainer that provides Result-based services."""

    def __init__(self, base_container: DependencyContainer) -> None:
        """Initialize with a base container."""
        self._base = base_container

    def register_result_services(self) -> None:
        """Register Result-based service implementations.

        Note: CouncilServiceResult is an alias for CouncilService which is already
        registered in bootstrap_container(), so we do NOT register it here.
        StateCouncilService is now unified and registered in bootstrap_container().
        """
        # 已整併：不再註冊 SupremeAssemblyServiceResult（改以 SupremeAssemblyService 單一路徑）
        # 本方法保留以維持相容 API，但不做任何註冊。


__all__ = ["ResultContainer"]
