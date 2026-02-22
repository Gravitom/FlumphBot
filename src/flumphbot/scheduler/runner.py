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
        """Set up all scheduled jobs."""
        config = self.bot.config.scheduler

        # Parse poll time
        hour, minute = map(int, config.poll_time.split(":"))
        day_of_week = DAY_MAP.get(config.poll_day.lower(), "mon")

        # Weekly poll job
        self.scheduler.add_job(
            self.tasks.post_weekly_poll,
            CronTrigger(
                day_of_week=day_of_week,
                hour=hour,
                minute=minute,
                timezone=config.timezone,
            ),
            id="weekly_poll",
            name="Post weekly scheduling poll",
            replace_existing=True,
        )
        logger.info(
            f"Scheduled weekly poll for {config.poll_day} at {config.poll_time}"
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
                timezone=config.timezone,
            ),
            id="vacation_confirmation",
            name="Vacation confirmation requests",
            replace_existing=True,
        )
        logger.info(
            f"Scheduled vacation confirmation for {config.poll_day} at {confirm_hour}:{minute:02d}"
        )

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
