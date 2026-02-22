"""Tests for the event analyzer."""

from datetime import datetime, timedelta

import pytest

from flumphbot.calendar.event_analyzer import EventAnalyzer
from flumphbot.calendar.models import CalendarEvent, EventStatus


@pytest.fixture
def analyzer():
    """Create an event analyzer for testing."""
    return EventAnalyzer(dnd_session_keyword="D&D")


@pytest.fixture
def sample_events():
    """Create sample calendar events for testing."""
    now = datetime.utcnow()
    return [
        CalendarEvent(
            id="1",
            summary="D&D Session - Campaign Name",
            start=now + timedelta(days=3),
            end=now + timedelta(days=3, hours=4),
            status=EventStatus.BUSY,
        ),
        CalendarEvent(
            id="2",
            summary="Vacation in Hawaii",
            start=now + timedelta(days=7),
            end=now + timedelta(days=14),
            status=EventStatus.BUSY,
            all_day=True,
        ),
        CalendarEvent(
            id="3",
            summary="Doctor appointment",
            start=now + timedelta(days=2),
            end=now + timedelta(days=2, hours=1),
            status=EventStatus.BUSY,
        ),
        CalendarEvent(
            id="4",
            summary="Team meeting",
            start=now + timedelta(days=1),
            end=now + timedelta(days=1, hours=1),
            status=EventStatus.FREE,
        ),
    ]


class TestIsDndSession:
    """Tests for D&D session detection."""

    def test_detects_dnd_keyword(self, analyzer):
        event = CalendarEvent(
            id="1",
            summary="D&D Session",
            start=datetime.utcnow(),
            end=datetime.utcnow() + timedelta(hours=4),
            status=EventStatus.BUSY,
        )
        assert analyzer.is_dnd_session(event) is True

    def test_detects_dnd_variant(self, analyzer):
        event = CalendarEvent(
            id="1",
            summary="Weekly DnD game",
            start=datetime.utcnow(),
            end=datetime.utcnow() + timedelta(hours=4),
            status=EventStatus.BUSY,
        )
        assert analyzer.is_dnd_session(event) is True

    def test_detects_session_keyword(self, analyzer):
        event = CalendarEvent(
            id="1",
            summary="Session 42 - The Dragon's Lair",
            start=datetime.utcnow(),
            end=datetime.utcnow() + timedelta(hours=4),
            status=EventStatus.BUSY,
        )
        assert analyzer.is_dnd_session(event) is True

    def test_does_not_match_unrelated(self, analyzer):
        event = CalendarEvent(
            id="1",
            summary="Doctor appointment",
            start=datetime.utcnow(),
            end=datetime.utcnow() + timedelta(hours=1),
            status=EventStatus.BUSY,
        )
        assert analyzer.is_dnd_session(event) is False


class TestShouldBeFree:
    """Tests for busy/free determination."""

    def test_dnd_should_be_busy(self, analyzer):
        event = CalendarEvent(
            id="1",
            summary="D&D Session",
            start=datetime.utcnow(),
            end=datetime.utcnow() + timedelta(hours=4),
            status=EventStatus.BUSY,
        )
        assert analyzer.should_be_free(event) is False

    def test_vacation_should_be_free(self, analyzer):
        event = CalendarEvent(
            id="1",
            summary="Vacation",
            start=datetime.utcnow(),
            end=datetime.utcnow() + timedelta(days=7),
            status=EventStatus.BUSY,
            all_day=True,
        )
        assert analyzer.should_be_free(event) is True

    def test_random_event_should_be_free(self, analyzer):
        event = CalendarEvent(
            id="1",
            summary="Some random event",
            start=datetime.utcnow(),
            end=datetime.utcnow() + timedelta(hours=2),
            status=EventStatus.BUSY,
        )
        assert analyzer.should_be_free(event) is True


class TestPersonalKeywordDetection:
    """Tests for personal event keyword detection."""

    def test_detects_doctor(self, analyzer):
        event = CalendarEvent(
            id="1",
            summary="Doctor appointment",
            start=datetime.utcnow(),
            end=datetime.utcnow() + timedelta(hours=1),
            status=EventStatus.BUSY,
        )
        keywords = analyzer.detect_personal_keywords(event)
        assert "doctor" in keywords
        assert "appointment" in keywords

    def test_detects_in_description(self, analyzer):
        event = CalendarEvent(
            id="1",
            summary="Important Event",
            start=datetime.utcnow(),
            end=datetime.utcnow() + timedelta(hours=1),
            status=EventStatus.BUSY,
            description="This is a therapy session",
        )
        keywords = analyzer.detect_personal_keywords(event)
        assert "therapy" in keywords

    def test_no_match_for_normal_event(self, analyzer):
        event = CalendarEvent(
            id="1",
            summary="D&D Session",
            start=datetime.utcnow(),
            end=datetime.utcnow() + timedelta(hours=4),
            status=EventStatus.BUSY,
        )
        keywords = analyzer.detect_personal_keywords(event)
        assert len(keywords) == 0


class TestFindEventsNeedingFix:
    """Tests for finding events that need status fixes."""

    def test_finds_busy_vacation(self, analyzer, sample_events):
        needs_fix = analyzer.find_events_needing_fix(sample_events)
        # Should find the vacation and doctor appointment (both Busy but should be Free)
        summaries = [e.summary for e in needs_fix]
        assert "Vacation in Hawaii" in summaries
        assert "Doctor appointment" in summaries

    def test_ignores_dnd_sessions(self, analyzer, sample_events):
        needs_fix = analyzer.find_events_needing_fix(sample_events)
        summaries = [e.summary for e in needs_fix]
        assert "D&D Session - Campaign Name" not in summaries

    def test_ignores_already_free(self, analyzer, sample_events):
        needs_fix = analyzer.find_events_needing_fix(sample_events)
        summaries = [e.summary for e in needs_fix]
        assert "Team meeting" not in summaries


class TestFindAvailableDates:
    """Tests for finding available dates."""

    def test_excludes_blocked_dates(self, analyzer):
        now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        events = [
            CalendarEvent(
                id="1",
                summary="Busy day",
                start=now + timedelta(days=3),
                end=now + timedelta(days=3, hours=4),
                status=EventStatus.BUSY,
            ),
        ]
        available = analyzer.find_available_dates(events, now, days_ahead=5)
        blocked_date = now + timedelta(days=3)
        assert all(slot.date != blocked_date for slot in available)

    def test_filters_by_preferred_day(self, analyzer):
        now = datetime.utcnow()
        available = analyzer.find_available_dates(
            [], now, days_ahead=14, preferred_day="Saturday"
        )
        for slot in available:
            assert slot.date.strftime("%A") == "Saturday"


class TestFindVacationEvents:
    """Tests for vacation detection."""

    def test_finds_vacation_keyword(self, analyzer, sample_events):
        vacations = analyzer.find_vacation_events(sample_events)
        summaries = [v.summary for v in vacations]
        assert "Vacation in Hawaii" in summaries

    def test_finds_multi_day_events(self, analyzer):
        now = datetime.utcnow()
        events = [
            CalendarEvent(
                id="1",
                summary="Out of office",
                start=now,
                end=now + timedelta(days=5),
                status=EventStatus.FREE,
                all_day=True,
            ),
        ]
        vacations = analyzer.find_vacation_events(events)
        assert len(vacations) == 1
