"""Harvester agent — scrapes job postings from configured sources.

Supports three source types:
  - Greenhouse JSON API (greenhouse)
  - Lever JSON API (lever)
  - Raw HTML via BeautifulSoup (html)

Operational rules enforced:
  - URL-level deduplication before DB insert
  - Per-domain rate limiting (SCRAPER_DELAY_SECONDS between requests)
  - Exponential backoff on HTTP 429 / 503 responses
  - robots.txt compliance per domain
  - Per-company error isolation (failure on one company never stops the run)
"""
import asyncio
import logging
import re
import time
from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from agents.harvester.sources import GREENHOUSE_SOURCES, HTML_SOURCES, LEVER_SOURCES
from core.config.settings import get_settings
from core.database.postgres import AsyncSessionLocal
from core.models.job_posting import JobPosting

logger = logging.getLogger(__name__)

settings = get_settings()

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER_API = "https://api.lever.co/v0/postings/{handle}?mode=json"

# Cached robots.txt parsers per domain, to avoid re-fetching during a run
_robots_cache: dict[str, RobotFileParser] = {}


# ---------------------------------------------------------------------------
# robots.txt helpers
# ---------------------------------------------------------------------------


async def _fetch_robots(client: httpx.AsyncClient, base_url: str) -> RobotFileParser:
    """Fetch and parse robots.txt for a given base URL.  Returns a permissive
    parser on any error so that a bad robots.txt never blocks scraping."""
    robots_url = f"{base_url}/robots.txt"
    rp = RobotFileParser(robots_url)
    try:
        resp = await client.get(robots_url, timeout=10)
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
        else:
            # No robots.txt → allow everything
            rp.allow_all = True
    except Exception:
        rp.allow_all = True
    return rp


def _base_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


async def _robots_for(client: httpx.AsyncClient, url: str) -> RobotFileParser:
    base = _base_url(url)
    if base not in _robots_cache:
        _robots_cache[base] = await _fetch_robots(client, base)
    return _robots_cache[base]


def _is_allowed(rp: RobotFileParser, url: str) -> bool:
    try:
        return rp.can_fetch("*", url)
    except Exception:
        return True


# ---------------------------------------------------------------------------
# HTTP helpers — exponential backoff
# ---------------------------------------------------------------------------


async def _get_with_backoff(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_retries: int = 4,
    initial_delay: float = 2.0,
) -> Optional[httpx.Response]:
    """GET url with exponential backoff on 429/503. Returns None after exhausting retries."""
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            resp = await client.get(url, timeout=30, follow_redirects=True)
            if resp.status_code in (429, 503):
                if attempt < max_retries - 1:
                    retry_after = int(resp.headers.get("Retry-After", delay))
                    logger.warning(
                        "Rate-limited on %s (HTTP %s) — waiting %ss",
                        url,
                        resp.status_code,
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    delay *= 2
                    continue
                return None
            return resp
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            if attempt < max_retries - 1:
                logger.warning("Request error for %s: %s — retrying in %ss", url, exc, delay)
                await asyncio.sleep(delay)
                delay *= 2
            else:
                logger.error("Exhausted retries for %s: %s", url, exc)
    return None


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


async def _url_exists(session, url: str) -> bool:
    """Return True if a job posting with this URL already exists in the DB."""
    result = await session.execute(select(JobPosting.id).where(JobPosting.url == url).limit(1))
    return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Source-type scrapers
# ---------------------------------------------------------------------------


async def _scrape_greenhouse(
    client: httpx.AsyncClient, source: dict, delay: float
) -> list[dict]:
    """Fetch all open jobs from the Greenhouse Jobs Board API."""
    token = source["board_token"]
    company = source["company"]
    api_url = GREENHOUSE_API.format(token=token)

    rp = await _robots_for(client, f"https://boards.greenhouse.io")
    if not _is_allowed(rp, api_url):
        logger.info("robots.txt disallows %s — skipping %s", api_url, company)
        return []

    resp = await _get_with_backoff(client, api_url)
    if resp is None or resp.status_code != 200:
        logger.warning("Greenhouse fetch failed for %s (token=%s)", company, token)
        return []

    try:
        data = resp.json()
        jobs_raw = data.get("jobs", [])
    except Exception as exc:
        logger.warning("JSON parse error for %s: %s", company, exc)
        return []

    postings = []
    for job in jobs_raw:
        job_url = job.get("absolute_url", "")
        if not job_url:
            continue

        # Parse posted_at if available
        posted_at = None
        if job.get("updated_at"):
            try:
                posted_at = datetime.fromisoformat(
                    job["updated_at"].replace("Z", "+00:00")
                ).date()
            except Exception:
                pass

        postings.append(
            {
                "company": company,
                "title": job.get("title", ""),
                "url": job_url,
                "raw_html": None,
                "raw_text": job.get("title", ""),
                "posted_date": posted_at,
                "source": "greenhouse",
            }
        )

    await asyncio.sleep(delay)
    return postings


async def _scrape_lever(
    client: httpx.AsyncClient, source: dict, delay: float
) -> list[dict]:
    """Fetch all open jobs from the Lever Postings API."""
    handle = source["handle"]
    company = source["company"]
    api_url = LEVER_API.format(handle=handle)

    resp = await _get_with_backoff(client, api_url)
    if resp is None or resp.status_code != 200:
        logger.warning("Lever fetch failed for %s (handle=%s)", company, handle)
        return []

    try:
        jobs_raw = resp.json()
    except Exception as exc:
        logger.warning("JSON parse error for %s: %s", company, exc)
        return []

    postings = []
    for job in jobs_raw:
        job_url = job.get("hostedUrl", "")
        if not job_url:
            continue

        # Combine text fields for raw_text
        additional = job.get("additional", "") or ""
        description = job.get("descriptionPlain", "") or ""
        raw_text = f"{job.get('text', '')}\n{description}\n{additional}".strip()

        # createdAt is Unix ms
        posted_at = None
        if job.get("createdAt"):
            try:
                posted_at = datetime.fromtimestamp(
                    job["createdAt"] / 1000, tz=timezone.utc
                ).date()
            except Exception:
                pass

        postings.append(
            {
                "company": company,
                "title": job.get("text", ""),
                "url": job_url,
                "raw_html": None,
                "raw_text": raw_text,
                "posted_date": posted_at,
                "source": "lever",
            }
        )

    await asyncio.sleep(delay)
    return postings


async def _scrape_html(
    client: httpx.AsyncClient, source: dict, delay: float
) -> list[dict]:
    """Scrape a raw HTML career page and extract job links via CSS selector."""
    company = source["company"]
    listing_url = source["url"]
    selector = source.get("job_selector", "a[href]")

    rp = await _robots_for(client, _base_url(listing_url))
    if not _is_allowed(rp, listing_url):
        logger.info("robots.txt disallows %s — skipping %s", listing_url, company)
        return []

    resp = await _get_with_backoff(client, listing_url)
    if resp is None or resp.status_code != 200:
        logger.warning("HTML fetch failed for %s", company)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    links = soup.select(selector)
    base = _base_url(listing_url)
    postings = []

    for tag in links[:50]:  # cap at 50 to avoid runaway scraping
        href = tag.get("href", "")
        if not href:
            continue
        # Resolve relative URLs
        if href.startswith("/"):
            href = base + href
        elif not href.startswith("http"):
            continue

        title = tag.get_text(strip=True) or ""
        if not title:
            continue

        postings.append(
            {
                "company": company,
                "title": title,
                "url": href,
                "raw_html": str(tag),
                "raw_text": title,
                "posted_date": None,
                "source": "html",
            }
        )

    await asyncio.sleep(delay)
    return postings


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------


async def _insert_new_postings(raw_postings: list[dict]) -> tuple[int, int]:
    """Insert postings that don't already exist. Returns (new_count, skipped_count)."""
    new_count = 0
    skipped_count = 0

    async with AsyncSessionLocal() as session:
        for p in raw_postings:
            if await _url_exists(session, p["url"]):
                skipped_count += 1
                continue
            posting = JobPosting(
                company=p["company"],
                title=p["title"],
                url=p["url"],
                raw_html=p["raw_html"],
                raw_text=p["raw_text"],
                posted_date=p["posted_date"],
                harvested_at=datetime.now(tz=timezone.utc),
                processed=False,
                source=p["source"],
            )
            session.add(posting)
            try:
                await session.flush()
                new_count += 1
            except IntegrityError:
                # Race condition: another worker inserted between our check and flush
                await session.rollback()
                skipped_count += 1
                continue

        await session.commit()

    return new_count, skipped_count


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_harvest() -> dict:
    """
    Main harvest entry point.  Iterates all configured sources, fetches new
    job postings, deduplicates, and inserts to DB.

    Returns a summary dict:
        {companies_attempted, companies_succeeded, postings_found,
         postings_new, postings_skipped, errors}
    """
    _robots_cache.clear()
    delay = float(settings.scraper_delay_seconds)
    headers = {
        "User-Agent": "WorkforceAI-Harvester/1.0 (research; contact: admin@workforceai.com)"
    }

    summary = {
        "companies_attempted": 0,
        "companies_succeeded": 0,
        "postings_found": 0,
        "postings_new": 0,
        "postings_skipped": 0,
        "errors": [],
    }

    async with httpx.AsyncClient(headers=headers) as client:
        # --- Greenhouse ---
        for source in GREENHOUSE_SOURCES:
            summary["companies_attempted"] += 1
            try:
                postings = await _scrape_greenhouse(client, source, delay)
                summary["postings_found"] += len(postings)
                new, skipped = await _insert_new_postings(postings)
                summary["postings_new"] += new
                summary["postings_skipped"] += skipped
                summary["companies_succeeded"] += 1
                logger.info(
                    "[Greenhouse] %s: found=%d new=%d skipped=%d",
                    source["company"],
                    len(postings),
                    new,
                    skipped,
                )
            except Exception as exc:
                logger.error("[Greenhouse] %s failed: %s", source["company"], exc, exc_info=True)
                summary["errors"].append({"company": source["company"], "error": str(exc)})

        # --- Lever ---
        for source in LEVER_SOURCES:
            summary["companies_attempted"] += 1
            try:
                postings = await _scrape_lever(client, source, delay)
                summary["postings_found"] += len(postings)
                new, skipped = await _insert_new_postings(postings)
                summary["postings_new"] += new
                summary["postings_skipped"] += skipped
                summary["companies_succeeded"] += 1
                logger.info(
                    "[Lever] %s: found=%d new=%d skipped=%d",
                    source["company"],
                    len(postings),
                    new,
                    skipped,
                )
            except Exception as exc:
                logger.error("[Lever] %s failed: %s", source["company"], exc, exc_info=True)
                summary["errors"].append({"company": source["company"], "error": str(exc)})

        # --- HTML ---
        for source in HTML_SOURCES:
            summary["companies_attempted"] += 1
            try:
                postings = await _scrape_html(client, source, delay)
                summary["postings_found"] += len(postings)
                new, skipped = await _insert_new_postings(postings)
                summary["postings_new"] += new
                summary["postings_skipped"] += skipped
                summary["companies_succeeded"] += 1
                logger.info(
                    "[HTML] %s: found=%d new=%d skipped=%d",
                    source["company"],
                    len(postings),
                    new,
                    skipped,
                )
            except Exception as exc:
                logger.error("[HTML] %s failed: %s", source["company"], exc, exc_info=True)
                summary["errors"].append({"company": source["company"], "error": str(exc)})

    logger.info(
        "Harvest complete — attempted=%d succeeded=%d found=%d new=%d skipped=%d errors=%d",
        summary["companies_attempted"],
        summary["companies_succeeded"],
        summary["postings_found"],
        summary["postings_new"],
        summary["postings_skipped"],
        len(summary["errors"]),
    )
    return summary
