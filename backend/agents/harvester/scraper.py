"""Harvester agent — scrapes job postings from configured sources."""
import logging

logger = logging.getLogger(__name__)


async def run_harvest() -> dict:
    """
    Main harvest entry point. Iterates all configured sources,
    fetches new job postings, deduplicates, and inserts to DB.

    Returns a summary dict: {companies_attempted, postings_found, postings_new, errors}
    """
    # Implemented in Phase 1b
    logger.info("Harvest triggered — Phase 1b implementation pending")
    return {
        "companies_attempted": 0,
        "companies_succeeded": 0,
        "postings_found": 0,
        "postings_new": 0,
        "postings_skipped": 0,
        "errors": [],
    }
