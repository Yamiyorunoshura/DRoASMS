"""Result-aware dependency injection container utilities."""

from __future__ import annotations

from src.bot.services.council_service_result import CouncilServiceResult
from src.bot.services.state_council_service_result import StateCouncilServiceResult
from src.bot.services.transfer_service import TransferService
from src.db.gateway.council_governance import CouncilGovernanceGateway
from src.db.gateway.state_council_governance import StateCouncilGovernanceGateway
from src.infra.di.container import DependencyContainer
from src.infra.di.lifecycle import Lifecycle


class ResultContainer:
    """Wrapper around DependencyContainer that provides Result-based services."""

    def __init__(self, base_container: DependencyContainer) -> None:
        """Initialize with a base container."""
        self._base = base_container

    def register_result_services(self) -> None:
        """Register Result-based service implementations."""
        # CouncilServiceResult - depends on CouncilGovernanceGateway and TransferService
        self._base.register(
            CouncilServiceResult,
            factory=lambda: CouncilServiceResult(
                gateway=self._base.resolve(CouncilGovernanceGateway),
                transfer_service=self._base.resolve(TransferService),
            ),
            lifecycle=Lifecycle.SINGLETON,
        )

        # StateCouncilServiceResult - depends on StateCouncilGovernanceGateway and other services
        self._base.register(
            StateCouncilServiceResult,
            factory=lambda: StateCouncilServiceResult(
                gateway=self._base.resolve(StateCouncilGovernanceGateway),
                transfer_service=self._base.resolve(TransferService),
            ),
            lifecycle=Lifecycle.SINGLETON,
        )


__all__ = ["ResultContainer"]
