"""Data models for calendar events."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EventStatus(Enum):
    """Calendar event busy/free status."""

    BUSY = "opaque"
    FREE = "transparent"


@dataclass
class CalendarEvent:
    """Represents a Google Calendar event."""

    id: str
    summary: str
    start: datetime
    end: datetime
    status: EventStatus
    creator_email: str | None = None
    description: str | None = None
    all_day: bool = False

    @classmethod
    def from_google_event(cls, event: dict) -> "CalendarEvent":
        """Create a CalendarEvent from a Google Calendar API event dict."""
        # Handle all-day events vs timed events
        start_data = event.get("start", {})
        end_data = event.get("end", {})

        if "date" in start_data:
            # All-day event
            start = datetime.fromisoformat(start_data["date"])
            end = datetime.fromisoformat(end_data["date"])
            all_day = True
        else:
            # Timed event
            start = datetime.fromisoformat(
                start_data.get("dateTime", "").replace("Z", "+00:00")
            )
            end = datetime.fromisoformat(
                end_data.get("dateTime", "").replace("Z", "+00:00")
            )
            all_day = False

        # Parse transparency (busy/free status)
        transparency = event.get("transparency", "opaque")
        status = EventStatus.FREE if transparency == "transparent" else EventStatus.BUSY

        return cls(
            id=event.get("id", ""),
            summary=event.get("summary", ""),
            start=start,
            end=end,
            status=status,
            creator_email=event.get("creator", {}).get("email"),
            description=event.get("description"),
            all_day=all_day,
        )

    def to_google_event(self) -> dict:
        """Convert to Google Calendar API event dict."""
        event = {
            "summary": self.summary,
            "transparency": self.status.value,
        }

        if self.description:
            event["description"] = self.description

        if self.all_day:
            event["start"] = {"date": self.start.date().isoformat()}
            event["end"] = {"date": self.end.date().isoformat()}
        else:
            event["start"] = {"dateTime": self.start.isoformat()}
            event["end"] = {"dateTime": self.end.isoformat()}

        return event


@dataclass
class AvailabilitySlot:
    """Represents a time slot when all players are available."""

    date: datetime
    start_time: datetime | None = None
    end_time: datetime | None = None

    @property
    def display_date(self) -> str:
        """Format date for display."""
        return self.date.strftime("%A, %B %d")

    @property
    def display_time(self) -> str:
        """Format time range for display."""
        if self.start_time and self.end_time:
            return f"{self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')}"
        return "All day"
