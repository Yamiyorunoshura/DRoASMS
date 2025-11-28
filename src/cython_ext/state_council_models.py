from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import UUID

__all__ = [
    "StateCouncilConfig",
    "DepartmentConfig",
    "DepartmentRoleConfig",
    "GovernmentAccount",
    "WelfareDisbursement",
    "TaxRecord",
    "IdentityRecord",
    "CurrencyIssuance",
    "InterdepartmentTransfer",
    "DepartmentStats",
    "StateCouncilSummary",
    "SuspectProfile",
    "Suspect",
    "SuspectReleaseResult",
    "BusinessLicense",
    "BusinessLicenseListResult",
    "WelfareApplication",
    "WelfareApplicationListResult",
    "LicenseApplication",
    "LicenseApplicationListResult",
    "Company",
    "CompanyListResult",
    "AvailableLicense",
]


@dataclass(slots=True, frozen=True)
class StateCouncilConfig:
    guild_id: int
    leader_id: int | None
    leader_role_id: int | None
    internal_affairs_account_id: int
    finance_account_id: int
    security_account_id: int
    central_bank_account_id: int
    created_at: datetime
    updated_at: datetime
    treasury_account_id: int | None = None
    welfare_account_id: int | None = None
    auto_release_hours: int | None = None
    citizen_role_id: int | None = None
    suspect_role_id: int | None = None


@dataclass(slots=True, frozen=True)
class DepartmentConfig:
    id: int
    guild_id: int
    department: str
    role_id: int | None
    welfare_amount: int
    welfare_interval_hours: int
    tax_rate_basis: int
    tax_rate_percent: int
    max_issuance_per_month: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class DepartmentRoleConfig:
    id: int
    guild_id: int
    department: str
    role_id: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class GovernmentAccount:
    account_id: int
    guild_id: int
    department: str
    balance: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class IdentityRecord:
    record_id: UUID | int
    guild_id: int
    target_id: int
    action: str
    reason: str | None
    performed_by: int
    performed_at: datetime


@dataclass(slots=True, frozen=True)
class CurrencyIssuance:
    issuance_id: UUID | int
    guild_id: int
    amount: int
    reason: str
    month_period: str
    performed_by: int | None = None
    issued_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class InterdepartmentTransfer:
    transfer_id: UUID | int
    guild_id: int
    from_department: str
    to_department: str
    amount: int
    reason: str
    performed_by: int
    transferred_at: datetime


@dataclass(slots=True, frozen=True, init=False)
class WelfareDisbursement:
    disbursement_id: UUID | int
    guild_id: int
    recipient_id: int
    amount: int
    period: str | None
    reason: str | None
    disbursement_type: str | None
    disbursed_by: int | None
    reference_id: str | None
    created_at: datetime | None
    disbursed_at: datetime | None

    def __init__(
        self,
        *,
        guild_id: int,
        recipient_id: int,
        amount: int,
        disbursement_id: UUID | int | None = None,
        id: int | None = None,
        period: str | None = None,
        reason: str | None = None,
        disbursement_type: str | None = None,
        disbursed_by: int | None = None,
        reference_id: str | None = None,
        created_at: datetime | None = None,
        disbursed_at: datetime | None = None,
    ) -> None:
        object.__setattr__(self, "disbursement_id", disbursement_id or id or 0)
        object.__setattr__(self, "guild_id", int(guild_id))
        object.__setattr__(self, "recipient_id", int(recipient_id))
        object.__setattr__(self, "amount", int(amount))
        object.__setattr__(self, "period", period)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "disbursement_type", disbursement_type)
        object.__setattr__(self, "disbursed_by", disbursed_by)
        object.__setattr__(self, "reference_id", reference_id)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "disbursed_at", disbursed_at)


@dataclass(slots=True, frozen=True, init=False)
class TaxRecord:
    tax_id: UUID | int
    guild_id: int
    taxpayer_id: int
    taxable_amount: int | None
    tax_rate_percent: int | None
    tax_amount: int
    tax_type: str
    assessment_period: str
    collected_at: datetime | None
    collected_by: int | None

    def __init__(
        self,
        *,
        guild_id: int,
        taxpayer_id: int,
        tax_amount: int,
        tax_type: str,
        assessment_period: str,
        tax_id: UUID | int | None = None,
        id: int | None = None,
        collected_at: datetime | None = None,
        collected_by: int | None = None,
        taxable_amount: int | None = None,
        tax_rate_percent: int | None = None,
    ) -> None:
        object.__setattr__(self, "tax_id", tax_id or id or 0)
        object.__setattr__(self, "guild_id", int(guild_id))
        object.__setattr__(self, "taxpayer_id", int(taxpayer_id))
        object.__setattr__(self, "taxable_amount", taxable_amount)
        object.__setattr__(self, "tax_rate_percent", tax_rate_percent)
        object.__setattr__(self, "tax_amount", int(tax_amount))
        object.__setattr__(self, "tax_type", tax_type)
        object.__setattr__(self, "assessment_period", assessment_period)
        object.__setattr__(self, "collected_at", collected_at)
        object.__setattr__(self, "collected_by", collected_by)


@dataclass(slots=True, frozen=True)
class DepartmentStats:
    department: str
    balance: int
    total_welfare_disbursed: int
    total_tax_collected: int
    identity_actions_count: int
    currency_issued: int


@dataclass(slots=True, frozen=True)
class StateCouncilSummary:
    leader_id: int | None
    leader_role_id: int | None
    total_balance: int
    department_stats: dict[str, DepartmentStats]
    recent_transfers: Sequence[InterdepartmentTransfer]


@dataclass(slots=True, frozen=True)
class Suspect:
    suspect_id: int
    guild_id: int
    member_id: int
    arrested_by: int
    arrest_reason: str
    status: str  # detained, charged, released
    arrested_at: datetime
    charged_at: datetime | None
    released_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class SuspectProfile:
    member_id: int
    display_name: str
    joined_at: datetime | None
    arrested_at: datetime | None
    arrest_reason: str | None
    auto_release_at: datetime | None
    auto_release_hours: int | None
    is_detained: bool = False
    detained_at: datetime | None = None
    detained_by: int | None = None
    reason: str | None = None
    evidence: str | None = None
    released_by: int | None = None
    release_reason: str | None = None


@dataclass(slots=True, frozen=True)
class SuspectReleaseResult:
    suspect_id: int
    display_name: str | None
    released: bool
    was_detained: bool = False
    released_by: int | None = None
    release_reason: str | None = None
    detention_duration_hours: int | None = None
    reason: str | None = None
    error: str | None = None


@dataclass(slots=True, frozen=True)
class BusinessLicense:
    """商業許可資料模型。"""

    license_id: UUID
    guild_id: int
    user_id: int
    license_type: str
    issued_by: int
    issued_at: datetime
    expires_at: datetime
    status: str  # active, expired, revoked
    created_at: datetime
    updated_at: datetime
    revoked_by: int | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None


@dataclass(slots=True, frozen=True)
class BusinessLicenseListResult:
    """商業許可列表結果（含分頁資訊）。"""

    licenses: Sequence[BusinessLicense]
    total_count: int
    page: int
    page_size: int


@dataclass(slots=True, frozen=True)
class WelfareApplication:
    """福利申請資料模型。"""

    id: int
    guild_id: int
    applicant_id: int
    amount: int
    reason: str
    status: str  # pending, approved, rejected
    created_at: datetime
    reviewer_id: int | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None


@dataclass(slots=True, frozen=True)
class WelfareApplicationListResult:
    """福利申請列表結果（含分頁資訊）。"""

    applications: Sequence[WelfareApplication]
    total_count: int
    page: int
    page_size: int


@dataclass(slots=True, frozen=True)
class LicenseApplication:
    """商業許可申請資料模型。"""

    id: int
    guild_id: int
    applicant_id: int
    license_type: str
    reason: str
    status: str  # pending, approved, rejected
    created_at: datetime
    reviewer_id: int | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None


@dataclass(slots=True, frozen=True)
class LicenseApplicationListResult:
    """商業許可申請列表結果（含分頁資訊）。"""

    applications: Sequence[LicenseApplication]
    total_count: int
    page: int
    page_size: int


@dataclass(slots=True, frozen=True)
class Company:
    """公司資料模型。"""

    id: int
    guild_id: int
    owner_id: int
    license_id: UUID
    name: str
    account_id: int
    created_at: datetime
    updated_at: datetime
    license_type: str | None = None
    license_status: str | None = None


@dataclass(slots=True, frozen=True)
class CompanyListResult:
    """公司列表結果（含分頁資訊）。"""

    companies: Sequence[Company]
    total_count: int
    page: int
    page_size: int


@dataclass(slots=True, frozen=True)
class AvailableLicense:
    """可用於建立公司的許可證。"""

    license_id: UUID
    license_type: str
    issued_at: datetime
    expires_at: datetime
