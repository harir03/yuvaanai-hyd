"""
Intelli-Credit — Compliance Auto-Flagging Route

GET   /api/compliance/{session_id}       — Get compliance scan result
POST  /api/compliance/{session_id}/scan  — Trigger compliance scan
GET   /api/compliance/{session_id}/flags — List compliance flags with filters
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from backend.agents.evidence.compliance_engine import (
    ComplianceFlag,
    ComplianceResult,
    ComplianceSeverity,
    ComplianceTrigger,
    scan_compliance,
)
from backend.api.routes._store import assessments_store, compliance_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["compliance"])


@router.get("/compliance/{session_id}", response_model=ComplianceResult)
async def get_compliance(session_id: str) -> ComplianceResult:
    """Get compliance scan result for a session."""
    logger.info("[Compliance] GET /compliance/%s", session_id)

    if session_id not in assessments_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    result = compliance_store.get(session_id)
    if result is None:
        # Return empty result if not yet scanned
        return ComplianceResult(session_id=session_id)

    return result


@router.post("/compliance/{session_id}/scan", response_model=ComplianceResult)
async def trigger_scan(session_id: str) -> ComplianceResult:
    """Trigger a compliance scan for a session using available assessment data."""
    logger.info("[Compliance] POST /compliance/%s/scan", session_id)

    if session_id not in assessments_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    # For hackathon: scan with whatever data is in the assessment.
    # In production, this reads from the pipeline state.
    result = scan_compliance(session_id=session_id)

    compliance_store[session_id] = result
    return result


@router.get("/compliance/{session_id}/flags", response_model=List[ComplianceFlag])
async def get_flags(
    session_id: str,
    severity: Optional[ComplianceSeverity] = Query(default=None),
    trigger: Optional[ComplianceTrigger] = Query(default=None),
    requires_notification: Optional[bool] = Query(default=None),
) -> List[ComplianceFlag]:
    """Get compliance flags for a session with optional filters."""
    logger.info("[Compliance] GET /compliance/%s/flags", session_id)

    if session_id not in assessments_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    result = compliance_store.get(session_id)
    if result is None:
        return []

    flags = result.flags

    if severity:
        flags = [f for f in flags if f.severity == severity]
    if trigger:
        flags = [f for f in flags if f.trigger == trigger]
    if requires_notification is not None:
        flags = [f for f in flags if f.requires_notification == requires_notification]

    return flags
