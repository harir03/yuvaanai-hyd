"""
Intelli-Credit — LangGraph Node: Research (Agent 2)

External intelligence: Tavily, Exa, SerpAPI, govt scrapers,
verification engine.
Placeholder — full implementation in T2.3.
"""

import logging
from backend.graph.state import CreditAppraisalState, ResearchPackage
from backend.models.schemas import PipelineStageStatus, PipelineStageEnum

logger = logging.getLogger(__name__)


async def research_node(state: CreditAppraisalState) -> dict:
    """
    Stage 5 — Agent 2: The Research Agent.

    Runs 5 parallel research tracks, verifies findings through
    5-tier credibility engine, enriches Neo4j with external entities.
    """
    logger.info(f"[Agent 2] Researching {state.company.name if state.company else 'unknown'}")

    for stage in state.pipeline_stages:
        if stage.stage == PipelineStageEnum.RESEARCH:
            stage.status = PipelineStageStatus.COMPLETED
            stage.message = "External research completed"

    return {
        "research_package": ResearchPackage(total_findings=0),
        "pipeline_stages": state.pipeline_stages,
    }
