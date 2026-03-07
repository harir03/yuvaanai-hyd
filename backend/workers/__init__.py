"""
Intelli-Credit — Document Workers Package

8 parallel document workers (W1–W8) for extracting structured data
from corporate loan documents.

T0: W1 (Annual Report), W2 (Bank Statement), W3 (GST Returns) implemented.
T1+: W4–W8 to follow.
"""

from backend.workers.task_registry import (
    dispatch_workers,
    get_worker_class,
    get_worker_id,
    list_registered_workers,
    WORKER_REGISTRY,
)
from backend.workers.base_worker import BaseDocumentWorker

__all__ = [
    "dispatch_workers",
    "get_worker_class",
    "get_worker_id",
    "list_registered_workers",
    "WORKER_REGISTRY",
    "BaseDocumentWorker",
]

