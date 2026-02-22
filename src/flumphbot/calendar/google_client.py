"""Google Calendar API client."""

import logging
from datetime import datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from flumphbot.calendar.models import CalendarEvent, EventStatus
from flumphbot.config import GoogleConfig

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarClient:
    """Client for interacting with Google Calendar API."""

    def __init__(self, config: GoogleConfig):
        """Initialize the Google Calendar client.

        Args:
            config: Google configuration with credentials and calendar ID.
        """
        self.calendar_id = config.calendar_id
        self._service = None
        self._credentials = config.credentials

    def _get_service(self):
        """Get or create the Google Calendar service."""
        if self._service is None:
            credentials = service_account.Credentials.from_service_account_info(
                self._credentials, scopes=SCOPES
            )
            self._service = build("calendar", "v3", credentials=credentials)
        return self._service

    def get_events(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        max_results: int = 100,
    ) -> list[CalendarEvent]:
        """Fetch events from the calendar.

        Args:
            start_date: Start of time range (defaults to now).
            end_date: End of time range (defaults to 2 weeks from now).
            max_results: Maximum number of events to return.

        Returns:
            List of CalendarEvent objects.
        """
        if start_date is None:
            start_date = datetime.utcnow()
        if end_date is None:
            end_date = start_date + timedelta(weeks=2)

        try:
            service = self._get_service()
            events_result = (
                service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=start_date.isoformat() + "Z",
                    timeMax=end_date.isoformat() + "Z",
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
            return [CalendarEvent.from_google_event(e) for e in events]
        except HttpError as e:
            logger.error(f"Error fetching calendar events: {e}")
            raise

    def create_event(self, event: CalendarEvent) -> CalendarEvent:
        """Create a new event on the calendar.

        Args:
            event: The event to create.

        Returns:
            The created event with ID populated.
        """
        try:
            service = self._get_service()
            result = (
                service.events()
                .insert(calendarId=self.calendar_id, body=event.to_google_event())
                .execute()
            )
            logger.info(f"Created event: {result.get('summary')} ({result.get('id')})")
            return CalendarEvent.from_google_event(result)
        except HttpError as e:
            logger.error(f"Error creating event: {e}")
            raise

    def update_event_status(self, event_id: str, status: EventStatus) -> CalendarEvent:
        """Update an event's busy/free status.

        Args:
            event_id: The ID of the event to update.
            status: The new status (BUSY or FREE).

        Returns:
            The updated event.
        """
        try:
            service = self._get_service()
            # First get the current event
            event = service.events().get(
                calendarId=self.calendar_id, eventId=event_id
            ).execute()

            # Update the transparency
            event["transparency"] = status.value

            # Patch the event
            result = (
                service.events()
                .patch(calendarId=self.calendar_id, eventId=event_id, body=event)
                .execute()
            )
            logger.info(
                f"Updated event {result.get('summary')} status to {status.name}"
            )
            return CalendarEvent.from_google_event(result)
        except HttpError as e:
            logger.error(f"Error updating event status: {e}")
            raise

    def get_event(self, event_id: str) -> CalendarEvent:
        """Get a single event by ID.

        Args:
            event_id: The ID of the event to fetch.

        Returns:
            The calendar event.
        """
        try:
            service = self._get_service()
            result = (
                service.events()
                .get(calendarId=self.calendar_id, eventId=event_id)
                .execute()
            )
            return CalendarEvent.from_google_event(result)
        except HttpError as e:
            logger.error(f"Error fetching event {event_id}: {e}")
            raise

    def delete_event(self, event_id: str) -> None:
        """Delete an event from the calendar.

        Args:
            event_id: The ID of the event to delete.
        """
        try:
            service = self._get_service()
            service.events().delete(
                calendarId=self.calendar_id, eventId=event_id
            ).execute()
            logger.info(f"Deleted event {event_id}")
        except HttpError as e:
            logger.error(f"Error deleting event {event_id}: {e}")
            raise
