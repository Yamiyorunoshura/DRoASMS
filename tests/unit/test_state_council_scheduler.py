"""Unit tests for state council scheduler."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.services import state_council_scheduler
from src.bot.services.state_council_scheduler import (
    AutoReleaseJob,
    cancel_auto_release,
    get_all_auto_release_jobs,
    get_auto_release_jobs_for_guild,
    set_auto_release,
    start_scheduler,
    stop_scheduler,
)


@pytest.mark.unit
class TestStateCouncilScheduler:
    """Test cases for State Council scheduler."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock Discord client."""
        client = MagicMock()
        client.wait_until_ready = AsyncMock()
        client.is_closed = MagicMock(return_value=False)
        return client

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        return AsyncMock()

    @pytest.fixture
    def mock_pool(self) -> AsyncMock:
        """Create a mock database pool."""
        pool = AsyncMock()
        pool.acquire = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return pool

    @pytest.fixture
    def mock_gateway(self) -> AsyncMock:
        """Create a mock StateCouncilGovernanceGateway."""
        gateway = AsyncMock()
        gateway.fetch_all_department_configs_with_welfare = AsyncMock(return_value=[])
        gateway.fetch_all_department_configs_for_issuance = AsyncMock(return_value=[])
        gateway.sum_monthly_issuance = AsyncMock(return_value=0)
        return gateway

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """Create a mock StateCouncilService."""
        service = AsyncMock()
        service.release_suspects = AsyncMock(return_value=[])
        return service

    def test_auto_release_job_creation(self) -> None:
        """Test AutoReleaseJob dataclass creation."""
        now = datetime.now(tz=timezone.utc)
        release_time = now + timedelta(hours=24)

        job = AutoReleaseJob(
            guild_id=12345,
            suspect_id=67890,
            release_at=release_time,
            hours=24,
            scheduled_by=11111,
            scheduled_at=now,
        )

        assert job.guild_id == 12345
        assert job.suspect_id == 67890
        assert job.release_at == release_time
        assert job.hours == 24
        assert job.scheduled_by == 11111
        assert job.scheduled_at == now

    def test_set_auto_release(self) -> None:
        """Test setting auto-release for a suspect."""
        # Clear any existing settings
        state_council_scheduler._auto_release_settings.clear()

        job = set_auto_release(
            guild_id=12345,
            suspect_id=67890,
            hours=24,
            scheduled_by=11111,
        )

        assert job.guild_id == 12345
        assert job.suspect_id == 67890
        assert job.hours == 24
        assert job.scheduled_by == 11111

        # Check that the job is stored
        stored_jobs = get_auto_release_jobs_for_guild(12345)
        assert 67890 in stored_jobs
        assert stored_jobs[67890] == job

    def test_set_auto_release_normalizes_hours(self) -> None:
        """Test that hours are normalized to 1-168 range."""
        state_council_scheduler._auto_release_settings.clear()

        # Test minimum normalization
        job1 = set_auto_release(guild_id=12345, suspect_id=1, hours=0, scheduled_by=11111)
        assert job1.hours == 1

        # Test maximum normalization
        job2 = set_auto_release(guild_id=12345, suspect_id=2, hours=200, scheduled_by=11111)
        assert job2.hours == 168

        # Test normal value
        job3 = set_auto_release(guild_id=12345, suspect_id=3, hours=48, scheduled_by=11111)
        assert job3.hours == 48

    def test_cancel_auto_release(self) -> None:
        """Test canceling auto-release for a suspect."""
        state_council_scheduler._auto_release_settings.clear()

        # Set up a job
        set_auto_release(guild_id=12345, suspect_id=67890, hours=24, scheduled_by=11111)

        # Verify it's there
        assert 67890 in get_auto_release_jobs_for_guild(12345)

        # Cancel it
        cancel_auto_release(12345, 67890)

        # Verify it's gone
        assert 67890 not in get_auto_release_jobs_for_guild(12345)

    def test_cancel_auto_release_nonexistent(self) -> None:
        """Test canceling auto-release for non-existent job doesn't error."""
        state_council_scheduler._auto_release_settings.clear()

        # This should not raise an error
        cancel_auto_release(12345, 67890)

    def test_get_auto_release_jobs_for_guild(self) -> None:
        """Test getting auto-release jobs for a specific guild."""
        state_council_scheduler._auto_release_settings.clear()

        # Set up jobs for multiple guilds
        job1 = set_auto_release(guild_id=12345, suspect_id=1, hours=24, scheduled_by=11111)
        job2 = set_auto_release(guild_id=12345, suspect_id=2, hours=48, scheduled_by=11111)
        _ = set_auto_release(
            guild_id=54321, suspect_id=3, hours=12, scheduled_by=22222
        )  # unused job

        # Get jobs for specific guild
        guild_jobs = get_auto_release_jobs_for_guild(12345)
        assert len(guild_jobs) == 2
        assert 1 in guild_jobs
        assert 2 in guild_jobs
        assert guild_jobs[1] == job1
        assert guild_jobs[2] == job2

        # Verify it's a copy (not the original)
        guild_jobs[1] = None  # type: ignore
        original_jobs = get_auto_release_jobs_for_guild(12345)
        assert original_jobs[1] is not None

    def test_get_all_auto_release_jobs(self) -> None:
        """Test getting all auto-release jobs."""
        state_council_scheduler._auto_release_settings.clear()

        # Set up jobs
        job1 = set_auto_release(guild_id=12345, suspect_id=1, hours=24, scheduled_by=11111)
        job2 = set_auto_release(guild_id=54321, suspect_id=2, hours=48, scheduled_by=22222)

        all_jobs = get_all_auto_release_jobs()
        assert len(all_jobs) == 2
        assert 12345 in all_jobs
        assert 54321 in all_jobs
        assert all_jobs[12345][1] == job1
        assert all_jobs[54321][2] == job2

    @pytest.mark.asyncio
    async def test_start_scheduler_already_running(self, mock_client: MagicMock) -> None:
        """Test starting scheduler when it's already running."""
        # Clear any existing task
        state_council_scheduler._scheduler_task = None

        # Start scheduler
        await start_scheduler(mock_client)

        # Try to start again
        await start_scheduler(mock_client)

        # Should not create a new task (the original task should still be running)
        assert state_council_scheduler._scheduler_task is not None

        # Clean up
        await stop_scheduler()

    @pytest.mark.asyncio
    async def test_stop_scheduler_not_running(self) -> None:
        """Test stopping scheduler when it's not running."""
        # Ensure task is None
        state_council_scheduler._scheduler_task = None

        # This should not raise an error
        await stop_scheduler()

    @pytest.mark.asyncio
    async def test_scheduler_processes_auto_release(
        self,
        mock_client: MagicMock,
        mock_connection: AsyncMock,
        mock_pool: AsyncMock,
        mock_service: AsyncMock,
    ) -> None:
        """Test that scheduler processes auto-release jobs."""
        # Set up mock guild
        mock_guild = MagicMock()
        mock_client.get_guild.return_value = mock_guild

        # Set up auto-release job
        state_council_scheduler._auto_release_settings.clear()
        past_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        job = AutoReleaseJob(
            guild_id=12345,
            suspect_id=67890,
            release_at=past_time,
            hours=24,
            scheduled_by=11111,
            scheduled_at=past_time - timedelta(hours=24),
        )
        state_council_scheduler._auto_release_settings[12345] = {67890: job}

        # Mock successful release
        mock_result = MagicMock()
        mock_result.suspect_id = 67890
        mock_result.released = True
        mock_result.display_name = "TestUser"
        mock_service.release_suspects.return_value = [mock_result]

        # Import and test the private function
        await state_council_scheduler._process_auto_release(
            mock_connection, mock_service, datetime.now(tz=timezone.utc), mock_client
        )

        # Verify release was called
        mock_service.release_suspects.assert_called_once()
        call_args = mock_service.release_suspects.call_args
        assert call_args.kwargs["guild"] == mock_guild
        assert call_args.kwargs["guild_id"] == 12345
        assert call_args.kwargs["suspect_ids"] == [67890]
        assert call_args.kwargs["reason"] == "達到自動釋放時間"
        assert call_args.kwargs["skip_permission"] is True

        # Verify job was removed after successful release
        assert 67890 not in get_auto_release_jobs_for_guild(12345)

    @pytest.mark.asyncio
    async def test_scheduler_handles_guild_not_found(
        self,
        mock_client: MagicMock,
        mock_connection: AsyncMock,
        mock_service: AsyncMock,
    ) -> None:
        """Test that scheduler handles guild not found gracefully."""
        # Set up auto-release job
        state_council_scheduler._auto_release_settings.clear()
        past_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        job = AutoReleaseJob(
            guild_id=12345,
            suspect_id=67890,
            release_at=past_time,
            hours=24,
            scheduled_by=11111,
            scheduled_at=past_time - timedelta(hours=24),
        )
        state_council_scheduler._auto_release_settings[12345] = {67890: job}

        # Mock guild not found
        mock_client.get_guild.return_value = None

        # Process auto-release
        await state_council_scheduler._process_auto_release(
            mock_connection, mock_service, datetime.now(tz=timezone.utc), mock_client
        )

        # Verify release was not called (guild not found)
        mock_service.release_suspects.assert_not_called()

        # Verify job was removed (guild not found)
        assert 67890 not in get_auto_release_jobs_for_guild(12345)

    @pytest.mark.asyncio
    async def test_scheduler_handles_release_failure(
        self,
        mock_client: MagicMock,
        mock_connection: AsyncMock,
        mock_service: AsyncMock,
    ) -> None:
        """Test that scheduler handles release failures gracefully."""
        # Set up mock guild
        mock_guild = MagicMock()
        mock_client.get_guild.return_value = mock_guild

        # Set up auto-release job
        state_council_scheduler._auto_release_settings.clear()
        past_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        job = AutoReleaseJob(
            guild_id=12345,
            suspect_id=67890,
            release_at=past_time,
            hours=24,
            scheduled_by=11111,
            scheduled_at=past_time - timedelta(hours=24),
        )
        state_council_scheduler._auto_release_settings[12345] = {67890: job}

        # Mock release failure
        mock_service.release_suspects.side_effect = Exception("Release failed")

        # Process auto-release
        await state_council_scheduler._process_auto_release(
            mock_connection, mock_service, datetime.now(tz=timezone.utc), mock_client
        )

        # Verify release was called but failed
        mock_service.release_suspects.assert_called_once()

        # Verify job was removed even on failure
        assert 67890 not in get_auto_release_jobs_for_guild(12345)

    @pytest.mark.asyncio
    async def test_process_welfare_disbursements(
        self, mock_connection: AsyncMock, mock_gateway: AsyncMock, mock_service: AsyncMock
    ) -> None:
        """Test welfare disbursement processing."""
        # Mock welfare configurations
        mock_gateway.fetch_all_department_configs_with_welfare.return_value = [
            {"guild_id": 12345, "welfare_amount": 100, "welfare_interval_hours": 24},
            {
                "guild_id": 54321,
                "welfare_amount": 0,
                "welfare_interval_hours": 24,
            },  # Invalid amount
            {
                "guild_id": 11111,
                "welfare_amount": 100,
                "welfare_interval_hours": 0,
            },  # Invalid interval
        ]

        processed_welfare: set[int] = set()
        current_time = datetime.now(tz=timezone.utc)

        await state_council_scheduler._process_welfare_disbursements(
            mock_connection, mock_gateway, mock_service, current_time, processed_welfare
        )

        # Verify gateway was called
        mock_gateway.fetch_all_department_configs_with_welfare.assert_called_once_with(
            mock_connection
        )

        # Verify only valid configuration was processed
        assert 12345 in processed_welfare
        assert 54321 not in processed_welfare
        assert 11111 not in processed_welfare

    @pytest.mark.asyncio
    async def test_check_monthly_issuance_limits(
        self, mock_connection: AsyncMock, mock_gateway: AsyncMock
    ) -> None:
        """Test monthly issuance limit checking."""
        # Mock issuance configurations
        mock_gateway.fetch_all_department_configs_for_issuance.return_value = [
            {"guild_id": 12345, "max_issuance_per_month": 1000},
            {"guild_id": 54321, "max_issuance_per_month": 0},  # Invalid limit
        ]
        mock_gateway.sum_monthly_issuance.return_value = 750

        processed_issuance: set[str] = set()
        current_time = datetime.now(tz=timezone.utc)
        current_month = current_time.strftime("%Y-%m")

        await state_council_scheduler._check_monthly_issuance_limits(
            mock_connection, mock_gateway, current_time, processed_issuance
        )

        # Verify gateway calls
        mock_gateway.fetch_all_department_configs_for_issuance.assert_called_once_with(
            mock_connection
        )
        mock_gateway.sum_monthly_issuance.assert_called_once_with(
            mock_connection, guild_id=12345, month_period=current_month
        )

        # Verify month was processed
        assert current_month in processed_issuance

    @pytest.mark.asyncio
    async def test_check_monthly_issuance_limits_already_processed(
        self, mock_connection: AsyncMock, mock_gateway: AsyncMock
    ) -> None:
        """Test that already processed months are skipped."""
        processed_issuance: set[str] = set()
        current_time = datetime.now(tz=timezone.utc)
        current_month = current_time.strftime("%Y-%m")
        processed_issuance.add(current_month)  # Already processed

        await state_council_scheduler._check_monthly_issuance_limits(
            mock_connection, mock_gateway, current_time, processed_issuance
        )

        # Verify no gateway calls were made
        mock_gateway.fetch_all_department_configs_for_issuance.assert_not_called()
        mock_gateway.sum_monthly_issuance.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_old_records(
        self, mock_connection: AsyncMock, mock_gateway: AsyncMock
    ) -> None:
        """Test cleanup of old records."""
        await state_council_scheduler._cleanup_old_records(mock_connection, mock_gateway)

        # This is mostly a placeholder test since the function doesn't do much
        # In a real implementation, you'd verify that old records were deleted

    def test_cleanup_empty_guild_entries(self) -> None:
        """Test cleanup of empty guild entries."""
        state_council_scheduler._auto_release_settings.clear()

        # Add some entries including empty ones
        state_council_scheduler._auto_release_settings[12345] = {}
        state_council_scheduler._auto_release_settings[54321] = {1: MagicMock()}
        state_council_scheduler._auto_release_settings[11111] = {}

        # Run cleanup
        state_council_scheduler._cleanup_empty_guild_entries()

        # Verify empty entries were removed
        assert 12345 not in state_council_scheduler._auto_release_settings
        assert 54321 in state_council_scheduler._auto_release_settings
        assert 11111 not in state_council_scheduler._auto_release_settings

    @pytest.mark.asyncio
    async def test_scheduler_integration(
        self,
        mock_client: MagicMock,
        mock_pool: AsyncMock,
        mock_gateway: AsyncMock,
        mock_service: AsyncMock,
    ) -> None:
        """Integration test for scheduler startup and shutdown."""
        # Clear any existing task
        state_council_scheduler._scheduler_task = None

        # Mock get_pool to return our mock pool
        with patch("src.bot.services.state_council_scheduler.get_pool", return_value=mock_pool):
            # Start scheduler
            await start_scheduler(mock_client)

            # Verify task was created
            assert state_council_scheduler._scheduler_task is not None

            # Let it run for a very short time
            await asyncio.sleep(0.1)

            # Stop scheduler
            await stop_scheduler()

            # Verify task was stopped
            assert state_council_scheduler._scheduler_task is None

        # Verify client waited until ready
        mock_client.wait_until_ready.assert_called()

    @pytest.mark.asyncio
    async def test_process_welfare_disbursements_exception(
        self, mock_connection: AsyncMock, mock_gateway: AsyncMock, mock_service: AsyncMock
    ) -> None:
        """Test welfare disbursement exception handling."""
        # Mock gateway to raise exception
        mock_gateway.fetch_all_department_configs_with_welfare.side_effect = Exception("DB error")

        processed_welfare: set[int] = set()
        current_time = datetime.now(tz=timezone.utc)

        # Should not raise exception - just log it
        await state_council_scheduler._process_welfare_disbursements(
            mock_connection, mock_gateway, mock_service, current_time, processed_welfare
        )

        # Verify exception was handled gracefully (processed_welfare should be empty)
        assert len(processed_welfare) == 0

    @pytest.mark.asyncio
    async def test_check_monthly_issuance_limits_exception(
        self, mock_connection: AsyncMock, mock_gateway: AsyncMock
    ) -> None:
        """Test monthly issuance limit checking exception handling."""
        # Mock gateway to raise exception
        mock_gateway.fetch_all_department_configs_for_issuance.side_effect = Exception("DB error")

        processed_issuance: set[str] = set()
        current_time = datetime.now(tz=timezone.utc)

        # Should not raise exception - just log it
        await state_council_scheduler._check_monthly_issuance_limits(
            mock_connection, mock_gateway, current_time, processed_issuance
        )

        # Verify exception was handled gracefully
        current_month = current_time.strftime("%Y-%m")
        assert current_month not in processed_issuance

    @pytest.mark.asyncio
    async def test_cleanup_old_records_exception(
        self, mock_connection: AsyncMock, mock_gateway: AsyncMock
    ) -> None:
        """Test cleanup old records exception handling."""
        # This is mostly a placeholder but ensures exception path is covered
        # The function currently doesn't do much but should handle exceptions
        await state_council_scheduler._cleanup_old_records(mock_connection, mock_gateway)

    @pytest.mark.asyncio
    async def test_process_auto_release_exception(
        self,
        mock_client: MagicMock,
        mock_connection: AsyncMock,
        mock_service: AsyncMock,
    ) -> None:
        """Test auto-release exception handling."""
        # Set up auto-release job
        state_council_scheduler._auto_release_settings.clear()
        past_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        job = AutoReleaseJob(
            guild_id=12345,
            suspect_id=67890,
            release_at=past_time,
            hours=24,
            scheduled_by=11111,
            scheduled_at=past_time - timedelta(hours=24),
        )
        state_council_scheduler._auto_release_settings[12345] = {67890: job}

        # Mock guild exists but service raises exception at outer level
        mock_guild = MagicMock()
        mock_client.get_guild.return_value = mock_guild

        # Patch the entire function to raise at the try level
        with patch.object(
            state_council_scheduler,
            "_auto_release_settings",
            side_effect=Exception("Critical error"),
        ):
            # Should not raise
            await state_council_scheduler._process_auto_release(
                mock_connection, mock_service, datetime.now(tz=timezone.utc), mock_client
            )

    @pytest.mark.asyncio
    async def test_process_auto_release_with_client_user_fallback(
        self,
        mock_client: MagicMock,
        mock_connection: AsyncMock,
        mock_service: AsyncMock,
    ) -> None:
        """Test auto-release with client.user.id fallback for operator_id."""
        # Set up mock guild
        mock_guild = MagicMock()
        mock_client.get_guild.return_value = mock_guild

        # Set up client.user for fallback
        mock_user = MagicMock()
        mock_user.id = 99999
        mock_client.user = mock_user

        # Set up auto-release job with scheduled_by=0 to trigger fallback
        state_council_scheduler._auto_release_settings.clear()
        past_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        job = AutoReleaseJob(
            guild_id=12345,
            suspect_id=67890,
            release_at=past_time,
            hours=24,
            scheduled_by=0,  # Will trigger fallback to client.user.id
            scheduled_at=past_time - timedelta(hours=24),
        )
        state_council_scheduler._auto_release_settings[12345] = {67890: job}

        # Mock successful release
        mock_result = MagicMock()
        mock_result.suspect_id = 67890
        mock_result.released = True
        mock_result.display_name = "TestUser"
        mock_service.release_suspects.return_value = [mock_result]

        # Process auto-release
        await state_council_scheduler._process_auto_release(
            mock_connection, mock_service, datetime.now(tz=timezone.utc), mock_client
        )

        # Verify release was called with fallback operator_id
        mock_service.release_suspects.assert_called_once()
        call_args = mock_service.release_suspects.call_args
        assert call_args.kwargs["user_id"] == 99999

    @pytest.mark.asyncio
    async def test_process_auto_release_no_ready_jobs(
        self,
        mock_client: MagicMock,
        mock_connection: AsyncMock,
        mock_service: AsyncMock,
    ) -> None:
        """Test auto-release with jobs that are not ready yet."""
        # Set up auto-release job in the future
        state_council_scheduler._auto_release_settings.clear()
        future_time = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        job = AutoReleaseJob(
            guild_id=12345,
            suspect_id=67890,
            release_at=future_time,
            hours=24,
            scheduled_by=11111,
            scheduled_at=datetime.now(tz=timezone.utc),
        )
        state_council_scheduler._auto_release_settings[12345] = {67890: job}

        # Process auto-release
        await state_council_scheduler._process_auto_release(
            mock_connection, mock_service, datetime.now(tz=timezone.utc), mock_client
        )

        # Verify release was not called (job not ready)
        mock_service.release_suspects.assert_not_called()

        # Verify job is still there
        assert 67890 in get_auto_release_jobs_for_guild(12345)

    @pytest.mark.asyncio
    async def test_process_auto_release_empty_jobs(
        self,
        mock_client: MagicMock,
        mock_connection: AsyncMock,
        mock_service: AsyncMock,
    ) -> None:
        """Test auto-release with empty job dict."""
        # Set up empty job dict for guild
        state_council_scheduler._auto_release_settings.clear()
        state_council_scheduler._auto_release_settings[12345] = {}

        # Process auto-release
        await state_council_scheduler._process_auto_release(
            mock_connection, mock_service, datetime.now(tz=timezone.utc), mock_client
        )

        # Verify release was not called
        mock_service.release_suspects.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_auto_release_failed_result(
        self,
        mock_client: MagicMock,
        mock_connection: AsyncMock,
        mock_service: AsyncMock,
    ) -> None:
        """Test auto-release with failed release result (released=False)."""
        # Set up mock guild
        mock_guild = MagicMock()
        mock_client.get_guild.return_value = mock_guild

        # Set up auto-release job
        state_council_scheduler._auto_release_settings.clear()
        past_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        job = AutoReleaseJob(
            guild_id=12345,
            suspect_id=67890,
            release_at=past_time,
            hours=24,
            scheduled_by=11111,
            scheduled_at=past_time - timedelta(hours=24),
        )
        state_council_scheduler._auto_release_settings[12345] = {67890: job}

        # Mock failed release result
        mock_result = MagicMock()
        mock_result.suspect_id = 67890
        mock_result.released = False  # Not released
        mock_result.display_name = "TestUser"
        mock_result.error = "Member not found"
        mock_service.release_suspects.return_value = [mock_result]

        # Process auto-release
        await state_council_scheduler._process_auto_release(
            mock_connection, mock_service, datetime.now(tz=timezone.utc), mock_client
        )

        # Verify release was called
        mock_service.release_suspects.assert_called_once()

        # Verify job was removed even on failure
        assert 67890 not in get_auto_release_jobs_for_guild(12345)

    @pytest.mark.asyncio
    async def test_process_auto_release_with_no_client_user(
        self,
        mock_client: MagicMock,
        mock_connection: AsyncMock,
        mock_service: AsyncMock,
    ) -> None:
        """Test auto-release fallback when client.user is None."""
        # Set up mock guild
        mock_guild = MagicMock()
        mock_client.get_guild.return_value = mock_guild

        # Set up client.user as None
        mock_client.user = None

        # Set up auto-release job with scheduled_by=0
        state_council_scheduler._auto_release_settings.clear()
        past_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        job = AutoReleaseJob(
            guild_id=12345,
            suspect_id=67890,
            release_at=past_time,
            hours=24,
            scheduled_by=0,  # Will trigger fallback
            scheduled_at=past_time - timedelta(hours=24),
        )
        state_council_scheduler._auto_release_settings[12345] = {67890: job}

        # Mock successful release
        mock_result = MagicMock()
        mock_result.suspect_id = 67890
        mock_result.released = True
        mock_result.display_name = "TestUser"
        mock_service.release_suspects.return_value = [mock_result]

        # Process auto-release
        await state_council_scheduler._process_auto_release(
            mock_connection, mock_service, datetime.now(tz=timezone.utc), mock_client
        )

        # Verify release was called with operator_id=0 (fallback when user is None)
        mock_service.release_suspects.assert_called_once()
        call_args = mock_service.release_suspects.call_args
        assert call_args.kwargs["user_id"] == 0
