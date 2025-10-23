from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from weakref import WeakKeyDictionary

import asyncpg
import structlog

LOGGER = structlog.get_logger(__name__)

_POOL_LOCKS: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = WeakKeyDictionary()
_POOLS: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncpg.Pool]" = WeakKeyDictionary()


@dataclass(frozen=True, slots=True)
class PoolConfig:
    """Configuration for the asyncpg connection pool."""

    dsn: str
    min_size: int = 1
    max_size: int = 10
    timeout: float | None = None

    @classmethod
    def from_env(cls) -> "PoolConfig":
        """Create a configuration object by reading environment variables."""
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL is not set; cannot initialise the database pool.")

        min_size = _int_from_env("DB_POOL_MIN_SIZE", default=1)
        max_size = _int_from_env("DB_POOL_MAX_SIZE", default=10)
        timeout = _float_from_env("DB_POOL_TIMEOUT_SECONDS")

        if max_size < min_size:
            raise RuntimeError(
                "DB_POOL_MAX_SIZE must be greater than or equal to DB_POOL_MIN_SIZE."
            )

        return cls(dsn=dsn, min_size=min_size, max_size=max_size, timeout=timeout)


async def init_pool(config: PoolConfig | None = None) -> asyncpg.Pool:
    """Initialise the asyncpg pool if it does not already exist."""
    loop = asyncio.get_running_loop()
    existing = _POOLS.get(loop)
    if existing is not None:
        return existing

    lock = _get_pool_lock(loop)

    async with lock:
        pool = _POOLS.get(loop)
        if pool is not None:
            return pool

        pool_config = config or PoolConfig.from_env()
        kwargs: dict[str, object] = {
            "dsn": pool_config.dsn,
            "min_size": pool_config.min_size,
            "max_size": pool_config.max_size,
        }
        if pool_config.timeout is not None:
            kwargs["timeout"] = pool_config.timeout

        pool = await asyncpg.create_pool(init=_configure_connection, **kwargs)
        _POOLS[loop] = pool
        LOGGER.info(
            "db.pool.initialised",
            min_size=pool_config.min_size,
            max_size=pool_config.max_size,
        )
        return pool


def get_pool() -> asyncpg.Pool:
    """Return the active pool or raise if it has not been initialised."""
    loop = asyncio.get_running_loop()
    pool = _POOLS.get(loop)
    if pool is None:
        raise RuntimeError("Database pool not initialised. Call init_pool() first.")
    return pool


async def close_pool() -> None:
    """Close the pool if one exists."""
    loop = asyncio.get_running_loop()
    lock = _get_pool_lock(loop)

    async with lock:
        pool = _POOLS.pop(loop, None)

    if pool is not None:
        await pool.close()
        LOGGER.info("db.pool.closed")


def _int_from_env(name: str, *, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer.") from exc


def _float_from_env(name: str) -> float | None:
    value = os.getenv(name)
    if value is None:
        return None

    try:
        return float(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be a float.") from exc


def _get_pool_lock(loop: asyncio.AbstractEventLoop | None = None) -> asyncio.Lock:
    if loop is None:
        loop = asyncio.get_running_loop()
    lock = _POOL_LOCKS.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _POOL_LOCKS[loop] = lock
    return lock


async def _configure_connection(connection: asyncpg.Connection) -> None:
    await connection.set_type_codec(
        "json",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
        format="text",
    )
    await connection.set_type_codec(
        "jsonb",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
        format="text",
    )
