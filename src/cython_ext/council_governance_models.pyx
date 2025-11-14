# cython: language_level=3, embedsignature=True

cdef class CouncilConfig:
    cdef public long long guild_id
    cdef public long long council_role_id
    cdef public long long council_account_member_id
    cdef public object created_at
    cdef public object updated_at

    def __cinit__(self, long long guild_id, long long council_role_id, long long council_account_member_id,
                  object created_at, object updated_at):
        self.guild_id = guild_id
        self.council_role_id = council_role_id
        self.council_account_member_id = council_account_member_id
        self.created_at = created_at
        self.updated_at = updated_at


cdef class CouncilRoleConfig:
    cdef public long long guild_id
    cdef public long long role_id
    cdef public object created_at
    cdef public object updated_at
    cdef public object id

    def __cinit__(self, long long guild_id, long long role_id, object created_at, object updated_at, object id=None):
        self.guild_id = guild_id
        self.role_id = role_id
        self.created_at = created_at
        self.updated_at = updated_at
        self.id = id


cdef class Proposal:
    cdef public object proposal_id
    cdef public long long guild_id
    cdef public long long proposer_id
    cdef public long long target_id
    cdef public long long amount
    cdef public object description
    cdef public object attachment_url
    cdef public int snapshot_n
    cdef public int threshold_t
    cdef public object deadline_at
    cdef public str status
    cdef public bint reminder_sent
    cdef public object created_at
    cdef public object updated_at
    cdef public object target_department_id

    def __cinit__(self, object proposal_id, long long guild_id, long long proposer_id, long long target_id, long long amount,
                  object description, object attachment_url, int snapshot_n, int threshold_t,
                  object deadline_at, str status, bint reminder_sent, object created_at,
                  object updated_at, object target_department_id=None):
        self.proposal_id = proposal_id
        self.guild_id = guild_id
        self.proposer_id = proposer_id
        self.target_id = target_id
        self.amount = amount
        self.description = description
        self.attachment_url = attachment_url
        self.snapshot_n = snapshot_n
        self.threshold_t = threshold_t
        self.deadline_at = deadline_at
        self.status = status
        self.reminder_sent = reminder_sent
        self.created_at = created_at
        self.updated_at = updated_at
        self.target_department_id = target_department_id

    def replace(self, **kwargs):
        """Create a new Proposal with specified fields replaced."""
        new_obj = Proposal(
            self.proposal_id, self.guild_id, self.proposer_id, self.target_id, self.amount,
            self.description, self.attachment_url, self.snapshot_n, self.threshold_t,
            self.deadline_at, self.status, self.reminder_sent, self.created_at,
            self.updated_at, self.target_department_id
        )
        for key, value in kwargs.items():
            if hasattr(new_obj, key):
                setattr(new_obj, key, value)
        return new_obj


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
