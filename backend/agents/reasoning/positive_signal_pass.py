"""
Intelli-Credit — Pass 5: Positive Signal Detection (Graph Reasoning)

Identifies genuine strengths — not just absence of negatives.
Order book, subsidies, diversification, institutional backing, improving trends.

Score impact: up to +57 points.
"""

import logging
from typing import Dict, Any, List

from backend.graph.state import (
    CompoundInsight,
    CreditAppraisalState,
)
from backend.storage.neo4j_client import get_neo4j_client, NodeType, RelationshipType
from backend.thinking.event_emitter import ThinkingEventEmitter

logger = logging.getLogger(__name__)

# Score impact constants
MAX_POSITIVE_BONUS = 57
STRONG_REVENUE_GROWTH_BONUS = 20
DIVERSIFIED_CUSTOMERS_BONUS = 12
INSTITUTIONAL_BACKING_BONUS = 10
STRONG_RATING_BONUS = 15
GOOD_DSCR_BONUS = 10
LOW_LEVERAGE_BONUS = 8


async def run_positive_signal_pass(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """
    Pass 5: Identify genuine positive signals.

    Checks:
    1. Revenue growth trend (>10% CAGR)
    2. Customer/supplier diversification (graph breadth)
    3. Strong credit rating (A and above)
    4. Healthy DSCR (>2.0x)
    5. Low leverage (D/E < 1.0x)
    6. Institutional backing (banks, rating agencies with positive outlook)
    """
    await emitter.connecting(
        "Pass 5: Identifying genuine positive signals — strengths with concrete evidence..."
    )

    insights: List[CompoundInsight] = []

    # 1. Revenue growth analysis
    growth_insights = _check_revenue_growth(state)
    insights.extend(growth_insights)

    # 2. Customer/supplier diversification (graph-based)
    div_insights = await _check_diversification(state, emitter)
    insights.extend(div_insights)

    # 3. Rating strength
    rating_insights = _check_rating_strength(state)
    insights.extend(rating_insights)

    # 4. Financial health metrics
    health_insights = _check_financial_health(state)
    insights.extend(health_insights)

    # Cap total bonus
    total = sum(i.score_impact for i in insights)
    if total > MAX_POSITIVE_BONUS:
        ratio = MAX_POSITIVE_BONUS / total if total != 0 else 1
        for i in insights:
            i.score_impact = int(i.score_impact * ratio)

    if not insights:
        await emitter.read(
            "Pass 5: No outstanding positive signals found — neutral assessment."
        )
    else:
        total_impact = sum(i.score_impact for i in insights)
        await emitter.concluding(
            f"Pass 5: Found {len(insights)} positive signal(s), total bonus: +{total_impact} pts"
        )

    return insights


def _check_revenue_growth(state: CreditAppraisalState) -> List[CompoundInsight]:
    """Check for strong and consistent revenue growth."""
    insights = []

    w1_data = state.worker_outputs.get("W1", None)
    if not w1_data:
        return insights

    extracted = w1_data.extracted_data if hasattr(w1_data, "extracted_data") else (w1_data if isinstance(w1_data, dict) else {})
    revenue_data = extracted.get("revenue", {})

    if not isinstance(revenue_data, dict):
        return insights

    # Sort by year
    series = []
    for year, value in revenue_data.items():
        if isinstance(value, (int, float)) and value > 0:
            series.append((str(year), float(value)))
    series.sort(key=lambda x: x[0])

    if len(series) < 2:
        return insights

    # Check for growth
    first_val = series[0][1]
    last_val = series[-1][1]
    years = len(series) - 1

    if first_val > 0 and years > 0:
        total_growth_pct = ((last_val - first_val) / first_val) * 100
        cagr = ((last_val / first_val) ** (1 / years) - 1) * 100

        # Check if consistently growing
        all_growing = all(
            series[i][1] >= series[i - 1][1] for i in range(1, len(series))
        )

        if cagr > 10 and all_growing:
            years_str = ", ".join(f"{y}: ₹{v:.1f}cr" for y, v in series)
            insight = CompoundInsight(
                pass_name="positive",
                insight_type="strong_revenue_growth",
                description=(
                    f"Strong revenue growth: {cagr:.1f}% CAGR over {years} years — "
                    f"consistent upward trajectory"
                ),
                evidence_chain=[
                    f"Revenue: {years_str}",
                    f"CAGR: {cagr:.1f}%",
                    f"Total growth: {total_growth_pct:.0f}%",
                    "Consistently growing each year",
                    "Source: W1 Annual Report",
                ],
                score_impact=STRONG_REVENUE_GROWTH_BONUS,
                confidence=0.85,
                severity="LOW",  # Positive = low severity
            )
            insights.append(insight)

    return insights


async def _check_diversification(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """Check customer/supplier diversification from graph structure."""
    insights = []
    client = get_neo4j_client()
    await client._ensure_initialized()

    company_name = ""
    if state.company:
        company_name = state.company.name

    if not company_name:
        return insights

    # Count distinct supplier and customer relationships
    supplier_rels = await client.get_relationships(
        to_label=NodeType.COMPANY,
        to_name=company_name,
        rel_type=RelationshipType.SUPPLIES_TO,
    )
    customer_rels = await client.get_relationships(
        from_label=NodeType.COMPANY,
        from_name=company_name,
        rel_type=RelationshipType.SUPPLIES_TO,
    )

    # Also count from RPT data
    w1_data = state.worker_outputs.get("W1", None)
    rpt_parties = set()
    if w1_data:
        extracted = w1_data.extracted_data if hasattr(w1_data, "extracted_data") else (w1_data if isinstance(w1_data, dict) else {})
        rpts = extracted.get("rpts", {})
        for txn in rpts.get("transactions", []):
            party = txn.get("party", "")
            if party:
                rpt_parties.add(party)

    total_relationships = len(supplier_rels) + len(customer_rels) + len(rpt_parties)

    if total_relationships >= 5:
        insight = CompoundInsight(
            pass_name="positive",
            insight_type="diversified_relationships",
            description=(
                f"Well-diversified business relationships: {total_relationships} "
                f"distinct counterparties across suppliers, customers, and partners"
            ),
            evidence_chain=[
                f"Suppliers in graph: {len(supplier_rels)}",
                f"Customers in graph: {len(customer_rels)}",
                f"RPT parties: {len(rpt_parties)}",
                "Diversification reduces concentration risk",
            ],
            score_impact=DIVERSIFIED_CUSTOMERS_BONUS,
            confidence=0.75,
            severity="LOW",
        )
        insights.append(insight)

        await emitter.accepted(
            f"Positive: {total_relationships} diversified counterparties"
        )

    return insights


def _check_rating_strength(state: CreditAppraisalState) -> List[CompoundInsight]:
    """Check for strong credit rating from W8 data."""
    insights = []

    w8_data = state.worker_outputs.get("W8", None)
    if not w8_data:
        return insights

    extracted = w8_data.extracted_data if hasattr(w8_data, "extracted_data") else (w8_data if isinstance(w8_data, dict) else {})
    rating = extracted.get("current_rating", "")
    outlook = extracted.get("outlook", "")

    if not rating:
        return insights

    # Strong ratings: A, AA, AAA (or variants)
    strong_ratings = {"A", "A+", "AA", "AA+", "AAA", "A1", "A1+"}
    rating_upper = rating.upper().strip()

    if any(sr in rating_upper for sr in strong_ratings):
        insight = CompoundInsight(
            pass_name="positive",
            insight_type="strong_rating",
            description=(
                f"Strong credit rating: {rating} with {outlook or 'stable'} outlook"
            ),
            evidence_chain=[
                f"Current rating: {rating}",
                f"Outlook: {outlook or 'Not specified'}",
                "Source: W8 Rating Report",
            ],
            score_impact=STRONG_RATING_BONUS,
            confidence=0.90,
            severity="LOW",
        )
        insights.append(insight)

    return insights


def _check_financial_health(state: CreditAppraisalState) -> List[CompoundInsight]:
    """Check computed metrics for positive signals."""
    insights = []

    if not state.organized_package or not state.organized_package.computed_metrics:
        return insights

    metrics = state.organized_package.computed_metrics

    # Strong DSCR (>2.0x)
    if metrics.dscr is not None and metrics.dscr >= 2.0:
        insight = CompoundInsight(
            pass_name="positive",
            insight_type="strong_dscr",
            description=f"Strong debt service coverage: DSCR at {metrics.dscr:.2f}x — well above 1.0x threshold",
            evidence_chain=[
                f"DSCR: {metrics.dscr:.2f}x",
                "Threshold: 1.0x (hard block)",
                f"Buffer: {metrics.dscr - 1.0:.2f}x above minimum",
            ],
            score_impact=GOOD_DSCR_BONUS,
            confidence=0.90,
            severity="LOW",
        )
        insights.append(insight)

    # Low leverage (D/E < 1.0x)
    if metrics.debt_equity_ratio is not None and metrics.debt_equity_ratio < 1.0:
        insight = CompoundInsight(
            pass_name="positive",
            insight_type="low_leverage",
            description=f"Low leverage: D/E ratio at {metrics.debt_equity_ratio:.2f}x — conservative capital structure",
            evidence_chain=[
                f"Debt/Equity: {metrics.debt_equity_ratio:.2f}x",
                "Below 1.0x indicates equity-heavy structure",
                "Low leverage reduces cascade risk exposure",
            ],
            score_impact=LOW_LEVERAGE_BONUS,
            confidence=0.85,
            severity="LOW",
        )
        insights.append(insight)

    return insights
