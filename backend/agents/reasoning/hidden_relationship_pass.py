"""
Intelli-Credit — Pass 3: Hidden Relationship Detection (Graph Reasoning)

Identifies undisclosed connections via shared directors, shell companies,
circular trading patterns, and community cluster analysis.

Score impact: up to -60 points.
"""

import logging
from typing import Dict, Any, List

from backend.graph.state import (
    CompoundInsight,
    CreditAppraisalState,
)
from backend.storage.neo4j_client import get_neo4j_client, NodeType
from backend.thinking.event_emitter import ThinkingEventEmitter

logger = logging.getLogger(__name__)

# Score impact constants
MAX_HIDDEN_REL_PENALTY = -60
SHARED_DIRECTOR_PENALTY = -25
CIRCULAR_TRADING_PENALTY = -35
SUSPICIOUS_CLUSTER_PENALTY = -20


async def run_hidden_relationship_pass(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """
    Pass 3: Detect hidden/undisclosed relationships in the knowledge graph.

    Checks:
    1. Shared directors across multiple companies (conflict of interest)
    2. Circular trading patterns (A→B→C→A fraud)
    3. Suspicious community clusters (tightly connected shell companies)
    """
    await emitter.connecting(
        "Pass 3: Analyzing graph for hidden relationships, circular trading, shell companies..."
    )

    insights: List[CompoundInsight] = []

    # 1. Shared director detection
    shared_insights = await _check_shared_directors(state, emitter)
    insights.extend(shared_insights)

    # 2. Circular trading detection
    circular_insights = await _check_circular_trading(state, emitter)
    insights.extend(circular_insights)

    # 3. Community cluster analysis
    cluster_insights = await _check_suspicious_clusters(state, emitter)
    insights.extend(cluster_insights)

    # Cap total penalty
    total = sum(i.score_impact for i in insights)
    if total < MAX_HIDDEN_REL_PENALTY:
        ratio = MAX_HIDDEN_REL_PENALTY / total if total != 0 else 1
        for i in insights:
            i.score_impact = int(i.score_impact * ratio)

    if not insights:
        await emitter.accepted("Pass 3: No hidden relationships or circular trading detected.")
    else:
        total_impact = sum(i.score_impact for i in insights)
        await emitter.flagged(
            f"Pass 3: Found {len(insights)} hidden relationship concern(s), total impact: {total_impact} pts"
        )

    return insights


async def _check_shared_directors(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """Detect directors who serve on multiple company boards."""
    insights = []
    client = get_neo4j_client()
    await client._ensure_initialized()

    shared = await client.find_shared_directors()

    company_name = ""
    if state.company:
        company_name = state.company.name.lower().strip()

    for entry in shared:
        director = entry.get("director", "")
        companies = entry.get("companies", [])

        if len(companies) < 2:
            continue

        # Only flag if the target company is one of them
        target_involved = any(
            c.lower().strip() == company_name for c in companies
        )
        if not target_involved and company_name:
            continue

        other_companies = [c for c in companies if c.lower().strip() != company_name]

        evidence_chain = [
            f"Director '{director}' serves on {len(companies)} company boards:",
        ]
        for c in companies:
            evidence_chain.append(f"  → {c}")
        evidence_chain.append("Potential conflict of interest / related party not disclosed")

        # More companies = higher severity
        severity = "CRITICAL" if len(companies) >= 4 else "HIGH" if len(companies) >= 3 else "MEDIUM"
        penalty = SHARED_DIRECTOR_PENALTY

        insight = CompoundInsight(
            pass_name="hidden_relationships",
            insight_type="shared_director",
            description=(
                f"Director '{director}' serves on {len(companies)} boards: "
                f"{', '.join(companies)} — potential conflict of interest"
            ),
            evidence_chain=evidence_chain,
            score_impact=penalty,
            confidence=0.90,
            severity=severity,
        )
        insights.append(insight)

        await emitter.critical(
            f"Shared director: '{director}' → {', '.join(other_companies)} "
            f"(undisclosed cross-directorships)"
        )

    return insights


async def _check_circular_trading(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """Detect circular supply chains (A→B→C→A) — indicative of round-tripping fraud."""
    insights = []
    client = get_neo4j_client()

    cycles = await client.detect_circular_trading()

    for cycle in cycles:
        chain_str = " → ".join(cycle) + f" → {cycle[0]}"
        evidence_chain = [
            f"Circular trading chain detected: {chain_str}",
            f"Cycle length: {len(cycle)} entities",
            "Potential round-tripping / fictitious revenue generation",
        ]

        insight = CompoundInsight(
            pass_name="hidden_relationships",
            insight_type="circular_trading",
            description=(
                f"Circular trading detected: {chain_str} — "
                f"potential round-tripping of goods/services to inflate revenue"
            ),
            evidence_chain=evidence_chain,
            score_impact=CIRCULAR_TRADING_PENALTY,
            confidence=0.85,
            severity="CRITICAL",
        )
        insights.append(insight)

        await emitter.critical(
            f"CIRCULAR TRADING: {chain_str} — suspected revenue round-tripping"
        )

    return insights


async def _check_suspicious_clusters(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """Analyze community clusters for suspicious tightly-connected groups."""
    insights = []
    client = get_neo4j_client()

    clusters = await client.get_community_clusters()

    company_name = ""
    if state.company:
        company_name = state.company.name.lower().strip()

    for cluster in clusters:
        # Only analyze clusters containing the target company
        if company_name and not any(
            c.lower().strip() == company_name for c in cluster
        ):
            continue

        # A cluster with many entities might indicate a shell company network
        if len(cluster) >= 6:
            evidence_chain = [
                f"Large connected cluster ({len(cluster)} entities):",
            ]
            for entity in cluster[:10]:  # Show first 10
                evidence_chain.append(f"  → {entity}")
            if len(cluster) > 10:
                evidence_chain.append(f"  ... and {len(cluster) - 10} more")
            evidence_chain.append(
                "Dense connectivity may indicate a controlled group of entities"
            )

            insight = CompoundInsight(
                pass_name="hidden_relationships",
                insight_type="suspicious_cluster",
                description=(
                    f"Suspicious entity cluster: {len(cluster)} tightly connected entities "
                    f"including target company — may indicate shell company network"
                ),
                evidence_chain=evidence_chain,
                score_impact=SUSPICIOUS_CLUSTER_PENALTY,
                confidence=0.65,
                severity="MEDIUM",
            )
            insights.append(insight)

            await emitter.questioning(
                f"Suspicious cluster: {len(cluster)} connected entities — "
                f"potential shell company network"
            )

    return insights
