"""Scheduler runner using APScheduler for local/generic deployments."""

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from flumphbot.scheduler.tasks import ScheduledTasks

if TYPE_CHECKING:
    from flumphbot.bot.client import FlumphBot

logger = logging.getLogger(__name__)

# Map day names to cron day-of-week values
DAY_MAP = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}


class SchedulerRunner:
    """Runs scheduled tasks using APScheduler."""

    def __init__(self, bot: "FlumphBot"):
        """Initialize the scheduler.

        Args:
            bot: The FlumphBot instance.
        """
        self.bot = bot
        self.tasks = ScheduledTasks(bot)
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self) -> None:
        """Set up all scheduled jobs using config defaults.

        Note: This is called synchronously during init. For dynamic settings
        from storage, call reload_schedule() after bot is ready.
        """
        config = self.bot.config.scheduler

        # Parse poll time from config defaults
        hour, minute = map(int, config.poll_time.split(":"))
        day_of_week = DAY_MAP.get(config.poll_day.lower(), "mon")
        timezone = config.timezone

        self._add_core_jobs(day_of_week, hour, minute, timezone, config)

    def _add_core_jobs(
        self,
        day_of_week: str,
        hour: int,
        minute: int,
        timezone: str,
        config,
    ) -> None:
        """Add all core scheduled jobs.

        Args:
            day_of_week: Cron day of week value.
            hour: Hour for weekly jobs.
            minute: Minute for weekly jobs.
            timezone: Timezone string.
            config: Scheduler config for other settings.
        """
        # Weekly poll job
        self.scheduler.add_job(
            self.tasks.post_weekly_poll,
            CronTrigger(
                day_of_week=day_of_week,
                hour=hour,
                minute=minute,
                timezone=timezone,
            ),
            id="weekly_poll",
            name="Post weekly scheduling poll",
            replace_existing=True,
        )
        logger.info(
            f"Scheduled weekly poll for {day_of_week} at {hour:02d}:{minute:02d} {timezone}"
        )

        # Calendar hygiene sync (every N minutes)
        self.scheduler.add_job(
            self.tasks.sync_calendar_hygiene,
            IntervalTrigger(minutes=config.sync_interval_minutes),
            id="calendar_hygiene",
            name="Calendar hygiene sync",
            replace_existing=True,
        )
        logger.info(
            f"Scheduled calendar sync every {config.sync_interval_minutes} minutes"
        )

        # Poll completion check (every 5 minutes)
        self.scheduler.add_job(
            self.tasks.check_poll_completion,
            IntervalTrigger(minutes=5),
            id="poll_completion",
            name="Check poll completion",
            replace_existing=True,
        )
        logger.info("Scheduled poll completion check every 5 minutes")

        # Vacation confirmation (weekly, 1 hour before poll)
        confirm_hour = hour - 1 if hour > 0 else 23
        self.scheduler.add_job(
            self.tasks.confirm_vacations,
            CronTrigger(
                day_of_week=day_of_week,
                hour=confirm_hour,
                minute=minute,
                timezone=timezone,
            ),
            id="vacation_confirmation",
            name="Vacation confirmation requests",
            replace_existing=True,
        )
        logger.info(
            f"Scheduled vacation confirmation for {day_of_week} at {confirm_hour}:{minute:02d}"
        )

        # Session reminders (hourly check)
        self.scheduler.add_job(
            self.tasks.send_session_reminders,
            IntervalTrigger(minutes=30),
            id="session_reminders",
            name="Session reminder check",
            replace_existing=True,
        )
        logger.info("Scheduled session reminder check every 30 minutes")

        # Poll warning (hourly check)
        self.scheduler.add_job(
            self.tasks.check_poll_warning,
            IntervalTrigger(minutes=30),
            id="poll_warning",
            name="Poll warning check",
            replace_existing=True,
        )
        logger.info("Scheduled poll warning check every 30 minutes")

    async def reload_schedule(self) -> None:
        """Reload schedule settings from storage.

        This method loads settings from storage (with config fallback)
        and reschedules all jobs accordingly. Call this after settings
        are changed via commands.
        """
        config = self.bot.config.scheduler

        # Load settings from storage with config fallback
        schedule_day = await self.bot.storage.get_setting("schedule_day")
        schedule_hour = await self.bot.storage.get_setting("schedule_hour")
        schedule_timezone = await self.bot.storage.get_setting("schedule_timezone")

        # Use storage values or fall back to config
        day = schedule_day or config.poll_day
        hour_str = schedule_hour or config.poll_time.split(":")[0]
        timezone = schedule_timezone or config.timezone

        hour = int(hour_str)
        minute = 0  # We only support hour-level scheduling
        day_of_week = DAY_MAP.get(day.lower(), "mon")

        logger.info(f"Reloading schedule: {day} at {hour:02d}:00 {timezone}")

        # Re-add all jobs with new settings
        self._add_core_jobs(day_of_week, hour, minute, timezone, config)

    def start(self) -> None:
        """Start the scheduler."""
        self.scheduler.start()
        logger.info("Scheduler started")

    def shutdown(self) -> None:
        """Shut down the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler shut down")

    def run_job_now(self, job_id: str) -> None:
        """Manually trigger a job immediately.

        Args:
            job_id: The ID of the job to run.
        """
        job = self.scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=None)
            logger.info(f"Manually triggered job: {job_id}")
        else:
            logger.warning(f"Job not found: {job_id}")
