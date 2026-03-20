from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from core.config.settings import get_settings

settings = get_settings()

qdrant_client = AsyncQdrantClient(url=settings.qdrant_url)

SKILLS_COLLECTION = "skills"
SURVEY_SESSIONS_COLLECTION = "survey_sessions"

SKILLS_VECTOR_SIZE = 1536  # text-embedding-3-small dimensions


async def ensure_collections() -> None:
    """Create Qdrant collections if they don't exist."""
    existing = await qdrant_client.get_collections()
    existing_names = {c.name for c in existing.collections}

    if SKILLS_COLLECTION not in existing_names:
        await qdrant_client.create_collection(
            collection_name=SKILLS_COLLECTION,
            vectors_config=VectorParams(size=SKILLS_VECTOR_SIZE, distance=Distance.COSINE),
        )

    if SURVEY_SESSIONS_COLLECTION not in existing_names:
        await qdrant_client.create_collection(
            collection_name=SURVEY_SESSIONS_COLLECTION,
            vectors_config=VectorParams(size=SKILLS_VECTOR_SIZE, distance=Distance.COSINE),
        )
