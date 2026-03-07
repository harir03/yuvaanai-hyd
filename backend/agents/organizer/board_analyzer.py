"""
Intelli-Credit — Board Minutes Analyzer (Agent 1.5 sub-module)

Extracts governance signals from Worker 6 (Board Minutes):
 - CFO / key management changes (instability signal)
 - RPT approvals vs AR RPT disclosure (concealment check)
 - Director resignation patterns
 - Risk committee discussions
"""

import logging
from typing import Dict, Any, List, Optional

from backend.graph.state import WorkerOutput

logger = logging.getLogger(__name__)


class BoardAnalysisResult:
    """Structured result from board minutes analysis."""

    def __init__(self):
        self.cfo_changes: int = 0
        self.director_resignations: int = 0
        self.rpt_approvals: List[Dict[str, Any]] = []
        self.rpt_approval_count: int = 0
        self.risk_discussions: List[str] = []
        self.governance_flags: List[str] = []
        self.governance_score: float = 1.0  # 1.0 = clean, 0.0 = serious concerns

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cfo_changes": self.cfo_changes,
            "director_resignations": self.director_resignations,
            "rpt_approvals": self.rpt_approvals,
            "rpt_approval_count": self.rpt_approval_count,
            "risk_discussions": self.risk_discussions,
            "governance_flags": self.governance_flags,
            "governance_score": self.governance_score,
        }


def analyze_board_minutes(
    worker_outputs: Dict[str, WorkerOutput],
) -> BoardAnalysisResult:
    """
    Analyze Board Minutes (W6) for governance signals.

    Returns structured analysis with governance flags and score.
    """
    result = BoardAnalysisResult()
    w6_data = _get_w6_data(worker_outputs)

    if not w6_data:
        logger.info("[BoardAnalyzer] No board minutes data available — skipping")
        return result

    # 1. CFO / Key Management Changes
    _check_cfo_changes(w6_data, result)

    # 2. Director Resignations
    _check_director_resignations(w6_data, result)

    # 3. RPT Approvals
    _check_rpt_approvals(w6_data, result)

    # 4. Risk Committee Discussions
    _check_risk_discussions(w6_data, result)

    # 5. Compute governance score
    _compute_governance_score(result)

    logger.info(
        f"[BoardAnalyzer] CFO changes={result.cfo_changes}, "
        f"Resignations={result.director_resignations}, "
        f"RPT approvals={result.rpt_approval_count}, "
        f"Flags={len(result.governance_flags)}, "
        f"Score={result.governance_score}"
    )

    return result


def _get_w6_data(outputs: Dict[str, WorkerOutput]) -> Dict[str, Any]:
    """Safely extract W6 data."""
    wo = outputs.get("W6")
    if wo is None:
        return {}
    if hasattr(wo, "extracted_data"):
        return wo.extracted_data or {}
    if isinstance(wo, dict):
        return wo.get("extracted_data", wo)
    return {}


def _check_cfo_changes(data: dict, result: BoardAnalysisResult):
    """Check for CFO or key management personnel changes."""
    cfo_changes = data.get("cfo_changes", 0)
    if isinstance(cfo_changes, (list, tuple)):
        result.cfo_changes = len(cfo_changes)
    elif isinstance(cfo_changes, (int, float)):
        result.cfo_changes = int(cfo_changes)

    if result.cfo_changes >= 2:
        result.governance_flags.append(
            f"Multiple CFO changes detected ({result.cfo_changes}) — potential management instability"
        )
    elif result.cfo_changes == 1:
        result.governance_flags.append("CFO change detected — monitor transition")

    # Key management changes
    kmp_changes = data.get("key_management_changes", [])
    if isinstance(kmp_changes, list) and len(kmp_changes) >= 3:
        result.governance_flags.append(
            f"High key management turnover ({len(kmp_changes)} changes)"
        )


def _check_director_resignations(data: dict, result: BoardAnalysisResult):
    """Check for director resignations (potential red flag)."""
    resignations = data.get("director_resignations", [])
    if isinstance(resignations, list):
        result.director_resignations = len(resignations)
    elif isinstance(resignations, (int, float)):
        result.director_resignations = int(resignations)

    if result.director_resignations >= 3:
        result.governance_flags.append(
            f"Multiple director resignations ({result.director_resignations}) — governance concern"
        )
    elif result.director_resignations >= 1:
        result.governance_flags.append(
            f"Director resignation(s) detected ({result.director_resignations})"
        )


def _check_rpt_approvals(data: dict, result: BoardAnalysisResult):
    """Extract RPT approvals from board minutes."""
    rpt_approvals = data.get("rpt_approvals", [])
    if isinstance(rpt_approvals, list):
        result.rpt_approvals = rpt_approvals
        result.rpt_approval_count = len(rpt_approvals)
    elif isinstance(rpt_approvals, (int, float)):
        result.rpt_approval_count = int(rpt_approvals)

    if result.rpt_approval_count > 5:
        result.governance_flags.append(
            f"High RPT approval count ({result.rpt_approval_count}) — needs cross-check with AR"
        )


def _check_risk_discussions(data: dict, result: BoardAnalysisResult):
    """Extract risk committee discussions."""
    risks = data.get("risk_discussions", [])
    if isinstance(risks, list):
        result.risk_discussions = [str(r) for r in risks]

    # Check for concerning keywords
    concerning = data.get("risk_flags", [])
    if isinstance(concerning, list):
        for flag in concerning:
            result.governance_flags.append(f"Board risk flag: {flag}")


def _compute_governance_score(result: BoardAnalysisResult):
    """
    Compute a normalized governance score (0.0 to 1.0).

    Deductions:
      - CFO changes: -0.15 each (after first)
      - Director resignations: -0.10 each (after first 2)
      - High RPT count: -0.10
      - Each governance flag: -0.05
    """
    score = 1.0

    # CFO instability
    if result.cfo_changes >= 2:
        score -= 0.15 * (result.cfo_changes - 1)
    elif result.cfo_changes == 1:
        score -= 0.05

    # Director resignations
    if result.director_resignations > 2:
        score -= 0.10 * (result.director_resignations - 2)
    elif result.director_resignations > 0:
        score -= 0.03 * result.director_resignations

    # High RPT
    if result.rpt_approval_count > 5:
        score -= 0.10

    # Floor at 0.0
    result.governance_score = round(max(0.0, min(1.0, score)), 2)
