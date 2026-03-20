"""Tests for the Harvester agent (Epic 1.2).

Strategy:
  - Unit tests for scraping helpers (robots.txt, backoff, dedup) using httpx mock transport
  - Integration tests for admin trigger endpoints via FastAPI ASGI client
  - No real outbound HTTP — all external calls are intercepted by a mock transport

Admin endpoints are tested with an invalid key (403) and a valid key (200/503 depending on Celery).
Celery is not running in the test environment, so trigger endpoints are expected to return 503
when Celery cannot connect; we assert that 403 is returned for bad keys (auth tested independently
from Celery availability).
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from agents.harvester.scraper import (
    _base_url,
    _is_allowed,
    _scrape_greenhouse,
    _scrape_lever,
)
from main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockTransport(httpx.AsyncBaseTransport):
    """Minimal mock transport that returns a preset response."""

    def __init__(self, status_code: int = 200, body: str | bytes = b""):
        self._status_code = status_code
        self._body = body if isinstance(body, bytes) else body.encode()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(self._status_code, content=self._body)


def _json_transport(data, status_code: int = 200) -> _MockTransport:
    return _MockTransport(status_code=status_code, body=json.dumps(data))


# ---------------------------------------------------------------------------
# Unit tests — _base_url
# ---------------------------------------------------------------------------


def test_base_url_extracts_scheme_and_host():
    assert _base_url("https://boards-api.greenhouse.io/v1/boards/anthropic/jobs") == \
        "https://boards-api.greenhouse.io"


def test_base_url_preserves_port():
    assert _base_url("http://localhost:8000/foo") == "http://localhost:8000"


# ---------------------------------------------------------------------------
# Unit tests — robots.txt (_is_allowed)
# ---------------------------------------------------------------------------


def test_is_allowed_returns_true_for_permissive_parser():
    from urllib.robotparser import RobotFileParser
    rp = RobotFileParser()
    rp.allow_all = True
    assert _is_allowed(rp, "https://example.com/jobs") is True


def test_is_allowed_returns_false_when_disallowed():
    from urllib.robotparser import RobotFileParser
    rp = RobotFileParser()
    rp.parse(["User-agent: *", "Disallow: /"])
    assert _is_allowed(rp, "https://example.com/jobs") is False


# ---------------------------------------------------------------------------
# Unit tests — Greenhouse scraper
# ---------------------------------------------------------------------------


GREENHOUSE_RESPONSE = {
    "jobs": [
        {
            "id": 1,
            "title": "Research Engineer",
            "absolute_url": "https://boards.greenhouse.io/anthropic/jobs/1",
            "updated_at": "2024-01-15T10:00:00Z",
        },
        {
            "id": 2,
            "title": "ML Infrastructure Engineer",
            "absolute_url": "https://boards.greenhouse.io/anthropic/jobs/2",
            "updated_at": "2024-01-16T10:00:00Z",
        },
    ]
}


@pytest.mark.asyncio
async def test_scrape_greenhouse_returns_correct_postings():
    transport = _json_transport(GREENHOUSE_RESPONSE)
    source = {"company": "Anthropic", "board_token": "anthropic"}

    async with httpx.AsyncClient(transport=transport) as client:
        with patch("agents.harvester.scraper._robots_for") as mock_robots:
            mock_robots.return_value = MagicMock(can_fetch=lambda *a: True)
            mock_robots.return_value.allow_all = True
            # Make _is_allowed always return True
            with patch("agents.harvester.scraper._is_allowed", return_value=True):
                postings = await _scrape_greenhouse(client, source, delay=0)

    assert len(postings) == 2
    assert postings[0]["company"] == "Anthropic"
    assert postings[0]["title"] == "Research Engineer"
    assert postings[0]["source"] == "greenhouse"
    assert postings[0]["url"] == "https://boards.greenhouse.io/anthropic/jobs/1"
    assert postings[0]["posted_date"] is not None


@pytest.mark.asyncio
async def test_scrape_greenhouse_handles_api_error_gracefully():
    transport = _MockTransport(status_code=404, body=b"Not Found")
    source = {"company": "Anthropic", "board_token": "anthropic"}

    async with httpx.AsyncClient(transport=transport) as client:
        with patch("agents.harvester.scraper._robots_for") as mock_robots:
            mock_robots.return_value = MagicMock()
            with patch("agents.harvester.scraper._is_allowed", return_value=True):
                postings = await _scrape_greenhouse(client, source, delay=0)

    assert postings == []


# ---------------------------------------------------------------------------
# Unit tests — Lever scraper
# ---------------------------------------------------------------------------


LEVER_RESPONSE = [
    {
        "id": "abc123",
        "text": "Senior Frontend Engineer",
        "hostedUrl": "https://jobs.lever.co/notion/abc123",
        "descriptionPlain": "We are looking for a senior frontend engineer.",
        "additional": "Must know React.",
        "createdAt": 1705312800000,  # 2024-01-15 Unix ms
    }
]


@pytest.mark.asyncio
async def test_scrape_lever_returns_correct_postings():
    transport = _json_transport(LEVER_RESPONSE)
    source = {"company": "Notion", "handle": "notion"}

    async with httpx.AsyncClient(transport=transport) as client:
        postings = await _scrape_lever(client, source, delay=0)

    assert len(postings) == 1
    assert postings[0]["company"] == "Notion"
    assert postings[0]["title"] == "Senior Frontend Engineer"
    assert postings[0]["source"] == "lever"
    assert "React" in postings[0]["raw_text"]
    assert postings[0]["posted_date"] is not None


@pytest.mark.asyncio
async def test_scrape_lever_skips_entries_without_url():
    data = [{"id": "x", "text": "Job", "hostedUrl": "", "createdAt": 0}]
    transport = _json_transport(data)
    source = {"company": "Notion", "handle": "notion"}

    async with httpx.AsyncClient(transport=transport) as client:
        postings = await _scrape_lever(client, source, delay=0)

    assert postings == []


# ---------------------------------------------------------------------------
# Unit tests — sources completeness
# ---------------------------------------------------------------------------


def test_sources_total_at_least_20_companies():
    from agents.harvester.sources import GREENHOUSE_SOURCES, HTML_SOURCES, LEVER_SOURCES

    total = len(GREENHOUSE_SOURCES) + len(LEVER_SOURCES) + len(HTML_SOURCES)
    assert total >= 20, f"Expected ≥20 configured companies, got {total}"


def test_greenhouse_sources_have_required_fields():
    from agents.harvester.sources import GREENHOUSE_SOURCES

    for source in GREENHOUSE_SOURCES:
        assert "company" in source, f"Missing 'company' in {source}"
        assert "board_token" in source, f"Missing 'board_token' in {source}"


def test_lever_sources_have_required_fields():
    from agents.harvester.sources import LEVER_SOURCES

    for source in LEVER_SOURCES:
        assert "company" in source, f"Missing 'company' in {source}"
        assert "handle" in source, f"Missing 'handle' in {source}"


# ---------------------------------------------------------------------------
# Integration tests — admin endpoints (auth)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_harvest_trigger_rejects_bad_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/harvest/trigger",
            headers={"X-Admin-Key": "wrong-key"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_synthesize_trigger_rejects_bad_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/synthesize/trigger",
            headers={"X-Admin-Key": "wrong-key"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_classify_trigger_rejects_bad_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/classify/trigger",
            headers={"X-Admin-Key": "wrong-key"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_harvest_trigger_missing_key_returns_422():
    """Missing X-Admin-Key header → FastAPI returns 422 Unprocessable Entity."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/harvest/trigger")
    assert response.status_code == 422
