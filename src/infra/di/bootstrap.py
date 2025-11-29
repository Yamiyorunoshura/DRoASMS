"""Bootstrap function for setting up dependency injection container."""

from __future__ import annotations

import os

import asyncpg
from dotenv import load_dotenv

from src.bot.services.adjustment_service import AdjustmentService
from src.bot.services.balance_service import BalanceService
from src.bot.services.company_service import CompanyService
from src.bot.services.council_service import CouncilService, CouncilServiceResult
from src.bot.services.currency_config_service import CurrencyConfigService
from src.bot.services.department_registry import DepartmentRegistry
from src.bot.services.permission_service import PermissionService
from src.bot.services.state_council_service import StateCouncilService
from src.bot.services.supreme_assembly_service import SupremeAssemblyService
from src.bot.services.transfer_service import TransferService
from src.db import pool as db_pool
from src.db.gateway.business_license import BusinessLicenseGateway
from src.db.gateway.company import CompanyGateway
from src.db.gateway.council_governance import CouncilGovernanceGateway
from src.db.gateway.economy_adjustments import EconomyAdjustmentGateway
from src.db.gateway.economy_configuration import EconomyConfigurationGateway
from src.db.gateway.economy_pending_transfers import PendingTransferGateway
from src.db.gateway.economy_queries import EconomyQueryGateway
from src.db.gateway.economy_transfers import EconomyTransferGateway
from src.db.gateway.state_council_governance import StateCouncilGovernanceGateway
from src.db.gateway.supreme_assembly_governance import (
    SupremeAssemblyGovernanceGateway,
)
from src.infra.di.container import DependencyContainer
from src.infra.di.lifecycle import Lifecycle
from src.infra.di.result_container import ResultContainer


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
    container.register(EconomyConfigurationGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(EconomyQueryGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(EconomyTransferGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(PendingTransferGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(StateCouncilGovernanceGateway, lifecycle=Lifecycle.SINGLETON)
    # Supreme Assembly governance (new)
    container.register(SupremeAssemblyGovernanceGateway, lifecycle=Lifecycle.SINGLETON)
    # Company governance (business entity management)
    container.register(CompanyGateway, lifecycle=Lifecycle.SINGLETON)

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

    # BalanceService depends on pool and EconomyQueryGateway
    def create_balance_service() -> BalanceService:
        pool = container.resolve(asyncpg.Pool)
        econ_q = container.resolve(EconomyQueryGateway)
        return BalanceService(pool, gateway=econ_q)

    container.register(
        BalanceService, factory=create_balance_service, lifecycle=Lifecycle.SINGLETON
    )

    # AdjustmentService depends on pool and optional gateway
    def create_adjustment_service() -> AdjustmentService:
        pool = container.resolve(asyncpg.Pool)
        return AdjustmentService(pool)

    container.register(
        AdjustmentService, factory=create_adjustment_service, lifecycle=Lifecycle.SINGLETON
    )

    # CurrencyConfigService depends on pool and EconomyConfigurationGateway
    def create_currency_config_service() -> CurrencyConfigService:
        pool = container.resolve(asyncpg.Pool)
        econ_cfg = container.resolve(EconomyConfigurationGateway)
        return CurrencyConfigService(pool, gateway=econ_cfg)

    container.register(
        CurrencyConfigService, factory=create_currency_config_service, lifecycle=Lifecycle.SINGLETON
    )

    # CompanyService depends on pool and company gateway
    def create_company_service() -> CompanyService:
        pool = container.resolve(asyncpg.Pool)
        gateway = container.resolve(CompanyGateway)
        return CompanyService(pool, gateway=gateway)

    container.register(
        CompanyService, factory=create_company_service, lifecycle=Lifecycle.SINGLETON
    )

    # CouncilService depends on optional gateway and transfer_service
    def create_council_service() -> CouncilService:
        transfer_service = container.resolve(TransferService)
        return CouncilService(transfer_service=transfer_service)

    container.register(
        CouncilService, factory=create_council_service, lifecycle=Lifecycle.SINGLETON
    )

    # StateCouncilService depends on gateways and services (strict DI)
    def create_state_council_service() -> StateCouncilService:
        transfer_service = container.resolve(TransferService)
        adjustment_service = container.resolve(AdjustmentService)
        sc_gw = container.resolve(StateCouncilGovernanceGateway)
        econ_q = container.resolve(EconomyQueryGateway)
        registry = container.resolve(DepartmentRegistry)
        license_gw = container.resolve(BusinessLicenseGateway)
        return StateCouncilService(
            gateway=sc_gw,
            transfer_service=transfer_service,
            adjustment_service=adjustment_service,
            department_registry=registry,
            business_license_gateway=license_gw,
            economy_gateway=econ_q,
        )

    container.register(
        StateCouncilService, factory=create_state_council_service, lifecycle=Lifecycle.SINGLETON
    )

    # SupremeAssemblyService registration
    container.register(SupremeAssemblyService, lifecycle=Lifecycle.SINGLETON)

    # Register additional singletons required by strict DI
    container.register(DepartmentRegistry, lifecycle=Lifecycle.SINGLETON)
    container.register(BusinessLicenseGateway, lifecycle=Lifecycle.SINGLETON)

    # Validation: ensure all critical resolutions succeed at bootstrap
    _ = container.resolve(TransferService)
    _ = container.resolve(BalanceService)
    _ = container.resolve(CurrencyConfigService)
    _ = container.resolve(CompanyService)
    _ = container.resolve(StateCouncilService)
    _ = container.resolve(CouncilService)
    _ = container.resolve(SupremeAssemblyService)

    return container


def bootstrap_result_container() -> tuple[DependencyContainer, ResultContainer]:
    """Bootstrap container with both traditional and Result-based services.

    This function creates a DependencyContainer with all traditional services
    and a ResultContainer wrapper that provides Result-based service implementations.

    Returns:
        Tuple of (base_container, result_container)
    """
    # First create the base container with traditional services
    base_container = bootstrap_container()

    # Create Result container wrapper
    result_container = ResultContainer(base_container)

    # Register Result-based services
    result_container.register_result_services()

    # PermissionService uses unified StateCouncilService
    def create_result_permission_service() -> PermissionService:
        council_result = base_container.resolve(CouncilServiceResult)
        state_council_service = base_container.resolve(StateCouncilService)
        supreme_assembly_service = base_container.resolve(SupremeAssemblyService)
        return PermissionService(
            council_service=council_result,
            state_council_service=state_council_service,
            supreme_assembly_service=supreme_assembly_service,
        )

    base_container.register(
        PermissionService,
        factory=create_result_permission_service,
        lifecycle=Lifecycle.SINGLETON,
    )

    return base_container, result_container
