# cython: language_level=3, embedsignature=True

cdef class PendingTransfer:
    cdef public object transfer_id
    cdef public int guild_id
    cdef public int initiator_id
    cdef public int target_id
    cdef public int amount
    cdef public str status
    cdef public dict checks
    cdef public int retry_count
    cdef public object expires_at
    cdef public dict metadata
    cdef public object created_at
    cdef public object updated_at

    def __cinit__(
        self,
        object transfer_id,
        int guild_id,
        int initiator_id,
        int target_id,
        int amount,
        str status,
        dict checks,
        int retry_count,
        object expires_at,
        dict metadata,
        object created_at,
        object updated_at,
    ):
        self.transfer_id = transfer_id
        self.guild_id = guild_id
        self.initiator_id = initiator_id
        self.target_id = target_id
        self.amount = amount
        self.status = status
        self.checks = checks
        self.retry_count = retry_count
        self.expires_at = expires_at
        self.metadata = metadata
        self.created_at = created_at
        self.updated_at = updated_at


cpdef PendingTransfer build_pending_transfer(object record):
    cdef dict checks
    cdef dict metadata
    if isinstance(record, dict):
        checks = dict(record.get("checks") or {})
        metadata = dict(record.get("metadata") or {})
        return PendingTransfer(
            record["transfer_id"],
            int(record["guild_id"]),
            int(record["initiator_id"]),
            int(record["target_id"]),
            int(record["amount"]),
            str(record["status"]),
            checks,
            int(record["retry_count"]),
            record["expires_at"],
            metadata,
            record["created_at"],
            record["updated_at"],
        )
    else:
        checks = dict(getattr(record, "checks", {}) or {})
        metadata = dict(getattr(record, "metadata", {}) or {})
        return PendingTransfer(
            getattr(record, "transfer_id"),
            int(getattr(record, "guild_id")),
            int(getattr(record, "initiator_id")),
            int(getattr(record, "target_id")),
            int(getattr(record, "amount")),
            str(getattr(record, "status")),
            checks,
            int(getattr(record, "retry_count")),
            getattr(record, "expires_at"),
            metadata,
            getattr(record, "created_at"),
            getattr(record, "updated_at"),
        )
