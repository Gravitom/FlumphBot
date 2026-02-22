"""Scheduled task definitions for FlumphBot."""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from flumphbot.bot.polls import VacationConfirmationView
from flumphbot.calendar.event_analyzer import EventCategory
from flumphbot.calendar.models import EventStatus

if TYPE_CHECKING:
    from flumphbot.bot.client import FlumphBot

logger = logging.getLogger(__name__)


class ScheduledTasks:
    """Collection of scheduled tasks for FlumphBot."""

    def __init__(self, bot: "FlumphBot"):
        """Initialize scheduled tasks.

        Args:
            bot: The FlumphBot instance.
        """
        self.bot = bot

    async def post_weekly_poll(self) -> None:
        """Post the weekly scheduling poll.

        This task runs on the configured day/time (e.g., Monday 9 AM).
        It checks calendar availability and posts a poll for available dates.
        """
        logger.info("Running weekly poll task")

        try:
            # Check for active poll
            active_poll = await self.bot.poll_manager.get_active_poll()
            if active_poll:
                logger.info("Active poll already exists, skipping")
                return

            # Get events for the next 2 weeks
            events = self.bot.calendar_client.get_events(
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(weeks=2),
            )

            # Find available dates
            available = self.bot.event_analyzer.find_available_dates(
                events,
                start_date=datetime.utcnow(),
                days_ahead=14,
            )

            if not available:
                await self.bot.send_notification(
                    "No available dates found for the next 2 weeks. "
                    "Everyone seems to be busy!"
                )
                return

            # Get away events to display in poll context
            away_events = self.bot.event_analyzer.find_away_events(events)

            # Get the notification channel
            channel = self.bot.get_channel(self.bot.config.discord.channel_id)
            if not channel:
                logger.error("Could not find notification channel")
                return

            # Create the poll
            import discord
            if isinstance(channel, discord.TextChannel):
                await self.bot.poll_manager.create_scheduling_poll(
                    channel,
                    available,
                    duration_hours=self.bot.config.scheduler.poll_duration_hours,
                    away_events=away_events,
                )
                logger.info("Weekly poll created successfully")

        except Exception:
            logger.exception("Error in weekly poll task")

    async def sync_calendar_hygiene(self) -> None:
        """Sync calendar and fix busy/free status.

        This task runs every 15-30 minutes to:
        1. Find events incorrectly marked as Busy
        2. Fix them to be Free
        3. Post notifications about fixes (especially for Away Time events)
        4. Detect personal events and alert users
        """
        logger.info("Running calendar hygiene sync")

        try:
            events = self.bot.calendar_client.get_events()

            # Find events needing status fix
            needs_fix = self.bot.event_analyzer.find_events_needing_fix(events)

            for event in needs_fix:
                try:
                    # Fix the status
                    self.bot.calendar_client.update_event_status(
                        event.id, EventStatus.FREE
                    )

                    # Determine event category for notification
                    category = self.bot.event_analyzer.get_category(event)

                    if category == EventCategory.AWAY:
                        # Special notification for Away Time events
                        creator_name = event.creator_email or "Someone"
                        if event.creator_email:
                            mapping = await self._find_user_by_email(event.creator_email)
                            if mapping:
                                creator_name = mapping.discord_name

                        await self.bot.send_notification(
                            f"**{creator_name}** - You created an Away Time item "
                            f"(\"{event.summary}\") in the shared D&D calendar that was "
                            f"set to Busy. I automatically changed it to Free to not "
                            f"interfere with shared free/busy schedules."
                        )
                    else:
                        # Generic fix notification
                        await self.bot.send_notification(
                            f"Fixed '{event.summary}' to 'Free' status "
                            f"(was incorrectly marked as 'Busy')"
                        )

                    logger.info(f"Fixed event {event.summary} to Free")

                except Exception:
                    logger.exception(f"Error fixing event {event.id}")

            # Find personal events
            personal = self.bot.event_analyzer.find_personal_events(events)

            for result in personal:
                # Try to find the creator's Discord ID
                if result.event.creator_email:
                    mapping = await self._find_user_by_email(result.event.creator_email)
                    if mapping:
                        await self._alert_personal_event(
                            mapping.discord_id,
                            result.event,
                            result.matched_keywords,
                        )

            logger.info(
                f"Calendar sync complete: fixed {len(needs_fix)}, "
                f"found {len(personal)} personal events"
            )

        except Exception:
            logger.exception("Error in calendar hygiene sync")

    async def check_poll_completion(self) -> None:
        """Check if active poll has completed and process results.

        This task runs frequently to detect when polls close and
        create the winning D&D session event.
        """
        logger.info("Checking poll completion")

        try:
            active_poll = await self.bot.poll_manager.get_active_poll()
            if not active_poll:
                return

            # Check if poll should be closed
            if datetime.utcnow() < active_poll.closes_at:
                return

            # Get the poll message
            channel = self.bot.get_channel(active_poll.channel_id)
            if not channel:
                return

            import discord
            if isinstance(channel, discord.TextChannel):
                try:
                    message = await channel.fetch_message(active_poll.message_id)
                except discord.NotFound:
                    logger.error(f"Poll message {active_poll.message_id} not found")
                    return

                # Close poll and get winner
                winning_date = await self.bot.poll_manager.close_poll_and_get_winner(
                    active_poll, message
                )

                if winning_date:
                    # Create D&D session event
                    event = self.bot.poll_manager.create_dnd_event(winning_date)
                    created = self.bot.calendar_client.create_event(event)

                    # Update poll record with event ID
                    active_poll.created_event_id = created.id
                    await self.bot.storage.update_poll(active_poll)

                    # Announce
                    await self.bot.send_notification(
                        f"D&D session scheduled for {winning_date.strftime('%A, %B %d')}!"
                    )
                    logger.info(f"Created D&D session event for {winning_date}")
                else:
                    await self.bot.send_notification(
                        "Poll closed but no votes were cast. No session scheduled."
                    )

        except Exception:
            logger.exception("Error checking poll completion")

    async def confirm_vacations(self) -> None:
        """Send vacation confirmation requests to users.

        This task runs weekly (before posting the poll) to ask users
        to confirm their upcoming vacation dates are still accurate.
        """
        logger.info("Running vacation confirmation")

        try:
            events = self.bot.calendar_client.get_events(
                end_date=datetime.utcnow() + timedelta(weeks=4)
            )

            vacations = self.bot.event_analyzer.find_vacation_events(events)

            # Group vacations by creator
            by_creator: dict = {}
            for vacation in vacations:
                email = vacation.creator_email
                if email:
                    if email not in by_creator:
                        by_creator[email] = []
                    by_creator[email].append(vacation)

            # Send confirmation requests
            for email, user_vacations in by_creator.items():
                mapping = await self._find_user_by_email(email)
                if mapping:
                    await self._send_vacation_confirmation(
                        mapping.discord_id, user_vacations
                    )

            logger.info(f"Sent vacation confirmations to {len(by_creator)} users")

        except Exception:
            logger.exception("Error in vacation confirmation")

    async def _find_user_by_email(self, email: str):
        """Find user mapping by calendar email."""
        mappings = await self.bot.storage.get_all_user_mappings()
        for mapping in mappings:
            if mapping.calendar_email.lower() == email.lower():
                return mapping
        return None

    async def _alert_personal_event(
        self, discord_id: int, event, keywords: list[str]
    ) -> None:
        """Send personal event alert to a user."""
        keyword_str = ", ".join(keywords)
        message = (
            f"Hey! Looks like '{event.summary}' might be personal. "
            f"(Detected keywords: {keyword_str})\n\n"
            f"Did you mean to add this to the D&D calendar?"
        )
        await self.bot.send_dm(discord_id, message)

    async def _send_vacation_confirmation(
        self, discord_id: int, vacations: list
    ) -> None:
        """Send vacation confirmation request to a user."""
        vacation_list = "\n".join(
            f"- {v.summary}: {v.start.strftime('%B %d')} - {v.end.strftime('%B %d')}"
            for v in vacations
        )

        message = (
            f"You have the following upcoming vacations on the D&D calendar:\n\n"
            f"{vacation_list}\n\n"
            f"Are these dates still accurate?"
        )

        try:
            user = await self.bot.fetch_user(discord_id)
            view = VacationConfirmationView(discord_id, vacations)
            await user.send(message, view=view)
        except Exception:
            logger.exception(f"Error sending vacation confirmation to {discord_id}")
