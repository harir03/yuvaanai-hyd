"""
Intelli-Credit — Compliance Auto-Flagging Engine (T4.5)

Scans assessment data for regulatory compliance triggers and auto-flags
assessments requiring compliance team review.

Compliance triggers (from architecture spec):
  1. Undisclosed RPTs — Board minutes show more RPTs than Annual Report discloses
  2. SEBI violations — Active SEBI action against promoter or company
  3. RBI defaulter — Wilful defaulter or RBI list presence
  4. Fraud signal threshold — ML fraud detections exceeding confidence threshold
  5. PMLA/FIU-IND — Suspicious transaction patterns requiring regulatory report
  6. NCLT proceedings — Active insolvency proceedings
  7. Regulatory non-compliance — Adverse regulatory findings from research

Each ComplianceFlag has:
  - trigger: what was detected
  - severity: CRITICAL / HIGH / MEDIUM
  - regulation: applicable regulation or circular
  - description: detailed explanation with evidence
  - auto_action: what the system recommends
  - requires_notification: whether compliance team must be notified immediately
"""

import logging
from typing import List, Optional
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from backend.graph.state import (
    EvidencePackage,
    CompoundInsight,
    HardBlock,
    ResearchFinding,
)
from backend.models.schemas import (
    Ticket,
    TicketSeverity,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Compliance Models
# ──────────────────────────────────────────────


class ComplianceSeverity(str, Enum):
    """Severity level for compliance flags."""
    CRITICAL = "CRITICAL"  # Immediate notification, pipeline may halt
    HIGH = "HIGH"          # Compliance team review required
    MEDIUM = "MEDIUM"      # Compliance awareness, no immediate action


class ComplianceTrigger(str, Enum):
    """Known compliance trigger types."""
    UNDISCLOSED_RPT = "UNDISCLOSED_RPT"
    SEBI_VIOLATION = "SEBI_VIOLATION"
    RBI_DEFAULTER = "RBI_DEFAULTER"
    FRAUD_SIGNAL = "FRAUD_SIGNAL"
    PMLA_SUSPICIOUS = "PMLA_SUSPICIOUS"
    NCLT_PROCEEDINGS = "NCLT_PROCEEDINGS"
    REGULATORY_NON_COMPLIANCE = "REGULATORY_NON_COMPLIANCE"


class ComplianceFlag(BaseModel):
    """A compliance flag raised by the auto-flagging engine."""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex[:12])
    trigger: ComplianceTrigger
    severity: ComplianceSeverity
    regulation: str = Field(..., description="Applicable regulation or circular")
    description: str = Field(..., description="Detailed explanation with evidence")
    auto_action: str = Field(..., description="Recommended action")
    evidence_sources: List[str] = Field(default_factory=list)
    requires_notification: bool = Field(default=False)
    flagged_at: datetime = Field(default_factory=datetime.utcnow)


class ComplianceResult(BaseModel):
    """Result of compliance auto-flagging scan."""
    session_id: str
    flagged: bool = False
    flags: List[ComplianceFlag] = Field(default_factory=list)
    summary: str = ""
    scanned_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.flags if f.severity == ComplianceSeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.flags if f.severity == ComplianceSeverity.HIGH)

    @property
    def requires_immediate_notification(self) -> bool:
        return any(f.requires_notification for f in self.flags)


# ──────────────────────────────────────────────
# Thresholds
# ──────────────────────────────────────────────

# Fraud confidence above this triggers compliance flag
FRAUD_CONFIDENCE_THRESHOLD = 0.70

# RPT count mismatch — if board minutes show more than AR discloses
RPT_MISMATCH_THRESHOLD = 0  # any undisclosed RPT is a compliance issue

# ML signal score threshold for PMLA-level suspicion
PMLA_ANOMALY_THRESHOLD = 0.85


# ──────────────────────────────────────────────
# Main Engine
# ──────────────────────────────────────────────


def scan_compliance(
    session_id: str,
    evidence: Optional[EvidencePackage] = None,
    hard_blocks: Optional[List[HardBlock]] = None,
    tickets: Optional[List[Ticket]] = None,
    research_findings: Optional[List[ResearchFinding]] = None,
    compound_insights: Optional[List[CompoundInsight]] = None,
    ml_signals: Optional[dict] = None,
) -> ComplianceResult:
    """
    Scan assessment data for compliance triggers.

    This function checks multiple data sources for conditions that require
    compliance team notification. It can run at any pipeline stage —
    evidence_package, hard_blocks, tickets, or research findings.
    """
    flags: List[ComplianceFlag] = []

    # 1. Check hard blocks for compliance-relevant triggers
    if hard_blocks:
        flags.extend(_check_hard_blocks(hard_blocks))

    # 2. Check evidence package
    if evidence:
        flags.extend(_check_evidence_rpt_disclosure(evidence))
        flags.extend(_check_evidence_fraud_signals(evidence))

    # 3. Check ML signals (can be from evidence or passed directly)
    effective_ml = ml_signals or (evidence.ml_signals if evidence else {})
    if effective_ml:
        flags.extend(_check_ml_fraud_threshold(effective_ml))
        flags.extend(_check_pmla_patterns(effective_ml))

    # 4. Check research findings for regulatory violations
    effective_research = research_findings or (
        evidence.research_findings if evidence else []
    )
    if effective_research:
        flags.extend(_check_regulatory_findings(effective_research))

    # 5. Check compound insights for NCLT / severe fraud
    effective_insights = compound_insights or (
        evidence.compound_insights if evidence else []
    )
    if effective_insights:
        flags.extend(_check_compound_insights_compliance(effective_insights))

    # 6. Check tickets for compliance-escalatable severity
    if tickets:
        flags.extend(_check_critical_tickets(tickets))

    # Deduplicate by trigger type (keep highest severity per trigger)
    flags = _deduplicate_flags(flags)

    # Build result
    flagged = len(flags) > 0
    summary = _build_summary(flags) if flagged else "No compliance flags raised."

    result = ComplianceResult(
        session_id=session_id,
        flagged=flagged,
        flags=flags,
        summary=summary,
    )

    logger.info(
        "[Compliance] Session %s: flagged=%s, flags=%d (CRITICAL=%d, HIGH=%d, MEDIUM=%d)",
        session_id, flagged, len(flags),
        result.critical_count, result.high_count,
        sum(1 for f in flags if f.severity == ComplianceSeverity.MEDIUM),
    )

    return result


# ──────────────────────────────────────────────
# Individual Checkers
# ──────────────────────────────────────────────


def _check_hard_blocks(hard_blocks: List[HardBlock]) -> List[ComplianceFlag]:
    """Check hard blocks for compliance triggers (wilful defaulter, NCLT, etc.)."""
    flags = []

    for hb in hard_blocks:
        trigger_lower = hb.trigger.lower()

        # Wilful Defaulter → RBI compliance issue
        if "wilful" in trigger_lower and "defaulter" in trigger_lower:
            flags.append(ComplianceFlag(
                trigger=ComplianceTrigger.RBI_DEFAULTER,
                severity=ComplianceSeverity.CRITICAL,
                regulation="RBI Master Circular on Wilful Defaulters (2023)",
                description=(
                    f"Wilful defaulter status detected: {hb.evidence}. "
                    f"Score capped at {hb.score_cap}. "
                    "As per RBI norms, lending to wilful defaulters requires "
                    "enhanced due diligence and compliance committee approval."
                ),
                auto_action="Notify compliance team. Halt pipeline pending review.",
                evidence_sources=[hb.source],
                requires_notification=True,
            ))

        # NCLT proceedings
        elif "nclt" in trigger_lower or "insolvency" in trigger_lower:
            flags.append(ComplianceFlag(
                trigger=ComplianceTrigger.NCLT_PROCEEDINGS,
                severity=ComplianceSeverity.CRITICAL,
                regulation="Insolvency and Bankruptcy Code, 2016 (IBC)",
                description=(
                    f"Active NCLT/insolvency proceedings detected: {hb.evidence}. "
                    f"Score capped at {hb.score_cap}. "
                    "Lending to entities under IBC resolution requires NCLT approval."
                ),
                auto_action="Verify NCLT status. Notify compliance team. No lending without NCLT approval.",
                evidence_sources=[hb.source],
                requires_notification=True,
            ))

        # Criminal case → possible SEBI/RBI issue
        elif "criminal" in trigger_lower:
            flags.append(ComplianceFlag(
                trigger=ComplianceTrigger.SEBI_VIOLATION,
                severity=ComplianceSeverity.HIGH,
                regulation="SEBI LODR Regulations / Companies Act 2013",
                description=(
                    f"Active criminal case against promoter: {hb.evidence}. "
                    f"Score capped at {hb.score_cap}."
                ),
                auto_action="Check if SEBI debarment order exists. Review with legal team.",
                evidence_sources=[hb.source],
                requires_notification=True,
            ))

    return flags


def _check_evidence_rpt_disclosure(evidence: EvidencePackage) -> List[ComplianceFlag]:
    """Check for undisclosed RPTs by comparing board minutes vs AR disclosure."""
    flags = []

    # Look for RPT-related cross-verification results
    for cv in evidence.cross_verifications:
        field_lower = cv.field_name.lower()
        if "rpt" not in field_lower and "related_party" not in field_lower:
            continue

        if cv.status == "conflicting":
            # RPT count or amount mismatch → undisclosed RPTs
            flags.append(ComplianceFlag(
                trigger=ComplianceTrigger.UNDISCLOSED_RPT,
                severity=ComplianceSeverity.HIGH,
                regulation="AS-18 / Ind AS 24 (Related Party Disclosures)",
                description=(
                    f"RPT disclosure discrepancy: {cv.field_name} shows "
                    f"{cv.max_deviation_pct:.1f}% deviation across sources. "
                    "This indicates potential concealment of related party transactions "
                    "in violation of AS-18 / Ind AS 24 disclosure requirements."
                ),
                auto_action=(
                    "Investigate RPT discrepancy. Compare Board Minutes RPT list "
                    "with Annual Report Note on Related Parties. "
                    "Request management explanation for undisclosed transactions."
                ),
                evidence_sources=list(cv.sources.keys()),
                requires_notification=True,
            ))

    # Also check compound insights for RPT concealment
    for insight in evidence.compound_insights:
        if "rpt" in insight.description.lower() and insight.severity in ("HIGH", "CRITICAL"):
            if "conceal" in insight.description.lower() or "undisclosed" in insight.description.lower():
                flags.append(ComplianceFlag(
                    trigger=ComplianceTrigger.UNDISCLOSED_RPT,
                    severity=ComplianceSeverity.HIGH,
                    regulation="AS-18 / Ind AS 24 (Related Party Disclosures)",
                    description=f"Graph reasoning detected RPT concealment: {insight.description}",
                    auto_action="Review RPT disclosure completeness with compliance team.",
                    evidence_sources=insight.evidence_chain,
                    requires_notification=True,
                ))

    return flags


def _check_evidence_fraud_signals(evidence: EvidencePackage) -> List[ComplianceFlag]:
    """Check evidence package compound insights for fraud indicators."""
    flags = []

    for insight in evidence.compound_insights:
        # Circular trading detected with high confidence
        if (
            "circular" in insight.insight_type.lower()
            and insight.confidence >= FRAUD_CONFIDENCE_THRESHOLD
            and insight.severity == "CRITICAL"
        ):
            flags.append(ComplianceFlag(
                trigger=ComplianceTrigger.FRAUD_SIGNAL,
                severity=ComplianceSeverity.CRITICAL,
                regulation="Prevention of Money Laundering Act 2002 (PMLA) / RBI KYC Norms",
                description=(
                    f"Circular trading pattern detected with {insight.confidence:.0%} confidence. "
                    f"{insight.description}"
                ),
                auto_action=(
                    "File suspicious transaction report (STR) with FIU-IND if confirmed. "
                    "Freeze lending process pending investigation."
                ),
                evidence_sources=insight.evidence_chain,
                requires_notification=True,
            ))

    return flags


def _check_ml_fraud_threshold(ml_signals: dict) -> List[ComplianceFlag]:
    """Check ML model outputs for compliance-level fraud signals."""
    flags = []

    # Circular trading by DOMINANT GNN
    if ml_signals.get("circular_trading_detected"):
        gnn_confidence = ml_signals.get("circular_trading_confidence", 0.0)
        if gnn_confidence >= FRAUD_CONFIDENCE_THRESHOLD:
            flags.append(ComplianceFlag(
                trigger=ComplianceTrigger.FRAUD_SIGNAL,
                severity=ComplianceSeverity.CRITICAL,
                regulation="PMLA 2002 / RBI Fraud Monitoring Framework",
                description=(
                    f"DOMINANT GNN detected circular trading with {gnn_confidence:.0%} confidence. "
                    "This exceeds the compliance reporting threshold."
                ),
                auto_action="Investigate circular trading pattern. File STR with FIU-IND if confirmed.",
                evidence_sources=["DOMINANT GNN model output"],
                requires_notification=True,
            ))

    return flags


def _check_pmla_patterns(ml_signals: dict) -> List[ComplianceFlag]:
    """Check for PMLA-reportable suspicious patterns."""
    flags = []

    # High anomaly score from Isolation Forest
    anomaly_score = ml_signals.get("isolation_forest_score", 0.0)
    if anomaly_score >= PMLA_ANOMALY_THRESHOLD:
        flags.append(ComplianceFlag(
            trigger=ComplianceTrigger.PMLA_SUSPICIOUS,
            severity=ComplianceSeverity.HIGH,
            regulation="PMLA 2002 Section 12 — Suspicious Transaction Reporting",
            description=(
                f"Isolation Forest anomaly score {anomaly_score:.2f} exceeds "
                f"PMLA threshold {PMLA_ANOMALY_THRESHOLD:.2f}. "
                "Financial patterns deviate significantly from sector norms."
            ),
            auto_action=(
                "Review flagged anomalies for suspicious transaction indicators. "
                "Determine if STR filing is required under PMLA Section 12."
            ),
            evidence_sources=["Isolation Forest model output"],
            requires_notification=False,
        ))

    # Round-number transaction patterns (money laundering indicator)
    if ml_signals.get("round_number_suspicious"):
        flags.append(ComplianceFlag(
            trigger=ComplianceTrigger.PMLA_SUSPICIOUS,
            severity=ComplianceSeverity.MEDIUM,
            regulation="PMLA 2002 / RBI KYC Master Direction 2016",
            description=(
                "Significant round-number transaction patterns detected in bank statement, "
                "potentially indicative of structuring or layering."
            ),
            auto_action="Review bank statement for transaction structuring patterns.",
            evidence_sources=["Bank statement analysis"],
            requires_notification=False,
        ))

    return flags


def _check_regulatory_findings(findings: List[ResearchFinding]) -> List[ComplianceFlag]:
    """Check research findings for regulatory actions (SEBI, RBI, MCA)."""
    flags = []

    for finding in findings:
        title_lower = finding.title.lower() if finding.title else ""
        content_lower = finding.content.lower() if finding.content else ""
        combined = title_lower + " " + content_lower

        # SEBI action / debarment / penalty
        if finding.category == "regulatory" or finding.source_tier <= 2:
            if any(kw in combined for kw in ["sebi order", "sebi penalty", "debarment", "sebi action"]):
                flags.append(ComplianceFlag(
                    trigger=ComplianceTrigger.SEBI_VIOLATION,
                    severity=ComplianceSeverity.HIGH,
                    regulation="SEBI Act 1992 / SEBI LODR Regulations",
                    description=f"SEBI regulatory action found: {finding.title}",
                    auto_action="Verify SEBI order details. Assess impact on company governance.",
                    evidence_sources=[finding.source, finding.url or ""],
                    requires_notification=True,
                ))

            # RBI circular violation / defaulter list
            if any(kw in combined for kw in [
                "rbi defaulter", "wilful defaulter", "rbi action", "rbi penalty",
                "rbi circular violation",
            ]):
                flags.append(ComplianceFlag(
                    trigger=ComplianceTrigger.RBI_DEFAULTER,
                    severity=ComplianceSeverity.CRITICAL,
                    regulation="RBI Master Circular on Wilful Defaulters",
                    description=f"RBI regulatory finding: {finding.title}",
                    auto_action="Check RBI defaulter database. Halt if confirmed.",
                    evidence_sources=[finding.source, finding.url or ""],
                    requires_notification=True,
                ))

            # NCLT / IBC
            if any(kw in combined for kw in ["nclt", "insolvency", "ibc", "resolution"]):
                flags.append(ComplianceFlag(
                    trigger=ComplianceTrigger.NCLT_PROCEEDINGS,
                    severity=ComplianceSeverity.HIGH,
                    regulation="Insolvency and Bankruptcy Code, 2016",
                    description=f"NCLT/IBC proceeding found: {finding.title}",
                    auto_action="Verify NCLT case status. Determine resolution stage.",
                    evidence_sources=[finding.source, finding.url or ""],
                    requires_notification=True,
                ))

    return flags


def _check_compound_insights_compliance(
    insights: List[CompoundInsight],
) -> List[ComplianceFlag]:
    """Check compound insights for compliance-triggering patterns."""
    flags = []

    for insight in insights:
        desc_lower = insight.description.lower()

        # NCLT / insolvency patterns
        if insight.severity == "CRITICAL" and any(
            kw in desc_lower for kw in ["nclt", "insolvency", "ibc"]
        ):
            flags.append(ComplianceFlag(
                trigger=ComplianceTrigger.NCLT_PROCEEDINGS,
                severity=ComplianceSeverity.CRITICAL,
                regulation="Insolvency and Bankruptcy Code, 2016",
                description=f"Graph reasoning flagged NCLT risk: {insight.description}",
                auto_action="Verify NCLT status. Escalate to compliance committee.",
                evidence_sources=insight.evidence_chain,
                requires_notification=True,
            ))

        # Fraud pattern from graph reasoning
        if insight.severity == "CRITICAL" and "fraud" in desc_lower:
            flags.append(ComplianceFlag(
                trigger=ComplianceTrigger.FRAUD_SIGNAL,
                severity=ComplianceSeverity.CRITICAL,
                regulation="PMLA 2002 / Indian Penal Code",
                description=f"Graph reasoning detected fraud pattern: {insight.description}",
                auto_action="Investigate fraud indicators. Consider filing FIR/STR.",
                evidence_sources=insight.evidence_chain,
                requires_notification=True,
            ))

    return flags


def _check_critical_tickets(tickets: List[Ticket]) -> List[ComplianceFlag]:
    """Check if any CRITICAL tickets indicate compliance issues."""
    flags = []

    for ticket in tickets:
        if ticket.severity != TicketSeverity.CRITICAL:
            continue

        category_lower = ticket.category.lower()

        # ML Fraud tickets → compliance
        if "fraud" in category_lower:
            flags.append(ComplianceFlag(
                trigger=ComplianceTrigger.FRAUD_SIGNAL,
                severity=ComplianceSeverity.HIGH,
                regulation="PMLA 2002 / RBI Fraud Monitoring Framework",
                description=(
                    f"CRITICAL ticket raised for fraud detection: {ticket.title}. "
                    f"{ticket.description[:200]}"
                ),
                auto_action="Review ticket resolution. Ensure compliance awareness.",
                evidence_sources=[ticket.source_a, ticket.source_b],
                requires_notification=False,
            ))

    return flags


# ──────────────────────────────────────────────
# Deduplication & Summary
# ──────────────────────────────────────────────


SEVERITY_ORDER = {
    ComplianceSeverity.CRITICAL: 0,
    ComplianceSeverity.HIGH: 1,
    ComplianceSeverity.MEDIUM: 2,
}


def _deduplicate_flags(flags: List[ComplianceFlag]) -> List[ComplianceFlag]:
    """Keep the highest severity flag for each trigger type."""
    by_trigger: dict[ComplianceTrigger, ComplianceFlag] = {}

    for flag in flags:
        existing = by_trigger.get(flag.trigger)
        if existing is None:
            by_trigger[flag.trigger] = flag
        else:
            # Keep higher severity (lower order number)
            if SEVERITY_ORDER.get(flag.severity, 99) < SEVERITY_ORDER.get(existing.severity, 99):
                by_trigger[flag.trigger] = flag

    # Sort by severity (CRITICAL first)
    result = sorted(
        by_trigger.values(),
        key=lambda f: SEVERITY_ORDER.get(f.severity, 99),
    )
    return result


def _build_summary(flags: List[ComplianceFlag]) -> str:
    """Build a human-readable summary of compliance flags."""
    parts = []
    critical = [f for f in flags if f.severity == ComplianceSeverity.CRITICAL]
    high = [f for f in flags if f.severity == ComplianceSeverity.HIGH]
    medium = [f for f in flags if f.severity == ComplianceSeverity.MEDIUM]

    if critical:
        triggers = ", ".join(f.trigger.value for f in critical)
        parts.append(f"{len(critical)} CRITICAL ({triggers})")
    if high:
        triggers = ", ".join(f.trigger.value for f in high)
        parts.append(f"{len(high)} HIGH ({triggers})")
    if medium:
        triggers = ", ".join(f.trigger.value for f in medium)
        parts.append(f"{len(medium)} MEDIUM ({triggers})")

    return f"Compliance flags: {'; '.join(parts)}. Immediate review required."
