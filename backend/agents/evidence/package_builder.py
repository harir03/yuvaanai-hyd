"""
Intelli-Credit — Evidence Package Builder

Collects ALL findings from all upstream stages into one structured,
fully cited EvidencePackage. Categorizes each finding as:
  - verified (cross-checked, high confidence)
  - uncertain (single source or low confidence)
  - rejected (contradicted or discredited)
  - conflicting (multiple sources disagree)

Agent 3 reads ONLY this package. It never touches raw data.
"""

import logging
from typing import List, Dict, Any, Optional

from backend.graph.state import (
    CreditAppraisalState,
    EvidencePackage,
    CrossVerificationResult,
    CompoundInsight,
    ResearchFinding,
)

logger = logging.getLogger(__name__)

# Confidence thresholds
VERIFIED_THRESHOLD = 0.80
UNCERTAIN_THRESHOLD = 0.50
# Below UNCERTAIN_THRESHOLD → rejected


def build_evidence_package(state: CreditAppraisalState) -> EvidencePackage:
    """
    Build a complete EvidencePackage from all upstream state.

    Collects:
    - 5 Cs data from organized_package
    - Computed metrics from organized_package
    - Cross-verification results from raw_data_package (consolidator output)
    - Compound insights from reasoning_package
    - Research findings from research_package
    - ML signals from organized_package
    - Categorizes everything into verified/uncertain/rejected/conflicting
    """
    evidence = EvidencePackage(
        session_id=state.session_id,
        company=state.company,
    )

    # 1. Copy 5 Cs and metrics from organized package
    if state.organized_package:
        evidence.five_cs = state.organized_package.five_cs
        evidence.computed_metrics = state.organized_package.computed_metrics

    # 2. Collect cross-verification results (already built by consolidator)
    evidence.cross_verifications = _collect_cross_verifications(state)

    # 3. Collect compound insights from reasoning
    evidence.compound_insights = _collect_compound_insights(state)

    # 4. Collect research findings
    evidence.research_findings = _collect_research_findings(state)

    # 5. Collect ML signals
    evidence.ml_signals = _collect_ml_signals(state)

    # 6. Categorize all findings
    verified, uncertain, rejected, conflicting = _categorize_findings(evidence)
    evidence.verified_findings = verified
    evidence.uncertain_findings = uncertain
    evidence.rejected_findings = rejected
    evidence.conflicting_findings = conflicting

    return evidence


def _collect_cross_verifications(state: CreditAppraisalState) -> List[CrossVerificationResult]:
    """Gather cross-verification results from the consolidator's raw_data_package."""
    if state.raw_data_package and state.raw_data_package.cross_verifications:
        return list(state.raw_data_package.cross_verifications)
    return []


def _collect_compound_insights(state: CreditAppraisalState) -> List[CompoundInsight]:
    """Gather compound insights from reasoning package."""
    if not state.reasoning_package:
        return []
    return list(state.reasoning_package.insights)


def _collect_research_findings(state: CreditAppraisalState) -> List[ResearchFinding]:
    """Gather research findings from research package."""
    if not state.research_package:
        return []
    return list(state.research_package.findings)


def _collect_ml_signals(state: CreditAppraisalState) -> Dict[str, Any]:
    """Gather ML signals from organized package."""
    signals: Dict[str, Any] = {}

    if state.organized_package and state.organized_package.ml_signals:
        signals = dict(state.organized_package.ml_signals)

    # Add fraud signals from reasoning (circular trading, etc.)
    if state.reasoning_package:
        fraud_insights = [
            i for i in state.reasoning_package.insights
            if i.severity == "CRITICAL" and "circular" in i.insight_type.lower()
        ]
        if fraud_insights:
            signals["circular_trading_detected"] = True
            signals["circular_trading_insights"] = [
                {"description": i.description, "confidence": i.confidence}
                for i in fraud_insights
            ]

    return signals


def _categorize_findings(evidence: EvidencePackage) -> tuple:
    """
    Categorize all findings into verified/uncertain/rejected/conflicting.

    Uses cross-verification status, confidence scores, and reasoning insights.
    """
    verified: List[Dict[str, Any]] = []
    uncertain: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    conflicting: List[Dict[str, Any]] = []

    # Categorize cross-verification results
    for cv in evidence.cross_verifications:
        finding = {
            "type": "cross_verification",
            "field": cv.field_name,
            "status": cv.status,
            "deviation_pct": cv.max_deviation_pct,
            "accepted_value": cv.accepted_value,
            "accepted_source": cv.accepted_source,
            "note": cv.note,
        }
        if cv.status == "verified":
            verified.append(finding)
        elif cv.status == "flagged":
            uncertain.append(finding)
        elif cv.status == "conflicting":
            conflicting.append(finding)

    # Categorize 5 Cs fields by confidence
    for c_name in ["capacity", "character", "capital", "collateral", "conditions"]:
        c_data = getattr(evidence.five_cs, c_name, {})
        for field_name, nf in c_data.items():
            finding = {
                "type": "five_cs",
                "category": c_name,
                "field": field_name,
                "value": nf.value,
                "source": nf.source_document,
                "page": nf.source_page,
                "confidence": nf.confidence,
            }
            if nf.confidence >= VERIFIED_THRESHOLD:
                verified.append(finding)
            elif nf.confidence >= UNCERTAIN_THRESHOLD:
                uncertain.append(finding)
            else:
                rejected.append(finding)

    # Categorize compound insights
    for insight in evidence.compound_insights:
        finding = {
            "type": "compound_insight",
            "pass_name": insight.pass_name,
            "insight_type": insight.insight_type,
            "description": insight.description,
            "confidence": insight.confidence,
            "severity": insight.severity,
            "score_impact": insight.score_impact,
        }
        if insight.confidence >= VERIFIED_THRESHOLD:
            verified.append(finding)
        elif insight.confidence >= UNCERTAIN_THRESHOLD:
            uncertain.append(finding)
        else:
            uncertain.append(finding)

    # Categorize research findings
    for rf in evidence.research_findings:
        finding = {
            "type": "research",
            "source": rf.source,
            "title": rf.title,
            "tier": rf.source_tier,
            "weight": rf.source_weight,
            "verified": rf.verified,
            "relevance": rf.relevance_score,
        }
        if rf.verified and rf.source_weight >= 0.85:
            verified.append(finding)
        elif rf.source_weight >= 0.60:
            uncertain.append(finding)
        elif rf.source_weight < 0.30:
            rejected.append(finding)
        else:
            uncertain.append(finding)

    return verified, uncertain, rejected, conflicting
