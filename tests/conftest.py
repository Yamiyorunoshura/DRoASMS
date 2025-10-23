from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from src.db.pool import PoolConfig, close_pool, init_pool


@pytest_asyncio.fixture
async def db_pool() -> AsyncIterator[asyncpg.Pool]:
    """Initialise the shared asyncpg pool for database-centric tests."""
    try:
        config = PoolConfig.from_env()
    except RuntimeError as exc:
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
