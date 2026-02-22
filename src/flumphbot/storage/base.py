"""Abstract storage interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class UserMapping:
    """Maps a Discord user to their calendar email."""

    discord_id: int
    discord_name: str
    calendar_email: str
    created_at: datetime


@dataclass
class PollRecord:
    """Record of a scheduling poll."""

    id: str
    message_id: int
    channel_id: int
    created_at: datetime
    closes_at: datetime
    closed: bool = False
    winning_date: datetime | None = None
    created_event_id: str | None = None


@dataclass
class PollOption:
    """A single option in a poll."""

    poll_id: str
    date: datetime
    vote_count: int = 0


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage backend (create tables, etc.)."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the storage backend connection."""
        pass

    # User mappings
    @abstractmethod
    async def get_user_mapping(self, discord_id: int) -> UserMapping | None:
        """Get a user mapping by Discord ID."""
        pass

    @abstractmethod
    async def set_user_mapping(self, mapping: UserMapping) -> None:
        """Create or update a user mapping."""
        pass

    @abstractmethod
    async def get_all_user_mappings(self) -> list[UserMapping]:
        """Get all user mappings."""
        pass

    @abstractmethod
    async def delete_user_mapping(self, discord_id: int) -> None:
        """Delete a user mapping."""
        pass

    # Poll management
    @abstractmethod
    async def create_poll(self, poll: PollRecord, options: list[PollOption]) -> None:
        """Create a new poll with its options."""
        pass

    @abstractmethod
    async def get_poll(self, poll_id: str) -> PollRecord | None:
        """Get a poll by ID."""
        pass

    @abstractmethod
    async def get_active_poll(self) -> PollRecord | None:
        """Get the currently active (not closed) poll."""
        pass

    @abstractmethod
    async def get_poll_options(self, poll_id: str) -> list[PollOption]:
        """Get all options for a poll."""
        pass

    @abstractmethod
    async def update_poll(self, poll: PollRecord) -> None:
        """Update a poll record."""
        pass

    @abstractmethod
    async def update_option_votes(self, poll_id: str, date: datetime, votes: int) -> None:
        """Update the vote count for a poll option."""
        pass

    # Settings
    @abstractmethod
    async def get_setting(self, key: str) -> str | None:
        """Get a setting value."""
        pass

    @abstractmethod
    async def set_setting(self, key: str, value: str) -> None:
        """Set a setting value."""
        pass
