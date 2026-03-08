"""
Intelli-Credit — T3.3 Decision Store Node Tests

Tests for the final LangGraph node that persists complete assessments.

5-Perspective Testing:
🏦 Credit Domain Expert — record captures full credit assessment data
🔒 Security Architect — no PII leakage, data integrity
⚙️ Systems Engineer — handles missing data, concurrent writes, large states
🧪 QA Engineer — edge cases: null scores, empty documents, partial state
🎯 Hackathon Judge — audit trail, summary messages, thinking events emitted
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from backend.graph.state import (
    CreditAppraisalState,
    WorkerOutput,
    RawDataPackage,
    CrossVerificationResult,
    ResearchPackage,
    ResearchFinding,
    ReasoningPackage,
    CompoundInsight,
    EvidencePackage,
    HardBlock,
)
from backend.graph.nodes.decision_store_node import (
    decision_store_node,
    decision_records,
    _build_decision_record,
)
from backend.models.schemas import (
    CompanyInfo,
    DocumentMeta,
    DocumentType,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
    ThinkingEvent,
    Ticket,
    TicketSeverity,
    TicketStatus,
    ScoreBand,
    ScoreModuleSummary,
    ScoreModule,
    ScoreBreakdownEntry,
    AssessmentOutcome,
    EventType,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_company(**overrides):
    defaults = dict(
        name="XYZ Steel Ltd",
        sector="Manufacturing",
        loan_type="Working Capital",
        loan_amount="₹50 Crore",
        loan_amount_numeric=50.0,
        cin="U27100MH2005PLC123456",
        gstin="27AAACX1234F1Z5",
    )
    defaults.update(overrides)
    return CompanyInfo(**defaults)


def _make_entry(module=ScoreModule.CAPACITY, metric="DSCR", impact=20):
    return ScoreBreakdownEntry(
        module=module,
        metric_name=metric,
        metric_value="1.38x",
        computation_formula="Net Profit + Depreciation / Debt Service",
        source_document="annual_report.pdf",
        source_page=42,
        source_excerpt="DSCR stands at 1.38x",
        benchmark_context="Benchmark: 1.25x for Manufacturing",
        score_impact=impact,
        reasoning="Adequate debt service coverage",
        confidence=0.92,
    )


def _make_state(session_id="ds-test-001", **overrides) -> CreditAppraisalState:
    defaults = dict(
        session_id=session_id,
        company=_make_company(),
        documents=[
            DocumentMeta(filename="annual_report.pdf", document_type=DocumentType.ANNUAL_REPORT, file_size=1024),
            DocumentMeta(filename="bank_stmt.pdf", document_type=DocumentType.BANK_STATEMENT, file_size=2048),
            DocumentMeta(filename="gst_returns.pdf", document_type=DocumentType.GST_RETURNS, file_size=512),
        ],
        score=477,
        score_band=ScoreBand.POOR,
        outcome=AssessmentOutcome.CONDITIONAL,
        score_modules=[
            ScoreModuleSummary(
                module=ScoreModule.CAPACITY,
                score=80,
                max_positive=150,
                max_negative=-100,
                metrics=[_make_entry()],
            ),
        ],
        thinking_events=[
            ThinkingEvent(session_id=session_id, agent="Workers", event_type=EventType.READ, message="Reading docs"),
        ],
        tickets=[
            Ticket(
                session_id=session_id,
                title="Revenue mismatch",
                description="AR vs GST divergence",
                severity=TicketSeverity.HIGH,
                status=TicketStatus.OPEN,
                category="Revenue Discrepancy",
                source_a="AR Revenue: ₹247cr",
                source_b="GST Revenue: ₹198cr",
                ai_recommendation="Use GST figure (government source, higher credibility)",
                score_impact=-25,
                raised_by="Agent 0.5",
            ),
        ],
        cam_path="/data/cam/ds-test-001.docx",
        created_at=datetime.utcnow() - timedelta(minutes=5),
    )
    defaults.update(overrides)
    return CreditAppraisalState(**defaults)


@pytest.fixture(autouse=True)
def clean_records():
    decision_records.clear()
    yield
    decision_records.clear()


# ──────────────────────────────────────────────
# 🏦 Credit Domain Expert — Record Captures Full Assessment
# ──────────────────────────────────────────────

class TestCreditDecisionStore:
    """🏦 Decision record must capture all credit assessment data."""

    @pytest.mark.asyncio
    async def test_persists_score_and_band(self):
        """Record captures final score and band correctly."""
        state = _make_state("credit-ds-001", score=650, score_band=ScoreBand.GOOD)
        await decision_store_node(state)

        record = decision_records["credit-ds-001"]
        assert record["score"] == 650
        assert record["score_band"] == "Good"

    @pytest.mark.asyncio
    async def test_persists_outcome(self):
        """Record captures the lending outcome."""
        state = _make_state("credit-ds-002", outcome=AssessmentOutcome.APPROVED)
        await decision_store_node(state)

        record = decision_records["credit-ds-002"]
        assert record["outcome"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_persists_hard_blocks(self):
        """Record captures hard block triggers with evidence."""
        state = _make_state("credit-ds-003", hard_blocks=[
            HardBlock(trigger="Wilful Defaulter", score_cap=200, evidence="RBI list match", source="RBI"),
            HardBlock(trigger="DSCR < 1.0", score_cap=300, evidence="DSCR = 0.87", source="Annual Report"),
        ])
        await decision_store_node(state)

        record = decision_records["credit-ds-003"]
        assert len(record["hard_blocks"]) == 2
        assert record["hard_blocks"][0]["trigger"] == "Wilful Defaulter"
        assert record["hard_blocks"][0]["score_cap"] == 200

    @pytest.mark.asyncio
    async def test_persists_company_info(self):
        """Record captures company details."""
        state = _make_state("credit-ds-004")
        await decision_store_node(state)

        record = decision_records["credit-ds-004"]
        assert record["company_name"] == "XYZ Steel Ltd"
        assert record["sector"] == "Manufacturing"
        assert record["loan_type"] == "Working Capital"
        assert record["loan_amount_numeric"] == 50.0

    @pytest.mark.asyncio
    async def test_persists_score_modules(self):
        """Record captures all scoring module summaries."""
        state = _make_state("credit-ds-005")
        await decision_store_node(state)

        record = decision_records["credit-ds-005"]
        assert len(record["score_modules"]) == 1
        assert record["score_modules"][0]["module"] == "CAPACITY"
        assert record["score_modules"][0]["score"] == 80

    @pytest.mark.asyncio
    async def test_persists_document_types(self):
        """Record captures which document types were analyzed."""
        state = _make_state("credit-ds-006")
        await decision_store_node(state)

        record = decision_records["credit-ds-006"]
        assert record["documents_analyzed"] == 3
        assert "ANNUAL_REPORT" in record["document_types"]
        assert "BANK_STATEMENT" in record["document_types"]


# ──────────────────────────────────────────────
# 🔒 Security Architect — Data Integrity
# ──────────────────────────────────────────────

class TestSecurityDecisionStore:
    """🔒 Decision store must maintain data integrity."""

    @pytest.mark.asyncio
    async def test_record_has_session_id(self):
        """Every record has its session_id for traceability."""
        state = _make_state("sec-ds-001")
        await decision_store_node(state)

        record = decision_records["sec-ds-001"]
        assert record["session_id"] == "sec-ds-001"

    @pytest.mark.asyncio
    async def test_no_raw_cin_in_record(self):
        """Record doesn't expose raw CIN (stored at company level, not duplicated)."""
        state = _make_state("sec-ds-002")
        await decision_store_node(state)

        record = decision_records["sec-ds-002"]
        # CIN should not be a top-level field in the decision record
        assert "cin" not in record

    @pytest.mark.asyncio
    async def test_separate_sessions_isolated(self):
        """Two sessions don't interfere with each other."""
        state1 = _make_state("sec-ds-003", score=700)
        state2 = _make_state("sec-ds-004", score=400)

        await decision_store_node(state1)
        await decision_store_node(state2)

        assert decision_records["sec-ds-003"]["score"] == 700
        assert decision_records["sec-ds-004"]["score"] == 400

    @pytest.mark.asyncio
    async def test_record_has_completion_timestamp(self):
        """Record includes completion timestamp for audit."""
        state = _make_state("sec-ds-005")
        await decision_store_node(state)

        record = decision_records["sec-ds-005"]
        assert record["completed_at"] is not None


# ──────────────────────────────────────────────
# ⚙️ Systems Engineer — Robustness
# ──────────────────────────────────────────────

class TestReliabilityDecisionStore:
    """⚙️ Decision store handles edge cases and failures."""

    @pytest.mark.asyncio
    async def test_handles_none_score(self):
        """Handles assessment with no score (pipeline failed early)."""
        state = _make_state("rel-ds-001", score=None, score_band=None)
        await decision_store_node(state)

        record = decision_records["rel-ds-001"]
        assert record["score"] is None
        assert record["score_band"] is None

    @pytest.mark.asyncio
    async def test_handles_empty_documents(self):
        """Handles state with no documents."""
        state = _make_state("rel-ds-002", documents=[])
        await decision_store_node(state)

        record = decision_records["rel-ds-002"]
        assert record["documents_analyzed"] == 0
        assert record["document_types"] == []

    @pytest.mark.asyncio
    async def test_handles_no_company(self):
        """Handles state with no company info."""
        state = CreditAppraisalState(session_id="rel-ds-003")
        await decision_store_node(state)

        record = decision_records["rel-ds-003"]
        assert record["company_name"] == "Unknown"
        assert record["sector"] == "Unknown"

    @pytest.mark.asyncio
    async def test_handles_empty_tickets(self):
        """Handles state with no tickets."""
        state = _make_state("rel-ds-004", tickets=[])
        await decision_store_node(state)

        record = decision_records["rel-ds-004"]
        assert record["total_tickets"] == 0
        assert record["tickets_blocking"] is False

    @pytest.mark.asyncio
    async def test_handles_no_research_package(self):
        """Handles state without research results."""
        state = _make_state("rel-ds-005", research_package=None)
        await decision_store_node(state)

        record = decision_records["rel-ds-005"]
        assert record["research_findings_count"] == 0

    @pytest.mark.asyncio
    async def test_handles_no_reasoning_package(self):
        """Handles state without graph reasoning results."""
        state = _make_state("rel-ds-006", reasoning_package=None)
        await decision_store_node(state)

        record = decision_records["rel-ds-006"]
        assert record["compound_insights_count"] == 0

    @pytest.mark.asyncio
    async def test_overwrites_on_rerun(self):
        """Re-running pipeline for same session overwrites the record."""
        state1 = _make_state("rel-ds-007", score=400)
        state2 = _make_state("rel-ds-007", score=600)

        await decision_store_node(state1)
        assert decision_records["rel-ds-007"]["score"] == 400

        await decision_store_node(state2)
        assert decision_records["rel-ds-007"]["score"] == 600


# ──────────────────────────────────────────────
# 🧪 QA Engineer — Edge Cases
# ──────────────────────────────────────────────

class TestEdgeCasesDecisionStore:
    """🧪 Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_returns_thinking_events(self):
        """Node returns thinking events in output dict."""
        state = _make_state("qa-ds-001")
        result = await decision_store_node(state)

        assert "thinking_events" in result
        # Should have original + new events from decision store
        assert len(result["thinking_events"]) > 1

    @pytest.mark.asyncio
    async def test_returns_processing_time(self):
        """Node returns processing time string."""
        state = _make_state("qa-ds-002")
        result = await decision_store_node(state)

        assert "processing_time" in result
        assert isinstance(result["processing_time"], str)
        assert len(result["processing_time"]) > 0

    @pytest.mark.asyncio
    async def test_preserves_existing_thinking_events(self):
        """Existing thinking events are preserved, new ones appended."""
        state = _make_state("qa-ds-003")
        original_count = len(state.thinking_events)
        result = await decision_store_node(state)

        # Original events preserved + new decision store events added
        assert len(result["thinking_events"]) > original_count

    @pytest.mark.asyncio
    async def test_emits_critical_for_hard_blocks(self):
        """Emits CRITICAL thinking event when hard blocks exist."""
        state = _make_state("qa-ds-004", hard_blocks=[
            HardBlock(trigger="Wilful Defaulter", score_cap=200, evidence="RBI", source="RBI"),
        ])
        result = await decision_store_node(state)

        critical_events = [
            e for e in result["thinking_events"]
            if e.event_type == EventType.CRITICAL
        ]
        assert len(critical_events) >= 1
        assert "Wilful Defaulter" in critical_events[0].message

    @pytest.mark.asyncio
    async def test_build_decision_record_standalone(self):
        """_build_decision_record works independently."""
        state = _make_state("qa-ds-005", score=800, score_band=ScoreBand.EXCELLENT)
        record = _build_decision_record(state)

        assert record["score"] == 800
        assert record["score_band"] == "Excellent"
        assert record["session_id"] == "qa-ds-005"

    @pytest.mark.asyncio
    async def test_score_at_boundary_values(self):
        """Records correct at score boundaries."""
        for score, band in [
            (850, ScoreBand.EXCELLENT),
            (750, ScoreBand.EXCELLENT),
            (650, ScoreBand.GOOD),
            (550, ScoreBand.FAIR),
            (450, ScoreBand.POOR),
            (350, ScoreBand.VERY_POOR),
            (0, ScoreBand.DEFAULT_RISK),
        ]:
            state = _make_state(f"qa-ds-boundary-{score}", score=score, score_band=band)
            await decision_store_node(state)
            record = decision_records[f"qa-ds-boundary-{score}"]
            assert record["score"] == score
            assert record["score_band"] == band.value


# ──────────────────────────────────────────────
# 🎯 Hackathon Judge — Audit Trail & Demo Value
# ──────────────────────────────────────────────

class TestDemoDecisionStore:
    """🎯 Decision store supports compelling demo story."""

    @pytest.mark.asyncio
    async def test_summary_message_has_score(self):
        """Thinking event summary mentions the score."""
        state = _make_state("demo-ds-001", score=477)
        result = await decision_store_node(state)

        decided_events = [
            e for e in result["thinking_events"]
            if e.event_type == EventType.DECIDED and "477" in e.message
        ]
        assert len(decided_events) >= 1

    @pytest.mark.asyncio
    async def test_summary_includes_outcome(self):
        """Summary message includes the lending outcome."""
        state = _make_state("demo-ds-002", outcome=AssessmentOutcome.REJECTED)
        result = await decision_store_node(state)

        messages = [e.message for e in result["thinking_events"]]
        assert any("REJECTED" in m for m in messages)

    @pytest.mark.asyncio
    async def test_summary_includes_document_count(self):
        """Summary mentions how many documents were analyzed."""
        state = _make_state("demo-ds-003")
        result = await decision_store_node(state)

        messages = [e.message for e in result["thinking_events"]]
        assert any("3 documents" in m for m in messages)

    @pytest.mark.asyncio
    async def test_record_has_all_demo_fields(self):
        """Record has every field needed for the Decision Store UI."""
        state = _make_state("demo-ds-004")
        state.research_package = ResearchPackage(
            findings=[
                ResearchFinding(source="tavily", source_tier=2, source_weight=0.85,
                                title="News", content="Steel sector outlook positive"),
            ],
            total_findings=1,
        )
        state.reasoning_package = ReasoningPackage(
            insights=[CompoundInsight(pass_name="cascade", insight_type="risk", description="Cascading debt risk")],
            total_compound_score_impact=-30,
            passes_completed=5,
        )
        state.raw_data_package = RawDataPackage(
            cross_verifications=[
                CrossVerificationResult(field_name="revenue", status="flagged", max_deviation_pct=20.0),
            ],
        )

        await decision_store_node(state)
        record = decision_records["demo-ds-004"]

        # All demo fields present
        assert record["company_name"] == "XYZ Steel Ltd"
        assert record["score"] == 477
        assert record["score_band"] == "Poor"
        assert record["outcome"] == "CONDITIONAL"
        assert record["documents_analyzed"] == 3
        assert record["total_tickets"] == 1
        assert record["research_findings_count"] == 1
        assert record["compound_insights_count"] == 1
        assert record["cross_verifications_count"] == 1
        assert record["cam_path"] is not None
        assert record["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_agent_name_is_decision_store(self):
        """Thinking events emitted by this node have correct agent name."""
        state = _make_state("demo-ds-005")
        result = await decision_store_node(state)

        ds_events = [e for e in result["thinking_events"] if e.agent == "Decision Store"]
        assert len(ds_events) >= 2  # At least READ + DECIDED
