from celery import Celery
from auditmind.config import settings

celery_app = Celery(
    "auditmind",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["auditmind.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,
    task_soft_time_limit=840,       # 14 min — sends SoftTimeLimitExceeded
    task_time_limit=900,            # 15 min — hard kill
    worker_concurrency=2,
    worker_prefetch_multiplier=1,
)