"""Model smoke tests — verify all 7 ORM models and the migrations are correct.

These tests hit the real PostgreSQL database (no mocks) to confirm:
- All 7 tables exist and accept basic INSERT/SELECT round-trips
- Foreign key relationships are enforced
- PostgreSQL-specific column types (ARRAY, JSONB) work correctly
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config.settings import get_settings
from core.models import (
    JobPosting,
    JobPostingSkill,
    Skill,
    SurveyExtraction,
    SurveyMessage,
    SurveySession,
    User,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _make_session() -> AsyncSession:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return SessionLocal(), engine


# ── Table existence ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_seven_tables_exist():
    """Confirm all 7 expected tables are present in the database."""
    session, engine = await _make_session()
    expected = {
        "users",
        "job_postings",
        "skills",
        "job_posting_skills",
        "survey_sessions",
        "survey_messages",
        "survey_extractions",
    }
    try:
        result = await session.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename != 'alembic_version'"
            )
        )
        actual = {row[0] for row in result.fetchall()}
        assert expected == actual, (
            f"Table mismatch. Missing: {expected - actual}, Extra: {actual - expected}"
        )
    finally:
        await session.close()
        await engine.dispose()


# ── Skill model (ARRAY column) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_skill_insert_and_select():
    """Skill inserts with ARRAY column and is retrievable by canonical_name."""
    session, engine = await _make_session()
    try:
        skill = Skill(
            canonical_name=f"TestSkill-{uuid.uuid4().hex[:8]}",
            skill_type="technical",
            domain="software_engineering",
            subdomain="backend_development",
            aliases=["test-skill", "testskill"],
        )
        session.add(skill)
        await session.flush()

        result = await session.get(Skill, skill.id)
        assert result is not None
        assert result.canonical_name == skill.canonical_name
        assert result.aliases == ["test-skill", "testskill"]
        assert result.embedding_status == "pending"
        assert result.low_confidence is False

        await session.rollback()
    finally:
        await session.close()
        await engine.dispose()


# ── JobPosting model ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_job_posting_insert():
    """JobPosting inserts correctly with required fields."""
    session, engine = await _make_session()
    try:
        posting = JobPosting(
            company="TestCo",
            title="Senior Engineer",
            url=f"https://example.com/jobs/{uuid.uuid4().hex}",
            source="greenhouse",
        )
        session.add(posting)
        await session.flush()

        result = await session.get(JobPosting, posting.id)
        assert result is not None
        assert result.processed is False
        assert result.extraction_failed is False

        await session.rollback()
    finally:
        await session.close()
        await engine.dispose()


# ── User model ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_insert():
    """User inserts with unique email."""
    session, engine = await _make_session()
    try:
        user = User(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Test User",
        )
        session.add(user)
        await session.flush()

        result = await session.get(User, user.id)
        assert result is not None
        assert result.is_active is True
        assert result.is_admin is False

        await session.rollback()
    finally:
        await session.close()
        await engine.dispose()


# ── SurveyExtraction JSONB columns ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_survey_extraction_jsonb():
    """SurveyExtraction accepts JSONB arrays and dicts."""
    session, engine = await _make_session()
    try:
        survey_session = SurveySession(status="completed")
        session.add(survey_session)
        await session.flush()

        extraction = SurveyExtraction(
            session_id=survey_session.id,
            self_reported_role="Data Engineer",
            self_reported_domain="data_and_ai",
            current_tools=["dbt", "Spark", "Airflow"],
            upskilling_goals=["LLMs", "MLOps"],
            key_themes=["automation anxiety", "AI tooling"],
            raw_llm_extraction={"confidence": 0.92, "model": "claude-sonnet-4-6"},
        )
        session.add(extraction)
        await session.flush()

        result = await session.get(SurveyExtraction, extraction.id)
        assert result is not None
        assert result.current_tools == ["dbt", "Spark", "Airflow"]
        assert result.raw_llm_extraction["model"] == "claude-sonnet-4-6"

        await session.rollback()
    finally:
        await session.close()
        await engine.dispose()


# ── FK relationship: job_posting_skills ───────────────────────────────────────

@pytest.mark.asyncio
async def test_job_posting_skill_relationship():
    """JobPostingSkill links a posting and skill via FK."""
    session, engine = await _make_session()
    try:
        posting = JobPosting(
            company="FKTestCo",
            title="ML Engineer",
            url=f"https://fk-test.com/jobs/{uuid.uuid4().hex}",
            source="lever",
        )
        skill = Skill(canonical_name=f"PyTorch-{uuid.uuid4().hex[:6]}", domain="data_and_ai")
        session.add_all([posting, skill])
        await session.flush()

        link = JobPostingSkill(
            job_posting_id=posting.id,
            skill_id=skill.id,
            context_snippet="Proficiency with PyTorch required.",
        )
        session.add(link)
        await session.flush()

        result = await session.get(JobPostingSkill, link.id)
        assert result is not None
        assert result.job_posting_id == posting.id
        assert result.skill_id == skill.id

        await session.rollback()
    finally:
        await session.close()
        await engine.dispose()


# ── FK relationship: survey messages ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_survey_message_relationship():
    """SurveyMessage is linked to a SurveySession via FK."""
    session, engine = await _make_session()
    try:
        survey_session = SurveySession(status="active", turn_count=1)
        session.add(survey_session)
        await session.flush()

        msg = SurveyMessage(
            session_id=survey_session.id,
            role="user",
            content="I work in data engineering.",
            turn_number=1,
        )
        session.add(msg)
        await session.flush()

        result = await session.get(SurveyMessage, msg.id)
        assert result is not None
        assert result.role == "user"
        assert result.session_id == survey_session.id

        await session.rollback()
    finally:
        await session.close()
        await engine.dispose()


# ── Seed verification ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_taxonomy_populated_skills():
    """Confirm seed_taxonomy.py inserted skills for all 6 domains."""
    session, engine = await _make_session()
    try:
        result = await session.execute(
            text("SELECT domain, COUNT(*) FROM skills GROUP BY domain ORDER BY domain")
        )
        rows = {row[0]: row[1] for row in result.fetchall()}
        expected_domains = {
            "software_engineering",
            "data_and_ai",
            "product_management",
            "design_and_ux",
            "go_to_market",
            "operations",
        }
        assert expected_domains == set(rows.keys()), f"Domain mismatch: {rows}"
        for domain, count in rows.items():
            assert count >= 1, f"Domain '{domain}' has no seeded skills"
    finally:
        await session.close()
        await engine.dispose()
