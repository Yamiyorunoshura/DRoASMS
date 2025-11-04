from __future__ import annotations

import asyncio
import json
import os
from typing import cast
from weakref import WeakKeyDictionary

import asyncpg
import structlog
from dotenv import load_dotenv

from src.config.db_settings import PoolConfig

LOGGER = structlog.get_logger(__name__)


class _PatchedConnection(asyncpg.Connection):  # type: ignore[misc]
    """Work around asyncpg restriction: prepared statements cannot contain multiple
    commands separated by semicolons. Some tests issue a single execute() call with
    multiple `SELECT ...; SELECT ...;` statements and one parameter list.

    We split such multi-statements and execute them sequentially with the same
    arguments. Return the last statement's status to preserve execute() contract.
    """

    async def execute(self, query: str, *args: object) -> str:
        q = query.strip()
        # Heuristic: treat as multi-statement if contains a semicolon and positional
        # parameters (e.g. $1). Avoid splitting when no semicolon or it's a single stmt.
        if ";" in q and "$" in q:
            statements = [s.strip() for s in q.split(";") if s.strip()]
            status: str | None = None
            for stmt in statements:
                status = await super().execute(stmt, *args)
            return status or ""
        return cast(str, await super().execute(query, *args))


_POOL_LOCKS: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = WeakKeyDictionary()
_POOLS: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncpg.Pool]" = WeakKeyDictionary()


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

        if config is None:
            # Load .env file manually for compatibility with existing code
            load_dotenv(override=False)
            pool_config = PoolConfig.model_validate({})  # Load from environment variables
        else:
            pool_config = config

        kwargs: dict[str, object] = {
            "dsn": pool_config.dsn,
            "min_size": pool_config.min_size,
            "max_size": pool_config.max_size,
        }
        if pool_config.timeout is not None:
            kwargs["timeout"] = pool_config.timeout

        pool = await asyncpg.create_pool(
            init=_configure_connection,
            connection_class=_PatchedConnection,
            **kwargs,
        )
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
    # 允許以環境變數覆寫每日轉帳上限，供 DB 函式透過 GUC 讀取
    daily_limit = os.getenv("TRANSFER_DAILY_LIMIT")
    if daily_limit:
        try:
            int(daily_limit)  # 驗證可解析為整數
            await connection.execute(
                "SELECT set_config('app.transfer_daily_limit', $1, true)", daily_limit
            )
        except Exception as exc:  # 防禦性：不阻斷連線建立
            LOGGER.warning("db.pool.set_guc_failed", key="app.transfer_daily_limit", error=str(exc))
