"""
Intelli-Credit — Ticket Raiser

Scans the EvidencePackage for conditions that warrant human review.
Creates Ticket objects with proper severity, category, and score impact.

Ticket-raising triggers:
  1. Contradiction between sources (deviation > 25%)          → HIGH
  2. Low confidence extraction (<0.70) on material finding     → HIGH
  3. ML fraud signal without full supporting evidence           → CRITICAL
  4. Finding that would change score by >20 pts but uncertain   → HIGH
  5. Management interview discrepancy vs documents              → HIGH
  6. Unverified material finding (>10 pts impact)               → LOW/HIGH

Severity behavior:
  - LOW: pipeline continues, ticket resolved async
  - HIGH: pipeline pauses at Agent 3, must resolve first
  - CRITICAL: pipeline stops completely, senior manager notification
"""

import logging
from typing import List

from backend.graph.state import EvidencePackage, CompoundInsight
from backend.models.schemas import (
    Ticket,
    TicketSeverity,
)

logger = logging.getLogger(__name__)

# Thresholds
CONTRADICTION_DEVIATION_THRESHOLD = 25.0  # % deviation → conflicting
LOW_CONFIDENCE_THRESHOLD = 0.70
HIGH_SCORE_IMPACT_THRESHOLD = 20  # points


def raise_tickets(
    session_id: str,
    evidence: EvidencePackage,
) -> List[Ticket]:
    """
    Scan the evidence package and raise tickets for anything
    ambiguous, conflicting, or high-impact-uncertain.
    """
    tickets: List[Ticket] = []

    # 1. Cross-verification contradictions
    tickets.extend(_check_cross_verification_conflicts(session_id, evidence))

    # 2. Low confidence material findings
    tickets.extend(_check_low_confidence_findings(session_id, evidence))

    # 3. ML fraud signals without full evidence
    tickets.extend(_check_ml_fraud_signals(session_id, evidence))

    # 4. High-impact uncertain compound insights
    tickets.extend(_check_uncertain_high_impact(session_id, evidence))

    # 5. Unverified material research findings
    tickets.extend(_check_unverified_material_research(session_id, evidence))

    logger.info(
        f"[Ticket Raiser] Raised {len(tickets)} tickets for session {session_id}: "
        f"{sum(1 for t in tickets if t.severity == TicketSeverity.LOW)} LOW, "
        f"{sum(1 for t in tickets if t.severity == TicketSeverity.HIGH)} HIGH, "
        f"{sum(1 for t in tickets if t.severity == TicketSeverity.CRITICAL)} CRITICAL"
    )

    return tickets


def _check_cross_verification_conflicts(
    session_id: str,
    evidence: EvidencePackage,
) -> List[Ticket]:
    """Raise tickets for cross-verification contradictions."""
    tickets = []

    for cv in evidence.cross_verifications:
        if cv.status != "conflicting":
            continue

        # Determine source descriptions
        source_names = list(cv.sources.keys())
        source_a_desc = f"{cv.field_name} from {source_names[0]}: {cv.sources[source_names[0]].value}" if source_names else "Unknown"
        source_b_desc = f"{cv.field_name} from {source_names[-1]}: {cv.sources[source_names[-1]].value}" if len(source_names) > 1 else "Unknown"

        # Revenue conflicts → HIGH, others → HIGH
        severity = TicketSeverity.HIGH
        score_impact = -15 if cv.field_name == "revenue" else -10

        tickets.append(Ticket(
            session_id=session_id,
            title=f"{cv.field_name.replace('_', ' ').title()} Discrepancy ({cv.max_deviation_pct:.1f}%)",
            description=(
                f"Cross-verification of {cv.field_name} shows {cv.max_deviation_pct:.1f}% deviation "
                f"across {len(cv.sources)} sources. This exceeds the {CONTRADICTION_DEVIATION_THRESHOLD}% threshold. "
                f"Manual verification required before scoring."
            ),
            severity=severity,
            category=f"{cv.field_name.replace('_', ' ').title()} Discrepancy",
            source_a=source_a_desc,
            source_b=source_b_desc,
            ai_recommendation=(
                f"Accept the highest-credibility source ({cv.accepted_source}). "
                f"The deviation of {cv.max_deviation_pct:.1f}% suggests potential misreporting. "
                f"Flag for detailed audit if deviation > 30%."
            ),
            score_impact=score_impact,
        ))

    return tickets


def _check_low_confidence_findings(
    session_id: str,
    evidence: EvidencePackage,
) -> List[Ticket]:
    """Raise tickets for low-confidence extractions on material 5Cs fields."""
    tickets = []

    # Material fields that matter for scoring
    material_fields = {
        "capacity": ["revenue", "ebitda", "pat", "dscr", "cash_flow"],
        "character": ["promoter_track_record", "rpt_disclosure", "pledge_pct"],
        "capital": ["net_worth", "debt_equity", "total_debt"],
        "collateral": ["coverage_ratio", "asset_quality"],
        "conditions": ["order_book", "sector_outlook"],
    }

    for c_name, important_fields in material_fields.items():
        c_data = getattr(evidence.five_cs, c_name, {})
        for field_name, nf in c_data.items():
            # Only check material fields
            if not any(kw in field_name.lower() for kw in important_fields):
                continue

            if nf.confidence < LOW_CONFIDENCE_THRESHOLD:
                severity = TicketSeverity.HIGH if nf.confidence < 0.50 else TicketSeverity.LOW
                tickets.append(Ticket(
                    session_id=session_id,
                    title=f"Low Confidence: {c_name.title()} — {field_name}",
                    description=(
                        f"The extraction of '{field_name}' under {c_name.title()} has confidence "
                        f"{nf.confidence:.0%}, below the {LOW_CONFIDENCE_THRESHOLD:.0%} threshold. "
                        f"Source: {nf.source_document}"
                        f"{f', page {nf.source_page}' if nf.source_page else ''}."
                    ),
                    severity=severity,
                    category="Low Confidence Extraction",
                    source_a=f"{field_name} = {nf.value} (confidence {nf.confidence:.0%})",
                    source_b=f"Threshold: {LOW_CONFIDENCE_THRESHOLD:.0%}",
                    ai_recommendation=(
                        f"Verify '{field_name}' manually from {nf.source_document}. "
                        f"Consider re-extracting with higher-quality scan if OCR issue suspected."
                    ),
                    score_impact=-10,
                ))

    return tickets


def _check_ml_fraud_signals(
    session_id: str,
    evidence: EvidencePackage,
) -> List[Ticket]:
    """Raise CRITICAL tickets for ML fraud signals without supporting evidence."""
    tickets = []

    if not evidence.ml_signals:
        return tickets

    # Circular trading detection
    if evidence.ml_signals.get("circular_trading_detected"):
        # Check if there's supporting document evidence
        supporting_insights = [
            i for i in evidence.compound_insights
            if i.severity == "CRITICAL" and "circular" in i.insight_type.lower()
        ]
        has_strong_evidence = any(
            len(i.evidence_chain) >= 3 and i.confidence >= 0.80
            for i in supporting_insights
        )

        if not has_strong_evidence:
            tickets.append(Ticket(
                session_id=session_id,
                title="ML Fraud Signal: Circular Trading (Unconfirmed)",
                description=(
                    "The ML model (DOMINANT GNN) detected a circular trading pattern, "
                    "but there is insufficient document evidence to fully confirm it. "
                    "This requires immediate human review before proceeding."
                ),
                severity=TicketSeverity.CRITICAL,
                category="ML Fraud Signal",
                source_a="DOMINANT GNN model: circular trading pattern detected",
                source_b="Document evidence: insufficient supporting documents",
                ai_recommendation=(
                    "Investigate the identified trading pattern manually. "
                    "Check supplier-customer relationships in Board Minutes and Annual Report. "
                    "If confirmed, this triggers Hard Block rules."
                ),
                score_impact=-50,
            ))

    # Isolation Forest anomaly
    if evidence.ml_signals.get("isolation_forest_anomaly"):
        anomaly_score = evidence.ml_signals.get("isolation_forest_score", 0)
        tickets.append(Ticket(
            session_id=session_id,
            title=f"ML Anomaly Signal: Tabular Outlier (score: {anomaly_score:.2f})",
            description=(
                "The Isolation Forest model detected tabular anomalies in the financial data. "
                "This may indicate data manipulation, unusual patterns, or legitimate outliers."
            ),
            severity=TicketSeverity.HIGH,
            category="ML Anomaly Signal",
            source_a=f"Isolation Forest anomaly score: {anomaly_score:.2f}",
            source_b="Expected: normal distribution within peer group",
            ai_recommendation=(
                "Review the flagged financial metrics against peer companies. "
                "Determine if anomalies are legitimate (e.g., rapid growth sector) "
                "or suspicious (e.g., inflated revenue)."
            ),
            score_impact=-20,
        ))

    # FinBERT buried risk
    if evidence.ml_signals.get("finbert_risk_detected"):
        risk_text = evidence.ml_signals.get("finbert_risk_text", "Risk detected in financial text")
        tickets.append(Ticket(
            session_id=session_id,
            title="NLP Risk Signal: Buried Risk Language Detected",
            description=(
                f"FinBERT detected risk-indicative language in document text: '{risk_text[:200]}'. "
                "This may indicate risks not explicitly disclosed in financial statements."
            ),
            severity=TicketSeverity.LOW,
            category="NLP Risk Signal",
            source_a=f"FinBERT detection: {risk_text[:100]}",
            source_b="Expected: neutral or positive tone in disclosures",
            ai_recommendation="Review the flagged sections for hidden risk factors.",
            score_impact=-5,
        ))

    return tickets


def _check_uncertain_high_impact(
    session_id: str,
    evidence: EvidencePackage,
) -> List[Ticket]:
    """Raise tickets for compound insights with high score impact but low confidence."""
    tickets = []

    for insight in evidence.compound_insights:
        abs_impact = abs(insight.score_impact)
        if abs_impact > HIGH_SCORE_IMPACT_THRESHOLD and insight.confidence < LOW_CONFIDENCE_THRESHOLD:
            tickets.append(Ticket(
                session_id=session_id,
                title=f"Uncertain High-Impact: {insight.insight_type}",
                description=(
                    f"Compound insight '{insight.description[:150]}' would change the score by "
                    f"{insight.score_impact:+d} points but has only {insight.confidence:.0%} confidence. "
                    f"This exceeds the {HIGH_SCORE_IMPACT_THRESHOLD}-point threshold for uncertain findings."
                ),
                severity=TicketSeverity.HIGH,
                category="Uncertain High-Impact Finding",
                source_a=f"{insight.pass_name}: {insight.insight_type} (impact: {insight.score_impact:+d})",
                source_b=f"Confidence: {insight.confidence:.0%} (below {LOW_CONFIDENCE_THRESHOLD:.0%})",
                ai_recommendation=(
                    f"Verify the evidence chain for this insight: "
                    f"{', '.join(insight.evidence_chain[:3])}. "
                    f"If confirmed, apply full impact. If unverifiable, reduce to 50%."
                ),
                score_impact=insight.score_impact,
            ))

    return tickets


def _check_unverified_material_research(
    session_id: str,
    evidence: EvidencePackage,
) -> List[Ticket]:
    """Raise tickets for unverified research findings from high-tier sources."""
    tickets = []

    for rf in evidence.research_findings:
        # Only flag material research from Tier 1-2 that isn't verified
        if rf.source_tier <= 2 and not rf.verified and rf.relevance_score >= 0.70:
            severity = TicketSeverity.HIGH if rf.source_tier == 1 else TicketSeverity.LOW
            tickets.append(Ticket(
                session_id=session_id,
                title=f"Unverified: {rf.title[:80]}",
                description=(
                    f"Research finding from {rf.source} (Tier {rf.source_tier}, weight {rf.source_weight}) "
                    f"has high relevance ({rf.relevance_score:.0%}) but has not been cross-verified "
                    f"against documents. Category: {rf.category}."
                ),
                severity=severity,
                category=f"Unverified {rf.category.title()} Finding",
                source_a=f"{rf.source}: {rf.title[:100]}",
                source_b="No document cross-verification available",
                ai_recommendation=(
                    f"Cross-check this finding against the uploaded documents. "
                    f"If from a government portal (Tier 1), treat as authoritative. "
                    f"If from financial media (Tier 2), seek corroboration."
                ),
                score_impact=-10,
            ))

    return tickets
