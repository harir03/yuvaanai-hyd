"""
Intelli-Credit — Decision Store Route

GET   /api/decisions                     — Paginated history with filters
GET   /api/decisions/{session_id}        — Full decision record
POST  /api/decisions/{session_id}/notes  — Add officer note
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from backend.models.schemas import (
    AddNoteRequest,
    AssessmentOutcome,
    DecisionRecord,
    HardBlockResponse,
    HistoryRecord,
    LoanTerms,
    NoteCategory,
    OfficerNote,
    ScoreBand,
)
from backend.api.routes._store import assessments_store, officer_notes_store
from backend.graph.nodes.recommendation_node import _get_loan_terms

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["decisions"])


def _to_decision_record(session_id: str) -> DecisionRecord:
    """Build DecisionRecord from assessment + notes."""
    a = assessments_store.get(session_id)
    if not a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    band = a.score_band or ScoreBand.DEFAULT_RISK
    terms_dict = _get_loan_terms(band)
    loan_terms = LoanTerms(
        sanction_pct=int(terms_dict["sanction_pct"]),
        rate=terms_dict["rate"],
        tenure=terms_dict["tenure"],
        review=terms_dict["review"],
    ) if a.score is not None else None

    notes = officer_notes_store.get(session_id, [])

    return DecisionRecord(
        session_id=session_id,
        company_name=a.company.name,
        sector=a.company.sector,
        loan_type=a.company.loan_type,
        loan_amount=a.company.loan_amount,
        score=a.score,
        score_band=a.score_band,
        outcome=a.outcome,
        modules=a.score_modules,
        hard_blocks=[],
        loan_terms=loan_terms,
        cam_url=a.cam_url,
        documents_analyzed=a.documents_analyzed,
        findings_count=a.findings_count,
        tickets_raised=a.tickets_raised,
        tickets_resolved=a.tickets_resolved,
        officer_notes=notes,
        processing_time=a.processing_time,
        created_at=a.created_at,
        completed_at=a.completed_at,
    )


@router.get("/decisions", response_model=List[HistoryRecord])
async def list_decisions(
    sector: Optional[str] = Query(None, description="Filter by sector"),
    band: Optional[ScoreBand] = Query(None, description="Filter by score band"),
    outcome: Optional[AssessmentOutcome] = Query(None, description="Filter by outcome"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> List[HistoryRecord]:
    """List decisions with optional filters, paginated."""
    logger.info("[Decisions] GET /decisions sector=%s band=%s outcome=%s", sector, band, outcome)

    records = []
    for a in assessments_store.values():
        if sector and a.company.sector.lower() != sector.lower():
            continue
        if band and a.score_band != band:
            continue
        if outcome and a.outcome != outcome:
            continue
        records.append(
            HistoryRecord(
                session_id=a.session_id,
                company_name=a.company.name,
                sector=a.company.sector,
                loan_type=a.company.loan_type,
                loan_amount=a.company.loan_amount,
                score=a.score or 0,
                score_band=a.score_band or ScoreBand.DEFAULT_RISK,
                outcome=a.outcome,
                processing_time=a.processing_time,
                created_at=a.created_at,
            )
        )

    # Sort by created_at descending (newest first)
    records.sort(key=lambda r: r.created_at, reverse=True)

    return records[offset : offset + limit]


@router.get("/decisions/{session_id}", response_model=DecisionRecord)
async def get_decision(session_id: str) -> DecisionRecord:
    """Get a full decision record for a session."""
    logger.info("[Decisions] GET /decisions/%s", session_id)
    return _to_decision_record(session_id)


@router.post("/decisions/{session_id}/notes", response_model=OfficerNote)
async def add_note(session_id: str, req: AddNoteRequest) -> OfficerNote:
    """Add an officer note to a decision."""
    logger.info("[Decisions] POST /decisions/%s/notes", session_id)

    if session_id not in assessments_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    note = OfficerNote(
        text=req.text,
        author=req.author,
        category=req.category,
        finding_id=req.finding_id,
        ticket_id=req.ticket_id,
    )

    if session_id not in officer_notes_store:
        officer_notes_store[session_id] = []
    officer_notes_store[session_id].append(note)

    return note


@router.get("/decisions/{session_id}/notes", response_model=List[OfficerNote])
async def get_notes(
    session_id: str,
    category: Optional[NoteCategory] = Query(default=None),
    finding_id: Optional[str] = Query(default=None),
    ticket_id: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=200),
) -> List[OfficerNote]:
    """Get officer notes for a session with optional filters and search."""
    logger.info("[Decisions] GET /decisions/%s/notes", session_id)

    if session_id not in assessments_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    notes = officer_notes_store.get(session_id, [])

    # Apply filters
    if category:
        notes = [n for n in notes if n.category == category]
    if finding_id:
        notes = [n for n in notes if n.finding_id == finding_id]
    if ticket_id:
        notes = [n for n in notes if n.ticket_id == ticket_id]
    if search:
        search_lower = search.lower()
        notes = [n for n in notes if search_lower in n.text.lower()]

    return notes


@router.delete("/decisions/{session_id}/notes/{note_id}")
async def delete_note(session_id: str, note_id: str):
    """Delete an officer note."""
    logger.info("[Decisions] DELETE /decisions/%s/notes/%s", session_id, note_id)

    if session_id not in assessments_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )

    notes = officer_notes_store.get(session_id, [])
    for i, note in enumerate(notes):
        if note.id == note_id:
            notes.pop(i)
            return {"deleted": True, "note_id": note_id}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Note {note_id} not found",
    )
