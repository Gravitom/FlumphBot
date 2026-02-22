"""Tests for calendar client and models."""

from datetime import datetime, timezone

from flumphbot.calendar.models import CalendarEvent, EventStatus


class TestCalendarEvent:
    """Tests for CalendarEvent model."""

    def test_from_google_event_timed(self):
        google_event = {
            "id": "event123",
            "summary": "Test Event",
            "start": {"dateTime": "2024-03-15T18:00:00-04:00"},
            "end": {"dateTime": "2024-03-15T22:00:00-04:00"},
            "transparency": "opaque",
            "creator": {"email": "test@example.com"},
            "description": "Test description",
        }

        event = CalendarEvent.from_google_event(google_event)

        assert event.id == "event123"
        assert event.summary == "Test Event"
        assert event.status == EventStatus.BUSY
        assert event.creator_email == "test@example.com"
        assert event.description == "Test description"
        assert event.all_day is False

    def test_from_google_event_all_day(self):
        google_event = {
            "id": "event456",
            "summary": "All Day Event",
            "start": {"date": "2024-03-15"},
            "end": {"date": "2024-03-16"},
            "transparency": "transparent",
        }

        event = CalendarEvent.from_google_event(google_event)

        assert event.id == "event456"
        assert event.summary == "All Day Event"
        assert event.status == EventStatus.FREE
        assert event.all_day is True

    def test_from_google_event_utc(self):
        google_event = {
            "id": "event789",
            "summary": "UTC Event",
            "start": {"dateTime": "2024-03-15T18:00:00Z"},
            "end": {"dateTime": "2024-03-15T22:00:00Z"},
        }

        event = CalendarEvent.from_google_event(google_event)

        assert event.start.tzinfo == timezone.utc
        assert event.end.tzinfo == timezone.utc

    def test_to_google_event_timed(self):
        event = CalendarEvent(
            id="test",
            summary="Test Event",
            start=datetime(2024, 3, 15, 18, 0),
            end=datetime(2024, 3, 15, 22, 0),
            status=EventStatus.BUSY,
            description="Test description",
        )

        google_event = event.to_google_event()

        assert google_event["summary"] == "Test Event"
        assert google_event["transparency"] == "opaque"
        assert google_event["description"] == "Test description"
        assert "dateTime" in google_event["start"]

    def test_to_google_event_all_day(self):
        event = CalendarEvent(
            id="test",
            summary="Vacation",
            start=datetime(2024, 3, 15),
            end=datetime(2024, 3, 20),
            status=EventStatus.FREE,
            all_day=True,
        )

        google_event = event.to_google_event()

        assert google_event["transparency"] == "transparent"
        assert "date" in google_event["start"]
        assert "date" in google_event["end"]


class TestEventStatus:
    """Tests for EventStatus enum."""

    def test_busy_value(self):
        assert EventStatus.BUSY.value == "opaque"

    def test_free_value(self):
        assert EventStatus.FREE.value == "transparent"
