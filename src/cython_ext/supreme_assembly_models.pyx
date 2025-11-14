# cython: language_level=3, embedsignature=True

cdef class SupremeAssemblyConfig:
    cdef public long long guild_id
    cdef public long long speaker_role_id
    cdef public long long member_role_id
    cdef public object created_at
    cdef public object updated_at

    def __cinit__(self, long long guild_id, long long speaker_role_id, long long member_role_id,
                  object created_at, object updated_at):
        self.guild_id = guild_id
        self.speaker_role_id = speaker_role_id
        self.member_role_id = member_role_id
        self.created_at = created_at
        self.updated_at = updated_at


cdef class Proposal:
    cdef public object proposal_id
    cdef public long long guild_id
    cdef public long long proposer_id
    cdef public object title
    cdef public object description
    cdef public int snapshot_n
    cdef public int threshold_t
    cdef public object deadline_at
    cdef public str status
    cdef public bint reminder_sent
    cdef public object created_at
    cdef public object updated_at

    def __cinit__(self, object proposal_id, long long guild_id, long long proposer_id, object title,
                  object description, int snapshot_n, int threshold_t, object deadline_at,
                  str status, bint reminder_sent, object created_at, object updated_at):
        self.proposal_id = proposal_id
        self.guild_id = guild_id
        self.proposer_id = proposer_id
        self.title = title
        self.description = description
        self.snapshot_n = snapshot_n
        self.threshold_t = threshold_t
        self.deadline_at = deadline_at
        self.status = status
        self.reminder_sent = reminder_sent
        self.created_at = created_at
        self.updated_at = updated_at


cdef class Tally:
    cdef public int approve
    cdef public int reject
    cdef public int abstain
    cdef public int total_voted

    def __cinit__(self, int approve, int reject, int abstain, int total_voted):
        self.approve = approve
        self.reject = reject
        self.abstain = abstain
        self.total_voted = total_voted


cdef class Summon:
    cdef public object summon_id
    cdef public long long guild_id
    cdef public long long invoked_by
    cdef public long long target_id
    cdef public str target_kind
    cdef public object note
    cdef public bint delivered
    cdef public object delivered_at
    cdef public object created_at

    def __cinit__(
        self,
        object summon_id,
        long long guild_id,
        long long invoked_by,
        long long target_id,
        str target_kind,
        object note,
        bint delivered,
        object delivered_at,
        object created_at,
    ):
        self.summon_id = summon_id
        self.guild_id = guild_id
        self.invoked_by = invoked_by
        self.target_id = target_id
        self.target_kind = target_kind
        self.note = note
        self.delivered = delivered
        self.delivered_at = delivered_at
        self.created_at = created_at


cdef class VoteTotals:
    cdef public int approve
    cdef public int reject
    cdef public int abstain
    cdef public int threshold_t
    cdef public int snapshot_n
    cdef public int remaining_unvoted

    def __cinit__(
        self,
        int approve,
        int reject,
        int abstain,
        int threshold_t,
        int snapshot_n,
        int remaining_unvoted,
    ):
        self.approve = approve
        self.reject = reject
        self.abstain = abstain
        self.threshold_t = threshold_t
        self.snapshot_n = snapshot_n
        self.remaining_unvoted = remaining_unvoted
