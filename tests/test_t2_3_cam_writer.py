"""
T2.3 — Enhanced CAM Writer Tests
Tests the enriched Credit Appraisal Memo: Key Financial Metrics,
Cross-Verification Summary, Risk Flags, Loan Terms, numbered sections.
"""

import os
import shutil
from unittest.mock import AsyncMock

import pytest

from backend.graph.nodes.recommendation_node import (
    _generate_cam,
    _get_loan_terms,
    BASE_SCORE,
)
from backend.models.schemas import (
    AssessmentOutcome,
    ScoreBand,
    ScoreBreakdownEntry,
    ScoreModule,
    ScoreModuleSummary,
)
from backend.graph.state import HardBlock
from backend.thinking.event_emitter import ThinkingEventEmitter
from backend.thinking.redis_publisher import reset_publisher


# ── fixtures ──


@pytest.fixture(autouse=True)
def _reset():
    reset_publisher()


def _emitter() -> ThinkingEventEmitter:
    e = ThinkingEventEmitter.__new__(ThinkingEventEmitter)
    e.session_id = "test"
    e.agent_name = "test"
    for m in ("read", "found", "computed", "accepted", "rejected",
              "flagged", "critical", "connecting", "concluding",
              "questioning", "decided"):
        setattr(e, m, AsyncMock())
    return e


def _make_module_summary(module: ScoreModule, score: int) -> ScoreModuleSummary:
    return ScoreModuleSummary(
        module=module,
        score=score,
        max_positive=150 if module == ScoreModule.CAPACITY else 80,
        max_negative=-100 if module == ScoreModule.CAPACITY else -80,
        metrics=[_make_entry(module=module)],
    )


def _make_entry(
    module: ScoreModule = ScoreModule.CAPACITY,
    metric_name: str = "TestMetric",
    metric_value: str = "OK",
    score_impact: int = 10,
    reasoning: str = "test reason",
) -> ScoreBreakdownEntry:
    return ScoreBreakdownEntry(
        module=module,
        metric_name=metric_name,
        metric_value=metric_value,
        computation_formula="n/a",
        source_document="Annual Report",
        source_page=1,
        source_excerpt="excerpt",
        benchmark_context="bench",
        score_impact=score_impact,
        reasoning=reasoning,
        confidence=0.80,
    )


CAM_DIR = os.path.join("data", "output", "cam_test_sess")


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    if os.path.exists(CAM_DIR):
        shutil.rmtree(CAM_DIR)


# ── helpers ──


async def _gen_cam(
    worker_data=None,
    hard_blocks=None,
    entries=None,
    module_summaries=None,
    score=500,
    band=ScoreBand.POOR,
) -> str:
    """Generate a CAM and return its text content."""
    if worker_data is None:
        worker_data = {}
    if hard_blocks is None:
        hard_blocks = []
    if entries is None:
        entries = [_make_entry()]
    if module_summaries is None:
        module_summaries = [_make_module_summary(ScoreModule.CAPACITY, 10)]

    path = await _generate_cam(
        session_id="cam_test_sess",
        company_name="TestCorp Ltd",
        score=score,
        band=band,
        outcome=AssessmentOutcome.CONDITIONAL,
        recommendation="Approved with conditions",
        module_summaries=module_summaries,
        all_entries=entries,
        hard_blocks=hard_blocks,
        worker_data=worker_data,
        emitter=_emitter(),
    )
    with open(path, encoding="utf-8") as f:
        return f.read()


# ─────────────────────── SECTION EXISTENCE ───────────────────────


@pytest.mark.asyncio
async def test_cam_has_numbered_sections():
    """CAM must have all 8 numbered section headers."""
    text = await _gen_cam()
    for header in [
        "1. EXECUTIVE SUMMARY",
        "3. KEY FINANCIAL METRICS",
        "4. SCORE BREAKDOWN BY MODULE",
        "5. CROSS-VERIFICATION SUMMARY",
        "6. RISK FLAGS",
        "7. LOAN TERMS RECOMMENDATION",
        "8. DETAILED METRIC BREAKDOWN",
    ]:
        assert header in text, f"Missing section: {header}"


@pytest.mark.asyncio
async def test_cam_hard_block_section_present():
    """Section 2 appears only when hard blocks exist."""
    text_no_hb = await _gen_cam(hard_blocks=[])
    assert "2. HARD BLOCK TRIGGERS" not in text_no_hb

    text_with_hb = await _gen_cam(hard_blocks=[
        HardBlock(trigger="nclt_active", score_cap=250,
                  evidence="NCLT pending", source="W5"),
    ])
    assert "2. HARD BLOCK TRIGGERS" in text_with_hb


# ─────────────────────── KEY FINANCIAL METRICS ───────────────────────


@pytest.mark.asyncio
async def test_key_metrics_revenue():
    """Section 3 shows revenue and growth when W1 has data."""
    w1 = {"revenue": {"fy2023": 5000, "fy2022": 4000}}
    text = await _gen_cam(worker_data={"W1": w1})
    assert "5,000L" in text.replace(" ", "").replace("₹", "")
    assert "25.0%" in text  # (5000-4000)/4000 = 25%


@pytest.mark.asyncio
async def test_key_metrics_ebitda_margin():
    """Section 3 shows EBITDA margin."""
    w1 = {"revenue": {"fy2023": 10000}, "ebitda": {"fy2023": 2000}}
    text = await _gen_cam(worker_data={"W1": w1})
    assert "20.0% margin" in text


@pytest.mark.asyncio
async def test_key_metrics_dscr():
    """Section 3 shows DSCR when ebitda and interest present."""
    w1 = {"ebitda": {"fy2023": 300}, "interest_expense": {"fy2023": 200}}
    text = await _gen_cam(worker_data={"W1": w1})
    assert "1.50x" in text


@pytest.mark.asyncio
async def test_key_metrics_debt_equity():
    """Section 3 shows D/E ratio."""
    w1 = {"total_debt": {"fy2023": 500}, "net_worth": {"fy2023": 250}}
    text = await _gen_cam(worker_data={"W1": w1})
    assert "2.00x" in text


@pytest.mark.asyncio
async def test_key_metrics_emi_regularity():
    """Section 3 shows EMI regularity from W2."""
    wd = {"W2": {"emi_regularity": {"regularity_pct": 95}}}
    text = await _gen_cam(worker_data=wd)
    assert "95%" in text


@pytest.mark.asyncio
async def test_key_metrics_empty_w1():
    """Section 3 still appears with no W1 data (just empty)."""
    text = await _gen_cam(worker_data={})
    assert "3. KEY FINANCIAL METRICS" in text


# ─────────────────────── CROSS-VERIFICATION SUMMARY ───────────────────────


@pytest.mark.asyncio
async def test_cross_verification_entries():
    """Section 5 shows compound Cross-Verification entries."""
    entries = [
        _make_entry(ScoreModule.COMPOUND, "Revenue Cross-Verification",
                    "Match", 20, "All sources agree"),
        _make_entry(ScoreModule.CAPACITY, "Revenue Growth", "15%", 15, "Good"),
    ]
    text = await _gen_cam(entries=entries)
    assert "Revenue Cross-Verification" in text.split("5. CROSS-VERIFICATION")[1].split("6. RISK")[0]


@pytest.mark.asyncio
async def test_cross_verification_itc():
    """Section 5 shows ITC/GSTR entries."""
    entries = [
        _make_entry(ScoreModule.COMPOUND, "ITC Mismatch", ">10%", -25, "Claimed > available"),
    ]
    text = await _gen_cam(entries=entries)
    section_5 = text.split("5. CROSS-VERIFICATION")[1].split("6. RISK")[0]
    assert "ITC Mismatch" in section_5


@pytest.mark.asyncio
async def test_cross_verification_none():
    """Section 5 says 'No cross-verification flags' when none present."""
    entries = [_make_entry(ScoreModule.CAPACITY)]  # not compound
    text = await _gen_cam(entries=entries)
    assert "No cross-verification flags" in text


# ─────────────────────── RISK FLAGS ───────────────────────


@pytest.mark.asyncio
async def test_risk_flags_populated():
    """Section 6 lists entries with impact < -10."""
    entries = [
        _make_entry(score_impact=-30, metric_name="HighRiskMetric", reasoning="Very risky"),
        _make_entry(score_impact=10, metric_name="GoodMetric"),
    ]
    text = await _gen_cam(entries=entries)
    section_6 = text.split("6. RISK FLAGS")[1].split("7. LOAN TERMS")[0]
    assert "HighRiskMetric" in section_6
    assert "GoodMetric" not in section_6


@pytest.mark.asyncio
async def test_risk_flags_none():
    """Section 6 says no significant risk flags when all impacts >= -10."""
    entries = [_make_entry(score_impact=-5)]
    text = await _gen_cam(entries=entries)
    assert "No significant risk flags" in text


# ─────────────────────── LOAN TERMS ───────────────────────


@pytest.mark.asyncio
async def test_loan_terms_excellent():
    text = await _gen_cam(score=800, band=ScoreBand.EXCELLENT)
    section_7 = text.split("7. LOAN TERMS")[1].split("8. DETAILED")[0]
    assert "100%" in section_7
    assert "MCLR + 1.5%" in section_7


@pytest.mark.asyncio
async def test_loan_terms_good():
    text = await _gen_cam(score=700, band=ScoreBand.GOOD)
    section_7 = text.split("7. LOAN TERMS")[1].split("8. DETAILED")[0]
    assert "85%" in section_7
    assert "MCLR + 2.5%" in section_7


@pytest.mark.asyncio
async def test_loan_terms_fair():
    text = await _gen_cam(score=600, band=ScoreBand.FAIR)
    section_7 = text.split("7. LOAN TERMS")[1].split("8. DETAILED")[0]
    assert "65%" in section_7
    assert "MCLR + 3.5%" in section_7


@pytest.mark.asyncio
async def test_loan_terms_poor():
    text = await _gen_cam(score=480, band=ScoreBand.POOR)
    section_7 = text.split("7. LOAN TERMS")[1].split("8. DETAILED")[0]
    assert "40%" in section_7
    assert "MCLR + 5.0%" in section_7


@pytest.mark.asyncio
async def test_loan_terms_reject():
    text = await _gen_cam(score=300, band=ScoreBand.VERY_POOR)
    section_7 = text.split("7. LOAN TERMS")[1].split("8. DETAILED")[0]
    assert "0%" in section_7
    assert "Rejected" in section_7


# ─────────────────────── _get_loan_terms UNIT ───────────────────────


def test_get_loan_terms_all_bands():
    """Pure unit test for _get_loan_terms helper."""
    assert _get_loan_terms(ScoreBand.EXCELLENT)["sanction_pct"] == "100"
    assert _get_loan_terms(ScoreBand.GOOD)["sanction_pct"] == "85"
    assert _get_loan_terms(ScoreBand.FAIR)["sanction_pct"] == "65"
    assert _get_loan_terms(ScoreBand.POOR)["sanction_pct"] == "40"
    assert _get_loan_terms(ScoreBand.VERY_POOR)["sanction_pct"] == "0"
    assert _get_loan_terms(ScoreBand.DEFAULT_RISK)["sanction_pct"] == "0"


# ─────────────────────── FILE OUTPUT ───────────────────────


@pytest.mark.asyncio
async def test_cam_file_created():
    """CAM file is written to the correct path."""
    path_result = await _generate_cam(
        session_id="cam_test_sess",
        company_name="TestCorp",
        score=500,
        band=ScoreBand.POOR,
        outcome=AssessmentOutcome.CONDITIONAL,
        recommendation="OK",
        module_summaries=[_make_module_summary(ScoreModule.CAPACITY, 10)],
        all_entries=[_make_entry()],
        hard_blocks=[],
        worker_data={},
        emitter=_emitter(),
    )
    assert os.path.exists(path_result)
    assert path_result.endswith("credit_appraisal_memo.txt")


@pytest.mark.asyncio
async def test_cam_header_footer():
    """CAM starts with header and ends with footer."""
    text = await _gen_cam()
    assert text.startswith("=" * 80)
    assert "END OF CREDIT APPRAISAL MEMO" in text


@pytest.mark.asyncio
async def test_cam_borrower_name():
    """CAM includes borrower name in header."""
    text = await _gen_cam()
    assert "TestCorp Ltd" in text
