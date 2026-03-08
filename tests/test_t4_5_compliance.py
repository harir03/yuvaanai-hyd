"""
Intelli-Credit — T4.5 Compliance Auto-Flagging Tests

Comprehensive tests covering the compliance engine, API endpoints,
and 5-perspective testing methodology.

Personas:
  🏦 Credit Expert  — Indian regulatory compliance (RBI, SEBI, MCA, PMLA)
  🔒 Security       — injection, path traversal, data isolation
  ⚙️ Systems        — multiple scans, concurrent sessions, deduplication
  🧪 QA Engineer    — edge cases, empty data, boundary thresholds
  🎯 Judge          — demo flow, compelling compliance story
"""

import pytest
from datetime import datetime
from typing import List
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.api.routes._store import assessments_store, compliance_store
from backend.agents.evidence.compliance_engine import (
    ComplianceFlag,
    ComplianceResult,
    ComplianceSeverity,
    ComplianceTrigger,
    scan_compliance,
    FRAUD_CONFIDENCE_THRESHOLD,
    PMLA_ANOMALY_THRESHOLD,
    _check_hard_blocks,
    _check_ml_fraud_threshold,
    _check_pmla_patterns,
    _check_regulatory_findings,
    _check_evidence_rpt_disclosure,
    _check_evidence_fraud_signals,
    _check_compound_insights_compliance,
    _check_critical_tickets,
    _deduplicate_flags,
    _build_summary,
)
from backend.graph.state import (
    CompoundInsight,
    CrossVerificationResult,
    NormalizedField,
    EvidencePackage,
    HardBlock,
)
from backend.graph.state import ResearchFinding
from backend.models.schemas import (
    AssessmentOutcome,
    AssessmentSummary,
    CompanyInfo,
    ScoreBand,
    Ticket,
    TicketSeverity,
)


# ── Helpers ──


def _make_assessment(session_id: str) -> AssessmentSummary:
    return AssessmentSummary(
        session_id=session_id,
        company=CompanyInfo(
            name="XYZ Steel Pvt Ltd",
            sector="Steel",
            loan_type="Working Capital",
            loan_amount="50Cr",
            loan_amount_numeric=50.0,
        ),
        score=477,
        score_band=ScoreBand.POOR,
        outcome=AssessmentOutcome.CONDITIONAL,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )


def _make_hard_block(trigger: str, score_cap: int, evidence: str = "Test evidence", source: str = "RBI") -> HardBlock:
    return HardBlock(trigger=trigger, score_cap=score_cap, evidence=evidence, source=source)


def _make_evidence(**kwargs) -> EvidencePackage:
    defaults = dict(session_id="s1")
    defaults.update(kwargs)
    return EvidencePackage(**defaults)


def _make_finding(
    title: str = "Test finding",
    content: str = "Test content",
    source: str = "MCA21",
    source_tier: int = 1,
    category: str = "regulatory",
    **kwargs,
) -> ResearchFinding:
    return ResearchFinding(
        source=source,
        source_tier=source_tier,
        source_weight=1.0,
        title=title,
        content=content,
        url="https://example.com",
        relevance_score=0.9,
        verified=True,
        category=category,
        **kwargs,
    )


def _make_insight(
    description: str,
    severity: str = "HIGH",
    confidence: float = 0.8,
    insight_type: str = "contradiction",
) -> CompoundInsight:
    return CompoundInsight(
        pass_name="test_pass",
        insight_type=insight_type,
        description=description,
        evidence_chain=["doc1.pdf page 5", "doc2.pdf page 12"],
        score_impact=-20,
        confidence=confidence,
        severity=severity,
    )


# ── Fixtures ──


@pytest.fixture(autouse=True)
def _clear_stores():
    assessments_store.clear()
    compliance_store.clear()
    yield
    assessments_store.clear()
    compliance_store.clear()


# ═══════════════════════════════════════════════════════════════════
#  1. Enum Tests (🧪)
# ═══════════════════════════════════════════════════════════════════


class TestComplianceEnums:
    """Test compliance enums are correctly defined."""

    def test_severity_values(self):
        assert ComplianceSeverity.CRITICAL.value == "CRITICAL"
        assert ComplianceSeverity.HIGH.value == "HIGH"
        assert ComplianceSeverity.MEDIUM.value == "MEDIUM"

    def test_severity_count(self):
        assert len(ComplianceSeverity) == 3

    def test_trigger_values(self):
        expected = {
            "UNDISCLOSED_RPT", "SEBI_VIOLATION", "RBI_DEFAULTER",
            "FRAUD_SIGNAL", "PMLA_SUSPICIOUS", "NCLT_PROCEEDINGS",
            "REGULATORY_NON_COMPLIANCE",
        }
        actual = {t.value for t in ComplianceTrigger}
        assert actual == expected

    def test_trigger_count(self):
        assert len(ComplianceTrigger) == 7


# ═══════════════════════════════════════════════════════════════════
#  2. ComplianceFlag Model Tests (🧪)
# ═══════════════════════════════════════════════════════════════════


class TestComplianceFlagModel:
    """Test ComplianceFlag Pydantic model."""

    def test_create_flag(self):
        flag = ComplianceFlag(
            trigger=ComplianceTrigger.RBI_DEFAULTER,
            severity=ComplianceSeverity.CRITICAL,
            regulation="RBI Master Circular on Wilful Defaulters",
            description="Wilful defaulter detected",
            auto_action="Halt pipeline",
        )
        assert flag.trigger == ComplianceTrigger.RBI_DEFAULTER
        assert flag.severity == ComplianceSeverity.CRITICAL
        assert flag.id  # auto-generated
        assert flag.flagged_at  # auto-timestamp

    def test_flag_with_evidence(self):
        flag = ComplianceFlag(
            trigger=ComplianceTrigger.SEBI_VIOLATION,
            severity=ComplianceSeverity.HIGH,
            regulation="SEBI Act 1992",
            description="SEBI penalty",
            auto_action="Review",
            evidence_sources=["MCA21", "SEBI website"],
        )
        assert len(flag.evidence_sources) == 2

    def test_flag_requires_notification_default_false(self):
        flag = ComplianceFlag(
            trigger=ComplianceTrigger.PMLA_SUSPICIOUS,
            severity=ComplianceSeverity.MEDIUM,
            regulation="PMLA 2002",
            description="Round-number pattern",
            auto_action="Review",
        )
        assert flag.requires_notification is False

    def test_flag_serialization(self):
        flag = ComplianceFlag(
            trigger=ComplianceTrigger.FRAUD_SIGNAL,
            severity=ComplianceSeverity.CRITICAL,
            regulation="PMLA 2002",
            description="Circular trading",
            auto_action="File STR",
            requires_notification=True,
        )
        data = flag.model_dump()
        assert data["trigger"] == "FRAUD_SIGNAL"
        assert data["severity"] == "CRITICAL"
        assert data["requires_notification"] is True


# ═══════════════════════════════════════════════════════════════════
#  3. ComplianceResult Model Tests (🧪)
# ═══════════════════════════════════════════════════════════════════


class TestComplianceResultModel:
    """Test ComplianceResult model and computed properties."""

    def test_empty_result(self):
        result = ComplianceResult(session_id="s1")
        assert result.flagged is False
        assert result.flags == []
        assert result.critical_count == 0
        assert result.high_count == 0
        assert result.requires_immediate_notification is False

    def test_result_with_flags(self):
        flags = [
            ComplianceFlag(
                trigger=ComplianceTrigger.RBI_DEFAULTER,
                severity=ComplianceSeverity.CRITICAL,
                regulation="RBI",
                description="test",
                auto_action="halt",
                requires_notification=True,
            ),
            ComplianceFlag(
                trigger=ComplianceTrigger.SEBI_VIOLATION,
                severity=ComplianceSeverity.HIGH,
                regulation="SEBI",
                description="test",
                auto_action="review",
            ),
        ]
        result = ComplianceResult(
            session_id="s1",
            flagged=True,
            flags=flags,
        )
        assert result.critical_count == 1
        assert result.high_count == 1
        assert result.requires_immediate_notification is True


# ═══════════════════════════════════════════════════════════════════
#  4. Hard Block Compliance Checks (🏦 Credit Expert)
# ═══════════════════════════════════════════════════════════════════


class TestHardBlockCompliance:
    """🏦 Credit domain: hard blocks trigger correct compliance flags."""

    def test_wilful_defaulter_triggers_rbi_flag(self):
        """Wilful defaulter on RBI list → CRITICAL RBI_DEFAULTER flag."""
        blocks = [_make_hard_block("Wilful Defaulter (RBI List)", 200, "Company on RBI wilful defaulter list")]
        flags = _check_hard_blocks(blocks)
        assert len(flags) == 1
        assert flags[0].trigger == ComplianceTrigger.RBI_DEFAULTER
        assert flags[0].severity == ComplianceSeverity.CRITICAL
        assert flags[0].requires_notification is True
        assert "RBI" in flags[0].regulation

    def test_nclt_proceedings_triggers_flag(self):
        """Active NCLT proceedings → CRITICAL NCLT flag."""
        blocks = [_make_hard_block("NCLT Active Proceedings", 250, "NCLT case filed")]
        flags = _check_hard_blocks(blocks)
        assert len(flags) == 1
        assert flags[0].trigger == ComplianceTrigger.NCLT_PROCEEDINGS
        assert flags[0].severity == ComplianceSeverity.CRITICAL
        assert "IBC" in flags[0].regulation

    def test_insolvency_proceedings_triggers_flag(self):
        """Insolvency keyword also triggers NCLT flag."""
        blocks = [_make_hard_block("Active insolvency case", 250, "IBC proceedings ongoing")]
        flags = _check_hard_blocks(blocks)
        assert len(flags) == 1
        assert flags[0].trigger == ComplianceTrigger.NCLT_PROCEEDINGS

    def test_criminal_case_triggers_sebi_flag(self):
        """Criminal case against promoter → HIGH SEBI flag."""
        blocks = [_make_hard_block("Active criminal case against promoter", 150, "FIR #12345")]
        flags = _check_hard_blocks(blocks)
        assert len(flags) == 1
        assert flags[0].trigger == ComplianceTrigger.SEBI_VIOLATION
        assert flags[0].severity == ComplianceSeverity.HIGH

    def test_dscr_hard_block_no_compliance_flag(self):
        """DSCR < 1.0x is a financial hard block, NOT a compliance issue."""
        blocks = [_make_hard_block("DSCR < 1.0x", 300, "DSCR = 0.85x")]
        flags = _check_hard_blocks(blocks)
        assert len(flags) == 0

    def test_multiple_hard_blocks(self):
        """Multiple hard blocks can each raise separate flags."""
        blocks = [
            _make_hard_block("Wilful Defaulter (RBI)", 200, "RBI list match"),
            _make_hard_block("NCLT proceedings", 250, "IBC case active"),
        ]
        flags = _check_hard_blocks(blocks)
        assert len(flags) == 2
        triggers = {f.trigger for f in flags}
        assert ComplianceTrigger.RBI_DEFAULTER in triggers
        assert ComplianceTrigger.NCLT_PROCEEDINGS in triggers


# ═══════════════════════════════════════════════════════════════════
#  5. RPT Disclosure Compliance (🏦 Credit Expert)
# ═══════════════════════════════════════════════════════════════════


class TestRPTDisclosure:
    """🏦 Credit domain: RPT concealment detection."""

    def test_rpt_cross_verification_conflict(self):
        """RPT discrepancy in cross-verification → UNDISCLOSED_RPT flag."""
        evidence = _make_evidence(
            cross_verifications=[
                CrossVerificationResult(
                    field_name="rpt_count",
                    status="conflicting",
                    sources={
                        "Board Minutes": NormalizedField(value="5", confidence=0.9, source_document="BoardMinutes.pdf"),
                        "Annual Report": NormalizedField(value="2", confidence=0.85, source_document="AR2024.pdf"),
                    },
                    accepted_value="5",
                    accepted_source="Board Minutes",
                    max_deviation_pct=60.0,
                ),
            ],
        )
        flags = _check_evidence_rpt_disclosure(evidence)
        assert len(flags) >= 1
        rpt_flags = [f for f in flags if f.trigger == ComplianceTrigger.UNDISCLOSED_RPT]
        assert len(rpt_flags) >= 1
        assert "AS-18" in rpt_flags[0].regulation or "Ind AS 24" in rpt_flags[0].regulation

    def test_rpt_concealment_in_compound_insights(self):
        """RPT concealment detected by graph reasoning → UNDISCLOSED_RPT flag."""
        evidence = _make_evidence(
            compound_insights=[
                _make_insight(
                    "Undisclosed RPT with Radiance Infra — Board Minutes show ₹12cr contract but AR mentions nothing",
                    severity="CRITICAL",
                ),
            ],
        )
        flags = _check_evidence_rpt_disclosure(evidence)
        rpt_flags = [f for f in flags if f.trigger == ComplianceTrigger.UNDISCLOSED_RPT]
        assert len(rpt_flags) >= 1

    def test_non_rpt_conflict_not_flagged(self):
        """Revenue conflict is NOT an RPT compliance issue."""
        evidence = _make_evidence(
            cross_verifications=[
                CrossVerificationResult(
                    field_name="revenue",
                    status="conflicting",
                    sources={
                        "AR": NormalizedField(value="247Cr", confidence=0.9, source_document="AR.pdf"),
                        "GST": NormalizedField(value="198Cr", confidence=0.95, source_document="GST.pdf"),
                    },
                    accepted_value="198Cr",
                    accepted_source="GST",
                    max_deviation_pct=20.0,
                ),
            ],
        )
        flags = _check_evidence_rpt_disclosure(evidence)
        assert len(flags) == 0


# ═══════════════════════════════════════════════════════════════════
#  6. ML Fraud Signal Compliance (🏦 + ⚙️)
# ═══════════════════════════════════════════════════════════════════


class TestMLFraudCompliance:
    """Compliance flags from ML model outputs."""

    def test_circular_trading_above_threshold(self):
        """GNN circular trading above confidence threshold → FRAUD_SIGNAL."""
        ml = {"circular_trading_detected": True, "circular_trading_confidence": 0.85}
        flags = _check_ml_fraud_threshold(ml)
        assert len(flags) == 1
        assert flags[0].trigger == ComplianceTrigger.FRAUD_SIGNAL
        assert flags[0].severity == ComplianceSeverity.CRITICAL

    def test_circular_trading_below_threshold(self):
        """GNN circular trading below threshold → no flag."""
        ml = {"circular_trading_detected": True, "circular_trading_confidence": 0.50}
        flags = _check_ml_fraud_threshold(ml)
        assert len(flags) == 0

    def test_no_circular_trading(self):
        """No circular trading detected → no flag."""
        ml = {"circular_trading_detected": False}
        flags = _check_ml_fraud_threshold(ml)
        assert len(flags) == 0

    def test_pmla_high_anomaly_score(self):
        """High anomaly score → PMLA_SUSPICIOUS flag."""
        ml = {"isolation_forest_score": 0.92}
        flags = _check_pmla_patterns(ml)
        assert len(flags) == 1
        assert flags[0].trigger == ComplianceTrigger.PMLA_SUSPICIOUS
        assert "PMLA" in flags[0].regulation

    def test_pmla_low_anomaly_score(self):
        """Low anomaly score → no flag."""
        ml = {"isolation_forest_score": 0.50}
        flags = _check_pmla_patterns(ml)
        assert len(flags) == 0

    def test_round_number_suspicious(self):
        """Round-number transaction patterns → PMLA MEDIUM flag."""
        ml = {"round_number_suspicious": True}
        flags = _check_pmla_patterns(ml)
        assert len(flags) == 1
        assert flags[0].trigger == ComplianceTrigger.PMLA_SUSPICIOUS
        assert flags[0].severity == ComplianceSeverity.MEDIUM

    def test_evidence_fraud_circular_critical(self):
        """Evidence package compound insight: circular trading with high confidence."""
        evidence = _make_evidence(
            compound_insights=[
                CompoundInsight(
                    pass_name="hidden_relationships",
                    insight_type="circular_trading",
                    description="A→B→C→A circular trading pattern detected",
                    evidence_chain=["AR p5", "GST p12", "Bank p34"],
                    score_impact=-80,
                    confidence=0.85,
                    severity="CRITICAL",
                ),
            ],
        )
        flags = _check_evidence_fraud_signals(evidence)
        assert len(flags) == 1
        assert flags[0].trigger == ComplianceTrigger.FRAUD_SIGNAL
        assert flags[0].requires_notification is True


# ═══════════════════════════════════════════════════════════════════
#  7. Regulatory Research Findings (🏦)
# ═══════════════════════════════════════════════════════════════════


class TestRegulatoryFindings:
    """Compliance flags from research/regulatory findings."""

    def test_sebi_penalty_finding(self):
        """SEBI penalty in research → SEBI_VIOLATION flag."""
        findings = [_make_finding(
            title="SEBI Order: Penalty on XYZ Steel",
            content="SEBI imposed ₹5cr penalty for RPT non-disclosure",
        )]
        flags = _check_regulatory_findings(findings)
        sebi = [f for f in flags if f.trigger == ComplianceTrigger.SEBI_VIOLATION]
        assert len(sebi) >= 1

    def test_sebi_debarment_finding(self):
        """SEBI debarment in research → SEBI_VIOLATION flag."""
        findings = [_make_finding(
            title="Promoter debarment by SEBI",
            content="SEBI debarment order for insider trading",
        )]
        flags = _check_regulatory_findings(findings)
        sebi = [f for f in flags if f.trigger == ComplianceTrigger.SEBI_VIOLATION]
        assert len(sebi) >= 1

    def test_rbi_defaulter_finding(self):
        """RBI wilful defaulter in research → RBI_DEFAULTER flag."""
        findings = [_make_finding(
            title="Company on RBI defaulter list",
            content="Promoter's other entity is a wilful defaulter on RBI list",
        )]
        flags = _check_regulatory_findings(findings)
        rbi = [f for f in flags if f.trigger == ComplianceTrigger.RBI_DEFAULTER]
        assert len(rbi) >= 1
        assert rbi[0].severity == ComplianceSeverity.CRITICAL

    def test_nclt_finding(self):
        """NCLT/IBC research finding → NCLT flag."""
        findings = [_make_finding(
            title="NCLT Case Against Subsidiary",
            content="NCLT insolvency proceedings filed by creditors",
        )]
        flags = _check_regulatory_findings(findings)
        nclt = [f for f in flags if f.trigger == ComplianceTrigger.NCLT_PROCEEDINGS]
        assert len(nclt) >= 1

    def test_non_regulatory_finding_no_flag(self):
        """General financial finding without regulatory keywords → no flag."""
        findings = [_make_finding(
            title="Revenue Growth Analysis",
            content="Company shows 15% revenue growth over 3 years",
            category="financial",
        )]
        flags = _check_regulatory_findings(findings)
        assert len(flags) == 0

    def test_low_tier_finding_not_flagged(self):
        """Low-tier source (blog, tier 4+) with non-regulatory category doesn't trigger compliance flag."""
        findings = [_make_finding(
            title="SEBI penalty rumor",
            content="Blog says SEBI action coming",
            source="random_blog",
            source_tier=4,
            category="news",
        )]
        flags = _check_regulatory_findings(findings)
        assert len(flags) == 0


# ═══════════════════════════════════════════════════════════════════
#  8. Compound Insights Compliance (🏦)
# ═══════════════════════════════════════════════════════════════════


class TestCompoundInsightsCompliance:
    """Compliance flags from graph reasoning compound insights."""

    def test_nclt_insight_critical(self):
        """CRITICAL insight mentioning NCLT → compliance flag."""
        insights = [_make_insight("NCLT proceedings may affect loan recovery", severity="CRITICAL")]
        flags = _check_compound_insights_compliance(insights)
        assert len(flags) >= 1
        nclt = [f for f in flags if f.trigger == ComplianceTrigger.NCLT_PROCEEDINGS]
        assert len(nclt) >= 1

    def test_fraud_insight_critical(self):
        """CRITICAL fraud insight → compliance flag."""
        insights = [_make_insight("Potential fraud detected in supply chain", severity="CRITICAL")]
        flags = _check_compound_insights_compliance(insights)
        fraud = [f for f in flags if f.trigger == ComplianceTrigger.FRAUD_SIGNAL]
        assert len(fraud) >= 1

    def test_non_critical_insight_no_flag(self):
        """HIGH severity non-NCLT/fraud insight → no compliance flag."""
        insights = [_make_insight("Revenue trending down", severity="HIGH")]
        flags = _check_compound_insights_compliance(insights)
        assert len(flags) == 0

    def test_low_severity_nclt_no_flag(self):
        """LOW severity NCLT mention → no compliance flag (only CRITICAL triggers)."""
        insights = [_make_insight("Minor NCLT reference in disclosures", severity="LOW")]
        flags = _check_compound_insights_compliance(insights)
        assert len(flags) == 0


# ═══════════════════════════════════════════════════════════════════
#  9. Critical Ticket Compliance (⚙️)
# ═══════════════════════════════════════════════════════════════════


class TestCriticalTickets:
    """Compliance flags from CRITICAL tickets."""

    def test_critical_fraud_ticket(self):
        """CRITICAL fraud ticket → compliance flag."""
        tickets = [Ticket(
            session_id="s1",
            title="ML Fraud: Circular Trading",
            description="GNN detected circular pattern",
            severity=TicketSeverity.CRITICAL,
            category="ML Fraud Signal",
            source_a="GNN model",
            source_b="No document evidence",
            ai_recommendation="Investigate",
            score_impact=-50,
        )]
        flags = _check_critical_tickets(tickets)
        assert len(flags) == 1
        assert flags[0].trigger == ComplianceTrigger.FRAUD_SIGNAL

    def test_non_critical_ticket_no_flag(self):
        """HIGH ticket → no compliance flag (only CRITICAL triggers here)."""
        tickets = [Ticket(
            session_id="s1",
            title="Revenue Discrepancy",
            description="20% gap",
            severity=TicketSeverity.HIGH,
            category="Revenue Discrepancy",
            source_a="AR",
            source_b="GST",
            ai_recommendation="Accept GST",
            score_impact=-15,
        )]
        flags = _check_critical_tickets(tickets)
        assert len(flags) == 0

    def test_critical_non_fraud_ticket_no_flag(self):
        """CRITICAL non-fraud category ticket → no compliance flag."""
        tickets = [Ticket(
            session_id="s1",
            title="Data Quality Issue",
            description="OCR failed",
            severity=TicketSeverity.CRITICAL,
            category="Data Quality",
            source_a="OCR",
            source_b="Expected",
            ai_recommendation="Re-scan",
            score_impact=-30,
        )]
        flags = _check_critical_tickets(tickets)
        assert len(flags) == 0


# ═══════════════════════════════════════════════════════════════════
#  10. Deduplication & Summary (⚙️ + 🧪)
# ═══════════════════════════════════════════════════════════════════


class TestDeduplicationAndSummary:
    """Test flag deduplication and summary generation."""

    def test_dedup_keeps_highest_severity(self):
        """When same trigger appears twice, keep CRITICAL over HIGH."""
        flags = [
            ComplianceFlag(
                trigger=ComplianceTrigger.RBI_DEFAULTER,
                severity=ComplianceSeverity.HIGH,
                regulation="RBI",
                description="High severity",
                auto_action="review",
            ),
            ComplianceFlag(
                trigger=ComplianceTrigger.RBI_DEFAULTER,
                severity=ComplianceSeverity.CRITICAL,
                regulation="RBI",
                description="Critical severity",
                auto_action="halt",
            ),
        ]
        deduped = _deduplicate_flags(flags)
        assert len(deduped) == 1
        assert deduped[0].severity == ComplianceSeverity.CRITICAL

    def test_dedup_different_triggers_kept(self):
        """Different trigger types are all kept."""
        flags = [
            ComplianceFlag(trigger=ComplianceTrigger.RBI_DEFAULTER, severity=ComplianceSeverity.CRITICAL, regulation="RBI", description="t", auto_action="a"),
            ComplianceFlag(trigger=ComplianceTrigger.SEBI_VIOLATION, severity=ComplianceSeverity.HIGH, regulation="SEBI", description="t", auto_action="a"),
            ComplianceFlag(trigger=ComplianceTrigger.PMLA_SUSPICIOUS, severity=ComplianceSeverity.MEDIUM, regulation="PMLA", description="t", auto_action="a"),
        ]
        deduped = _deduplicate_flags(flags)
        assert len(deduped) == 3

    def test_dedup_sorted_by_severity(self):
        """Results are sorted: CRITICAL first, then HIGH, then MEDIUM."""
        flags = [
            ComplianceFlag(trigger=ComplianceTrigger.PMLA_SUSPICIOUS, severity=ComplianceSeverity.MEDIUM, regulation="P", description="t", auto_action="a"),
            ComplianceFlag(trigger=ComplianceTrigger.RBI_DEFAULTER, severity=ComplianceSeverity.CRITICAL, regulation="R", description="t", auto_action="a"),
            ComplianceFlag(trigger=ComplianceTrigger.SEBI_VIOLATION, severity=ComplianceSeverity.HIGH, regulation="S", description="t", auto_action="a"),
        ]
        deduped = _deduplicate_flags(flags)
        assert deduped[0].severity == ComplianceSeverity.CRITICAL
        assert deduped[1].severity == ComplianceSeverity.HIGH
        assert deduped[2].severity == ComplianceSeverity.MEDIUM

    def test_summary_with_flags(self):
        """Summary includes counts per severity."""
        flags = [
            ComplianceFlag(trigger=ComplianceTrigger.RBI_DEFAULTER, severity=ComplianceSeverity.CRITICAL, regulation="R", description="t", auto_action="a"),
            ComplianceFlag(trigger=ComplianceTrigger.SEBI_VIOLATION, severity=ComplianceSeverity.HIGH, regulation="S", description="t", auto_action="a"),
        ]
        summary = _build_summary(flags)
        assert "1 CRITICAL" in summary
        assert "1 HIGH" in summary
        assert "review required" in summary.lower()

    def test_empty_dedup(self):
        """Empty input → empty output."""
        assert _deduplicate_flags([]) == []


# ═══════════════════════════════════════════════════════════════════
#  11. Full scan_compliance Integration (🏦 + ⚙️)
# ═══════════════════════════════════════════════════════════════════


class TestScanComplianceFull:
    """Integration tests for the full scan_compliance function."""

    def test_scan_with_no_data(self):
        """Scan with no data → no flags."""
        result = scan_compliance(session_id="s1")
        assert result.flagged is False
        assert len(result.flags) == 0
        assert result.summary == "No compliance flags raised."

    def test_scan_with_hard_block(self):
        """Scan with wilful defaulter hard block → compliance flagged."""
        result = scan_compliance(
            session_id="s1",
            hard_blocks=[_make_hard_block("Wilful Defaulter", 200, "RBI match")],
        )
        assert result.flagged is True
        assert result.critical_count >= 1

    def test_scan_with_ml_signals(self):
        """Scan with ML fraud signals → compliance flagged."""
        result = scan_compliance(
            session_id="s1",
            ml_signals={
                "circular_trading_detected": True,
                "circular_trading_confidence": 0.90,
            },
        )
        assert result.flagged is True
        fraud = [f for f in result.flags if f.trigger == ComplianceTrigger.FRAUD_SIGNAL]
        assert len(fraud) >= 1

    def test_scan_with_evidence_package(self):
        """Scan reads from evidence package when provided."""
        ep = _make_evidence(
            ml_signals={"isolation_forest_score": 0.92},
            compound_insights=[
                _make_insight("NCLT risk detected", severity="CRITICAL"),
            ],
        )
        result = scan_compliance(session_id="s1", evidence=ep)
        assert result.flagged is True

    def test_scan_deduplicates(self):
        """Scan deduplicates flags from multiple sources."""
        result = scan_compliance(
            session_id="s1",
            hard_blocks=[_make_hard_block("Wilful Defaulter (RBI)", 200)],
            research_findings=[_make_finding(
                title="RBI defaulter list match",
                content="Company on wilful defaulter registry",
            )],
        )
        # Both hard block and research trigger RBI_DEFAULTER, dedup to 1
        rbi_flags = [f for f in result.flags if f.trigger == ComplianceTrigger.RBI_DEFAULTER]
        assert len(rbi_flags) == 1

    def test_scan_preserves_session_id(self):
        result = scan_compliance(session_id="session-xyz")
        assert result.session_id == "session-xyz"

    def test_scan_combined_all_sources(self):
        """Scan with all data sources produces comprehensive result."""
        result = scan_compliance(
            session_id="s1",
            hard_blocks=[_make_hard_block("NCLT proceedings", 250)],
            ml_signals={"circular_trading_detected": True, "circular_trading_confidence": 0.80},
            research_findings=[_make_finding(
                title="SEBI penalty imposed",
                content="SEBI order for ₹5cr penalty",
            )],
            compound_insights=[_make_insight("Fraud pattern in supply chain", severity="CRITICAL")],
        )
        assert result.flagged is True
        # Multiple distinct triggers
        triggers = {f.trigger for f in result.flags}
        assert len(triggers) >= 2  # At least NCLT + FRAUD or SEBI


# ═══════════════════════════════════════════════════════════════════
#  12. API Endpoint Tests (🧪 + 🔒)
# ═══════════════════════════════════════════════════════════════════


class TestComplianceAPI:
    """Tests for compliance REST API endpoints."""

    @pytest.mark.asyncio
    async def test_get_compliance_empty(self):
        """GET returns empty result when not yet scanned."""
        assessments_store["s1"] = _make_assessment("s1")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/s1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["flagged"] is False
        assert data["flags"] == []

    @pytest.mark.asyncio
    async def test_get_compliance_404(self):
        """GET for unknown session → 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_scan(self):
        """POST scan creates a result."""
        assessments_store["s1"] = _make_assessment("s1")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/api/compliance/s1/scan")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "flagged" in data
        assert "flags" in data

    @pytest.mark.asyncio
    async def test_scan_persists_to_store(self):
        """POST scan result is retrievable via GET."""
        assessments_store["s1"] = _make_assessment("s1")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            await ac.post("/api/compliance/s1/scan")
            resp = await ac.get("/api/compliance/s1")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "s1"

    @pytest.mark.asyncio
    async def test_scan_404(self):
        """POST scan for unknown session → 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/api/compliance/nonexistent/scan")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_flags_empty(self):
        """GET flags returns empty list when no scan done."""
        assessments_store["s1"] = _make_assessment("s1")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/s1/flags")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_flags_404(self):
        """GET flags for unknown session → 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/nonexistent/flags")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_flags_with_stored_result(self):
        """GET flags returns stored compliance flags."""
        assessments_store["s1"] = _make_assessment("s1")
        compliance_store["s1"] = ComplianceResult(
            session_id="s1",
            flagged=True,
            flags=[
                ComplianceFlag(
                    trigger=ComplianceTrigger.RBI_DEFAULTER,
                    severity=ComplianceSeverity.CRITICAL,
                    regulation="RBI Master Circular",
                    description="Wilful defaulter",
                    auto_action="Halt",
                    requires_notification=True,
                ),
                ComplianceFlag(
                    trigger=ComplianceTrigger.SEBI_VIOLATION,
                    severity=ComplianceSeverity.HIGH,
                    regulation="SEBI LODR",
                    description="Penalty imposed",
                    auto_action="Review",
                ),
            ],
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/s1/flags")
        data = resp.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_filter_flags_by_severity(self):
        """GET flags with severity filter."""
        assessments_store["s1"] = _make_assessment("s1")
        compliance_store["s1"] = ComplianceResult(
            session_id="s1",
            flagged=True,
            flags=[
                ComplianceFlag(trigger=ComplianceTrigger.RBI_DEFAULTER, severity=ComplianceSeverity.CRITICAL, regulation="R", description="t", auto_action="a"),
                ComplianceFlag(trigger=ComplianceTrigger.PMLA_SUSPICIOUS, severity=ComplianceSeverity.MEDIUM, regulation="P", description="t", auto_action="a"),
            ],
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/s1/flags?severity=CRITICAL")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["severity"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_filter_flags_by_trigger(self):
        """GET flags with trigger filter."""
        assessments_store["s1"] = _make_assessment("s1")
        compliance_store["s1"] = ComplianceResult(
            session_id="s1",
            flagged=True,
            flags=[
                ComplianceFlag(trigger=ComplianceTrigger.RBI_DEFAULTER, severity=ComplianceSeverity.CRITICAL, regulation="R", description="t", auto_action="a"),
                ComplianceFlag(trigger=ComplianceTrigger.SEBI_VIOLATION, severity=ComplianceSeverity.HIGH, regulation="S", description="t", auto_action="a"),
            ],
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/s1/flags?trigger=SEBI_VIOLATION")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["trigger"] == "SEBI_VIOLATION"

    @pytest.mark.asyncio
    async def test_filter_flags_by_notification(self):
        """GET flags with requires_notification filter."""
        assessments_store["s1"] = _make_assessment("s1")
        compliance_store["s1"] = ComplianceResult(
            session_id="s1",
            flagged=True,
            flags=[
                ComplianceFlag(trigger=ComplianceTrigger.RBI_DEFAULTER, severity=ComplianceSeverity.CRITICAL, regulation="R", description="t", auto_action="a", requires_notification=True),
                ComplianceFlag(trigger=ComplianceTrigger.PMLA_SUSPICIOUS, severity=ComplianceSeverity.MEDIUM, regulation="P", description="t", auto_action="a", requires_notification=False),
            ],
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/s1/flags?requires_notification=true")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["requires_notification"] is True


# ═══════════════════════════════════════════════════════════════════
#  13. Security Tests (🔒)
# ═══════════════════════════════════════════════════════════════════


class TestComplianceSecurity:
    """Security-focused compliance tests."""

    @pytest.mark.asyncio
    async def test_session_isolation(self):
        """Compliance flags for s1 not visible in s2."""
        assessments_store["s1"] = _make_assessment("s1")
        assessments_store["s2"] = _make_assessment("s2")
        compliance_store["s1"] = ComplianceResult(
            session_id="s1",
            flagged=True,
            flags=[ComplianceFlag(trigger=ComplianceTrigger.RBI_DEFAULTER, severity=ComplianceSeverity.CRITICAL, regulation="R", description="t", auto_action="a")],
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/s2/flags")
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_path_traversal(self):
        """Path traversal in session_id returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/../../etc/passwd")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_severity_filter(self):
        """Invalid severity filter returns 422."""
        assessments_store["s1"] = _make_assessment("s1")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/s1/flags?severity=INVALID")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_trigger_filter(self):
        """Invalid trigger filter returns 422."""
        assessments_store["s1"] = _make_assessment("s1")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/compliance/s1/flags?trigger=INVALID")
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
#  14. Edge Cases (🧪)
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case tests for compliance engine."""

    def test_empty_hard_blocks(self):
        assert _check_hard_blocks([]) == []

    def test_empty_ml_signals(self):
        assert _check_ml_fraud_threshold({}) == []
        assert _check_pmla_patterns({}) == []

    def test_empty_findings(self):
        assert _check_regulatory_findings([]) == []

    def test_empty_insights(self):
        assert _check_compound_insights_compliance([]) == []

    def test_empty_tickets(self):
        assert _check_critical_tickets([]) == []

    def test_threshold_boundary_fraud(self):
        """Confidence exactly at threshold → flag raised."""
        ml = {
            "circular_trading_detected": True,
            "circular_trading_confidence": FRAUD_CONFIDENCE_THRESHOLD,
        }
        flags = _check_ml_fraud_threshold(ml)
        assert len(flags) == 1

    def test_threshold_boundary_pmla(self):
        """Anomaly score exactly at PMLA threshold → flag raised."""
        ml = {"isolation_forest_score": PMLA_ANOMALY_THRESHOLD}
        flags = _check_pmla_patterns(ml)
        assert len(flags) == 1

    def test_threshold_below_fraud(self):
        """Confidence just below threshold → no flag."""
        ml = {
            "circular_trading_detected": True,
            "circular_trading_confidence": FRAUD_CONFIDENCE_THRESHOLD - 0.01,
        }
        flags = _check_ml_fraud_threshold(ml)
        assert len(flags) == 0

    def test_threshold_below_pmla(self):
        """Anomaly score just below PMLA threshold → no flag."""
        ml = {"isolation_forest_score": PMLA_ANOMALY_THRESHOLD - 0.01}
        flags = _check_pmla_patterns(ml)
        assert len(flags) == 0


# ═══════════════════════════════════════════════════════════════════
#  15. Demo / Judge Tests (🎯)
# ═══════════════════════════════════════════════════════════════════


class TestDemoCompliance:
    """Demo-quality tests demonstrating compliance storytelling."""

    def test_xyz_steel_compliance_story(self):
        """Full compliance scan telling the XYZ Steel story for judges."""
        # XYZ Steel: wilful defaulter + undisclosed RPT + ML fraud
        result = scan_compliance(
            session_id="xyz-steel-001",
            hard_blocks=[
                _make_hard_block(
                    "Wilful Defaulter (RBI List)",
                    200,
                    "XYZ Steel promoter's entity 'Radiance Infra' is on RBI wilful defaulter list",
                    "RBI CRILC database",
                ),
            ],
            ml_signals={
                "circular_trading_detected": True,
                "circular_trading_confidence": 0.87,
                "isolation_forest_score": 0.89,
            },
            research_findings=[
                _make_finding(
                    "SEBI Order: Penalty on Promoter",
                    "SEBI imposed ₹2cr penalty for RPT non-disclosure under LODR",
                    source="SEBI website",
                    source_tier=1,
                ),
            ],
        )

        assert result.flagged is True
        assert result.critical_count >= 1
        assert result.requires_immediate_notification is True

        # Three distinct compliance concerns
        triggers = {f.trigger for f in result.flags}
        assert ComplianceTrigger.RBI_DEFAULTER in triggers
        assert ComplianceTrigger.FRAUD_SIGNAL in triggers

        # Summary tells a compelling story
        assert "CRITICAL" in result.summary

    @pytest.mark.asyncio
    async def test_api_compliance_workflow(self):
        """Full API workflow: scan → get result → filter flags."""
        assessments_store["demo1"] = _make_assessment("demo1")

        # Store a rich compliance result
        compliance_store["demo1"] = ComplianceResult(
            session_id="demo1",
            flagged=True,
            flags=[
                ComplianceFlag(
                    trigger=ComplianceTrigger.RBI_DEFAULTER,
                    severity=ComplianceSeverity.CRITICAL,
                    regulation="RBI Master Circular on Wilful Defaulters (2023)",
                    description="Promoter's related entity on RBI wilful defaulter list — CRILC match",
                    auto_action="CRITICAL: Notify compliance. Halt lending. File regulatory disclosure.",
                    evidence_sources=["RBI CRILC", "MCA21 director network"],
                    requires_notification=True,
                ),
                ComplianceFlag(
                    trigger=ComplianceTrigger.UNDISCLOSED_RPT,
                    severity=ComplianceSeverity.HIGH,
                    regulation="AS-18 / Ind AS 24 (Related Party Disclosures)",
                    description="Board minutes show 5 RPTs totaling ₹47cr, AR discloses only 2 RPTs (₹18cr)",
                    auto_action="Request full RPT schedule from management. Verify with audit committee.",
                    evidence_sources=["Board Minutes FY24", "Annual Report FY24 Note 33"],
                    requires_notification=True,
                ),
                ComplianceFlag(
                    trigger=ComplianceTrigger.PMLA_SUSPICIOUS,
                    severity=ComplianceSeverity.MEDIUM,
                    regulation="PMLA 2002 Section 12",
                    description="Anomaly score 0.89 — unusual financial patterns compared to sector peers",
                    auto_action="Review anomalies with compliance. Determine STR filing necessity.",
                    evidence_sources=["Isolation Forest model"],
                    requires_notification=False,
                ),
            ],
            summary="Compliance flags: 1 CRITICAL (RBI_DEFAULTER); 1 HIGH (UNDISCLOSED_RPT); 1 MEDIUM (PMLA_SUSPICIOUS). Immediate review required.",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # Get full result
            resp = await ac.get("/api/compliance/demo1")
            assert resp.json()["flagged"] is True
            assert len(resp.json()["flags"]) == 3

            # Filter: only CRITICAL
            resp = await ac.get("/api/compliance/demo1/flags?severity=CRITICAL")
            assert len(resp.json()) == 1
            assert resp.json()[0]["trigger"] == "RBI_DEFAULTER"

            # Filter: only notifications
            resp = await ac.get("/api/compliance/demo1/flags?requires_notification=true")
            assert len(resp.json()) == 2  # RBI + RPT
