"""
Intelli-Credit — Pass 1: Contradiction Detection (Graph Reasoning)

Compares self-reported document claims against externally verified findings.
Detects lies, omissions, and material misstatements.

Score impact: up to -45 points.
"""

import logging
from typing import Dict, Any, List, Optional

from backend.graph.state import (
    CompoundInsight,
    CreditAppraisalState,
    ResearchFinding,
    CrossVerificationResult,
)
from backend.storage.neo4j_client import get_neo4j_client, NodeType, RelationshipType
from backend.thinking.event_emitter import ThinkingEventEmitter

logger = logging.getLogger(__name__)

# Score impact constants
MAX_CONTRADICTION_PENALTY = -45
LITIGATION_CONCEALMENT_PENALTY = -25
REVENUE_CONTRADICTION_PENALTY = -15
RPT_CONCEALMENT_PENALTY = -20
DISCLOSURE_GAP_PENALTY = -10


async def run_contradiction_pass(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """
    Pass 1: Find contradictions between document claims and verified sources.

    Checks:
    1. Litigation disclosure: AR claims vs NJDG/Court graph records
    2. Revenue consistency: AR vs ITR vs GST vs Bank cross-verifications
    3. RPT disclosure: self-reported RPTs vs graph-discovered relationships
    4. Director/governance discrepancies
    """
    await emitter.connecting(
        "Pass 1: Scanning for contradictions between self-reported and verified data..."
    )

    insights: List[CompoundInsight] = []

    # 1. Litigation concealment check
    litigation_insights = await _check_litigation_concealment(state, emitter)
    insights.extend(litigation_insights)

    # 2. Revenue contradiction check
    revenue_insights = await _check_revenue_contradictions(state, emitter)
    insights.extend(revenue_insights)

    # 3. RPT concealment check (graph-based)
    rpt_insights = await _check_rpt_concealment_graph(state, emitter)
    insights.extend(rpt_insights)

    # Cap total penalty
    total = sum(i.score_impact for i in insights)
    if total < MAX_CONTRADICTION_PENALTY:
        # Scale down proportionally
        ratio = MAX_CONTRADICTION_PENALTY / total if total != 0 else 1
        for i in insights:
            i.score_impact = int(i.score_impact * ratio)

    if not insights:
        await emitter.accepted("Pass 1: No contradictions detected — self-reported data consistent with verified sources.")
    else:
        total_impact = sum(i.score_impact for i in insights)
        await emitter.flagged(
            f"Pass 1: Found {len(insights)} contradiction(s), total impact: {total_impact} pts"
        )

    return insights


async def _check_litigation_concealment(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """Check if AR-disclosed litigation matches graph records from NJDG/courts."""
    insights = []

    # Get disclosed litigation from W1 (Annual Report)
    w1_data = state.worker_outputs.get("W1", None)
    disclosed_cases: List[Dict[str, Any]] = []
    if w1_data:
        extracted = w1_data.extracted_data if hasattr(w1_data, "extracted_data") else (w1_data if isinstance(w1_data, dict) else {})
        litigation = extracted.get("litigation", [])
        if isinstance(litigation, list):
            disclosed_cases = litigation

    # Get actual cases from Neo4j graph (populated by NJDG enricher)
    client = get_neo4j_client()
    await client._ensure_initialized()

    company_name = ""
    if state.company:
        company_name = state.company.name
    elif w1_data:
        extracted = w1_data.extracted_data if hasattr(w1_data, "extracted_data") else (w1_data if isinstance(w1_data, dict) else {})
        company_name = extracted.get("company_name", "")

    graph_cases = await client.get_relationships(
        to_label=NodeType.COMPANY,
        to_name=company_name,
        rel_type=RelationshipType.FILED_CASE_AGAINST,
    )

    disclosed_count = len(disclosed_cases)
    graph_count = len(graph_cases)

    if graph_count > disclosed_count:
        undisclosed = graph_count - disclosed_count
        # Build evidence chain from graph data
        evidence_chain = [
            f"Annual Report discloses {disclosed_count} case(s)",
            f"NJDG/Court records show {graph_count} case(s) against company",
        ]
        for case_rel in graph_cases:
            from_node = case_rel.get("from", {})
            case_name = from_node.get("name", "Unknown")
            props = case_rel.get("properties", {})
            source = props.get("source", "graph")
            evidence_chain.append(f"Case: {case_name} (source: {source})")

        severity = "HIGH" if undisclosed >= 2 else "MEDIUM"
        penalty = LITIGATION_CONCEALMENT_PENALTY if undisclosed >= 2 else DISCLOSURE_GAP_PENALTY

        insight = CompoundInsight(
            pass_name="contradictions",
            insight_type="litigation_concealment",
            description=(
                f"Company disclosed {disclosed_count} litigation case(s) in Annual Report, "
                f"but graph records show {graph_count} — {undisclosed} undisclosed case(s)"
            ),
            evidence_chain=evidence_chain,
            score_impact=penalty,
            confidence=0.90,
            severity=severity,
        )
        insights.append(insight)

        await emitter.critical(
            f"Litigation concealment: {undisclosed} undisclosed case(s) found. "
            f"AR: {disclosed_count}, Actual: {graph_count}"
        )
    elif graph_count > 0:
        await emitter.accepted(
            f"Litigation disclosure consistent: {disclosed_count} case(s) in AR, "
            f"{graph_count} in graph records"
        )

    return insights


async def _check_revenue_contradictions(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """Check cross-verification results for material revenue contradictions."""
    insights = []

    if not state.raw_data_package:
        return insights

    for cv in state.raw_data_package.cross_verifications:
        if cv.status == "conflicting" and cv.max_deviation_pct > 15:
            evidence_chain = [
                f"Cross-verification field: {cv.field_name}",
                f"Max deviation: {cv.max_deviation_pct:.1f}%",
            ]
            for src_name, nf in cv.sources.items():
                evidence_chain.append(
                    f"{src_name}: {nf.value} (conf: {nf.confidence:.0%})"
                )

            penalty = REVENUE_CONTRADICTION_PENALTY if cv.max_deviation_pct > 25 else DISCLOSURE_GAP_PENALTY

            insight = CompoundInsight(
                pass_name="contradictions",
                insight_type="revenue_contradiction",
                description=(
                    f"Material revenue contradiction: {cv.field_name} deviates "
                    f"{cv.max_deviation_pct:.1f}% across sources"
                ),
                evidence_chain=evidence_chain,
                score_impact=penalty,
                confidence=0.85,
                severity="HIGH" if cv.max_deviation_pct > 25 else "MEDIUM",
            )
            insights.append(insight)

            await emitter.flagged(
                f"Revenue contradiction: {cv.field_name} — {cv.max_deviation_pct:.1f}% deviation"
            )

    return insights


async def _check_rpt_concealment_graph(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """Check if graph shows relationships not disclosed as RPTs."""
    insights = []
    client = get_neo4j_client()

    # Get disclosed RPT parties from W1
    w1_data = state.worker_outputs.get("W1", None)
    disclosed_rpt_parties: set = set()
    if w1_data:
        extracted = w1_data.extracted_data if hasattr(w1_data, "extracted_data") else (w1_data if isinstance(w1_data, dict) else {})
        rpts = extracted.get("rpts", {})
        for txn in rpts.get("transactions", []):
            party = txn.get("party", "")
            if party:
                disclosed_rpt_parties.add(party.lower().strip())

    # Check shared directors — these entities should be disclosed as RPTs
    shared = await client.find_shared_directors()
    for entry in shared:
        companies = entry.get("companies", [])
        director = entry.get("director", "")
        # If a director serves on both target + another company,
        # the other company should be an RPT
        if len(companies) >= 2:
            for comp in companies:
                comp_lower = comp.lower().strip()
                # Skip the target company itself
                if state.company and comp_lower == state.company.name.lower().strip():
                    continue
                # Check if this related company is disclosed
                if comp_lower not in disclosed_rpt_parties:
                    insight = CompoundInsight(
                        pass_name="contradictions",
                        insight_type="rpt_concealment_graph",
                        description=(
                            f"Director '{director}' serves on '{comp}' — "
                            f"not disclosed as Related Party in Annual Report"
                        ),
                        evidence_chain=[
                            f"Director {director} → IS_DIRECTOR_OF → {comp}",
                            f"Director {director} → IS_DIRECTOR_OF → target company",
                            f"'{comp}' not found in W1 RPT disclosures",
                        ],
                        score_impact=RPT_CONCEALMENT_PENALTY,
                        confidence=0.85,
                        severity="HIGH",
                    )
                    insights.append(insight)

                    await emitter.critical(
                        f"RPT concealment (graph): Director '{director}' links target to '{comp}' — undisclosed"
                    )

    return insights
