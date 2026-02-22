"""Event analysis for calendar hygiene and personal event detection."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from flumphbot.calendar.models import AvailabilitySlot, CalendarEvent, EventStatus

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Result of analyzing an event."""

    event: CalendarEvent
    should_be_free: bool
    is_personal: bool
    is_dnd_session: bool
    matched_keywords: list[str]


class EventAnalyzer:
    """Analyzes calendar events for hygiene and personal content detection."""

    def __init__(
        self,
        dnd_session_keyword: str = "D&D",
        personal_keywords: list[str] | None = None,
    ):
        """Initialize the event analyzer.

        Args:
            dnd_session_keyword: Keyword to identify D&D session events.
            personal_keywords: List of keywords indicating personal events.
        """
        self.dnd_session_keyword = dnd_session_keyword
        self.personal_keywords = personal_keywords or [
            "doctor",
            "dentist",
            "appointment",
            "interview",
            "therapy",
            "medical",
            "checkup",
            "prescription",
            "court",
            "lawyer",
            "accountant",
            "meeting",
            "call with",
            "date",
            "wedding",
        ]

    def is_dnd_session(self, event: CalendarEvent) -> bool:
        """Check if an event is a D&D session.

        Args:
            event: The event to check.

        Returns:
            True if this appears to be a D&D session.
        """
        title = event.summary.lower()
        keyword = self.dnd_session_keyword.lower()

        # Check for various D&D patterns
        patterns = [
            keyword,
            "d&d",
            "dnd",
            "dungeons",
            "session",
            "campaign",
        ]

        return any(pattern in title for pattern in patterns)

    def should_be_free(self, event: CalendarEvent) -> bool:
        """Determine if an event should be marked as Free.

        D&D sessions should be Busy, everything else should be Free.

        Args:
            event: The event to check.

        Returns:
            True if the event should be marked as Free.
        """
        # D&D sessions should remain Busy, everything else should be Free
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

        return AnalysisResult(
            event=event,
            should_be_free=self.should_be_free(event),
            is_personal=len(matched_keywords) > 0,
            is_dnd_session=is_dnd,
            matched_keywords=matched_keywords,
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

    def find_vacation_events(
        self,
        events: list[CalendarEvent],
        vacation_keywords: list[str] | None = None,
    ) -> list[CalendarEvent]:
        """Find events that appear to be vacations or time off.

        Args:
            events: List of events to check.
            vacation_keywords: Keywords indicating vacation/time off.

        Returns:
            List of vacation-related events.
        """
        if vacation_keywords is None:
            vacation_keywords = [
                "vacation",
                "pto",
                "time off",
                "holiday",
                "away",
                "out of office",
                "ooo",
                "trip",
                "travel",
            ]

        vacations = []
        for event in events:
            title = event.summary.lower()
            if any(kw in title for kw in vacation_keywords) or event.all_day and (event.end - event.start).days > 1:
                vacations.append(event)

        return vacations
