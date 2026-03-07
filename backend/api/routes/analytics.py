"""
Intelli-Credit — Analytics Route

GET /api/analytics — Aggregated statistics for the Analytics Dashboard
"""

import logging
from collections import Counter

from fastapi import APIRouter

from backend.models.schemas import AnalyticsData, AssessmentOutcome
from backend.api.routes._store import assessments_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsData)
async def get_analytics():
    """Get aggregated analytics data across all assessments."""
    assessments = list(assessments_store.values())

    if not assessments:
        return AnalyticsData()

    total = len(assessments)
    scores = [a.score for a in assessments if a.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    approved = sum(1 for a in assessments if a.outcome in [
        AssessmentOutcome.APPROVED, AssessmentOutcome.CONDITIONAL
    ])
    approval_rate = (approved / total * 100) if total > 0 else 0.0

    # Outcome distribution
    outcome_counts = Counter(a.outcome.value for a in assessments)

    # Score distribution by band
    band_counts = Counter()
    for a in assessments:
        if a.score_band:
            band_counts[a.score_band.value] += 1

    # Sector breakdown
    sector_counts = Counter(a.company.sector for a in assessments)
    sector_breakdown = [
        {"sector": sector, "count": count}
        for sector, count in sector_counts.most_common()
    ]

    return AnalyticsData(
        total_assessments=total,
        average_score=round(avg_score, 1),
        approval_rate=round(approval_rate, 1),
        average_processing_time="13m 00s",
        score_distribution=dict(band_counts),
        sector_breakdown=sector_breakdown,
        outcome_distribution=dict(outcome_counts),
    )
