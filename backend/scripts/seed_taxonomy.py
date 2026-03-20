"""Seed the canonical taxonomy from taxonomy.yaml into the skills table.

For each domain in taxonomy.yaml, inserts all canonical_anchor skills with
their domain pre-classified. Idempotent: skips existing canonical names.
"""
import asyncio
import logging
import sys
import uuid
from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

sys.path.insert(0, "/app")
from core.config.settings import get_settings

logger = logging.getLogger(__name__)


async def seed() -> None:
    taxonomy_path = Path(__file__).parent.parent / "agents" / "taxonomist" / "taxonomy.yaml"
    with open(taxonomy_path) as f:
        taxonomy = yaml.safe_load(f)

    domains = taxonomy.get("domains", {})
    logger.info(f"Taxonomy loaded: {len(domains)} domains — {list(domains.keys())}")

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    inserted = 0
    skipped = 0

    async with SessionLocal() as session:
        for domain_key, domain_data in domains.items():
            anchors = domain_data.get("canonical_anchors", [])
            logger.info(
                f"  Domain '{domain_key}' ({domain_data.get('label', domain_key)}): "
                f"{len(anchors)} canonical anchors"
            )
            for anchor_name in anchors:
                # Upsert: insert if canonical_name doesn't exist, skip otherwise
                result = await session.execute(
                    text("SELECT id FROM skills WHERE canonical_name = :name"),
                    {"name": anchor_name},
                )
                existing = result.fetchone()
                if existing:
                    skipped += 1
                    continue

                skill_id = uuid.uuid4()
                await session.execute(
                    text(
                        """
                        INSERT INTO skills (
                            id, canonical_name, domain, skill_type,
                            low_confidence, embedding_status, aliases
                        ) VALUES (
                            :id, :canonical_name, :domain, 'technical',
                            false, 'pending', ARRAY[]::text[]
                        )
                        """
                    ),
                    {
                        "id": str(skill_id),
                        "canonical_name": anchor_name,
                        "domain": domain_key,
                    },
                )
                inserted += 1

        await session.commit()

    await engine.dispose()
    logger.info(f"Seed complete: {inserted} skills inserted, {skipped} already existed.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    asyncio.run(seed())
