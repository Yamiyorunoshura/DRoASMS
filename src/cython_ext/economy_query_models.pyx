# cython: language_level=3, embedsignature=True

cdef class BalanceRecord:
    cdef public int guild_id
    cdef public int member_id
    cdef public int balance
    cdef public object last_modified_at
    cdef public object throttled_until

    def __cinit__(
        self,
        int guild_id,
        int member_id,
        int balance,
        object last_modified_at,
        object throttled_until,
    ):
        self.guild_id = guild_id
        self.member_id = member_id
        self.balance = balance
        self.last_modified_at = last_modified_at
        self.throttled_until = throttled_until


cdef class HistoryRecord:
    cdef public object transaction_id
    cdef public int guild_id
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
        self.initiator_id = initiator_id
        self.target_id = target_id
        self.amount = amount
        self.direction = direction
        self.reason = reason
        self.created_at = created_at
        self.metadata = metadata
        self.balance_after_initiator = balance_after_initiator
        self.balance_after_target = balance_after_target
