"""
Intelli-Credit — LangGraph Orchestrator

The central state machine that wires all pipeline nodes together.
Defines the node graph, conditional edges for routing
(normal path, auto-reject, deep fraud, human review),
and the entry point for running a full credit assessment.

Run with: await run_pipeline(session_id, company, documents)
"""

import logging
from typing import Optional, List
from datetime import datetime

from langgraph.graph import StateGraph, END

from backend.graph.state import CreditAppraisalState
from backend.models.schemas import (
    CompanyInfo,
    DocumentMeta,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
    AssessmentOutcome,
    TicketSeverity,
    TicketStatus,
)

# Node imports
from backend.graph.nodes.workers_node import workers_node
from backend.graph.nodes.consolidator_node import consolidator_node
from backend.graph.nodes.validator_node import validator_node
from backend.graph.nodes.organizer_node import organizer_node
from backend.graph.nodes.research_node import research_node
from backend.graph.nodes.reasoning_node import reasoning_node
from backend.graph.nodes.evidence_node import evidence_node
from backend.graph.nodes.ticket_node import ticket_node
from backend.graph.nodes.recommendation_node import recommendation_node
from backend.graph.nodes.decision_store_node import decision_store_node

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Conditional Edge Functions
# ──────────────────────────────────────────────

def should_continue_after_validation(state: CreditAppraisalState) -> str:
    """After validation, check if we should continue or stop."""
    if not state.validation_passed:
        logger.warning(f"[Orchestrator] Validation failed: {state.validation_errors}")
        return "end"
    return "organizer"


def should_continue_after_tickets(state: CreditAppraisalState) -> str:
    """After ticket check, decide whether to proceed to scoring."""
    if state.tickets_blocking:
        logger.warning("[Orchestrator] Blocking tickets — pausing pipeline")
        return "end"  # In production, this would be a human-in-the-loop pause
    return "recommendation"


def check_hard_blocks(state: CreditAppraisalState) -> str:
    """After scoring, check for hard blocks that override the score."""
    if state.hard_blocks:
        logger.warning(f"[Orchestrator] Hard blocks detected: {[hb.trigger for hb in state.hard_blocks]}")
    return "decision_store"


# ──────────────────────────────────────────────
# Graph Building
# ──────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Build the LangGraph state machine for the credit appraisal pipeline.

    Pipeline Flow:
    workers → consolidator → validator →(conditional)→ organizer → research →
    reasoning → evidence → tickets →(conditional)→ recommendation → decision_store → END
    """
    graph = StateGraph(CreditAppraisalState)

    # ── Add Nodes ──
    graph.add_node("workers", workers_node)
    graph.add_node("consolidator", consolidator_node)
    graph.add_node("validator", validator_node)
    graph.add_node("organizer", organizer_node)
    graph.add_node("research", research_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("evidence", evidence_node)
    graph.add_node("tickets", ticket_node)
    graph.add_node("recommendation", recommendation_node)
    graph.add_node("decision_store", decision_store_node)

    # ── Set Entry Point ──
    graph.set_entry_point("workers")

    # ── Add Edges ──
    # Normal flow
    graph.add_edge("workers", "consolidator")
    graph.add_edge("consolidator", "validator")

    # Conditional: validation passed?
    graph.add_conditional_edges(
        "validator",
        should_continue_after_validation,
        {
            "organizer": "organizer",
            "end": END,
        }
    )

    # Normal flow continues
    graph.add_edge("organizer", "research")
    graph.add_edge("research", "reasoning")
    graph.add_edge("reasoning", "evidence")
    graph.add_edge("evidence", "tickets")

    # Conditional: blocking tickets?
    graph.add_conditional_edges(
        "tickets",
        should_continue_after_tickets,
        {
            "recommendation": "recommendation",
            "end": END,
        }
    )

    # Final stages
    graph.add_edge("recommendation", "decision_store")
    graph.add_edge("decision_store", END)

    return graph


# ── Compiled Graph (singleton) ──
_compiled_graph = None


def get_compiled_graph():
    """Get or create the compiled LangGraph pipeline."""
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_graph()
        _compiled_graph = graph.compile()
        logger.info("[Orchestrator] LangGraph pipeline compiled successfully")
    return _compiled_graph


# ──────────────────────────────────────────────
# Pipeline Entry Point
# ──────────────────────────────────────────────

async def run_pipeline(
    session_id: str,
    company: CompanyInfo,
    documents: List[DocumentMeta],
) -> CreditAppraisalState:
    """
    Run the full credit appraisal pipeline.

    Args:
        session_id: Unique assessment session ID
        company: Company information
        documents: List of uploaded document metadata

    Returns:
        Final CreditAppraisalState with score, band, outcome, CAM
    """
    logger.info(f"[Orchestrator] Starting pipeline for session {session_id}")

    # Initialize pipeline stages
    pipeline_stages = [
        PipelineStage(stage=s, status=PipelineStageStatus.PENDING)
        for s in PipelineStageEnum
    ]
    # Mark upload as complete
    pipeline_stages[0].status = PipelineStageStatus.COMPLETED

    # Build initial state
    initial_state = CreditAppraisalState(
        session_id=session_id,
        company=company,
        documents=documents,
        pipeline_stages=pipeline_stages,
        workers_total=len(documents),
    )

    # Run the graph
    compiled = get_compiled_graph()
    final_state = await compiled.ainvoke(initial_state)

    logger.info(
        f"[Orchestrator] Pipeline complete for {session_id} — "
        f"Score: {final_state.get('score', 'N/A')}, "
        f"Outcome: {final_state.get('outcome', 'N/A')}"
    )

    return final_state
