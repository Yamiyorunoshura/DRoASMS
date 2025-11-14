# cython: language_level=3, embedsignature=True

from datetime import datetime, timezone

cdef object _now_utc():
    return datetime.now(timezone.utc)


cdef class BalanceSnapshot:
    cdef public int guild_id
    cdef public int member_id
    cdef public int balance
    cdef public object last_modified_at
    cdef public object throttled_until

    def __cinit__(
        self,
        int guild_id=0,
        int member_id=0,
        int balance=0,
        object last_modified_at=None,
        object throttled_until=None,
        object is_throttled=None,
    ):
        if last_modified_at is None:
            last_modified_at = _now_utc()
        self.guild_id = guild_id
        self.member_id = member_id
        self.balance = balance
        self.last_modified_at = last_modified_at
        self.throttled_until = throttled_until

    @property
    def is_throttled(self):
        if self.throttled_until is None:
            return False
        cdef object now = _now_utc()
        try:
            return self.throttled_until > now
        except Exception:
            return False


cdef class HistoryEntry:
    cdef public object transaction_id
    cdef public int guild_id
    cdef public int member_id
    cdef public int initiator_id
    cdef public object target_id
    cdef public int amount
    cdef public str direction
    cdef public object reason
    cdef public object created_at
    cdef public dict metadata
    cdef public int balance_after_initiator
    cdef public object balance_after_target

    def __cinit__(
        self,
        object transaction_id,
        int guild_id,
        int member_id,
        int initiator_id,
        object target_id,
        int amount,
        str direction,
        object reason,
        object created_at,
        dict metadata,
        int balance_after_initiator,
        object balance_after_target,
    ):
        self.transaction_id = transaction_id
        self.guild_id = guild_id
        self.member_id = member_id
        self.initiator_id = initiator_id
        self.target_id = target_id
        self.amount = amount
        self.direction = direction
        self.reason = reason
        self.created_at = created_at
        self.metadata = metadata
        self.balance_after_initiator = balance_after_initiator
        self.balance_after_target = balance_after_target

    @property
    def is_credit(self):
        return self.target_id == self.member_id

    @property
    def is_debit(self):
        return self.initiator_id == self.member_id and not self.is_credit


cdef class HistoryPage:
    cdef public object items
    cdef public object next_cursor

    def __cinit__(self, object items, object next_cursor):
        self.items = items
        self.next_cursor = next_cursor


cpdef BalanceSnapshot make_balance_snapshot(object record):
    return BalanceSnapshot(
        guild_id=int(getattr(record, "guild_id")),
        member_id=int(getattr(record, "member_id")),
        balance=int(getattr(record, "balance")),
        last_modified_at=getattr(record, "last_modified_at"),
        throttled_until=getattr(record, "throttled_until"),
    )


cpdef HistoryEntry make_history_entry(object record, int member_id):
    cdef dict metadata = dict(getattr(record, "metadata", {}) or {})
    return HistoryEntry(
        transaction_id=getattr(record, "transaction_id"),
        guild_id=int(getattr(record, "guild_id")),
        member_id=member_id,
        initiator_id=int(getattr(record, "initiator_id")),
        target_id=getattr(record, "target_id"),
        amount=int(getattr(record, "amount")),
        direction=str(getattr(record, "direction")),
        reason=getattr(record, "reason"),
        created_at=getattr(record, "created_at"),
        metadata=metadata,
        balance_after_initiator=int(getattr(record, "balance_after_initiator")),
        balance_after_target=getattr(record, "balance_after_target"),
    )


cpdef void ensure_view_permission(
    int requester_id, int target_id, bint can_view_others, object error_type
):
    if requester_id != target_id and not can_view_others:
        raise error_type("You do not have permission to view other members' balances.")
