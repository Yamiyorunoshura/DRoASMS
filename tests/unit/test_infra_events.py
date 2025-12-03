"""Unit tests for event infrastructure (council_events, state_council_events)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from src.infra.events.council_events import (
    CouncilEvent,
    CouncilEventKind,
    publish,
    subscribe,
)
from src.infra.events.state_council_events import (
    StateCouncilEvent,
    StateCouncilEventKind,
)
from src.infra.events.state_council_events import publish as sc_publish
from src.infra.events.state_council_events import subscribe as sc_subscribe

# =============================================================================
# Test: CouncilEvent dataclass
# =============================================================================


@pytest.mark.unit
class TestCouncilEvent:
    """Test cases for CouncilEvent dataclass."""

    def test_council_event_creation(self) -> None:
        """Test creating a CouncilEvent."""
        guild_id = 123456
        proposal_id = uuid4()
        event = CouncilEvent(
            guild_id=guild_id,
            proposal_id=proposal_id,
            kind="proposal_created",
            status="pending",
        )

        assert event.guild_id == guild_id
        assert event.proposal_id == proposal_id
        assert event.kind == "proposal_created"
        assert event.status == "pending"

    def test_council_event_without_status(self) -> None:
        """Test creating a CouncilEvent without status."""
        guild_id = 123456
        proposal_id = uuid4()
        event = CouncilEvent(
            guild_id=guild_id,
            proposal_id=proposal_id,
            kind="proposal_updated",
        )

        assert event.guild_id == guild_id
        assert event.proposal_id == proposal_id
        assert event.kind == "proposal_updated"
        assert event.status is None

    def test_council_event_without_proposal_id(self) -> None:
        """Test creating a CouncilEvent without proposal_id."""
        guild_id = 123456
        event = CouncilEvent(
            guild_id=guild_id,
            proposal_id=None,
            kind="proposal_cancelled",
        )

        assert event.guild_id == guild_id
        assert event.proposal_id is None
        assert event.kind == "proposal_cancelled"

    def test_council_event_frozen(self) -> None:
        """Test that CouncilEvent is frozen (immutable)."""
        event = CouncilEvent(
            guild_id=123,
            proposal_id=uuid4(),
            kind="proposal_created",
        )

        with pytest.raises(AttributeError):
            event.guild_id = 456  # type: ignore[misc]

    def test_council_event_kind_literals(self) -> None:
        """Test all valid CouncilEventKind literals."""
        kinds: list[CouncilEventKind] = [
            "proposal_created",
            "proposal_updated",
            "proposal_cancelled",
            "proposal_status_changed",
        ]

        for kind in kinds:
            event = CouncilEvent(guild_id=123, proposal_id=uuid4(), kind=kind)
            assert event.kind == kind


# =============================================================================
# Test: CouncilEvents subscribe/publish
# =============================================================================


@pytest.mark.unit
class TestCouncilEventsSubscription:
    """Test cases for council events subscription and publishing."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self) -> None:
        """Test subscribing to and publishing council events."""
        guild_id = 123456
        proposal_id = uuid4()
        received_events: list[CouncilEvent] = []

        async def callback(event: CouncilEvent) -> None:
            received_events.append(event)

        # Subscribe
        unsubscribe = await subscribe(guild_id, callback)

        # Publish event
        event = CouncilEvent(
            guild_id=guild_id,
            proposal_id=proposal_id,
            kind="proposal_created",
            status="pending",
        )
        await publish(event)

        # Give time for async task to execute
        await asyncio.sleep(0.1)

        # Verify callback was called
        assert len(received_events) == 1
        assert received_events[0].guild_id == guild_id
        assert received_events[0].proposal_id == proposal_id

        # Cleanup
        await unsubscribe()

    @pytest.mark.asyncio
    async def test_subscribe_multiple_callbacks(self) -> None:
        """Test multiple callbacks for the same guild."""
        guild_id = 123456
        received_1: list[CouncilEvent] = []
        received_2: list[CouncilEvent] = []

        async def callback1(event: CouncilEvent) -> None:
            received_1.append(event)

        async def callback2(event: CouncilEvent) -> None:
            received_2.append(event)

        # Subscribe both
        unsubscribe1 = await subscribe(guild_id, callback1)
        unsubscribe2 = await subscribe(guild_id, callback2)

        # Publish event
        event = CouncilEvent(
            guild_id=guild_id,
            proposal_id=uuid4(),
            kind="proposal_updated",
        )
        await publish(event)

        await asyncio.sleep(0.1)

        # Both callbacks should receive the event
        assert len(received_1) == 1
        assert len(received_2) == 1

        # Cleanup
        await unsubscribe1()
        await unsubscribe2()

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_callback(self) -> None:
        """Test that unsubscribe removes the callback."""
        guild_id = 123456
        received_events: list[CouncilEvent] = []

        async def callback(event: CouncilEvent) -> None:
            received_events.append(event)

        unsubscribe = await subscribe(guild_id, callback)

        # Publish first event (should be received)
        event1 = CouncilEvent(
            guild_id=guild_id,
            proposal_id=uuid4(),
            kind="proposal_created",
        )
        await publish(event1)
        await asyncio.sleep(0.1)

        assert len(received_events) == 1

        # Unsubscribe
        await unsubscribe()

        # Publish second event (should NOT be received)
        event2 = CouncilEvent(
            guild_id=guild_id,
            proposal_id=uuid4(),
            kind="proposal_updated",
        )
        await publish(event2)
        await asyncio.sleep(0.1)

        # Should still be 1 (second event not received)
        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_publish_to_empty_subscribers(self) -> None:
        """Test publishing when there are no subscribers."""
        guild_id = 123456
        event = CouncilEvent(
            guild_id=guild_id,
            proposal_id=uuid4(),
            kind="proposal_created",
        )

        # Should not raise
        await publish(event)

    @pytest.mark.asyncio
    async def test_publish_different_guild_not_received(self) -> None:
        """Test that events for different guilds are not received."""
        guild_id_1 = 111111
        guild_id_2 = 222222
        received_events: list[CouncilEvent] = []

        async def callback(event: CouncilEvent) -> None:
            received_events.append(event)

        # Subscribe to guild_id_1
        unsubscribe = await subscribe(guild_id_1, callback)

        # Publish to guild_id_2
        event = CouncilEvent(
            guild_id=guild_id_2,
            proposal_id=uuid4(),
            kind="proposal_created",
        )
        await publish(event)
        await asyncio.sleep(0.1)

        # Should not receive event
        assert len(received_events) == 0

        # Cleanup
        await unsubscribe()

    @pytest.mark.asyncio
    async def test_callback_error_is_logged_not_raised(self) -> None:
        """Test that callback errors are logged but not raised."""
        guild_id = 123456

        async def failing_callback(event: CouncilEvent) -> None:
            raise RuntimeError("Callback failed")

        unsubscribe = await subscribe(guild_id, failing_callback)

        event = CouncilEvent(
            guild_id=guild_id,
            proposal_id=uuid4(),
            kind="proposal_created",
        )

        # Should not raise (error is logged internally)
        await publish(event)
        await asyncio.sleep(0.1)

        # Cleanup
        await unsubscribe()

    @pytest.mark.asyncio
    async def test_unsubscribe_idempotent(self) -> None:
        """Test that calling unsubscribe multiple times is safe."""
        guild_id = 123456

        async def callback(event: CouncilEvent) -> None:
            pass

        unsubscribe = await subscribe(guild_id, callback)

        # Call unsubscribe multiple times
        await unsubscribe()
        await unsubscribe()
        await unsubscribe()

        # Should not raise

    @pytest.mark.asyncio
    async def test_multiple_events_published(self) -> None:
        """Test publishing multiple events."""
        guild_id = 123456
        received_events: list[CouncilEvent] = []

        async def callback(event: CouncilEvent) -> None:
            received_events.append(event)

        unsubscribe = await subscribe(guild_id, callback)

        # Publish multiple events
        for _ in range(5):
            event = CouncilEvent(
                guild_id=guild_id,
                proposal_id=uuid4(),
                kind="proposal_created",
            )
            await publish(event)

        await asyncio.sleep(0.2)

        # Should receive all 5 events
        assert len(received_events) == 5

        # Cleanup
        await unsubscribe()


# =============================================================================
# Test: StateCouncilEvent dataclass
# =============================================================================


@pytest.mark.unit
class TestStateCouncilEvent:
    """Test cases for StateCouncilEvent dataclass."""

    def test_state_council_event_creation(self) -> None:
        """Test creating a StateCouncilEvent."""
        guild_id = 123456
        event = StateCouncilEvent(
            guild_id=guild_id,
            kind="department_balance_changed",
            departments=("財政部", "中央銀行"),
            cause="transaction_success",
        )

        assert event.guild_id == guild_id
        assert event.kind == "department_balance_changed"
        assert event.departments == ("財政部", "中央銀行")
        assert event.cause == "transaction_success"

    def test_state_council_event_minimal(self) -> None:
        """Test creating a StateCouncilEvent with minimal fields."""
        guild_id = 123456
        event = StateCouncilEvent(
            guild_id=guild_id,
            kind="department_config_updated",
        )

        assert event.guild_id == guild_id
        assert event.kind == "department_config_updated"
        assert event.departments == ()
        assert event.cause is None

    def test_state_council_event_frozen(self) -> None:
        """Test that StateCouncilEvent is frozen (immutable)."""
        event = StateCouncilEvent(
            guild_id=123,
            kind="department_balance_changed",
        )

        with pytest.raises(AttributeError):
            event.guild_id = 456  # type: ignore[misc]

    def test_state_council_event_kind_literals(self) -> None:
        """Test all valid StateCouncilEventKind literals."""
        kinds: list[StateCouncilEventKind] = [
            "department_balance_changed",
            "department_config_updated",
        ]

        for kind in kinds:
            event = StateCouncilEvent(guild_id=123, kind=kind)
            assert event.kind == kind


# =============================================================================
# Test: StateCouncilEvents subscribe/publish
# =============================================================================


@pytest.mark.unit
class TestStateCouncilEventsSubscription:
    """Test cases for state council events subscription and publishing."""

    @pytest.mark.asyncio
    async def test_sc_subscribe_and_publish(self) -> None:
        """Test subscribing to and publishing state council events."""
        guild_id = 123456
        received_events: list[StateCouncilEvent] = []

        async def callback(event: StateCouncilEvent) -> None:
            received_events.append(event)

        # Subscribe
        unsubscribe = await sc_subscribe(guild_id, callback)

        # Publish event
        event = StateCouncilEvent(
            guild_id=guild_id,
            kind="department_balance_changed",
            departments=("財政部",),
            cause="adjustment_success",
        )
        await sc_publish(event)

        await asyncio.sleep(0.1)

        # Verify callback was called
        assert len(received_events) == 1
        assert received_events[0].guild_id == guild_id
        assert received_events[0].kind == "department_balance_changed"
        assert received_events[0].departments == ("財政部",)

        # Cleanup
        await unsubscribe()

    @pytest.mark.asyncio
    async def test_sc_subscribe_multiple_callbacks(self) -> None:
        """Test multiple callbacks for state council events."""
        guild_id = 123456
        received_1: list[StateCouncilEvent] = []
        received_2: list[StateCouncilEvent] = []

        async def callback1(event: StateCouncilEvent) -> None:
            received_1.append(event)

        async def callback2(event: StateCouncilEvent) -> None:
            received_2.append(event)

        unsubscribe1 = await sc_subscribe(guild_id, callback1)
        unsubscribe2 = await sc_subscribe(guild_id, callback2)

        event = StateCouncilEvent(
            guild_id=guild_id,
            kind="department_config_updated",
        )
        await sc_publish(event)

        await asyncio.sleep(0.1)

        assert len(received_1) == 1
        assert len(received_2) == 1

        await unsubscribe1()
        await unsubscribe2()

    @pytest.mark.asyncio
    async def test_sc_unsubscribe_removes_callback(self) -> None:
        """Test that unsubscribe removes the callback."""
        guild_id = 123456
        received_events: list[StateCouncilEvent] = []

        async def callback(event: StateCouncilEvent) -> None:
            received_events.append(event)

        unsubscribe = await sc_subscribe(guild_id, callback)

        event1 = StateCouncilEvent(guild_id=guild_id, kind="department_balance_changed")
        await sc_publish(event1)
        await asyncio.sleep(0.1)

        assert len(received_events) == 1

        await unsubscribe()

        event2 = StateCouncilEvent(guild_id=guild_id, kind="department_config_updated")
        await sc_publish(event2)
        await asyncio.sleep(0.1)

        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_sc_publish_to_empty_subscribers(self) -> None:
        """Test publishing when there are no subscribers."""
        event = StateCouncilEvent(
            guild_id=123456,
            kind="department_balance_changed",
        )

        # Should not raise
        await sc_publish(event)

    @pytest.mark.asyncio
    async def test_sc_publish_different_guild_not_received(self) -> None:
        """Test that events for different guilds are not received."""
        guild_id_1 = 111111
        guild_id_2 = 222222
        received_events: list[StateCouncilEvent] = []

        async def callback(event: StateCouncilEvent) -> None:
            received_events.append(event)

        unsubscribe = await sc_subscribe(guild_id_1, callback)

        event = StateCouncilEvent(
            guild_id=guild_id_2,
            kind="department_balance_changed",
        )
        await sc_publish(event)
        await asyncio.sleep(0.1)

        assert len(received_events) == 0

        await unsubscribe()

    @pytest.mark.asyncio
    async def test_sc_callback_error_is_logged_not_raised(self) -> None:
        """Test that callback errors are logged but not raised."""
        guild_id = 123456

        async def failing_callback(event: StateCouncilEvent) -> None:
            raise RuntimeError("State council callback failed")

        unsubscribe = await sc_subscribe(guild_id, failing_callback)

        event = StateCouncilEvent(
            guild_id=guild_id,
            kind="department_balance_changed",
        )

        # Should not raise
        await sc_publish(event)
        await asyncio.sleep(0.1)

        await unsubscribe()

    @pytest.mark.asyncio
    async def test_sc_unsubscribe_idempotent(self) -> None:
        """Test that calling unsubscribe multiple times is safe."""
        guild_id = 123456

        async def callback(event: StateCouncilEvent) -> None:
            pass

        unsubscribe = await sc_subscribe(guild_id, callback)

        await unsubscribe()
        await unsubscribe()
        await unsubscribe()

    @pytest.mark.asyncio
    async def test_sc_multiple_events_published(self) -> None:
        """Test publishing multiple state council events."""
        guild_id = 123456
        received_events: list[StateCouncilEvent] = []

        async def callback(event: StateCouncilEvent) -> None:
            received_events.append(event)

        unsubscribe = await sc_subscribe(guild_id, callback)

        for i in range(5):
            event = StateCouncilEvent(
                guild_id=guild_id,
                kind="department_balance_changed",
                departments=(f"部門{i}",),
            )
            await sc_publish(event)

        await asyncio.sleep(0.2)

        assert len(received_events) == 5

        await unsubscribe()


# =============================================================================
# Test: Event isolation between council and state_council
# =============================================================================


@pytest.mark.unit
class TestEventIsolation:
    """Test that council and state_council events are isolated."""

    @pytest.mark.asyncio
    async def test_council_and_state_council_events_isolated(self) -> None:
        """Test that council and state_council subscribers don't interfere."""
        guild_id = 123456
        council_events: list[CouncilEvent] = []
        state_council_events: list[StateCouncilEvent] = []

        async def council_callback(event: CouncilEvent) -> None:
            council_events.append(event)

        async def state_council_callback(event: StateCouncilEvent) -> None:
            state_council_events.append(event)

        # Subscribe to both
        council_unsub = await subscribe(guild_id, council_callback)
        state_council_unsub = await sc_subscribe(guild_id, state_council_callback)

        # Publish council event
        council_event = CouncilEvent(
            guild_id=guild_id,
            proposal_id=uuid4(),
            kind="proposal_created",
        )
        await publish(council_event)

        # Publish state council event
        state_council_event = StateCouncilEvent(
            guild_id=guild_id,
            kind="department_balance_changed",
        )
        await sc_publish(state_council_event)

        await asyncio.sleep(0.1)

        # Each should receive only their respective event
        assert len(council_events) == 1
        assert len(state_council_events) == 1

        # Cleanup
        await council_unsub()
        await state_council_unsub()
