"""
Intelli-Credit — Pass 4: Temporal Pattern Detection (Graph Reasoning)

Analyzes multi-year financial trends to identify deterioration patterns,
approaching thresholds, and accelerating decline.

Score impact: up to -20 points.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.graph.state import (
    CompoundInsight,
    CreditAppraisalState,
)
from backend.thinking.event_emitter import ThinkingEventEmitter

logger = logging.getLogger(__name__)

# Score impact constants
MAX_TEMPORAL_PENALTY = -20
DECLINING_TREND_PENALTY = -10
ACCELERATING_DECLINE_PENALTY = -15
THRESHOLD_APPROACH_PENALTY = -12


async def run_temporal_pass(
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> List[CompoundInsight]:
    """
    Pass 4: Detect temporal patterns (multi-year deterioration trends).

    Checks:
    1. Revenue / EBITDA / PAT declining trends
    2. Accelerating deterioration (getting worse faster)
    3. Metrics approaching critical thresholds (DSCR near 1.0x, D/E near 3.0x)
    """
    await emitter.connecting(
        "Pass 4: Analyzing multi-year financial trends for deterioration patterns..."
    )

    insights: List[CompoundInsight] = []

    # Extract time-series data from W1 worker output
    w1_data = state.worker_outputs.get("W1", None)
    if not w1_data:
        await emitter.read("Pass 4: No W1 data available — skipping temporal analysis.")
        return insights

    extracted = w1_data.extracted_data if hasattr(w1_data, "extracted_data") else (w1_data if isinstance(w1_data, dict) else {})

    # 1. Revenue trend analysis
    revenue_insights = _analyze_revenue_trend(extracted)
    insights.extend(revenue_insights)

    # 2. EBITDA margin trend
    ebitda_insights = _analyze_ebitda_trend(extracted)
    insights.extend(ebitda_insights)

    # 3. Debt growth trend
    debt_insights = _analyze_debt_trend(extracted)
    insights.extend(debt_insights)

    # 4. DSCR threshold proximity (from organized package)
    if state.organized_package and state.organized_package.computed_metrics:
        threshold_insights = _check_threshold_proximity(state.organized_package.computed_metrics)
        insights.extend(threshold_insights)

    # Cap total penalty
    total = sum(i.score_impact for i in insights)
    if total < MAX_TEMPORAL_PENALTY:
        ratio = MAX_TEMPORAL_PENALTY / total if total != 0 else 1
        for i in insights:
            i.score_impact = int(i.score_impact * ratio)

    if not insights:
        await emitter.accepted("Pass 4: No concerning temporal deterioration patterns detected.")
    else:
        total_impact = sum(i.score_impact for i in insights)
        await emitter.flagged(
            f"Pass 4: Found {len(insights)} concerning temporal pattern(s), total impact: {total_impact} pts"
        )

    return insights


def _extract_time_series(data: Dict[str, Any], key: str) -> List[Tuple[str, float]]:
    """Extract a time-series from worker data as sorted (year, value) pairs."""
    series_data = data.get(key, {})
    if not isinstance(series_data, dict):
        return []

    pairs = []
    for year, value in series_data.items():
        if isinstance(value, (int, float)) and value != 0:
            pairs.append((str(year), float(value)))

    # Sort by year
    pairs.sort(key=lambda x: x[0])
    return pairs


def _is_declining(series: List[Tuple[str, float]]) -> bool:
    """Check if a series has consistent decline (each year < previous)."""
    if len(series) < 2:
        return False
    return all(series[i][1] < series[i - 1][1] for i in range(1, len(series)))


def _is_accelerating_decline(series: List[Tuple[str, float]]) -> bool:
    """Check if decline is accelerating (YoY change getting worse)."""
    if len(series) < 3:
        return False
    changes = [series[i][1] - series[i - 1][1] for i in range(1, len(series))]
    # Accelerating decline: each change is more negative than the previous
    return all(changes[i] < changes[i - 1] for i in range(1, len(changes)))


def _analyze_revenue_trend(data: Dict[str, Any]) -> List[CompoundInsight]:
    """Analyze multi-year revenue trend."""
    insights = []
    series = _extract_time_series(data, "revenue")

    if len(series) < 2:
        return insights

    if _is_declining(series):
        years_str = ", ".join(f"{y}: ₹{v:.1f}cr" for y, v in series)
        first_val = series[0][1]
        last_val = series[-1][1]
        decline_pct = ((first_val - last_val) / first_val * 100) if first_val > 0 else 0

        penalty = ACCELERATING_DECLINE_PENALTY if _is_accelerating_decline(series) else DECLINING_TREND_PENALTY
        severity = "HIGH" if decline_pct > 20 else "MEDIUM"

        insight = CompoundInsight(
            pass_name="temporal",
            insight_type="revenue_decline",
            description=(
                f"Revenue declining over {len(series)} years: {years_str} "
                f"({decline_pct:.0f}% total decline)"
            ),
            evidence_chain=[
                f"Revenue time series: {years_str}",
                f"Total decline: {decline_pct:.0f}%",
                "Accelerating decline" if _is_accelerating_decline(series) else "Steady decline",
                "Source: W1 Annual Report",
            ],
            score_impact=penalty,
            confidence=0.85,
            severity=severity,
        )
        insights.append(insight)

    return insights


def _analyze_ebitda_trend(data: Dict[str, Any]) -> List[CompoundInsight]:
    """Analyze multi-year EBITDA trend."""
    insights = []
    series = _extract_time_series(data, "ebitda")

    if len(series) < 2:
        return insights

    if _is_declining(series):
        years_str = ", ".join(f"{y}: ₹{v:.1f}cr" for y, v in series)
        first_val = series[0][1]
        last_val = series[-1][1]
        decline_pct = ((first_val - last_val) / first_val * 100) if first_val > 0 else 0

        penalty = DECLINING_TREND_PENALTY
        severity = "HIGH" if decline_pct > 25 else "MEDIUM"

        insight = CompoundInsight(
            pass_name="temporal",
            insight_type="ebitda_decline",
            description=(
                f"EBITDA declining over {len(series)} years: {years_str} "
                f"({decline_pct:.0f}% total decline)"
            ),
            evidence_chain=[
                f"EBITDA time series: {years_str}",
                f"Margin compression: {decline_pct:.0f}%",
                "Source: W1 Annual Report",
            ],
            score_impact=penalty,
            confidence=0.80,
            severity=severity,
        )
        insights.append(insight)

    return insights


def _analyze_debt_trend(data: Dict[str, Any]) -> List[CompoundInsight]:
    """Check if total debt is growing while revenue declines."""
    insights = []
    revenue_series = _extract_time_series(data, "revenue")
    debt_series = _extract_time_series(data, "total_debt")

    if len(debt_series) < 2:
        return insights

    # Debt increasing
    debt_increasing = all(
        debt_series[i][1] > debt_series[i - 1][1]
        for i in range(1, len(debt_series))
    )

    # Revenue declining
    revenue_declining = _is_declining(revenue_series) if len(revenue_series) >= 2 else False

    if debt_increasing and revenue_declining:
        insight = CompoundInsight(
            pass_name="temporal",
            insight_type="debt_revenue_divergence",
            description=(
                f"Dangerous divergence: debt growing while revenue declining — "
                f"leverage increasing with shrinking capacity"
            ),
            evidence_chain=[
                f"Debt: {', '.join(f'{y}: ₹{v:.1f}cr' for y, v in debt_series)}",
                f"Revenue: {', '.join(f'{y}: ₹{v:.1f}cr' for y, v in revenue_series)}",
                "Debt rising + Revenue falling = deteriorating leverage",
            ],
            score_impact=DECLINING_TREND_PENALTY,
            confidence=0.85,
            severity="HIGH",
        )
        insights.append(insight)

    return insights


def _check_threshold_proximity(metrics) -> List[CompoundInsight]:
    """Check if key metrics are approaching critical thresholds."""
    insights = []

    # DSCR approaching 1.0x (hard block threshold)
    if metrics.dscr is not None and 1.0 <= metrics.dscr < 1.2:
        insight = CompoundInsight(
            pass_name="temporal",
            insight_type="dscr_threshold_proximity",
            description=(
                f"DSCR at {metrics.dscr:.2f}x — dangerously close to 1.0x hard block threshold"
            ),
            evidence_chain=[
                f"Current DSCR: {metrics.dscr:.2f}x",
                "Hard block threshold: 1.0x",
                f"Buffer: only {(metrics.dscr - 1.0):.2f}x above threshold",
                "Any revenue decline could trigger hard block",
            ],
            score_impact=THRESHOLD_APPROACH_PENALTY,
            confidence=0.90,
            severity="HIGH",
        )
        insights.append(insight)

    # Debt/Equity approaching danger zone (>3.0x)
    if metrics.debt_equity_ratio is not None and metrics.debt_equity_ratio > 2.5:
        insight = CompoundInsight(
            pass_name="temporal",
            insight_type="de_ratio_high",
            description=(
                f"Debt/Equity at {metrics.debt_equity_ratio:.2f}x — high leverage"
            ),
            evidence_chain=[
                f"Current D/E: {metrics.debt_equity_ratio:.2f}x",
                "Industry concern threshold: 2.5x",
                "High leverage increases cascade risk exposure",
            ],
            score_impact=DECLINING_TREND_PENALTY,
            confidence=0.85,
            severity="MEDIUM",
        )
        insights.append(insight)

    return insights
