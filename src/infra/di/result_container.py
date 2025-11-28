"""Result-aware dependency injection container utilities."""

from __future__ import annotations

from src.bot.services.supreme_assembly_service_result import SupremeAssemblyServiceResult
from src.bot.services.transfer_service import TransferService
from src.db.gateway.supreme_assembly_governance import (
    SupremeAssemblyGovernanceGateway,
)
from src.infra.di.container import DependencyContainer
from src.infra.di.lifecycle import Lifecycle


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
        # SupremeAssemblyServiceResult - depends on SupremeAssemblyGovernanceGateway
        # and TransferService
        self._base.register(
            SupremeAssemblyServiceResult,
            factory=lambda: SupremeAssemblyServiceResult(
                gateway=self._base.resolve(SupremeAssemblyGovernanceGateway),
                transfer_service=self._base.resolve(TransferService),
            ),
            lifecycle=Lifecycle.SINGLETON,
        )


__all__ = ["ResultContainer"]
