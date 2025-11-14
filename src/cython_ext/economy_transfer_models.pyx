# cython: language_level=3, embedsignature=True

cdef class TransferProcedureResult:
    cdef public object transaction_id
    cdef public int guild_id
    cdef public int initiator_id
    cdef public int target_id
    cdef public int amount
    cdef public str direction
    cdef public object created_at
    cdef public int initiator_balance
    cdef public object target_balance
    cdef public object throttled_until
    cdef public dict metadata

    def __cinit__(
        self,
        object transaction_id,
        int guild_id,
        int initiator_id,
        int target_id,
        int amount,
        str direction,
        object created_at,
        int initiator_balance,
        object target_balance,
        object throttled_until,
        dict metadata,
    ):
        self.transaction_id = transaction_id
        self.guild_id = guild_id
        self.initiator_id = initiator_id
        self.target_id = target_id
        self.amount = amount
        self.direction = direction
        self.created_at = created_at
        self.initiator_balance = initiator_balance
        self.target_balance = target_balance
        self.throttled_until = throttled_until
        self.metadata = metadata


cdef class TransferResult:
    cdef public object transaction_id
    cdef public int guild_id
    cdef public int initiator_id
    cdef public int target_id
    cdef public int amount
    cdef public int initiator_balance
    cdef public object target_balance
    cdef public str direction
    cdef public object created_at
    cdef public object throttled_until
    cdef public dict metadata

    def __cinit__(
        self,
        object transaction_id,
        int guild_id,
        int initiator_id,
        int target_id,
        int amount,
        int initiator_balance,
        object target_balance,
        str direction="transfer",
        object created_at=None,
        object throttled_until=None,
        dict metadata=None,
    ):
        if metadata is None:
            metadata = {}
        self.transaction_id = transaction_id
        self.guild_id = guild_id
        self.initiator_id = initiator_id
        self.target_id = target_id
        self.amount = amount
        self.initiator_balance = initiator_balance
        self.target_balance = target_balance
        self.direction = direction
        self.created_at = created_at
        self.throttled_until = throttled_until
        self.metadata = metadata


cpdef TransferProcedureResult build_transfer_procedure_result(object record):
    cdef dict metadata
    if isinstance(record, dict):
        metadata = dict(record.get("metadata") or {})
        return TransferProcedureResult(
            record["transaction_id"],
            int(record["guild_id"]),
            int(record["initiator_id"]),
            int(record["target_id"]),
            int(record["amount"]),
            str(record["direction"]),
            record["created_at"],
            int(record["initiator_balance"]),
            record["target_balance"],
            record["throttled_until"],
            metadata,
        )
    else:
        metadata = dict(getattr(record, "metadata", {}) or {})
        return TransferProcedureResult(
            getattr(record, "transaction_id"),
            int(getattr(record, "guild_id")),
            int(getattr(record, "initiator_id")),
            int(getattr(record, "target_id")),
            int(getattr(record, "amount")),
            str(getattr(record, "direction")),
            getattr(record, "created_at"),
            int(getattr(record, "initiator_balance")),
            getattr(record, "target_balance"),
            getattr(record, "throttled_until"),
            metadata,
        )


cpdef TransferResult transfer_result_from_procedure(TransferProcedureResult record):
    cdef dict metadata = dict(record.metadata or {})
    cdef object target_balance = record.target_balance
    if target_balance is None:
        target_balance = 0
    return TransferResult(
        record.transaction_id,
        record.guild_id,
        record.initiator_id,
        record.target_id,
        record.amount,
        record.initiator_balance,
        target_balance,
        record.direction,
        record.created_at,
        record.throttled_until,
        metadata,
    )
