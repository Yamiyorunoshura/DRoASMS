from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from faker import Faker

from src.cython_ext.economy_adjustment_models import (
    AdjustmentProcedureResult,
    AdjustmentResult,
    adjustment_result_from_procedure,
    build_adjustment_procedure_result,
)
from src.cython_ext.economy_balance_models import (
    BalanceSnapshot,
    HistoryEntry,
    HistoryPage,
    ensure_view_permission,
    make_balance_snapshot,
    make_history_entry,
)
from src.cython_ext.economy_transfer_models import (
    TransferProcedureResult,
    TransferResult,
    build_transfer_procedure_result,
    transfer_result_from_procedure,
)
from src.cython_ext.pending_transfer_models import PendingTransfer, build_pending_transfer

# ==================== AdjustmentProcedureResult Tests ====================


@pytest.mark.unit
def test_adjustment_procedure_result_initialization(faker: Faker) -> None:
    """測試 AdjustmentProcedureResult 基本初始化"""
    transaction_id = uuid4()
    guild_id = faker.random_int(min=1)
    admin_id = faker.random_int(min=1)
    target_id = faker.random_int(min=1)
    amount = faker.random_int(min=1, max=1000000)
    direction = faker.random_element(["add", "remove"])
    created_at = datetime.now(timezone.utc)
    target_balance_after = faker.random_int(min=0, max=1000000)
    metadata = {"reason": faker.sentence()}

    result = AdjustmentProcedureResult(
        transaction_id=transaction_id,
        guild_id=guild_id,
        admin_id=admin_id,
        target_id=target_id,
        amount=amount,
        direction=direction,
        created_at=created_at,
        target_balance_after=target_balance_after,
        metadata=metadata,
    )

    assert result.transaction_id == transaction_id
    assert result.guild_id == guild_id
    assert result.admin_id == admin_id
    assert result.target_id == target_id
    assert result.amount == amount
    assert result.direction == direction
    assert result.created_at == created_at
    assert result.target_balance_after == target_balance_after
    assert result.metadata == metadata


@pytest.mark.unit
def test_adjustment_procedure_result_frozen(faker: Faker) -> None:
    """測試 AdjustmentProcedureResult 是不可變的"""
    result = AdjustmentProcedureResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
        metadata={},
    )

    with pytest.raises(AttributeError):
        result.amount = 999  # type: ignore


@pytest.mark.unit
def test_adjustment_procedure_result_with_empty_metadata(faker: Faker) -> None:
    """測試 AdjustmentProcedureResult 空 metadata"""
    result = AdjustmentProcedureResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
        metadata={},
    )

    assert result.metadata == {}


@pytest.mark.unit
def test_adjustment_procedure_result_with_zero_amount(faker: Faker) -> None:
    """測試 AdjustmentProcedureResult 零金額"""
    result = AdjustmentProcedureResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=0,
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
        metadata={},
    )

    assert result.amount == 0


@pytest.mark.unit
def test_adjustment_procedure_result_with_negative_balance(faker: Faker) -> None:
    """測試 AdjustmentProcedureResult 負餘額"""
    result = AdjustmentProcedureResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="remove",
        created_at=datetime.now(timezone.utc),
        target_balance_after=-100,
        metadata={},
    )

    assert result.target_balance_after == -100


# ==================== AdjustmentResult Tests ====================


@pytest.mark.unit
def test_adjustment_result_initialization(faker: Faker) -> None:
    """測試 AdjustmentResult 基本初始化"""
    transaction_id = uuid4()
    guild_id = faker.random_int(min=1)
    admin_id = faker.random_int(min=1)
    target_id = faker.random_int(min=1)
    amount = faker.random_int(min=1, max=1000000)
    direction = faker.random_element(["add", "remove"])
    created_at = datetime.now(timezone.utc)
    target_balance_after = faker.random_int(min=0, max=1000000)
    metadata = {"reason": faker.sentence()}

    result = AdjustmentResult(
        transaction_id=transaction_id,
        guild_id=guild_id,
        admin_id=admin_id,
        target_id=target_id,
        amount=amount,
        direction=direction,
        created_at=created_at,
        target_balance_after=target_balance_after,
        metadata=metadata,
    )

    assert result.transaction_id == transaction_id
    assert result.guild_id == guild_id
    assert result.admin_id == admin_id
    assert result.target_id == target_id
    assert result.amount == amount
    assert result.direction == direction
    assert result.created_at == created_at
    assert result.target_balance_after == target_balance_after
    assert result.metadata == metadata


@pytest.mark.unit
def test_adjustment_result_frozen(faker: Faker) -> None:
    """測試 AdjustmentResult 是不可變的"""
    result = AdjustmentResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
        metadata={},
    )

    with pytest.raises(AttributeError):
        result.amount = 999  # type: ignore


# ==================== build_adjustment_procedure_result Tests ====================


@pytest.mark.unit
def test_build_adjustment_procedure_result_from_object(faker: Faker) -> None:
    """測試從物件建構 AdjustmentProcedureResult"""
    transaction_id = uuid4()
    record = SimpleNamespace(
        transaction_id=transaction_id,
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
        metadata={"key": "value"},
    )

    result = build_adjustment_procedure_result(record)

    assert isinstance(result, AdjustmentProcedureResult)
    assert result.transaction_id == transaction_id
    assert result.guild_id == record.guild_id
    assert result.metadata == {"key": "value"}


@pytest.mark.unit
def test_build_adjustment_procedure_result_from_dict(faker: Faker) -> None:
    """測試從字典建構 AdjustmentProcedureResult"""
    transaction_id = uuid4()
    record = {
        "transaction_id": transaction_id,
        "guild_id": faker.random_int(),
        "admin_id": faker.random_int(),
        "target_id": faker.random_int(),
        "amount": faker.random_int(),
        "direction": "add",
        "created_at": datetime.now(timezone.utc),
        "target_balance_after": faker.random_int(),
        "metadata": {"key": "value"},
    }

    result = build_adjustment_procedure_result(record)

    assert isinstance(result, AdjustmentProcedureResult)
    assert result.transaction_id == transaction_id
    assert result.metadata == {"key": "value"}


@pytest.mark.unit
def test_build_adjustment_procedure_result_with_none_metadata(faker: Faker) -> None:
    """測試從 None metadata 建構 AdjustmentProcedureResult"""
    record = SimpleNamespace(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
        metadata=None,
    )

    result = build_adjustment_procedure_result(record)

    assert result.metadata == {}


@pytest.mark.unit
def test_build_adjustment_procedure_result_without_metadata(faker: Faker) -> None:
    """測試從缺少 metadata 的記錄建構 AdjustmentProcedureResult"""
    record = SimpleNamespace(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
    )

    result = build_adjustment_procedure_result(record)

    assert result.metadata == {}


@pytest.mark.unit
def test_build_adjustment_procedure_result_type_conversion(faker: Faker) -> None:
    """測試建構時的類型轉換"""
    record = SimpleNamespace(
        transaction_id=uuid4(),
        guild_id="123",  # 字串應該被轉為 int
        admin_id="456",
        target_id="789",
        amount="100",
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after="500",
        metadata={},
    )

    result = build_adjustment_procedure_result(record)

    assert isinstance(result.guild_id, int)
    assert result.guild_id == 123
    assert isinstance(result.admin_id, int)
    assert result.admin_id == 456
    assert isinstance(result.target_id, int)
    assert isinstance(result.amount, int)
    assert isinstance(result.target_balance_after, int)


# ==================== adjustment_result_from_procedure Tests ====================


@pytest.mark.unit
def test_adjustment_result_from_procedure(faker: Faker) -> None:
    """測試從 AdjustmentProcedureResult 轉換為 AdjustmentResult"""
    transaction_id = uuid4()
    procedure_result = AdjustmentProcedureResult(
        transaction_id=transaction_id,
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
        metadata={"key": "value"},
    )

    result = adjustment_result_from_procedure(procedure_result)

    assert isinstance(result, AdjustmentResult)
    assert result.transaction_id == transaction_id
    assert result.guild_id == procedure_result.guild_id
    assert result.metadata == {"key": "value"}


@pytest.mark.unit
def test_adjustment_result_from_procedure_with_none_metadata(faker: Faker) -> None:
    """測試從含 None metadata 的 procedure result 轉換"""
    procedure_result = AdjustmentProcedureResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
        metadata=None,  # type: ignore
    )

    result = adjustment_result_from_procedure(procedure_result)

    assert result.metadata == {}


@pytest.mark.unit
def test_adjustment_result_from_procedure_metadata_copy(faker: Faker) -> None:
    """測試轉換時 metadata 是獨立的副本"""
    metadata = {"key": "value"}
    procedure_result = AdjustmentProcedureResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
        metadata=metadata,
    )

    result = adjustment_result_from_procedure(procedure_result)

    # metadata 應該是副本
    assert result.metadata == metadata
    assert result.metadata is not metadata


# ==================== BalanceSnapshot Tests ====================


@pytest.mark.unit
def test_balance_snapshot_default_initialization() -> None:
    """測試 BalanceSnapshot 默認初始化"""
    snapshot = BalanceSnapshot()

    assert snapshot.guild_id == 0
    assert snapshot.member_id == 0
    assert snapshot.balance == 0
    assert isinstance(snapshot.last_modified_at, datetime)
    assert snapshot.throttled_until is None


@pytest.mark.unit
def test_balance_snapshot_full_initialization(faker: Faker) -> None:
    """測試 BalanceSnapshot 完整初始化"""
    guild_id = faker.random_int(min=1)
    member_id = faker.random_int(min=1)
    balance = faker.random_int(min=0, max=1000000)
    last_modified_at = datetime.now(timezone.utc)
    throttled_until = datetime.now(timezone.utc) + timedelta(hours=1)

    snapshot = BalanceSnapshot(
        guild_id=guild_id,
        member_id=member_id,
        balance=balance,
        last_modified_at=last_modified_at,
        throttled_until=throttled_until,
    )

    assert snapshot.guild_id == guild_id
    assert snapshot.member_id == member_id
    assert snapshot.balance == balance
    assert snapshot.last_modified_at == last_modified_at
    assert snapshot.throttled_until == throttled_until


@pytest.mark.unit
def test_balance_snapshot_is_throttled_property() -> None:
    """測試 BalanceSnapshot.is_throttled 屬性"""
    # 未被節流
    snapshot1 = BalanceSnapshot(throttled_until=None)
    assert snapshot1.is_throttled is False

    # 已過期的節流
    snapshot2 = BalanceSnapshot(throttled_until=datetime.now(timezone.utc) - timedelta(hours=1))
    assert snapshot2.is_throttled is False

    # 仍在節流中
    snapshot3 = BalanceSnapshot(throttled_until=datetime.now(timezone.utc) + timedelta(hours=1))
    assert snapshot3.is_throttled is True


@pytest.mark.unit
def test_balance_snapshot_backward_compatibility_is_throttled_param(faker: Faker) -> None:
    """測試 BalanceSnapshot 向後兼容的 is_throttled 參數"""
    snapshot = BalanceSnapshot(
        guild_id=faker.random_int(),
        member_id=faker.random_int(),
        balance=faker.random_int(),
        is_throttled=True,  # 向後兼容參數，應該被忽略
    )

    # is_throttled 參數不影響實際狀態
    assert snapshot.throttled_until is None
    assert snapshot.is_throttled is False


@pytest.mark.unit
def test_balance_snapshot_frozen(faker: Faker) -> None:
    """測試 BalanceSnapshot 是不可變的"""
    snapshot = BalanceSnapshot(guild_id=faker.random_int())

    with pytest.raises(AttributeError):
        snapshot.balance = 999  # type: ignore


@pytest.mark.unit
def test_balance_snapshot_with_negative_balance(faker: Faker) -> None:
    """測試 BalanceSnapshot 負餘額"""
    snapshot = BalanceSnapshot(
        guild_id=faker.random_int(), member_id=faker.random_int(), balance=-100
    )

    assert snapshot.balance == -100


@pytest.mark.unit
def test_balance_snapshot_none_last_modified_at_defaults_to_now() -> None:
    """測試 BalanceSnapshot last_modified_at 為 None 時默認為當前時間"""
    before = datetime.now(timezone.utc)
    snapshot = BalanceSnapshot(last_modified_at=None)
    after = datetime.now(timezone.utc)

    assert before <= snapshot.last_modified_at <= after


# ==================== HistoryEntry Tests ====================


@pytest.mark.unit
def test_history_entry_initialization(faker: Faker) -> None:
    """測試 HistoryEntry 基本初始化"""
    transaction_id = uuid4()
    guild_id = faker.random_int(min=1)
    member_id = faker.random_int(min=1)
    initiator_id = faker.random_int(min=1)
    target_id = faker.random_int(min=1)
    amount = faker.random_int(min=1, max=1000000)
    direction = "transfer"
    reason = faker.sentence()
    created_at = datetime.now(timezone.utc)
    metadata: dict[str, object] = {"key": "value"}
    balance_after_initiator = faker.random_int(min=0)
    balance_after_target = faker.random_int(min=0)

    entry = HistoryEntry(
        transaction_id=transaction_id,
        guild_id=guild_id,
        member_id=member_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        direction=direction,
        reason=reason,
        created_at=created_at,
        metadata=metadata,
        balance_after_initiator=balance_after_initiator,
        balance_after_target=balance_after_target,
    )

    assert entry.transaction_id == transaction_id
    assert entry.guild_id == guild_id
    assert entry.member_id == member_id
    assert entry.initiator_id == initiator_id
    assert entry.target_id == target_id
    assert entry.amount == amount
    assert entry.direction == direction
    assert entry.reason == reason
    assert entry.created_at == created_at
    assert entry.metadata == metadata
    assert entry.balance_after_initiator == balance_after_initiator
    assert entry.balance_after_target == balance_after_target


@pytest.mark.unit
def test_history_entry_with_none_target(faker: Faker) -> None:
    """測試 HistoryEntry 無目標 ID"""
    entry = HistoryEntry(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        member_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=None,
        amount=faker.random_int(),
        direction="add",
        reason=None,
        created_at=datetime.now(timezone.utc),
        metadata={},
        balance_after_initiator=faker.random_int(),
        balance_after_target=None,
    )

    assert entry.target_id is None
    assert entry.balance_after_target is None


@pytest.mark.unit
def test_history_entry_is_credit_property(faker: Faker) -> None:
    """測試 HistoryEntry.is_credit 屬性"""
    member_id = faker.random_int(min=1)
    target_id = member_id

    entry = HistoryEntry(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        member_id=member_id,
        initiator_id=faker.random_int(min=1000),
        target_id=target_id,
        amount=faker.random_int(),
        direction="transfer",
        reason=None,
        created_at=datetime.now(timezone.utc),
        metadata={},
        balance_after_initiator=faker.random_int(),
        balance_after_target=faker.random_int(),
    )

    assert entry.is_credit is True


@pytest.mark.unit
def test_history_entry_is_debit_property(faker: Faker) -> None:
    """測試 HistoryEntry.is_debit 屬性"""
    member_id = faker.random_int(min=1)
    initiator_id = member_id

    entry = HistoryEntry(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        member_id=member_id,
        initiator_id=initiator_id,
        target_id=faker.random_int(min=1000),
        amount=faker.random_int(),
        direction="transfer",
        reason=None,
        created_at=datetime.now(timezone.utc),
        metadata={},
        balance_after_initiator=faker.random_int(),
        balance_after_target=faker.random_int(),
    )

    assert entry.is_debit is True
    assert entry.is_credit is False


@pytest.mark.unit
def test_history_entry_neither_credit_nor_debit(faker: Faker) -> None:
    """測試 HistoryEntry 既不是收入也不是支出（管理員調整）"""
    member_id = 100
    initiator_id = 200
    target_id = 300

    entry = HistoryEntry(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        member_id=member_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=faker.random_int(),
        direction="add",
        reason=None,
        created_at=datetime.now(timezone.utc),
        metadata={},
        balance_after_initiator=faker.random_int(),
        balance_after_target=faker.random_int(),
    )

    assert entry.is_credit is False
    assert entry.is_debit is False


@pytest.mark.unit
def test_history_entry_frozen(faker: Faker) -> None:
    """測試 HistoryEntry 是不可變的"""
    entry = HistoryEntry(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        member_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="transfer",
        reason=None,
        created_at=datetime.now(timezone.utc),
        metadata={},
        balance_after_initiator=faker.random_int(),
        balance_after_target=faker.random_int(),
    )

    with pytest.raises(AttributeError):
        entry.amount = 999  # type: ignore


# ==================== HistoryPage Tests ====================


@pytest.mark.unit
def test_history_page_initialization(faker: Faker) -> None:
    """測試 HistoryPage 基本初始化"""
    items = [
        HistoryEntry(
            transaction_id=uuid4(),
            guild_id=faker.random_int(),
            member_id=faker.random_int(),
            initiator_id=faker.random_int(),
            target_id=faker.random_int(),
            amount=faker.random_int(),
            direction="transfer",
            reason=None,
            created_at=datetime.now(timezone.utc),
            metadata={},
            balance_after_initiator=faker.random_int(),
            balance_after_target=faker.random_int(),
        )
        for _ in range(3)
    ]
    next_cursor = datetime.now(timezone.utc)

    page = HistoryPage(items=items, next_cursor=next_cursor)

    assert len(page.items) == 3
    assert page.next_cursor == next_cursor


@pytest.mark.unit
def test_history_page_empty() -> None:
    """測試空 HistoryPage"""
    page = HistoryPage(items=[], next_cursor=None)

    assert len(page.items) == 0
    assert page.next_cursor is None


@pytest.mark.unit
def test_history_page_frozen(faker: Faker) -> None:
    """測試 HistoryPage 是不可變的"""
    page = HistoryPage(items=[], next_cursor=None)

    with pytest.raises(AttributeError):
        page.items = []  # type: ignore


# ==================== make_balance_snapshot Tests ====================


@pytest.mark.unit
def test_make_balance_snapshot(faker: Faker) -> None:
    """測試從記錄建構 BalanceSnapshot"""
    guild_id = faker.random_int()
    member_id = faker.random_int()
    balance = faker.random_int()
    last_modified_at = datetime.now(timezone.utc)
    throttled_until = datetime.now(timezone.utc) + timedelta(hours=1)

    record = SimpleNamespace(
        guild_id=guild_id,
        member_id=member_id,
        balance=balance,
        last_modified_at=last_modified_at,
        throttled_until=throttled_until,
    )

    snapshot = make_balance_snapshot(record)

    assert isinstance(snapshot, BalanceSnapshot)
    assert snapshot.guild_id == guild_id
    assert snapshot.member_id == member_id
    assert snapshot.balance == balance
    assert snapshot.last_modified_at == last_modified_at
    assert snapshot.throttled_until == throttled_until


@pytest.mark.unit
def test_make_balance_snapshot_with_none_throttled_until(faker: Faker) -> None:
    """測試從記錄建構 BalanceSnapshot（無節流）"""
    record = SimpleNamespace(
        guild_id=faker.random_int(),
        member_id=faker.random_int(),
        balance=faker.random_int(),
        last_modified_at=datetime.now(timezone.utc),
        throttled_until=None,
    )

    snapshot = make_balance_snapshot(record)

    assert snapshot.throttled_until is None


# ==================== make_history_entry Tests ====================


@pytest.mark.unit
def test_make_history_entry(faker: Faker) -> None:
    """測試從記錄建構 HistoryEntry"""
    transaction_id = uuid4()
    guild_id = faker.random_int()
    member_id = faker.random_int()
    initiator_id = faker.random_int()
    target_id = faker.random_int()
    amount = faker.random_int()
    direction = "transfer"
    reason = faker.sentence()
    created_at = datetime.now(timezone.utc)
    metadata = {"key": "value"}
    balance_after_initiator = faker.random_int()
    balance_after_target = faker.random_int()

    record = SimpleNamespace(
        transaction_id=transaction_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        direction=direction,
        reason=reason,
        created_at=created_at,
        metadata=metadata,
        balance_after_initiator=balance_after_initiator,
        balance_after_target=balance_after_target,
    )

    entry = make_history_entry(record, member_id)

    assert isinstance(entry, HistoryEntry)
    assert entry.transaction_id == transaction_id
    assert entry.guild_id == guild_id
    assert entry.member_id == member_id
    assert entry.initiator_id == initiator_id
    assert entry.target_id == target_id
    assert entry.metadata == metadata


@pytest.mark.unit
def test_make_history_entry_with_none_metadata(faker: Faker) -> None:
    """測試從含 None metadata 的記錄建構 HistoryEntry"""
    record = SimpleNamespace(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="transfer",
        reason=None,
        created_at=datetime.now(timezone.utc),
        metadata=None,
        balance_after_initiator=faker.random_int(),
        balance_after_target=faker.random_int(),
    )

    entry = make_history_entry(record, faker.random_int())

    assert entry.metadata == {}


@pytest.mark.unit
def test_make_history_entry_without_metadata(faker: Faker) -> None:
    """測試從缺少 metadata 的記錄建構 HistoryEntry"""
    record = SimpleNamespace(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="transfer",
        reason=None,
        created_at=datetime.now(timezone.utc),
        balance_after_initiator=faker.random_int(),
        balance_after_target=faker.random_int(),
    )

    entry = make_history_entry(record, faker.random_int())

    assert entry.metadata == {}


# ==================== ensure_view_permission Tests ====================


class _TestPermissionError(Exception):
    """測試用的權限錯誤"""


@pytest.mark.unit
def test_ensure_view_permission_same_user(faker: Faker) -> None:
    """測試同一用戶查看自己的餘額"""
    user_id = faker.random_int()

    # 應該不拋出異常
    ensure_view_permission(user_id, user_id, can_view_others=False, error_type=_TestPermissionError)


@pytest.mark.unit
def test_ensure_view_permission_with_permission(faker: Faker) -> None:
    """測試有權限查看其他用戶的餘額"""
    requester_id = faker.random_int()
    target_id = faker.random_int()

    # 應該不拋出異常
    ensure_view_permission(
        requester_id, target_id, can_view_others=True, error_type=_TestPermissionError
    )


@pytest.mark.unit
def test_ensure_view_permission_without_permission(faker: Faker) -> None:
    """測試無權限查看其他用戶的餘額"""
    requester_id = faker.random_int(min=1, max=100)
    target_id = faker.random_int(min=101, max=200)

    with pytest.raises(_TestPermissionError, match="You do not have permission"):
        ensure_view_permission(
            requester_id, target_id, can_view_others=False, error_type=_TestPermissionError
        )


# ==================== TransferProcedureResult Tests ====================


@pytest.mark.unit
def test_transfer_procedure_result_initialization(faker: Faker) -> None:
    """測試 TransferProcedureResult 基本初始化"""
    transaction_id = uuid4()
    guild_id = faker.random_int(min=1)
    initiator_id = faker.random_int(min=1)
    target_id = faker.random_int(min=1)
    amount = faker.random_int(min=1, max=1000000)
    direction = "transfer"
    created_at = datetime.now(timezone.utc)
    initiator_balance = faker.random_int(min=0)
    target_balance = faker.random_int(min=0)
    throttled_until = datetime.now(timezone.utc) + timedelta(hours=1)
    metadata = {"reason": faker.sentence()}

    result = TransferProcedureResult(
        transaction_id=transaction_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        direction=direction,
        created_at=created_at,
        initiator_balance=initiator_balance,
        target_balance=target_balance,
        throttled_until=throttled_until,
        metadata=metadata,
    )

    assert result.transaction_id == transaction_id
    assert result.guild_id == guild_id
    assert result.initiator_id == initiator_id
    assert result.target_id == target_id
    assert result.amount == amount
    assert result.direction == direction
    assert result.created_at == created_at
    assert result.initiator_balance == initiator_balance
    assert result.target_balance == target_balance
    assert result.throttled_until == throttled_until
    assert result.metadata == metadata


@pytest.mark.unit
def test_transfer_procedure_result_with_none_target_balance(faker: Faker) -> None:
    """測試 TransferProcedureResult 無目標餘額"""
    result = TransferProcedureResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="transfer",
        created_at=datetime.now(timezone.utc),
        initiator_balance=faker.random_int(),
        target_balance=None,
        throttled_until=None,
        metadata={},
    )

    assert result.target_balance is None


@pytest.mark.unit
def test_transfer_procedure_result_frozen(faker: Faker) -> None:
    """測試 TransferProcedureResult 是不可變的"""
    result = TransferProcedureResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="transfer",
        created_at=datetime.now(timezone.utc),
        initiator_balance=faker.random_int(),
        target_balance=faker.random_int(),
        throttled_until=None,
        metadata={},
    )

    with pytest.raises(AttributeError):
        result.amount = 999  # type: ignore


# ==================== TransferResult Tests ====================


@pytest.mark.unit
def test_transfer_result_initialization(faker: Faker) -> None:
    """測試 TransferResult 基本初始化"""
    transaction_id = uuid4()
    guild_id = faker.random_int(min=1)
    initiator_id = faker.random_int(min=1)
    target_id = faker.random_int(min=1)
    amount = faker.random_int(min=1, max=1000000)
    initiator_balance = faker.random_int(min=0)
    target_balance = faker.random_int(min=0)
    direction = "transfer"
    created_at = datetime.now(timezone.utc)
    throttled_until = datetime.now(timezone.utc) + timedelta(hours=1)
    metadata = {"reason": faker.sentence()}

    result = TransferResult(
        transaction_id=transaction_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        initiator_balance=initiator_balance,
        target_balance=target_balance,
        direction=direction,
        created_at=created_at,
        throttled_until=throttled_until,
        metadata=metadata,
    )

    assert result.transaction_id == transaction_id
    assert result.guild_id == guild_id
    assert result.initiator_id == initiator_id
    assert result.target_id == target_id
    assert result.amount == amount
    assert result.initiator_balance == initiator_balance
    assert result.target_balance == target_balance
    assert result.direction == direction
    assert result.created_at == created_at
    assert result.throttled_until == throttled_until
    assert result.metadata == metadata


@pytest.mark.unit
def test_transfer_result_default_values(faker: Faker) -> None:
    """測試 TransferResult 默認值"""
    result = TransferResult(
        transaction_id=None,
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        initiator_balance=faker.random_int(),
        target_balance=faker.random_int(),
    )

    assert result.transaction_id is None
    assert result.direction == "transfer"
    assert result.created_at is None
    assert result.throttled_until is None
    assert result.metadata is None


@pytest.mark.unit
def test_transfer_result_metadata_defensive_copy(faker: Faker) -> None:
    """測試 TransferResult metadata 的防禦性複製"""
    original_metadata = {"key": "value"}
    result = TransferResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        initiator_balance=faker.random_int(),
        target_balance=faker.random_int(),
        metadata=original_metadata,
    )

    # metadata 應該是副本
    assert result.metadata == original_metadata
    assert result.metadata is not original_metadata


@pytest.mark.unit
def test_transfer_result_frozen(faker: Faker) -> None:
    """測試 TransferResult 是不可變的"""
    result = TransferResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        initiator_balance=faker.random_int(),
        target_balance=faker.random_int(),
    )

    with pytest.raises(AttributeError):
        result.amount = 999  # type: ignore


# ==================== build_transfer_procedure_result Tests ====================


@pytest.mark.unit
def test_build_transfer_procedure_result_from_object(faker: Faker) -> None:
    """測試從物件建構 TransferProcedureResult"""
    transaction_id = uuid4()
    record = SimpleNamespace(
        transaction_id=transaction_id,
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="transfer",
        created_at=datetime.now(timezone.utc),
        initiator_balance=faker.random_int(),
        target_balance=faker.random_int(),
        throttled_until=None,
        metadata={"key": "value"},
    )

    result = build_transfer_procedure_result(record)

    assert isinstance(result, TransferProcedureResult)
    assert result.transaction_id == transaction_id
    assert result.metadata == {"key": "value"}


@pytest.mark.unit
def test_build_transfer_procedure_result_from_dict(faker: Faker) -> None:
    """測試從字典建構 TransferProcedureResult"""
    transaction_id = uuid4()
    record = {
        "transaction_id": transaction_id,
        "guild_id": faker.random_int(),
        "initiator_id": faker.random_int(),
        "target_id": faker.random_int(),
        "amount": faker.random_int(),
        "direction": "transfer",
        "created_at": datetime.now(timezone.utc),
        "initiator_balance": faker.random_int(),
        "target_balance": faker.random_int(),
        "throttled_until": None,
        "metadata": {"key": "value"},
    }

    result = build_transfer_procedure_result(record)

    assert isinstance(result, TransferProcedureResult)
    assert result.transaction_id == transaction_id
    assert result.metadata == {"key": "value"}


@pytest.mark.unit
def test_build_transfer_procedure_result_with_none_metadata(faker: Faker) -> None:
    """測試從 None metadata 建構 TransferProcedureResult"""
    record = SimpleNamespace(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="transfer",
        created_at=datetime.now(timezone.utc),
        initiator_balance=faker.random_int(),
        target_balance=faker.random_int(),
        throttled_until=None,
        metadata=None,
    )

    result = build_transfer_procedure_result(record)

    assert result.metadata == {}


@pytest.mark.unit
def test_build_transfer_procedure_result_type_conversion(faker: Faker) -> None:
    """測試建構時的類型轉換"""
    record = SimpleNamespace(
        transaction_id=uuid4(),
        guild_id="123",  # 字串應該被轉為 int
        initiator_id="456",
        target_id="789",
        amount="100",
        direction="transfer",
        created_at=datetime.now(timezone.utc),
        initiator_balance="500",
        target_balance="300",
        throttled_until=None,
        metadata={},
    )

    result = build_transfer_procedure_result(record)

    assert isinstance(result.guild_id, int)
    assert result.guild_id == 123
    assert isinstance(result.initiator_id, int)
    assert isinstance(result.target_id, int)
    assert isinstance(result.amount, int)
    assert isinstance(result.initiator_balance, int)


# ==================== transfer_result_from_procedure Tests ====================


@pytest.mark.unit
def test_transfer_result_from_procedure(faker: Faker) -> None:
    """測試從 TransferProcedureResult 轉換為 TransferResult"""
    transaction_id = uuid4()
    procedure_result = TransferProcedureResult(
        transaction_id=transaction_id,
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="transfer",
        created_at=datetime.now(timezone.utc),
        initiator_balance=faker.random_int(),
        target_balance=faker.random_int(),
        throttled_until=None,
        metadata={"key": "value"},
    )

    result = transfer_result_from_procedure(procedure_result)

    assert isinstance(result, TransferResult)
    assert result.transaction_id == transaction_id
    assert result.guild_id == procedure_result.guild_id
    assert result.metadata == {"key": "value"}


@pytest.mark.unit
def test_transfer_result_from_procedure_with_none_target_balance(faker: Faker) -> None:
    """測試從含 None target_balance 的 procedure result 轉換"""
    procedure_result = TransferProcedureResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="transfer",
        created_at=datetime.now(timezone.utc),
        initiator_balance=faker.random_int(),
        target_balance=None,
        throttled_until=None,
        metadata={},
    )

    result = transfer_result_from_procedure(procedure_result)

    # None 應該被轉為 0
    assert result.target_balance == 0


@pytest.mark.unit
def test_transfer_result_from_procedure_metadata_copy(faker: Faker) -> None:
    """測試轉換時 metadata 是獨立的副本"""
    metadata = {"key": "value"}
    procedure_result = TransferProcedureResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="transfer",
        created_at=datetime.now(timezone.utc),
        initiator_balance=faker.random_int(),
        target_balance=faker.random_int(),
        throttled_until=None,
        metadata=metadata,
    )

    result = transfer_result_from_procedure(procedure_result)

    # metadata 應該是副本
    assert result.metadata == metadata
    assert result.metadata is not metadata


# ==================== PendingTransfer Tests ====================


@pytest.mark.unit
def test_pending_transfer_initialization(faker: Faker) -> None:
    """測試 PendingTransfer 基本初始化"""
    transfer_id = uuid4()
    guild_id = faker.random_int(min=1)
    initiator_id = faker.random_int(min=1)
    target_id = faker.random_int(min=1)
    amount = faker.random_int(min=1, max=1000000)
    status = faker.random_element(["pending", "processing", "completed", "failed"])
    checks = {"anti_spam": True, "balance": True}
    retry_count = faker.random_int(min=0, max=5)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    metadata = {"reason": faker.sentence()}
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)

    transfer = PendingTransfer(
        transfer_id=transfer_id,
        guild_id=guild_id,
        initiator_id=initiator_id,
        target_id=target_id,
        amount=amount,
        status=status,
        checks=checks,
        retry_count=retry_count,
        expires_at=expires_at,
        metadata=metadata,
        created_at=created_at,
        updated_at=updated_at,
    )

    assert transfer.transfer_id == transfer_id
    assert transfer.guild_id == guild_id
    assert transfer.initiator_id == initiator_id
    assert transfer.target_id == target_id
    assert transfer.amount == amount
    assert transfer.status == status
    assert transfer.checks == checks
    assert transfer.retry_count == retry_count
    assert transfer.expires_at == expires_at
    assert transfer.metadata == metadata
    assert transfer.created_at == created_at
    assert transfer.updated_at == updated_at


@pytest.mark.unit
def test_pending_transfer_with_none_expires_at(faker: Faker) -> None:
    """測試 PendingTransfer 無過期時間"""
    transfer = PendingTransfer(
        transfer_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        status="pending",
        checks={},
        retry_count=0,
        expires_at=None,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    assert transfer.expires_at is None


@pytest.mark.unit
def test_pending_transfer_with_zero_retry_count(faker: Faker) -> None:
    """測試 PendingTransfer 零重試次數"""
    transfer = PendingTransfer(
        transfer_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        status="pending",
        checks={},
        retry_count=0,
        expires_at=None,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    assert transfer.retry_count == 0


@pytest.mark.unit
def test_pending_transfer_frozen(faker: Faker) -> None:
    """測試 PendingTransfer 是不可變的"""
    transfer = PendingTransfer(
        transfer_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        status="pending",
        checks={},
        retry_count=0,
        expires_at=None,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with pytest.raises(AttributeError):
        transfer.amount = 999  # type: ignore


# ==================== build_pending_transfer Tests ====================


@pytest.mark.unit
def test_build_pending_transfer_from_object(faker: Faker) -> None:
    """測試從物件建構 PendingTransfer"""
    transfer_id = uuid4()
    record = SimpleNamespace(
        transfer_id=transfer_id,
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        status="pending",
        checks={"anti_spam": True},
        retry_count=0,
        expires_at=None,
        metadata={"key": "value"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    transfer = build_pending_transfer(record)

    assert isinstance(transfer, PendingTransfer)
    assert transfer.transfer_id == transfer_id
    assert transfer.checks == {"anti_spam": True}
    assert transfer.metadata == {"key": "value"}


@pytest.mark.unit
def test_build_pending_transfer_from_dict(faker: Faker) -> None:
    """測試從字典建構 PendingTransfer"""
    transfer_id = uuid4()
    record = {
        "transfer_id": transfer_id,
        "guild_id": faker.random_int(),
        "initiator_id": faker.random_int(),
        "target_id": faker.random_int(),
        "amount": faker.random_int(),
        "status": "pending",
        "checks": {"anti_spam": True},
        "retry_count": 0,
        "expires_at": None,
        "metadata": {"key": "value"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    transfer = build_pending_transfer(record)

    assert isinstance(transfer, PendingTransfer)
    assert transfer.transfer_id == transfer_id
    assert transfer.metadata == {"key": "value"}


@pytest.mark.unit
def test_build_pending_transfer_with_none_checks(faker: Faker) -> None:
    """測試從 None checks 建構 PendingTransfer"""
    record = SimpleNamespace(
        transfer_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        status="pending",
        checks=None,
        retry_count=0,
        expires_at=None,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    transfer = build_pending_transfer(record)

    assert transfer.checks == {}


@pytest.mark.unit
def test_build_pending_transfer_with_none_metadata(faker: Faker) -> None:
    """測試從 None metadata 建構 PendingTransfer"""
    record = SimpleNamespace(
        transfer_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        status="pending",
        checks={},
        retry_count=0,
        expires_at=None,
        metadata=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    transfer = build_pending_transfer(record)

    assert transfer.metadata == {}


@pytest.mark.unit
def test_build_pending_transfer_without_checks(faker: Faker) -> None:
    """測試從缺少 checks 的記錄建構 PendingTransfer"""
    record = SimpleNamespace(
        transfer_id=uuid4(),
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        status="pending",
        retry_count=0,
        expires_at=None,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    transfer = build_pending_transfer(record)

    assert transfer.checks == {}


@pytest.mark.unit
def test_build_pending_transfer_type_conversion(faker: Faker) -> None:
    """測試建構時的類型轉換"""
    record = SimpleNamespace(
        transfer_id=uuid4(),
        guild_id="123",  # 字串應該被轉為 int
        initiator_id="456",
        target_id="789",
        amount="100",
        status="pending",
        checks={},
        retry_count="2",
        expires_at=None,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    transfer = build_pending_transfer(record)

    assert isinstance(transfer.guild_id, int)
    assert transfer.guild_id == 123
    assert isinstance(transfer.initiator_id, int)
    assert isinstance(transfer.target_id, int)
    assert isinstance(transfer.amount, int)
    assert isinstance(transfer.retry_count, int)
    assert transfer.retry_count == 2


@pytest.mark.unit
def test_pending_transfer_from_record(faker: Faker) -> None:
    """測試 PendingTransfer.from_record 類方法"""
    transfer_id = uuid4()
    record = SimpleNamespace(
        transfer_id=transfer_id,
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        status="pending",
        checks={},
        retry_count=0,
        expires_at=None,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    transfer = PendingTransfer.from_record(record)

    assert isinstance(transfer, PendingTransfer)
    assert transfer.transfer_id == transfer_id


# ==================== Edge Cases and Integration Tests ====================


class _DictLikeObject:
    """類似 dict 但不繼承 Mapping 的物件，用於測試邊界情況"""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def keys(self) -> list[str]:
        return list(self._data.keys())

    def __getitem__(self, key: str) -> Any:
        return self._data[key]


@pytest.mark.unit
def test_build_adjustment_procedure_result_from_dict_like_object(faker: Faker) -> None:
    """測試從類 dict 物件建構 AdjustmentProcedureResult"""
    transaction_id = uuid4()
    record = _DictLikeObject(
        {
            "transaction_id": transaction_id,
            "guild_id": faker.random_int(),
            "admin_id": faker.random_int(),
            "target_id": faker.random_int(),
            "amount": faker.random_int(),
            "direction": "add",
            "created_at": datetime.now(timezone.utc),
            "target_balance_after": faker.random_int(),
            "metadata": {"key": "value"},
        }
    )

    result = build_adjustment_procedure_result(record)

    assert isinstance(result, AdjustmentProcedureResult)
    assert result.transaction_id == transaction_id


@pytest.mark.unit
def test_build_transfer_procedure_result_from_dict_like_object(faker: Faker) -> None:
    """測試從類 dict 物件建構 TransferProcedureResult"""
    transaction_id = uuid4()
    record = _DictLikeObject(
        {
            "transaction_id": transaction_id,
            "guild_id": faker.random_int(),
            "initiator_id": faker.random_int(),
            "target_id": faker.random_int(),
            "amount": faker.random_int(),
            "direction": "transfer",
            "created_at": datetime.now(timezone.utc),
            "initiator_balance": faker.random_int(),
            "target_balance": faker.random_int(),
            "throttled_until": None,
            "metadata": {"key": "value"},
        }
    )

    result = build_transfer_procedure_result(record)

    assert isinstance(result, TransferProcedureResult)
    assert result.transaction_id == transaction_id


@pytest.mark.unit
def test_build_pending_transfer_from_dict_like_object(faker: Faker) -> None:
    """測試從類 dict 物件建構 PendingTransfer"""
    transfer_id = uuid4()
    record = _DictLikeObject(
        {
            "transfer_id": transfer_id,
            "guild_id": faker.random_int(),
            "initiator_id": faker.random_int(),
            "target_id": faker.random_int(),
            "amount": faker.random_int(),
            "status": "pending",
            "checks": {"anti_spam": True},
            "retry_count": 0,
            "expires_at": None,
            "metadata": {"key": "value"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    transfer = build_pending_transfer(record)

    assert isinstance(transfer, PendingTransfer)
    assert transfer.transfer_id == transfer_id


class _ObjectWithoutKeysMethod:
    """測試用的物件，沒有 keys 方法但有屬性"""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.mark.unit
def test_build_adjustment_procedure_result_from_plain_object(faker: Faker) -> None:
    """測試從純物件建構 AdjustmentProcedureResult（沒有 keys/__getitem__）"""
    transaction_id = uuid4()
    record = _ObjectWithoutKeysMethod(
        transaction_id=transaction_id,
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
        metadata={"key": "value"},
    )

    result = build_adjustment_procedure_result(record)

    assert isinstance(result, AdjustmentProcedureResult)
    assert result.transaction_id == transaction_id


@pytest.mark.unit
def test_build_transfer_procedure_result_from_plain_object(faker: Faker) -> None:
    """測試從純物件建構 TransferProcedureResult（沒有 keys/__getitem__）"""
    transaction_id = uuid4()
    record = _ObjectWithoutKeysMethod(
        transaction_id=transaction_id,
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="transfer",
        created_at=datetime.now(timezone.utc),
        initiator_balance=faker.random_int(),
        target_balance=faker.random_int(),
        throttled_until=None,
        metadata={"key": "value"},
    )

    result = build_transfer_procedure_result(record)

    assert isinstance(result, TransferProcedureResult)
    assert result.transaction_id == transaction_id


@pytest.mark.unit
def test_build_pending_transfer_from_plain_object(faker: Faker) -> None:
    """測試從純物件建構 PendingTransfer（沒有 keys/__getitem__）"""
    transfer_id = uuid4()
    record = _ObjectWithoutKeysMethod(
        transfer_id=transfer_id,
        guild_id=faker.random_int(),
        initiator_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        status="pending",
        checks={"anti_spam": True},
        retry_count=0,
        expires_at=None,
        metadata={"key": "value"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    transfer = build_pending_transfer(record)

    assert isinstance(transfer, PendingTransfer)
    assert transfer.transfer_id == transfer_id


@pytest.mark.unit
def test_all_models_with_large_numbers(faker: Faker) -> None:
    """測試所有模型處理大數字"""
    large_number = 999_999_999_999

    adjustment = AdjustmentProcedureResult(
        transaction_id=uuid4(),
        guild_id=large_number,
        admin_id=large_number,
        target_id=large_number,
        amount=large_number,
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=large_number,
        metadata={},
    )
    assert adjustment.amount == large_number

    transfer = TransferProcedureResult(
        transaction_id=uuid4(),
        guild_id=large_number,
        initiator_id=large_number,
        target_id=large_number,
        amount=large_number,
        direction="transfer",
        created_at=datetime.now(timezone.utc),
        initiator_balance=large_number,
        target_balance=large_number,
        throttled_until=None,
        metadata={},
    )
    assert transfer.amount == large_number

    pending = PendingTransfer(
        transfer_id=uuid4(),
        guild_id=large_number,
        initiator_id=large_number,
        target_id=large_number,
        amount=large_number,
        status="pending",
        checks={},
        retry_count=0,
        expires_at=None,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert pending.amount == large_number


@pytest.mark.unit
def test_complex_metadata_structures(faker: Faker) -> None:
    """測試複雜的 metadata 結構"""
    complex_metadata: dict[str, Any] = {
        "nested": {"key": "value", "list": [1, 2, 3]},
        "number": 123,
        "boolean": True,
        "null": None,
    }

    adjustment = AdjustmentProcedureResult(
        transaction_id=uuid4(),
        guild_id=faker.random_int(),
        admin_id=faker.random_int(),
        target_id=faker.random_int(),
        amount=faker.random_int(),
        direction="add",
        created_at=datetime.now(timezone.utc),
        target_balance_after=faker.random_int(),
        metadata=complex_metadata,
    )
    assert adjustment.metadata == complex_metadata
    assert adjustment.metadata["nested"]["list"] == [1, 2, 3]


@pytest.mark.unit
def test_datetime_edge_cases(faker: Faker) -> None:
    """測試日期時間邊界情況"""
    # 過去的時間
    past = datetime.now(timezone.utc) - timedelta(days=365)
    # 未來的時間
    future = datetime.now(timezone.utc) + timedelta(days=365)

    snapshot = BalanceSnapshot(
        guild_id=faker.random_int(),
        member_id=faker.random_int(),
        balance=faker.random_int(),
        last_modified_at=past,
        throttled_until=future,
    )
    assert snapshot.last_modified_at == past
    assert snapshot.throttled_until == future
    assert snapshot.is_throttled is True
