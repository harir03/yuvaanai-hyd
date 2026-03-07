"""
Intelli-Credit — Pass 2: Cascade Risk Analysis (Graph Reasoning)

Traces multi-hop chains in the knowledge graph to identify cascade failure risks.
E.g., counterparty in NCLT → revenue at risk → DSCR drops below 1.0x.

Score impact: up to -50 points.
"""

import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal

from backend.graph.state import (
    CompoundInsight,
    CreditAppraisalState,
)
from backend.storage.neo4j_client import get_neo4j_client, NodeType, RelationshipType
from backend.thinking.event_emitter import ThinkingEventEmitter

logger = logging.getLogger(__name__)

# Score impact constants
MAX_CASCADE_PENALTY = -50
NCLT_COUNTERPARTY_PENALTY = -30
HIGH_CONCENTRATION_PENALTY = -20
DSCR_BREACH_PENALTY = -25
SUPPLIER_RISK_PENALTY = -15


async def run_cascade_pass(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """
    Pass 2: Cascade risk analysis via multi-hop graph traversal.

    Traces:
    1. Customer/supplier in NCLT/NPA → revenue/supply chain at risk
    2. Revenue concentration → DSCR impact if counterparty fails
    3. Supplier concentration → production risk
    """
    await emitter.connecting(
        "Pass 2: Tracing cascade risk chains through counterparty graph..."
    )

    insights: List[CompoundInsight] = []

    # 1. Check counterparties with NCLT/litigation exposure
    nclt_insights = await _check_counterparty_nclt_risk(state, emitter)
    insights.extend(nclt_insights)

    # 2. Revenue concentration risk
    concentration_insights = await _check_revenue_concentration(state, emitter)
    insights.extend(concentration_insights)

    # 3. DSCR cascade impact
    dscr_insights = await _check_dscr_cascade(state, emitter)
    insights.extend(dscr_insights)

    # Cap total penalty
    total = sum(i.score_impact for i in insights)
    if total < MAX_CASCADE_PENALTY:
        ratio = MAX_CASCADE_PENALTY / total if total != 0 else 1
        for i in insights:
            i.score_impact = int(i.score_impact * ratio)

    if not insights:
        await emitter.accepted("Pass 2: No significant cascade risks detected in counterparty graph.")
    else:
        total_impact = sum(i.score_impact for i in insights)
        await emitter.flagged(
            f"Pass 2: Found {len(insights)} cascade risk(s), total impact: {total_impact} pts"
        )

    return insights


async def _check_counterparty_nclt_risk(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """Check if any counterparties have NCLT/litigation exposure via graph."""
    insights = []
    client = get_neo4j_client()
    await client._ensure_initialized()

    company_name = ""
    if state.company:
        company_name = state.company.name
    else:
        w1 = state.worker_outputs.get("W1", None)
        if w1:
            extracted = w1.extracted_data if hasattr(w1, "extracted_data") else (w1 if isinstance(w1, dict) else {})
            company_name = extracted.get("company_name", "")

    if not company_name:
        return insights

    # Multi-hop BFS from company — find counterparties connected to courts/cases
    paths = await client.multi_hop_query(NodeType.COMPANY, company_name, max_hops=3)

    for path_entry in paths:
        end_node = path_entry.get("end_node", {})
        end_label = end_node.get("label", "")
        end_name = end_node.get("name", "")
        hops = path_entry.get("hops", 0)
        path_steps = path_entry.get("path", [])

        # Look for Case or Court nodes reachable from the company
        if end_label in ("Case", "Court"):
            # Build the chain narrative
            chain = []
            for step in path_steps:
                from_name = step.get("from", {}).get("name", "?")
                rel = step.get("relationship", "?")
                to_name = step.get("to", {}).get("name", "?")
                chain.append(f"{from_name} →[{rel}]→ {to_name}")

            # Check if the case involves a counterparty (not the target itself)
            involves_counterparty = any(
                step.get("from", {}).get("label", "") in ("Supplier", "Customer")
                or step.get("to", {}).get("label", "") in ("Supplier", "Customer")
                for step in path_steps
            )

            if involves_counterparty:
                case_props = end_node
                case_type = case_props.get("case_type", "litigation")
                amount = case_props.get("amount", "unknown")

                insight = CompoundInsight(
                    pass_name="cascade",
                    insight_type="counterparty_nclt",
                    description=(
                        f"Counterparty litigation detected: {end_name} "
                        f"({case_type}) reachable in {hops} hops — potential supply/revenue disruption"
                    ),
                    evidence_chain=chain,
                    score_impact=NCLT_COUNTERPARTY_PENALTY,
                    confidence=0.80,
                    severity="HIGH",
                )
                insights.append(insight)

                await emitter.critical(
                    f"Cascade risk: {end_name} ({case_type}) connected to counterparty in {hops} hops"
                )

    return insights


async def _check_revenue_concentration(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """Check if revenue is concentrated in few customers (graph-based count)."""
    insights = []
    client = get_neo4j_client()

    company_name = ""
    if state.company:
        company_name = state.company.name
    else:
        w1 = state.worker_outputs.get("W1", None)
        if w1:
            extracted = w1.extracted_data if hasattr(w1, "extracted_data") else (w1 if isinstance(w1, dict) else {})
            company_name = extracted.get("company_name", "")

    if not company_name:
        return insights

    # Count customer relationships
    customer_rels = await client.get_relationships(
        from_label=NodeType.COMPANY,
        from_name=company_name,
        rel_type=RelationshipType.SUPPLIES_TO,
    )

    # Also check BUYS_FROM (reverse direction)
    buyer_rels = await client.get_relationships(
        to_label=NodeType.COMPANY,
        to_name=company_name,
        rel_type=RelationshipType.BUYS_FROM,
    )

    total_customers = len(customer_rels) + len(buyer_rels)

    # Check RPT-based revenue concentration from W1
    w1_data = state.worker_outputs.get("W1", None)
    if w1_data:
        extracted = w1_data.extracted_data if hasattr(w1_data, "extracted_data") else (w1_data if isinstance(w1_data, dict) else {})
        rpts = extracted.get("rpts", {})
        transactions = rpts.get("transactions", [])

        # Sum sale transactions
        sale_amounts = []
        for txn in transactions:
            nature = txn.get("nature", "").lower()
            amount = txn.get("amount", 0)
            if "sale" in nature and amount > 0:
                sale_amounts.append((txn.get("party", ""), amount))

        if sale_amounts:
            total_sales = sum(a for _, a in sale_amounts)
            if total_sales > 0:
                top_customer, top_amount = max(sale_amounts, key=lambda x: x[1])
                concentration_pct = (top_amount / total_sales) * 100

                if concentration_pct > 40:
                    insight = CompoundInsight(
                        pass_name="cascade",
                        insight_type="revenue_concentration",
                        description=(
                            f"Revenue concentration risk: top customer '{top_customer}' "
                            f"accounts for {concentration_pct:.0f}% of RPT sales"
                        ),
                        evidence_chain=[
                            f"Top customer: {top_customer} — ₹{top_amount:.1f}cr",
                            f"Total RPT sales: ₹{total_sales:.1f}cr",
                            f"Concentration: {concentration_pct:.0f}%",
                            f"Total customers in graph: {total_customers}",
                        ],
                        score_impact=HIGH_CONCENTRATION_PENALTY,
                        confidence=0.75,
                        severity="MEDIUM",
                    )
                    insights.append(insight)

                    await emitter.flagged(
                        f"Revenue concentration: {top_customer} = {concentration_pct:.0f}% of RPT sales"
                    )

    return insights


async def _check_dscr_cascade(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """Check if counterparty failure would push DSCR below 1.0x."""
    insights = []

    # Need organized package for DSCR
    if not state.organized_package or not state.organized_package.computed_metrics:
        return insights

    metrics = state.organized_package.computed_metrics
    current_dscr = metrics.dscr
    if current_dscr is None:
        return insights

    # Get revenue from W1 to compute at-risk amount
    w1_data = state.worker_outputs.get("W1", None)
    if not w1_data:
        return insights

    extracted = w1_data.extracted_data if hasattr(w1_data, "extracted_data") else (w1_data if isinstance(w1_data, dict) else {})
    revenue_data = extracted.get("revenue", {})

    # Get latest revenue
    latest_revenue = 0
    if isinstance(revenue_data, dict):
        for year in sorted(revenue_data.keys(), reverse=True):
            val = revenue_data[year]
            if isinstance(val, (int, float)) and val > 0:
                latest_revenue = val
                break
    elif isinstance(revenue_data, (int, float)):
        latest_revenue = revenue_data

    if latest_revenue <= 0:
        return insights

    # Simulate: if top counterparty fails and takes 30% revenue
    # (conservative estimate based on typical concentration)
    at_risk_pct = 0.30
    revenue_at_risk = latest_revenue * at_risk_pct
    projected_dscr = current_dscr * (1 - at_risk_pct)

    if projected_dscr < 1.0 and current_dscr >= 1.0:
        insight = CompoundInsight(
            pass_name="cascade",
            insight_type="dscr_cascade",
            description=(
                f"DSCR cascade risk: if top counterparty fails (30% revenue at risk), "
                f"DSCR drops from {current_dscr:.2f}x to {projected_dscr:.2f}x — below 1.0x threshold"
            ),
            evidence_chain=[
                f"Current DSCR: {current_dscr:.2f}x",
                f"Revenue: ₹{latest_revenue:.1f}cr",
                f"30% revenue at risk: ₹{revenue_at_risk:.1f}cr",
                f"Projected DSCR: {projected_dscr:.2f}x (below 1.0x)",
            ],
            score_impact=DSCR_BREACH_PENALTY,
            confidence=0.70,
            severity="HIGH",
        )
        insights.append(insight)

        await emitter.critical(
            f"DSCR cascade: {current_dscr:.2f}x → {projected_dscr:.2f}x if top counterparty fails"
        )
    elif current_dscr > 0:
        await emitter.computed(
            f"DSCR cascade simulation: {current_dscr:.2f}x → {projected_dscr:.2f}x "
            f"(above 1.0x — acceptable resilience)"
        )

    return insights
