"""Synthesizer agent — LLM skill extraction from job postings."""
import logging
import re
import uuid

from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.config.settings import get_settings
from core.database.postgres import AsyncSessionLocal
from core.models.job_posting import JobPosting
from core.models.skill import JobPostingSkill, Skill
from agents.synthesizer.embedder import embed_and_store

logger = logging.getLogger(__name__)
settings = get_settings()

_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are a skill extraction engine. Given a job posting, return a JSON object with a "
            "'skills' array. Each element must have exactly three fields:\n"
            "  'name': the skill name (string)\n"
            "  'type': one of: technical, tool, methodology, soft (string)\n"
            "  'context_snippet': a short excerpt from the posting mentioning the skill (string, max 100 chars)\n"
            "Extract only concrete, specific skills — not vague personality traits. "
            "Return only valid JSON, no commentary, no markdown fences."
        ),
    ),
    ("human", "Job title: {title}\n\nPosting text:\n{text}"),
])


def _normalize_name(name: str) -> str:
    """Lowercase, strip whitespace, collapse multiple spaces."""
    name = name.lower().strip()
    name = re.sub(r"\s+", " ", name)
    return name


def _build_extraction_chain():
    """Build LangChain extraction chain. Separated for testability."""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.output_parsers import JsonOutputParser

    llm = ChatAnthropic(
        model=settings.synthesizer_model,
        api_key=settings.anthropic_api_key,
        temperature=0,
    )
    return _EXTRACTION_PROMPT | llm | JsonOutputParser()


async def run_extraction() -> dict:
    """Extract skills from all unprocessed job postings."""
    chain = _build_extraction_chain()
    processed_count = 0
    skills_extracted = 0
    errors: list[dict] = []
    new_skill_ids: list[uuid.UUID] = []

    # Fetch all unprocessed, non-failed postings up front
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(JobPosting).where(
                JobPosting.processed.is_(False),
                JobPosting.extraction_failed.is_(False),
            )
        )
        postings = result.scalars().all()

    logger.info("Synthesizer: found %d unprocessed postings", len(postings))

    for posting in postings:
        try:
            text = posting.raw_text or ""
            if not text and posting.raw_html:
                text = re.sub(r"<[^>]+>", " ", posting.raw_html)
                text = re.sub(r"\s+", " ", text).strip()

            async with AsyncSessionLocal() as session:
                if not text:
                    logger.warning("Posting %s has no text, marking processed", posting.id)
                    await session.execute(
                        update(JobPosting)
                        .where(JobPosting.id == posting.id)
                        .values(processed=True)
                    )
                    await session.commit()
                    processed_count += 1
                    continue

                truncated = text[:8000]
                raw = await chain.ainvoke({"title": posting.title, "text": truncated})
                extracted = raw.get("skills", []) if isinstance(raw, dict) else []

                seen_names: set[str] = set()
                posting_skill_count = 0

                for item in extracted:
                    raw_name = item.get("name", "").strip()
                    if not raw_name:
                        continue
                    normalized = _normalize_name(raw_name)
                    if not normalized or normalized in seen_names:
                        continue
                    seen_names.add(normalized)

                    skill_type = item.get("type", "technical")
                    context_snippet = (item.get("context_snippet") or "")[:500]

                    # Upsert skill — ON CONFLICT DO NOTHING on canonical_name
                    aliases = [raw_name] if raw_name != normalized else []
                    insert_stmt = (
                        pg_insert(Skill)
                        .values(
                            id=uuid.uuid4(),
                            canonical_name=normalized,
                            skill_type=skill_type,
                            aliases=aliases,
                        )
                        .on_conflict_do_nothing(index_elements=["canonical_name"])
                    )
                    await session.execute(insert_stmt)
                    await session.flush()

                    # Retrieve skill ID (whether newly inserted or pre-existing)
                    skill_row = await session.execute(
                        select(Skill.id).where(Skill.canonical_name == normalized)
                    )
                    skill_id: uuid.UUID = skill_row.scalar_one()

                    if skill_id not in new_skill_ids:
                        new_skill_ids.append(skill_id)

                    # Junction row — simple insert (no unique constraint to rely on)
                    junction_stmt = (
                        pg_insert(JobPostingSkill)
                        .values(
                            id=uuid.uuid4(),
                            job_posting_id=posting.id,
                            skill_id=skill_id,
                            context_snippet=context_snippet,
                        )
                        .on_conflict_do_nothing()
                    )
                    await session.execute(junction_stmt)
                    posting_skill_count += 1

                await session.execute(
                    update(JobPosting)
                    .where(JobPosting.id == posting.id)
                    .values(processed=True)
                )
                await session.commit()

            skills_extracted += posting_skill_count
            processed_count += 1
            logger.info(
                "Synthesizer: processed posting %s — %d skills",
                posting.id,
                posting_skill_count,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("Synthesizer: failed posting %s: %s", posting.id, exc)
            errors.append({"posting_id": str(posting.id), "error": str(exc)})
            try:
                async with AsyncSessionLocal() as err_session:
                    await err_session.execute(
                        update(JobPosting)
                        .where(JobPosting.id == posting.id)
                        .values(extraction_failed=True)
                    )
                    await err_session.commit()
            except Exception as mark_exc:  # noqa: BLE001
                logger.error("Synthesizer: could not mark posting %s failed: %s", posting.id, mark_exc)

    if new_skill_ids:
        embed_result = await embed_and_store(new_skill_ids)
        logger.info("Synthesizer: embed_and_store result: %s", embed_result)

    return {
        "processed": processed_count,
        "skills_extracted": skills_extracted,
        "errors": errors,
    }
