from __future__ import annotations

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
        await close_pool()


@pytest_asyncio.fixture
async def db_connection(db_pool: asyncpg.Pool) -> AsyncIterator[asyncpg.Connection]:
    """Yield a transaction-scoped connection for database tests."""
    async with db_pool.acquire() as connection:
        transaction = connection.transaction()
        await transaction.start()
        try:
            yield connection
        finally:
            await transaction.rollback()
