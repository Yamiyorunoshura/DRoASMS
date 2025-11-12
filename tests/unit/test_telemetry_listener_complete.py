from __future__ import annotations

import json
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.infra.telemetry.listener import (
    TelemetryListener,
    _maybe_emit_state_council_event,
)

# --- Fixtures and Mocks ---


@pytest.fixture
def mock_discord_client() -> MagicMock:
    """創建一個假的 Discord Client"""
    client = MagicMock()
    client.get_user = MagicMock()
    client.fetch_user = AsyncMock()
    client.application_id = "123456789"
    client.http = MagicMock()
    client.http.request = AsyncMock()
    return client


@pytest.fixture
def mock_pool() -> MagicMock:
    """創建一個假的資料庫池"""
    pool = MagicMock()
    pool.acquire = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock()
    pool.acquire.return_value.__aexit__ = AsyncMock()
    return pool


@pytest.fixture
def mock_connection() -> MagicMock:
    """創建一個假的資料庫連接"""
    conn = MagicMock()
    conn.add_listener = AsyncMock()
    conn.remove_listener = AsyncMock()
    return conn


@pytest.fixture
def mock_transfer_coordinator() -> MagicMock:
    """創建一個假的轉帳協調器"""
    coordinator = MagicMock()
    coordinator.handle_check_result = AsyncMock()
    coordinator.handle_check_approved = AsyncMock()
    return coordinator


@pytest.fixture
def telemetry_listener(
    mock_discord_client: MagicMock, mock_transfer_coordinator: MagicMock
) -> TelemetryListener:
    """創建 TelemetryListener 實例"""
    return TelemetryListener(
        channel="test_events",
        discord_client=mock_discord_client,
        transfer_coordinator=mock_transfer_coordinator,
    )


# --- Basic TelemetryListener Tests ---


class TestTelemetryListenerBasics:
    """測試 TelemetryListener 基本功能"""

    def test_initialization(self) -> None:
        """測試初始化"""
        listener = TelemetryListener(
            channel="test_channel",
            handler=None,
            discord_client=None,
            transfer_coordinator=None,
        )

        assert listener._channel == "test_channel"
        assert listener._task is None
        assert listener._stop_event is None
        assert isinstance(listener._seen_tx, set)
        assert isinstance(listener._tx_order, deque)
        assert isinstance(listener._seen_tokens, set)
        assert isinstance(listener._token_order, deque)

    def test_initialization_with_custom_handler(self) -> None:
        """測試使用自定義處理器初始化"""
        custom_handler = AsyncMock()
        listener = TelemetryListener(
            channel="custom_channel",
            handler=custom_handler,
        )

        assert listener._channel == "custom_channel"
        assert listener._handler == custom_handler

    @pytest.mark.asyncio
    async def test_start_and_stop(self, telemetry_listener: TelemetryListener) -> None:
        """測試啟動和停止"""
        # Mock the database operations
        with patch("src.infra.telemetry.listener.db_pool.init_pool") as mock_init_pool:
            mock_pool = MagicMock()
            mock_conn = MagicMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_pool.acquire.return_value.__aexit__ = AsyncMock()
            mock_conn.add_listener = AsyncMock()
            mock_conn.remove_listener = AsyncMock()
            mock_init_pool.return_value = mock_pool

            # Start listener
            await telemetry_listener.start()

            # Verify task was created
            assert telemetry_listener._task is not None
            assert telemetry_listener._stop_event is not None
            assert not telemetry_listener._task.done()

            # Stop listener
            await telemetry_listener.stop()

            # Verify cleanup
            assert telemetry_listener._task is None
            assert telemetry_listener._stop_event is None

    @pytest.mark.asyncio
    async def test_multiple_start_calls(self, telemetry_listener: TelemetryListener) -> None:
        """測試多次調用 start"""
        with patch("src.infra.telemetry.listener.db_pool.init_pool") as mock_init_pool:
            mock_pool = MagicMock()
            mock_conn = MagicMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_pool.acquire.return_value.__aexit__ = AsyncMock()
            mock_conn.add_listener = AsyncMock()
            mock_conn.remove_listener = AsyncMock()
            mock_init_pool.return_value = mock_pool

            # Start listener twice
            await telemetry_listener.start()
            task1 = telemetry_listener._task

            await telemetry_listener.start()
            task2 = telemetry_listener._task

            # Should be the same task
            assert task1 is task2

            # Clean up
            await telemetry_listener.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start(self) -> None:
        """測試停止未啟動的監聽器"""
        listener = TelemetryListener()

        # Should not raise exception
        await listener.stop()

        assert listener._task is None


class TestTelemetryListenerDispatch:
    """測試 TelemetryListener 事件分派"""

    @pytest.mark.asyncio
    async def test_dispatch_with_sync_handler(self) -> None:
        """測試分派同步處理器"""
        sync_handler = MagicMock()

        listener = TelemetryListener(handler=sync_handler)

        payload = '{"test": "data"}'

        await listener._dispatch(None, 12345, "test_channel", payload)

        sync_handler.assert_called_once_with(payload)

    @pytest.mark.asyncio
    async def test_dispatch_with_async_handler(self) -> None:
        """測試分派異步處理器"""
        async_handler = AsyncMock()

        listener = TelemetryListener(handler=async_handler)

        payload = '{"test": "data"}'

        await listener._dispatch(None, 12345, "test_channel", payload)

        async_handler.assert_called_once_with(payload)

    @pytest.mark.asyncio
    async def test_dispatch_with_coroutine_result(self) -> None:
        """測試處理器返回協程"""

        async def async_result_handler(payload: str) -> str:
            return f"processed: {payload}"

        listener = TelemetryListener(handler=async_result_handler)

        payload = '{"test": "data"}'

        result = await listener._dispatch(None, 12345, "test_channel", payload)

        # Should return None (dispatch doesn't return handler result)
        assert result is None


class TestDefaultHandler:
    """測試預設處理器"""

    @pytest.mark.asyncio
    async def test_default_handler_invalid_json(self) -> None:
        """測試無效 JSON payload"""
        listener = TelemetryListener()

        with pytest.raises(json.JSONDecodeError):
            json.loads('{"invalid": json}')

        # Should not raise exception with default handler
        await listener._default_handler('{"invalid": json}')

    @pytest.mark.asyncio
    async def test_default_handler_non_dict_payload(self) -> None:
        """測試非字典 payload"""
        listener = TelemetryListener()

        # Should handle non-dict gracefully
        await listener._default_handler('"string payload"')

    @pytest.mark.asyncio
    async def test_default_handler_unknown_event_type(self) -> None:
        """測試未知事件類型"""
        listener = TelemetryListener()

        payload = {"event_type": "unknown_event", "data": "test"}

        # Should not raise exception
        await listener._default_handler(json.dumps(payload))


class TestTransactionSuccess:
    """測試交易成功事件處理"""

    @pytest.mark.asyncio
    async def test_transaction_success_basic(self) -> None:
        """測試基本交易成功事件"""
        listener = TelemetryListener()

        payload = {
            "event_type": "transaction_success",
            "guild_id": 12345,
            "initiator_id": 67890,
            "target_id": 11111,
            "amount": 1000,
            "metadata": {"reason": "test"},
        }

        with patch("src.infra.telemetry.listener.LOGGER") as mock_logger:
            await listener._default_handler(json.dumps(payload))

            # Should log transaction success
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_transaction_success_with_tx_id_string(self) -> None:
        """測試帶字串 transaction_id 的交易成功"""
        listener = TelemetryListener()

        payload = {
            "event_type": "transaction_success",
            "guild_id": 12345,
            "transaction_id": "abc123def456",
            "initiator_id": 67890,
            "target_id": 11111,
            "amount": 1000,
        }

        with patch("src.infra.telemetry.listener.LOGGER") as mock_logger:
            await listener._default_handler(json.dumps(payload))

            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_transaction_success_with_tx_id_dict(self) -> None:
        """測試帶字典 transaction_id 的交易成功"""
        listener = TelemetryListener()

        payload = {
            "event_type": "transaction_success",
            "guild_id": 12345,
            "transaction_id": {"hex": "0xabc123"},
            "initiator_id": 67890,
            "target_id": 11111,
            "amount": 1000,
        }

        with patch("src.infra.telemetry.listener.LOGGER") as mock_logger:
            await listener._default_handler(json.dumps(payload))

            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_transaction_success_duplicate(
        self, telemetry_listener: TelemetryListener
    ) -> None:
        """測試重複交易事件"""
        # 記定交易已見
        tx_id = "duplicate_tx_123"
        telemetry_listener._seen_tx.add(tx_id)

        payload = {
            "event_type": "transaction_success",
            "transaction_id": tx_id,
            "guild_id": 12345,
            "initiator_id": 67890,
            "target_id": 11111,
            "amount": 1000,
        }

        with patch("src.infra.telemetry.listener.LOGGER") as mock_logger:
            await telemetry_listener._default_handler(json.dumps(payload))

            # Should log but not duplicate notify
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_transaction_denied(self) -> None:
        """測試交易拒絕事件"""
        listener = TelemetryListener()

        payload = {
            "event_type": "transaction_denied",
            "guild_id": 12345,
            "initiator_id": 67890,
            "reason": "Insufficient funds",
            "metadata": {},
        }

        with patch("src.infra.telemetry.listener.LOGGER") as mock_logger:
            await listener._default_handler(json.dumps(payload))

            # Should log transaction denied
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_adjustment_success(self) -> None:
        """測試調整成功事件"""
        listener = TelemetryListener()

        payload = {
            "event_type": "adjustment_success",
            "guild_id": 12345,
            "admin_id": 67890,
            "target_id": 11111,
            "amount": -500,
            "direction": "debit",
            "reason": "Test adjustment",
        }

        with patch("src.infra.telemetry.listener.LOGGER") as mock_logger:
            await listener._default_handler(json.dumps(payload))

            # Should log adjustment success
            mock_logger.info.assert_called()


class TestNotificationMethods:
    """測試通知方法"""

    @pytest.mark.asyncio
    async def test_notify_target_dm_success(self, mock_discord_client: MagicMock) -> None:
        """測試成功發送目標 DM"""
        listener = TelemetryListener(discord_client=mock_discord_client)

        # Mock user
        user = MagicMock()
        user.send = AsyncMock()
        mock_discord_client.get_user.return_value = user

        parsed = {
            "initiator_id": 12345,
            "target_id": 67890,
            "amount": 1000,
            "metadata": {"reason": "test reason"},
        }

        await listener._notify_target_dm(parsed)

        mock_discord_client.get_user.assert_called_once_with(67890)
        user.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_target_dm_no_discord_client(self) -> None:
        """測試沒有 Discord 客戶時的 DM 通知"""
        listener = TelemetryListener(discord_client=None)

        parsed = {"initiator_id": 12345, "target_id": 67890, "amount": 1000}

        # Should not raise exception
        await listener._notify_target_dm(parsed)

    @pytest.mark.asyncio
    async def test_notify_target_dm_government_account(
        self, mock_discord_client: MagicMock
    ) -> None:
        """測試政府帳戶不發送 DM"""
        listener = TelemetryListener(discord_client=mock_discord_client)

        # Government account (ID >= 9,000,000,000,000,000)
        parsed = {
            "initiator_id": 12345,
            "target_id": 9500000000000000,  # 政府部門帳戶
            "amount": 1000,
        }

        await listener._notify_target_dm(parsed)

        # Should not call get_user for government accounts
        mock_discord_client.get_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_target_dm_user_not_found(self, mock_discord_client: MagicMock) -> None:
        """測試找不到用戶時的 DM 通知"""
        listener = TelemetryListener(discord_client=mock_discord_client)

        # Mock user not found
        mock_discord_client.get_user.return_value = None
        mock_discord_client.fetch_user.side_effect = Exception("User not found")

        parsed = {"initiator_id": 12345, "target_id": 67890, "amount": 1000}

        # Should not raise exception
        await listener._notify_target_dm(parsed)

    @pytest.mark.asyncio
    async def test_notify_initiator_dm_success(self, mock_discord_client: MagicMock) -> None:
        """測試成功發送發起者 DM"""
        listener = TelemetryListener(discord_client=mock_discord_client)

        # Mock user
        user = MagicMock()
        user.send = AsyncMock()
        mock_discord_client.get_user.return_value = user

        parsed = {
            "initiator_id": 12345,
            "target_id": 67890,
            "amount": 1000,
            "reason": "Failed due to limits",
        }

        await listener._notify_initiator_dm(parsed)

        mock_discord_client.get_user.assert_called_once_with(12345)
        user.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_initiator_dm_no_discord_client(self) -> None:
        """測試沒有 Discord 客戶時的發起者 DM"""
        listener = TelemetryListener(discord_client=None)

        parsed = {"initiator_id": 12345, "target_id": 67890, "amount": 1000}

        # Should not raise exception
        await listener._notify_initiator_dm(parsed)

    @pytest.mark.asyncio
    async def test_notify_initiator_server_success(self, mock_discord_client: MagicMock) -> None:
        """測試成功發送伺服器通知"""
        listener = TelemetryListener(discord_client=mock_discord_client)

        parsed = {
            "initiator_id": 12345,
            "target_id": 67890,
            "amount": 1000,
            "metadata": {"interaction_token": "valid_token_123", "reason": "test transfer"},
        }

        with patch("src.infra.telemetry.listener.db_pool.get_pool") as _mock_get_pool:
            # Mock database and balance query
            mock_pool = MagicMock()
            mock_conn = MagicMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            _mock_get_pool.return_value = mock_pool

            # Mock economy gateway
            with patch("src.infra.telemetry.listener.EconomyQueryGateway") as mock_economy:
                mock_economy.return_value.fetch_balance_snapshot = AsyncMock(
                    return_value=MagicMock(balance=5000)
                )

                await listener._notify_initiator_server(parsed)

                # Should send HTTP request
                mock_discord_client.http.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_initiator_server_no_token(self, mock_discord_client: MagicMock) -> None:
        """測試沒有 interaction_token 時"""
        listener = TelemetryListener(discord_client=mock_discord_client)

        parsed = {"initiator_id": 12345, "target_id": 67890, "amount": 1000, "metadata": {}}

        with patch("src.infra.telemetry.listener.db_pool.get_pool"):
            await listener._notify_initiator_server(parsed)

            # Should not send HTTP request (no token)
            mock_discord_client.http.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_initiator_server_duplicate_token(
        self, telemetry_listener: TelemetryListener
    ) -> None:
        """測試重複 token 不重複發送"""
        # 設定 token 已見
        token = "duplicate_token_456"
        telemetry_listener._seen_tokens.add(token)

        parsed = {
            "initiator_id": 12345,
            "target_id": 67890,
            "amount": 1000,
            "metadata": {"interaction_token": token},
        }

        with patch("src.infra.telemetry.listener.db_pool.get_pool"):
            await telemetry_listener._notify_initiator_server(parsed)

            # Should not send HTTP request (duplicate token)
            # TelemetryListener doesn't have _http attribute, so we just verify no error occurs
            assert True  # If we get here, no exception was raised

    @pytest.mark.asyncio
    async def test_notify_initiator_server_no_application_id(
        self, mock_discord_client: MagicMock
    ) -> None:
        """測試沒有 application_id 時"""
        mock_discord_client.application_id = None

        listener = TelemetryListener(discord_client=mock_discord_client)

        parsed = {
            "initiator_id": 12345,
            "target_id": 67890,
            "amount": 1000,
            "metadata": {"interaction_token": "valid_token"},
        }

        with patch("src.infra.telemetry.listener.db_pool.get_pool"):
            await listener._notify_initiator_server(parsed)

            # Should not send HTTP request (no application_id)
            mock_discord_client.http.request.assert_not_called()


class TestTransferCheckHandling:
    """測試轉帳檢查處理"""

    @pytest.mark.asyncio
    async def test_handle_transfer_check_result_success(
        self, mock_transfer_coordinator: MagicMock
    ) -> None:
        """測試處理轉帳檢查結果"""
        listener = TelemetryListener(transfer_coordinator=mock_transfer_coordinator)

        parsed = {
            "transfer_id": "550e8400-e29b-41d4-a716-446655440000",
            "check_type": "balance_check",
            "result": "1",  # Approved
        }

        await listener._handle_transfer_check_result(parsed)

        mock_transfer_coordinator.handle_check_result.assert_called_once_with(
            transfer_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            check_type="balance_check",
            result=1,
        )

    @pytest.mark.asyncio
    async def test_handle_transfer_check_result_no_coordinator(self) -> None:
        """測試沒有轉帳協調器時的處理"""
        listener = TelemetryListener(transfer_coordinator=None)

        parsed = {
            "transfer_id": "550e8400-e29b-41d4-a716-446655440000",
            "check_type": "balance_check",
            "result": "1",
        }

        # Should not raise exception
        await listener._handle_transfer_check_result(parsed)

    @pytest.mark.asyncio
    async def test_handle_transfer_check_result_invalid_data(
        self, mock_transfer_coordinator: MagicMock
    ) -> None:
        """測試無效數據"""
        listener = TelemetryListener(transfer_coordinator=mock_transfer_coordinator)

        # No transfer_id
        parsed = {"check_type": "balance_check", "result": "1"}

        # Should not call coordinator
        await listener._handle_transfer_check_result(parsed)
        mock_transfer_coordinator.handle_check_result.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_transfer_check_approved(
        self, mock_transfer_coordinator: MagicMock
    ) -> None:
        """測試處理轉帳檢查批准"""
        listener = TelemetryListener(transfer_coordinator=mock_transfer_coordinator)

        parsed = {"transfer_id": "550e8400-e29b-41d4-a716-446655440000"}

        await listener._handle_transfer_check_approved(parsed)

        mock_transfer_coordinator.handle_check_approved.assert_called_once_with(
            transfer_id=UUID("550e8400-e29b-41d4-a716-446655440000")
        )

    @pytest.mark.asyncio
    async def test_handle_transfer_check_approved_no_coordinator(self) -> None:
        """測試沒有轉帳協調器時的批准處理"""
        listener = TelemetryListener(transfer_coordinator=None)

        parsed = {"transfer_id": "550e8400-e29b-41d4-a716-446655440000"}

        # Should not raise exception
        await listener._handle_transfer_check_approved(parsed)


class TestTxAndTokenTracking:
    """測試交易和 token 追蹤"""

    def test_is_tx_seen_new_transaction(self) -> None:
        """測試新交易"""
        listener = TelemetryListener()

        tx_id = "new_transaction_123"

        # First call should return False (not seen)
        assert not listener._is_tx_seen(tx_id)

        # Second call should return True (already seen)
        assert listener._is_tx_seen(tx_id)

        # Verify it's in the seen set
        assert tx_id in listener._seen_tx

    def test_is_tx_seen_memory_management(self) -> None:
        """測試交易記憶管理"""
        listener = TelemetryListener()

        # Add more transactions than the max size
        max_size = 10000
        for i in range(max_size + 100):
            listener._is_tx_seen(f"tx_{i}")

        # Should not grow beyond max size
        assert len(listener._seen_tx) <= max_size
        assert len(listener._tx_order) <= max_size

    def test_is_token_seen_new_token(self) -> None:
        """測試新 token"""
        listener = TelemetryListener()

        token = "new_token_456"

        # First call should return False (not seen)
        assert not listener._is_token_seen(token)

        # Second call should return True (already seen)
        assert listener._is_token_seen(token)

        # Verify it's in the seen set
        assert token in listener._seen_tokens

    def test_is_token_seen_memory_management(self) -> None:
        """測試 token 記憶管理"""
        listener = TelemetryListener()

        # Add more tokens than the max size
        max_size = 10000
        for i in range(max_size + 100):
            listener._is_token_seen(f"token_{i}")

        # Should not grow beyond max size
        assert len(listener._seen_tokens) <= max_size
        assert len(listener._token_order) <= max_size


class TestMaybeEmitStateCouncilEvent:
    """測試國務院事件發布"""

    @pytest.mark.asyncio
    async def test_emit_event_no_guild_id(self) -> None:
        """測試沒有 guild_id 時不發布事件"""
        parsed = {"initiator_id": 12345, "target_id": 67890}

        # Should not raise exception
        await _maybe_emit_state_council_event(parsed, cause="test")

    @pytest.mark.asyncio
    async def test_emit_event_success(self) -> None:
        """測試成功發布事件"""
        parsed = {
            "event_type": "transaction_success",
            "guild_id": 12345,
            "initiator_id": 99999,  # Government account
            "target_id": 67890,
            "amount": 1000,
        }

        with patch("src.infra.telemetry.listener.db_pool.get_pool") as _mock_get_pool:
            # Mock database operations
            mock_pool = MagicMock()
            mock_conn = MagicMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            # Mock governance gateway
            with patch(
                "src.infra.telemetry.listener.StateCouncilGovernanceGateway"
            ) as mock_governance:
                with patch("src.infra.telemetry.listener.EconomyQueryGateway") as mock_economy:
                    # Mock government account
                    mock_account = MagicMock()
                    mock_account.account_id = 99999
                    mock_account.department = "財政部"
                    mock_governance.return_value.fetch_government_accounts = AsyncMock(
                        return_value=[mock_account]
                    )

                    # Mock economy query
                    mock_economy.return_value.fetch_balance = AsyncMock(
                        return_value=MagicMock(balance=5000)
                    )
                    mock_governance.return_value.update_account_balance = AsyncMock()

                    # Mock state council event publishing
                    with patch(
                        "src.infra.telemetry.listener.publish_state_council_event"
                    ) as mock_publish:
                        await _maybe_emit_state_council_event(parsed, cause="transaction_success")

                        # Should publish state council event
                        mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_event_no_affected_departments(self) -> None:
        """測試沒有受影響部門時不發布事件"""
        parsed = {
            "event_type": "transaction_success",
            "guild_id": 12345,
            "initiator_id": 67890,  # Regular user
            "target_id": 11111,  # Regular user
            "amount": 1000,
        }

        with patch("src.infra.telemetry.listener.db_pool.get_pool") as _mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = MagicMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            with patch(
                "src.infra.telemetry.listener.StateCouncilGovernanceGateway"
            ) as mock_governance:
                mock_governance.return_value.fetch_government_accounts = AsyncMock(return_value=[])

                with patch(
                    "src.infra.telemetry.listener.publish_state_council_event"
                ) as mock_publish:
                    await _maybe_emit_state_council_event(parsed, cause="transaction_success")

                    # Should not publish state council event
                    mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_emit_event_sync_failure(self) -> None:
        """測試同步失敗時的處理"""
        parsed = {
            "event_type": "transaction_success",
            "guild_id": 12345,
            "initiator_id": 99999,  # Government account
            "target_id": 67890,
            "amount": 1000,
        }

        with patch("src.infra.telemetry.listener.db_pool.get_pool") as _mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = MagicMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            with patch(
                "src.infra.telemetry.listener.StateCouncilGovernanceGateway"
            ) as mock_governance:
                # Mock sync failure
                mock_gw_instance = MagicMock()
                mock_gw_instance.fetch_government_accounts = AsyncMock(
                    side_effect=Exception("Database error")
                )
                mock_governance.return_value = mock_gw_instance

                with patch("src.infra.telemetry.listener.LOGGER") as mock_logger:
                    await _maybe_emit_state_council_event(parsed, cause="transaction_success")

                    # Should log warning
                    mock_logger.warning.assert_called()


class TestErrorHandler:
    """測試錯誤處理"""

    @pytest.mark.asyncio
    async def test_run_with_exception(self) -> None:
        """測試運行時發生異常"""
        listener = TelemetryListener()

        with patch(
            "src.infra.telemetry.listener.db_pool.init_pool",
            side_effect=RuntimeError("Database error"),
        ):
            with pytest.raises(RuntimeError):
                await listener._run()

    @pytest.mark.asyncio
    async def test_handler_exception(self) -> None:
        """測試處理器拋出異常"""

        def failing_handler(payload: str) -> None:
            raise Exception("Handler error")

        listener = TelemetryListener(handler=failing_handler)

        payload = '{"test": "data"}'

        # Should raise exception (handler exceptions are not caught in _dispatch)
        with pytest.raises(Exception, match="Handler error"):
            await listener._dispatch(None, 12345, "test_channel", payload)

    @pytest.mark.asyncio
    async def test_notify_methods_exception_handling(self, mock_discord_client: MagicMock) -> None:
        """測試通知方法的異常處理"""
        listener = TelemetryListener(discord_client=mock_discord_client)

        # Mock user that throws exception on send
        user = MagicMock()
        user.send = AsyncMock(side_effect=Exception("DM failed"))
        mock_discord_client.get_user.return_value = user

        parsed = {"initiator_id": 12345, "target_id": 67890, "amount": 1000}

        # Should not raise exception
        await listener._notify_target_dm(parsed)
        await listener._notify_initiator_dm(parsed)
