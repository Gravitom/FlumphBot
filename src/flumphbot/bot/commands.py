"""Slash commands for FlumphBot."""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands

from flumphbot.bot.views import SettingsView, StatusView

if TYPE_CHECKING:
    from flumphbot.bot.client import FlumphBot

logger = logging.getLogger(__name__)

# Valid keyword categories
KeywordCategory = Literal["dnd", "away", "personal"]

# Day choices for schedule command
DAY_CHOICES = [
    app_commands.Choice(name="Monday", value="Monday"),
    app_commands.Choice(name="Tuesday", value="Tuesday"),
    app_commands.Choice(name="Wednesday", value="Wednesday"),
    app_commands.Choice(name="Thursday", value="Thursday"),
    app_commands.Choice(name="Friday", value="Friday"),
    app_commands.Choice(name="Saturday", value="Saturday"),
    app_commands.Choice(name="Sunday", value="Sunday"),
]

# On/Off choices
ON_OFF_CHOICES = [
    app_commands.Choice(name="on", value="on"),
    app_commands.Choice(name="off", value="off"),
]


class FlumphCommands(app_commands.Group):
    """Slash commands for D&D session management."""

    def __init__(self, bot: "FlumphBot"):
        """Initialize commands.

        Args:
            bot: The FlumphBot instance.
        """
        super().__init__(name="dnd", description="D&D session scheduling commands")
        self.bot = bot

    @app_commands.command(name="help", description="Show all FlumphBot commands")
    async def help(self, interaction: discord.Interaction) -> None:
        """Show all available commands and their descriptions."""
        embed = discord.Embed(
            title="FlumphBot Commands",
            description="Commands for managing D&D sessions and calendar events.",
            color=discord.Color.purple(),
        )

        embed.add_field(
            name="/dnd pollnow <start_day> <days_ahead>",
            value="Create a scheduling poll. start_day: days from today (0-14). "
            "days_ahead: number of days to include (1-14).",
            inline=False,
        )
        embed.add_field(
            name="/dnd showsettings",
            value="View current bot settings (schedule, notifications, etc.).",
            inline=False,
        )
        embed.add_field(
            name="/dnd allsettings",
            value="Interactive settings panel with buttons to edit all settings.",
            inline=False,
        )
        embed.add_field(
            name="/dnd schedule <day> <hour> <duration> <timezone>",
            value="Configure weekly auto-poll schedule.",
            inline=False,
        )
        embed.add_field(
            name="/dnd everyone <on|off>",
            value="Toggle @everyone tagging in poll posts.",
            inline=False,
        )
        embed.add_field(
            name="/dnd reminder <hours>",
            value="Configure session reminder DMs (0 = disabled).",
            inline=False,
        )
        embed.add_field(
            name="/dnd pollwarn <hours> <min_votes>",
            value="Configure poll close warnings (0 hours = disabled).",
            inline=False,
        )
        embed.add_field(
            name="/dnd status",
            value="Show upcoming sessions and vacations with quick actions.",
            inline=False,
        )
        embed.add_field(
            name="/dnd sync",
            value="Force calendar sync and fix Busy/Free issues.",
            inline=False,
        )
        embed.add_field(
            name="/dnd config",
            value="View environment-based configuration. (Admin only)",
            inline=False,
        )
        embed.add_field(
            name="/vacation add",
            value="Add a vacation entry to the calendar.",
            inline=False,
        )
        embed.add_field(
            name="/keywords",
            value="Manage detection keywords. Use `/keywords help` for details.",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pollnow", description="Create a scheduling poll with custom date range")
    @app_commands.describe(
        start_day="Days from today to start polling (0=today, 1=tomorrow, max 14)",
        days_ahead="Number of days to include in poll (1-14)",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def pollnow(
        self,
        interaction: discord.Interaction,
        start_day: app_commands.Range[int, 0, 14],
        days_ahead: app_commands.Range[int, 1, 14],
    ) -> None:
        """Create a scheduling poll with configurable date range."""
        await interaction.response.defer()

        try:
            # Check for existing active poll
            active_poll = await self.bot.poll_manager.get_active_poll()
            if active_poll:
                await interaction.followup.send(
                    "There's already an active poll. Please wait for it to close."
                )
                return

            # Calculate date range
            start_date = datetime.utcnow() + timedelta(days=start_day)
            end_date = start_date + timedelta(days=days_ahead)

            # Get events
            events = self.bot.calendar_client.get_events(
                start_date=start_date,
                end_date=end_date,
            )

            # Find available dates
            available = self.bot.event_analyzer.find_available_dates(
                events,
                start_date=start_date,
                days_ahead=days_ahead,
            )

            if not available:
                await interaction.followup.send(
                    f"No available dates found from {start_date.strftime('%B %d')} "
                    f"to {end_date.strftime('%B %d')}. Everyone seems to be busy!"
                )
                return

            # Get away events to display in poll context
            away_events = self.bot.event_analyzer.find_away_events(events)

            # Check tag_everyone setting
            tag_everyone_setting = await self.bot.storage.get_setting("tag_everyone")
            tag_everyone = tag_everyone_setting == "true"

            # Get poll duration from settings
            duration_setting = await self.bot.storage.get_setting("poll_duration_days")
            duration_hours = int(duration_setting or "2") * 24

            # Create poll
            channel = interaction.channel
            if isinstance(channel, discord.TextChannel):
                await self.bot.poll_manager.create_scheduling_poll(
                    channel,
                    available,
                    duration_hours=duration_hours,
                    away_events=away_events,
                    tag_everyone=tag_everyone,
                )
                await interaction.followup.send("Scheduling poll created!")
            else:
                await interaction.followup.send(
                    "Please use this command in a text channel."
                )
        except Exception as e:
            logger.exception("Error creating schedule poll")
            await interaction.followup.send(f"Error creating poll: {e}")

    @app_commands.command(name="showsettings", description="View current bot settings")
    async def showsettings(self, interaction: discord.Interaction) -> None:
        """Display all current settings."""
        config = self.bot.config.scheduler

        # Load settings from storage with config fallback
        schedule_day = await self.bot.storage.get_setting("schedule_day") or config.poll_day
        schedule_hour = await self.bot.storage.get_setting("schedule_hour") or config.poll_time.split(":")[0]
        schedule_timezone = await self.bot.storage.get_setting("schedule_timezone") or config.timezone
        poll_duration = await self.bot.storage.get_setting("poll_duration_days") or str(config.poll_duration_hours // 24)
        tag_everyone = await self.bot.storage.get_setting("tag_everyone") or "false"
        reminder_hours = await self.bot.storage.get_setting("reminder_hours") or "0"
        pollwarn_hours = await self.bot.storage.get_setting("pollwarn_hours") or "0"
        pollwarn_min_votes = await self.bot.storage.get_setting("pollwarn_min_votes") or "3"

        # Build embed
        embed = discord.Embed(
            title="FlumphBot Settings",
            color=discord.Color.blue(),
        )

        # Schedule section
        schedule_info = (
            f"Day: **{schedule_day}**\n"
            f"Time: **{schedule_hour}:00**\n"
            f"Timezone: **{schedule_timezone}**\n"
            f"Poll Duration: **{poll_duration} days**"
        )
        embed.add_field(
            name="Weekly Poll Schedule",
            value=schedule_info,
            inline=False,
        )

        # Notifications section
        everyone_status = "ON" if tag_everyone == "true" else "OFF"
        reminder_status = f"{reminder_hours} hours before" if int(reminder_hours) > 0 else "Disabled"
        pollwarn_status = (
            f"{pollwarn_hours} hours before (min {pollwarn_min_votes} votes)"
            if int(pollwarn_hours) > 0 else "Disabled"
        )

        notifications_info = (
            f"@everyone: **{everyone_status}**\n"
            f"Session Reminder: **{reminder_status}**\n"
            f"Poll Warning: **{pollwarn_status}**"
        )
        embed.add_field(
            name="Notifications",
            value=notifications_info,
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="allsettings", description="Interactive settings panel")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def allsettings(self, interaction: discord.Interaction) -> None:
        """Show interactive settings panel with buttons."""
        config = self.bot.config.scheduler

        # Load settings
        schedule_day = await self.bot.storage.get_setting("schedule_day") or config.poll_day
        schedule_hour = await self.bot.storage.get_setting("schedule_hour") or config.poll_time.split(":")[0]
        schedule_timezone = await self.bot.storage.get_setting("schedule_timezone") or config.timezone
        poll_duration = await self.bot.storage.get_setting("poll_duration_days") or str(config.poll_duration_hours // 24)
        tag_everyone = await self.bot.storage.get_setting("tag_everyone") or "false"
        reminder_hours = await self.bot.storage.get_setting("reminder_hours") or "0"
        pollwarn_hours = await self.bot.storage.get_setting("pollwarn_hours") or "0"
        pollwarn_min_votes = await self.bot.storage.get_setting("pollwarn_min_votes") or "3"

        # Build embed
        embed = discord.Embed(
            title="FlumphBot Settings",
            description="Use the buttons below to edit settings.",
            color=discord.Color.blue(),
        )

        # Schedule section
        embed.add_field(
            name="Weekly Poll Schedule",
            value=f"Day: {schedule_day} | Hour: {schedule_hour}:00 | Timezone: {schedule_timezone}\n"
                  f"Poll Duration: {poll_duration} days",
            inline=False,
        )

        # Notifications section
        everyone_status = "ON" if tag_everyone == "true" else "OFF"
        reminder_text = f"{reminder_hours}h before" if int(reminder_hours) > 0 else "Off"
        pollwarn_text = f"{pollwarn_hours}h before (min {pollwarn_min_votes})" if int(pollwarn_hours) > 0 else "Off"

        embed.add_field(
            name="Notifications",
            value=f"@everyone: {everyone_status} | Session Reminder: {reminder_text}\n"
                  f"Poll Warning: {pollwarn_text}",
            inline=False,
        )

        view = SettingsView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="schedule", description="Configure weekly auto-poll schedule")
    @app_commands.describe(
        day="Day of week for the weekly poll",
        hour="Hour in 24h format (0-23)",
        duration="Days the poll stays active (1-7)",
        timezone="Timezone (e.g., America/New_York)",
    )
    @app_commands.choices(day=DAY_CHOICES)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def schedule(
        self,
        interaction: discord.Interaction,
        day: app_commands.Choice[str],
        hour: app_commands.Range[int, 0, 23],
        duration: app_commands.Range[int, 1, 7],
        timezone: str,
    ) -> None:
        """Configure the weekly auto-poll schedule."""
        await interaction.response.defer()

        try:
            # Save settings
            await self.bot.storage.set_setting("schedule_day", day.value)
            await self.bot.storage.set_setting("schedule_hour", str(hour))
            await self.bot.storage.set_setting("poll_duration_days", str(duration))
            await self.bot.storage.set_setting("schedule_timezone", timezone)

            # Reload scheduler
            await self.bot.reload_scheduler()

            await interaction.followup.send(
                f"Schedule updated: **{day.value}** at **{hour:02d}:00 {timezone}**, "
                f"poll duration **{duration} days**. Changes applied immediately."
            )
        except Exception as e:
            logger.exception("Error updating schedule")
            await interaction.followup.send(f"Error updating schedule: {e}")

    @app_commands.command(name="everyone", description="Toggle @everyone tagging in poll posts")
    @app_commands.describe(enabled="Enable or disable @everyone tagging")
    @app_commands.choices(enabled=ON_OFF_CHOICES)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def everyone(
        self,
        interaction: discord.Interaction,
        enabled: app_commands.Choice[str],
    ) -> None:
        """Toggle @everyone tagging for polls."""
        value = "true" if enabled.value == "on" else "false"
        await self.bot.storage.set_setting("tag_everyone", value)

        status = "enabled" if value == "true" else "disabled"
        await interaction.response.send_message(f"@everyone tagging is now **{status}**.")

    @app_commands.command(name="reminder", description="Configure session reminder DMs")
    @app_commands.describe(hours="Hours before session to send reminder (0 = disabled)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def reminder(
        self,
        interaction: discord.Interaction,
        hours: app_commands.Range[int, 0, 48],
    ) -> None:
        """Configure session reminder DMs."""
        await self.bot.storage.set_setting("reminder_hours", str(hours))

        # Reload scheduler to update jobs
        await self.bot.reload_scheduler()

        if hours == 0:
            await interaction.response.send_message("Session reminders are now **disabled**.")
        else:
            await interaction.response.send_message(
                f"Session reminders will be sent **{hours} hours** before each session."
            )

    @app_commands.command(name="pollwarn", description="Configure poll close warnings")
    @app_commands.describe(
        hours="Hours before poll closes to warn (0 = disabled)",
        min_votes="Minimum votes to consider 'enough' (warning only triggers if below this)",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def pollwarn(
        self,
        interaction: discord.Interaction,
        hours: app_commands.Range[int, 0, 24],
        min_votes: app_commands.Range[int, 1, 10],
    ) -> None:
        """Configure poll close warnings."""
        await self.bot.storage.set_setting("pollwarn_hours", str(hours))
        await self.bot.storage.set_setting("pollwarn_min_votes", str(min_votes))

        # Reload scheduler to update jobs
        await self.bot.reload_scheduler()

        if hours == 0:
            await interaction.response.send_message("Poll close warnings are now **disabled**.")
        else:
            await interaction.response.send_message(
                f"Poll warning will be sent **{hours} hours** before close "
                f"if there are fewer than **{min_votes} votes**."
            )

    @app_commands.command(name="status", description="Show upcoming sessions and vacations")
    async def status(self, interaction: discord.Interaction) -> None:
        """Show upcoming sessions and vacations."""
        await interaction.response.defer()

        try:
            events = self.bot.calendar_client.get_events(
                end_date=datetime.utcnow() + timedelta(weeks=4)
            )

            # Categorize events
            sessions = []
            vacations = []

            for event in events:
                if self.bot.event_analyzer.is_dnd_session(event):
                    sessions.append(event)
                elif event.all_day or "vacation" in event.summary.lower():
                    vacations.append(event)

            # Build response
            embed = discord.Embed(
                title="D&D Schedule Status",
                color=discord.Color.blue(),
            )

            if sessions:
                session_text = "\n".join(
                    f"- {s.summary}: {s.start.strftime('%B %d, %Y')}"
                    for s in sessions[:5]
                )
                embed.add_field(
                    name="Upcoming Sessions",
                    value=session_text,
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Upcoming Sessions",
                    value="No sessions scheduled",
                    inline=False,
                )

            if vacations:
                vacation_text = "\n".join(
                    f"- {v.summary}: {v.start.strftime('%B %d')} - {v.end.strftime('%B %d')}"
                    for v in vacations[:5]
                )
                embed.add_field(
                    name="Upcoming Vacations",
                    value=vacation_text,
                    inline=False,
                )

            # Check for active poll
            active_poll = await self.bot.poll_manager.get_active_poll()
            if active_poll:
                embed.add_field(
                    name="Active Poll",
                    value=f"Closes: {active_poll.closes_at.strftime('%B %d at %I:%M %p')}",
                    inline=False,
                )

            # Add view with Create Poll Now button
            view = StatusView(self.bot)
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            logger.exception("Error getting status")
            await interaction.followup.send(f"Error getting status: {e}")

    @app_commands.command(name="sync", description="Force calendar sync and show issues")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def sync(self, interaction: discord.Interaction) -> None:
        """Force calendar sync and show any issues found."""
        await interaction.response.defer()

        try:
            events = self.bot.calendar_client.get_events()

            # Find issues
            needs_fix = self.bot.event_analyzer.find_events_needing_fix(events)
            personal = self.bot.event_analyzer.find_personal_events(events)

            embed = discord.Embed(
                title="Calendar Sync Results",
                color=discord.Color.green() if not needs_fix else discord.Color.orange(),
            )

            if needs_fix:
                fix_text = "\n".join(
                    f"- {e.summary}: should be Free"
                    for e in needs_fix[:5]
                )
                embed.add_field(
                    name=f"Events to Fix ({len(needs_fix)})",
                    value=fix_text,
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Busy/Free Status",
                    value="All events have correct status",
                    inline=False,
                )

            if personal:
                personal_text = "\n".join(
                    f"- {r.event.summary}: matched [{', '.join(r.matched_keywords)}]"
                    for r in personal[:5]
                )
                embed.add_field(
                    name=f"Potential Personal Events ({len(personal)})",
                    value=personal_text,
                    inline=False,
                )

            embed.set_footer(text=f"Checked {len(events)} events")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.exception("Error syncing calendar")
            await interaction.followup.send(f"Error syncing: {e}")

    @app_commands.command(name="config", description="View or update bot configuration")
    @app_commands.checks.has_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction) -> None:
        """View current configuration."""
        embed = discord.Embed(
            title="FlumphBot Configuration",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Poll Day",
            value=self.bot.config.scheduler.poll_day,
            inline=True,
        )
        embed.add_field(
            name="Poll Time",
            value=self.bot.config.scheduler.poll_time,
            inline=True,
        )
        embed.add_field(
            name="Poll Duration",
            value=f"{self.bot.config.scheduler.poll_duration_hours} hours",
            inline=True,
        )
        embed.add_field(
            name="Sync Interval",
            value=f"{self.bot.config.scheduler.sync_interval_minutes} minutes",
            inline=True,
        )
        embed.add_field(
            name="D&D Keyword",
            value=self.bot.config.dnd_session_keyword,
            inline=True,
        )
        embed.add_field(
            name="Storage Backend",
            value=self.bot.config.storage_backend,
            inline=True,
        )

        await interaction.response.send_message(embed=embed)


class VacationCommands(app_commands.Group):
    """Commands for managing vacation entries."""

    def __init__(self, bot: "FlumphBot"):
        """Initialize vacation commands.

        Args:
            bot: The FlumphBot instance.
        """
        super().__init__(name="vacation", description="Manage vacation entries")
        self.bot = bot

    @app_commands.command(name="add", description="Add a vacation to the calendar")
    @app_commands.describe(
        start="Start date (YYYY-MM-DD)",
        end="End date (YYYY-MM-DD)",
        title="Optional title for the vacation",
    )
    async def add(
        self,
        interaction: discord.Interaction,
        start: str,
        end: str,
        title: str = "Vacation",
    ) -> None:
        """Add a vacation entry to the calendar."""
        await interaction.response.defer()

        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")

            if end_date <= start_date:
                await interaction.followup.send(
                    "End date must be after start date."
                )
                return

            # Create calendar event
            from flumphbot.calendar.models import CalendarEvent, EventStatus

            event = CalendarEvent(
                id="",
                summary=f"{interaction.user.display_name} - {title}",
                start=start_date,
                end=end_date,
                status=EventStatus.FREE,  # Vacations should be Free
                all_day=True,
            )

            created = self.bot.calendar_client.create_event(event)
            await interaction.followup.send(
                f"Added vacation from {start} to {end}: {created.summary}"
            )
        except ValueError:
            await interaction.followup.send(
                "Invalid date format. Please use YYYY-MM-DD (e.g., 2024-03-15)"
            )
        except Exception as e:
            logger.exception("Error adding vacation")
            await interaction.followup.send(f"Error adding vacation: {e}")


class KeywordsCommands(app_commands.Group):
    """Commands for managing detection keywords."""

    def __init__(self, bot: "FlumphBot"):
        """Initialize keywords commands.

        Args:
            bot: The FlumphBot instance.
        """
        super().__init__(name="keywords", description="Manage detection keywords")
        self.bot = bot

    @app_commands.command(name="help", description="Explain keyword categories and usage")
    async def help(self, interaction: discord.Interaction) -> None:
        """Explain keyword categories and how they work."""
        embed = discord.Embed(
            title="Keyword Categories",
            description="Keywords determine how FlumphBot categorizes calendar events.",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🎲 D&D (`dnd`)",
            value="Events matching these keywords are treated as D&D sessions. "
            "They stay marked as **Busy** and block dates during scheduling polls.\n"
            "Default: D&D, DND, Dungeons, Campaign, Session",
            inline=False,
        )
        embed.add_field(
            name="🏖️ Away Time (`away`)",
            value="Events matching these keywords indicate player absences. "
            "They should be marked as **Free** (won't block shared calendars) "
            "and will be displayed in scheduling polls for context.\n"
            "Default: Away, Unavailable, Holiday, Vacation, Busy, PTO, etc.",
            inline=False,
        )
        embed.add_field(
            name="⚠️ Personal (`personal`)",
            value="Events matching these keywords might be accidentally personal. "
            "FlumphBot will DM the event creator to check if they meant to add it "
            "to the D&D calendar.\n"
            "Default: birthday, doctor, dentist, appointment, etc.",
            inline=False,
        )

        embed.add_field(
            name="Usage",
            value="```\n"
            "/keywords list                    - Show all keywords\n"
            "/keywords add <category> <word>   - Add a keyword\n"
            "/keywords remove <category> <word> - Remove a keyword\n"
            "```",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="list", description="Show all keywords by category")
    async def list(self, interaction: discord.Interaction) -> None:
        """Display all keywords organized by category."""
        await interaction.response.defer()

        try:
            # Get keywords from storage or defaults
            dnd_kw = await self.bot.storage.get_keywords("dnd") or self.bot.config.dnd_keywords
            away_kw = await self.bot.storage.get_keywords("away") or self.bot.config.away_keywords
            personal_kw = await self.bot.storage.get_keywords("personal") or self.bot.config.personal_keywords

            embed = discord.Embed(
                title="Detection Keywords",
                color=discord.Color.blue(),
            )

            embed.add_field(
                name="🎲 D&D Sessions",
                value=", ".join(f"`{kw}`" for kw in dnd_kw) or "None",
                inline=False,
            )
            embed.add_field(
                name="🏖️ Away Time",
                value=", ".join(f"`{kw}`" for kw in away_kw) or "None",
                inline=False,
            )
            embed.add_field(
                name="⚠️ Personal Events",
                value=", ".join(f"`{kw}`" for kw in personal_kw) or "None",
                inline=False,
            )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.exception("Error listing keywords")
            await interaction.followup.send(f"Error listing keywords: {e}")

    @app_commands.command(name="add", description="Add a keyword to a category")
    @app_commands.describe(
        category="The category to add the keyword to",
        keyword="The keyword to add",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def add(
        self,
        interaction: discord.Interaction,
        category: KeywordCategory,
        keyword: str,
    ) -> None:
        """Add a keyword to a category."""
        await interaction.response.defer()

        try:
            # Get current keywords
            if category == "dnd":
                keywords = await self.bot.storage.get_keywords("dnd") or list(self.bot.config.dnd_keywords)
            elif category == "away":
                keywords = await self.bot.storage.get_keywords("away") or list(self.bot.config.away_keywords)
            else:
                keywords = await self.bot.storage.get_keywords("personal") or list(self.bot.config.personal_keywords)

            # Check if already exists (case-insensitive)
            if any(kw.lower() == keyword.lower() for kw in keywords):
                await interaction.followup.send(f"Keyword `{keyword}` already exists in `{category}`.")
                return

            # Add and save
            keywords.append(keyword)
            await self.bot.storage.set_keywords(category, keywords)

            # Reload event analyzer
            await self.bot.reload_event_analyzer()

            await interaction.followup.send(f"Added `{keyword}` to `{category}` keywords.")
        except Exception as e:
            logger.exception("Error adding keyword")
            await interaction.followup.send(f"Error adding keyword: {e}")

    @app_commands.command(name="remove", description="Remove a keyword from a category")
    @app_commands.describe(
        category="The category to remove the keyword from",
        keyword="The keyword to remove",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def remove(
        self,
        interaction: discord.Interaction,
        category: KeywordCategory,
        keyword: str,
    ) -> None:
        """Remove a keyword from a category."""
        await interaction.response.defer()

        try:
            # Get current keywords
            if category == "dnd":
                keywords = await self.bot.storage.get_keywords("dnd") or list(self.bot.config.dnd_keywords)
            elif category == "away":
                keywords = await self.bot.storage.get_keywords("away") or list(self.bot.config.away_keywords)
            else:
                keywords = await self.bot.storage.get_keywords("personal") or list(self.bot.config.personal_keywords)

            # Find and remove (case-insensitive)
            original_len = len(keywords)
            keywords = [kw for kw in keywords if kw.lower() != keyword.lower()]

            if len(keywords) == original_len:
                await interaction.followup.send(f"Keyword `{keyword}` not found in `{category}`.")
                return

            # Save
            await self.bot.storage.set_keywords(category, keywords)

            # Reload event analyzer
            await self.bot.reload_event_analyzer()

            await interaction.followup.send(f"Removed `{keyword}` from `{category}` keywords.")
        except Exception as e:
            logger.exception("Error removing keyword")
            await interaction.followup.send(f"Error removing keyword: {e}")


def setup_commands(bot: "FlumphBot") -> None:
    """Set up all slash commands for the bot.

    Args:
        bot: The FlumphBot instance.
    """
    bot.tree.add_command(FlumphCommands(bot))
    bot.tree.add_command(VacationCommands(bot))
    bot.tree.add_command(KeywordsCommands(bot))
