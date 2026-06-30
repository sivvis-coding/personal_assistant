"""Scheduler implementation based on APScheduler."""

from collections.abc import Callable, Coroutine
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.logging.logger import logger

JobFunc = Callable[[], Coroutine[Any, Any, None]]


class Scheduler:
    """Job scheduler that invokes async callables at configured intervals.

    Parameters:
        None.

    Returns:
        Scheduler instance.

    Edge cases:
        Jobs are idempotent at the invocation level; each callable is
        responsible for its own concurrency safety.
    """

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._jobs: list[tuple[str, str, JobFunc]] = []

    def add_job(self, name: str, cron: str, func: JobFunc) -> None:
        """Register a scheduled job.

        Parameters:
            name: Human-readable job name.
            cron: Cron expression.
            func: Async callable invoked when the job fires.

        Returns:
            None.
        """
        self._jobs.append((name, cron, func))

    def start(self) -> None:
        """Start the scheduler and register all configured jobs."""
        for name, cron, func in self._jobs:
            self._scheduler.add_job(
                func=self._run_job,
                trigger=CronTrigger.from_crontab(cron),
                id=name,
                replace_existing=True,
                args=(name, func),
            )
        self._scheduler.start()
        logger.info("Scheduler started", extra={"job_count": len(self._jobs)})

    def shutdown(self) -> None:
        """Stop the scheduler."""
        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    async def _run_job(self, name: str, func: JobFunc) -> None:
        """Execute a scheduled job by calling the registered callable."""
        logger.info("Running scheduled job", extra={"job_name": name})
        try:
            await func()
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Scheduled job failed",
                extra={"job_name": name, "error": str(exc)},
            )
