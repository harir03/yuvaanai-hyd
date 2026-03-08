"""
Intelli-Credit — Pipeline Route

POST /api/pipeline/{session_id}/run — Trigger pipeline execution for a session.
GET  /api/pipeline/{session_id}/status — Get detailed pipeline status.
POST /api/pipeline/{session_id}/cancel — Cancel a running pipeline.

The pipeline run is dispatched as a background task so the API returns
immediately. Progress is tracked via the assessments_store and
streamed to clients via WebSocket.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status

from backend.api.auth.jwt_handler import optional_auth

from backend.models.schemas import (
    AssessmentSummary,
    AssessmentOutcome,
    PipelineStageStatus,
    ScoreBand,
)
from backend.api.routes._store import assessments_store
from backend.graph.orchestrator import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"], dependencies=[Depends(optional_auth)])

# Track running pipelines so we can prevent double-starts
_running_pipelines: dict[str, bool] = {}


async def _execute_pipeline(session_id: str) -> None:
    """
    Background task: run the LangGraph pipeline and update the store.

    This is the integration glue between the API layer and the orchestrator.
    It reads the session from the store, runs the pipeline, and writes
    the results back to the store.
    """
    assessment = assessments_store.get(session_id)
    if not assessment:
        logger.error(f"[Pipeline] Session {session_id} not found in store")
        return

    _running_pipelines[session_id] = True
    logger.info(f"[Pipeline] Starting execution for {session_id}")

    try:
        # Mark first processing stage as active
        for stage in assessment.pipeline_stages:
            if stage.status == PipelineStageStatus.PENDING:
                stage.status = PipelineStageStatus.ACTIVE
                stage.started_at = datetime.utcnow()
                break

        assessment.outcome = AssessmentOutcome.PENDING

        # Run the full LangGraph pipeline
        final_state = await run_pipeline(
            session_id=session_id,
            company=assessment.company,
            documents=assessment.documents,
        )

        # Extract results from final state dict (LangGraph returns dict)
        state_dict = final_state if isinstance(final_state, dict) else final_state.__dict__

        # Update assessment with pipeline results
        assessment.score = state_dict.get("score")
        assessment.score_band = state_dict.get("score_band")
        assessment.outcome = state_dict.get("outcome", AssessmentOutcome.PENDING)
        assessment.cam_path = state_dict.get("cam_path")

        # Update pipeline stages from state
        state_stages = state_dict.get("pipeline_stages", [])
        if state_stages:
            assessment.pipeline_stages = state_stages

        # Mark all stages as completed if pipeline succeeded
        now = datetime.utcnow()
        for stage in assessment.pipeline_stages:
            if stage.status == PipelineStageStatus.ACTIVE:
                stage.status = PipelineStageStatus.COMPLETED
                stage.completed_at = now
            elif stage.status == PipelineStageStatus.PENDING:
                stage.status = PipelineStageStatus.COMPLETED
                stage.completed_at = now

        assessment.documents_analyzed = len(assessment.documents)
        assessment.processing_time = str(now - assessment.created_at)

        logger.info(
            f"[Pipeline] Completed {session_id} — "
            f"Score: {assessment.score}, Band: {assessment.score_band}, "
            f"Outcome: {assessment.outcome}"
        )

    except Exception as e:
        logger.error(f"[Pipeline] Failed for {session_id}: {e}", exc_info=True)

        # Mark current stage as failed
        for stage in assessment.pipeline_stages:
            if stage.status == PipelineStageStatus.ACTIVE:
                stage.status = PipelineStageStatus.FAILED
                stage.message = str(e)
                break

        assessment.outcome = AssessmentOutcome.PENDING
        assessment.error = str(e)

    finally:
        _running_pipelines.pop(session_id, None)


@router.post("/{session_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline(session_id: str, background_tasks: BackgroundTasks):
    """
    Trigger the credit appraisal pipeline for a session.

    Returns immediately with 202 Accepted. The pipeline runs in the
    background. Track progress via GET /api/pipeline/{session_id}/status
    or via the WebSocket at /ws/progress/{session_id}.
    """
    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    if session_id in _running_pipelines:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pipeline already running for session {session_id}",
        )

    # Dispatch background execution
    background_tasks.add_task(_execute_pipeline, session_id)

    return {
        "session_id": session_id,
        "status": "pipeline_started",
        "message": "Pipeline execution started. Track via /ws/progress/{session_id}",
    }


@router.get("/{session_id}/status")
async def get_pipeline_status(session_id: str):
    """
    Get detailed pipeline status for a session.

    Returns current stage, completed stages, pending stages,
    and whether the pipeline is actively running.
    """
    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    is_running = session_id in _running_pipelines

    # Compute progress
    total_stages = len(assessment.pipeline_stages)
    completed_stages = sum(
        1 for s in assessment.pipeline_stages
        if s.status == PipelineStageStatus.COMPLETED
    )
    failed_stages = sum(
        1 for s in assessment.pipeline_stages
        if s.status == PipelineStageStatus.FAILED
    )

    # Find current stage
    current_stage = None
    for stage in assessment.pipeline_stages:
        if stage.status == PipelineStageStatus.ACTIVE:
            current_stage = stage.stage.value
            break

    return {
        "session_id": session_id,
        "is_running": is_running,
        "outcome": assessment.outcome.value if assessment.outcome else None,
        "score": assessment.score,
        "score_band": assessment.score_band.value if assessment.score_band else None,
        "current_stage": current_stage,
        "progress": {
            "total": total_stages,
            "completed": completed_stages,
            "failed": failed_stages,
            "percent": round(completed_stages / total_stages * 100) if total_stages > 0 else 0,
        },
        "stages": [
            {
                "stage": s.stage.value,
                "status": s.status.value,
                "message": s.message,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in assessment.pipeline_stages
        ],
        "error": assessment.error if hasattr(assessment, "error") else None,
    }


@router.post("/{session_id}/cancel")
async def cancel_pipeline(session_id: str):
    """
    Cancel a running pipeline.

    Note: In hackathon mode, this marks the pipeline as cancelled
    but doesn't actually interrupt the background task (asyncio
    task cancellation would be needed for production).
    """
    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    if session_id not in _running_pipelines:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No running pipeline for session {session_id}",
        )

    # Mark as cancelled
    _running_pipelines.pop(session_id, None)
    for stage in assessment.pipeline_stages:
        if stage.status == PipelineStageStatus.ACTIVE:
            stage.status = PipelineStageStatus.FAILED
            stage.message = "Pipeline cancelled by user"
            break

    return {
        "session_id": session_id,
        "status": "cancelled",
        "message": "Pipeline cancellation requested",
    }
