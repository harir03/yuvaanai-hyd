"""
Intelli-Credit — Score Route

GET   /api/score/{session_id}       — Detailed score breakdown
POST  /api/score/{session_id}/run   — Trigger scoring for a session (mock)
GET   /api/score/{session_id}/pdf   — Download score report as PDF
GET   /api/score/{session_id}/html  — Render score report as HTML (Jinja2)
"""

import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.auth.jwt_handler import optional_auth
from fastapi.responses import Response

from backend.models.schemas import (
    AssessmentOutcome,
    HardBlockResponse,
    LoanTerms,
    ScoreBand,
    ScoreResponse,
)
from backend.api.routes._store import assessments_store
from config.scoring import (
    BASE_SCORE,
    MAX_SCORE,
    get_loan_terms,
    get_score_band,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["score"], dependencies=[Depends(optional_auth)])


def _build_score_response(session_id: str) -> ScoreResponse:
    """Build ScoreResponse from the in-memory assessment store."""
    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    if assessment.score is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Assessment {session_id} has not been scored yet",
        )

    # Derive loan terms from band
    band = assessment.score_band or ScoreBand.DEFAULT_RISK
    terms_dict = get_loan_terms(band)
    loan_terms = LoanTerms(
        sanction_pct=int(terms_dict["sanction_pct"]),
        rate=terms_dict["rate"],
        tenure=terms_dict["tenure"],
        review=terms_dict["review"],
    )

    # Count total metrics across all modules
    total_metrics = sum(len(m.metrics) for m in assessment.score_modules)

    return ScoreResponse(
        session_id=session_id,
        company_name=assessment.company.name,
        score=assessment.score,
        score_band=band,
        outcome=assessment.outcome,
        recommendation=_recommendation_text(assessment.outcome, band),
        base_score=BASE_SCORE,
        modules=assessment.score_modules,
        hard_blocks=[],  # Hard blocks not stored in AssessmentSummary yet
        loan_terms=loan_terms,
        cam_url=assessment.cam_url,
        total_metrics=total_metrics,
        scored_at=assessment.completed_at,
    )


def _recommendation_text(outcome: AssessmentOutcome, band: ScoreBand) -> str:
    """Generate recommendation text from outcome and band."""
    if outcome == AssessmentOutcome.APPROVED:
        return f"Full approval recommended ({band.value})"
    elif outcome == AssessmentOutcome.CONDITIONAL:
        return f"Conditional approval — additional review required ({band.value})"
    elif outcome == AssessmentOutcome.REJECTED:
        return f"Rejection recommended ({band.value})"
    return f"Pending scoring ({band.value})"


@router.get("/score/{session_id}", response_model=ScoreResponse)
async def get_score(session_id: str) -> ScoreResponse:
    """Get detailed score breakdown for a session."""
    logger.info("[Score API] GET /score/%s", session_id)
    return _build_score_response(session_id)


@router.post("/score/{session_id}/run", response_model=ScoreResponse)
async def run_scoring(session_id: str) -> ScoreResponse:
    """
    Trigger scoring for a session.

    T2: Mock implementation — sets a demo score on the assessment.
    Future: Will invoke the LangGraph recommendation node.
    """
    logger.info("[Score API] POST /score/%s/run", session_id)

    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    if assessment.score is not None:
        # Already scored — return existing
        return _build_score_response(session_id)

    # Compute score dynamically from module data if available,
    # otherwise use base score as starting point for demo
    if assessment.score_modules:
        total_impact = sum(
            sum(m.score_impact for m in mod.metrics) for mod in assessment.score_modules
        )
        computed_score = max(0, min(MAX_SCORE, BASE_SCORE + total_impact))
    else:
        # No module data yet — use base score (demo fallback)
        computed_score = BASE_SCORE

    band, outcome, _ = get_score_band(computed_score)
    assessment.score = computed_score
    assessment.score_band = band
    assessment.outcome = outcome
    assessment.completed_at = datetime.utcnow()

    logger.info("[Score API] Score computed for %s: %d/%d", session_id, computed_score, MAX_SCORE)
    return _build_score_response(session_id)


# ---------- Session ID validation ----------

_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


def _validate_session_id(session_id: str) -> str:
    """Validate session_id format."""
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format",
        )
    return session_id


# ---------- Score PDF Download ----------


@router.get("/score/{session_id}/pdf")
async def download_score_pdf(session_id: str):
    """Download the score report as a PDF with gauge visualization."""
    session_id = _validate_session_id(session_id)
    score_response = _build_score_response(session_id)

    from backend.output.pdf_generator import build_score_context, generate_score_pdf

    context = build_score_context(score_response)
    pdf_bytes = generate_score_pdf(context)

    logger.info("[Score API] Generated PDF for %s (%d bytes)", session_id, len(pdf_bytes))

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="score_{session_id}.pdf"'},
    )


# ---------- Score HTML Render ----------


@router.get("/score/{session_id}/html")
async def render_score_html(session_id: str):
    """Render the score report as HTML via Jinja2 template."""
    session_id = _validate_session_id(session_id)
    score_response = _build_score_response(session_id)

    from backend.output.pdf_generator import build_score_context
    from backend.output.template_engine import render_template

    context = build_score_context(score_response)
    html = render_template("score_report.html", context)

    return Response(content=html, media_type="text/html")
