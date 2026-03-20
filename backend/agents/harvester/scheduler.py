"""APScheduler job definitions for the intelligence pipeline.

The scheduler dispatches Celery tasks rather than running agents directly —
this keeps the scheduler lightweight and lets the Celery worker handle
concurrency and retries.

Schedule:
  - 1 AM UTC daily  — cleanup_abandoned_sessions
  - 2 AM UTC daily  — harvest_new_postings (Harvester)
  - 4 AM UTC daily  — extract_skills_from_postings (Synthesizer)
  - 6 AM UTC daily  — classify_and_deduplicate (Taxonomist)
  - 3 AM UTC Sunday — qdrant_orphan_cleanup (future)
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


def _dispatch_harvest():
    """Enqueue the harvest Celery task."""
    from pipelines.skill_pipeline import harvest_new_postings  # noqa: PLC0415
    result = harvest_new_postings.delay()
    logger.info("Harvest task enqueued: task_id=%s", result.id)


def _dispatch_extraction():
    """Enqueue the skill extraction Celery task."""
    from pipelines.skill_pipeline import extract_skills_from_postings  # noqa: PLC0415
    result = extract_skills_from_postings.delay()
    logger.info("Extraction task enqueued: task_id=%s", result.id)


def _dispatch_classification():
    """Enqueue the taxonomy classification Celery task."""
    from pipelines.skill_pipeline import classify_and_deduplicate  # noqa: PLC0415
    result = classify_and_deduplicate.delay()
    logger.info("Classification task enqueued: task_id=%s", result.id)


def setup_scheduler() -> AsyncIOScheduler:
    """Register all scheduled pipeline jobs and return the configured scheduler."""

    scheduler.add_job(
        _dispatch_harvest,
        CronTrigger(hour=2, minute=0),
        id="harvest_job",
        replace_existing=True,
        misfire_grace_time=3600,  # allow up to 1h late if scheduler was down
    )

    scheduler.add_job(
        _dispatch_extraction,
        CronTrigger(hour=4, minute=0),
        id="synthesize_job",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        _dispatch_classification,
        CronTrigger(hour=6, minute=0),
        id="classify_job",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    logger.info("Pipeline scheduler configured with %d jobs", len(scheduler.get_jobs()))
    return scheduler
