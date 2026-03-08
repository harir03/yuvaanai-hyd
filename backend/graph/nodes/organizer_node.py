"""
Intelli-Credit — LangGraph Node: Organizer (Agent 1.5)

Maps data to 5 Cs framework, computes derived metrics,
builds Neo4j knowledge graph, analyzes board minutes & shareholding,
runs ML suite (placeholder stubs until ML models implemented).

Orchestrates sub-modules:
  - five_cs_mapper: Map worker data → 5 Cs framework
  - metric_computer: Compute DSCR, D/E, margins, CAGR, etc.
  - graph_builder: Build Neo4j knowledge graph (already implemented T1.3)
  - board_analyzer: Governance signals from board minutes
  - shareholding_analyzer: Pledge, ownership, cross-holding signals
"""

import logging
from typing import Dict, Any

from backend.graph.state import (
    CreditAppraisalState,
    OrganizedPackage,
    ComputedMetrics,
    FiveCsMapping,
)
from backend.models.schemas import (
    PipelineStageStatus,
    PipelineStageEnum,
    EventType,
    ThinkingEvent,
)
from backend.agents.organizer.five_cs_mapper import map_to_five_cs
from backend.agents.organizer.metric_computer import compute_metrics
from backend.agents.organizer.graph_builder import build_knowledge_graph
from backend.agents.organizer.board_analyzer import analyze_board_minutes
from backend.agents.organizer.shareholding_analyzer import analyze_shareholding

logger = logging.getLogger(__name__)


async def organizer_node(state: CreditAppraisalState) -> dict:
    """
    Stage 4 — Agent 1.5: The Organizer.

    Transforms raw consolidated data into organized, computed,
    graph-connected, ML-analyzed package.

    Steps:
      1. Map worker outputs to 5 Cs framework
      2. Compute derived financial metrics
      3. Build Neo4j knowledge graph
      4. Analyze board minutes for governance signals
      5. Analyze shareholding pattern
      6. Run ML suite (stubs for now)
      7. Assemble OrganizedPackage
    """
    logger.info(f"[Agent 1.5] Organizing data for session {state.session_id}")

    # Mark pipeline stage active
    for stage in state.pipeline_stages:
        if stage.stage == PipelineStageEnum.ORGANIZATION:
            stage.status = PipelineStageStatus.ACTIVE
            stage.message = "Organizing data into 5 Cs framework..."

    events = list(state.thinking_events or [])
    worker_outputs = state.worker_outputs or {}

    events.append(_event(state.session_id, EventType.READ,
                         f"Reading {len(worker_outputs)} worker outputs for organization"))

    try:
        # ── Step 1: Map to 5 Cs ──
        events.append(_event(state.session_id, EventType.COMPUTED,
                             "Mapping extracted data to 5 Cs framework (Capacity, Character, Capital, Collateral, Conditions)"))
        five_cs = map_to_five_cs(worker_outputs)
        total_fields = (len(five_cs.capacity) + len(five_cs.character) +
                        len(five_cs.capital) + len(five_cs.collateral) +
                        len(five_cs.conditions))
        events.append(_event(state.session_id, EventType.FOUND,
                             f"Mapped {total_fields} data points across 5 Cs: "
                             f"Capacity={len(five_cs.capacity)}, Character={len(five_cs.character)}, "
                             f"Capital={len(five_cs.capital)}, Collateral={len(five_cs.collateral)}, "
                             f"Conditions={len(five_cs.conditions)}"))

        # ── Step 2: Compute metrics ──
        events.append(_event(state.session_id, EventType.COMPUTED,
                             "Computing derived financial metrics (DSCR, D/E, margins, CAGR...)"))
        metrics = compute_metrics(five_cs, worker_outputs)
        _emit_metrics_events(events, state.session_id, metrics)

        # ── Step 3: Build knowledge graph ──
        events.append(_event(state.session_id, EventType.CONNECTING,
                             "Building Neo4j knowledge graph from extracted entities"))
        # graph_builder expects Dict[str, Dict] of extracted_data, not WorkerOutput objects
        raw_outputs: Dict[str, Any] = {}
        for wid, wo in worker_outputs.items():
            if hasattr(wo, "extracted_data"):
                raw_outputs[wid] = wo.extracted_data or {}
            elif isinstance(wo, dict):
                raw_outputs[wid] = wo
            else:
                raw_outputs[wid] = {}
        graph_result = await build_knowledge_graph(
            session_id=state.session_id,
            worker_outputs=raw_outputs,
            company_name=state.company.name if state.company else "Unknown",
        )
        nodes_created = graph_result.get("nodes_created", 0)
        rels_created = graph_result.get("relationships_created", 0)
        events.append(_event(state.session_id, EventType.CONNECTING,
                             f"Knowledge graph built: {nodes_created} nodes, {rels_created} relationships"))

        # ── Step 4: Board analysis ──
        events.append(_event(state.session_id, EventType.READ,
                             "Analyzing board minutes for governance signals"))
        board_result = analyze_board_minutes(worker_outputs)
        if board_result.governance_flags:
            for flag in board_result.governance_flags:
                events.append(_event(state.session_id, EventType.FLAGGED,
                                     f"[Governance] {flag}"))
        else:
            events.append(_event(state.session_id, EventType.ACCEPTED,
                                 "Board governance analysis: no significant concerns"))

        # ── Step 5: Shareholding analysis ──
        events.append(_event(state.session_id, EventType.READ,
                             "Analyzing shareholding pattern for pledge and ownership signals"))
        sh_result = analyze_shareholding(worker_outputs)
        if sh_result.shareholding_flags:
            for flag in sh_result.shareholding_flags:
                events.append(_event(state.session_id, EventType.FLAGGED,
                                     f"[Shareholding] {flag}"))
        else:
            events.append(_event(state.session_id, EventType.ACCEPTED,
                                 "Shareholding analysis: no significant concerns"))

        # ── Step 6: ML Suite ──
        ml_signals: Dict[str, Any] = {}
        events.append(_event(state.session_id, EventType.COMPUTED,
                             "Running ML suite: Isolation Forest + FinBERT"))

        # 6a. Isolation Forest — tabular anomaly on computed metrics
        try:
            metrics_dict = metrics.model_dump() if hasattr(metrics, "model_dump") else {}
            if_result = iforest.detect_anomalies(metrics_dict)
            ml_signals["isolation_forest_anomaly"] = if_result.get("is_anomaly", False)
            ml_signals["isolation_forest_score"] = if_result.get("anomaly_score", 0.0)
            ml_signals["isolation_forest_detail"] = if_result
            if if_result.get("is_anomaly"):
                anom_feats = if_result.get("anomalous_features", [])
                feat_names = ", ".join(f["feature"] for f in anom_feats[:3])
                events.append(_event(state.session_id, EventType.FLAGGED,
                                     f"Isolation Forest: anomaly detected "
                                     f"(score={if_result['anomaly_score']:.2f}) — {feat_names}"))
            else:
                events.append(_event(state.session_id, EventType.ACCEPTED,
                                     f"Isolation Forest: no anomaly "
                                     f"(score={if_result.get('anomaly_score', 0):.2f}, "
                                     f"method={if_result.get('method')})"))
        except Exception as e:
            logger.warning(f"[Agent 1.5] Isolation Forest failed: {e}")
            events.append(_event(state.session_id, EventType.FLAGGED,
                                 f"Isolation Forest unavailable: {e}"))

        # 6b. FinBERT — buried risk in document text
        try:
            doc_texts = {}
            for wid, wo in worker_outputs.items():
                ed = wo.extracted_data if hasattr(wo, "extracted_data") else (wo if isinstance(wo, dict) else {})
                text_content = ed.get("raw_text", "") or ed.get("text", "") or ed.get("notes", "")
                if text_content and len(str(text_content)) > 50:
                    doc_texts[wid] = str(text_content)[:2000]

            if doc_texts:
                fb_result = finbert.analyze_documents(doc_texts)
                ml_signals["finbert_risk_detected"] = fb_result.get("risk_detected", False)
                ml_signals["finbert_risk_score"] = fb_result.get("aggregate_risk_score", 0.0)
                ml_signals["finbert_sentiment"] = fb_result.get("aggregate_sentiment", "neutral")
                ml_signals["finbert_risk_text"] = ""
                if fb_result.get("risk_detected"):
                    top_doc = fb_result.get("highest_risk_document", "")
                    risk_texts = fb_result.get("risk_texts", [])
                    snippet = risk_texts[0]["snippet"][:200] if risk_texts else ""
                    ml_signals["finbert_risk_text"] = snippet
                    events.append(_event(state.session_id, EventType.FLAGGED,
                                         f"FinBERT: risk language detected in {top_doc} "
                                         f"(risk={fb_result['aggregate_risk_score']:.2f})"))
                else:
                    events.append(_event(state.session_id, EventType.ACCEPTED,
                                         f"FinBERT: no buried risk "
                                         f"(sentiment={fb_result.get('aggregate_sentiment', 'neutral')})"))
            else:
                events.append(_event(state.session_id, EventType.COMPUTED,
                                     "FinBERT: no text content to analyze"))
        except Exception as e:
            logger.warning(f"[Agent 1.5] FinBERT failed: {e}")
            events.append(_event(state.session_id, EventType.FLAGGED,
                                 f"FinBERT unavailable: {e}"))

        # ── Step 7: Assemble OrganizedPackage ──
        # Merge board/shareholding analysis into ml_signals for downstream access
        ml_signals["board_analysis"] = board_result.to_dict()
        ml_signals["shareholding_analysis"] = sh_result.to_dict()

        organized = OrganizedPackage(
            five_cs=five_cs,
            computed_metrics=metrics,
            ml_signals=ml_signals,
            graph_entities_created=nodes_created,
            graph_relationships_created=rels_created,
        )

        # Mark stage completed
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.ORGANIZATION:
                stage.status = PipelineStageStatus.COMPLETED
                stage.message = (
                    f"Organized: {total_fields} fields → 5 Cs, "
                    f"{_count_metrics(metrics)} metrics computed, "
                    f"{nodes_created} graph nodes, {rels_created} relationships"
                )

        events.append(_event(state.session_id, EventType.CONCLUDING,
                             f"Agent 1.5 complete — OrganizedPackage assembled with "
                             f"{total_fields} data points, {_count_metrics(metrics)} metrics, "
                             f"graph ({nodes_created}N/{rels_created}R)"))

        return {
            "organized_package": organized,
            "thinking_events": events,
            "pipeline_stages": state.pipeline_stages,
        }

    except Exception as e:
        logger.error(f"[Agent 1.5] Organization failed: {e}")
        events.append(_event(state.session_id, EventType.CRITICAL,
                             f"Organization failed: {str(e)}"))

        # Mark stage failed
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.ORGANIZATION:
                stage.status = PipelineStageStatus.FAILED
                stage.message = f"Organization failed: {str(e)}"

        return {
            "organized_package": OrganizedPackage(),
            "thinking_events": events,
            "pipeline_stages": state.pipeline_stages,
        }


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def _event(session_id: str, event_type: EventType, message: str) -> ThinkingEvent:
    """Create a ThinkingEvent for the Organizer agent."""
    return ThinkingEvent(
        session_id=session_id,
        agent="Agent 1.5 — The Organizer",
        event_type=event_type,
        message=message,
    )


def _emit_metrics_events(events: list, session_id: str, m: ComputedMetrics):
    """Emit ThinkingEvents for computed metrics."""
    if m.dscr is not None:
        events.append(_event(session_id, EventType.COMPUTED, f"DSCR = {m.dscr}x"))
    if m.current_ratio is not None:
        events.append(_event(session_id, EventType.COMPUTED, f"Current Ratio = {m.current_ratio}x"))
    if m.debt_equity_ratio is not None:
        events.append(_event(session_id, EventType.COMPUTED, f"D/E Ratio = {m.debt_equity_ratio}"))
    if m.ebitda_margin is not None:
        events.append(_event(session_id, EventType.COMPUTED, f"EBITDA Margin = {m.ebitda_margin}%"))
    if m.revenue_cagr_3yr is not None:
        events.append(_event(session_id, EventType.COMPUTED,
                             f"Revenue CAGR (3yr) = {m.revenue_cagr_3yr}%"))
    if m.interest_coverage_ratio is not None:
        events.append(_event(session_id, EventType.COMPUTED,
                             f"Interest Coverage Ratio = {m.interest_coverage_ratio}x"))
    if m.gst_bank_divergence_pct is not None:
        event_type = EventType.FLAGGED if m.gst_bank_divergence_pct > 15.0 else EventType.ACCEPTED
        events.append(_event(session_id, event_type,
                             f"GST-Bank Divergence = {m.gst_bank_divergence_pct}%"))
    if m.itr_ar_divergence_pct is not None:
        event_type = EventType.FLAGGED if m.itr_ar_divergence_pct > 15.0 else EventType.ACCEPTED
        events.append(_event(session_id, event_type,
                             f"ITR-AR Divergence = {m.itr_ar_divergence_pct}%"))


def _count_metrics(m: ComputedMetrics) -> int:
    """Count how many metrics were actually computed (non-None)."""
    count = 0
    for field_name in ComputedMetrics.model_fields:
        if getattr(m, field_name) is not None:
            count += 1
    return count
