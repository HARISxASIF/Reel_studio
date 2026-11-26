from celery import Celery
from app.config import settings

celery_app = Celery(
    "reel_studio",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,      # Bounded task prefetch for heavy media tasks
    task_acks_late=True,                # Acknowledge after completion for failure resilience
    task_reject_on_worker_lost=True,    # Re-queue task if worker crashes
    task_track_started=True,
)

# Auto-discover tasks
celery_app.autodiscover_tasks([
    "app.tasks.pipeline",
    "app.tasks.live_pipeline",
    "app.tasks.social_tasks",
])
