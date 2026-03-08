"""
Tests for T2.1 — Enhanced Score Modules.

Tests the NEW metrics added to each module:
  CAPACITY:   DSCR scoring
  CAPITAL:    Net Worth Adequacy, Interest Coverage Ratio
  COLLATERAL: Promoter Holding %, Promoter Pledge % (replaces stub)
  CONDITIONS: Rating Outlook

Tests:
1.  DSCR strong (≥2.0x) → +40
2.  DSCR good (1.5-2.0x) → +25
3.  DSCR adequate (1.2-1.5x) → +10
4.  DSCR thin (1.0-1.2x) → -10
5.  DSCR deficit (<1.0x) → -50
6.  DSCR missing data → no entry
7.  Net Worth Adequacy strong (≥1.5x) → +25
8.  Net Worth Adequacy weak (<0.5x) → -30
9.  Net Worth Adequacy without state → skipped
10. Interest Coverage strong (≥4.0x) → +20
11. Interest Coverage weak (<1.5x) → -25
12. Capital module all 3 metrics together
13. Collateral with W7 data — promoter holding + pledge
14. Collateral high pledge (>30%) → -25
15. Collateral no pledge (0%) → +20
16. Collateral no W7 data → default fallback
17. Conditions with rating outlook positive → +20
18. Conditions with rating outlook negative → -15
19. Conditions with rating outlook stable → +10
20. Conditions no rating data → only GST metric
21. Full pipeline with all enhanced data
22. Enhanced modules backward compatible (no state)
23. Module limits still enforced with new metrics
24. DSCR + Revenue + EBITDA + EMI all score in capacity
"""

import asyncio
import os
import sys
import shutil

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
    _make_entry,
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
from backend.thinking.redis_publisher import reset_publisher


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _build_full_worker_data():
    """Build realistic worker data with ALL document types including W7, W8."""
    return {
        "W1": {
            "revenue": {"fy2023": 4850.0, "fy2022": 4200.0, "fy2021": 3750.0, "source_page": 45},
            "ebitda": {"fy2023": 825.0, "fy2022": 714.0, "source_page": 45},
            "pat": {"fy2023": 412.0, "fy2022": 357.0},
            "total_debt": {"fy2023": 1850.0, "fy2022": 1750.0, "source_page": 50},
            "net_worth": {"fy2023": 1280.0, "fy2022": 1100.0, "source_page": 50},
            "interest_expense": {"fy2023": 195.0, "source_page": 46},
            "auditor_qualifications": [],
            "rpts": {"count": 3, "total_amount": 150.0, "source_page": 68},
            "litigation_disclosure": {"cases": []},
            "directors": [
                {"name": "Vikram Mehta", "din": "00123456"},
            ],
        },
        "W2": {
            "monthly_summary": [
                {"month": f"2023-{m:02d}", "credits": 400 + m * 10, "debits": 380 + m * 8}
                for m in range(1, 13)
            ],
            "bounces": {"count": 0, "total_amount": 0},
            "emi_regularity": {"regularity_pct": 96.0, "on_time": 11.5, "total_months": 12},
            "revenue_from_bank": 5280.0,
        },
        "W3": {
            "gstr3b_monthly": [],
            "aggregate_turnover": 5100.0,
            "filing_compliance": {"regularity_pct": 100, "months_filed": 12},
            "revenue_from_gst": 5100.0,
        },
        "W7": {
            "promoter_holding_pct": 62.5,
            "promoter_pledge_pct": 8.0,
            "institutional_holding_pct": 22.0,
            "source_page": 1,
        },
        "W8": {
            "current_rating": "BBB+",
            "outlook": "Stable",
            "rating_agency": "CARE",
            "source_page": 1,
        },
    }


def _build_state_with_data(worker_data=None, loan_amount=5000.0):
    """Build a CreditAppraisalState with worker outputs and company info."""
    wd = worker_data or _build_full_worker_data()
    state = CreditAppraisalState(
        session_id="test-t2-1",
        company=CompanyInfo(
            name="XYZ Steel Limited",
            sector="Steel Manufacturing",
            loan_type="Working Capital",
            loan_amount="₹50,00,00,000",
            loan_amount_numeric=loan_amount,
        ),
        pipeline_stages=[
            PipelineStage(
                stage=PipelineStageEnum.RECOMMENDATION,
                status=PipelineStageStatus.PENDING,
            ),
        ],
    )
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
# Test 1: DSCR strong (≥2.0x) → +40
# ──────────────────────────────────────────────

async def test_dscr_strong():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-dscr-strong", "DSCR Strong")
    data = _build_full_worker_data()
    # EBITDA=825, Interest=195 → DSCR=4.23x → +40
    entries, total = await _score_capacity(data, emitter)

    dscr_entries = [e for e in entries if e.metric_name == "DSCR"]
    assert len(dscr_entries) == 1, f"Expected 1 DSCR entry, got {len(dscr_entries)}"
    assert dscr_entries[0].score_impact == 40, f"DSCR 4.23x should be +40, got {dscr_entries[0].score_impact}"
    assert "4.23" in dscr_entries[0].metric_value


# ──────────────────────────────────────────────
# Test 2: DSCR good (1.5-2.0x) → +25
# ──────────────────────────────────────────────

async def test_dscr_good():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-dscr-good", "DSCR Good")
    data = _build_full_worker_data()
    # Set interest so DSCR ≈ 1.7x: EBITDA=825, Interest=825/1.7≈485
    data["W1"]["interest_expense"]["fy2023"] = 485.0
    entries, total = await _score_capacity(data, emitter)

    dscr_entries = [e for e in entries if e.metric_name == "DSCR"]
    assert len(dscr_entries) == 1
    assert dscr_entries[0].score_impact == 25


# ──────────────────────────────────────────────
# Test 3: DSCR adequate (1.2-1.5x) → +10
# ──────────────────────────────────────────────

async def test_dscr_adequate():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-dscr-adeq", "DSCR Adequate")
    data = _build_full_worker_data()
    # DSCR ≈ 1.3x: EBITDA=825, Interest=825/1.3≈635
    data["W1"]["interest_expense"]["fy2023"] = 635.0
    entries, total = await _score_capacity(data, emitter)

    dscr_entries = [e for e in entries if e.metric_name == "DSCR"]
    assert len(dscr_entries) == 1
    assert dscr_entries[0].score_impact == 10


# ──────────────────────────────────────────────
# Test 4: DSCR thin (1.0-1.2x) → -10
# ──────────────────────────────────────────────

async def test_dscr_thin():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-dscr-thin", "DSCR Thin")
    data = _build_full_worker_data()
    # DSCR ≈ 1.1x: EBITDA=825, Interest=825/1.1≈750
    data["W1"]["interest_expense"]["fy2023"] = 750.0
    entries, total = await _score_capacity(data, emitter)

    dscr_entries = [e for e in entries if e.metric_name == "DSCR"]
    assert len(dscr_entries) == 1
    assert dscr_entries[0].score_impact == -10


# ──────────────────────────────────────────────
# Test 5: DSCR deficit (<1.0x) → -50
# ──────────────────────────────────────────────

async def test_dscr_deficit():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-dscr-def", "DSCR Deficit")
    data = _build_full_worker_data()
    # DSCR ≈ 0.8x: EBITDA=825, Interest=825/0.8≈1031
    data["W1"]["interest_expense"]["fy2023"] = 1031.0
    entries, total = await _score_capacity(data, emitter)

    dscr_entries = [e for e in entries if e.metric_name == "DSCR"]
    assert len(dscr_entries) == 1
    assert dscr_entries[0].score_impact == -50


# ──────────────────────────────────────────────
# Test 6: DSCR missing data → no entry
# ──────────────────────────────────────────────

async def test_dscr_missing():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-dscr-miss", "DSCR Missing")
    data = _build_full_worker_data()
    del data["W1"]["interest_expense"]
    entries, total = await _score_capacity(data, emitter)

    dscr_entries = [e for e in entries if e.metric_name == "DSCR"]
    assert len(dscr_entries) == 0, "DSCR should not be scored when interest_expense missing"


# ──────────────────────────────────────────────
# Test 7: Net Worth Adequacy strong (≥1.5x) → +25
# ──────────────────────────────────────────────

async def test_nw_adequacy_strong():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-nwa-strong", "NWA Strong")
    data = _build_full_worker_data()
    # NW=1280, Loan=500 → coverage=2.56x → +25
    state = _build_state_with_data(data, loan_amount=500.0)
    entries, total = await _score_capital(data, emitter, state)

    nwa = [e for e in entries if "Net Worth Adequacy" in e.metric_name]
    assert len(nwa) == 1
    assert nwa[0].score_impact == 25


# ──────────────────────────────────────────────
# Test 8: Net Worth Adequacy weak (<0.5x) → -30
# ──────────────────────────────────────────────

async def test_nw_adequacy_weak():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-nwa-weak", "NWA Weak")
    data = _build_full_worker_data()
    # NW=1280, Loan=10000 → coverage=0.128x → -30
    state = _build_state_with_data(data, loan_amount=10000.0)
    entries, total = await _score_capital(data, emitter, state)

    nwa = [e for e in entries if "Net Worth Adequacy" in e.metric_name]
    assert len(nwa) == 1
    assert nwa[0].score_impact == -30


# ──────────────────────────────────────────────
# Test 9: Net Worth Adequacy without state → skipped
# ──────────────────────────────────────────────

async def test_nw_adequacy_no_state():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-nwa-nostate", "NWA No State")
    data = _build_full_worker_data()
    # No state passed — NWA should be skipped, only D/E and ICR scored
    entries, total = await _score_capital(data, emitter)

    nwa = [e for e in entries if "Net Worth Adequacy" in e.metric_name]
    assert len(nwa) == 0, "NWA should not be scored when state is None"


# ──────────────────────────────────────────────
# Test 10: Interest Coverage strong (≥4.0x) → +20
# ──────────────────────────────────────────────

async def test_icr_strong():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-icr-strong", "ICR Strong")
    data = _build_full_worker_data()
    # EBITDA=825, Interest=195 → ICR=4.23x → +20
    entries, total = await _score_capital(data, emitter)

    icr = [e for e in entries if "Interest Coverage" in e.metric_name]
    assert len(icr) == 1
    assert icr[0].score_impact == 20


# ──────────────────────────────────────────────
# Test 11: Interest Coverage weak (<1.5x) → -25
# ──────────────────────────────────────────────

async def test_icr_weak():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-icr-weak", "ICR Weak")
    data = _build_full_worker_data()
    # EBITDA=825, Interest=800 → ICR=1.03x → -25
    data["W1"]["interest_expense"]["fy2023"] = 800.0
    entries, total = await _score_capital(data, emitter)

    icr = [e for e in entries if "Interest Coverage" in e.metric_name]
    assert len(icr) == 1
    assert icr[0].score_impact == -25


# ──────────────────────────────────────────────
# Test 12: Capital module all 3 metrics together
# ──────────────────────────────────────────────

async def test_capital_all_three():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-cap-all", "Capital All")
    data = _build_full_worker_data()
    state = _build_state_with_data(data, loan_amount=5000.0)
    entries, total = await _score_capital(data, emitter, state)

    metrics = {e.metric_name for e in entries}
    assert "Debt-to-Equity Ratio" in metrics
    assert "Net Worth Adequacy" in metrics
    assert "Interest Coverage Ratio" in metrics
    assert len(entries) == 3, f"Expected 3 entries, got {len(entries)}"

    # D/E = 1850/1280 = 1.445 → +15
    de = [e for e in entries if "Debt-to-Equity" in e.metric_name][0]
    assert de.score_impact == 15

    # NW Adequacy = 1280/5000 = 0.256x → -30
    nwa = [e for e in entries if "Net Worth" in e.metric_name][0]
    assert nwa.score_impact == -30

    # ICR = 825/195 = 4.23x → +20
    icr = [e for e in entries if "Interest Coverage" in e.metric_name][0]
    assert icr.score_impact == 20

    # Total = 15 + (-30) + 20 = 5, clamped to [-80, +80]
    assert total == 5


# ──────────────────────────────────────────────
# Test 13: Collateral with W7 data — both metrics
# ──────────────────────────────────────────────

async def test_collateral_with_w7():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-coll-w7", "Collateral W7")
    data = _build_full_worker_data()
    # W7: promoter_holding_pct=62.5 (≥60 → +25), pledge_pct=8.0 (≤10 → +5)
    entries, total = await _score_collateral(data, emitter)

    assert len(entries) == 2, f"Expected 2 entries (holding + pledge), got {len(entries)}"

    holding = [e for e in entries if "Promoter Holding" in e.metric_name][0]
    assert holding.score_impact == 25  # ≥60%

    pledge = [e for e in entries if "Promoter Pledge" in e.metric_name][0]
    assert pledge.score_impact == 5  # ≤10%

    assert total == 30  # 25 + 5


# ──────────────────────────────────────────────
# Test 14: Collateral high pledge (>30%) → -25
# ──────────────────────────────────────────────

async def test_collateral_high_pledge():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-coll-hp", "Collateral High Pledge")
    data = _build_full_worker_data()
    data["W7"]["promoter_pledge_pct"] = 45.0
    entries, total = await _score_collateral(data, emitter)

    pledge = [e for e in entries if "Pledge" in e.metric_name][0]
    assert pledge.score_impact == -25


# ──────────────────────────────────────────────
# Test 15: Collateral no pledge (0%) → +20
# ──────────────────────────────────────────────

async def test_collateral_no_pledge():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-coll-np", "Collateral No Pledge")
    data = _build_full_worker_data()
    data["W7"]["promoter_pledge_pct"] = 0.0
    entries, total = await _score_collateral(data, emitter)

    pledge = [e for e in entries if "Pledge" in e.metric_name][0]
    assert pledge.score_impact == 20


# ──────────────────────────────────────────────
# Test 16: Collateral no W7 data → default fallback
# ──────────────────────────────────────────────

async def test_collateral_no_w7():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-coll-no-w7", "Collateral No W7")
    entries, total = await _score_collateral({}, emitter)

    assert len(entries) == 1
    assert entries[0].metric_name == "Collateral Coverage"
    assert entries[0].score_impact == 5
    assert entries[0].confidence == 0.40


# ──────────────────────────────────────────────
# Test 17: Conditions rating positive → +20
# ──────────────────────────────────────────────

async def test_conditions_rating_positive():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-cond-pos", "Conditions Positive")
    data = _build_full_worker_data()
    data["W8"]["outlook"] = "Positive"
    entries, total = await _score_conditions(data, emitter)

    rating = [e for e in entries if "Rating Outlook" in e.metric_name]
    assert len(rating) == 1
    assert rating[0].score_impact == 20


# ──────────────────────────────────────────────
# Test 18: Conditions rating negative → -15
# ──────────────────────────────────────────────

async def test_conditions_rating_negative():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-cond-neg", "Conditions Negative")
    data = _build_full_worker_data()
    data["W8"]["outlook"] = "Negative"
    entries, total = await _score_conditions(data, emitter)

    rating = [e for e in entries if "Rating Outlook" in e.metric_name]
    assert len(rating) == 1
    assert rating[0].score_impact == -15


# ──────────────────────────────────────────────
# Test 19: Conditions rating stable → +10
# ──────────────────────────────────────────────

async def test_conditions_rating_stable():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-cond-stab", "Conditions Stable")
    data = _build_full_worker_data()
    # Default is "Stable"
    entries, total = await _score_conditions(data, emitter)

    rating = [e for e in entries if "Rating Outlook" in e.metric_name]
    assert len(rating) == 1
    assert rating[0].score_impact == 10

    # GST + Rating both present
    assert len(entries) == 2


# ──────────────────────────────────────────────
# Test 20: Conditions no rating data → only GST
# ──────────────────────────────────────────────

async def test_conditions_no_rating():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-cond-no-r", "Conditions No Rating")
    data = _build_full_worker_data()
    del data["W8"]
    entries, total = await _score_conditions(data, emitter)

    rating = [e for e in entries if "Rating" in e.metric_name]
    assert len(rating) == 0
    # GST still scored
    gst = [e for e in entries if "GST" in e.metric_name]
    assert len(gst) == 1


# ──────────────────────────────────────────────
# Test 21: Full pipeline with all enhanced data
# ──────────────────────────────────────────────

async def test_full_pipeline_enhanced():
    reset_publisher()
    data = _build_full_worker_data()
    state = _build_state_with_data(data, loan_amount=5000.0)
    state.raw_data_package = RawDataPackage(
        session_id="test-t2-1-full",
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

    score = result["score"]
    assert 0 <= score <= 850

    # Verify all 6 modules present
    assert len(result["score_modules"]) == 6

    # Verify new metrics are in the breakdown
    all_metrics = {e.metric_name for e in result["score_breakdown"]}
    assert "DSCR" in all_metrics, f"Missing DSCR. Got: {all_metrics}"
    assert "Net Worth Adequacy" in all_metrics, f"Missing NWA. Got: {all_metrics}"
    assert "Interest Coverage Ratio" in all_metrics, f"Missing ICR. Got: {all_metrics}"
    assert "Promoter Holding" in all_metrics, f"Missing Promoter Holding. Got: {all_metrics}"
    assert "Promoter Pledge" in all_metrics, f"Missing Promoter Pledge. Got: {all_metrics}"
    assert "Rating Outlook" in all_metrics, f"Missing Rating Outlook. Got: {all_metrics}"

    # Cleanup
    cam_dir = os.path.join("data", "output", state.session_id)
    if os.path.exists(cam_dir):
        shutil.rmtree(cam_dir)


# ──────────────────────────────────────────────
# Test 22: Enhanced modules backward compatible
# ──────────────────────────────────────────────

async def test_backward_compatible():
    """All enhanced modules still work without state param (old call pattern)."""
    reset_publisher()
    emitter = ThinkingEventEmitter("test-compat", "Compat")
    data = _build_full_worker_data()

    # Call without state — should not error
    cap_entries, cap_total = await _score_capacity(data, emitter)
    assert len(cap_entries) >= 3  # Revenue + EBITDA + EMI + DSCR (at least 3)

    cap2_entries, cap2_total = await _score_capital(data, emitter)
    assert len(cap2_entries) >= 1  # D/E at minimum (NWA skipped, ICR present)

    coll_entries, coll_total = await _score_collateral(data, emitter)
    assert len(coll_entries) >= 1  # W7 data present

    cond_entries, cond_total = await _score_conditions(data, emitter)
    assert len(cond_entries) >= 1  # GST + Rating


# ──────────────────────────────────────────────
# Test 23: Module limits enforced with new metrics
# ──────────────────────────────────────────────

async def test_module_limits_enhanced():
    """Verify module total is clamped even with many new metrics."""
    reset_publisher()
    emitter = ThinkingEventEmitter("test-limits", "Limits")
    data = _build_full_worker_data()
    # Strong collateral: holding 80% (+25) + pledge 0% (+20) = +45
    # But COLLATERAL max is +60, so should be fine — but let's verify clamping
    data["W7"]["promoter_holding_pct"] = 80.0
    data["W7"]["promoter_pledge_pct"] = 0.0
    entries, total = await _score_collateral(data, emitter)

    limits = MODULE_LIMITS[ScoreModule.COLLATERAL]
    assert total <= limits["max_positive"], f"Total {total} exceeds max {limits['max_positive']}"
    assert total >= limits["max_negative"], f"Total {total} below min {limits['max_negative']}"
    assert total == 45  # 25 + 20, within [-40, +60]


# ──────────────────────────────────────────────
# Test 24: DSCR + Revenue + EBITDA + EMI all scored
# ──────────────────────────────────────────────

async def test_capacity_all_four_metrics():
    """With full data, all 4 capacity metrics should be scored."""
    reset_publisher()
    emitter = ThinkingEventEmitter("test-cap4", "Capacity Four")
    data = _build_full_worker_data()
    entries, total = await _score_capacity(data, emitter)

    metrics = {e.metric_name for e in entries}
    assert "Revenue Growth YoY" in metrics
    assert "EBITDA Margin" in metrics
    assert "EMI Regularity" in metrics
    assert "DSCR" in metrics
    assert len(entries) == 4, f"Expected 4 entries, got {len(entries)}: {metrics}"
