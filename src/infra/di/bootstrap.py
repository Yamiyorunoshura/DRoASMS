"""Bootstrap function for setting up dependency injection container."""

from __future__ import annotations

import os

import asyncpg
from dotenv import load_dotenv

from src.bot.services.adjustment_service import AdjustmentService
from src.bot.services.balance_service import BalanceService
from src.bot.services.council_service import CouncilService
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.transfer_service import TransferService
from src.db import pool as db_pool
from src.db.gateway.council_governance import CouncilGovernanceGateway
from src.db.gateway.economy_adjustments import EconomyAdjustmentGateway
from src.db.gateway.economy_pending_transfers import PendingTransferGateway
from src.db.gateway.economy_queries import EconomyQueryGateway
from src.db.gateway.economy_transfers import EconomyTransferGateway
from src.db.gateway.state_council_governance import StateCouncilGovernanceGateway
from src.infra.di.container import DependencyContainer
from src.infra.di.lifecycle import Lifecycle


def bootstrap_container() -> DependencyContainer:
    """Bootstrap and configure the dependency injection container.

    This function registers all core infrastructure and service dependencies.
    The database pool must be initialized before calling this function.

    Returns:
        A configured DependencyContainer instance.
    """
    container = DependencyContainer()

    # Register database pool (must be initialized before this call)
    container.register_instance(asyncpg.Pool, db_pool.get_pool())

    # Register gateways (stateless, can be singletons)
    container.register(CouncilGovernanceGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(EconomyAdjustmentGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(EconomyQueryGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(EconomyTransferGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(PendingTransferGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(StateCouncilGovernanceGateway, lifecycle=Lifecycle.SINGLETON)

    # Register services with dependencies
    # TransferService needs pool and event_pool_enabled flag
    load_dotenv(override=False)
    event_pool_enabled = os.getenv("TRANSFER_EVENT_POOL_ENABLED", "false").lower() == "true"

    def create_transfer_service() -> TransferService:
        pool = container.resolve(asyncpg.Pool)
        return TransferService(pool, event_pool_enabled=event_pool_enabled)

    container.register(
        TransferService, factory=create_transfer_service, lifecycle=Lifecycle.SINGLETON
    )

    # BalanceService depends on pool and optional gateway
    container.register(BalanceService, lifecycle=Lifecycle.SINGLETON)

    # AdjustmentService depends on pool and optional gateway
    container.register(AdjustmentService, lifecycle=Lifecycle.SINGLETON)

    # CouncilService depends on optional gateway and transfer_service
    container.register(CouncilService, lifecycle=Lifecycle.SINGLETON)

    # StateCouncilService depends on optional gateway, transfer_service, and adjustment_service
    container.register(StateCouncilService, lifecycle=Lifecycle.SINGLETON)

    return container
