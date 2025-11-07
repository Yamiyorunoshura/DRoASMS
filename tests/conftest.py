from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from faker import Faker

from src.config.db_settings import PoolConfig
from src.db.pool import close_pool, init_pool
from src.infra.di.container import DependencyContainer


@pytest.fixture
def faker() -> Faker:
    """Provide a Faker instance with Chinese and English locales for test data generation."""
    return Faker(["zh_TW", "en_US"])


@pytest_asyncio.fixture
async def db_pool() -> AsyncIterator[asyncpg.Pool]:
    """Initialise the shared asyncpg pool for database-centric tests."""
    try:
        load_dotenv(override=False)
        config = PoolConfig.model_validate({})  # Load from environment variables
    except (ValueError, RuntimeError) as exc:
        pytest.skip(f"Skipping database tests: {exc}")

    pool = await init_pool(config)
    try:
        yield pool
    finally:
        # Ensure all connections are properly closed
        await close_pool()
        # Give a small delay to ensure cleanup completes
        await asyncio.sleep(0.1)


@pytest_asyncio.fixture
async def db_connection(db_pool: asyncpg.Pool) -> AsyncIterator[asyncpg.Connection]:
    """Yield a transaction-scoped connection for database tests."""
    async with db_pool.acquire() as connection:
        transaction = connection.transaction()
        await transaction.start()
        try:
            yield connection
        finally:
            # Ensure transaction is rolled back
            try:
                await transaction.rollback()
            except Exception:
                pass  # Ignore errors during rollback cleanup


@pytest.fixture
def docker_compose_project() -> str:
    """Provide a unique Docker Compose project name for test isolation."""
    # Generate a unique project name using test session and random suffix
    test_id = secrets.token_hex(4)
    return f"droasms-test-{test_id}"


@pytest_asyncio.fixture
async def async_coordinator_cleanup() -> AsyncIterator[None]:
    """Fixture to ensure all async coordinators are cleaned up after tests."""
    coordinators: list[object] = []
    try:
        yield coordinators
    finally:
        # Cleanup all registered coordinators
        for coordinator in coordinators:
            if hasattr(coordinator, "stop"):
                try:
                    # Add timeout protection
                    await asyncio.wait_for(coordinator.stop(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Force cancel if timeout
                    if hasattr(coordinator, "_cleanup_task") and coordinator._cleanup_task:
                        coordinator._cleanup_task.cancel()
                except Exception:
                    pass  # Ignore cleanup errors


@pytest_asyncio.fixture
async def di_container(db_pool: asyncpg.Pool) -> DependencyContainer:
    """Provide a dependency injection container configured for testing.

    The container is pre-configured with the test database pool and all services.
    Tests can override registrations by calling container.register() or container.register_instance()
    to replace dependencies with mocks.
    """
    # Create a fresh container and register the test pool
    import os

    import asyncpg
    from dotenv import load_dotenv

    from src.infra.di.container import DependencyContainer
    from src.infra.di.lifecycle import Lifecycle

    container = DependencyContainer()

    # Register the test database pool
    container.register_instance(asyncpg.Pool, db_pool)

    # Register gateways (stateless, can be singletons)
    from src.db.gateway.council_governance import CouncilGovernanceGateway
    from src.db.gateway.economy_adjustments import EconomyAdjustmentGateway
    from src.db.gateway.economy_pending_transfers import PendingTransferGateway
    from src.db.gateway.economy_queries import EconomyQueryGateway
    from src.db.gateway.economy_transfers import EconomyTransferGateway
    from src.db.gateway.state_council_governance import StateCouncilGovernanceGateway

    container.register(CouncilGovernanceGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(EconomyAdjustmentGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(EconomyQueryGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(EconomyTransferGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(PendingTransferGateway, lifecycle=Lifecycle.SINGLETON)
    container.register(StateCouncilGovernanceGateway, lifecycle=Lifecycle.SINGLETON)

    # Register services with dependencies
    from src.bot.services.adjustment_service import AdjustmentService
    from src.bot.services.balance_service import BalanceService
    from src.bot.services.council_service import CouncilService
    from src.bot.services.state_council_service import StateCouncilService
    from src.bot.services.transfer_service import TransferService

    load_dotenv(override=False)
    event_pool_enabled = os.getenv("TRANSFER_EVENT_POOL_ENABLED", "false").lower() == "true"

    def create_transfer_service() -> TransferService:
        pool = container.resolve(asyncpg.Pool)
        return TransferService(pool, event_pool_enabled=event_pool_enabled)

    container.register(
        TransferService, factory=create_transfer_service, lifecycle=Lifecycle.SINGLETON
    )
    container.register(BalanceService, lifecycle=Lifecycle.SINGLETON)
    container.register(AdjustmentService, lifecycle=Lifecycle.SINGLETON)
    container.register(CouncilService, lifecycle=Lifecycle.SINGLETON)
    container.register(StateCouncilService, lifecycle=Lifecycle.SINGLETON)

    return container
