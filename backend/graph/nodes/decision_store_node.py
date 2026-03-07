"""
Intelli-Credit — LangGraph Node: Decision Store

Writes the complete assessment to the Universal Decision Store.
Placeholder — full implementation in T2.7.
"""

import logging
from backend.graph.state import CreditAppraisalState
from backend.models.schemas import PipelineStageStatus, PipelineStageEnum

logger = logging.getLogger(__name__)


async def decision_store_node(state: CreditAppraisalState) -> dict:
    """
    Final Stage — Decision Store Writer.

    Persists the complete assessment: score breakdown, findings,
    tickets, thinking events, CAM path, LangSmith trace.
    """
    logger.info(f"[Decision Store] Persisting session {state.session_id} — Score: {state.score}")

    # TODO: Write to PostgreSQL (T0.4 / T2.7)

    return {
        "processing_time": "13m 00s",
    }
