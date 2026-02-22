"""Event analysis for calendar hygiene and personal event detection."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from flumphbot.calendar.models import AvailabilitySlot, CalendarEvent, EventStatus

logger = logging.getLogger(__name__)


class EventCategory(Enum):
    """Category of a calendar event."""

    DND = "dnd"
    AWAY = "away"
    PERSONAL = "personal"
    OTHER = "other"


@dataclass
class AnalysisResult:
    """Result of analyzing an event."""

    event: CalendarEvent
    should_be_free: bool
    is_personal: bool
    is_dnd_session: bool
    matched_keywords: list[str]
    category: EventCategory = EventCategory.OTHER


class EventAnalyzer:
    """Analyzes calendar events for hygiene and personal content detection."""

    # Default keywords for each category
    DEFAULT_DND_KEYWORDS = [
        "D&D",
        "DND",
        "Dungeons",
        "Campaign",
        "Session",
    ]

    DEFAULT_AWAY_KEYWORDS = [
        "Away",
        "Unavailable",
        "Holiday",
        "Vacation",
        "Busy",
        "PTO",
        "Time Off",
        "Out of Office",
        "OOO",
        "Trip",
        "Travel",
    ]

    DEFAULT_PERSONAL_KEYWORDS = [
        "birthday",
        "doctor",
        "dentist",
        "appointment",
        "interview",
        "therapy",
        "medical",
    ]

    def __init__(
        self,
        dnd_keywords: list[str] | None = None,
        away_keywords: list[str] | None = None,
        personal_keywords: list[str] | None = None,
    ):
        """Initialize the event analyzer.

        Args:
            dnd_keywords: Keywords to identify D&D session events.
            away_keywords: Keywords to identify away time / vacation events.
            personal_keywords: Keywords indicating potentially personal events.
        """
        self.dnd_keywords = dnd_keywords or self.DEFAULT_DND_KEYWORDS
        self.away_keywords = away_keywords or self.DEFAULT_AWAY_KEYWORDS
        self.personal_keywords = personal_keywords or self.DEFAULT_PERSONAL_KEYWORDS

    def is_dnd_session(self, event: CalendarEvent) -> bool:
        """Check if an event is a D&D session.

        Args:
            event: The event to check.

        Returns:
            True if this appears to be a D&D session.
        """
        title = event.summary.lower()
        return any(kw.lower() in title for kw in self.dnd_keywords)

    def is_away_event(self, event: CalendarEvent) -> bool:
        """Check if an event is an away time / vacation event.

        Args:
            event: The event to check.

        Returns:
            True if this appears to be an away time event.
        """
        title = event.summary.lower()
        return any(kw.lower() in title for kw in self.away_keywords)

    def get_category(self, event: CalendarEvent) -> EventCategory:
        """Determine the category of an event.

        Args:
            event: The event to categorize.

        Returns:
            The EventCategory for this event.
        """
        # D&D takes priority
        if self.is_dnd_session(event):
            return EventCategory.DND

        # Check for away time
        if self.is_away_event(event):
            return EventCategory.AWAY

        # Check for personal events
        if self.detect_personal_keywords(event):
            return EventCategory.PERSONAL

        return EventCategory.OTHER

    def should_be_free(self, event: CalendarEvent) -> bool:
        """Determine if an event should be marked as Free.

        D&D sessions should be Busy, everything else should be Free.

        Args:
            event: The event to check.

        Returns:
            True if the event should be marked as Free.
        """
        # Only D&D sessions should remain Busy
        # Away time and everything else should be Free
        return not self.is_dnd_session(event)

    def detect_personal_keywords(self, event: CalendarEvent) -> list[str]:
        """Find personal keywords in an event.

        Args:
            event: The event to check.

        Returns:
            List of matched personal keywords.
        """
        text = f"{event.summary} {event.description or ''}".lower()
        matched = []

        for keyword in self.personal_keywords:
            # Use word boundary matching for more accurate detection
            pattern = rf"\b{re.escape(keyword)}\b"
            if re.search(pattern, text, re.IGNORECASE):
                matched.append(keyword)

        return matched

    def analyze_event(self, event: CalendarEvent) -> AnalysisResult:
        """Perform full analysis of an event.

        Args:
            event: The event to analyze.

        Returns:
            AnalysisResult with all findings.
        """
        is_dnd = self.is_dnd_session(event)
        matched_keywords = self.detect_personal_keywords(event)
        category = self.get_category(event)

        return AnalysisResult(
            event=event,
            should_be_free=self.should_be_free(event),
            is_personal=len(matched_keywords) > 0,
            is_dnd_session=is_dnd,
            matched_keywords=matched_keywords,
            category=category,
        )

    def find_events_needing_fix(
        self, events: list[CalendarEvent]
    ) -> list[CalendarEvent]:
        """Find events that need their status fixed.

        Args:
            events: List of events to check.

        Returns:
            List of events that should be Free but are currently Busy.
        """
        needs_fix = []

        for event in events:
            if self.should_be_free(event) and event.status == EventStatus.BUSY:
                needs_fix.append(event)

        return needs_fix

    def find_personal_events(self, events: list[CalendarEvent]) -> list[AnalysisResult]:
        """Find events that appear to be personal.

        Args:
            events: List of events to check.

        Returns:
            List of AnalysisResult for events with personal keywords.
        """
        personal = []

        for event in events:
            result = self.analyze_event(event)
            if result.is_personal:
                personal.append(result)

        return personal

    def find_available_dates(
        self,
        events: list[CalendarEvent],
        start_date: datetime,
        days_ahead: int = 14,
        preferred_day: str | None = None,
    ) -> list[AvailabilitySlot]:
        """Find dates without conflicting events.

        Args:
            events: List of existing events.
            start_date: Starting date for search.
            days_ahead: Number of days to look ahead.
            preferred_day: Preferred day of week (e.g., "Saturday").

        Returns:
            List of available date slots.
        """
        # Build a set of dates that have blocking events
        blocked_dates: set[datetime] = set()

        for event in events:
            # Consider all events that would conflict with a D&D session
            # For simplicity, we'll just block the entire date
            event_date = event.start.replace(hour=0, minute=0, second=0, microsecond=0)
            blocked_dates.add(event_date)

        # Find available dates
        available: list[AvailabilitySlot] = []
        current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        for _ in range(days_ahead):
            current += timedelta(days=1)

            # Skip if date is blocked
            if current in blocked_dates:
                continue

            # If preferred day is set, filter to only that day
            if preferred_day and current.strftime("%A").lower() != preferred_day.lower():
                continue

            available.append(AvailabilitySlot(date=current))

        return available

    def find_away_events(
        self,
        events: list[CalendarEvent],
    ) -> list[CalendarEvent]:
        """Find events that are away time / vacations.

        Args:
            events: List of events to check.

        Returns:
            List of away/vacation-related events.
        """
        away_events = []
        for event in events:
            if self.is_away_event(event):
                away_events.append(event)
            # Also include multi-day all-day events as potential away time
            elif event.all_day and (event.end - event.start).days > 1:
                away_events.append(event)

        return away_events

    def find_vacation_events(
        self,
        events: list[CalendarEvent],
        vacation_keywords: list[str] | None = None,
    ) -> list[CalendarEvent]:
        """Find events that appear to be vacations or time off.

        Deprecated: Use find_away_events() instead.

        Args:
            events: List of events to check.
            vacation_keywords: Ignored, uses away_keywords from config.

        Returns:
            List of vacation-related events.
        """
        return self.find_away_events(events)
