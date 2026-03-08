"""
Intelli-Credit — Celery Task Definitions

Defines registered Celery tasks for parallel document processing.
Each task wraps the corresponding worker's process() method.

When Celery is available:
    - Tasks dispatch to Redis-backed queues
    - Workers run in parallel across replicas
    - Results are staged in Redis for the Consolidator

When Celery is unavailable:
    - Fallback to synchronous execution via dispatch_workers()
    - Same output, just sequential

Usage:
    # Dispatch via Celery
    from backend.workers.tasks import process_document
    result = process_document.delay(session_id, "annual_report", "/path/to/file.pdf")

    # Check result
    result.get(timeout=300)
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from backend.workers.celery_app import celery_app, is_celery_available

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _process_document_async(
    session_id: str, document_type: str, file_path: str,
) -> Dict[str, Any]:
    """
    Core async document processing logic.
    Imports worker class, instantiates, and runs extraction.
    """
    from backend.models.schemas import DocumentType
    from backend.workers.task_registry import get_worker_class

    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        logger.error(f"[Tasks] Unknown document type: {document_type}")
        return {"status": "failed", "error": f"Unknown document type: {document_type}"}

    WorkerClass = get_worker_class(doc_type)
    if not WorkerClass:
        logger.error(f"[Tasks] No worker registered for: {document_type}")
        return {"status": "failed", "error": f"No worker for: {document_type}"}

    worker = WorkerClass(session_id, file_path)
    output = await worker.process()
    return output.model_dump(mode="json")


# ──────────────────────────────────────────────
# Celery Task Definitions
# ──────────────────────────────────────────────

if celery_app is not None:

    @celery_app.task(
        name="backend.workers.tasks.process_document",
        bind=True,
        max_retries=2,
        default_retry_delay=10,
        soft_time_limit=300,
        time_limit=360,
    )
    def process_document(self, session_id: str, document_type: str, file_path: str) -> Dict[str, Any]:
        """
        Generic document processing task.
        Routes to the appropriate worker based on document_type.
        """
        logger.info(f"[Celery] Processing {document_type} for session {session_id}")
        try:
            return _run_async(_process_document_async(session_id, document_type, file_path))
        except Exception as exc:
            logger.error(f"[Celery] Task failed: {exc}")
            raise self.retry(exc=exc)

    # ── Specific task aliases for routing ──

    @celery_app.task(name="backend.workers.tasks.process_annual_report", bind=True, max_retries=2)
    def process_annual_report(self, session_id: str, file_path: str) -> Dict[str, Any]:
        logger.info(f"[Celery:W1] Annual Report for {session_id}")
        try:
            return _run_async(_process_document_async(session_id, "annual_report", file_path))
        except Exception as exc:
            raise self.retry(exc=exc)

    @celery_app.task(name="backend.workers.tasks.process_bank_statement", bind=True, max_retries=2)
    def process_bank_statement(self, session_id: str, file_path: str) -> Dict[str, Any]:
        logger.info(f"[Celery:W2] Bank Statement for {session_id}")
        try:
            return _run_async(_process_document_async(session_id, "bank_statement", file_path))
        except Exception as exc:
            raise self.retry(exc=exc)

    @celery_app.task(name="backend.workers.tasks.process_gst_returns", bind=True, max_retries=2)
    def process_gst_returns(self, session_id: str, file_path: str) -> Dict[str, Any]:
        logger.info(f"[Celery:W3] GST Returns for {session_id}")
        try:
            return _run_async(_process_document_async(session_id, "gst_returns", file_path))
        except Exception as exc:
            raise self.retry(exc=exc)

    @celery_app.task(name="backend.workers.tasks.process_itr", bind=True, max_retries=2)
    def process_itr(self, session_id: str, file_path: str) -> Dict[str, Any]:
        logger.info(f"[Celery:W4] ITR for {session_id}")
        try:
            return _run_async(_process_document_async(session_id, "itr", file_path))
        except Exception as exc:
            raise self.retry(exc=exc)

    @celery_app.task(name="backend.workers.tasks.process_legal_notice", bind=True, max_retries=2)
    def process_legal_notice(self, session_id: str, file_path: str) -> Dict[str, Any]:
        logger.info(f"[Celery:W5] Legal Notice for {session_id}")
        try:
            return _run_async(_process_document_async(session_id, "legal_notice", file_path))
        except Exception as exc:
            raise self.retry(exc=exc)

    @celery_app.task(name="backend.workers.tasks.process_board_minutes", bind=True, max_retries=2)
    def process_board_minutes(self, session_id: str, file_path: str) -> Dict[str, Any]:
        logger.info(f"[Celery:W6] Board Minutes for {session_id}")
        try:
            return _run_async(_process_document_async(session_id, "board_minutes", file_path))
        except Exception as exc:
            raise self.retry(exc=exc)

    @celery_app.task(name="backend.workers.tasks.process_shareholding", bind=True, max_retries=2)
    def process_shareholding(self, session_id: str, file_path: str) -> Dict[str, Any]:
        logger.info(f"[Celery:W7] Shareholding for {session_id}")
        try:
            return _run_async(_process_document_async(session_id, "shareholding_pattern", file_path))
        except Exception as exc:
            raise self.retry(exc=exc)

    @celery_app.task(name="backend.workers.tasks.process_rating_report", bind=True, max_retries=2)
    def process_rating_report(self, session_id: str, file_path: str) -> Dict[str, Any]:
        logger.info(f"[Celery:W8] Rating Report for {session_id}")
        try:
            return _run_async(_process_document_async(session_id, "rating_report", file_path))
        except Exception as exc:
            raise self.retry(exc=exc)


# ──────────────────────────────────────────────
# Dispatch Helper — Celery or Synchronous
# ──────────────────────────────────────────────

# Map document_type → specific task name
_TASK_MAP = {
    "annual_report": "backend.workers.tasks.process_annual_report",
    "bank_statement": "backend.workers.tasks.process_bank_statement",
    "gst_returns": "backend.workers.tasks.process_gst_returns",
    "itr": "backend.workers.tasks.process_itr",
    "legal_notice": "backend.workers.tasks.process_legal_notice",
    "board_minutes": "backend.workers.tasks.process_board_minutes",
    "shareholding_pattern": "backend.workers.tasks.process_shareholding",
    "rating_report": "backend.workers.tasks.process_rating_report",
}


def dispatch_celery_task(
    session_id: str, document_type: str, file_path: str,
) -> Optional[Any]:
    """
    Dispatch a document processing task via Celery.

    Returns the AsyncResult if Celery is available, None otherwise.
    Falls back to None — caller should use synchronous fallback.
    """
    if not is_celery_available():
        logger.info("[Tasks] Celery unavailable, caller should use sync fallback")
        return None

    task_name = _TASK_MAP.get(document_type)
    if task_name:
        return celery_app.send_task(task_name, args=[session_id, file_path])
    else:
        # Use generic task
        return celery_app.send_task(
            "backend.workers.tasks.process_document",
            args=[session_id, document_type, file_path],
        )


async def dispatch_all_documents(
    session_id: str, documents: list,
) -> Dict[str, Any]:
    """
    Dispatch all documents for a session — Celery parallel or sync fallback.

    Args:
        session_id: Pipeline session ID
        documents: List of dicts with 'document_type' and 'file_path'

    Returns:
        If Celery: dict of {doc_type: AsyncResult}
        If sync: dict of {worker_id: WorkerOutput dict}
    """
    if is_celery_available():
        # Dispatch all tasks in parallel via Celery
        results = {}
        for doc in documents:
            doc_type = doc.get("document_type", "")
            file_path = doc.get("file_path", "")
            async_result = dispatch_celery_task(session_id, doc_type, file_path)
            if async_result:
                results[doc_type] = async_result
                logger.info(f"[Tasks] Dispatched {doc_type} → Celery task {async_result.id}")
        return results
    else:
        # Synchronous fallback
        logger.info("[Tasks] Using synchronous fallback for all documents")
        results = {}
        for doc in documents:
            doc_type = doc.get("document_type", "")
            file_path = doc.get("file_path", "")
            output = await _process_document_async(session_id, doc_type, file_path)
            results[doc_type] = output
        return results
