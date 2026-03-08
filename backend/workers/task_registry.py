"""
Intelli-Credit — Worker Task Registry

Maps DocumentType → Worker class.
Provides dispatch functions for both Celery (async) and
synchronous fallback execution.

Usage:
    # Get worker class for a document type
    WorkerClass = get_worker_class(DocumentType.ANNUAL_REPORT)

    # Dispatch all documents for a session
    results = await dispatch_workers(session_id, documents)
"""

import logging
from typing import Dict, Type, List, Optional

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker
from backend.workers.w1_annual_report import AnnualReportWorker
from backend.workers.w2_bank_statement import BankStatementWorker
from backend.workers.w3_gst_returns import GSTReturnsWorker
from backend.workers.w4_itr import ITRWorker
from backend.workers.w5_legal_notice import LegalNoticeWorker
from backend.workers.w6_board_minutes import BoardMinutesWorker
from backend.workers.w7_shareholding import ShareholdingWorker
from backend.workers.w8_rating_report import RatingReportWorker
from backend.graph.state import WorkerOutput

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Worker Registry — maps DocumentType → Worker class
# ──────────────────────────────────────────────

WORKER_REGISTRY: Dict[DocumentType, Type[BaseDocumentWorker]] = {
    DocumentType.ANNUAL_REPORT: AnnualReportWorker,
    DocumentType.BANK_STATEMENT: BankStatementWorker,
    DocumentType.GST_RETURNS: GSTReturnsWorker,
    DocumentType.ITR: ITRWorker,
    DocumentType.LEGAL_NOTICE: LegalNoticeWorker,
    DocumentType.BOARD_MINUTES: BoardMinutesWorker,
    DocumentType.SHAREHOLDING_PATTERN: ShareholdingWorker,
    DocumentType.RATING_REPORT: RatingReportWorker,
}


def get_worker_class(doc_type: DocumentType) -> Optional[Type[BaseDocumentWorker]]:
    """Get the worker class for a given document type."""
    return WORKER_REGISTRY.get(doc_type)


def get_worker_id(doc_type: DocumentType) -> str:
    """Get the worker ID for a given document type."""
    worker_cls = WORKER_REGISTRY.get(doc_type)
    if worker_cls:
        return worker_cls.worker_id
    return f"W?-{doc_type.value}"


def list_registered_workers() -> List[str]:
    """List all registered worker IDs."""
    return [cls.worker_id for cls in WORKER_REGISTRY.values()]


async def dispatch_workers(
    session_id: str,
    documents: List[dict],
) -> Dict[str, WorkerOutput]:
    """
    Dispatch workers for all documents in a session.

    This is the SYNCHRONOUS FALLBACK executor — runs workers sequentially.
    In production with Celery, workers run in parallel via Celery tasks.

    For hackathon demo, this executes each worker's process() directly.

    Args:
        session_id: Pipeline session ID
        documents: List of dicts with 'document_type' and 'file_path' keys. 
                   Each 'document_type' should be a DocumentType enum value or string.

    Returns:
        Dict mapping worker_id → WorkerOutput
    """
    results: Dict[str, WorkerOutput] = {}

    for doc in documents:
        doc_type_raw = doc.get("document_type", "")
        file_path = doc.get("file_path", "")

        # Resolve DocumentType
        if isinstance(doc_type_raw, DocumentType):
            doc_type = doc_type_raw
        else:
            try:
                doc_type = DocumentType(doc_type_raw)
            except ValueError:
                logger.warning(f"[Registry] Unknown document type: {doc_type_raw}")
                continue

        worker_cls = get_worker_class(doc_type)

        if worker_cls is None:
            logger.warning(
                f"[Registry] No worker registered for {doc_type.value}, skipping"
            )
            # Create a stub output so we know it was skipped
            results[f"W?-{doc_type.value}"] = WorkerOutput(
                worker_id=f"W?-{doc_type.value}",
                document_type=doc_type.value,
                status="skipped",
                errors=[f"No worker implemented for {doc_type.value}"],
            )
            continue

        # Instantiate and run
        worker = worker_cls(session_id, file_path)
        logger.info(f"[Registry] Dispatching {worker.worker_id} for {doc_type.value}")

        output = await worker.process()
        results[worker.worker_id] = output
        logger.info(
            f"[Registry] {worker.worker_id} finished: status={output.status}, "
            f"confidence={output.confidence:.2f}"
        )

    return results
