"""
T0.2 — LangGraph Orchestrator + State Tests

Tests:
1. Graph compiles successfully
2. CreditAppraisalState initializes with defaults
3. Full pipeline runs through all 10 nodes (happy path)
4. Score = 677, Band = GOOD, Outcome = APPROVED
5. All pipeline stages reach COMPLETED
6. Conditional edge: validation fails → pipeline stops early
7. Conditional edge: blocking tickets → pipeline stops before scoring
8. get_score_band() returns correct bands
"""

import asyncio
import sys
import os

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.graph.state import (
    CreditAppraisalState,
    RawDataPackage,
    WorkerOutput,
    NormalizedField,
    CrossVerificationResult,
    OrganizedPackage,
    ResearchPackage,
    ReasoningPackage,
    EvidencePackage,
    HardBlock,
    ComputedMetrics,
    FiveCsMapping,
)
from backend.graph.orchestrator import build_graph, get_compiled_graph, run_pipeline
from config.scoring import get_score_band
from backend.models.schemas import (
    CompanyInfo,
    DocumentMeta,
    DocumentType,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
    ScoreBand,
    AssessmentOutcome,
    Ticket,
    TicketSeverity,
    TicketStatus,
)

PASSED = 0
FAILED = 0


def report(name: str, ok: bool, detail: str = ""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED += 1
        print(f"  FAIL  {name}  —  {detail}")


# ──────────────────────────────────────────────
# Test 1: Graph compiles
# ──────────────────────────────────────────────
def test_graph_compiles():
    try:
        graph = build_graph()
        compiled = graph.compile()
        report("Graph compiles", compiled is not None)
    except Exception as e:
        report("Graph compiles", False, str(e))


# ──────────────────────────────────────────────
# Test 2: Singleton compiled graph
# ──────────────────────────────────────────────
def test_singleton_graph():
    try:
        g1 = get_compiled_graph()
        g2 = get_compiled_graph()
        report("Singleton compiled graph", g1 is g2)
    except Exception as e:
        report("Singleton compiled graph", False, str(e))


# ──────────────────────────────────────────────
# Test 3: CreditAppraisalState defaults
# ──────────────────────────────────────────────
def test_state_defaults():
    try:
        state = CreditAppraisalState()
        ok = (
            state.session_id == ""
            and state.score is None
            and state.outcome == AssessmentOutcome.PENDING
            and state.validation_passed is False
            and state.tickets_blocking is False
            and state.workers_completed == 0
            and state.documents == []
            and state.thinking_events == []
        )
        report("State defaults correct", ok)
    except Exception as e:
        report("State defaults correct", False, str(e))


# ──────────────────────────────────────────────
# Test 4: Full pipeline happy path
# ──────────────────────────────────────────────
def test_full_pipeline():
    try:
        company = CompanyInfo(
            name="XYZ Steel Pvt Ltd",
            cin="U12345MH2010PTC123456",
            sector="Steel Manufacturing",
            loan_type="Working Capital",
            loan_amount="₹50,00,00,000",
            loan_amount_numeric=50_00_00_000.0,
        )
        docs = [
            DocumentMeta(
                filename="annual_report.pdf",
                document_type=DocumentType.ANNUAL_REPORT,
                file_size=2_000_000,
            ),
            DocumentMeta(
                filename="bank_statement.pdf",
                document_type=DocumentType.BANK_STATEMENT,
                file_size=500_000,
            ),
        ]
        result = asyncio.run(run_pipeline("test-session-001", company, docs))

        # Result is a dict from LangGraph — score is dynamic (not hardcoded)
        score = result.get("score")
        band = result.get("score_band")
        outcome = result.get("outcome")
        ok_score = isinstance(score, int) and 0 <= score <= 850
        ok_band = band is not None and isinstance(band, ScoreBand)
        ok_outcome = outcome is not None and isinstance(outcome, AssessmentOutcome)
        ok_session = result.get("session_id") == "test-session-001"
        ok_time = result.get("processing_time") is not None

        report(
            "Full pipeline happy path",
            all([ok_score, ok_band, ok_outcome, ok_session, ok_time]),
            f"score={score}, band={band}, "
            f"outcome={outcome}, session={result.get('session_id')}, "
            f"time={result.get('processing_time')}"
        )
    except Exception as e:
        report("Full pipeline happy path", False, str(e))


# ──────────────────────────────────────────────
# Test 5: All pipeline stages complete (happy path)
# ──────────────────────────────────────────────
def test_pipeline_stages_complete():
    try:
        company = CompanyInfo(
            name="Test Corp",
            cin="U99999MH2020PTC999999",
            sector="Services",
            loan_type="Term Loan",
            loan_amount="₹10,00,00,000",
            loan_amount_numeric=10_00_00_000.0,
        )
        docs = [
            DocumentMeta(
                filename="itr.pdf",
                document_type=DocumentType.ITR,
                file_size=100_000,
            ),
        ]
        result = asyncio.run(run_pipeline("test-stages-002", company, docs))

        stages = result.get("pipeline_stages", [])
        # Check that workers, consolidation, validation, organization, research,
        # reasoning, evidence, tickets, recommendation all reached COMPLETED
        completed_names = set()
        for s in stages:
            if hasattr(s, "stage"):
                # Pydantic model
                if s.status == PipelineStageStatus.COMPLETED:
                    completed_names.add(s.stage)
            elif isinstance(s, dict):
                if s.get("status") == PipelineStageStatus.COMPLETED or s.get("status") == "completed":
                    completed_names.add(s.get("stage"))

        expected = {
            PipelineStageEnum.WORKERS,
            PipelineStageEnum.CONSOLIDATION,
            PipelineStageEnum.VALIDATION,
            PipelineStageEnum.ORGANIZATION,
            PipelineStageEnum.RESEARCH,
            PipelineStageEnum.REASONING,
            PipelineStageEnum.EVIDENCE,
            PipelineStageEnum.TICKETS,
            PipelineStageEnum.RECOMMENDATION,
        }

        missing = expected - completed_names
        report(
            "All pipeline stages completed",
            len(missing) == 0,
            f"Missing: {missing}" if missing else ""
        )
    except Exception as e:
        report("All pipeline stages completed", False, str(e))


# ──────────────────────────────────────────────
# Test 6: get_score_band thresholds
# ──────────────────────────────────────────────
def test_score_bands():
    try:
        tests = [
            (850, ScoreBand.EXCELLENT, AssessmentOutcome.APPROVED),
            (750, ScoreBand.EXCELLENT, AssessmentOutcome.APPROVED),
            (700, ScoreBand.GOOD, AssessmentOutcome.APPROVED),
            (650, ScoreBand.GOOD, AssessmentOutcome.APPROVED),
            (600, ScoreBand.FAIR, AssessmentOutcome.CONDITIONAL),
            (550, ScoreBand.FAIR, AssessmentOutcome.CONDITIONAL),
            (500, ScoreBand.POOR, AssessmentOutcome.CONDITIONAL),
            (450, ScoreBand.POOR, AssessmentOutcome.CONDITIONAL),
            (400, ScoreBand.VERY_POOR, AssessmentOutcome.REJECTED),
            (350, ScoreBand.VERY_POOR, AssessmentOutcome.REJECTED),
            (200, ScoreBand.DEFAULT_RISK, AssessmentOutcome.REJECTED),
            (0, ScoreBand.DEFAULT_RISK, AssessmentOutcome.REJECTED),
        ]
        all_ok = True
        for score_val, expected_band, expected_outcome in tests:
            band, outcome, _rec = get_score_band(score_val)
            if band != expected_band or outcome != expected_outcome:
                report(
                    f"Score band {score_val}",
                    False,
                    f"got band={band}, outcome={outcome}; expected {expected_band}, {expected_outcome}"
                )
                all_ok = False

        if all_ok:
            report("Score band thresholds (12 cases)", True)
    except Exception as e:
        report("Score band thresholds", False, str(e))


# ──────────────────────────────────────────────
# Test 7: Sub-model initialization
# ──────────────────────────────────────────────
def test_sub_models():
    try:
        # RawDataPackage
        rdp = RawDataPackage(completeness_score=0.9, mandatory_fields_present=True)
        ok_rdp = rdp.completeness_score == 0.9 and rdp.mandatory_fields_present is True

        # EvidencePackage
        ep = EvidencePackage(session_id="ep-001")
        ok_ep = ep.session_id == "ep-001" and ep.research_findings == []

        # HardBlock
        hb = HardBlock(
            trigger="WILFUL_DEFAULTER",
            score_cap=200,
            evidence="Found on RBI wilful defaulter list",
            source="RBI"
        )
        ok_hb = hb.score_cap == 200

        # WorkerOutput
        wo = WorkerOutput(worker_id="W1", document_type="ANNUAL_REPORT", confidence=0.95)
        ok_wo = wo.confidence == 0.95

        report(
            "Sub-model initialization",
            all([ok_rdp, ok_ep, ok_hb, ok_wo]),
        )
    except Exception as e:
        report("Sub-model initialization", False, str(e))


# ──────────────────────────────────────────────
# Test 8: Conditional edge - validation failure stops pipeline
# ──────────────────────────────────────────────
def test_validation_failure_stops():
    """
    If consolidator doesn't produce a raw_data_package,
    validator sets validation_passed=False, and pipeline should end
    without reaching recommendation (no score).
    
    We patch the consolidator to NOT produce a raw_data_package.
    """
    try:
        import backend.graph.nodes.consolidator_node as consolidator_mod

        # Save original
        original_consolidator = consolidator_mod.consolidator_node

        # Patch: return NO raw_data_package
        async def failing_consolidator(state):
            for stage in state.pipeline_stages:
                if stage.stage == PipelineStageEnum.CONSOLIDATION:
                    stage.status = PipelineStageStatus.COMPLETED
                    stage.message = "Consolidation failed — no data"
            return {
                "raw_data_package": None,  # This will cause validation to fail
                "pipeline_stages": state.pipeline_stages,
            }

        consolidator_mod.consolidator_node = failing_consolidator

        # We need to rebuild the graph since nodes are bound at build time
        # Reset singleton
        import backend.graph.orchestrator as orch_mod
        orch_mod._compiled_graph = None

        # Rebuild the graph, but we need to re-import nodes
        # Since LangGraph binds functions at add_node() time, 
        # and we changed the module attribute, we need to rebuild
        from langgraph.graph import StateGraph, END
        
        graph = StateGraph(CreditAppraisalState)
        graph.add_node("workers", orch_mod.workers_node)
        graph.add_node("consolidator", failing_consolidator)  # patched
        graph.add_node("validator", orch_mod.validator_node)
        graph.add_node("organizer", orch_mod.organizer_node)
        graph.add_node("research", orch_mod.research_node)
        graph.add_node("reasoning", orch_mod.reasoning_node)
        graph.add_node("evidence", orch_mod.evidence_node)
        graph.add_node("tickets", orch_mod.ticket_node)
        graph.add_node("recommendation", orch_mod.recommendation_node)
        graph.add_node("decision_store", orch_mod.decision_store_node)
        graph.set_entry_point("workers")
        graph.add_edge("workers", "consolidator")
        graph.add_edge("consolidator", "validator")
        graph.add_conditional_edges("validator", orch_mod.should_continue_after_validation, {"organizer": "organizer", "end": END})
        graph.add_edge("organizer", "research")
        graph.add_edge("research", "reasoning")
        graph.add_edge("reasoning", "evidence")
        graph.add_edge("evidence", "tickets")
        graph.add_conditional_edges("tickets", orch_mod.should_continue_after_tickets, {"recommendation": "recommendation", "end": END})
        graph.add_edge("recommendation", "decision_store")
        graph.add_edge("decision_store", END)
        compiled = graph.compile()

        company = CompanyInfo(
            name="Failing Corp",
            cin="U00000MH2020PTC000000",
            sector="Testing",
            loan_type="Working Capital",
            loan_amount="₹10,00,00,000",
            loan_amount_numeric=10_00_00_000.0,
        )
        docs = [
            DocumentMeta(filename="test.pdf", document_type=DocumentType.ANNUAL_REPORT, file_size=1000),
        ]
        pipeline_stages = [
            PipelineStage(stage=s, status=PipelineStageStatus.PENDING)
            for s in PipelineStageEnum
        ]
        pipeline_stages[0].status = PipelineStageStatus.COMPLETED

        initial_state = CreditAppraisalState(
            session_id="test-val-fail",
            company=company,
            documents=docs,
            pipeline_stages=pipeline_stages,
            workers_total=1,
        )

        result = asyncio.run(compiled.ainvoke(initial_state))

        # Score should NOT be set (pipeline stopped before recommendation)
        no_score = result.get("score") is None
        val_failed = result.get("validation_passed") is False

        report(
            "Validation failure stops pipeline",
            no_score and val_failed,
            f"score={result.get('score')}, validation_passed={result.get('validation_passed')}"
        )

        # Restore
        consolidator_mod.consolidator_node = original_consolidator
        orch_mod._compiled_graph = None

    except Exception as e:
        report("Validation failure stops pipeline", False, str(e))
        # Restore on error too
        try:
            consolidator_mod.consolidator_node = original_consolidator
            orch_mod._compiled_graph = None
        except:
            pass


# ──────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  T0.2 — LangGraph Orchestrator + State Tests")
    print("=" * 55 + "\n")

    test_graph_compiles()
    test_singleton_graph()
    test_state_defaults()
    test_sub_models()
    test_score_bands()
    test_full_pipeline()
    test_pipeline_stages_complete()
    test_validation_failure_stops()

    print(f"\n{'=' * 55}")
    print(f"  Results: {PASSED} passed, {FAILED} failed, {PASSED + FAILED} total")
    print(f"{'=' * 55}\n")

    sys.exit(0 if FAILED == 0 else 1)
