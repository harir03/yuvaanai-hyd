"""
Intelli-Credit — Assessment Route

GET  /api/assessment/{session_id}  — Full assessment state
GET  /api/assessments              — List all assessments (history)
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status

from backend.models.schemas import AssessmentSummary, HistoryRecord, ScoreBand, AssessmentOutcome
from backend.api.routes._store import assessments_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["assessment"])


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
                score_band=a.score_band or ScoreBand.FAIR,
                outcome=a.outcome,
                processing_time=a.processing_time,
                created_at=a.created_at,
            )
        )
    return records
