"""
Intelli-Credit — T3.1 Tests: Workers W4-W8

Five-Perspective Testing:
🏦 Credit Domain Expert — ITR/AR divergence detection, RPT concealment cross-check,
    rating downgrade impact, litigation disclosure gaps, pledge delta analysis
🔒 Security Architect — path traversal in file_path, malformed extraction resilience
⚙️ Systems Engineer — concurrent worker dispatch, large file handling, idempotency
🧪 QA Engineer — missing files, empty docs, null propagation, boundary values
🎯 Hackathon Judge — realistic XYZ Steel data, storytelling in ThinkingEvents

Tests cover:
  W4 (ITR): Schedule BP/BS extraction, ITR-AR divergence, revenue cross-verification
  W5 (Legal): Case extraction, forum classification, AR disclosure gap detection
  W6 (Board): Director attendance, RPT concealment (board vs AR), KMP changes
  W7 (Shareholding): Promoter pledge, pledge delta, cross-holdings, dilution trend
  W8 (Rating): Rating/outlook, downgrade history, watch status, peer comparison
  Registry: All 8 workers registered, dispatch for all document types
  Integration: Full 8-document dispatch cycle through workers_node
"""

import asyncio
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.schemas import (
    DocumentType, WorkerStatusEnum, CompanyInfo, DocumentMeta,
    PipelineStage, PipelineStageEnum,
)
from backend.graph.state import WorkerOutput, CreditAppraisalState
from backend.workers.base_worker import BaseDocumentWorker
from backend.workers.w4_itr import ITRWorker
from backend.workers.w5_legal_notice import LegalNoticeWorker
from backend.workers.w6_board_minutes import BoardMinutesWorker
from backend.workers.w7_shareholding import ShareholdingWorker
from backend.workers.w8_rating_report import RatingReportWorker
from backend.workers.task_registry import (
    WORKER_REGISTRY,
    get_worker_class,
    get_worker_id,
    list_registered_workers,
    dispatch_workers,
)
from backend.thinking.redis_publisher import reset_publisher, get_publisher
from backend.storage.redis_client import get_redis_client, reset_redis_client


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
async def reset_singletons():
    """Reset Redis + publisher singletons for clean state."""
    reset_publisher()
    reset_redis_client()
    redis = get_redis_client()
    await redis.initialize()
    yield


@pytest.fixture
def tmp_files():
    """Create temporary mock document files for all 8 types."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = {}
        for name in [
            "annual_report.pdf", "bank_statement.pdf", "gst_returns.pdf",
            "itr.pdf", "legal_notice.pdf", "board_minutes.pdf",
            "shareholding.pdf", "rating_report.pdf",
        ]:
            path = os.path.join(tmpdir, name)
            with open(path, "w") as f:
                f.write(f"Mock document content for {name}")
            paths[name.split(".")[0]] = path
        yield paths


SESSION = "test-t31-session"


# ══════════════════════════════════════════════
# REGISTRY TESTS — All 8 Workers
# ══════════════════════════════════════════════

class TestWorkerRegistry:
    """🏦 + ⚙️ — Verify all 8 workers are properly registered."""

    def test_registry_has_8_workers(self):
        """All 8 document types have registered workers."""
        registered = list_registered_workers()
        assert len(registered) == 8
        for wid in ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]:
            assert wid in registered, f"Worker {wid} not registered"

    def test_worker_class_lookup_w4_itr(self):
        assert get_worker_class(DocumentType.ITR) is ITRWorker

    def test_worker_class_lookup_w5_legal(self):
        assert get_worker_class(DocumentType.LEGAL_NOTICE) is LegalNoticeWorker

    def test_worker_class_lookup_w6_board(self):
        assert get_worker_class(DocumentType.BOARD_MINUTES) is BoardMinutesWorker

    def test_worker_class_lookup_w7_shareholding(self):
        assert get_worker_class(DocumentType.SHAREHOLDING_PATTERN) is ShareholdingWorker

    def test_worker_class_lookup_w8_rating(self):
        assert get_worker_class(DocumentType.RATING_REPORT) is RatingReportWorker

    def test_worker_id_generation(self):
        """get_worker_id returns correct IDs for all document types."""
        assert get_worker_id(DocumentType.ITR) == "W4"
        assert get_worker_id(DocumentType.LEGAL_NOTICE) == "W5"
        assert get_worker_id(DocumentType.BOARD_MINUTES) == "W6"
        assert get_worker_id(DocumentType.SHAREHOLDING_PATTERN) == "W7"
        assert get_worker_id(DocumentType.RATING_REPORT) == "W8"


# ══════════════════════════════════════════════
# W4 — ITR Worker Tests
# ══════════════════════════════════════════════

class TestW4ITRWorker:
    """🏦 Credit Expert: ITR-AR divergence, Schedule BP/BS accuracy.
    🧪 QA: Missing file, null propagation.
    🎯 Judge: Realistic XYZ Steel data with cross-verification signals."""

    async def test_w4_completes_successfully(self, tmp_files):
        w = ITRWorker(SESSION, tmp_files["itr"])
        output = await w.process()
        assert output.status == "completed"
        assert output.worker_id == "W4"
        assert output.document_type == DocumentType.ITR.value
        assert output.confidence > 0.8
        assert output.pages_processed > 0

    async def test_w4_extracts_schedule_bp(self, tmp_files):
        """🏦 Schedule BP must have turnover, gross profit, net profit, tax."""
        w = ITRWorker(SESSION, tmp_files["itr"])
        output = await w.process()
        bp = output.extracted_data["schedule_bp"]
        assert bp["turnover"] > 0, "Schedule BP turnover must be positive"
        assert bp["gross_profit"] > 0
        assert bp["net_profit"] > 0
        assert bp["tax_payable"] > 0
        assert bp["source_page"] is not None

    async def test_w4_extracts_schedule_bs(self, tmp_files):
        """🏦 Schedule BS must have assets, liabilities, net worth, debt."""
        w = ITRWorker(SESSION, tmp_files["itr"])
        output = await w.process()
        bs = output.extracted_data["schedule_bs"]
        assert bs["total_assets"] > 0
        assert bs["net_worth"] > 0
        assert bs["total_debt"] > 0
        # Balance sheet must balance
        assert bs["total_assets"] == bs["total_liabilities"]

    async def test_w4_revenue_for_cross_verification(self, tmp_files):
        """🏦 ITR must provide revenue figure matching cross-verification format."""
        w = ITRWorker(SESSION, tmp_files["itr"])
        output = await w.process()
        rev = output.extracted_data["revenue_from_itr"]
        assert "turnover" in rev
        assert rev["turnover"] > 0
        assert rev["unit"] == "lakhs"

    async def test_w4_itr_ar_divergence_detection(self, tmp_files):
        """🏦 Credit Expert: System must flag ITR vs AR revenue divergence."""
        w = ITRWorker(SESSION, tmp_files["itr"])
        output = await w.process()
        div = output.extracted_data["itr_ar_divergence"]
        assert "itr_revenue" in div
        assert "ar_revenue_expected" in div
        assert "divergence_pct" in div
        # Real-world: small divergences are common, large ones are red flags
        assert div["divergence_pct"] >= 0

    async def test_w4_handles_missing_file(self):
        """🧪 QA: Missing file must return failed status, not crash."""
        w = ITRWorker("test-missing", "/nonexistent/itr.pdf")
        output = await w.process()
        assert output.status == "failed"
        assert len(output.errors) > 0

    async def test_w4_emits_thinking_events(self, tmp_files):
        """🎯 Judge: Events must tell a story about what was found."""
        w = ITRWorker(SESSION, tmp_files["itr"])
        await w.process()
        publisher = get_publisher()
        events = publisher.get_event_log(SESSION)
        # Must have READ + FOUND + FLAGGED events
        event_types = [e.get("event_type") or e.get("type", "") for e in events]
        assert any("READ" in str(t) for t in event_types), "No READ events emitted"
        assert any("FOUND" in str(t) for t in event_types), "No FOUND events emitted"
        assert any("FLAGGED" in str(t) for t in event_types), "Must flag ITR-AR divergence"


# ══════════════════════════════════════════════
# W5 — Legal Notice Worker Tests
# ══════════════════════════════════════════════

class TestW5LegalNoticeWorker:
    """🏦 Credit Expert: Case classification, NCLT detection, AR disclosure gap.
    🧪 QA: Missing file, boundary cases.
    🎯 Judge: Dramatic undisclosed litigation finding."""

    async def test_w5_completes_successfully(self, tmp_files):
        w = LegalNoticeWorker(SESSION, tmp_files["legal_notice"])
        output = await w.process()
        assert output.status == "completed"
        assert output.worker_id == "W5"
        assert output.confidence > 0.8

    async def test_w5_extracts_all_cases(self, tmp_files):
        """🏦 Must extract each case with forum, amount, status, severity."""
        w = LegalNoticeWorker(SESSION, tmp_files["legal_notice"])
        output = await w.process()
        cases = output.extracted_data["cases"]
        assert len(cases) >= 2, "Must find multiple cases"
        for case in cases:
            assert "case_id" in case
            assert "forum" in case
            assert "claim_amount" in case
            assert case["claim_amount"] > 0
            assert "status" in case
            assert "severity" in case

    async def test_w5_classifies_forum_types(self, tmp_files):
        """🏦 Must distinguish NCLT, ITAT, Consumer, High Court, etc."""
        w = LegalNoticeWorker(SESSION, tmp_files["legal_notice"])
        output = await w.process()
        forums = [c["forum"] for c in output.extracted_data["cases"]]
        # XYZ Steel has NCLT + ITAT + Consumer Forum cases
        assert any("NCLT" in f for f in forums), "Must identify NCLT cases"
        assert any("ITAT" in f for f in forums), "Must identify ITAT cases"

    async def test_w5_detects_nclt_active(self, tmp_files):
        """🏦 Credit Expert: Active NCLT is a hard block signal."""
        w = LegalNoticeWorker(SESSION, tmp_files["legal_notice"])
        output = await w.process()
        risk = output.extracted_data["risk_classification"]
        assert "nclt_active" in risk
        # XYZ Steel has an active NCLT case
        assert risk["nclt_active"] is True

    async def test_w5_ar_disclosure_gap(self, tmp_files):
        """🏦 Credit Expert: Must flag cases not disclosed in Annual Report."""
        w = LegalNoticeWorker(SESSION, tmp_files["legal_notice"])
        output = await w.process()
        check = output.extracted_data["ar_disclosure_check"]
        assert check["cases_in_legal_docs"] > check["cases_disclosed_in_ar"]
        assert check["undisclosed_cases"] >= 1
        assert len(check["undisclosed_details"]) >= 1

    async def test_w5_total_contingent_liability(self, tmp_files):
        """🏦 Must calculate total exposure across all pending cases."""
        w = LegalNoticeWorker(SESSION, tmp_files["legal_notice"])
        output = await w.process()
        total = output.extracted_data["total_contingent_liability"]
        assert total["amount"] > 0
        assert total["unit"] == "lakhs"

    async def test_w5_handles_missing_file(self):
        """🧪 QA: Graceful failure on missing file."""
        w = LegalNoticeWorker("test-missing", "/nonexistent/legal.pdf")
        output = await w.process()
        assert output.status == "failed"
        assert len(output.errors) > 0


# ══════════════════════════════════════════════
# W6 — Board Minutes Worker Tests
# ══════════════════════════════════════════════

class TestW6BoardMinutesWorker:
    """🏦 Credit Expert: RPT concealment (board vs AR), governance signals.
    🔒 Security: No sensitive data exposure.
    🎯 Judge: Dramatic concealment finding — 2 RPTs worth ₹6.2cr hidden."""

    async def test_w6_completes_successfully(self, tmp_files):
        w = BoardMinutesWorker(SESSION, tmp_files["board_minutes"])
        output = await w.process()
        assert output.status == "completed"
        assert output.worker_id == "W6"
        assert output.confidence > 0.8

    async def test_w6_director_attendance(self, tmp_files):
        """🏦 Must track attendance per director with percentages."""
        w = BoardMinutesWorker(SESSION, tmp_files["board_minutes"])
        output = await w.process()
        attendance = output.extracted_data["director_attendance"]
        assert len(attendance) >= 3
        for d in attendance:
            assert "name" in d
            assert "attended" in d
            assert "total" in d
            assert "attendance_pct" in d
            assert 0 <= d["attendance_pct"] <= 100

    async def test_w6_rpt_concealment_detection(self, tmp_files):
        """🏦 Credit Expert: CRITICAL — board approved more RPTs than AR discloses."""
        w = BoardMinutesWorker(SESSION, tmp_files["board_minutes"])
        output = await w.process()
        concealment = output.extracted_data["rpt_concealment_check"]
        assert concealment["board_approved_count"] > concealment["ar_disclosed_count"]
        assert concealment["undisclosed_count"] >= 1
        assert concealment["undisclosed_amount"] > 0
        assert concealment["concealment_severity"] in ["HIGH", "CRITICAL"]

    async def test_w6_rpt_transactions_have_resolution_numbers(self, tmp_files):
        """🏦 Every RPT must trace to a board resolution number."""
        w = BoardMinutesWorker(SESSION, tmp_files["board_minutes"])
        output = await w.process()
        rpts = output.extracted_data["rpt_approvals"]["transactions"]
        for rpt in rpts:
            assert "resolution_no" in rpt, f"RPT '{rpt['party']}' missing resolution number"
            assert "disclosed_in_ar" in rpt, "Must track AR disclosure status per RPT"

    async def test_w6_borrowing_resolutions(self, tmp_files):
        """🏦 Must capture new borrowing approvals with lender and purpose."""
        w = BoardMinutesWorker(SESSION, tmp_files["board_minutes"])
        output = await w.process()
        borrowings = output.extracted_data["borrowing_resolutions"]
        assert len(borrowings) >= 1
        for b in borrowings:
            assert b["amount"] > 0
            assert "lender" in b
            assert "purpose" in b

    async def test_w6_risk_discussions(self, tmp_files):
        """🏦 Board risk discussions provide sentiment on company health."""
        w = BoardMinutesWorker(SESSION, tmp_files["board_minutes"])
        output = await w.process()
        risks = output.extracted_data["risk_discussions"]
        assert len(risks) >= 1
        for r in risks:
            assert "topic" in r
            assert "severity" in r
            assert r["severity"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    async def test_w6_handles_missing_file(self):
        """🧪 QA: Graceful failure."""
        w = BoardMinutesWorker("test-missing", "/nonexistent/minutes.pdf")
        output = await w.process()
        assert output.status == "failed"


# ══════════════════════════════════════════════
# W7 — Shareholding Pattern Worker Tests
# ══════════════════════════════════════════════

class TestW7ShareholdingWorker:
    """🏦 Credit Expert: Pledge delta (not just absolute), cross-holdings, dilution.
    🧪 QA: Boundary pledge values, percentage totals.
    🎯 Judge: HIGH PLEDGE ALERT is a dramatic demo moment."""

    async def test_w7_completes_successfully(self, tmp_files):
        w = ShareholdingWorker(SESSION, tmp_files["shareholding"])
        output = await w.process()
        assert output.status == "completed"
        assert output.worker_id == "W7"
        assert output.confidence > 0.8

    async def test_w7_promoter_holding_with_pledge(self, tmp_files):
        """🏦 Must extract promoter %, pledged %, and previous quarter for delta."""
        w = ShareholdingWorker(SESSION, tmp_files["shareholding"])
        output = await w.process()
        promo = output.extracted_data["promoter_holding"]
        assert "percentage" in promo
        assert promo["percentage"] > 0
        assert "pledged_pct" in promo
        assert "pledged_pct_previous_quarter" in promo
        assert "pledge_change" in promo

    async def test_w7_pledge_delta_analysis(self, tmp_files):
        """🏦 Credit Expert: Pledge INCREASE is worse than high absolute pledge.
        60% pledge is concerning; 60% pledge + 16% jump is critical."""
        w = ShareholdingWorker(SESSION, tmp_files["shareholding"])
        output = await w.process()
        promo = output.extracted_data["promoter_holding"]
        delta = promo["pledge_change"]
        assert delta > 0, "XYZ Steel has increasing pledge — must be positive delta"
        assert promo["pledge_trend"] == "increasing"

    async def test_w7_institutional_breakdown(self, tmp_files):
        """🏦 FII, DII, Insurance, Banks must be separately tracked."""
        w = ShareholdingWorker(SESSION, tmp_files["shareholding"])
        output = await w.process()
        inst = output.extracted_data["institutional_holding"]
        assert "fii" in inst
        assert "dii_mutual_funds" in inst
        assert "insurance" in inst
        assert "banks_fi" in inst
        total_inst = inst["total_institutional"]["pct"]
        assert total_inst > 0

    async def test_w7_cross_holdings_detected(self, tmp_files):
        """🏦 Credit Expert: Cross-holdings between group entities = circular risk."""
        w = ShareholdingWorker(SESSION, tmp_files["shareholding"])
        output = await w.process()
        cross = output.extracted_data["cross_holdings"]
        assert cross["detected"] is True
        assert len(cross["entities"]) >= 1
        entity = cross["entities"][0]
        assert "relationship" in entity
        assert "risk" in entity

    async def test_w7_quarterly_dilution_trend(self, tmp_files):
        """🏦 Declining promoter holding over quarters = potential exit signal."""
        w = ShareholdingWorker(SESSION, tmp_files["shareholding"])
        output = await w.process()
        trend = output.extracted_data["quarterly_trend"]
        assert trend["trend"] in ["declining", "stable", "increasing"]
        # Q1 should be >= Q4 for declining trend
        if trend["trend"] == "declining":
            assert trend["q1_fy23_promoter_pct"] >= trend["q4_fy23_promoter_pct"]

    async def test_w7_top_shareholders(self, tmp_files):
        """Must extract top 10 shareholders with category classification."""
        w = ShareholdingWorker(SESSION, tmp_files["shareholding"])
        output = await w.process()
        top10 = output.extracted_data["top_10_shareholders"]
        assert len(top10) >= 5
        for s in top10:
            assert "name" in s
            assert "pct" in s
            assert "category" in s

    async def test_w7_handles_missing_file(self):
        """🧪 QA: Graceful failure."""
        w = ShareholdingWorker("test-missing", "/nonexistent/shareholding.pdf")
        output = await w.process()
        assert output.status == "failed"


# ══════════════════════════════════════════════
# W8 — Rating Report Worker Tests
# ══════════════════════════════════════════════

class TestW8RatingReportWorker:
    """🏦 Credit Expert: Downgrade detection, outlook analysis, peer comparison.
    🧪 QA: Rating history ordering, date validity.
    🎯 Judge: Downgrade A- → BBB+ is a dramatic risk signal."""

    async def test_w8_completes_successfully(self, tmp_files):
        w = RatingReportWorker(SESSION, tmp_files["rating_report"])
        output = await w.process()
        assert output.status == "completed"
        assert output.worker_id == "W8"
        assert output.confidence > 0.8

    async def test_w8_current_rating_extraction(self, tmp_files):
        """🏦 Must extract rating, outlook, facility type with amounts."""
        w = RatingReportWorker(SESSION, tmp_files["rating_report"])
        output = await w.process()
        rating = output.extracted_data["current_rating"]
        assert "long_term" in rating
        assert rating["long_term"] in ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
                                         "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
                                         "B+", "B", "B-", "C", "D"]
        assert "outlook" in rating
        assert rating["outlook"] in ["Stable", "Positive", "Negative", "Watch"]
        assert rating["facility_amount"] > 0

    async def test_w8_downgrade_detection(self, tmp_files):
        """🏦 Credit Expert: Rating downgrade is a major risk signal."""
        w = RatingReportWorker(SESSION, tmp_files["rating_report"])
        output = await w.process()
        downgrade = output.extracted_data["downgrade_details"]
        assert downgrade["has_downgrade"] is True
        assert downgrade["from_rating"] != downgrade["to_rating"]
        assert len(downgrade["reasons"]) >= 1
        assert downgrade["notches"] >= 1

    async def test_w8_rating_history_chronological(self, tmp_files):
        """🧪 QA: Rating history must be ordered newest-first."""
        w = RatingReportWorker(SESSION, tmp_files["rating_report"])
        output = await w.process()
        history = output.extracted_data["rating_history"]
        assert len(history) >= 3
        dates = [h["date"] for h in history]
        # Should be descending (newest first)
        assert dates == sorted(dates, reverse=True), "Rating history must be newest-first"

    async def test_w8_watch_status(self, tmp_files):
        """🏦 Watch/review status affects credit assessment urgency."""
        w = RatingReportWorker(SESSION, tmp_files["rating_report"])
        output = await w.process()
        watch = output.extracted_data["watch_status"]
        assert "on_watch" in watch
        assert isinstance(watch["on_watch"], bool)

    async def test_w8_strengths_and_weaknesses(self, tmp_files):
        """🏦 Rating rationale provides key positive/negative signals."""
        w = RatingReportWorker(SESSION, tmp_files["rating_report"])
        output = await w.process()
        assert len(output.extracted_data["key_strengths"]) >= 2
        assert len(output.extracted_data["key_weaknesses"]) >= 2

    async def test_w8_peer_comparison(self, tmp_files):
        """🏦 Peer comparison helps contextualize the rating."""
        w = RatingReportWorker(SESSION, tmp_files["rating_report"])
        output = await w.process()
        peer = output.extracted_data["peer_comparison"]
        assert "industry_median_rating" in peer
        assert "peer_companies" in peer
        assert len(peer["peer_companies"]) >= 2

    async def test_w8_financial_indicators(self, tmp_files):
        """🏦 Rating report often has independent financial data for cross-check."""
        w = RatingReportWorker(SESSION, tmp_files["rating_report"])
        output = await w.process()
        fin = output.extracted_data["financial_indicators_from_rating"]
        assert fin["revenue_fy23"] > 0
        assert fin["debt_equity"] > 0
        assert fin["interest_coverage"] > 0

    async def test_w8_handles_missing_file(self):
        """🧪 QA: Graceful failure."""
        w = RatingReportWorker("test-missing", "/nonexistent/rating.pdf")
        output = await w.process()
        assert output.status == "failed"


# ══════════════════════════════════════════════
# FULL DISPATCH — All 8 Workers
# ══════════════════════════════════════════════

class TestFullWorkerDispatch:
    """⚙️ Systems Engineer: Full 8-document dispatch, no state leakage.
    🎯 Judge: All 8 document types process successfully in one cycle."""

    async def test_dispatch_all_8_workers(self, tmp_files):
        """Dispatch all 8 document types and verify all complete."""
        documents = [
            {"document_type": DocumentType.ANNUAL_REPORT, "file_path": tmp_files["annual_report"]},
            {"document_type": DocumentType.BANK_STATEMENT, "file_path": tmp_files["bank_statement"]},
            {"document_type": DocumentType.GST_RETURNS, "file_path": tmp_files["gst_returns"]},
            {"document_type": DocumentType.ITR, "file_path": tmp_files["itr"]},
            {"document_type": DocumentType.LEGAL_NOTICE, "file_path": tmp_files["legal_notice"]},
            {"document_type": DocumentType.BOARD_MINUTES, "file_path": tmp_files["board_minutes"]},
            {"document_type": DocumentType.SHAREHOLDING_PATTERN, "file_path": tmp_files["shareholding"]},
            {"document_type": DocumentType.RATING_REPORT, "file_path": tmp_files["rating_report"]},
        ]
        results = await dispatch_workers("test-full-dispatch", documents)
        assert len(results) == 8
        for wid in ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]:
            assert wid in results, f"Worker {wid} missing from results"
            assert results[wid].status == "completed", f"Worker {wid} status: {results[wid].status}"
            assert results[wid].confidence > 0.5

    async def test_dispatch_mixed_valid_and_missing(self, tmp_files):
        """⚙️ Some valid, some missing — must not crash, partial results OK."""
        documents = [
            {"document_type": DocumentType.ANNUAL_REPORT, "file_path": tmp_files["annual_report"]},
            {"document_type": DocumentType.ITR, "file_path": "/nonexistent/itr.pdf"},
            {"document_type": DocumentType.RATING_REPORT, "file_path": tmp_files["rating_report"]},
        ]
        results = await dispatch_workers("test-mixed", documents)
        assert results["W1"].status == "completed"
        assert results["W4"].status == "failed"
        assert results["W8"].status == "completed"

    async def test_dispatch_thinking_events_from_all_workers(self, tmp_files):
        """🎯 Judge: Every worker must emit events visible in chatbot."""
        documents = [
            {"document_type": DocumentType.ITR, "file_path": tmp_files["itr"]},
            {"document_type": DocumentType.LEGAL_NOTICE, "file_path": tmp_files["legal_notice"]},
            {"document_type": DocumentType.BOARD_MINUTES, "file_path": tmp_files["board_minutes"]},
            {"document_type": DocumentType.SHAREHOLDING_PATTERN, "file_path": tmp_files["shareholding"]},
            {"document_type": DocumentType.RATING_REPORT, "file_path": tmp_files["rating_report"]},
        ]
        sid = "test-events-all"
        await dispatch_workers(sid, documents)
        publisher = get_publisher()
        events = publisher.get_event_log(sid)
        # Each worker emits 5+ events → 25+ total
        assert len(events) >= 20, f"Expected 20+ events, got {len(events)}"

    async def test_dispatch_worker_outputs_staged_in_redis(self, tmp_files):
        """⚙️ All outputs must be staged in Redis for Consolidator."""
        documents = [
            {"document_type": DocumentType.ITR, "file_path": tmp_files["itr"]},
            {"document_type": DocumentType.LEGAL_NOTICE, "file_path": tmp_files["legal_notice"]},
            {"document_type": DocumentType.BOARD_MINUTES, "file_path": tmp_files["board_minutes"]},
            {"document_type": DocumentType.SHAREHOLDING_PATTERN, "file_path": tmp_files["shareholding"]},
            {"document_type": DocumentType.RATING_REPORT, "file_path": tmp_files["rating_report"]},
        ]
        sid = "test-staged"
        await dispatch_workers(sid, documents)
        redis = get_redis_client()
        staged = await redis.get_all_staged_outputs(sid)
        for wid in ["W4", "W5", "W6", "W7", "W8"]:
            assert wid in staged, f"Worker {wid} output not staged in Redis"
            assert staged[wid].get("status") == "completed"


# ══════════════════════════════════════════════
# WORKERS_NODE INTEGRATION — Full 8-Document Cycle
# ══════════════════════════════════════════════

class TestWorkersNodeIntegration:
    """⚙️ + 🎯 — Full pipeline integration: workers_node with all 8 docs."""

    async def test_workers_node_all_8_documents(self, tmp_files):
        """workers_node dispatches all 8 workers and returns correct structure."""
        from backend.graph.nodes.workers_node import workers_node

        state = CreditAppraisalState(
            session_id="test-node-8docs",
            company=CompanyInfo(
                name="XYZ Steel Industries Ltd",
                sector="Steel Manufacturing",
                loan_type="Working Capital",
                loan_amount="₹50,00,00,000",
                loan_amount_numeric=5000.0,
            ),
            documents=[
                DocumentMeta(filename="ar.pdf", document_type=DocumentType.ANNUAL_REPORT,
                             file_size=1024, file_path=tmp_files["annual_report"]),
                DocumentMeta(filename="bs.pdf", document_type=DocumentType.BANK_STATEMENT,
                             file_size=512, file_path=tmp_files["bank_statement"]),
                DocumentMeta(filename="gst.pdf", document_type=DocumentType.GST_RETURNS,
                             file_size=256, file_path=tmp_files["gst_returns"]),
                DocumentMeta(filename="itr.pdf", document_type=DocumentType.ITR,
                             file_size=384, file_path=tmp_files["itr"]),
                DocumentMeta(filename="legal.pdf", document_type=DocumentType.LEGAL_NOTICE,
                             file_size=192, file_path=tmp_files["legal_notice"]),
                DocumentMeta(filename="minutes.pdf", document_type=DocumentType.BOARD_MINUTES,
                             file_size=448, file_path=tmp_files["board_minutes"]),
                DocumentMeta(filename="share.pdf", document_type=DocumentType.SHAREHOLDING_PATTERN,
                             file_size=128, file_path=tmp_files["shareholding"]),
                DocumentMeta(filename="rating.pdf", document_type=DocumentType.RATING_REPORT,
                             file_size=320, file_path=tmp_files["rating_report"]),
            ],
            pipeline_stages=[
                PipelineStage(stage=PipelineStageEnum.WORKERS),
            ],
        )

        result = await workers_node(state)
        assert result["workers_completed"] == 8
        assert result["workers_total"] == 8
        assert len(result["worker_outputs"]) == 8

        # All worker statuses should be COMPLETED
        worker_statuses = result["workers"]
        assert len(worker_statuses) == 8
        all_completed = all(ws.status == WorkerStatusEnum.COMPLETED for ws in worker_statuses)
        assert all_completed, f"Not all completed: {[ws.status.value for ws in worker_statuses]}"

    async def test_workers_node_partial_documents(self, tmp_files):
        """⚙️ Pipeline works with fewer than 8 documents."""
        from backend.graph.nodes.workers_node import workers_node

        state = CreditAppraisalState(
            session_id="test-node-partial",
            company=CompanyInfo(
                name="Small Corp",
                sector="IT Services",
                loan_type="Term Loan",
                loan_amount="₹10,00,00,000",
                loan_amount_numeric=1000.0,
            ),
            documents=[
                DocumentMeta(filename="ar.pdf", document_type=DocumentType.ANNUAL_REPORT,
                             file_size=1024, file_path=tmp_files["annual_report"]),
                DocumentMeta(filename="itr.pdf", document_type=DocumentType.ITR,
                             file_size=384, file_path=tmp_files["itr"]),
            ],
            pipeline_stages=[
                PipelineStage(stage=PipelineStageEnum.WORKERS),
            ],
        )

        result = await workers_node(state)
        assert result["workers_completed"] == 2
        assert result["workers_total"] == 2


# ══════════════════════════════════════════════
# CROSS-VERIFICATION DATA READINESS
# ══════════════════════════════════════════════

class TestCrossVerificationReadiness:
    """🏦 Credit Expert: Revenue comparison across 4 sources must be possible."""

    async def test_all_revenue_sources_available(self, tmp_files):
        """4-way revenue cross-verification data available from W1, W2, W3, W4."""
        from backend.workers.w1_annual_report import AnnualReportWorker
        from backend.workers.w2_bank_statement import BankStatementWorker
        from backend.workers.w3_gst_returns import GSTReturnsWorker

        w1 = AnnualReportWorker("test-xver", tmp_files["annual_report"])
        w2 = BankStatementWorker("test-xver", tmp_files["bank_statement"])
        w3 = GSTReturnsWorker("test-xver", tmp_files["gst_returns"])
        w4 = ITRWorker("test-xver", tmp_files["itr"])

        o1 = await w1.process()
        o2 = await w2.process()
        o3 = await w3.process()
        o4 = await w4.process()

        # All 4 sources must provide revenue data
        ar_rev = o1.extracted_data["revenue"]["fy2023"]
        bank_rev = o2.extracted_data["revenue_from_bank"]["annual_credits"]
        gst_rev = o3.extracted_data["revenue_from_gst"]["annual_turnover"]
        itr_rev = o4.extracted_data["revenue_from_itr"]["turnover"]

        assert ar_rev > 0, "AR revenue must be positive"
        assert bank_rev > 0, "Bank credits must be positive"
        assert gst_rev > 0, "GST turnover must be positive"
        assert itr_rev > 0, "ITR turnover must be positive"

        # All in same unit (lakhs) for comparison
        assert o1.extracted_data["revenue"]["unit"] == "lakhs"
        assert o2.extracted_data["revenue_from_bank"]["unit"] == "lakhs"
        assert o3.extracted_data["revenue_from_gst"]["unit"] == "lakhs"
        assert o4.extracted_data["revenue_from_itr"]["unit"] == "lakhs"

    async def test_rpt_cross_check_data_available(self, tmp_files):
        """🏦 RPT count: Board Minutes vs AR must be comparable."""
        from backend.workers.w1_annual_report import AnnualReportWorker

        w1 = AnnualReportWorker("test-rpt", tmp_files["annual_report"])
        w6 = BoardMinutesWorker("test-rpt", tmp_files["board_minutes"])

        o1 = await w1.process()
        o6 = await w6.process()

        ar_rpt_count = o1.extracted_data["rpts"]["count"]
        board_rpt_count = o6.extracted_data["rpt_approvals"]["count"]

        assert ar_rpt_count > 0
        assert board_rpt_count > 0
        # Board should have >= AR disclosed (concealment = board > AR)
        assert board_rpt_count >= ar_rpt_count
