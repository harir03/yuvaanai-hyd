"""
Intelli-Credit — LangGraph Node: Ticket Resolution

Implements the human-AI dialogue system for conflict resolution:
 - Categorizes tickets by severity (LOW, HIGH, CRITICAL)
 - LOW: pipeline continues, resolved async
 - HIGH: pipeline pauses at Agent 3, must resolve first
 - CRITICAL: pipeline stops, senior manager notification
 - Emits ThinkingEvents for every ticket decision
 - Searches for past precedents from resolved tickets
"""

import logging
from typing import Dict, List, Any, Optional

from backend.graph.state import CreditAppraisalState
from backend.models.schemas import (
    PipelineStageStatus,
    PipelineStageEnum,
    TicketSeverity,
    TicketStatus,
    Ticket,
    ThinkingEvent,
    EventType,
)

logger = logging.getLogger(__name__)

# In-memory store for resolved ticket precedents (across assessments)
_precedent_store: List[Dict[str, Any]] = []


async def ticket_node(state: CreditAppraisalState) -> dict:
    """
    Stage 8 — Ticket Resolution.

    Checks all tickets, categorizes by severity, emits thinking events,
    searches for precedents, determines if pipeline should be blocked.

    Severity behavior:
      - LOW: pipeline continues, ticket resolved async
      - HIGH: pipeline pauses, must be resolved before Agent 3
      - CRITICAL: pipeline stops, senior manager needed
    """
    logger.info(f"[Tickets] Processing {len(state.tickets)} tickets for session {state.session_id}")

    events: List[ThinkingEvent] = list(state.thinking_events or [])
    tickets = list(state.tickets or [])

    if not tickets:
        events.append(_event(state.session_id, EventType.ACCEPTED,
                             "No tickets raised — pipeline proceeding to scoring"))
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.TICKETS:
                stage.status = PipelineStageStatus.COMPLETED
                stage.message = "No tickets to resolve"
        return {
            "tickets_blocking": False,
            "thinking_events": events,
            "pipeline_stages": state.pipeline_stages,
        }

    # Categorize tickets
    low_tickets = [t for t in tickets if t.severity == TicketSeverity.LOW and t.status != TicketStatus.RESOLVED]
    high_tickets = [t for t in tickets if t.severity == TicketSeverity.HIGH and t.status != TicketStatus.RESOLVED]
    critical_tickets = [t for t in tickets if t.severity == TicketSeverity.CRITICAL and t.status != TicketStatus.RESOLVED]
    resolved_tickets = [t for t in tickets if t.status == TicketStatus.RESOLVED]

    events.append(_event(
        state.session_id, EventType.READ,
        f"Reviewing {len(tickets)} tickets: "
        f"{len(critical_tickets)} CRITICAL, {len(high_tickets)} HIGH, "
        f"{len(low_tickets)} LOW, {len(resolved_tickets)} already resolved"
    ))

    # Search precedents for each unresolved ticket
    for ticket in tickets:
        if ticket.status == TicketStatus.RESOLVED:
            continue
        precedents = _find_precedents(ticket)
        if precedents:
            ticket.precedents = precedents
            events.append(_event(
                state.session_id, EventType.FOUND,
                f"Found {len(precedents)} precedent(s) for ticket '{ticket.title}'"
            ))

    # Emit events for each severity level
    if critical_tickets:
        for t in critical_tickets:
            events.append(_event(
                state.session_id, EventType.CRITICAL,
                f"CRITICAL ticket: {t.title} — {t.description} "
                f"(score impact: {t.score_impact:+d} pts)"
            ))

    if high_tickets:
        for t in high_tickets:
            events.append(_event(
                state.session_id, EventType.FLAGGED,
                f"HIGH severity ticket: {t.title} — {t.description} "
                f"(score impact: {t.score_impact:+d} pts)"
            ))

    if low_tickets:
        events.append(_event(
            state.session_id, EventType.QUESTIONING,
            f"{len(low_tickets)} LOW severity ticket(s) — pipeline continues, "
            "will be resolved async"
        ))

    # Determine blocking status
    blocking = len(high_tickets) > 0 or len(critical_tickets) > 0

    if blocking:
        total_blocking = len(high_tickets) + len(critical_tickets)
        total_score_impact = sum(
            abs(t.score_impact) for t in high_tickets + critical_tickets
        )
        events.append(_event(
            state.session_id, EventType.QUESTIONING,
            f"Pipeline PAUSED — {total_blocking} blocking ticket(s) "
            f"(total score impact: ±{total_score_impact} pts). "
            "Credit officer must resolve before scoring."
        ))
    else:
        events.append(_event(
            state.session_id, EventType.CONCLUDING,
            "No blocking tickets — pipeline proceeding to scoring"
        ))

    # Update pipeline stage
    for stage in state.pipeline_stages:
        if stage.stage == PipelineStageEnum.TICKETS:
            if blocking:
                stage.status = PipelineStageStatus.ACTIVE
                stage.message = (
                    f"Waiting: {len(high_tickets)} HIGH + "
                    f"{len(critical_tickets)} CRITICAL tickets need resolution"
                )
            else:
                stage.status = PipelineStageStatus.COMPLETED
                stage.message = (
                    f"All blocking tickets resolved "
                    f"({len(low_tickets)} LOW tickets for async resolution)"
                    if low_tickets else "No blocking tickets"
                )

    return {
        "tickets": tickets,
        "tickets_blocking": blocking,
        "thinking_events": events,
        "pipeline_stages": state.pipeline_stages,
    }


def store_precedent(ticket: Ticket):
    """
    Store a resolved ticket as a precedent for future reference.
    Called when a ticket is resolved via the API.
    """
    if ticket.status != TicketStatus.RESOLVED:
        return

    _precedent_store.append({
        "ticket_id": ticket.id,
        "session_id": ticket.session_id,
        "category": ticket.category,
        "title": ticket.title,
        "severity": ticket.severity.value,
        "resolution": ticket.resolution,
        "resolved_by": ticket.resolved_by,
        "score_impact": ticket.score_impact,
        "source_a": ticket.source_a,
        "source_b": ticket.source_b,
    })


def _find_precedents(ticket: Ticket) -> List[Dict[str, Any]]:
    """
    Find past resolved tickets similar to this one.
    Matches on category (exact) and title similarity (contains).
    """
    matches = []
    for p in _precedent_store:
        # Same category
        if p["category"] == ticket.category:
            matches.append(p)
        # Title overlap (keyword matching)
        elif _titles_similar(ticket.title, p.get("title", "")):
            matches.append(p)

    # Return top 3 most relevant precedents
    return matches[:3]


def _titles_similar(a: str, b: str) -> bool:
    """Simple keyword overlap check between two ticket titles."""
    if not a or not b:
        return False
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    # Remove common words
    stopwords = {"the", "a", "an", "in", "of", "for", "and", "or", "is", "was", "to"}
    words_a -= stopwords
    words_b -= stopwords
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
    return overlap >= 0.5


def get_ticket_statistics(tickets: List[Ticket]) -> Dict[str, Any]:
    """
    Compute ticket statistics for an assessment session.
    """
    if not tickets:
        return {
            "total": 0,
            "by_severity": {"LOW": 0, "HIGH": 0, "CRITICAL": 0},
            "by_status": {"OPEN": 0, "IN_REVIEW": 0, "RESOLVED": 0, "ESCALATED": 0},
            "total_score_impact": 0,
            "blocking": False,
        }

    by_severity = {s.value: 0 for s in TicketSeverity}
    by_status = {s.value: 0 for s in TicketStatus}

    for t in tickets:
        by_severity[t.severity.value] = by_severity.get(t.severity.value, 0) + 1
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1

    unresolved_blocking = any(
        t.severity in (TicketSeverity.HIGH, TicketSeverity.CRITICAL)
        and t.status != TicketStatus.RESOLVED
        for t in tickets
    )

    return {
        "total": len(tickets),
        "by_severity": by_severity,
        "by_status": by_status,
        "total_score_impact": sum(abs(t.score_impact) for t in tickets),
        "blocking": unresolved_blocking,
    }


def _event(session_id: str, event_type: EventType, message: str) -> ThinkingEvent:
    """Create a ThinkingEvent for the Ticket node."""
    return ThinkingEvent(
        session_id=session_id,
        agent="Ticket Resolution",
        event_type=event_type,
        message=message,
    )
