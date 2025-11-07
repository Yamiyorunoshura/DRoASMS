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
