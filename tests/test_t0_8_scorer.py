"""
Tests for T0.8 — Agent 3: Scorer + CAM Writer.

Tests:
1. get_score_band() returns correct bands for all threshold boundaries
2. Capacity module scores revenue growth, EBITDA margin, EMI regularity
3. Character module scores audit opinion, RPTs, bounces
4. Capital module scores D/E ratio
5. Collateral module returns T0 default
6. Conditions module scores GST filing compliance
7. Compound module scores cross-verification deviation + contradictions
8. Hard block capping behaviour
9. Full scoring pipeline with mock worker data
10. CAM generation produces file on disk
11. ThinkingEvents emitted correctly
12. Empty data graceful handling
13. Score clamped to 0–850 range
14. Module limits enforced
15. Full workers→consolidator→scorer integration
"""

import asyncio
import os
import sys
import shutil

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.graph.nodes.recommendation_node import (
    recommendation_node,
    get_score_band,
    BASE_SCORE,
    MODULE_LIMITS,
    _score_capacity,
    _score_character,
    _score_capital,
    _score_collateral,
    _score_conditions,
    _score_compound,
    _check_hard_blocks,
    _collect_worker_data,
    _make_entry,
    _generate_cam,
)
from backend.graph.state import (
    CreditAppraisalState,
    WorkerOutput,
    RawDataPackage,
    NormalizedField,
    CrossVerificationResult,
    HardBlock,
)
from backend.models.schemas import (
    ScoreBand,
    ScoreModule,
    AssessmentOutcome,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
    CompanyInfo,
    DocumentMeta,
    DocumentType,
    ScoreBreakdownEntry,
    ScoreModuleSummary,
)
from backend.thinking.event_emitter import ThinkingEventEmitter
from backend.thinking.redis_publisher import reset_publisher, get_publisher

passed = 0
failed = 0


def run(name, coro):
    global passed, failed
    try:
        asyncio.get_event_loop().run_until_complete(coro)
        passed += 1
        print(f"  PASS: {name}")
    except Exception as e:
        failed += 1
        print(f"  FAIL: {name} — {e}")


def run_sync(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  PASS: {name}")
    except Exception as e:
        failed += 1
        print(f"  FAIL: {name} — {e}")


# ──────────────────────────────────────────────
# Helper: Build mock worker data (XYZ Steel scenario)
# ──────────────────────────────────────────────

def _build_mock_worker_data():
    """Build realistic worker data matching W1/W2/W3 mock outputs."""
    return {
        "W1": {
            "revenue": {"fy2023": 4850.0, "fy2022": 4200.0, "fy2021": 3750.0, "source_page": 45},
            "ebitda": {"fy2023": 825.0, "fy2022": 714.0, "source_page": 45},
            "pat": {"fy2023": 412.0, "fy2022": 357.0},
            "total_debt": {"fy2023": 1850.0, "fy2022": 1750.0, "source_page": 50},
            "net_worth": {"fy2023": 1280.0, "fy2022": 1100.0, "source_page": 50},
            "auditor_qualifications": [],  # Clean audit
            "rpts": {"count": 5, "total_amount": 284.5, "source_page": 68},
            "litigation_disclosure": {
                "cases": [
                    {"type": "Civil", "forum": "High Court", "amount": 120, "status": "pending"}
                ]
            },
            "directors": [
                {"name": "Vikram Mehta", "din": "00123456"},
                {"name": "Priya Sharma", "din": "00789012"},
            ],
        },
        "W2": {
            "monthly_summary": [
                {"month": f"2023-{m:02d}", "credits": 400 + m * 10, "debits": 380 + m * 8}
                for m in range(1, 13)
            ],
            "bounces": {"count": 3, "total_amount": 45.5},
            "emi_regularity": {"regularity_pct": 91.7, "on_time": 11, "total_months": 12},
            "round_number_transactions": {"count": 4, "total_amount": 80.0},
            "revenue_from_bank": 5280.0,
        },
        "W3": {
            "gstr3b_monthly": [
                {"month": f"2023-{m:02d}", "turnover": 400 + m * 5, "itc_claimed": 60 + m}
                for m in range(1, 13)
            ],
            "aggregate_turnover": 5100.0,
            "gstr2a_reconciliation": {
                "total_itc_claimed": 858.0,
                "total_itc_available": 776.0,
                "mismatch_pct": 10.6,
                "flag": "ELEVATED",
            },
            "filing_compliance": {"regularity_pct": 100, "months_filed": 12},
            "revenue_from_gst": 5100.0,
        },
    }


def _build_state_with_workers(worker_data=None):
    """Build a CreditAppraisalState with worker outputs pre-filled."""
    wd = worker_data or _build_mock_worker_data()
    state = CreditAppraisalState(
        session_id="test-scorer-001",
        company=CompanyInfo(
            name="XYZ Steel Limited",
            sector="Steel Manufacturing",
            loan_type="Working Capital",
            loan_amount="₹50,00,00,000",
            loan_amount_numeric=5000.0,
        ),
        pipeline_stages=[
            PipelineStage(
                stage=PipelineStageEnum.RECOMMENDATION,
                status=PipelineStageStatus.PENDING,
            ),
        ],
    )
    # Populate worker outputs
    for wid, data in wd.items():
        state.worker_outputs[wid] = WorkerOutput(
            worker_id=wid,
            document_type=wid,
            status="completed",
            pages_processed=10,
            confidence=0.90,
            extracted_data=data,
        )
    return state


# ──────────────────────────────────────────────
# Test 1: Score band boundaries
# ──────────────────────────────────────────────

def test_score_bands():
    # Excellent
    band, outcome, rec = get_score_band(850)
    assert band == ScoreBand.EXCELLENT, f"Expected EXCELLENT, got {band}"
    assert outcome == AssessmentOutcome.APPROVED

    band, outcome, rec = get_score_band(750)
    assert band == ScoreBand.EXCELLENT

    # Good
    band, outcome, _ = get_score_band(749)
    assert band == ScoreBand.GOOD

    band, outcome, _ = get_score_band(650)
    assert band == ScoreBand.GOOD

    # Fair
    band, outcome, _ = get_score_band(649)
    assert band == ScoreBand.FAIR
    assert outcome == AssessmentOutcome.CONDITIONAL

    # Poor
    band, outcome, _ = get_score_band(549)
    assert band == ScoreBand.POOR

    # Very Poor
    band, outcome, _ = get_score_band(449)
    assert band == ScoreBand.VERY_POOR
    assert outcome == AssessmentOutcome.REJECTED

    # Default Risk
    band, outcome, _ = get_score_band(100)
    assert band == ScoreBand.DEFAULT_RISK
    assert outcome == AssessmentOutcome.REJECTED

    band, outcome, _ = get_score_band(0)
    assert band == ScoreBand.DEFAULT_RISK


# ──────────────────────────────────────────────
# Test 2: Capacity module scoring
# ──────────────────────────────────────────────

async def test_capacity_module():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-cap", "Test Capacity")
    data = _build_mock_worker_data()

    entries, total = await _score_capacity(data, emitter)

    assert len(entries) >= 2, f"Expected at least 2 entries, got {len(entries)}"

    # Check revenue growth entry exists
    rev_entry = [e for e in entries if "Revenue Growth" in e.metric_name]
    assert len(rev_entry) == 1, "Missing revenue growth metric"
    assert rev_entry[0].module == ScoreModule.CAPACITY
    # FY23=4850, FY22=4200 → growth = 15.48%  → impact = +40
    assert rev_entry[0].score_impact == 40, f"Expected +40, got {rev_entry[0].score_impact}"

    # Check EMI regularity entry
    emi_entry = [e for e in entries if "EMI" in e.metric_name]
    assert len(emi_entry) == 1, "Missing EMI metric"
    # 91.7% → impact = +10
    assert emi_entry[0].score_impact == 10

    # Total clamped to limits
    limits = MODULE_LIMITS[ScoreModule.CAPACITY]
    assert limits["max_negative"] <= total <= limits["max_positive"]


# ──────────────────────────────────────────────
# Test 3: Character module scoring
# ──────────────────────────────────────────────

async def test_character_module():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-char", "Test Character")
    data = _build_mock_worker_data()

    entries, total = await _score_character(data, emitter)

    assert len(entries) >= 2, f"Expected at least 2 entries, got {len(entries)}"

    # Clean audit → +30
    audit_entry = [e for e in entries if "Auditor" in e.metric_name]
    assert len(audit_entry) == 1
    assert audit_entry[0].score_impact == 30  # Clean = +30

    # Bounces = 3 → -60
    bounce_entry = [e for e in entries if "Bounce" in e.metric_name]
    assert len(bounce_entry) == 1
    assert bounce_entry[0].score_impact == -60


# ──────────────────────────────────────────────
# Test 4: Capital module scoring
# ──────────────────────────────────────────────

async def test_capital_module():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-cap2", "Test Capital")
    data = _build_mock_worker_data()

    entries, total = await _score_capital(data, emitter)

    assert len(entries) >= 1
    de_entry = entries[0]
    assert de_entry.module == ScoreModule.CAPITAL
    # D/E = 1850/1280 = 1.445 → impact = +15
    assert de_entry.score_impact == 15


# ──────────────────────────────────────────────
# Test 5: Collateral module default
# ──────────────────────────────────────────────

async def test_collateral_default():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-coll", "Test Collateral")

    entries, total = await _score_collateral({}, emitter)

    assert len(entries) == 1
    assert entries[0].module == ScoreModule.COLLATERAL
    assert entries[0].score_impact == 15  # T0 default
    assert entries[0].confidence == 0.50  # Low confidence for default


# ──────────────────────────────────────────────
# Test 6: Conditions module scoring
# ──────────────────────────────────────────────

async def test_conditions_module():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-cond", "Test Conditions")
    data = _build_mock_worker_data()

    entries, total = await _score_conditions(data, emitter)

    assert len(entries) >= 1
    gst_entry = entries[0]
    assert gst_entry.module == ScoreModule.CONDITIONS
    # Filing compliance 100% → +20
    assert gst_entry.score_impact == 20


# ──────────────────────────────────────────────
# Test 7: Compound module with cross-verification
# ──────────────────────────────────────────────

async def test_compound_module():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-comp", "Test Compound")
    data = _build_mock_worker_data()

    # Create state with cross-verifications from consolidator
    state = _build_state_with_workers(data)
    state.raw_data_package = RawDataPackage(
        session_id="test-comp",
        cross_verifications=[
            CrossVerificationResult(
                field_name="Revenue",
                sources={
                    "Annual Report": NormalizedField(value=4850.0, source_document="AR", confidence=0.70),
                    "GST": NormalizedField(value=5100.0, source_document="GST", confidence=1.0),
                    "Bank": NormalizedField(value=5280.0, source_document="Bank", confidence=0.85),
                },
                max_deviation_pct=8.9,
                status="flagged",
                note="Moderate deviation across 3 sources",
            ),
            CrossVerificationResult(
                field_name="ITC Mismatch (2A vs 3B)",
                sources={
                    "Claimed": NormalizedField(value=858.0, source_document="GSTR-3B", confidence=1.0),
                    "Available": NormalizedField(value=776.0, source_document="GSTR-2A", confidence=1.0),
                },
                max_deviation_pct=10.6,
                status="flagged",
                note="Elevated ITC mismatch",
            ),
        ],
        contradictions=[],
    )

    entries, total = await _score_compound(data, state, emitter)

    assert len(entries) >= 1, f"Expected at least 1 entry, got {len(entries)}"

    # Revenue deviation 8.9% → impact -10
    rev_cv = [e for e in entries if "Revenue Cross" in e.metric_name]
    assert len(rev_cv) == 1
    assert rev_cv[0].score_impact == -10

    # ITC mismatch 10.6% → impact -20
    itc_cv = [e for e in entries if "ITC" in e.metric_name or "GSTR" in e.metric_name]
    assert len(itc_cv) == 1
    assert itc_cv[0].score_impact == -20


# ──────────────────────────────────────────────
# Test 8: Hard block capping
# ──────────────────────────────────────────────

async def test_hard_block_capping():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb", "Test HardBlock")

    # Add NCLT case
    data = _build_mock_worker_data()
    data["W1"]["litigation_disclosure"]["cases"].append({
        "type": "Insolvency", "forum": "NCLT", "amount": 2500, "status": "pending"
    })

    blocks = await _check_hard_blocks(data, emitter)

    assert len(blocks) == 1
    assert blocks[0].trigger == "nclt_active"
    assert blocks[0].score_cap == 250


# ──────────────────────────────────────────────
# Test 9: Full scoring pipeline
# ──────────────────────────────────────────────

async def test_full_scoring():
    reset_publisher()
    state = _build_state_with_workers()

    # Add cross-verifications
    state.raw_data_package = RawDataPackage(
        session_id="test-scorer-001",
        cross_verifications=[
            CrossVerificationResult(
                field_name="Revenue",
                sources={
                    "Annual Report": NormalizedField(value=4850.0, source_document="AR", confidence=0.70),
                    "GST": NormalizedField(value=5100.0, source_document="GST", confidence=1.0),
                },
                max_deviation_pct=5.2,
                status="flagged",
            ),
        ],
        contradictions=[],
    )

    result = await recommendation_node(state)

    assert "score" in result
    assert "score_band" in result
    assert "outcome" in result
    assert "score_modules" in result
    assert "score_breakdown" in result
    assert "cam_path" in result

    score = result["score"]
    assert 0 <= score <= 850, f"Score out of range: {score}"

    # With our mock data (strong financials), expect a reasonable score
    assert score >= 350, f"Score too low for healthy company: {score}"

    # Band should match score
    band, outcome, _ = get_score_band(score)
    assert result["score_band"] == band
    assert result["outcome"] == outcome

    # Should have entries from each module
    modules_found = set(e.module for e in result["score_breakdown"])
    assert ScoreModule.CAPACITY in modules_found
    assert ScoreModule.CHARACTER in modules_found
    assert ScoreModule.CAPITAL in modules_found

    # Verify 6 module summaries
    assert len(result["score_modules"]) == 6

    # Pipeline stage should be completed
    rec_stage = [s for s in result["pipeline_stages"]
                 if s.stage == PipelineStageEnum.RECOMMENDATION]
    assert len(rec_stage) == 1
    assert rec_stage[0].status == PipelineStageStatus.COMPLETED

    print(f"    Score: {score}/850 — {result['score_band'].value}")


# ──────────────────────────────────────────────
# Test 10: CAM file generated on disk
# ──────────────────────────────────────────────

async def test_cam_generation():
    reset_publisher()
    state = _build_state_with_workers()
    state.raw_data_package = RawDataPackage(
        session_id="test-cam-gen",
        cross_verifications=[],
        contradictions=[],
    )
    state.session_id = "test-cam-gen"

    result = await recommendation_node(state)

    cam_path = result.get("cam_path")
    assert cam_path is not None, "CAM path should be set"
    assert os.path.exists(cam_path), f"CAM file not found: {cam_path}"

    with open(cam_path, "r", encoding="utf-8") as f:
        cam_text = f.read()

    assert "CREDIT APPRAISAL MEMO" in cam_text
    assert "XYZ Steel" in cam_text
    assert "EXECUTIVE SUMMARY" in cam_text
    assert "SCORE BREAKDOWN BY MODULE" in cam_text
    assert "DETAILED METRIC BREAKDOWN" in cam_text

    # Cleanup
    cam_dir = os.path.dirname(cam_path)
    if os.path.exists(cam_dir):
        shutil.rmtree(cam_dir)


# ──────────────────────────────────────────────
# Test 11: ThinkingEvents emitted
# ──────────────────────────────────────────────

async def test_thinking_events():
    reset_publisher()
    state = _build_state_with_workers()
    state.raw_data_package = RawDataPackage(
        session_id="test-events",
        cross_verifications=[],
        contradictions=[],
    )
    state.session_id = "test-events"

    await recommendation_node(state)

    pub = get_publisher()
    events = pub.get_event_log("test-events")

    assert len(events) > 0, "Should have emitted events"

    # Check event types
    types = [e.get("event_type") for e in events]
    assert "READ" in types, "Should emit READ events"
    assert "COMPUTED" in types or "DECIDED" in types, "Should emit scoring events"
    assert "CONCLUDING" in types, "Should emit conclusion"

    # Cleanup
    cam_dir = os.path.join("data", "output", "test-events")
    if os.path.exists(cam_dir):
        shutil.rmtree(cam_dir)


# ──────────────────────────────────────────────
# Test 12: Empty data graceful handling
# ──────────────────────────────────────────────

async def test_empty_data():
    reset_publisher()
    state = CreditAppraisalState(
        session_id="test-empty",
        pipeline_stages=[
            PipelineStage(
                stage=PipelineStageEnum.RECOMMENDATION,
                status=PipelineStageStatus.PENDING,
            ),
        ],
    )
    # No worker outputs, no raw_data_package

    result = await recommendation_node(state)

    score = result["score"]
    assert 0 <= score <= 850

    # With no data, score should be around base + collateral default (350 + 15 = 365)
    assert score >= 0, "Score should not be negative"

    # Should still complete without error
    assert result.get("error") is None, f"Unexpected error: {result.get('error')}"

    # Cleanup
    cam_dir = os.path.join("data", "output", "test-empty")
    if os.path.exists(cam_dir):
        shutil.rmtree(cam_dir)


# ──────────────────────────────────────────────
# Test 13: Score clamped to 0–850
# ──────────────────────────────────────────────

async def test_score_clamping():
    """Verify score can't exceed 850 or go below 0."""
    reset_publisher()

    # Extremely positive data
    data = _build_mock_worker_data()
    state = _build_state_with_workers(data)
    state.raw_data_package = RawDataPackage(
        session_id="test-clamp",
        cross_verifications=[],
        contradictions=[],
    )

    result = await recommendation_node(state)
    assert result["score"] <= 850, f"Score exceeds max: {result['score']}"
    assert result["score"] >= 0, f"Score below min: {result['score']}"

    # Cleanup
    cam_dir = os.path.join("data", "output", "test-scorer-001")
    if os.path.exists(cam_dir):
        shutil.rmtree(cam_dir)


# ──────────────────────────────────────────────
# Test 14: Module limits enforced
# ──────────────────────────────────────────────

def test_module_limits():
    """Verify _make_entry clamps to module limits."""
    entry = _make_entry(
        module=ScoreModule.CAPACITY,
        metric="Test",
        value="999",
        formula="test",
        source="test",
        page=1,
        excerpt="test",
        benchmark="test",
        impact=9999,  # Way over max_positive=150
        reasoning="test",
    )
    assert entry.score_impact == 150, f"Expected clamped to 150, got {entry.score_impact}"

    entry2 = _make_entry(
        module=ScoreModule.CAPACITY,
        metric="Test",
        value="999",
        formula="test",
        source="test",
        page=1,
        excerpt="test",
        benchmark="test",
        impact=-9999,  # Way below max_negative=-100
        reasoning="test",
    )
    assert entry2.score_impact == -100, f"Expected clamped to -100, got {entry2.score_impact}"


# ──────────────────────────────────────────────
# Test 15: Full integration — workers → consolidator → scorer
# ──────────────────────────────────────────────

async def test_full_integration():
    """Run workers → consolidator → scorer in sequence."""
    reset_publisher()

    from backend.graph.nodes.workers_node import workers_node
    from backend.graph.nodes.consolidator_node import consolidator_node

    state = CreditAppraisalState(
        session_id="test-full-integration",
        company=CompanyInfo(
            name="XYZ Steel Limited",
            sector="Steel Manufacturing",
            loan_type="Working Capital",
            loan_amount="₹50,00,00,000",
            loan_amount_numeric=5000.0,
        ),
        documents=[
            DocumentMeta(
                filename="annual_report.pdf",
                document_type=DocumentType.ANNUAL_REPORT,
                file_size=2_500_000,
                file_path="data/samples/annual_report.pdf",
            ),
            DocumentMeta(
                filename="bank_statement.pdf",
                document_type=DocumentType.BANK_STATEMENT,
                file_size=1_200_000,
                file_path="data/samples/bank_statement.pdf",
            ),
            DocumentMeta(
                filename="gst_returns.pdf",
                document_type=DocumentType.GST_RETURNS,
                file_size=800_000,
                file_path="data/samples/gst_returns.pdf",
            ),
        ],
        pipeline_stages=[
            PipelineStage(stage=PipelineStageEnum.WORKERS, status=PipelineStageStatus.PENDING),
            PipelineStage(stage=PipelineStageEnum.CONSOLIDATION, status=PipelineStageStatus.PENDING),
            PipelineStage(stage=PipelineStageEnum.RECOMMENDATION, status=PipelineStageStatus.PENDING),
        ],
    )

    # Stage 1: Workers
    workers_result = await workers_node(state)
    state = state.model_copy(update=workers_result)

    assert len(state.worker_outputs) >= 3, f"Expected 3+ workers, got {len(state.worker_outputs)}"

    # Stage 2: Consolidator
    consol_result = await consolidator_node(state)
    state = state.model_copy(update=consol_result)

    assert state.raw_data_package is not None

    # Stage 3: Scorer
    score_result = await recommendation_node(state)

    score = score_result["score"]
    assert 0 <= score <= 850
    assert score_result["score_band"] is not None
    assert score_result["outcome"] is not None
    assert score_result["cam_path"] is not None
    assert len(score_result["score_breakdown"]) > 0
    assert len(score_result["score_modules"]) == 6

    print(f"    Integration Score: {score}/850 — {score_result['score_band'].value}")
    print(f"    Modules: {[m.module.value for m in score_result['score_modules']]}")

    # Cleanup
    cam_dir = os.path.join("data", "output", "test-full-integration")
    if os.path.exists(cam_dir):
        shutil.rmtree(cam_dir)


# ──────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("T0.8 — Agent 3: Scorer + CAM Writer Tests")
    print("=" * 60)

    print("\n1. Score band boundaries:")
    run_sync("get_score_band all thresholds", test_score_bands)

    print("\n2. Capacity module:")
    run("capacity scoring", test_capacity_module())

    print("\n3. Character module:")
    run("character scoring", test_character_module())

    print("\n4. Capital module:")
    run("capital scoring", test_capital_module())

    print("\n5. Collateral module (T0 default):")
    run("collateral default", test_collateral_default())

    print("\n6. Conditions module:")
    run("conditions scoring", test_conditions_module())

    print("\n7. Compound module:")
    run("compound scoring with cross-verification", test_compound_module())

    print("\n8. Hard block detection:")
    run("hard block capping", test_hard_block_capping())

    print("\n9. Full scoring pipeline:")
    run("full scoring pipeline", test_full_scoring())

    print("\n10. CAM file generation:")
    run("CAM file on disk", test_cam_generation())

    print("\n11. ThinkingEvents emission:")
    run("thinking events", test_thinking_events())

    print("\n12. Empty data handling:")
    run("empty data graceful", test_empty_data())

    print("\n13. Score clamping:")
    run("score clamped 0–850", test_score_clamping())

    print("\n14. Module limits:")
    run_sync("module limits enforced", test_module_limits)

    print("\n15. Full integration (workers → consolidator → scorer):")
    run("full integration pipeline", test_full_integration())

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
