"""SQLite storage backend for local development and self-hosted deployments."""

import logging
from datetime import datetime
from pathlib import Path

import aiosqlite

from flumphbot.storage.base import (
    PollOption,
    PollRecord,
    StorageBackend,
    UserMapping,
)

logger = logging.getLogger(__name__)


class SQLiteStorage(StorageBackend):
    """SQLite-based storage backend."""

    def __init__(self, db_path: str = "flumphbot.db"):
        """Initialize the SQLite storage.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self._connection: aiosqlite.Connection | None = None

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create the database connection."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
        return self._connection

    async def initialize(self) -> None:
        """Create database tables if they don't exist."""
        conn = await self._get_connection()

        await conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_mappings (
                discord_id INTEGER PRIMARY KEY,
                discord_name TEXT NOT NULL,
                calendar_email TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS polls (
                id TEXT PRIMARY KEY,
                message_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                closes_at TEXT NOT NULL,
                closed INTEGER DEFAULT 0,
                winning_date TEXT,
                created_event_id TEXT
            );

            CREATE TABLE IF NOT EXISTS poll_options (
                poll_id TEXT NOT NULL,
                date TEXT NOT NULL,
                vote_count INTEGER DEFAULT 0,
                PRIMARY KEY (poll_id, date),
                FOREIGN KEY (poll_id) REFERENCES polls(id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """
        )
        await conn.commit()
        logger.info(f"SQLite database initialized at {self.db_path}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    # User mappings
    async def get_user_mapping(self, discord_id: int) -> UserMapping | None:
        """Get a user mapping by Discord ID."""
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM user_mappings WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return UserMapping(
                    discord_id=row["discord_id"],
                    discord_name=row["discord_name"],
                    calendar_email=row["calendar_email"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            return None

    async def set_user_mapping(self, mapping: UserMapping) -> None:
        """Create or update a user mapping."""
        conn = await self._get_connection()
        await conn.execute(
            """
            INSERT OR REPLACE INTO user_mappings
            (discord_id, discord_name, calendar_email, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                mapping.discord_id,
                mapping.discord_name,
                mapping.calendar_email,
                mapping.created_at.isoformat(),
            ),
        )
        await conn.commit()

    async def get_all_user_mappings(self) -> list[UserMapping]:
        """Get all user mappings."""
        conn = await self._get_connection()
        async with conn.execute("SELECT * FROM user_mappings") as cursor:
            rows = await cursor.fetchall()
            return [
                UserMapping(
                    discord_id=row["discord_id"],
                    discord_name=row["discord_name"],
                    calendar_email=row["calendar_email"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

    async def delete_user_mapping(self, discord_id: int) -> None:
        """Delete a user mapping."""
        conn = await self._get_connection()
        await conn.execute(
            "DELETE FROM user_mappings WHERE discord_id = ?", (discord_id,)
        )
        await conn.commit()

    # Poll management
    async def create_poll(self, poll: PollRecord, options: list[PollOption]) -> None:
        """Create a new poll with its options."""
        conn = await self._get_connection()

        await conn.execute(
            """
            INSERT INTO polls
            (id, message_id, channel_id, created_at, closes_at, closed, winning_date, created_event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                poll.id,
                poll.message_id,
                poll.channel_id,
                poll.created_at.isoformat(),
                poll.closes_at.isoformat(),
                1 if poll.closed else 0,
                poll.winning_date.isoformat() if poll.winning_date else None,
                poll.created_event_id,
            ),
        )

        for option in options:
            await conn.execute(
                """
                INSERT INTO poll_options (poll_id, date, vote_count)
                VALUES (?, ?, ?)
                """,
                (option.poll_id, option.date.isoformat(), option.vote_count),
            )

        await conn.commit()

    async def get_poll(self, poll_id: str) -> PollRecord | None:
        """Get a poll by ID."""
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM polls WHERE id = ?", (poll_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_poll(row)
            return None

    async def get_active_poll(self) -> PollRecord | None:
        """Get the currently active (not closed) poll."""
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM polls WHERE closed = 0 ORDER BY created_at DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_poll(row)
            return None

    async def get_poll_options(self, poll_id: str) -> list[PollOption]:
        """Get all options for a poll."""
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM poll_options WHERE poll_id = ? ORDER BY date",
            (poll_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                PollOption(
                    poll_id=row["poll_id"],
                    date=datetime.fromisoformat(row["date"]),
                    vote_count=row["vote_count"],
                )
                for row in rows
            ]

    async def update_poll(self, poll: PollRecord) -> None:
        """Update a poll record."""
        conn = await self._get_connection()
        await conn.execute(
            """
            UPDATE polls SET
                closed = ?,
                winning_date = ?,
                created_event_id = ?
            WHERE id = ?
            """,
            (
                1 if poll.closed else 0,
                poll.winning_date.isoformat() if poll.winning_date else None,
                poll.created_event_id,
                poll.id,
            ),
        )
        await conn.commit()

    async def update_option_votes(
        self, poll_id: str, date: datetime, votes: int
    ) -> None:
        """Update the vote count for a poll option."""
        conn = await self._get_connection()
        await conn.execute(
            """
            UPDATE poll_options SET vote_count = ?
            WHERE poll_id = ? AND date = ?
            """,
            (votes, poll_id, date.isoformat()),
        )
        await conn.commit()

    # Settings
    async def get_setting(self, key: str) -> str | None:
        """Get a setting value."""
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        """Set a setting value."""
        conn = await self._get_connection()
        await conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await conn.commit()

    def _row_to_poll(self, row: aiosqlite.Row) -> PollRecord:
        """Convert a database row to a PollRecord."""
        return PollRecord(
            id=row["id"],
            message_id=row["message_id"],
            channel_id=row["channel_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            closes_at=datetime.fromisoformat(row["closes_at"]),
            closed=bool(row["closed"]),
            winning_date=(
                datetime.fromisoformat(row["winning_date"])
                if row["winning_date"]
                else None
            ),
            created_event_id=row["created_event_id"],
        )
