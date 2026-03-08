"""
T2.4 — Score API Endpoint Tests

Tests GET /api/score/{session_id} and POST /api/score/{session_id}/run.
"""

from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.api.routes._store import assessments_store
from backend.models.schemas import (
    AssessmentOutcome,
    AssessmentSummary,
    CompanyInfo,
    LoanTerms,
    ScoreBand,
    ScoreBreakdownEntry,
    ScoreModule,
    ScoreModuleSummary,
    ScoreResponse,
    HardBlockResponse,
)
from config.scoring import BASE_SCORE, get_score_band, get_loan_terms


# ── fixtures ──


@pytest.fixture(autouse=True)
def _clear_store():
    assessments_store.clear()
    yield
    assessments_store.clear()


def _make_entry(module=ScoreModule.CAPACITY, impact=10) -> ScoreBreakdownEntry:
    return ScoreBreakdownEntry(
        module=module,
        metric_name="TestMetric",
        metric_value="OK",
        computation_formula="n/a",
        source_document="AR",
        source_page=1,
        source_excerpt="excerpt",
        benchmark_context="bench",
        score_impact=impact,
        reasoning="test",
        confidence=0.80,
    )


def _scored_assessment(session_id: str = "sess-1") -> AssessmentSummary:
    """Create an assessment that has already been scored."""
    return AssessmentSummary(
        session_id=session_id,
        company=CompanyInfo(
            name="TestCorp Ltd",
            sector="Manufacturing",
            loan_type="Working Capital",
            loan_amount="₹50 Cr",
            loan_amount_numeric=5000.0,
        ),
        score=650,
        score_band=ScoreBand.GOOD,
        outcome=AssessmentOutcome.APPROVED,
        score_modules=[
            ScoreModuleSummary(
                module=ScoreModule.CAPACITY, score=80,
                max_positive=150, max_negative=-100,
                metrics=[_make_entry(ScoreModule.CAPACITY, 80)],
            ),
            ScoreModuleSummary(
                module=ScoreModule.CHARACTER, score=50,
                max_positive=120, max_negative=-200,
                metrics=[_make_entry(ScoreModule.CHARACTER, 50)],
            ),
        ],
        completed_at=datetime.utcnow(),
        cam_url="/data/output/sess-1/credit_appraisal_memo.txt",
    )


def _unscored_assessment(session_id: str = "sess-2") -> AssessmentSummary:
    """Create an assessment that has NOT been scored yet."""
    return AssessmentSummary(
        session_id=session_id,
        company=CompanyInfo(
            name="Unscored Inc",
            sector="IT",
            loan_type="Term Loan",
            loan_amount="₹10 Cr",
            loan_amount_numeric=1000.0,
        ),
    )


# ── GET /api/score/{session_id} ──


@pytest.mark.asyncio
async def test_get_score_success():
    """GET returns ScoreResponse for a scored session."""
    assessments_store["sess-1"] = _scored_assessment()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/score/sess-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "sess-1"
    assert data["score"] == 650
    assert data["score_band"] == ScoreBand.GOOD.value
    assert data["company_name"] == "TestCorp Ltd"
    assert data["base_score"] == BASE_SCORE


@pytest.mark.asyncio
async def test_get_score_not_found():
    """GET returns 404 for unknown session."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/score/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_score_not_scored():
    """GET returns 409 when session exists but hasn't been scored."""
    assessments_store["sess-2"] = _unscored_assessment()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/score/sess-2")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_score_modules():
    """GET returns module summaries with correct structure."""
    assessments_store["sess-1"] = _scored_assessment()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/score/sess-1")
    data = resp.json()
    modules = data["modules"]
    assert len(modules) == 2
    assert modules[0]["module"] == "CAPACITY"
    assert modules[0]["score"] == 80
    assert len(modules[0]["metrics"]) == 1


@pytest.mark.asyncio
async def test_get_score_loan_terms_good():
    """GET returns correct loan terms for GOOD band."""
    assessments_store["sess-1"] = _scored_assessment()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/score/sess-1")
    terms = resp.json()["loan_terms"]
    expected_terms = get_loan_terms(ScoreBand.GOOD)
    assert terms["sanction_pct"] == int(expected_terms["sanction_pct"])
    assert terms["rate"] == expected_terms["rate"]
    assert terms["tenure"] == expected_terms["tenure"]
    assert terms["review"] == expected_terms["review"]


@pytest.mark.asyncio
async def test_get_score_total_metrics():
    """GET returns correct total_metrics count."""
    assessments_store["sess-1"] = _scored_assessment()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/score/sess-1")
    assert resp.json()["total_metrics"] == 2  # 1 per module


@pytest.mark.asyncio
async def test_get_score_cam_url():
    """GET includes cam_url when present."""
    assessments_store["sess-1"] = _scored_assessment()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/score/sess-1")
    assert resp.json()["cam_url"] == "/data/output/sess-1/credit_appraisal_memo.txt"


@pytest.mark.asyncio
async def test_get_score_recommendation_text():
    """GET returns meaningful recommendation text."""
    assessments_store["sess-1"] = _scored_assessment()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/score/sess-1")
    rec = resp.json()["recommendation"]
    assert ScoreBand.GOOD.value in rec
    assert "approval" in rec.lower()


# ── POST /api/score/{session_id}/run ──


@pytest.mark.asyncio
async def test_run_scoring_not_found():
    """POST returns 404 for unknown session."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/score/nonexistent/run")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_scoring_dynamic():
    """POST computes dynamic score on unscored session (no modules = BASE_SCORE)."""
    assessments_store["sess-2"] = _unscored_assessment()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/score/sess-2/run")
    assert resp.status_code == 200
    data = resp.json()
    # No modules attached → score defaults to BASE_SCORE
    expected_band, expected_outcome, _ = get_score_band(BASE_SCORE)
    assert data["score"] == BASE_SCORE
    assert data["score_band"] == expected_band.value
    assert data["outcome"] == expected_outcome.value


@pytest.mark.asyncio
async def test_run_scoring_already_scored():
    """POST returns existing score if already scored."""
    assessments_store["sess-1"] = _scored_assessment()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/score/sess-1/run")
    assert resp.status_code == 200
    assert resp.json()["score"] == 650  # unchanged


@pytest.mark.asyncio
async def test_run_scoring_updates_store():
    """POST sets score on the in-memory store."""
    assessments_store["sess-2"] = _unscored_assessment()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.post("/api/score/sess-2/run")
    assert assessments_store["sess-2"].score == BASE_SCORE
    assert assessments_store["sess-2"].completed_at is not None


@pytest.mark.asyncio
async def test_run_scoring_sets_completed_at():
    """POST sets completed_at timestamp."""
    assessments_store["sess-2"] = _unscored_assessment()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/score/sess-2/run")
    assert resp.json()["scored_at"] is not None


# ── Pydantic model tests ──


def test_score_response_model_validation():
    """ScoreResponse validates field constraints."""
    resp = ScoreResponse(
        session_id="s1",
        company_name="X",
        score=700,
        score_band=ScoreBand.GOOD,
        outcome=AssessmentOutcome.APPROVED,
        recommendation="OK",
    )
    assert resp.score == 700
    assert resp.base_score == BASE_SCORE


def test_loan_terms_model():
    """LoanTerms model works correctly."""
    terms = LoanTerms(sanction_pct=85, rate="MCLR+2.5%", tenure="5yr", review="Semi")
    assert terms.sanction_pct == 85


def test_hard_block_response_model():
    """HardBlockResponse model validates."""
    hb = HardBlockResponse(trigger="nclt", score_cap=250, evidence="e", source="W5")
    assert hb.score_cap == 250


def test_score_response_rejects_invalid_score():
    """ScoreResponse rejects score > 850."""
    with pytest.raises(Exception):
        ScoreResponse(
            session_id="s1",
            company_name="X",
            score=900,
            score_band=ScoreBand.EXCELLENT,
            outcome=AssessmentOutcome.APPROVED,
            recommendation="OK",
        )
