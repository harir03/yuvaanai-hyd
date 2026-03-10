"""
Intelli-Credit — Celery Application Configuration

Configures the Celery app for parallel document processing.
Falls back to synchronous execution when Celery/Redis is unavailable.

Usage:
    # With Celery + Redis
    celery -A backend.workers.celery_app worker --loglevel=info

    # Without Celery (synchronous fallback)
    from backend.workers.celery_app import run_worker_task
    result = await run_worker_task("W1", session_id, doc_path)
"""

import os
import logging
from typing import Optional

from kombu import Queue

logger = logging.getLogger(__name__)

# Try to import Celery — fall back gracefully if not available / no broker
_celery_available = False
celery_app = None

try:
    from celery import Celery

    broker_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    result_backend = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    celery_app = Celery(
        "intelli_credit",
        broker=broker_url,
        backend=result_backend,
        include=["backend.workers.tasks"],
    )

    celery_app.conf.update(
        # Task serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",

        # Timeouts and retries
        task_soft_time_limit=300,      # 5 min soft limit
        task_time_limit=360,           # 6 min hard limit
        task_acks_late=True,           # Ack after completion (reliability)
        worker_prefetch_multiplier=1,  # One task per worker (fairness)

        # Task routing — each worker type gets its own queue
        task_default_queue="workers",
        task_queues=(Queue("workers"),),
        task_routes={
            "backend.workers.tasks.process_annual_report": {"queue": "workers"},
            "backend.workers.tasks.process_bank_statement": {"queue": "workers"},
            "backend.workers.tasks.process_gst_returns": {"queue": "workers"},
            "backend.workers.tasks.process_itr": {"queue": "workers"},
            "backend.workers.tasks.process_legal_notice": {"queue": "workers"},
            "backend.workers.tasks.process_board_minutes": {"queue": "workers"},
            "backend.workers.tasks.process_shareholding": {"queue": "workers"},
            "backend.workers.tasks.process_rating_report": {"queue": "workers"},
        },

        # Retry policy
        task_default_retry_delay=10,
        task_max_retries=2,
    )

    _celery_available = True
    logger.info("[Celery] App configured with broker: %s", broker_url)

except ImportError:
    logger.warning("[Celery] Celery not installed, using synchronous fallback")
except Exception as e:
    logger.warning(f"[Celery] Configuration failed ({e}), using synchronous fallback")


def is_celery_available() -> bool:
    """Check if Celery is properly configured and available."""
    return _celery_available and celery_app is not None
