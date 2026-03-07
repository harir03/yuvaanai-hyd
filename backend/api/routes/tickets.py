"""
Intelli-Credit — Tickets Route

GET  /api/tickets/{session_id}                — All tickets for a session
GET  /api/tickets/{session_id}/stats          — Ticket statistics
GET  /api/tickets/detail/{ticket_id}          — Single ticket detail
POST /api/tickets/{ticket_id}/resolve         — Resolve a ticket
POST /api/tickets/{ticket_id}/escalate        — Escalate a ticket
"""

import logging
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, status

from backend.models.schemas import Ticket, TicketResolveRequest, TicketStatus
from backend.api.routes._store import assessments_store
from backend.graph.nodes.ticket_node import store_precedent, get_ticket_statistics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["tickets"])


@router.get("/tickets/{session_id}", response_model=List[Ticket])
async def get_tickets(session_id: str):
    """Get all tickets for a given assessment session."""
    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )
    return assessment.tickets


@router.get("/tickets/{session_id}/stats")
async def get_ticket_stats(session_id: str) -> Dict[str, Any]:
    """Get ticket statistics for a session."""
    assessment = assessments_store.get(session_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {session_id} not found",
        )
    return get_ticket_statistics(assessment.tickets)


@router.get("/tickets/detail/{ticket_id}", response_model=Ticket)
async def get_ticket_detail(ticket_id: str):
    """Get a single ticket by ID."""
    for assessment in assessments_store.values():
        for ticket in assessment.tickets:
            if ticket.id == ticket_id:
                return ticket
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Ticket {ticket_id} not found",
    )


@router.post("/tickets/{ticket_id}/resolve", response_model=Ticket)
async def resolve_ticket(ticket_id: str, request: TicketResolveRequest):
    """Resolve a ticket with the officer's decision."""
    for assessment in assessments_store.values():
        for ticket in assessment.tickets:
            if ticket.id == ticket_id:
                if ticket.status == TicketStatus.RESOLVED:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Ticket {ticket_id} is already resolved",
                    )

                ticket.resolution = request.resolution
                ticket.resolved_by = request.resolved_by
                ticket.resolved_at = datetime.utcnow()
                ticket.status = TicketStatus.RESOLVED

                # Store as precedent for future similar tickets
                store_precedent(ticket)

                # Update assessment counters
                assessment.tickets_resolved = sum(
                    1 for t in assessment.tickets if t.status == TicketStatus.RESOLVED
                )

                logger.info(f"[Tickets] Ticket {ticket_id} resolved by {request.resolved_by}")
                return ticket

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Ticket {ticket_id} not found",
    )


@router.post("/tickets/{ticket_id}/escalate", response_model=Ticket)
async def escalate_ticket(ticket_id: str):
    """Escalate a ticket to senior manager review."""
    for assessment in assessments_store.values():
        for ticket in assessment.tickets:
            if ticket.id == ticket_id:
                if ticket.status == TicketStatus.RESOLVED:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Ticket {ticket_id} is already resolved — cannot escalate",
                    )
                if ticket.status == TicketStatus.ESCALATED:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Ticket {ticket_id} is already escalated",
                    )

                ticket.status = TicketStatus.ESCALATED
                logger.info(f"[Tickets] Ticket {ticket_id} escalated to senior review")
                return ticket

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Ticket {ticket_id} not found",
    )
