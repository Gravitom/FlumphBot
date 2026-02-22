"""Discord UI Views for FlumphBot settings and interactions."""

import logging
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from flumphbot.bot.client import FlumphBot

logger = logging.getLogger(__name__)


def get_day_options(selected: str | None = None) -> list[discord.SelectOption]:
    """Get day of week options with optional default selection."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return [
        discord.SelectOption(label=day, value=day, default=(day == selected))
        for day in days
    ]


def get_timezone_options(selected: str | None = None) -> list[discord.SelectOption]:
    """Get timezone options (15 most common) with optional default selection."""
    timezones = [
        ("US/Eastern", "US/Eastern (New York)"),
        ("US/Central", "US/Central (Chicago)"),
        ("US/Mountain", "US/Mountain (Denver)"),
        ("US/Pacific", "US/Pacific (Los Angeles)"),
        ("America/New_York", "America/New_York"),
        ("America/Chicago", "America/Chicago"),
        ("America/Denver", "America/Denver"),
        ("America/Los_Angeles", "America/Los_Angeles"),
        ("America/Phoenix", "America/Phoenix (Arizona)"),
        ("UTC", "UTC"),
        ("Europe/London", "Europe/London"),
        ("Europe/Paris", "Europe/Paris"),
        ("Europe/Berlin", "Europe/Berlin"),
        ("Asia/Tokyo", "Asia/Tokyo"),
        ("Australia/Sydney", "Australia/Sydney"),
    ]
    return [
        discord.SelectOption(label=label, value=value, default=(value == selected))
        for value, label in timezones
    ]


class ScheduleModal(discord.ui.Modal, title="Edit Poll Schedule"):
    """Modal for editing schedule settings."""

    hour = discord.ui.TextInput(
        label="Hour (0-23)",
        placeholder="e.g., 14 for 2:00 PM",
        min_length=1,
        max_length=2,
        required=True,
    )

    duration = discord.ui.TextInput(
        label="Poll Duration (days)",
        placeholder="e.g., 2",
        min_length=1,
        max_length=1,
        required=True,
    )

    def __init__(self, bot: "FlumphBot", current_hour: str, current_duration: str):
        super().__init__()
        self.bot = bot
        self.hour.default = current_hour
        self.duration.default = current_duration

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle modal submission."""
        try:
            hour_val = int(self.hour.value)
            duration_val = int(self.duration.value)

            if not (0 <= hour_val <= 23):
                await interaction.response.send_message(
                    "Hour must be between 0 and 23.", ephemeral=True
                )
                return

            if not (1 <= duration_val <= 7):
                await interaction.response.send_message(
                    "Duration must be between 1 and 7 days.", ephemeral=True
                )
                return

            # Save settings
            await self.bot.storage.set_setting("schedule_hour", str(hour_val))
            await self.bot.storage.set_setting("poll_duration_days", str(duration_val))

            # Reload scheduler
            await self.bot.reload_scheduler()

            await interaction.response.send_message(
                f"Updated schedule: Hour={hour_val:02d}:00, Duration={duration_val} days",
                ephemeral=True,
            )

        except ValueError:
            await interaction.response.send_message(
                "Invalid input. Please enter valid numbers.", ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle modal errors."""
        logger.exception("Error in ScheduleModal")
        await interaction.response.send_message(
            f"An error occurred: {error}", ephemeral=True
        )


class ReminderModal(discord.ui.Modal, title="Edit Reminder Settings"):
    """Modal for editing reminder and warning settings."""

    reminder_hours = discord.ui.TextInput(
        label="Session Reminder (hours before, 0=off)",
        placeholder="e.g., 2",
        min_length=1,
        max_length=2,
        required=True,
    )

    pollwarn_hours = discord.ui.TextInput(
        label="Poll Warning (hours before close, 0=off)",
        placeholder="e.g., 4",
        min_length=1,
        max_length=2,
        required=True,
    )

    pollwarn_min_votes = discord.ui.TextInput(
        label="Min Votes for Warning",
        placeholder="e.g., 3",
        min_length=1,
        max_length=2,
        required=True,
    )

    def __init__(
        self,
        bot: "FlumphBot",
        current_reminder: str,
        current_pollwarn: str,
        current_min_votes: str,
    ):
        super().__init__()
        self.bot = bot
        self.reminder_hours.default = current_reminder
        self.pollwarn_hours.default = current_pollwarn
        self.pollwarn_min_votes.default = current_min_votes

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle modal submission."""
        try:
            reminder_val = int(self.reminder_hours.value)
            pollwarn_val = int(self.pollwarn_hours.value)
            min_votes_val = int(self.pollwarn_min_votes.value)

            if not (0 <= reminder_val <= 48):
                await interaction.response.send_message(
                    "Reminder hours must be between 0 and 48.", ephemeral=True
                )
                return

            if not (0 <= pollwarn_val <= 24):
                await interaction.response.send_message(
                    "Poll warning hours must be between 0 and 24.", ephemeral=True
                )
                return

            if not (1 <= min_votes_val <= 10):
                await interaction.response.send_message(
                    "Min votes must be between 1 and 10.", ephemeral=True
                )
                return

            # Save settings
            await self.bot.storage.set_setting("reminder_hours", str(reminder_val))
            await self.bot.storage.set_setting("pollwarn_hours", str(pollwarn_val))
            await self.bot.storage.set_setting("pollwarn_min_votes", str(min_votes_val))

            # Reload scheduler
            await self.bot.reload_scheduler()

            await interaction.response.send_message(
                f"Updated reminders: Session={reminder_val}h, "
                f"Poll Warning={pollwarn_val}h (min {min_votes_val} votes)",
                ephemeral=True,
            )

        except ValueError:
            await interaction.response.send_message(
                "Invalid input. Please enter valid numbers.", ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle modal errors."""
        logger.exception("Error in ReminderModal")
        await interaction.response.send_message(
            f"An error occurred: {error}", ephemeral=True
        )


class ScheduleSelectView(discord.ui.View):
    """View with dropdowns for selecting schedule day and timezone."""

    def __init__(self, bot: "FlumphBot", current_day: str, current_timezone: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.selected_day = current_day
        self.selected_timezone = current_timezone

        # Add selects with fresh options (not shared)
        day_select = discord.ui.Select(
            placeholder="Select day of week",
            options=get_day_options(current_day),
            row=0,
        )
        day_select.callback = self.day_select_callback
        self.add_item(day_select)

        tz_select = discord.ui.Select(
            placeholder="Select timezone",
            options=get_timezone_options(current_timezone),
            row=1,
        )
        tz_select.callback = self.timezone_select_callback
        self.add_item(tz_select)

    async def day_select_callback(self, interaction: discord.Interaction) -> None:
        """Handle day selection."""
        self.selected_day = interaction.data["values"][0]
        await interaction.response.defer()

    async def timezone_select_callback(self, interaction: discord.Interaction) -> None:
        """Handle timezone selection."""
        self.selected_timezone = interaction.data["values"][0]
        await interaction.response.defer()

    @discord.ui.button(label="Save", style=discord.ButtonStyle.green, row=2)
    async def save_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Save the selected values."""
        try:
            await self.bot.storage.set_setting("schedule_day", self.selected_day)
            await self.bot.storage.set_setting("schedule_timezone", self.selected_timezone)

            # Reload scheduler
            await self.bot.reload_scheduler()

            await interaction.response.send_message(
                f"Saved: Day={self.selected_day}, Timezone={self.selected_timezone}",
                ephemeral=True,
            )
            self.stop()
        except Exception as e:
            logger.exception("Error saving schedule")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=2)
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Cancel without saving."""
        await interaction.response.send_message("Cancelled.", ephemeral=True)
        self.stop()


class PollNowModal(discord.ui.Modal, title="Create Poll Now"):
    """Modal for creating a poll with custom date range."""

    start_day = discord.ui.TextInput(
        label="Start Day (0=today, 1=tomorrow, etc.)",
        placeholder="e.g., 1",
        min_length=1,
        max_length=2,
        required=True,
        default="1",
    )

    days_ahead = discord.ui.TextInput(
        label="Days to Include (1-14)",
        placeholder="e.g., 14",
        min_length=1,
        max_length=2,
        required=True,
        default="14",
    )

    def __init__(self, bot: "FlumphBot", channel: discord.TextChannel):
        super().__init__()
        self.bot = bot
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle modal submission."""
        from datetime import datetime, timedelta

        try:
            start_val = int(self.start_day.value)
            days_val = int(self.days_ahead.value)

            if not (0 <= start_val <= 14):
                await interaction.response.send_message(
                    "Start day must be between 0 and 14.", ephemeral=True
                )
                return

            if not (1 <= days_val <= 14):
                await interaction.response.send_message(
                    "Days ahead must be between 1 and 14.", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Check for existing active poll
            active_poll = await self.bot.poll_manager.get_active_poll()
            if active_poll:
                await interaction.followup.send(
                    "There's already an active poll. Please wait for it to close.",
                    ephemeral=True,
                )
                return

            # Calculate date range
            start_date = datetime.utcnow() + timedelta(days=start_val)
            end_date = start_date + timedelta(days=days_val)

            # Get events
            events = self.bot.calendar_client.get_events(
                start_date=start_date,
                end_date=end_date,
            )

            # Find available dates
            available = self.bot.event_analyzer.find_available_dates(
                events,
                start_date=start_date,
                days_ahead=days_val,
            )

            if not available:
                await interaction.followup.send(
                    "No available dates found in the specified range.",
                    ephemeral=True,
                )
                return

            # Get away events
            away_events = self.bot.event_analyzer.find_away_events(events)

            # Check tag_everyone setting
            tag_everyone = await self.bot.storage.get_setting("tag_everyone")
            tag_everyone = tag_everyone == "true" if tag_everyone else False

            # Get poll duration
            duration_setting = await self.bot.storage.get_setting("poll_duration_days")
            duration_hours = int(duration_setting or "2") * 24

            # Create poll
            await self.bot.poll_manager.create_scheduling_poll(
                self.channel,
                available,
                duration_hours=duration_hours,
                away_events=away_events,
                tag_everyone=tag_everyone,
            )

            await interaction.followup.send("Scheduling poll created!", ephemeral=True)

        except ValueError:
            await interaction.response.send_message(
                "Invalid input. Please enter valid numbers.", ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle modal errors."""
        logger.exception("Error in PollNowModal")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"An error occurred: {error}", ephemeral=True
            )
        else:
            await interaction.followup.send(f"An error occurred: {error}", ephemeral=True)


class SettingsView(discord.ui.View):
    """Main settings panel with buttons for each category."""

    def __init__(self, bot: "FlumphBot"):
        super().__init__(timeout=300)
        self.bot = bot

    async def _get_settings(self) -> dict:
        """Load all settings from storage with defaults."""
        config = self.bot.config.scheduler

        schedule_day = await self.bot.storage.get_setting("schedule_day") or config.poll_day
        schedule_hour = await self.bot.storage.get_setting("schedule_hour") or config.poll_time.split(":")[0]
        schedule_timezone = await self.bot.storage.get_setting("schedule_timezone") or config.timezone
        poll_duration = await self.bot.storage.get_setting("poll_duration_days") or str(config.poll_duration_hours // 24)
        tag_everyone = await self.bot.storage.get_setting("tag_everyone") or "false"
        reminder_hours = await self.bot.storage.get_setting("reminder_hours") or "0"
        pollwarn_hours = await self.bot.storage.get_setting("pollwarn_hours") or "0"
        pollwarn_min_votes = await self.bot.storage.get_setting("pollwarn_min_votes") or "3"

        return {
            "schedule_day": schedule_day,
            "schedule_hour": schedule_hour,
            "schedule_timezone": schedule_timezone,
            "poll_duration_days": poll_duration,
            "tag_everyone": tag_everyone == "true",
            "reminder_hours": reminder_hours,
            "pollwarn_hours": pollwarn_hours,
            "pollwarn_min_votes": pollwarn_min_votes,
        }

    @discord.ui.button(label="Edit Schedule", style=discord.ButtonStyle.primary, row=0)
    async def edit_schedule_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Open schedule configuration."""
        try:
            settings = await self._get_settings()
            view = ScheduleSelectView(
                self.bot,
                settings["schedule_day"],
                settings["schedule_timezone"],
            )
            await interaction.response.send_message(
                "Select schedule day and timezone:",
                view=view,
                ephemeral=True,
            )
        except Exception as e:
            logger.exception("Error in edit_schedule_button")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Edit Time/Duration", style=discord.ButtonStyle.primary, row=0)
    async def edit_time_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Open time/duration modal."""
        try:
            settings = await self._get_settings()
            modal = ScheduleModal(
                self.bot,
                settings["schedule_hour"],
                settings["poll_duration_days"],
            )
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.exception("Error in edit_time_button")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Toggle @everyone", style=discord.ButtonStyle.secondary, row=1)
    async def toggle_everyone_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Toggle @everyone setting."""
        try:
            current = await self.bot.storage.get_setting("tag_everyone")
            new_value = "false" if current == "true" else "true"
            await self.bot.storage.set_setting("tag_everyone", new_value)

            status = "ON" if new_value == "true" else "OFF"
            await interaction.response.send_message(
                f"@everyone tagging is now **{status}**",
                ephemeral=True,
            )
        except Exception as e:
            logger.exception("Error in toggle_everyone_button")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Edit Reminders", style=discord.ButtonStyle.secondary, row=1)
    async def edit_reminders_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Open reminders modal."""
        try:
            settings = await self._get_settings()
            modal = ReminderModal(
                self.bot,
                settings["reminder_hours"],
                settings["pollwarn_hours"],
                settings["pollwarn_min_votes"],
            )
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.exception("Error in edit_reminders_button")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Create Poll Now", style=discord.ButtonStyle.success, row=2)
    async def create_poll_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Open poll creation modal."""
        try:
            if not isinstance(interaction.channel, discord.TextChannel):
                await interaction.response.send_message(
                    "Please use this in a text channel.", ephemeral=True
                )
                return

            modal = PollNowModal(self.bot, interaction.channel)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.exception("Error in create_poll_button")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)


class StatusView(discord.ui.View):
    """View for status display with Create Poll Now button."""

    def __init__(self, bot: "FlumphBot"):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label="Create Poll Now", style=discord.ButtonStyle.primary)
    async def create_poll_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Open poll creation modal."""
        try:
            if not isinstance(interaction.channel, discord.TextChannel):
                await interaction.response.send_message(
                    "Please use this in a text channel.", ephemeral=True
                )
                return

            modal = PollNowModal(self.bot, interaction.channel)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.exception("Error in create_poll_button")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
