"""Azure Table Storage backend for cloud deployments."""

import contextlib
import logging
from datetime import datetime

from flumphbot.storage.base import (
    PollOption,
    PollRecord,
    StorageBackend,
    UserMapping,
)

logger = logging.getLogger(__name__)

try:
    from azure.core.exceptions import ResourceNotFoundError
    from azure.data.tables import TableServiceClient

    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    logger.warning(
        "azure-data-tables not installed. Install with: pip install azure-data-tables"
    )


class AzureTableStorage(StorageBackend):
    """Azure Table Storage backend."""

    def __init__(self, connection_string: str):
        """Initialize the Azure Table Storage.

        Args:
            connection_string: Azure Storage connection string.
        """
        if not AZURE_AVAILABLE:
            raise ImportError(
                "azure-data-tables is required for Azure storage. "
                "Install with: pip install azure-data-tables"
            )

        self.connection_string = connection_string
        self._service_client: TableServiceClient | None = None
        self._tables: dict = {}

    def _get_service(self) -> TableServiceClient:
        """Get or create the table service client."""
        if self._service_client is None:
            self._service_client = TableServiceClient.from_connection_string(
                self.connection_string
            )
        return self._service_client

    def _get_table(self, table_name: str):
        """Get or create a table client."""
        if table_name not in self._tables:
            service = self._get_service()
            self._tables[table_name] = service.get_table_client(table_name)
        return self._tables[table_name]

    async def initialize(self) -> None:
        """Create tables if they don't exist."""
        service = self._get_service()

        table_names = ["usermappings", "polls", "polloptions", "settings"]
        for table_name in table_names:
            try:
                service.create_table(table_name)
                logger.info(f"Created table: {table_name}")
            except Exception:
                # Table likely already exists
                pass

        logger.info("Azure Table Storage initialized")

    async def close(self) -> None:
        """Close the storage connection."""
        if self._service_client:
            self._service_client.close()
            self._service_client = None
            self._tables.clear()

    # User mappings
    async def get_user_mapping(self, discord_id: int) -> UserMapping | None:
        """Get a user mapping by Discord ID."""
        table = self._get_table("usermappings")
        try:
            entity = table.get_entity("users", str(discord_id))
            return UserMapping(
                discord_id=int(entity["RowKey"]),
                discord_name=entity["discord_name"],
                calendar_email=entity["calendar_email"],
                created_at=datetime.fromisoformat(entity["created_at"]),
            )
        except ResourceNotFoundError:
            return None

    async def set_user_mapping(self, mapping: UserMapping) -> None:
        """Create or update a user mapping."""
        table = self._get_table("usermappings")
        entity = {
            "PartitionKey": "users",
            "RowKey": str(mapping.discord_id),
            "discord_name": mapping.discord_name,
            "calendar_email": mapping.calendar_email,
            "created_at": mapping.created_at.isoformat(),
        }
        table.upsert_entity(entity)

    async def get_all_user_mappings(self) -> list[UserMapping]:
        """Get all user mappings."""
        table = self._get_table("usermappings")
        entities = table.query_entities("PartitionKey eq 'users'")
        return [
            UserMapping(
                discord_id=int(e["RowKey"]),
                discord_name=e["discord_name"],
                calendar_email=e["calendar_email"],
                created_at=datetime.fromisoformat(e["created_at"]),
            )
            for e in entities
        ]

    async def delete_user_mapping(self, discord_id: int) -> None:
        """Delete a user mapping."""
        table = self._get_table("usermappings")
        with contextlib.suppress(ResourceNotFoundError):
            table.delete_entity("users", str(discord_id))

    # Poll management
    async def create_poll(self, poll: PollRecord, options: list[PollOption]) -> None:
        """Create a new poll with its options."""
        polls_table = self._get_table("polls")
        options_table = self._get_table("polloptions")

        poll_entity = {
            "PartitionKey": "polls",
            "RowKey": poll.id,
            "message_id": poll.message_id,
            "channel_id": poll.channel_id,
            "created_at": poll.created_at.isoformat(),
            "closes_at": poll.closes_at.isoformat(),
            "closed": poll.closed,
            "winning_date": poll.winning_date.isoformat() if poll.winning_date else "",
            "created_event_id": poll.created_event_id or "",
        }
        polls_table.upsert_entity(poll_entity)

        for option in options:
            option_entity = {
                "PartitionKey": poll.id,
                "RowKey": option.date.isoformat(),
                "vote_count": option.vote_count,
            }
            options_table.upsert_entity(option_entity)

    async def get_poll(self, poll_id: str) -> PollRecord | None:
        """Get a poll by ID."""
        table = self._get_table("polls")
        try:
            entity = table.get_entity("polls", poll_id)
            return self._entity_to_poll(entity)
        except ResourceNotFoundError:
            return None

    async def get_active_poll(self) -> PollRecord | None:
        """Get the currently active (not closed) poll."""
        table = self._get_table("polls")
        entities = table.query_entities(
            "PartitionKey eq 'polls' and closed eq false"
        )
        polls = [self._entity_to_poll(e) for e in entities]
        if polls:
            # Return the most recent
            return max(polls, key=lambda p: p.created_at)
        return None

    async def get_poll_options(self, poll_id: str) -> list[PollOption]:
        """Get all options for a poll."""
        table = self._get_table("polloptions")
        entities = table.query_entities(f"PartitionKey eq '{poll_id}'")
        return [
            PollOption(
                poll_id=poll_id,
                date=datetime.fromisoformat(e["RowKey"]),
                vote_count=e["vote_count"],
            )
            for e in entities
        ]

    async def update_poll(self, poll: PollRecord) -> None:
        """Update a poll record."""
        table = self._get_table("polls")
        entity = {
            "PartitionKey": "polls",
            "RowKey": poll.id,
            "message_id": poll.message_id,
            "channel_id": poll.channel_id,
            "created_at": poll.created_at.isoformat(),
            "closes_at": poll.closes_at.isoformat(),
            "closed": poll.closed,
            "winning_date": poll.winning_date.isoformat() if poll.winning_date else "",
            "created_event_id": poll.created_event_id or "",
        }
        table.upsert_entity(entity)

    async def update_option_votes(
        self, poll_id: str, date: datetime, votes: int
    ) -> None:
        """Update the vote count for a poll option."""
        table = self._get_table("polloptions")
        entity = {
            "PartitionKey": poll_id,
            "RowKey": date.isoformat(),
            "vote_count": votes,
        }
        table.upsert_entity(entity)

    # Settings
    async def get_setting(self, key: str) -> str | None:
        """Get a setting value."""
        table = self._get_table("settings")
        try:
            entity = table.get_entity("settings", key)
            return entity["value"]
        except ResourceNotFoundError:
            return None

    async def set_setting(self, key: str, value: str) -> None:
        """Set a setting value."""
        table = self._get_table("settings")
        entity = {
            "PartitionKey": "settings",
            "RowKey": key,
            "value": value,
        }
        table.upsert_entity(entity)

    def _entity_to_poll(self, entity: dict) -> PollRecord:
        """Convert a table entity to a PollRecord."""
        return PollRecord(
            id=entity["RowKey"],
            message_id=entity["message_id"],
            channel_id=entity["channel_id"],
            created_at=datetime.fromisoformat(entity["created_at"]),
            closes_at=datetime.fromisoformat(entity["closes_at"]),
            closed=entity["closed"],
            winning_date=(
                datetime.fromisoformat(entity["winning_date"])
                if entity["winning_date"]
                else None
            ),
            created_event_id=entity["created_event_id"] or None,
        )
