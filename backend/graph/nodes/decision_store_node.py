"""
Intelli-Credit — LangGraph Node: Decision Store

Final pipeline node. Persists the complete assessment to the Decision Store:
- Score breakdown (every point in 0-850)
- All findings with source tracing
- Ticket resolutions
- Complete thinking event log
- CAM document path
- Final outcome and recommendation

Persists to PostgreSQL (with in-memory fallback for demo).
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from backend.graph.state import CreditAppraisalState
from backend.models.schemas import (
    PipelineStageStatus,
    PipelineStageEnum,
    EventType,
    ThinkingEvent,
    AssessmentOutcome,
)
from backend.storage.postgres_client import DatabaseClient

logger = logging.getLogger(__name__)

# Singleton database client
_db: Optional[DatabaseClient] = None


async def _get_db() -> DatabaseClient:
    """Get or initialize the PostgreSQL client."""
    global _db
    if _db is None:
        _db = DatabaseClient()
        await _db.initialize()
    return _db


# In-memory fallback for when DB is unavailable
decision_records: Dict[str, Dict[str, Any]] = {}


def _build_decision_record(state: CreditAppraisalState) -> Dict[str, Any]:
    """Build a structured decision record from the final pipeline state."""
    record = {
        "session_id": state.session_id,
        "company_name": state.company.name if state.company else "Unknown",
        "sector": state.company.sector if state.company else "Unknown",
        "loan_type": state.company.loan_type if state.company else "Unknown",
        "loan_amount": state.company.loan_amount if state.company else "Unknown",
        "loan_amount_numeric": state.company.loan_amount_numeric if state.company else 0.0,

        # Scoring
        "score": state.score,
        "score_band": state.score_band.value if state.score_band else None,
        "outcome": state.outcome.value if state.outcome else None,
        "hard_blocks": [
            {
                "trigger": hb.trigger,
                "score_cap": hb.score_cap,
                "evidence": hb.evidence,
                "source": hb.source,
            }
            for hb in (state.hard_blocks or [])
        ],
        "score_modules": [
            {
                "module": mod.module.value,
                "score": mod.score,
                "max_positive": mod.max_positive,
                "max_negative": mod.max_negative,
                "metrics_count": len(mod.metrics),
            }
            for mod in (state.score_modules or [])
        ],

        # Documents
        "documents_analyzed": len(state.documents),
        "document_types": [d.document_type.value for d in (state.documents or [])],

        # Findings summary
        "total_thinking_events": len(state.thinking_events or []),
        "total_tickets": len(state.tickets or []),
        "tickets_blocking": state.tickets_blocking,

        # Cross-verification summary
        "cross_verifications_count": (
            len(state.raw_data_package.cross_verifications)
            if state.raw_data_package else 0
        ),

        # Research summary
        "research_findings_count": (
            state.research_package.total_findings
            if state.research_package else 0
        ),

        # Compound insights summary
        "compound_insights_count": (
            len(state.reasoning_package.insights)
            if state.reasoning_package else 0
        ),

        # CAM
        "cam_path": state.cam_path,

        # Timestamps
        "created_at": state.created_at.isoformat() if state.created_at else None,
        "completed_at": datetime.utcnow().isoformat(),

        # Tracing
        "langsmith_trace_url": state.langsmith_trace_url,
    }
    return record


async def decision_store_node(state: CreditAppraisalState) -> dict:
    """
    Final Stage — Decision Store Writer.

    Persists the complete assessment to the decision store.
    Emits thinking events for audit trail visibility.
    """
    logger.info(f"[Decision Store] Persisting session {state.session_id} — Score: {state.score}")

    # Emit start event
    thinking_events = list(state.thinking_events or [])

    thinking_events.append(ThinkingEvent(
        session_id=state.session_id,
        agent="Decision Store",
        event_type=EventType.READ,
        message=f"Persisting assessment for {state.company.name if state.company else 'Unknown'}...",
    ))

    # Build decision record
    record = _build_decision_record(state)

    # Persist to in-memory store (always — fast, available)
    decision_records[state.session_id] = record

    # Persist to PostgreSQL (async, non-blocking on failure)
    try:
        db = await _get_db()
        await db.save_assessment({
            "session_id": state.session_id,
            "company_name": record["company_name"],
            "sector": record["sector"],
            "loan_type": record["loan_type"],
            "loan_amount": record["loan_amount"],
            "loan_amount_numeric": record.get("loan_amount_numeric", 0.0),
            "status": "completed",
            "score": state.score,
            "score_band": record["score_band"],
            "outcome": record["outcome"],
            "cam_path": record["cam_path"],
            "processing_time": record.get("processing_time"),
            "langsmith_trace_url": record.get("langsmith_trace_url"),
        })

        # Persist thinking events in batch
        te_dicts = [
            {
                "session_id": state.session_id,
                "agent": te.agent,
                "event_type": te.event_type.value if hasattr(te.event_type, "value") else str(te.event_type),
                "message": te.message,
            }
            for te in (state.thinking_events or [])
        ]
        if te_dicts:
            await db.save_thinking_events_batch(te_dicts)

        logger.info(f"[Decision Store] Persisted to PostgreSQL: {state.session_id}")
    except Exception as e:
        # Non-blocking: in-memory store already has the record
        logger.warning(f"[Decision Store] PostgreSQL persist failed (in-memory OK): {e}")

    # Build summary message
    score_str = f"{state.score}/850" if state.score is not None else "N/A"
    band_str = state.score_band.value if state.score_band else "N/A"
    outcome_str = state.outcome.value if state.outcome else "PENDING"
    docs_count = len(state.documents) if state.documents else 0
    tickets_count = len(state.tickets) if state.tickets else 0

    summary = (
        f"Assessment complete: {score_str} ({band_str}) → {outcome_str}. "
        f"{docs_count} documents analyzed, {tickets_count} tickets raised."
    )

    thinking_events.append(ThinkingEvent(
        session_id=state.session_id,
        agent="Decision Store",
        event_type=EventType.CONCLUDED if hasattr(EventType, "CONCLUDED") else EventType.DECIDED,
        message=summary,
    ))

    # Log hard blocks if any
    if state.hard_blocks:
        block_names = [hb.trigger for hb in state.hard_blocks]
        thinking_events.append(ThinkingEvent(
            session_id=state.session_id,
            agent="Decision Store",
            event_type=EventType.CRITICAL,
            message=f"Hard blocks recorded: {', '.join(block_names)}",
        ))

    logger.info(f"[Decision Store] Persisted {state.session_id}: {summary}")

    # Calculate processing time
    elapsed = datetime.utcnow() - state.created_at if state.created_at else None
    processing_time = str(elapsed) if elapsed else "Unknown"

    return {
        "thinking_events": thinking_events,
        "processing_time": processing_time,
    }

