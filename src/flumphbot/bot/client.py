"""Discord bot client for FlumphBot."""

import logging

import discord
from discord.ext import commands

from flumphbot.bot.commands import setup_commands
from flumphbot.bot.polls import PollManager
from flumphbot.calendar.event_analyzer import EventAnalyzer
from flumphbot.calendar.google_client import GoogleCalendarClient
from flumphbot.config import Config
from flumphbot.scheduler.runner import SchedulerRunner
from flumphbot.storage.base import StorageBackend
from flumphbot.storage.sqlite import SQLiteStorage

logger = logging.getLogger(__name__)


class FlumphBot(commands.Bot):
    """Discord bot for D&D session scheduling."""

    def __init__(self, config: Config):
        """Initialize the FlumphBot.

        Args:
            config: Bot configuration.
        """
        intents = discord.Intents.default()
        intents.message_content = True
        intents.polls = True

        super().__init__(
            command_prefix="!",  # Fallback, using slash commands
            intents=intents,
            help_command=None,
        )

        self.config = config
        self._storage: StorageBackend | None = None
        self._calendar_client: GoogleCalendarClient | None = None
        self._event_analyzer: EventAnalyzer | None = None
        self._poll_manager: PollManager | None = None
        self._scheduler: SchedulerRunner | None = None

    @property
    def storage(self) -> StorageBackend:
        """Get the storage backend."""
        if self._storage is None:
            if self.config.storage_backend == "azure":
                from flumphbot.storage.azure_tables import AzureTableStorage

                self._storage = AzureTableStorage(
                    self.config.azure_storage_connection_string or ""
                )
            else:
                self._storage = SQLiteStorage(self.config.database_path)
        return self._storage

    @property
    def calendar_client(self) -> GoogleCalendarClient:
        """Get the Google Calendar client."""
        if self._calendar_client is None:
            self._calendar_client = GoogleCalendarClient(self.config.google)
        return self._calendar_client

    @property
    def event_analyzer(self) -> EventAnalyzer:
        """Get the event analyzer."""
        if self._event_analyzer is None:
            self._event_analyzer = EventAnalyzer(
                dnd_session_keyword=self.config.dnd_session_keyword,
                personal_keywords=self.config.personal_keywords,
            )
        return self._event_analyzer

    @property
    def poll_manager(self) -> PollManager:
        """Get the poll manager."""
        if self._poll_manager is None:
            self._poll_manager = PollManager(self.storage)
        return self._poll_manager

    async def setup_hook(self) -> None:
        """Called when the bot is starting up."""
        logger.info("Setting up FlumphBot...")

        # Initialize storage
        await self.storage.initialize()

        # Set up slash commands
        setup_commands(self)

        # Sync commands to guild (faster for development)
        if self.config.discord.guild_id:
            guild = discord.Object(id=self.config.discord.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Synced commands to guild {self.config.discord.guild_id}")
        else:
            await self.tree.sync()
            logger.info("Synced commands globally")

        # Set up scheduler
        self._scheduler = SchedulerRunner(self)
        self._scheduler.start()

        logger.info("FlumphBot setup complete")

    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # Set activity
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="for D&D scheduling",
        )
        await self.change_presence(activity=activity)

    async def on_poll_vote_add(
        self, poll: discord.Poll, user: discord.User, answer: discord.PollAnswer
    ) -> None:
        """Handle poll vote additions."""
        # Check if this is one of our polls
        active_poll = await self.poll_manager.get_active_poll()
        if not active_poll:
            return

        # We could track individual votes here if needed
        logger.debug(f"Vote added by {user.name} for option {answer.id}")

    async def on_poll_vote_remove(
        self, poll: discord.Poll, user: discord.User, answer: discord.PollAnswer
    ) -> None:
        """Handle poll vote removals."""
        logger.debug(f"Vote removed by {user.name} for option {answer.id}")

    async def close(self) -> None:
        """Clean up when bot is shutting down."""
        logger.info("Shutting down FlumphBot...")

        if self._scheduler:
            self._scheduler.shutdown()

        if self._storage:
            await self._storage.close()

        await super().close()

    async def send_notification(
        self, message: str, channel_id: int | None = None
    ) -> discord.Message | None:
        """Send a notification to the configured channel.

        Args:
            message: The message to send.
            channel_id: Optional override channel ID.

        Returns:
            The sent message, or None if failed.
        """
        target_id = channel_id or self.config.discord.channel_id
        channel = self.get_channel(target_id)

        if isinstance(channel, discord.TextChannel):
            return await channel.send(message)
        else:
            logger.warning(f"Could not find channel {target_id}")
            return None

    async def send_dm(self, user_id: int, message: str) -> discord.Message | None:
        """Send a DM to a user.

        Args:
            user_id: Discord user ID.
            message: The message to send.

        Returns:
            The sent message, or None if failed.
        """
        try:
            user = await self.fetch_user(user_id)
            return await user.send(message)
        except discord.Forbidden:
            logger.warning(f"Cannot DM user {user_id} (DMs disabled)")
            return None
        except discord.NotFound:
            logger.warning(f"User {user_id} not found")
            return None
