"""Slash commands for FlumphBot."""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands

if TYPE_CHECKING:
    from flumphbot.bot.client import FlumphBot

logger = logging.getLogger(__name__)

# Valid keyword categories
KeywordCategory = Literal["dnd", "away", "personal"]


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
            name="/dnd schedule",
            value="Manually trigger a scheduling poll for D&D sessions. "
            "Checks calendar availability and creates a poll with available dates.",
            inline=False,
        )
        embed.add_field(
            name="/dnd status",
            value="Show upcoming D&D sessions and player absences. "
            "Displays the next 4 weeks of scheduled events.",
            inline=False,
        )
        embed.add_field(
            name="/dnd sync",
            value="Force calendar sync and fix any Busy/Free issues. "
            "Shows events that were corrected and potential personal events.",
            inline=False,
        )
        embed.add_field(
            name="/dnd config",
            value="View current bot configuration settings. (Admin only)",
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

    @app_commands.command(name="schedule", description="Manually trigger a scheduling poll")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def schedule(self, interaction: discord.Interaction) -> None:
        """Manually trigger a scheduling poll."""
        await interaction.response.defer()

        try:
            # Check for existing active poll
            active_poll = await self.bot.poll_manager.get_active_poll()
            if active_poll:
                await interaction.followup.send(
                    "There's already an active poll. Please wait for it to close."
                )
                return

            # Get available dates
            events = self.bot.calendar_client.get_events()
            available = self.bot.event_analyzer.find_available_dates(
                events,
                start_date=datetime.utcnow(),
                days_ahead=14,
            )

            if not available:
                await interaction.followup.send(
                    "No available dates found in the next 2 weeks. "
                    "Everyone seems to be busy!"
                )
                return

            # Get away events to display in poll context
            away_events = self.bot.event_analyzer.find_away_events(events)

            # Create poll
            channel = interaction.channel
            if isinstance(channel, discord.TextChannel):
                await self.bot.poll_manager.create_scheduling_poll(
                    channel,
                    available,
                    duration_hours=self.bot.config.scheduler.poll_duration_hours,
                    away_events=away_events,
                )
                await interaction.followup.send("Scheduling poll created!")
            else:
                await interaction.followup.send(
                    "Please use this command in a text channel."
                )
        except Exception as e:
            logger.exception("Error creating schedule poll")
            await interaction.followup.send(f"Error creating poll: {e}")

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

            await interaction.followup.send(embed=embed)
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
