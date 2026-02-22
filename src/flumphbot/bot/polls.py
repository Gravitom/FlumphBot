"""Poll creation and management for D&D session scheduling."""

import logging
import uuid
from datetime import datetime, timedelta

import discord

from flumphbot.calendar.models import AvailabilitySlot, CalendarEvent, EventStatus
from flumphbot.storage.base import PollOption, PollRecord, StorageBackend

logger = logging.getLogger(__name__)

# Maximum poll options Discord allows
MAX_POLL_OPTIONS = 10


class PollManager:
    """Manages D&D session scheduling polls."""

    def __init__(self, storage: StorageBackend):
        """Initialize the poll manager.

        Args:
            storage: Storage backend for poll persistence.
        """
        self.storage = storage

    async def create_scheduling_poll(
        self,
        channel: discord.TextChannel,
        available_slots: list[AvailabilitySlot],
        duration_hours: int = 48,
    ) -> discord.Message | None:
        """Create a scheduling poll in the given channel.

        Args:
            channel: Discord channel to post the poll in.
            available_slots: List of available date/time slots.
            duration_hours: How long the poll should run.

        Returns:
            The posted message, or None if no slots available.
        """
        if not available_slots:
            logger.warning("No available slots for poll")
            return None

        # Limit to max poll options
        slots_to_use = available_slots[:MAX_POLL_OPTIONS]

        # Create poll options
        poll_answers = []
        for slot in slots_to_use:
            label = slot.display_date
            if slot.start_time:
                label += f" ({slot.display_time})"
            poll_answers.append(discord.PollAnswer(text=label[:55]))  # Discord limit

        # Create the poll
        poll = discord.Poll(
            question=discord.PollQuestion(text="When should we have our next D&D session?"),
            answers=poll_answers,
            duration=timedelta(hours=duration_hours),
            multiple=False,
        )

        # Send the poll
        message = await channel.send(poll=poll)

        # Store poll record
        poll_id = str(uuid.uuid4())
        poll_record = PollRecord(
            id=poll_id,
            message_id=message.id,
            channel_id=channel.id,
            created_at=datetime.utcnow(),
            closes_at=datetime.utcnow() + timedelta(hours=duration_hours),
        )

        poll_options = [
            PollOption(poll_id=poll_id, date=slot.date, vote_count=0)
            for slot in slots_to_use
        ]

        await self.storage.create_poll(poll_record, poll_options)
        logger.info(f"Created poll {poll_id} with {len(slots_to_use)} options")

        return message

    async def close_poll_and_get_winner(
        self, poll_record: PollRecord, message: discord.Message
    ) -> datetime | None:
        """Close a poll and determine the winning date.

        Args:
            poll_record: The poll record from storage.
            message: The Discord message containing the poll.

        Returns:
            The winning date, or None if no clear winner.
        """
        if not message.poll:
            logger.error(f"Message {message.id} has no poll")
            return None

        # Get vote counts from the poll
        options = await self.storage.get_poll_options(poll_record.id)

        # Match poll answers to our stored options by index
        max_votes = 0
        winning_date = None

        for i, answer in enumerate(message.poll.answers):
            if i < len(options):
                vote_count = answer.vote_count
                if vote_count > max_votes:
                    max_votes = vote_count
                    winning_date = options[i].date

        if winning_date and max_votes > 0:
            # Update poll record
            poll_record.closed = True
            poll_record.winning_date = winning_date
            await self.storage.update_poll(poll_record)
            logger.info(f"Poll {poll_record.id} won by {winning_date} with {max_votes} votes")

        return winning_date

    async def get_active_poll(self) -> PollRecord | None:
        """Get the currently active poll.

        Returns:
            The active poll record, or None.
        """
        return await self.storage.get_active_poll()

    def create_dnd_event(
        self,
        date: datetime,
        title: str = "D&D Session",
        duration_hours: int = 4,
        description: str | None = None,
    ) -> CalendarEvent:
        """Create a D&D session event object.

        Args:
            date: The date/time for the session.
            title: Event title.
            duration_hours: Session duration.
            description: Optional event description.

        Returns:
            CalendarEvent ready to be created on the calendar.
        """
        # Default to evening time if only date provided
        if date.hour == 0 and date.minute == 0:
            date = date.replace(hour=18, minute=0)  # 6 PM default

        return CalendarEvent(
            id="",  # Will be set by Google Calendar
            summary=title,
            start=date,
            end=date + timedelta(hours=duration_hours),
            status=EventStatus.BUSY,  # D&D sessions are always Busy
            description=description or "D&D session scheduled via FlumphBot",
        )


class VacationConfirmationView(discord.ui.View):
    """Discord UI view for vacation confirmation buttons."""

    def __init__(self, user_id: int, vacation_events: list[CalendarEvent]):
        """Initialize the view.

        Args:
            user_id: Discord user ID this confirmation is for.
            vacation_events: List of vacation events to confirm.
        """
        super().__init__(timeout=86400)  # 24 hours
        self.user_id = user_id
        self.vacation_events = vacation_events
        self.confirmed = False
        self.needs_update = False

    @discord.ui.button(label="Still accurate", style=discord.ButtonStyle.green)
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle confirmation button click."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This confirmation isn't for you!", ephemeral=True
            )
            return

        self.confirmed = True
        await interaction.response.edit_message(
            content="Thanks for confirming your vacation dates are still accurate!",
            view=None,
        )
        self.stop()

    @discord.ui.button(label="Need to update", style=discord.ButtonStyle.red)
    async def update_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle update needed button click."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This confirmation isn't for you!", ephemeral=True
            )
            return

        self.needs_update = True
        await interaction.response.edit_message(
            content="Please update your vacation dates on the shared calendar. "
            "The next poll will use the updated information.",
            view=None,
        )
        self.stop()
