"""
Intelli-Credit — Assessment Route

GET  /api/assessment/{session_id}      — Full assessment state
GET  /api/assessments                  — List all assessments (history)
GET  /api/cam/{session_id}             — Download CAM document (text)
GET  /api/cam/{session_id}/docx        — Download CAM as .docx
GET  /api/cam/{session_id}/html        — Render CAM as HTML (Jinja2)
"""

import logging
import os
import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response

from backend.api.auth.jwt_handler import optional_auth
from backend.models.schemas import AssessmentSummary, HistoryRecord, ScoreBand, AssessmentOutcome, InterviewSubmission
from backend.api.routes._store import assessments_store, interview_store
from config.scoring import DEFAULT_MISSING_BAND, CAM_OUTPUT_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["assessment"], dependencies=[Depends(optional_auth)])


@router.get("/assessment/{session_id}", response_model=AssessmentSummary)
async def get_assessment(session_id: str):
    """Get the full assessment state for a given session."""
    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )
    return assessment


@router.get("/assessments", response_model=List[AssessmentSummary])
async def list_assessments():
    """List all assessments (for the Decision Store / History page)."""
    return list(assessments_store.values())


@router.get("/history", response_model=List[HistoryRecord])
async def get_history():
    """Get assessment history as simplified records."""
    records = []
    for a in assessments_store.values():
        records.append(
            HistoryRecord(
                session_id=a.session_id,
                company_name=a.company.name,
                sector=a.company.sector,
                loan_type=a.company.loan_type,
                loan_amount=a.company.loan_amount,
                score=a.score or 0,
                score_band=a.score_band or DEFAULT_MISSING_BAND,
                outcome=a.outcome,
                processing_time=a.processing_time,
                created_at=a.created_at,
            )
        )
    return records


# ---------- Session ID validation ----------

_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")

# Allowed root for CAM files — sourced from config
CAM_OUTPUT_ROOT = os.path.join(*CAM_OUTPUT_DIR.split("/"))


def _validate_session_id(session_id: str) -> str:
    """Validate session_id to prevent path traversal."""
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format",
        )
    return session_id


# ---------- CAM Download ----------


@router.get("/cam/{session_id}")
async def download_cam(session_id: str):
    """Download the Credit Appraisal Memo for a completed assessment.

    Returns the CAM as a plain-text file attachment.
    """
    session_id = _validate_session_id(session_id)

    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    cam_path = assessment.cam_path
    if not cam_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CAM has not been generated yet for this assessment",
        )

    # Resolve to absolute and verify path stays within allowed root
    abs_cam_path = os.path.abspath(cam_path)
    allowed_root = os.path.abspath(CAM_OUTPUT_ROOT)
    if not abs_cam_path.startswith(allowed_root):
        logger.warning(f"[CAM] Path traversal attempt blocked: {cam_path}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CAM path",
        )

    if not os.path.isfile(abs_cam_path):
        logger.error(f"[CAM] File not found on disk: {abs_cam_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CAM file not found on disk",
        )

    return FileResponse(
        path=abs_cam_path,
        media_type="text/plain",
        filename=f"cam_{session_id}.txt",
    )


# ---------- CAM .docx Download ----------


@router.get("/cam/{session_id}/docx")
async def download_cam_docx(session_id: str):
    """Download the Credit Appraisal Memo as a .docx Word document."""
    session_id = _validate_session_id(session_id)

    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    if assessment.score is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assessment has not been scored yet",
        )

    # Lazy imports to avoid circular dependencies and keep startup fast
    from backend.api.routes.score import _build_score_response
    from backend.output.docx_generator import build_cam_context, generate_cam_docx

    score_response = _build_score_response(session_id)
    context = build_cam_context(score_response, assessment)
    docx_bytes = generate_cam_docx(context)

    logger.info("[CAM] Generated .docx for %s (%d bytes)", session_id, len(docx_bytes))

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="cam_{session_id}.docx"'},
    )


# ---------- CAM HTML Render ----------


@router.get("/cam/{session_id}/html")
async def render_cam_html(session_id: str):
    """Render the Credit Appraisal Memo as HTML via Jinja2 template."""
    session_id = _validate_session_id(session_id)

    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    if assessment.score is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assessment has not been scored yet",
        )

    from backend.api.routes.score import _build_score_response
    from backend.output.docx_generator import build_cam_context
    from backend.output.template_engine import render_template

    score_response = _build_score_response(session_id)
    context = build_cam_context(score_response, assessment)
    html = render_template("cam_report.html", context)

    return Response(content=html, media_type="text/html")


# ---------- Management Interview ----------


@router.post("/assessment/{session_id}/interview")
async def submit_interview(session_id: str, submission: InterviewSubmission):
    """Submit management interview answers for a given assessment.

    Stores the question-answer pairs and links them to the assessment session.
    """
    session_id = _validate_session_id(session_id)

    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    # Store interview answers
    interview_store[session_id] = submission.answers
    logger.info(
        "[Interview] Stored %d answers for session %s",
        len(submission.answers),
        session_id,
    )

    return {"status": "submitted", "answers_count": len(submission.answers)}
