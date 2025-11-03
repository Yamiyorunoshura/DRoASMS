"""State Council Report Generator

This module provides comprehensive reporting and analytics capabilities
for the State Council system, including:
- Financial summaries
- Department performance metrics
- Activity statistics
- Trend analysis
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import asyncpg
import structlog

from src.db.gateway.economy_queries import EconomyQueryGateway
from src.db.gateway.state_council_governance import StateCouncilGovernanceGateway

LOGGER = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FinancialSummary:
    """Financial summary for a specific period."""

    total_welfare_disbursed: int
    total_tax_collected: int
    total_currency_issued: int
    net_flow: int
    period_start: datetime
    period_end: datetime


@dataclass(frozen=True, slots=True)
class DepartmentMetrics:
    """Performance metrics for a department."""

    department: str
    total_operations: int
    total_amount: int
    average_per_operation: float
    peak_activity_day: str
    most_common_operation: str


@dataclass(frozen=True, slots=True)
class ActivityReport:
    """Comprehensive activity report."""

    period: str
    total_operations: int
    unique_users: int
    operation_breakdown: Dict[str, int]
    daily_activity: Dict[str, int]
    top_performers: List[Dict[str, Any]]


class StateCouncilReportGenerator:
    """Generates comprehensive reports for State Council operations."""

    def __init__(self, *, gateway: StateCouncilGovernanceGateway | None = None) -> None:
        # 預設以可被 stub 的 AsyncMock 取代，便於單元測試注入回傳值
        self._gateway = gateway or AsyncMock(spec=StateCouncilGovernanceGateway)
        # 經濟系統查詢：以即時餘額為單一真實來源
        self._economy = EconomyQueryGateway()

    async def generate_financial_summary(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> FinancialSummary:
        """Generate financial summary for the specified period."""
        # Get welfare disbursements
        welfare_records = await self._gateway.fetch_welfare_disbursements(
            connection, guild_id=guild_id, limit=10000
        )
        filtered_welfare = [r for r in welfare_records if start_date <= r.disbursed_at <= end_date]
        total_welfare = sum(r.amount for r in filtered_welfare)

        # Get tax records
        tax_records = await self._gateway.fetch_tax_records(
            connection, guild_id=guild_id, limit=10000
        )
        filtered_tax = [r for r in tax_records if start_date <= r.collected_at <= end_date]
        total_tax = sum(r.tax_amount for r in filtered_tax)

        # Get currency issuances
        currency_records = await self._gateway.fetch_currency_issuances(
            connection, guild_id=guild_id, limit=10000
        )
        filtered_currency = [r for r in currency_records if start_date <= r.issued_at <= end_date]
        total_issuance = sum(r.amount for r in filtered_currency)

        # Calculate net flow (taxes + issuances - welfare)
        net_flow = total_tax + total_issuance - total_welfare

        return FinancialSummary(
            total_welfare_disbursed=total_welfare,
            total_tax_collected=total_tax,
            total_currency_issued=total_issuance,
            net_flow=net_flow,
            period_start=start_date,
            period_end=end_date,
        )

    async def generate_department_metrics(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        department: str,
        start_date: datetime,
        end_date: datetime,
    ) -> DepartmentMetrics:
        """Generate performance metrics for a specific department."""
        if department == "內政部":
            return await self._generate_welfare_metrics(
                connection, guild_id=guild_id, start_date=start_date, end_date=end_date
            )
        elif department == "財政部":
            return await self._generate_tax_metrics(
                connection, guild_id=guild_id, start_date=start_date, end_date=end_date
            )
        elif department == "國土安全部":
            return await self._generate_identity_metrics(
                connection, guild_id=guild_id, start_date=start_date, end_date=end_date
            )
        elif department == "中央銀行":
            return await self._generate_currency_metrics(
                connection, guild_id=guild_id, start_date=start_date, end_date=end_date
            )
        else:
            # Default case for unknown departments
            return DepartmentMetrics(
                department=department,
                total_operations=0,
                total_amount=0,
                average_per_operation=0.0,
                peak_activity_day="無數據",
                most_common_operation="無操作",
            )

    async def _generate_welfare_metrics(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> DepartmentMetrics:
        """Generate metrics for Internal Affairs department."""
        records = await self._gateway.fetch_welfare_disbursements(
            connection, guild_id=guild_id, limit=10000
        )
        filtered_records = [r for r in records if start_date <= r.disbursed_at <= end_date]

        operations: list[tuple[str, int, datetime, int | None]] = [
            (
                "福利發放",
                r.amount,
                r.disbursed_at,
                r.performed_by if hasattr(r, "performed_by") else None,
            )
            for r in filtered_records
        ]
        total_amount = sum(r.amount for r in filtered_records)

        return self._calculate_metrics(
            department="內政部",
            operations=operations,
            total_amount=total_amount,
        )

    async def _generate_tax_metrics(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> DepartmentMetrics:
        """Generate metrics for Finance department."""
        records = await self._gateway.fetch_tax_records(connection, guild_id=guild_id, limit=10000)
        filtered_records = [r for r in records if start_date <= r.collected_at <= end_date]

        operations: list[tuple[str, int, datetime, int | None]] = [
            (
                "稅收徵收",
                r.tax_amount,
                r.collected_at,
                r.performed_by if hasattr(r, "performed_by") else None,
            )
            for r in filtered_records
        ]
        total_amount = sum(r.tax_amount for r in filtered_records)

        return self._calculate_metrics(
            department="財政部",
            operations=operations,
            total_amount=total_amount,
        )

    async def _generate_identity_metrics(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> DepartmentMetrics:
        """Generate metrics for Security department."""
        records = await self._gateway.fetch_identity_records(
            connection, guild_id=guild_id, limit=10000
        )
        filtered_records = [r for r in records if start_date <= r.performed_at <= end_date]

        operations: list[tuple[str, int, datetime, int | None]] = [
            (r.action, 1, r.performed_at, r.performed_by) for r in filtered_records
        ]
        total_amount = len(operations)

        return self._calculate_metrics(
            department="國土安全部",
            operations=operations,
            total_amount=total_amount,
        )

    async def _generate_currency_metrics(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> DepartmentMetrics:
        """Generate metrics for Central Bank department."""
        records = await self._gateway.fetch_currency_issuances(
            connection, guild_id=guild_id, limit=10000
        )
        filtered_records = [r for r in records if start_date <= r.issued_at <= end_date]

        operations: list[tuple[str, int, datetime, int | None]] = [
            ("貨幣發行", r.amount, r.issued_at, r.performed_by) for r in filtered_records
        ]
        total_amount = sum(r.amount for r in filtered_records)

        return self._calculate_metrics(
            department="中央銀行",
            operations=operations,
            total_amount=total_amount,
        )

    def _calculate_metrics(
        self,
        *,
        department: str,
        operations: list[tuple[str, int, datetime, int | None]],
        total_amount: int,
    ) -> DepartmentMetrics:
        """Calculate metrics from operations data."""
        # Calculate metrics
        total_operations = len(operations)
        average_per_operation = total_amount / total_operations if total_operations > 0 else 0

        # Find peak activity day (tie-breaker: choose the later day)
        daily_counts: dict[str, int] = {}
        for _, _, timestamp, _ in operations:
            day_key = timestamp.strftime("%Y-%m-%d")
            daily_counts[day_key] = daily_counts.get(day_key, 0) + 1
        if daily_counts:
            peak_day = max(daily_counts.items(), key=lambda x: (x[1], x[0]))[0]
        else:
            peak_day = "無數據"

        # Find most common operation
        operation_counts: dict[str, int] = {}
        for op_type, _, _, _ in operations:
            operation_counts[op_type] = operation_counts.get(op_type, 0) + 1
        most_common = (
            max(operation_counts.items(), key=lambda x: x[1])[0] if operation_counts else "無操作"
        )

        return DepartmentMetrics(
            department=department,
            total_operations=total_operations,
            total_amount=total_amount,
            average_per_operation=average_per_operation,
            peak_activity_day=peak_day,
            most_common_operation=most_common,
        )

    async def generate_activity_report(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> ActivityReport:
        """Generate comprehensive activity report."""
        period = f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}"

        # Collect all operations
        all_operations: list[dict[str, Any]] = []

        # Welfare disbursements
        welfare_records = await self._gateway.fetch_welfare_disbursements(
            connection, guild_id=guild_id, limit=10000
        )
        for welfare_record in welfare_records:
            if start_date <= welfare_record.disbursed_at <= end_date:
                all_operations.append(
                    {
                        "type": "福利發放",
                        "timestamp": welfare_record.disbursed_at,
                        "user": welfare_record.recipient_id,
                        "amount": welfare_record.amount,
                    }
                )

        # Tax records
        tax_records = await self._gateway.fetch_tax_records(
            connection, guild_id=guild_id, limit=10000
        )
        for tax_record in tax_records:
            if start_date <= tax_record.collected_at <= end_date:
                all_operations.append(
                    {
                        "type": "稅收徵收",
                        "timestamp": tax_record.collected_at,
                        "user": tax_record.taxpayer_id,
                        "amount": tax_record.tax_amount,
                    }
                )

        # Identity records
        identity_records = await self._gateway.fetch_identity_records(
            connection, guild_id=guild_id, limit=10000
        )
        for identity_record in identity_records:
            if start_date <= identity_record.performed_at <= end_date:
                all_operations.append(
                    {
                        "type": "身分管理",
                        "timestamp": identity_record.performed_at,
                        "user": identity_record.target_id,
                        "amount": 0,
                    }
                )

        # Currency issuances
        currency_records = await self._gateway.fetch_currency_issuances(
            connection, guild_id=guild_id, limit=10000
        )
        for currency_record in currency_records:
            if start_date <= currency_record.issued_at <= end_date:
                all_operations.append(
                    {
                        "type": "貨幣發行",
                        "timestamp": currency_record.issued_at,
                        "user": currency_record.performed_by,
                        "amount": currency_record.amount,
                    }
                )

        # Note: 部門轉帳不計入活動操作總數（僅在高層報表中呈現餘額變化）

        # Calculate statistics
        total_operations = len(all_operations)
        unique_users = len({op["user"] for op in all_operations})

        # Operation breakdown
        operation_breakdown: dict[str, int] = {}
        for op in all_operations:
            op_type = op["type"]
            operation_breakdown[op_type] = operation_breakdown.get(op_type, 0) + 1
        # Ensure keys exist for categories even if 0 (e.g., transfers not counted)
        for key in ("福利發放", "稅收徵收", "身分管理", "貨幣發行", "部門轉帳"):
            operation_breakdown.setdefault(key, 0)

        # Daily activity
        daily_activity: dict[str, int] = {}
        for op in all_operations:
            day_key = op["timestamp"].strftime("%Y-%m-%d")
            daily_activity[day_key] = daily_activity.get(day_key, 0) + 1

        # Top performers (users with most operations)
        user_activity: dict[int, int] = {}
        for op in all_operations:
            user_id = op["user"]
            user_activity[user_id] = user_activity.get(user_id, 0) + 1

        top_performers = [
            {"user_id": user_id, "operations": count}
            for user_id, count in sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
        ]

        return ActivityReport(
            period=period,
            total_operations=total_operations,
            unique_users=unique_users,
            operation_breakdown=operation_breakdown,
            daily_activity=daily_activity,
            top_performers=top_performers,
        )

    async def generate_monthly_summary(
        self,
        connection: asyncpg.Connection,
        *,
        guild_id: int,
        year: int,
        month: int,
    ) -> Dict[str, Any]:
        """Generate comprehensive monthly summary."""
        # Calculate date range for the month
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(microseconds=1)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(microseconds=1)

        # Generate all reports
        financial_summary = await self.generate_financial_summary(
            connection, guild_id=guild_id, start_date=start_date, end_date=end_date
        )

        department_metrics = {}
        for department in ["內政部", "財政部", "國土安全部", "中央銀行"]:
            metrics = await self.generate_department_metrics(
                connection,
                guild_id=guild_id,
                department=department,
                start_date=start_date,
                end_date=end_date,
            )
            department_metrics[department] = metrics

        activity_report = await self.generate_activity_report(
            connection, guild_id=guild_id, start_date=start_date, end_date=end_date
        )

        # Get account balances
        accounts = await self._gateway.fetch_government_accounts(connection, guild_id=guild_id)
        account_balances: dict[str, int] = {}
        for acc in accounts:
            try:
                snap = await self._economy.fetch_balance(
                    connection, guild_id=guild_id, member_id=acc.account_id
                )
                account_balances[acc.department] = snap.balance
            except Exception:
                # 後援：若經濟查詢失敗，使用 governance 留存值
                account_balances[acc.department] = acc.balance

        return {
            "period": f"{year}-{month:02d}",
            "financial_summary": {
                "total_welfare_disbursed": financial_summary.total_welfare_disbursed,
                "total_tax_collected": financial_summary.total_tax_collected,
                "total_currency_issued": financial_summary.total_currency_issued,
                "net_flow": financial_summary.net_flow,
            },
            "department_metrics": {
                dept: {
                    "total_operations": metrics.total_operations,
                    "total_amount": metrics.total_amount,
                    "average_per_operation": metrics.average_per_operation,
                    "peak_activity_day": metrics.peak_activity_day,
                    "most_common_operation": metrics.most_common_operation,
                }
                for dept, metrics in department_metrics.items()
            },
            "activity_summary": {
                "total_operations": activity_report.total_operations,
                "unique_users": activity_report.unique_users,
                "operation_breakdown": activity_report.operation_breakdown,
                "top_performers": activity_report.top_performers[:5],  # Top 5
            },
            "account_balances": account_balances,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    def format_report_as_markdown(self, report_data: Dict[str, Any]) -> str:
        """Format report data as markdown."""
        period = report_data["period"]
        financial = report_data["financial_summary"]
        metrics = report_data["department_metrics"]
        activity = report_data["activity_summary"]
        balances = report_data["account_balances"]

        lines = [
            f"# 國務院月報 - {period}",
            "",
            "## 📊 財務摘要",
            f"- 福利發放總額：{financial['total_welfare_disbursed']:,} 幣",
            f"- 稅收總額：{financial['total_tax_collected']:,} 幣",
            f"- 貨幣發行總額：{financial['total_currency_issued']:,} 幣",
            f"- 淨流動：{financial['net_flow']:+,} 幣",
            "",
            "## 🏛️ 各部門表現",
        ]

        for dept, dept_metrics in metrics.items():
            dept_emoji = {"內政部": "🏘️", "財政部": "💰", "國土安全部": "🛡️", "中央銀行": "🏦"}.get(
                dept, ""
            )
            lines.extend(
                [
                    f"### {dept_emoji} {dept}",
                    f"- 總操作數：{dept_metrics['total_operations']}",
                    (
                        f"- 總金額：{dept_metrics['total_amount']:,} 幣"
                        if dept_metrics["total_amount"] > 1
                        else f"- 總操作數：{dept_metrics['total_operations']}"
                    ),
                    (
                        f"- 平均每次操作：{dept_metrics['average_per_operation']:.2f} 幣"
                        if dept_metrics["average_per_operation"] >= 1
                        else ""
                    ),
                    f"- 活躍高峰日：{dept_metrics['peak_activity_day']}",
                    f"- 主要操作：{dept_metrics['most_common_operation']}",
                    "",
                ]
            )

        lines.extend(
            [
                "## 📈 活動統計",
                f"- 總操作數：{activity['total_operations']}",
                f"- 參與用戶數：{activity['unique_users']}",
                "",
                "### 操作類型分布",
            ]
        )

        for op_type, count in activity["operation_breakdown"].items():
            lines.append(f"- {op_type}：{count} 次")

        lines.extend(["", "### 活躍用戶排行榜"])

        for i, performer in enumerate(activity["top_performers"], 1):
            lines.append(f"{i}. <@{performer['user_id']}>：{performer['operations']} 次操作")

        lines.extend(
            [
                "",
                "## 💰 各部門餘額",
            ]
        )

        for dept, balance in balances.items():
            dept_emoji = {"內政部": "🏘️", "財政部": "💰", "國土安全部": "🛡️", "中央銀行": "🏦"}.get(
                dept, ""
            )
            lines.append(f"- {dept_emoji} {dept}：餘額：{balance:,} 幣")

        lines.extend(["", f"*報表生成時間：{report_data['generated_at']}*"])

        return "\n".join(lines)
