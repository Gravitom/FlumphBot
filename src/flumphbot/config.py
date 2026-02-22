"""Configuration management for FlumphBot."""

import base64
import json
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass
class DiscordConfig:
    """Discord-related configuration."""

    bot_token: str
    guild_id: int
    channel_id: int


@dataclass
class GoogleConfig:
    """Google Calendar configuration."""

    credentials: dict
    calendar_id: str


@dataclass
class SchedulerConfig:
    """Scheduler configuration."""

    poll_day: str = "Monday"
    poll_time: str = "09:00"
    poll_duration_hours: int = 48
    sync_interval_minutes: int = 15
    timezone: str = "America/New_York"


@dataclass
class Config:
    """Main configuration container."""

    discord: DiscordConfig
    google: GoogleConfig
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    storage_backend: str = "sqlite"
    azure_storage_connection_string: str | None = None
    dnd_session_keyword: str = "D&D"

    # Keywords that indicate potentially personal events
    personal_keywords: list[str] = field(
        default_factory=lambda: [
            "doctor",
            "dentist",
            "appointment",
            "interview",
            "therapy",
            "medical",
            "checkup",
            "prescription",
            "court",
            "lawyer",
            "accountant",
            "meeting",
            "call with",
            "date",
            "wedding",
        ]
    )


def load_config() -> Config:
    """Load configuration from environment variables."""
    load_dotenv()

    # Parse Google credentials from base64-encoded JSON
    google_creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    if google_creds_b64:
        try:
            google_creds = json.loads(base64.b64decode(google_creds_b64).decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            # Try loading as plain JSON (for local development)
            google_creds = json.loads(google_creds_b64)
    else:
        google_creds = {}

    discord_config = DiscordConfig(
        bot_token=os.environ.get("DISCORD_BOT_TOKEN", ""),
        guild_id=int(os.environ.get("DISCORD_GUILD_ID", "0")),
        channel_id=int(os.environ.get("DISCORD_CHANNEL_ID", "0")),
    )

    google_config = GoogleConfig(
        credentials=google_creds,
        calendar_id=os.environ.get("GOOGLE_CALENDAR_ID", ""),
    )

    scheduler_config = SchedulerConfig(
        poll_day=os.environ.get("POLL_DAY", "Monday"),
        poll_time=os.environ.get("POLL_TIME", "09:00"),
        poll_duration_hours=int(os.environ.get("POLL_DURATION_HOURS", "48")),
        sync_interval_minutes=int(os.environ.get("SYNC_INTERVAL_MINUTES", "15")),
        timezone=os.environ.get("TIMEZONE", "America/New_York"),
    )

    return Config(
        discord=discord_config,
        google=google_config,
        scheduler=scheduler_config,
        storage_backend=os.environ.get("STORAGE_BACKEND", "sqlite"),
        azure_storage_connection_string=os.environ.get("AZURE_STORAGE_CONNECTION_STRING"),
        dnd_session_keyword=os.environ.get("DND_SESSION_KEYWORD", "D&D"),
    )
