from __future__ import annotations

import asyncio
import json
import os
from typing import TYPE_CHECKING, Any, cast
from weakref import WeakKeyDictionary

import asyncpg
import structlog
from dotenv import load_dotenv

from src.config.db_settings import PoolConfig

LOGGER = structlog.get_logger(__name__)

if TYPE_CHECKING:
    # 僅供型別檢查使用；避免 AsyncPG 沒有完整型別時回退為 Any
    from asyncpg.connection import Connection as _AsyncpgConnection
else:  # pragma: no cover - runtime 分支
    from asyncpg import connection as _asyncpg_connection

    _AsyncpgConnection = _asyncpg_connection.Connection


class _PatchedConnection(_AsyncpgConnection):  # type: ignore[misc]
    """Work around asyncpg restriction: prepared statements cannot contain multiple
    commands separated by semicolons. Some tests issue a single execute() call with
    multiple `SELECT ...; SELECT ...;` statements and one parameter list.

    We split such multi-statements and execute them sequentially with the same
    arguments. Return the last statement's status to preserve execute() contract.
    """

    async def execute(
        self,
        query: str,
        *args: object,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> str:
        q = query.strip()
        # Heuristic: treat as multi-statement if contains a semicolon and positional
        # parameters (e.g. $1). Avoid splitting when no semicolon or it's a single stmt.
        if ";" in q and "$" in q:
            statements = [s.strip() for s in q.split(";") if s.strip()]
            status: str | None = None
            for stmt in statements:
                # 以 Any 呼叫父類別 execute，避免第三方型別資訊不完整導致 Unknown 診斷
                _super: Any = super()
                if timeout is None:
                    status = await _super.execute(stmt, *args)
                else:
                    status = await _super.execute(stmt, *args, timeout=timeout)
            return status or ""
        _super2: Any = super()
        if timeout is None:
            return cast(str, await _super2.execute(query, *args))
        return cast(str, await _super2.execute(query, *args, timeout=timeout))


_POOL_LOCKS: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = WeakKeyDictionary()
_POOLS: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncpg.Pool]" = WeakKeyDictionary()
_last_pool: asyncpg.Pool | None = None


async def init_pool(config: PoolConfig | None = None) -> asyncpg.Pool:
    """Initialise the asyncpg pool if it does not already exist."""
    global _last_pool
    loop = asyncio.get_running_loop()
    existing = _POOLS.get(loop)
    if existing is not None:
        _last_pool = existing
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

        _apg = cast(Any, asyncpg)
        pool = await _apg.create_pool(
            dsn=pool_config.dsn,
            min_size=pool_config.min_size,
            max_size=pool_config.max_size,
            init=_configure_connection,
            connection_class=_PatchedConnection,
        )
        _POOLS[loop] = pool
        _last_pool = pool
        # Best-effort: ensure DB schema is migrated for tests/first-run environments.
        # Contract tests may run before dedicated DB test migrations; auto-upgrade here.
        try:
            async with pool.acquire() as _conn:
                conn = cast(asyncpg.Connection, _conn)
                from typing import Any as _Any
                from typing import cast as _cast

                _conn_any = _cast(_Any, conn)
                exists_obj = _cast(
                    object | None,
                    await _conn_any.fetchval(
                        "SELECT to_regclass('economy.guild_member_balances') IS NOT NULL"
                    ),
                )
                exists: bool = bool(exists_obj)
                if not exists:
                    # Attempt to run Alembic upgrade if available in PATH
                    LOGGER.info("db.pool.auto_migrate.start")
                    try:
                        proc = await asyncio.create_subprocess_exec("alembic", "upgrade", "head")
                        rc = await proc.wait()
                        if rc == 0:
                            LOGGER.info("db.pool.auto_migrate.done")
                        else:
                            LOGGER.warning("db.pool.auto_migrate.failed", code=rc)
                    except Exception as exc:  # pragma: no cover - best-effort only
                        LOGGER.warning("db.pool.auto_migrate.failed", error=str(exc))
        except Exception as exc:  # pragma: no cover - non-fatal
            LOGGER.warning("db.pool.schema_check_failed", error=str(exc))

        LOGGER.info(
            "db.pool.initialised",
            min_size=pool_config.min_size,
            max_size=pool_config.max_size,
        )
        return pool


def get_pool() -> asyncpg.Pool:
    """Return the active pool or raise if it has not been initialised."""
    loop = _maybe_get_running_loop()
    if loop is not None:
        pool = _POOLS.get(loop)
        if pool is not None:
            return pool
    if _last_pool is not None:
        return _last_pool
    raise RuntimeError("Database pool not initialised. Call init_pool() first.")


async def close_pool() -> None:
    """Close the pool if one exists."""
    global _last_pool
    loop = asyncio.get_running_loop()
    lock = _get_pool_lock(loop)

    async with lock:
        pool = _POOLS.pop(loop, None)

    if pool is not None:
        await pool.close()
        if _last_pool is pool:
            _last_pool = None
        LOGGER.info("db.pool.closed")


def _get_pool_lock(loop: asyncio.AbstractEventLoop | None = None) -> asyncio.Lock:
    if loop is None:
        loop = asyncio.get_running_loop()
    lock = _POOL_LOCKS.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _POOL_LOCKS[loop] = lock
    return lock


def _maybe_get_running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


async def _configure_connection(connection: asyncpg.Connection) -> None:
    # cast to Any 以避免第三方套件型別提示不完整造成的 reportUnknownMemberType 警告
    from typing import Any as _Any

    _conn_any = cast(_Any, connection)
    await _conn_any.set_type_codec(
        "json",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
        format="text",
    )
    await _conn_any.set_type_codec(
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
            await _conn_any.execute(
                "SELECT set_config('app.transfer_daily_limit', $1, true)", daily_limit
            )
        except Exception as exc:  # 防禦性：不阻斷連線建立
            LOGGER.warning("db.pool.set_guc_failed", key="app.transfer_daily_limit", error=str(exc))
