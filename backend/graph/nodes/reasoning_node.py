"""
Intelli-Credit — LangGraph Node: Graph Reasoning (Agent 2.5)

5 structured reasoning passes over the Neo4j knowledge graph:
  Pass 1: Contradictions (-45 pts max)
  Pass 2: Cascade Risk (-50 pts max)
  Pass 3: Hidden Relationships (-60 pts max)
  Pass 4: Temporal Patterns (-20 pts max)
  Pass 5: Positive Signals (+57 pts max)
"""

import logging
from backend.graph.state import CreditAppraisalState, ReasoningPackage
from backend.models.schemas import PipelineStageStatus, PipelineStageEnum
from backend.thinking.event_emitter import ThinkingEventEmitter
from backend.agents.reasoning.contradiction_pass import run_contradiction_pass
from backend.agents.reasoning.cascade_pass import run_cascade_pass
from backend.agents.reasoning.hidden_relationship_pass import run_hidden_relationship_pass
from backend.agents.reasoning.temporal_pass import run_temporal_pass
from backend.agents.reasoning.positive_signal_pass import run_positive_signal_pass
from backend.agents.reasoning.insight_store import InsightStore

logger = logging.getLogger(__name__)


async def reasoning_node(state: CreditAppraisalState) -> dict:
    """
    Stage 6 — Agent 2.5: Graph Reasoning.

    Runs 5 structured passes over the knowledge graph, collecting
    CompoundInsights into an InsightStore. Builds a ReasoningPackage
    with all insights and their total score impact.
    """
    logger.info(f"[Agent 2.5] Running graph reasoning for session {state.session_id}")

    emitter = ThinkingEventEmitter(state.session_id, "Agent 2.5 — Graph Reasoning")
    store = InsightStore()
    passes_completed = 0

    try:
        await emitter.read("Starting 5 graph reasoning passes over knowledge graph...")

        # Pass 1: Contradictions
        try:
            p1_insights = await run_contradiction_pass(state, emitter)
            store.add_many(p1_insights)
            passes_completed += 1
        except Exception as e:
            logger.error(f"[Agent 2.5] Pass 1 (Contradictions) failed: {e}")
            await emitter.flagged(f"Pass 1 (Contradictions) failed: {e}")

        # Pass 2: Cascade Risk
        try:
            p2_insights = await run_cascade_pass(state, emitter)
            store.add_many(p2_insights)
            passes_completed += 1
        except Exception as e:
            logger.error(f"[Agent 2.5] Pass 2 (Cascade Risk) failed: {e}")
            await emitter.flagged(f"Pass 2 (Cascade Risk) failed: {e}")

        # Pass 3: Hidden Relationships
        try:
            p3_insights = await run_hidden_relationship_pass(state, emitter)
            store.add_many(p3_insights)
            passes_completed += 1
        except Exception as e:
            logger.error(f"[Agent 2.5] Pass 3 (Hidden Relationships) failed: {e}")
            await emitter.flagged(f"Pass 3 (Hidden Relationships) failed: {e}")

        # Pass 4: Temporal Patterns
        try:
            p4_insights = await run_temporal_pass(state, emitter)
            store.add_many(p4_insights)
            passes_completed += 1
        except Exception as e:
            logger.error(f"[Agent 2.5] Pass 4 (Temporal Patterns) failed: {e}")
            await emitter.flagged(f"Pass 4 (Temporal Patterns) failed: {e}")

        # Pass 5: Positive Signals
        try:
            p5_insights = await run_positive_signal_pass(state, emitter)
            store.add_many(p5_insights)
            passes_completed += 1
        except Exception as e:
            logger.error(f"[Agent 2.5] Pass 5 (Positive Signals) failed: {e}")
            await emitter.flagged(f"Pass 5 (Positive Signals) failed: {e}")

        # Build reasoning package
        all_insights = store.get_all()
        total_impact = store.total_score_impact()

        reasoning_package = ReasoningPackage(
            insights=all_insights,
            total_compound_score_impact=total_impact,
            passes_completed=passes_completed,
        )

        # Summary emission
        summary = store.summary()
        await emitter.decided(
            f"Graph reasoning complete: {passes_completed}/5 passes, "
            f"{len(all_insights)} insights, net score impact: {total_impact:+d} pts"
        )

        logger.info(
            f"[Agent 2.5] Completed {passes_completed}/5 passes, "
            f"{len(all_insights)} insights, impact: {total_impact:+d}"
        )

    except Exception as e:
        logger.error(f"[Agent 2.5] Reasoning node failed: {e}")
        await emitter.critical(f"Graph reasoning failed: {e}")
        reasoning_package = ReasoningPackage(passes_completed=passes_completed)

    # Update pipeline stage
    for stage in state.pipeline_stages:
        if stage.stage == PipelineStageEnum.REASONING:
            stage.status = PipelineStageStatus.COMPLETED
            stage.message = (
                f"{passes_completed}/5 passes, "
                f"{len(reasoning_package.insights)} insights"
            )

    return {
        "reasoning_package": reasoning_package,
        "pipeline_stages": state.pipeline_stages,
    }
