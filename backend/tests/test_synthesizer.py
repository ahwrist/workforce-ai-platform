"""Tests for the Synthesizer agent (Epic 1.3).

Strategy:
  - Unit tests for _normalize_name helper
  - Unit tests for embed_and_store with mocked OpenAI + Qdrant + DB
  - Unit tests for run_extraction with mocked DB + LangChain chain
  - Admin endpoint auth tests for /synthesize/trigger

All external I/O (DB, OpenAI, Qdrant, Anthropic) is fully mocked.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from agents.synthesizer.extractor import _normalize_name
from main import app


# ---------------------------------------------------------------------------
# Unit tests — _normalize_name
# ---------------------------------------------------------------------------


def test_normalize_name_lowercases():
    assert _normalize_name("Python") == "python"


def test_normalize_name_strips_whitespace():
    assert _normalize_name("  react  ") == "react"


def test_normalize_name_collapses_internal_spaces():
    assert _normalize_name("machine  learning") == "machine learning"


def test_normalize_name_handles_mixed_case_and_spaces():
    assert _normalize_name("  REST API  ") == "rest api"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_cm(mock_session: AsyncMock) -> MagicMock:
    """Return a context-manager mock that yields mock_session."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


# ---------------------------------------------------------------------------
# Unit tests — embed_and_store
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_and_store_empty_list_returns_zeros():
    from agents.synthesizer.embedder import embed_and_store

    result = await embed_and_store([])
    assert result == {"embedded": 0, "failed": 0}


@pytest.mark.asyncio
async def test_embed_and_store_no_pending_skills_returns_zeros():
    """When all skill IDs have already been embedded, returns zeroed counts."""
    from agents.synthesizer.embedder import embed_and_store

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch(
        "agents.synthesizer.embedder.AsyncSessionLocal",
        return_value=_make_session_cm(mock_session),
    ):
        result = await embed_and_store([uuid.uuid4()])

    assert result["embedded"] == 0
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_embed_and_store_embeds_pending_skills():
    """Happy-path: 2 pending skills are embedded and stored in Qdrant."""
    from agents.synthesizer.embedder import embed_and_store

    skill_id_1 = uuid.uuid4()
    skill_id_2 = uuid.uuid4()

    mock_skill_1 = MagicMock()
    mock_skill_1.id = skill_id_1
    mock_skill_1.canonical_name = "python"
    mock_skill_1.skill_type = "technical"
    mock_skill_1.domain = None

    mock_skill_2 = MagicMock()
    mock_skill_2.id = skill_id_2
    mock_skill_2.canonical_name = "docker"
    mock_skill_2.skill_type = "tool"
    mock_skill_2.domain = None

    # First session call returns skills; second session call is for update
    fetch_session = AsyncMock()
    fetch_result = MagicMock()
    fetch_result.scalars.return_value.all.return_value = [mock_skill_1, mock_skill_2]
    fetch_session.execute = AsyncMock(return_value=fetch_result)

    update_session = AsyncMock()
    update_session.execute = AsyncMock(return_value=MagicMock())
    update_session.commit = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_session_cm(fetch_session)
        return _make_session_cm(update_session)

    mock_openai = AsyncMock()
    mock_embed_response = MagicMock()
    mock_embed_response.data = [
        MagicMock(embedding=[0.1] * 1536),
        MagicMock(embedding=[0.2] * 1536),
    ]
    mock_openai.embeddings.create = AsyncMock(return_value=mock_embed_response)

    mock_qdrant_upsert = AsyncMock()

    with (
        patch("agents.synthesizer.embedder.AsyncSessionLocal", side_effect=_session_factory),
        patch("agents.synthesizer.embedder.AsyncOpenAI", return_value=mock_openai),
        patch("agents.synthesizer.embedder.qdrant_client") as mock_qdrant,
    ):
        mock_qdrant.upsert = mock_qdrant_upsert
        result = await embed_and_store([skill_id_1, skill_id_2])

    assert result["embedded"] == 2
    assert result["failed"] == 0
    mock_qdrant_upsert.assert_called_once()


@pytest.mark.asyncio
async def test_embed_and_store_marks_failed_on_openai_error():
    """When OpenAI raises an exception, skills are marked as failed."""
    from agents.synthesizer.embedder import embed_and_store

    skill_id = uuid.uuid4()
    mock_skill = MagicMock()
    mock_skill.id = skill_id
    mock_skill.canonical_name = "kubernetes"
    mock_skill.skill_type = "tool"
    mock_skill.domain = None

    fetch_session = AsyncMock()
    fetch_result = MagicMock()
    fetch_result.scalars.return_value.all.return_value = [mock_skill]
    fetch_session.execute = AsyncMock(return_value=fetch_result)

    update_session = AsyncMock()
    update_session.execute = AsyncMock(return_value=MagicMock())
    update_session.commit = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_session_cm(fetch_session)
        return _make_session_cm(update_session)

    mock_openai = AsyncMock()
    mock_openai.embeddings.create = AsyncMock(side_effect=RuntimeError("API error"))

    with (
        patch("agents.synthesizer.embedder.AsyncSessionLocal", side_effect=_session_factory),
        patch("agents.synthesizer.embedder.AsyncOpenAI", return_value=mock_openai),
        patch("agents.synthesizer.embedder.qdrant_client"),
    ):
        result = await embed_and_store([skill_id])

    assert result["embedded"] == 0
    assert result["failed"] == 1


# ---------------------------------------------------------------------------
# Unit tests — run_extraction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_extraction_no_unprocessed_returns_zeros():
    """Returns zeroed summary when there are no unprocessed postings."""
    from agents.synthesizer.extractor import run_extraction

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch(
        "agents.synthesizer.extractor.AsyncSessionLocal",
        return_value=_make_session_cm(mock_session),
    ):
        result = await run_extraction()

    assert result["processed"] == 0
    assert result["skills_extracted"] == 0
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_run_extraction_marks_posting_processed_on_success():
    """A posting with text is marked processed=True after successful extraction."""
    from agents.synthesizer.extractor import run_extraction

    posting_id = uuid.uuid4()
    mock_posting = MagicMock()
    mock_posting.id = posting_id
    mock_posting.title = "Software Engineer"
    mock_posting.raw_text = "We need Python and Docker skills."
    mock_posting.raw_html = None

    # First session: fetch postings
    fetch_session = AsyncMock()
    fetch_result = MagicMock()
    fetch_result.scalars.return_value.all.return_value = [mock_posting]
    fetch_session.execute = AsyncMock(return_value=fetch_result)

    # Second session: per-posting upsert + mark processed
    process_session = AsyncMock()
    # execute calls: insert skill, flush, select skill_id, insert junction, update posting
    skill_id = uuid.uuid4()
    skill_id_result = MagicMock()
    skill_id_result.scalar_one.return_value = skill_id
    process_session.execute = AsyncMock(return_value=skill_id_result)
    process_session.flush = AsyncMock()
    process_session.commit = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_session_cm(fetch_session)
        return _make_session_cm(process_session)

    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value={"skills": [{"name": "Python", "type": "technical", "context_snippet": "need Python"}]}
    )

    with (
        patch("agents.synthesizer.extractor.AsyncSessionLocal", side_effect=_session_factory),
        patch("agents.synthesizer.extractor._build_extraction_chain", return_value=mock_chain),
        patch("agents.synthesizer.extractor.embed_and_store", new=AsyncMock(return_value={"embedded": 1, "failed": 0})),
    ):
        result = await run_extraction()

    assert result["processed"] == 1
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_run_extraction_marks_extraction_failed_on_error():
    """When the LLM chain raises, the posting is marked extraction_failed=True."""
    from agents.synthesizer.extractor import run_extraction

    posting_id = uuid.uuid4()
    mock_posting = MagicMock()
    mock_posting.id = posting_id
    mock_posting.title = "Data Engineer"
    mock_posting.raw_text = "Some posting text."
    mock_posting.raw_html = None

    fetch_session = AsyncMock()
    fetch_result = MagicMock()
    fetch_result.scalars.return_value.all.return_value = [mock_posting]
    fetch_session.execute = AsyncMock(return_value=fetch_result)

    error_session = AsyncMock()
    error_session.execute = AsyncMock(return_value=MagicMock())
    error_session.commit = AsyncMock()

    fail_mark_session = AsyncMock()
    fail_mark_session.execute = AsyncMock(return_value=MagicMock())
    fail_mark_session.commit = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_session_cm(fetch_session)
        if call_count == 2:
            return _make_session_cm(error_session)
        return _make_session_cm(fail_mark_session)

    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    with (
        patch("agents.synthesizer.extractor.AsyncSessionLocal", side_effect=_session_factory),
        patch("agents.synthesizer.extractor._build_extraction_chain", return_value=mock_chain),
        patch("agents.synthesizer.extractor.embed_and_store", new=AsyncMock(return_value={"embedded": 0, "failed": 0})),
    ):
        result = await run_extraction()

    assert result["processed"] == 0
    assert len(result["errors"]) == 1
    assert result["errors"][0]["posting_id"] == str(posting_id)


@pytest.mark.asyncio
async def test_run_extraction_deduplicates_skills_within_posting():
    """Duplicate skill names within a single posting are inserted only once."""
    from agents.synthesizer.extractor import run_extraction

    posting_id = uuid.uuid4()
    mock_posting = MagicMock()
    mock_posting.id = posting_id
    mock_posting.title = "Engineer"
    mock_posting.raw_text = "Python Python python skills needed."
    mock_posting.raw_html = None

    fetch_session = AsyncMock()
    fetch_result = MagicMock()
    fetch_result.scalars.return_value.all.return_value = [mock_posting]
    fetch_session.execute = AsyncMock(return_value=fetch_result)

    process_session = AsyncMock()
    skill_id = uuid.uuid4()
    skill_id_result = MagicMock()
    skill_id_result.scalar_one.return_value = skill_id
    process_session.execute = AsyncMock(return_value=skill_id_result)
    process_session.flush = AsyncMock()
    process_session.commit = AsyncMock()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_session_cm(fetch_session)
        return _make_session_cm(process_session)

    # Return 3 "python" entries (should dedup to 1)
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value={
            "skills": [
                {"name": "Python", "type": "technical", "context_snippet": "Python"},
                {"name": "python", "type": "technical", "context_snippet": "python"},
                {"name": "PYTHON", "type": "technical", "context_snippet": "PYTHON"},
            ]
        }
    )

    with (
        patch("agents.synthesizer.extractor.AsyncSessionLocal", side_effect=_session_factory),
        patch("agents.synthesizer.extractor._build_extraction_chain", return_value=mock_chain),
        patch("agents.synthesizer.extractor.embed_and_store", new=AsyncMock(return_value={"embedded": 1, "failed": 0})),
    ):
        result = await run_extraction()

    # Only 1 unique skill (python) should be extracted
    assert result["skills_extracted"] == 1


# ---------------------------------------------------------------------------
# Integration tests — admin endpoint auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_synthesize_trigger_rejects_bad_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/synthesize/trigger",
            headers={"X-Admin-Key": "wrong-key"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_synthesize_trigger_missing_key_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/synthesize/trigger")
    assert response.status_code == 422
