"""
Intelli-Credit — Insight Store

Collects, deduplicates, and summarizes CompoundInsights from all 5 reasoning passes.
Acts as the central registry for Agent 2.5 outputs before they flow into the
Evidence Package and ultimately to Agent 3 (Scorer).
"""

import logging
from typing import List, Dict, Any

from backend.graph.state import CompoundInsight

logger = logging.getLogger(__name__)


class InsightStore:
    """
    Collects compound insights from all 5 reasoning passes,
    deduplicates by description similarity, and computes totals.
    """

    def __init__(self):
        self._insights: List[CompoundInsight] = []

    def add(self, insight: CompoundInsight) -> bool:
        """
        Add an insight if it's not a duplicate.
        Returns True if added, False if deduplicated away.
        """
        # Simple dedup: same pass + same insight_type + similar description
        for existing in self._insights:
            if (
                existing.pass_name == insight.pass_name
                and existing.insight_type == insight.insight_type
                and _descriptions_similar(existing.description, insight.description)
            ):
                # Keep the one with higher confidence
                if insight.confidence > existing.confidence:
                    self._insights.remove(existing)
                    self._insights.append(insight)
                    logger.debug(f"[InsightStore] Replaced lower-confidence duplicate: {insight.insight_type}")
                else:
                    logger.debug(f"[InsightStore] Deduplicated: {insight.insight_type}")
                return False

        self._insights.append(insight)
        return True

    def add_many(self, insights: List[CompoundInsight]) -> int:
        """Add multiple insights, returns count actually added."""
        return sum(1 for i in insights if self.add(i))

    def get_all(self) -> List[CompoundInsight]:
        """Return all collected insights."""
        return list(self._insights)

    def get_by_pass(self, pass_name: str) -> List[CompoundInsight]:
        """Return insights from a specific pass."""
        return [i for i in self._insights if i.pass_name == pass_name]

    def get_by_severity(self, severity: str) -> List[CompoundInsight]:
        """Return insights at or above a given severity."""
        severity_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        threshold = severity_order.get(severity.upper(), 0)
        return [
            i for i in self._insights
            if severity_order.get(i.severity, 0) >= threshold
        ]

    def total_score_impact(self) -> int:
        """Sum of all insight score impacts (can be negative overall)."""
        return sum(i.score_impact for i in self._insights)

    def summary(self) -> Dict[str, Any]:
        """Return a summary of all insights by pass."""
        by_pass: Dict[str, List[CompoundInsight]] = {}
        for i in self._insights:
            by_pass.setdefault(i.pass_name, []).append(i)

        return {
            "total_insights": len(self._insights),
            "total_score_impact": self.total_score_impact(),
            "by_pass": {
                name: {
                    "count": len(insights),
                    "score_impact": sum(i.score_impact for i in insights),
                    "severities": [i.severity for i in insights],
                }
                for name, insights in by_pass.items()
            },
        }


def _descriptions_similar(a: str, b: str) -> bool:
    """Simple similarity check — same first 50 chars after normalization."""
    norm_a = a.lower().strip()[:50]
    norm_b = b.lower().strip()[:50]
    return norm_a == norm_b
