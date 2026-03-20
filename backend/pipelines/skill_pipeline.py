"""Celery task chain: Harvester → Synthesizer → Taxonomist."""
from celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="pipelines.skill_pipeline.harvest_new_postings")
def harvest_new_postings(self):
    """Celery task wrapper for the Harvester agent."""
    import asyncio
    from agents.harvester.scraper import run_harvest
    return asyncio.run(run_harvest())


@celery_app.task(bind=True, name="pipelines.skill_pipeline.extract_skills_from_postings")
def extract_skills_from_postings(self):
    """Celery task wrapper for the Synthesizer agent."""
    import asyncio
    from agents.synthesizer.extractor import run_extraction
    return asyncio.run(run_extraction())


@celery_app.task(bind=True, name="pipelines.skill_pipeline.classify_and_deduplicate")
def classify_and_deduplicate(self):
    """Celery task wrapper for the Taxonomist agent."""
    import asyncio
    from agents.taxonomist.mapper import run_classification
    return asyncio.run(run_classification())
