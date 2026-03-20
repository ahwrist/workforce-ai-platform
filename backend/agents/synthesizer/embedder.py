"""Embedding generation and Qdrant upsert for skills."""
import logging
import uuid

from openai import AsyncOpenAI
from qdrant_client.models import PointStruct
from sqlalchemy import select, update

from core.config.settings import get_settings
from core.database.postgres import AsyncSessionLocal
from core.database.qdrant import SKILLS_COLLECTION, qdrant_client
from core.models.skill import Skill

logger = logging.getLogger(__name__)
settings = get_settings()

_EMBED_BATCH_SIZE = 100


async def embed_and_store(skill_ids: list) -> dict:
    """Generate embeddings for the given skill IDs and upsert to Qdrant.

    Only processes skills with embedding_status == 'pending'.
    Updates embedding_status to 'complete' or 'failed' per skill.
    """
    if not skill_ids:
        return {"embedded": 0, "failed": 0}

    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    embedded_count = 0
    failed_count = 0

    # Load pending skills for the given IDs
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Skill).where(
                Skill.id.in_(skill_ids),
                Skill.embedding_status == "pending",
            )
        )
        skills = result.scalars().all()

    if not skills:
        logger.info("Embedder: no pending skills found for %d IDs", len(skill_ids))
        return {"embedded": 0, "failed": 0}

    logger.info("Embedder: embedding %d pending skills", len(skills))

    # Process in batches
    for batch_start in range(0, len(skills), _EMBED_BATCH_SIZE):
        batch = skills[batch_start : batch_start + _EMBED_BATCH_SIZE]
        names = [s.canonical_name for s in batch]

        try:
            response = await openai_client.embeddings.create(
                model=settings.embedding_model,
                input=names,
            )
            vectors = [item.embedding for item in response.data]

            points = [
                PointStruct(
                    id=str(skill.id),
                    vector=vector,
                    payload={
                        "canonical_name": skill.canonical_name,
                        "skill_type": skill.skill_type,
                        "domain": skill.domain,
                    },
                )
                for skill, vector in zip(batch, vectors)
            ]

            await qdrant_client.upsert(
                collection_name=SKILLS_COLLECTION,
                points=points,
            )

            # Mark embedded skills as complete
            batch_ids = [s.id for s in batch]
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(Skill)
                    .where(Skill.id.in_(batch_ids))
                    .values(embedding_status="complete")
                )
                await session.commit()

            embedded_count += len(batch)
            logger.info("Embedder: embedded batch of %d skills", len(batch))

        except Exception as exc:  # noqa: BLE001
            logger.error("Embedder: batch embedding failed: %s", exc)
            batch_ids = [s.id for s in batch]
            try:
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        update(Skill)
                        .where(Skill.id.in_(batch_ids))
                        .values(embedding_status="failed")
                    )
                    await session.commit()
            except Exception as mark_exc:  # noqa: BLE001
                logger.error("Embedder: could not mark batch failed: %s", mark_exc)
            failed_count += len(batch)

    return {"embedded": embedded_count, "failed": failed_count}
