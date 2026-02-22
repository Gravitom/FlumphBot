"""Storage backends for FlumphBot."""

from flumphbot.storage.base import StorageBackend
from flumphbot.storage.sqlite import SQLiteStorage

__all__ = ["StorageBackend", "SQLiteStorage"]
