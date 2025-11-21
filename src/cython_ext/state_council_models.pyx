# cython: language_level=3, embedsignature=True
# cython: optimize.use_switch=True
# cython: boundscheck=False
# cython: wraparound=False

cdef class StateCouncilConfig:
    cdef public long long guild_id
    cdef public object leader_id
    cdef public object leader_role_id
    cdef public long long internal_affairs_account_id
    cdef public long long finance_account_id
    cdef public long long security_account_id
    cdef public long long central_bank_account_id
    cdef public object created_at
    cdef public object updated_at
    cdef public object citizen_role_id
    cdef public object suspect_role_id

    def __cinit__(
        self,
        long long guild_id,
        object leader_id,
        object leader_role_id,
        long long internal_affairs_account_id,
        long long finance_account_id,
        long long security_account_id,
        long long central_bank_account_id,
        object created_at,
        object updated_at,
        object citizen_role_id=None,
        object suspect_role_id=None,
    ):
        self.guild_id = guild_id
        self.leader_id = leader_id
        self.leader_role_id = leader_role_id
        self.internal_affairs_account_id = internal_affairs_account_id
        self.finance_account_id = finance_account_id
        self.security_account_id = security_account_id
        self.central_bank_account_id = central_bank_account_id
        self.created_at = created_at
        self.updated_at = updated_at
        self.citizen_role_id = citizen_role_id
        self.suspect_role_id = suspect_role_id


cdef class DepartmentConfig:
    cdef public int id
    cdef public long long guild_id
    cdef public str department
    cdef public object role_id
    cdef public long long welfare_amount
    cdef public int welfare_interval_hours
    cdef public long long tax_rate_basis
    cdef public int tax_rate_percent
    cdef public long long max_issuance_per_month
    cdef public object created_at
    cdef public object updated_at

    def __cinit__(
        self,
        int id,
        long long guild_id,
        str department,
        object role_id,
        long long welfare_amount,
        int welfare_interval_hours,
        long long tax_rate_basis,
        int tax_rate_percent,
        long long max_issuance_per_month,
        object created_at,
        object updated_at,
    ):
        self.id = id
        self.guild_id = guild_id
        self.department = department
        self.role_id = role_id
        self.welfare_amount = welfare_amount
        self.welfare_interval_hours = welfare_interval_hours
        self.tax_rate_basis = tax_rate_basis
        self.tax_rate_percent = tax_rate_percent
        self.max_issuance_per_month = max_issuance_per_month
        self.created_at = created_at
        self.updated_at = updated_at


cdef class DepartmentRoleConfig:
    cdef public int id
    cdef public long long guild_id
    cdef public str department
    cdef public long long role_id
    cdef public object created_at
    cdef public object updated_at

    def __cinit__(
        self,
        int id,
        long long guild_id,
        str department,
        long long role_id,
        object created_at,
        object updated_at,
    ):
        self.id = id
        self.guild_id = guild_id
        self.department = department
        self.role_id = role_id
        self.created_at = created_at
        self.updated_at = updated_at


cdef class GovernmentAccount:
    cdef public long long account_id
    cdef public long long guild_id
    cdef public str department
    cdef public long long balance
    cdef public object created_at
    cdef public object updated_at

    def __cinit__(
        self,
        long long account_id,
        long long guild_id,
        str department,
        long long balance,
        object created_at,
        object updated_at,
    ):
        self.account_id = account_id
        self.guild_id = guild_id
        self.department = department
        self.balance = balance
        self.created_at = created_at
        self.updated_at = updated_at


cdef class IdentityRecord:
    cdef public object record_id
    cdef public long long guild_id
    cdef public long long target_id
    cdef public str action
    cdef public object reason
    cdef public long long performed_by
    cdef public object performed_at

    def __cinit__(
        self,
        object record_id,
        long long guild_id,
        long long target_id,
        str action,
        object reason,
        long long performed_by,
        object performed_at,
    ):
        self.record_id = record_id
        self.guild_id = guild_id
        self.target_id = target_id
        self.action = action
        self.reason = reason
        self.performed_by = performed_by
        self.performed_at = performed_at


cdef class CurrencyIssuance:
    cdef public object issuance_id
    cdef public long long guild_id
    cdef public long long amount
    cdef public str reason
    cdef public str month_period
    cdef public object performed_by
    cdef public object issued_at
    cdef public object created_at

    def __cinit__(
        self,
        object issuance_id,
        long long guild_id,
        long long amount,
        str reason,
        str month_period,
        object performed_by=None,
        object issued_at=None,
        object created_at=None,
    ):
        self.issuance_id = issuance_id
        self.guild_id = guild_id
        self.amount = amount
        self.reason = reason
        self.month_period = month_period
        self.performed_by = performed_by
        self.issued_at = issued_at
        self.created_at = created_at


cdef class InterdepartmentTransfer:
    cdef public object transfer_id
    cdef public long long guild_id
    cdef public str from_department
    cdef public str to_department
    cdef public long long amount
    cdef public str reason
    cdef public long long performed_by
    cdef public object transferred_at

    def __cinit__(
        self,
        object transfer_id,
        long long guild_id,
        str from_department,
        str to_department,
        long long amount,
        str reason,
        long long performed_by,
        object transferred_at,
    ):
        self.transfer_id = transfer_id
        self.guild_id = guild_id
        self.from_department = from_department
        self.to_department = to_department
        self.amount = amount
        self.reason = reason
        self.performed_by = performed_by
        self.transferred_at = transferred_at


cdef class WelfareDisbursement:
    cdef public object disbursement_id
    cdef public long long guild_id
    cdef public long long recipient_id
    cdef public long long amount
    cdef public object period
    cdef public object reason
    cdef public object disbursement_type
    cdef public object disbursed_by
    cdef public object reference_id
    cdef public object created_at
    cdef public object disbursed_at

    def __cinit__(
        self,
        long long guild_id,
        long long recipient_id,
        long long amount,
        object disbursement_id=None,
        object id=None,
        object period=None,
        object reason=None,
        object disbursement_type=None,
        object disbursed_by=None,
        object reference_id=None,
        object created_at=None,
        object disbursed_at=None,
    ):
        self.disbursement_id = disbursement_id if disbursement_id is not None else (
            id if id is not None else 0
        )
        self.guild_id = guild_id
        self.recipient_id = recipient_id
        self.amount = amount
        self.period = period
        self.reason = reason
        self.disbursement_type = disbursement_type
        self.disbursed_by = disbursed_by
        self.reference_id = reference_id
        self.created_at = created_at
        self.disbursed_at = disbursed_at


cdef class TaxRecord:
    cdef public object tax_id
    cdef public long long guild_id
    cdef public long long taxpayer_id
    cdef public object taxable_amount
    cdef public object tax_rate_percent
    cdef public long long tax_amount
    cdef public str tax_type
    cdef public str assessment_period
    cdef public object collected_at
    cdef public object collected_by

    def __cinit__(
        self,
        long long guild_id,
        long long taxpayer_id,
        long long tax_amount,
        str tax_type,
        str assessment_period,
        object tax_id=None,
        object id=None,
        object collected_at=None,
        object collected_by=None,
        object taxable_amount=None,
        object tax_rate_percent=None,
    ):
        self.tax_id = tax_id if tax_id is not None else (id if id is not None else 0)
        self.guild_id = guild_id
        self.taxpayer_id = taxpayer_id
        self.taxable_amount = taxable_amount
        self.tax_rate_percent = tax_rate_percent
        self.tax_amount = tax_amount
        self.tax_type = tax_type
        self.assessment_period = assessment_period
        self.collected_at = collected_at
        self.collected_by = collected_by


cdef class DepartmentStats:
    cdef public str department
    cdef public int balance
    cdef public int total_welfare_disbursed
    cdef public int total_tax_collected
    cdef public int identity_actions_count
    cdef public int currency_issued

    def __cinit__(
        self,
        str department,
        int balance,
        int total_welfare_disbursed,
        int total_tax_collected,
        int identity_actions_count,
        int currency_issued,
    ):
        self.department = department
        self.balance = balance
        self.total_welfare_disbursed = total_welfare_disbursed
        self.total_tax_collected = total_tax_collected
        self.identity_actions_count = identity_actions_count
        self.currency_issued = currency_issued


cdef class StateCouncilSummary:
    cdef public object leader_id
    cdef public object leader_role_id
    cdef public int total_balance
    cdef public dict department_stats
    cdef public object recent_transfers

    def __cinit__(
        self,
        object leader_id,
        object leader_role_id,
        int total_balance,
        dict department_stats,
        object recent_transfers,
    ):
        self.leader_id = leader_id
        self.leader_role_id = leader_role_id
        self.total_balance = total_balance
        self.department_stats = department_stats
        self.recent_transfers = recent_transfers


cdef class SuspectProfile:
    cdef public int member_id
    cdef public str display_name
    cdef public object joined_at
    cdef public object arrested_at
    cdef public object arrest_reason
    cdef public object auto_release_at
    cdef public object auto_release_hours

    def __cinit__(
        self,
        int member_id,
        str display_name,
        object joined_at,
        object arrested_at,
        object arrest_reason,
        object auto_release_at,
        object auto_release_hours,
    ):
        self.member_id = member_id
        self.display_name = display_name
        self.joined_at = joined_at
        self.arrested_at = arrested_at
        self.arrest_reason = arrest_reason
        self.auto_release_at = auto_release_at
        self.auto_release_hours = auto_release_hours


cdef class Suspect:
    cdef public int id
    cdef public int guild_id
    cdef public int member_id
    cdef public int arrested_by
    cdef public str arrest_reason
    cdef public str status  # detained, charged, released
    cdef public object arrested_at
    cdef public object charged_at
    cdef public object released_at
    cdef public object created_at
    cdef public object updated_at

    def __cinit__(
        self,
        int id,
        int guild_id,
        int member_id,
        int arrested_by,
        str arrest_reason,
        str status,
        object arrested_at,
        object charged_at=None,
        object released_at=None,
        object created_at=None,
        object updated_at=None,
    ):
        self.id = id
        self.guild_id = guild_id
        self.member_id = member_id
        self.arrested_by = arrested_by
        self.arrest_reason = arrest_reason
        self.status = status
        self.arrested_at = arrested_at
        self.charged_at = charged_at
        self.released_at = released_at
        self.created_at = created_at
        self.updated_at = updated_at


cdef class SuspectReleaseResult:
    cdef public int suspect_id
    cdef public object display_name
    cdef public bint released
    cdef public object reason
    cdef public object error

    def __cinit__(
        self,
        int suspect_id,
        object display_name,
        bint released,
        object reason=None,
        object error=None,
    ):
        self.suspect_id = suspect_id
        self.display_name = display_name
        self.released = released
        self.reason = reason
        self.error = error
