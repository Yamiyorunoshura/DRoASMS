"""Unit tests for State Council report generator."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID

import asyncpg
import pytest

from src.bot.services.state_council_reports import (
    ActivityReport,
    DepartmentMetrics,
    FinancialSummary,
    StateCouncilReportGenerator,
)
from src.db.gateway.state_council_governance import (
    CurrencyIssuance,
    IdentityRecord,
    InterdepartmentTransfer,
    TaxRecord,
    WelfareDisbursement,
)


def _snowflake() -> int:
    """Generate a Discord snowflake-like ID."""
    return secrets.randbits(63)


@pytest.mark.unit
class TestStateCouncilReportGenerator:
    """Test cases for StateCouncilReportGenerator."""

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock(spec=asyncpg.Connection)

    @pytest.fixture
    def generator(self) -> StateCouncilReportGenerator:
        """Create report generator instance."""
        return StateCouncilReportGenerator()

    @pytest.fixture
    def sample_welfare_records(self) -> list[WelfareDisbursement]:
        """Sample welfare disbursement records."""
        return [
            WelfareDisbursement(
                disbursement_id=UUID(int=1),
                guild_id=_snowflake(),
                recipient_id=_snowflake(),
                amount=1000,
                disbursement_type="定期福利",
                reference_id=None,
                disbursed_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
            ),
            WelfareDisbursement(
                disbursement_id=UUID(int=2),
                guild_id=_snowflake(),
                recipient_id=_snowflake(),
                amount=1500,
                disbursement_type="特殊福利",
                reference_id="REF123",
                disbursed_at=datetime(2024, 1, 20, tzinfo=timezone.utc),
            ),
        ]

    @pytest.fixture
    def sample_tax_records(self) -> list[TaxRecord]:
        """Sample tax records."""
        return [
            TaxRecord(
                tax_id=UUID(int=1),
                guild_id=_snowflake(),
                taxpayer_id=_snowflake(),
                taxable_amount=10000,
                tax_rate_percent=10,
                tax_amount=1000,
                tax_type="所得稅",
                assessment_period="2024-01",
                collected_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
            ),
            TaxRecord(
                tax_id=UUID(int=2),
                guild_id=_snowflake(),
                taxpayer_id=_snowflake(),
                taxable_amount=20000,
                tax_rate_percent=15,
                tax_amount=3000,
                tax_type="所得稅",
                assessment_period="2024-01",
                collected_at=datetime(2024, 1, 25, tzinfo=timezone.utc),
            ),
        ]

    @pytest.fixture
    def sample_identity_records(self) -> list[IdentityRecord]:
        """Sample identity records."""
        return [
            IdentityRecord(
                record_id=UUID(int=1),
                guild_id=_snowflake(),
                target_id=_snowflake(),
                action="移除公民身分",
                reason="違反規定",
                performed_by=_snowflake(),
                performed_at=datetime(2024, 1, 5, tzinfo=timezone.utc),
            ),
            IdentityRecord(
                record_id=UUID(int=2),
                guild_id=_snowflake(),
                target_id=_snowflake(),
                action="標記疑犯",
                reason="可疑行為",
                performed_by=_snowflake(),
                performed_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
            ),
        ]

    @pytest.fixture
    def sample_currency_records(self) -> list[CurrencyIssuance]:
        """Sample currency issuance records."""
        return [
            CurrencyIssuance(
                issuance_id=UUID(int=1),
                guild_id=_snowflake(),
                amount=5000,
                reason="經濟刺激",
                performed_by=_snowflake(),
                month_period="2024-01",
                issued_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
            CurrencyIssuance(
                issuance_id=UUID(int=2),
                guild_id=_snowflake(),
                amount=3000,
                reason="流動性支持",
                performed_by=_snowflake(),
                month_period="2024-01",
                issued_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
            ),
        ]

    @pytest.fixture
    def sample_transfer_records(self) -> list[InterdepartmentTransfer]:
        """Sample interdepartment transfer records."""
        return [
            InterdepartmentTransfer(
                transfer_id=UUID(int=1),
                guild_id=_snowflake(),
                from_department="內政部",
                to_department="財政部",
                amount=2000,
                reason="預算調整",
                performed_by=_snowflake(),
                transferred_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
            ),
            InterdepartmentTransfer(
                transfer_id=UUID(int=2),
                guild_id=_snowflake(),
                from_department="財政部",
                to_department="國土安全部",
                amount=1500,
                reason="安全預算",
                performed_by=_snowflake(),
                transferred_at=datetime(2024, 1, 20, tzinfo=timezone.utc),
            ),
        ]

    # --- Financial Summary Tests ---

    @pytest.mark.asyncio
    async def test_generate_financial_summary(
        self,
        generator: StateCouncilReportGenerator,
        mock_connection: AsyncMock,
        sample_welfare_records: list[WelfareDisbursement],
        sample_tax_records: list[TaxRecord],
        sample_currency_records: list[CurrencyIssuance],
    ) -> None:
        """Test generating financial summary."""
        guild_id = _snowflake()
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        # Mock gateway methods (cast for mypy strict)
        gateway = cast(AsyncMock, generator._gateway)
        gateway.fetch_welfare_disbursements.return_value = sample_welfare_records
        gateway.fetch_tax_records.return_value = sample_tax_records
        gateway.fetch_currency_issuances.return_value = sample_currency_records

        summary = await generator.generate_financial_summary(
            mock_connection,
            guild_id=guild_id,
            start_date=start_date,
            end_date=end_date,
        )

        assert isinstance(summary, FinancialSummary)
        assert summary.total_welfare_disbursed == 2500  # 1000 + 1500
        assert summary.total_tax_collected == 4000  # 1000 + 3000
        assert summary.total_currency_issued == 8000  # 5000 + 3000
        assert summary.net_flow == 9500  # 4000 + 8000 - 2500
        assert summary.period_start == start_date
        assert summary.period_end == end_date

        # Verify gateway calls
        gateway.fetch_welfare_disbursements.assert_called_once_with(
            mock_connection, guild_id=guild_id, limit=10000
        )
        gateway.fetch_tax_records.assert_called_once_with(
            mock_connection, guild_id=guild_id, limit=10000
        )
        gateway.fetch_currency_issuances.assert_called_once_with(
            mock_connection, guild_id=guild_id, limit=10000
        )

    @pytest.mark.asyncio
    async def test_generate_financial_summary_empty_data(
        self, generator: StateCouncilReportGenerator, mock_connection: AsyncMock
    ) -> None:
        """Test generating financial summary with no data."""
        guild_id = _snowflake()
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        # Mock empty data
        gateway = cast(AsyncMock, generator._gateway)
        gateway.fetch_welfare_disbursements.return_value = []
        gateway.fetch_tax_records.return_value = []
        gateway.fetch_currency_issuances.return_value = []

        summary = await generator.generate_financial_summary(
            mock_connection, guild_id=guild_id, start_date=start_date, end_date=end_date
        )

        assert summary.total_welfare_disbursed == 0
        assert summary.total_tax_collected == 0
        assert summary.total_currency_issued == 0
        assert summary.net_flow == 0

    # --- Department Metrics Tests ---

    @pytest.mark.asyncio
    async def test_generate_department_metrics_internal_affairs(
        self,
        generator: StateCouncilReportGenerator,
        mock_connection: AsyncMock,
        sample_welfare_records: list[WelfareDisbursement],
    ) -> None:
        """Test generating metrics for Internal Affairs department."""
        guild_id = _snowflake()
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        gateway = cast(AsyncMock, generator._gateway)
        gateway.fetch_welfare_disbursements.return_value = sample_welfare_records

        metrics = await generator.generate_department_metrics(
            mock_connection,
            guild_id=guild_id,
            department="內政部",
            start_date=start_date,
            end_date=end_date,
        )

        assert isinstance(metrics, DepartmentMetrics)
        assert metrics.department == "內政部"
        assert metrics.total_operations == 2
        assert metrics.total_amount == 2500
        assert metrics.average_per_operation == 1250.0
        assert metrics.peak_activity_day == "2024-01-20"
        assert metrics.most_common_operation == "福利發放"

    @pytest.mark.asyncio
    async def test_generate_department_metrics_finance(
        self,
        generator: StateCouncilReportGenerator,
        mock_connection: AsyncMock,
        sample_tax_records: list[TaxRecord],
    ) -> None:
        """Test generating metrics for Finance department."""
        guild_id = _snowflake()
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        gateway = cast(AsyncMock, generator._gateway)
        gateway.fetch_tax_records.return_value = sample_tax_records

        metrics = await generator.generate_department_metrics(
            mock_connection,
            guild_id=guild_id,
            department="財政部",
            start_date=start_date,
            end_date=end_date,
        )

        assert isinstance(metrics, DepartmentMetrics)
        assert metrics.department == "財政部"
        assert metrics.total_operations == 2
        assert metrics.total_amount == 4000
        assert metrics.average_per_operation == 2000.0
        assert metrics.peak_activity_day == "2024-01-25"
        assert metrics.most_common_operation == "稅收徵收"

    @pytest.mark.asyncio
    async def test_generate_department_metrics_security(
        self,
        generator: StateCouncilReportGenerator,
        mock_connection: AsyncMock,
        sample_identity_records: list[IdentityRecord],
    ) -> None:
        """Test generating metrics for Security department."""
        guild_id = _snowflake()
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        gateway = cast(AsyncMock, generator._gateway)
        gateway.fetch_identity_records.return_value = sample_identity_records

        metrics = await generator.generate_department_metrics(
            mock_connection,
            guild_id=guild_id,
            department="國土安全部",
            start_date=start_date,
            end_date=end_date,
        )

        assert isinstance(metrics, DepartmentMetrics)
        assert metrics.department == "國土安全部"
        assert metrics.total_operations == 2
        assert metrics.total_amount == 2  # Count of identity actions
        assert metrics.average_per_operation == 1.0
        assert metrics.peak_activity_day == "2024-01-15"
        assert metrics.most_common_operation == "移除公民身分"  # First encountered

    @pytest.mark.asyncio
    async def test_generate_department_metrics_central_bank(
        self,
        generator: StateCouncilReportGenerator,
        mock_connection: AsyncMock,
        sample_currency_records: list[CurrencyIssuance],
    ) -> None:
        """Test generating metrics for Central Bank department."""
        guild_id = _snowflake()
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        gateway = cast(AsyncMock, generator._gateway)
        gateway.fetch_currency_issuances.return_value = sample_currency_records

        metrics = await generator.generate_department_metrics(
            mock_connection,
            guild_id=guild_id,
            department="中央銀行",
            start_date=start_date,
            end_date=end_date,
        )

        assert isinstance(metrics, DepartmentMetrics)
        assert metrics.department == "中央銀行"
        assert metrics.total_operations == 2
        assert metrics.total_amount == 8000
        assert metrics.average_per_operation == 4000.0
        assert metrics.peak_activity_day == "2024-01-15"
        assert metrics.most_common_operation == "貨幣發行"

    @pytest.mark.asyncio
    async def test_generate_department_metrics_unknown_department(
        self, generator: StateCouncilReportGenerator, mock_connection: AsyncMock
    ) -> None:
        """Test generating metrics for unknown department."""
        guild_id = _snowflake()
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        metrics = await generator.generate_department_metrics(
            mock_connection,
            guild_id=guild_id,
            department="不存在的部門",
            start_date=start_date,
            end_date=end_date,
        )

        assert isinstance(metrics, DepartmentMetrics)
        assert metrics.department == "不存在的部門"
        assert metrics.total_operations == 0
        assert metrics.total_amount == 0
        assert metrics.average_per_operation == 0.0
        assert metrics.peak_activity_day == "無數據"
        assert metrics.most_common_operation == "無操作"

    # --- Activity Report Tests ---

    @pytest.mark.asyncio
    async def test_generate_activity_report(
        self,
        generator: StateCouncilReportGenerator,
        mock_connection: AsyncMock,
        sample_welfare_records: list[WelfareDisbursement],
        sample_tax_records: list[TaxRecord],
        sample_identity_records: list[IdentityRecord],
        sample_currency_records: list[CurrencyIssuance],
        sample_transfer_records: list[InterdepartmentTransfer],
    ) -> None:
        """Test generating comprehensive activity report."""
        guild_id = _snowflake()
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        # Mock all gateway methods
        gateway = cast(AsyncMock, generator._gateway)
        gateway.fetch_welfare_disbursements.return_value = sample_welfare_records
        gateway.fetch_tax_records.return_value = sample_tax_records
        gateway.fetch_identity_records.return_value = sample_identity_records
        gateway.fetch_currency_issuances.return_value = sample_currency_records
        gateway.fetch_interdepartment_transfers.return_value = sample_transfer_records

        report = await generator.generate_activity_report(
            mock_connection,
            guild_id=guild_id,
            start_date=start_date,
            end_date=end_date,
        )

        assert isinstance(report, ActivityReport)
        assert "2024-01-01 至 2024-01-31" in report.period
        assert report.total_operations == 8  # 2 + 2 + 2 + 2 (all records)
        assert report.unique_users > 0
        assert len(report.operation_breakdown) > 0
        assert len(report.daily_activity) > 0
        assert len(report.top_performers) > 0

        # Check operation breakdown
        assert "福利發放" in report.operation_breakdown
        assert "稅收徵收" in report.operation_breakdown
        assert "身分管理" in report.operation_breakdown
        assert "貨幣發行" in report.operation_breakdown
        assert "部門轉帳" in report.operation_breakdown

    @pytest.mark.asyncio
    async def test_generate_monthly_summary(
        self,
        generator: StateCouncilReportGenerator,
        mock_connection: AsyncMock,
        sample_welfare_records: list[WelfareDisbursement],
        sample_tax_records: list[TaxRecord],
        sample_currency_records: list[CurrencyIssuance],
    ) -> None:
        """Test generating monthly summary."""
        guild_id = _snowflake()
        year = 2024
        month = 1

        # Mock gateway methods
        gateway = cast(AsyncMock, generator._gateway)
        gateway.fetch_welfare_disbursements.return_value = sample_welfare_records
        gateway.fetch_tax_records.return_value = sample_tax_records
        gateway.fetch_identity_records.return_value = []
        gateway.fetch_currency_issuances.return_value = sample_currency_records
        gateway.fetch_interdepartment_transfers.return_value = []
        gateway.fetch_government_accounts.return_value = [
            AsyncMock(department="內政部", balance=5000),
            AsyncMock(department="財政部", balance=3000),
            AsyncMock(department="國土安全部", balance=2000),
            AsyncMock(department="中央銀行", balance=10000),
        ]

        summary = await generator.generate_monthly_summary(
            mock_connection, guild_id=guild_id, year=year, month=month
        )

        assert summary["period"] == "2024-01"
        assert "financial_summary" in summary
        assert "department_metrics" in summary
        assert "activity_summary" in summary
        assert "account_balances" in summary
        assert "generated_at" in summary

        # Check financial summary
        financial = summary["financial_summary"]
        assert financial["total_welfare_disbursed"] == 2500
        assert financial["total_tax_collected"] == 4000
        assert financial["total_currency_issued"] == 8000
        assert financial["net_flow"] == 9500

        # Check department metrics
        dept_metrics = summary["department_metrics"]
        assert "內政部" in dept_metrics
        assert "財政部" in dept_metrics
        assert "國土安全部" in dept_metrics
        assert "中央銀行" in dept_metrics

        # Check account balances
        balances = summary["account_balances"]
        assert "內政部" in balances
        assert "財政部" in balances
        assert "國土安全部" in balances
        assert "中央銀行" in balances

    # --- Report Formatting Tests ---

    def test_format_report_as_markdown(self, generator: StateCouncilReportGenerator) -> None:
        """Test formatting report data as markdown."""
        report_data = {
            "period": "2024-01",
            "financial_summary": {
                "total_welfare_disbursed": 2500,
                "total_tax_collected": 4000,
                "total_currency_issued": 8000,
                "net_flow": 9500,
            },
            "department_metrics": {
                "內政部": {
                    "total_operations": 2,
                    "total_amount": 2500,
                    "average_per_operation": 1250.0,
                    "peak_activity_day": "2024-01-20",
                    "most_common_operation": "福利發放",
                },
                "財政部": {
                    "total_operations": 2,
                    "total_amount": 4000,
                    "average_per_operation": 2000.0,
                    "peak_activity_day": "2024-01-25",
                    "most_common_operation": "稅收徵收",
                },
            },
            "activity_summary": {
                "total_operations": 8,
                "unique_users": 5,
                "operation_breakdown": {
                    "福利發放": 2,
                    "稅收徵收": 2,
                    "身分管理": 2,
                    "貨幣發行": 2,
                    "部門轉帳": 0,
                },
                "top_performers": [
                    {"user_id": 123, "operations": 3},
                    {"user_id": 456, "operations": 2},
                ],
            },
            "account_balances": {
                "內政部": 5000,
                "財政部": 3000,
                "國土安全部": 2000,
                "中央銀行": 10000,
            },
            "generated_at": "2024-01-31T23:59:59Z",
        }

        markdown = generator.format_report_as_markdown(report_data)

        assert "國務院月報 - 2024-01" in markdown
        assert "財務摘要" in markdown
        assert "福利發放總額：2,500 幣" in markdown
        assert "稅收總額：4,000 幣" in markdown
        assert "貨幣發行總額：8,000 幣" in markdown
        assert "淨流動：+9,500 幣" in markdown
        assert "各部門表現" in markdown
        assert "內政部" in markdown
        assert "財政部" in markdown
        assert "活動統計" in markdown
        assert "總操作數：8" in markdown
        assert "參與用戶數：5" in markdown
        assert "各部門餘額" in markdown
        assert "報表生成時間" in markdown

    def test_format_report_as_markdown_edge_cases(
        self, generator: StateCouncilReportGenerator
    ) -> None:
        """Test formatting report with edge cases."""
        report_data = {
            "period": "2024-01",
            "financial_summary": {
                "total_welfare_disbursed": 0,
                "total_tax_collected": 0,
                "total_currency_issued": 0,
                "net_flow": 0,
            },
            "department_metrics": {
                "國土安全部": {
                    "total_operations": 1,
                    "total_amount": 1,  # Edge case: amount = 1
                    "average_per_operation": 1.0,
                    "peak_activity_day": "2024-01-15",
                    "most_common_operation": "身分管理",
                },
            },
            "activity_summary": {
                "total_operations": 1,
                "unique_users": 1,
                "operation_breakdown": {"身分管理": 1},
                "top_performers": [],
            },
            "account_balances": {
                "內政部": 0,
                "財政部": 0,
                "國土安全部": 0,
                "中央銀行": 0,
            },
            "generated_at": "2024-01-31T23:59:59Z",
        }

        markdown = generator.format_report_as_markdown(report_data)

        # Should handle zero values gracefully
        assert "福利發放總額：0 幣" in markdown
        assert "稅收總額：0 幣" in markdown
        assert "貨幣發行總額：0 幣" in markdown
        assert "淨流動：+0 幣" in markdown
        assert "餘額：0 幣" in markdown

        # Should handle departments with small amounts correctly
        assert "總操作數：1" in markdown
        assert "總金額：1 幣" not in markdown  # Should show "總操作數：1" instead
        assert "平均每次操作：1.00 幣" in markdown

    # --- Helper Method Tests ---

    def test_calculate_metrics_empty_operations(
        self, generator: StateCouncilReportGenerator
    ) -> None:
        """Test calculating metrics with empty operations."""
        metrics = generator._calculate_metrics(
            department="測試部門",
            operations=[],
            total_amount=0,
        )

        assert metrics.department == "測試部門"
        assert metrics.total_operations == 0
        assert metrics.total_amount == 0
        assert metrics.average_per_operation == 0.0
        assert metrics.peak_activity_day == "無數據"
        assert metrics.most_common_operation == "無操作"

    def test_calculate_metrics_single_operation(
        self, generator: StateCouncilReportGenerator
    ) -> None:
        """Test calculating metrics with single operation."""
        operations: list[tuple[str, int, datetime, int | None]] = [
            ("測試操作", 1000, datetime(2024, 1, 15, tzinfo=timezone.utc), 12345)
        ]

        metrics = generator._calculate_metrics(
            department="測試部門",
            operations=operations,
            total_amount=1000,
        )

        assert metrics.department == "測試部門"
        assert metrics.total_operations == 1
        assert metrics.total_amount == 1000
        assert metrics.average_per_operation == 1000.0
        assert metrics.peak_activity_day == "2024-01-15"
        assert metrics.most_common_operation == "測試操作"
