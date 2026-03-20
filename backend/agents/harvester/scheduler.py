"""APScheduler job definitions for the intelligence pipeline."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler(timezone="UTC")


def setup_scheduler():
    """Register all scheduled pipeline jobs."""
    # Harvest: 2 AM UTC daily
    scheduler.add_job(
        "pipelines.skill_pipeline:harvest_new_postings",
        CronTrigger(hour=2, minute=0),
        id="harvest_job",
        replace_existing=True,
    )
    return scheduler
