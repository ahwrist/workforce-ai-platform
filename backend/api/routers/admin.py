"""Admin router — manually trigger pipeline agents.

All endpoints require the X-Admin-Key header matching settings.admin_api_key.
"""
import logging

from fastapi import APIRouter, Header, HTTPException, status

from core.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _verify_admin_key(x_admin_key: str) -> None:
    """Raise 403 if the provided key does not match the configured admin API key."""
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin API key",
        )


@router.post("/harvest/trigger")
async def trigger_harvest(x_admin_key: str = Header(...)):
    """Manually enqueue the Harvester agent via Celery."""
    _verify_admin_key(x_admin_key)
    try:
        from pipelines.skill_pipeline import harvest_new_postings  # noqa: PLC0415
        result = harvest_new_postings.delay()
        logger.info("Admin triggered harvest: task_id=%s", result.id)
        return {
            "data": {"message": "Harvest enqueued", "task_id": result.id},
            "meta": {"version": "1.0"},
            "error": None,
        }
    except Exception as exc:
        logger.error("Failed to enqueue harvest: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to enqueue harvest task: {exc}",
        )


@router.post("/synthesize/trigger")
async def trigger_synthesize(x_admin_key: str = Header(...)):
    """Manually enqueue the Synthesizer agent via Celery."""
    _verify_admin_key(x_admin_key)
    try:
        from pipelines.skill_pipeline import extract_skills_from_postings  # noqa: PLC0415
        result = extract_skills_from_postings.delay()
        logger.info("Admin triggered extraction: task_id=%s", result.id)
        return {
            "data": {"message": "Synthesis enqueued", "task_id": result.id},
            "meta": {"version": "1.0"},
            "error": None,
        }
    except Exception as exc:
        logger.error("Failed to enqueue synthesis: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to enqueue synthesis task: {exc}",
        )


@router.post("/classify/trigger")
async def trigger_classify(x_admin_key: str = Header(...)):
    """Manually enqueue the Taxonomist agent via Celery."""
    _verify_admin_key(x_admin_key)
    try:
        from pipelines.skill_pipeline import classify_and_deduplicate  # noqa: PLC0415
        result = classify_and_deduplicate.delay()
        logger.info("Admin triggered classification: task_id=%s", result.id)
        return {
            "data": {"message": "Classification enqueued", "task_id": result.id},
            "meta": {"version": "1.0"},
            "error": None,
        }
    except Exception as exc:
        logger.error("Failed to enqueue classification: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to enqueue classification task: {exc}",
        )
