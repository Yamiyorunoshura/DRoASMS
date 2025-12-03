from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pytest

from src.config.db_settings import PoolConfig
from src.db import pool as pool_module


class _DummyAcquire:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


class _DummyConnection:
    def __init__(self, *, exists: bool) -> None:
        self.exists = exists
        self.fetchval_calls: list[str] = []

    async def fetchval(self, query: str) -> bool:
        self.fetchval_calls.append(query)
        # 模擬 `SELECT to_regclass(...) IS NOT NULL` 的回傳值
        return self.exists


class _DummyPool:
    def __init__(self, conn: _DummyConnection) -> None:
        self._conn = conn
        self.closed = False

    def acquire(self) -> _DummyAcquire:
        return _DummyAcquire(self._conn)

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_init_pool_uses_config_and_reuses_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    # 重置模組層級狀態，避免與其他測試互相干擾
    pool_module._POOL_LOCKS.clear()
    pool_module._POOLS.clear()
    pool_module._last_pool = None

    dummy_conn = _DummyConnection(exists=True)
    created_args: list[dict[str, Any]] = []

    async def fake_create_pool(**kwargs: Any) -> _DummyPool:
        created_args.append(kwargs)
        return _DummyPool(dummy_conn)

    monkeypatch.setattr(pool_module.asyncpg, "create_pool", fake_create_pool)

    cfg = PoolConfig.model_validate(
        {
            "DATABASE_URL": "postgresql://test-db",
            "DB_POOL_MIN_SIZE": 2,
            "DB_POOL_MAX_SIZE": 4,
            "DB_POOL_TIMEOUT_SECONDS": None,
        }
    )

    pool1 = await pool_module.init_pool(cfg)
    pool2 = await pool_module.init_pool(cfg)

    # create_pool 僅被呼叫一次，第二次呼叫 init_pool 應重用既有 pool
    assert pool1 is pool2
    assert len(created_args) == 1

    args = created_args[0]
    assert args["dsn"] == cfg.dsn
    assert args["min_size"] == cfg.min_size
    assert args["max_size"] == cfg.max_size
    # 確認傳入的 init 回呼與 connection_class 皆來自 pool 模組
    assert args["init"] is pool_module._configure_connection
    assert args["connection_class"] is pool_module._PatchedConnection


@pytest.mark.asyncio
async def test_get_pool_and_close_pool_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    pool_module._POOL_LOCKS.clear()
    pool_module._POOLS.clear()
    pool_module._last_pool = None

    dummy_conn = _DummyConnection(exists=True)
    dummy_pool = _DummyPool(dummy_conn)

    async def fake_create_pool(**_: Any) -> _DummyPool:  # pragma: no cover - trivial wrapper
        return dummy_pool

    monkeypatch.setattr(pool_module.asyncpg, "create_pool", fake_create_pool)

    cfg = PoolConfig.model_validate(
        {
            "DATABASE_URL": "postgresql://test-db",
            "DB_POOL_MIN_SIZE": 1,
            "DB_POOL_MAX_SIZE": 1,
            "DB_POOL_TIMEOUT_SECONDS": None,
        }
    )

    # 建立並取得 pool
    pool = await pool_module.init_pool(cfg)
    assert pool is dummy_pool

    # get_pool 應回傳相同實例
    same_pool = pool_module.get_pool()
    assert same_pool is dummy_pool

    # 關閉 pool 後，_last_pool 也應被清空
    await pool_module.close_pool()
    assert dummy_pool.closed is True
    assert pool_module._last_pool is None

    # 再次呼叫 get_pool 應丟出錯誤
    with pytest.raises(RuntimeError):
        pool_module.get_pool()


@pytest.mark.asyncio
async def test_configure_connection_sets_codecs_and_guc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @dataclass
    class ConnRecorder:
        codecs: list[tuple[str, str, str]] = None  # type: ignore[assignment]
        executed: list[tuple[str, tuple[Any, ...]]] = None  # type: ignore[assignment]

        def __post_init__(self) -> None:
            self.codecs = []
            self.executed = []

        async def set_type_codec(
            self,
            name: str,
            *,
            schema: str,
            encoder: Callable[[Any], str],
            decoder: Callable[[str], Any],
            format: str,
        ) -> None:
            # 僅記錄呼叫參數，實際編碼／解碼交由 asyncpg 自行處理
            self.codecs.append((name, schema, format))

        async def execute(self, query: str, *args: Any) -> None:
            self.executed.append((query, args))

    conn = ConnRecorder()
    monkeypatch.setenv("TRANSFER_DAILY_LIMIT", "123")

    await pool_module._configure_connection(conn)  # type: ignore[arg-type]

    # 應註冊 json / jsonb 兩種型別編碼器
    assert ("json", "pg_catalog", "text") in conn.codecs
    assert ("jsonb", "pg_catalog", "text") in conn.codecs

    # 應根據 TRANSFER_DAILY_LIMIT 建立 GUC
    assert any("set_config('app.transfer_daily_limit'" in q for (q, _args) in conn.executed)
