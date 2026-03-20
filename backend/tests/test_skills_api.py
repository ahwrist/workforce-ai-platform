"""API-level tests for /api/v1/skills/ and /api/v1/domains/ endpoints.

These tests hit the real PostgreSQL database (no mocks) via the FastAPI ASGI app.
The 32 canonical skills seeded by seed_taxonomy.py must be present for counts to pass.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


# ── List skills ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_skills_returns_200_envelope():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/skills/")
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert "items" in body["data"]
    assert "total" in body["data"]
    assert "has_more" in body["data"]


@pytest.mark.asyncio
async def test_list_skills_total_equals_32_seeded():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/skills/?limit=100")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 32, f"Expected 32 seeded skills, got {data['total']}"
    assert len(data["items"]) == 32


@pytest.mark.asyncio
async def test_list_skills_pagination_cursor():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        page1 = await client.get("/api/v1/skills/?limit=10")
    assert page1.status_code == 200
    data1 = page1.json()["data"]
    assert data1["has_more"] is True
    assert data1["next_cursor"] is not None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        page2 = await client.get(f"/api/v1/skills/?limit=10&cursor={data1['next_cursor']}")
    assert page2.status_code == 200
    data2 = page2.json()["data"]
    # Pages must not overlap
    names1 = {s["canonical_name"] for s in data1["items"]}
    names2 = {s["canonical_name"] for s in data2["items"]}
    assert names1.isdisjoint(names2), "Page 1 and page 2 items overlap"


@pytest.mark.asyncio
async def test_list_skills_domain_filter_returns_only_matching():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/skills/?domain=data_and_ai&limit=100")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["domain"] == "data_and_ai", f"Unexpected domain: {item['domain']}"


# ── Single skill ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_skill_by_valid_id_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        list_resp = await client.get("/api/v1/skills/?limit=1")
        skill_id = list_resp.json()["data"]["items"][0]["id"]
        response = await client.get(f"/api/v1/skills/{skill_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["id"] == skill_id


@pytest.mark.asyncio
async def test_get_skill_nonexistent_uuid_returns_404_envelope():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/skills/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_get_skill_invalid_uuid_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/skills/not-a-valid-uuid")
    assert response.status_code == 404


# ── Trending skills ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trending_skills_returns_200_with_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/skills/trending")
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert isinstance(body["data"], list)


# ── Domains ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_domains_returns_six_domains_with_labels():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/domains/")
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    domains = body["data"]
    assert len(domains) == 6, f"Expected 6 domains, got {len(domains)}"
    for d in domains:
        assert d["domain"]
        assert d["label"]
        assert d["skill_count"] >= 0


@pytest.mark.asyncio
async def test_domains_skill_counts_sum_to_32():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/domains/")
    assert response.status_code == 200
    domains = response.json()["data"]
    total = sum(d["skill_count"] for d in domains)
    assert total == 32, f"Domain skill_counts should sum to 32, got {total}"
