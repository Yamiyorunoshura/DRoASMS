# cython: language_level=3, embedsignature=True

cdef class AdjustmentProcedureResult:
    cdef public object transaction_id
    cdef public int guild_id
    cdef public int admin_id
    cdef public int target_id
    cdef public int amount
    cdef public str direction
    cdef public object created_at
    cdef public int target_balance_after
    cdef public dict metadata

    def __cinit__(
        self,
        object transaction_id,
        int guild_id,
        int admin_id,
        int target_id,
        int amount,
        str direction,
        object created_at,
        int target_balance_after,
        dict metadata,
    ):
        self.transaction_id = transaction_id
        self.guild_id = guild_id
        self.admin_id = admin_id
        self.target_id = target_id
        self.amount = amount
        self.direction = direction
        self.created_at = created_at
        self.target_balance_after = target_balance_after
        self.metadata = metadata


cdef class AdjustmentResult:
    cdef public object transaction_id
    cdef public int guild_id
    cdef public int admin_id
    cdef public int target_id
    cdef public int amount
    cdef public str direction
    cdef public object created_at
    cdef public int target_balance_after
    cdef public dict metadata

    def __cinit__(
        self,
        object transaction_id,
        int guild_id,
        int admin_id,
        int target_id,
        int amount,
        str direction,
        object created_at,
        int target_balance_after,
        dict metadata,
    ):
        self.transaction_id = transaction_id
        self.guild_id = guild_id
        self.admin_id = admin_id
        self.target_id = target_id
        self.amount = amount
        self.direction = direction
        self.created_at = created_at
        self.target_balance_after = target_balance_after
        self.metadata = metadata


cpdef AdjustmentProcedureResult build_adjustment_procedure_result(object record):
    cdef dict metadata
    if isinstance(record, dict):
        metadata = dict(record.get("metadata") or {})
        return AdjustmentProcedureResult(
            record["transaction_id"],
            int(record["guild_id"]),
            int(record["admin_id"]),
            int(record["target_id"]),
            int(record["amount"]),
            str(record["direction"]),
            record["created_at"],
            int(record["target_balance_after"]),
            metadata,
        )
    else:
        metadata = dict(getattr(record, "metadata", {}) or {})
        return AdjustmentProcedureResult(
            getattr(record, "transaction_id"),
            int(getattr(record, "guild_id")),
            int(getattr(record, "admin_id")),
            int(getattr(record, "target_id")),
            int(getattr(record, "amount")),
            str(getattr(record, "direction")),
            getattr(record, "created_at"),
            int(getattr(record, "target_balance_after")),
            metadata,
        )


cpdef AdjustmentResult adjustment_result_from_procedure(AdjustmentProcedureResult record):
    cdef dict metadata = dict(record.metadata or {})
    return AdjustmentResult(
        record.transaction_id,
        record.guild_id,
        record.admin_id,
        record.target_id,
        record.amount,
        record.direction,
        record.created_at,
        record.target_balance_after,
        metadata,
    )
