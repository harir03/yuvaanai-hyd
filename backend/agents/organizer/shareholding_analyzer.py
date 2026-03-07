"""
Intelli-Credit — Shareholding Analyzer (Agent 1.5 sub-module)

Analyzes Worker 7 (Shareholding Pattern) output for:
 - Promoter holding % and trend
 - Pledge ratio and trend
 - Institutional holding changes
 - Cross-holding detection
"""

import logging
from typing import Dict, Any, List, Optional

from backend.graph.state import WorkerOutput

logger = logging.getLogger(__name__)


class ShareholdingAnalysisResult:
    """Structured result from shareholding analysis."""

    def __init__(self):
        self.promoter_holding_pct: Optional[float] = None
        self.promoter_pledge_pct: Optional[float] = None
        self.institutional_holding_pct: Optional[float] = None
        self.public_holding_pct: Optional[float] = None
        self.pledge_trend: Optional[str] = None          # "increasing", "decreasing", "stable"
        self.promoter_trend: Optional[str] = None         # "increasing", "decreasing", "stable"
        self.cross_holdings: List[Dict[str, Any]] = []
        self.shareholding_flags: List[str] = []
        self.shareholding_score: float = 1.0  # 1.0 = clean, 0.0 = serious concerns

    def to_dict(self) -> Dict[str, Any]:
        return {
            "promoter_holding_pct": self.promoter_holding_pct,
            "promoter_pledge_pct": self.promoter_pledge_pct,
            "institutional_holding_pct": self.institutional_holding_pct,
            "public_holding_pct": self.public_holding_pct,
            "pledge_trend": self.pledge_trend,
            "promoter_trend": self.promoter_trend,
            "cross_holdings": self.cross_holdings,
            "shareholding_flags": self.shareholding_flags,
            "shareholding_score": self.shareholding_score,
        }


def analyze_shareholding(
    worker_outputs: Dict[str, WorkerOutput],
) -> ShareholdingAnalysisResult:
    """
    Analyze Shareholding Pattern (W7) for ownership and pledge signals.

    Returns structured analysis with flags and risk score.
    """
    result = ShareholdingAnalysisResult()
    w7_data = _get_w7_data(worker_outputs)

    if not w7_data:
        logger.info("[ShareholdingAnalyzer] No shareholding data available — skipping")
        return result

    # 1. Current holdings
    _extract_holdings(w7_data, result)

    # 2. Pledge analysis
    _analyze_pledge(w7_data, result)

    # 3. Promoter trend
    _analyze_promoter_trend(w7_data, result)

    # 4. Cross-holdings
    _detect_cross_holdings(w7_data, result)

    # 5. Compute score
    _compute_shareholding_score(result)

    logger.info(
        f"[ShareholdingAnalyzer] Promoter={result.promoter_holding_pct}%, "
        f"Pledge={result.promoter_pledge_pct}%, "
        f"Flags={len(result.shareholding_flags)}, "
        f"Score={result.shareholding_score}"
    )

    return result


def _get_w7_data(outputs: Dict[str, WorkerOutput]) -> Dict[str, Any]:
    """Safely extract W7 data."""
    wo = outputs.get("W7")
    if wo is None:
        return {}
    if hasattr(wo, "extracted_data"):
        return wo.extracted_data or {}
    if isinstance(wo, dict):
        return wo.get("extracted_data", wo)
    return {}


def _safe_float(val: Any) -> Optional[float]:
    """Convert to float or return None."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _extract_holdings(data: dict, result: ShareholdingAnalysisResult):
    """Extract current holding percentages."""
    result.promoter_holding_pct = _safe_float(data.get("promoter_holding_pct"))
    result.institutional_holding_pct = _safe_float(data.get("institutional_holding_pct"))
    result.public_holding_pct = _safe_float(data.get("public_holding_pct"))
    result.promoter_pledge_pct = _safe_float(data.get("promoter_pledge_pct"))

    # Flag low promoter holding
    if result.promoter_holding_pct is not None and result.promoter_holding_pct < 26.0:
        result.shareholding_flags.append(
            f"Low promoter holding ({result.promoter_holding_pct}%) — below 26% threshold"
        )
    elif result.promoter_holding_pct is not None and result.promoter_holding_pct < 40.0:
        result.shareholding_flags.append(
            f"Moderate promoter holding ({result.promoter_holding_pct}%) — below 40%"
        )


def _analyze_pledge(data: dict, result: ShareholdingAnalysisResult):
    """Analyze pledge ratio and trend."""
    pledge = result.promoter_pledge_pct
    if pledge is not None and pledge > 50.0:
        result.shareholding_flags.append(
            f"CRITICAL: Very high promoter pledge ({pledge}%) — over 50% of holdings pledged"
        )
    elif pledge is not None and pledge > 25.0:
        result.shareholding_flags.append(
            f"High promoter pledge ({pledge}%) — over 25% of holdings pledged"
        )

    # Pledge trend from historical data
    pledge_history = data.get("pledge_history", [])
    if isinstance(pledge_history, list) and len(pledge_history) >= 2:
        result.pledge_trend = _determine_trend(pledge_history)
        if result.pledge_trend == "increasing":
            result.shareholding_flags.append(
                "Pledge ratio trending upward — potential liquidity stress"
            )


def _analyze_promoter_trend(data: dict, result: ShareholdingAnalysisResult):
    """Analyze promoter holding trend."""
    promoter_history = data.get("promoter_holding_history", [])
    if isinstance(promoter_history, list) and len(promoter_history) >= 2:
        result.promoter_trend = _determine_trend(promoter_history)
        if result.promoter_trend == "decreasing":
            result.shareholding_flags.append(
                "Promoter holding declining over time — potential dilution or exit"
            )


def _detect_cross_holdings(data: dict, result: ShareholdingAnalysisResult):
    """Detect cross-holdings (company holds shares in its own group companies)."""
    cross = data.get("cross_holdings", [])
    if isinstance(cross, list):
        result.cross_holdings = cross
        if len(cross) > 0:
            result.shareholding_flags.append(
                f"Cross-holdings detected ({len(cross)} entities) — potential circular ownership"
            )


def _determine_trend(values: List) -> str:
    """Determine if a series of values is increasing, decreasing, or stable."""
    try:
        floats = [float(v) for v in values]
    except (TypeError, ValueError):
        return "stable"

    if len(floats) < 2:
        return "stable"

    first_half = sum(floats[:len(floats)//2]) / max(len(floats)//2, 1)
    second_half = sum(floats[len(floats)//2:]) / max(len(floats) - len(floats)//2, 1)

    pct_change = abs(second_half - first_half) / max(abs(first_half), 0.01) * 100

    if pct_change < 5.0:
        return "stable"
    elif second_half > first_half:
        return "increasing"
    else:
        return "decreasing"


def _compute_shareholding_score(result: ShareholdingAnalysisResult):
    """
    Compute a normalized shareholding score (0.0 to 1.0).

    Deductions:
      - High pledge (>50%): -0.30
      - High pledge (>25%): -0.15
      - Low promoter (<26%): -0.20
      - Low promoter (<40%): -0.10
      - Increasing pledge trend: -0.10
      - Decreasing promoter trend: -0.10
      - Cross-holdings: -0.10 each (max -0.30)
    """
    score = 1.0

    if result.promoter_pledge_pct is not None:
        if result.promoter_pledge_pct > 50.0:
            score -= 0.30
        elif result.promoter_pledge_pct > 25.0:
            score -= 0.15

    if result.promoter_holding_pct is not None:
        if result.promoter_holding_pct < 26.0:
            score -= 0.20
        elif result.promoter_holding_pct < 40.0:
            score -= 0.10

    if result.pledge_trend == "increasing":
        score -= 0.10

    if result.promoter_trend == "decreasing":
        score -= 0.10

    if result.cross_holdings:
        score -= min(0.10 * len(result.cross_holdings), 0.30)

    result.shareholding_score = round(max(0.0, min(1.0, score)), 2)
