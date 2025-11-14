from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from src.cython_ext.economy_balance_models import (
    BalanceSnapshot,
    make_balance_snapshot,
)
from src.cython_ext.economy_transfer_models import (
    build_transfer_procedure_result,
    transfer_result_from_procedure,
)
from src.cython_ext.pending_transfer_models import build_pending_transfer
from src.cython_ext.transfer_pool_core import TransferCheckStateStore


@pytest.mark.performance
def test_balance_snapshot_instantiation_speed() -> None:
    """Ensure we can rapidly instantiate snapshots."""
    iterations = 5000
    start = time.perf_counter()
    for _ in range(iterations):
        BalanceSnapshot(guild_id=1, member_id=2, balance=3)
    duration = time.perf_counter() - start
    assert duration < 0.35, f"expected <0.35s, got {duration:.3f}s"


@pytest.mark.performance
def test_transfer_check_state_store_scaling() -> None:
    """Ensure the check state store handles many updates quickly."""
    store = TransferCheckStateStore()
    transfer_id = uuid4()
    start = time.perf_counter()
    for _ in range(2000):
        for check in ("balance", "cooldown", "daily_limit"):
            store.record(transfer_id, check, 1)
        store.remove(transfer_id)
    duration = time.perf_counter() - start
    assert duration < 0.4, f"state tracker updates too slow: {duration:.3f}s"


def test_balance_snapshot_memory_profile() -> None:
    snapshot = BalanceSnapshot(guild_id=99, member_id=42, balance=123)
    assert not hasattr(snapshot, "__dict__")
    assert snapshot.balance == 123


def test_transfer_result_conversion_isolated_metadata() -> None:
    payload = {
        "transaction_id": uuid4(),
        "guild_id": 1,
        "initiator_id": 2,
        "target_id": 3,
        "amount": 50,
        "direction": "transfer",
        "created_at": datetime.now(timezone.utc),
        "initiator_balance": 900,
        "target_balance": None,
        "throttled_until": None,
        "metadata": {"note": "gift"},
    }
    procedure = build_transfer_procedure_result(payload)
    result = transfer_result_from_procedure(procedure)
    payload["metadata"]["note"] = "tampered"
    assert result.metadata["note"] == "gift"
    assert result.target_balance == 0


def test_pending_transfer_builder_handles_dict_input() -> None:
    now = datetime.now(timezone.utc)
    record = {
        "transfer_id": uuid4(),
        "guild_id": 1,
        "initiator_id": 2,
        "target_id": 3,
        "amount": 100,
        "status": "pending",
        "checks": {"cooldown": 1},
        "retry_count": 0,
        "expires_at": now,
        "metadata": {"reason": "demo"},
        "created_at": now,
        "updated_at": now,
    }
    pending = build_pending_transfer(record)
    assert pending.guild_id == 1
    assert pending.metadata["reason"] == "demo"


def test_make_balance_snapshot_from_record_object() -> None:
    record = SimpleNamespace(
        guild_id=1,
        member_id=2,
        balance=3,
        last_modified_at=datetime.now(timezone.utc),
        throttled_until=None,
    )
    snapshot = make_balance_snapshot(record)
    assert snapshot.member_id == 2


def test_pyproject_contains_new_cython_targets() -> None:
    pyproject = Path("pyproject.toml").read_bytes()
    data = tomllib.loads(pyproject.decode("utf-8"))
    targets = {entry["name"] for entry in data["tool"]["cython-compiler"]["targets"]}
    expected = {
        "economy-balance-models",
        "economy-transfer-models",
        "economy-adjustment-models",
        "pending-transfer-models",
        "transfer-pool-core",
        "state-council-models",
    }
    assert expected.issubset(targets)
