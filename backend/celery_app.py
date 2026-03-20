from celery import Celery
from core.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "workforce_ai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "pipelines.skill_pipeline",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)
