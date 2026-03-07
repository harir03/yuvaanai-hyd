"""
Intelli-Credit — LangGraph Node: Workers

Dispatches parallel document workers for processing.
Uses Celery workers when available, falls back to synchronous execution.
Worker outputs are staged in Redis for the Consolidator node.
"""

import logging
from backend.graph.state import CreditAppraisalState
from backend.models.schemas import (
    PipelineStageStatus,
    PipelineStageEnum,
    WorkerStatusEnum,
    WorkerStatus,
)
from backend.thinking.event_emitter import ThinkingEventEmitter
from backend.workers.task_registry import dispatch_workers, get_worker_id

logger = logging.getLogger(__name__)


async def workers_node(state: CreditAppraisalState) -> dict:
    """
    Stage 1 — Parallel Document Workers.

    Dispatches workers for each uploaded document.
    Each worker parses one document type and stages output in Redis.

    Flow:
        1. Emit thinking events
        2. Build document list from state
        3. Dispatch workers (Celery or sync fallback)
        4. Collect results
        5. Update pipeline stage status
    """
    emitter = ThinkingEventEmitter(state.session_id, "Pipeline — Worker Dispatcher")

    await emitter.read(
        f"Preparing to process {len(state.documents)} documents for "
        f"{state.company.name if state.company else 'Unknown Company'}"
    )

    # Update pipeline stage to active
    for stage in state.pipeline_stages:
        if stage.stage == PipelineStageEnum.WORKERS:
            stage.status = PipelineStageStatus.ACTIVE
            stage.message = f"Processing {len(state.documents)} documents in parallel"

    # Build document dispatch list
    doc_list = []
    worker_statuses = []
    for doc in state.documents:
        doc_type = doc.document_type
        doc_list.append({
            "document_type": doc_type,
            "file_path": doc.file_path if hasattr(doc, "file_path") and doc.file_path else "",
        })
        worker_statuses.append(WorkerStatus(
            worker_id=get_worker_id(doc_type),
            document_type=doc_type,
            status=WorkerStatusEnum.PROCESSING,
            progress=0,
            current_task=f"Starting {doc_type.value if hasattr(doc_type, 'value') else doc_type}...",
        ))

    await emitter.found(
        f"Dispatching {len(doc_list)} workers: "
        + ", ".join(d.get("document_type", "?").value if hasattr(d.get("document_type", ""), "value") else str(d.get("document_type", "?")) for d in doc_list)
    )

    # Dispatch workers (synchronous fallback for hackathon)
    worker_outputs = await dispatch_workers(state.session_id, doc_list)

    # Update worker statuses based on results
    completed = 0
    failed = 0
    for ws in worker_statuses:
        output = worker_outputs.get(ws.worker_id)
        if output and output.status == "completed":
            ws.status = WorkerStatusEnum.COMPLETED
            ws.progress = 100
            ws.pages_processed = output.pages_processed
            ws.current_task = f"Done: {output.pages_processed} pages, confidence {output.confidence:.0%}"
            completed += 1
        elif output and output.status == "failed":
            ws.status = WorkerStatusEnum.FAILED
            ws.progress = 0
            ws.error = ", ".join(output.errors)
            ws.current_task = "Failed"
            failed += 1
        elif output and output.status == "skipped":
            ws.status = WorkerStatusEnum.QUEUED
            ws.current_task = "Worker not yet implemented"

    # Update pipeline stage
    for stage_obj in state.pipeline_stages:
        if stage_obj.stage == PipelineStageEnum.WORKERS:
            if failed > 0 and completed == 0:
                stage_obj.status = PipelineStageStatus.FAILED
                stage_obj.message = f"All {failed} workers failed"
            else:
                stage_obj.status = PipelineStageStatus.COMPLETED
                stage_obj.message = f"{completed} completed, {failed} failed out of {len(doc_list)}"

    await emitter.concluding(
        f"Worker dispatch complete: {completed} succeeded, {failed} failed"
    )

    return {
        "worker_outputs": worker_outputs,
        "workers_completed": completed,
        "workers_total": len(doc_list),
        "workers": worker_statuses,
        "pipeline_stages": state.pipeline_stages,
    }
