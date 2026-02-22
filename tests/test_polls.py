"""Tests for poll management."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from flumphbot.bot.polls import PollManager
from flumphbot.calendar.models import AvailabilitySlot, EventStatus
from flumphbot.storage.base import PollRecord


@pytest.fixture
def mock_storage():
    """Create a mock storage backend."""
    storage = AsyncMock()
    storage.create_poll = AsyncMock()
    storage.get_poll = AsyncMock(return_value=None)
    storage.get_active_poll = AsyncMock(return_value=None)
    storage.get_poll_options = AsyncMock(return_value=[])
    storage.update_poll = AsyncMock()
    return storage


@pytest.fixture
def poll_manager(mock_storage):
    """Create a poll manager with mock storage."""
    return PollManager(mock_storage)


class TestCreateDndEvent:
    """Tests for D&D event creation."""

    def test_creates_busy_event(self, poll_manager):
        date = datetime(2024, 3, 15, 18, 0)
        event = poll_manager.create_dnd_event(date)
        assert event.status == EventStatus.BUSY

    def test_sets_default_duration(self, poll_manager):
        date = datetime(2024, 3, 15, 18, 0)
        event = poll_manager.create_dnd_event(date)
        duration = event.end - event.start
        assert duration == timedelta(hours=4)

    def test_custom_duration(self, poll_manager):
        date = datetime(2024, 3, 15, 18, 0)
        event = poll_manager.create_dnd_event(date, duration_hours=6)
        duration = event.end - event.start
        assert duration == timedelta(hours=6)

    def test_default_evening_time(self, poll_manager):
        date = datetime(2024, 3, 15)  # No time specified
        event = poll_manager.create_dnd_event(date)
        assert event.start.hour == 18

    def test_custom_title(self, poll_manager):
        date = datetime(2024, 3, 15, 18, 0)
        event = poll_manager.create_dnd_event(date, title="Epic Campaign Session 5")
        assert event.summary == "Epic Campaign Session 5"


class TestAvailabilitySlot:
    """Tests for availability slot formatting."""

    def test_display_date(self):
        slot = AvailabilitySlot(date=datetime(2024, 3, 15))
        assert "Friday" in slot.display_date
        assert "March" in slot.display_date
        assert "15" in slot.display_date

    def test_display_time_with_times(self):
        slot = AvailabilitySlot(
            date=datetime(2024, 3, 15),
            start_time=datetime(2024, 3, 15, 18, 0),
            end_time=datetime(2024, 3, 15, 22, 0),
        )
        assert "PM" in slot.display_time

    def test_display_time_all_day(self):
        slot = AvailabilitySlot(date=datetime(2024, 3, 15))
        assert slot.display_time == "All day"


class TestPollManager:
    """Tests for poll manager functionality."""

    @pytest.mark.asyncio
    async def test_no_poll_with_empty_slots(self, poll_manager):
        channel = MagicMock()
        result = await poll_manager.create_scheduling_poll(channel, [])
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_poll_returns_none(self, poll_manager):
        result = await poll_manager.get_active_poll()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_poll_returns_poll(self, poll_manager, mock_storage):
        expected = PollRecord(
            id="test-id",
            message_id=12345,
            channel_id=67890,
            created_at=datetime.utcnow(),
            closes_at=datetime.utcnow() + timedelta(hours=48),
        )
        mock_storage.get_active_poll.return_value = expected

        result = await poll_manager.get_active_poll()
        assert result == expected
