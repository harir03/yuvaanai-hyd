"""
T5.5 — Mock Pipeline End-to-End Test

Exercises the full upload → pipeline trigger → score → CAM flow
by mocking the LangGraph orchestrator. Validates that the API layer,
state management, and store updates all work correctly end-to-end.

Perspective: 🎯 Hackathon Judge (Demo Impact)
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.api.routes._store import assessments_store
from backend.models.schemas import (
    AssessmentOutcome,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
    ScoreBand,
    ScoreBreakdownEntry,
    ScoreModule,
    ScoreModuleSummary,
)
from config.scoring import BASE_SCORE, MAX_SCORE, get_score_band

# Mock pipeline demo score (XYZ Steel scenario)
MOCK_PIPELINE_SCORE = 477
MOCK_PIPELINE_BAND, MOCK_PIPELINE_OUTCOME, _ = get_score_band(MOCK_PIPELINE_SCORE)


# ── Mock pipeline result ──

def _mock_pipeline_result(session_id: str):
    """Build a realistic pipeline result dict mimicking LangGraph final state."""
    return {
        "session_id": session_id,
        "score": MOCK_PIPELINE_SCORE,
        "score_band": MOCK_PIPELINE_BAND,
        "outcome": MOCK_PIPELINE_OUTCOME,
        "cam_path": f"/data/output/{session_id}/credit_appraisal_memo.txt",
        "pipeline_stages": [
            PipelineStage(
                stage=s,
                status=PipelineStageStatus.COMPLETED,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                message=f"{s.value} completed",
            )
            for s in PipelineStageEnum
        ],
        "score_modules": [
            ScoreModuleSummary(
                module=ScoreModule.CAPACITY, score=60,
                max_positive=150, max_negative=-100,
                metrics=[
                    ScoreBreakdownEntry(
                        module=ScoreModule.CAPACITY,
                        metric_name="DSCR",
                        metric_value="1.38x",
                        computation_formula="Net Cash / Debt Service",
                        source_document="Annual Report",
                        source_page=42,
                        source_excerpt="Debt service coverage ratio stood at 1.38x",
                        benchmark_context="Manufacturing median: 1.5x",
                        score_impact=60,
                        reasoning="Below benchmark but adequate",
                        confidence=0.85,
                    )
                ],
            ),
            ScoreModuleSummary(
                module=ScoreModule.CHARACTER, score=27,
                max_positive=120, max_negative=-200,
                metrics=[
                    ScoreBreakdownEntry(
                        module=ScoreModule.CHARACTER,
                        metric_name="Promoter Track Record",
                        metric_value="Mixed",
                        computation_formula="Weighted history",
                        source_document="Board Minutes",
                        source_page=3,
                        source_excerpt="Director attendance 60% in last 4 meetings",
                        benchmark_context="Expected: >75%",
                        score_impact=27,
                        reasoning="Below average attendance raises governance concerns",
                        confidence=0.80,
                    )
                ],
            ),
        ],
        "thinking_events": [
            {"event_type": "READ", "agent": "Workers", "message": "Processing Annual Report..."},
            {"event_type": "FOUND", "agent": "Consolidator", "message": "Revenue: AR ₹247cr, GST ₹198cr — 20% divergence"},
            {"event_type": "FLAGGED", "agent": "Research", "message": "NJDG shows 2 undisclosed litigation cases"},
            {"event_type": "COMPUTED", "agent": "Scorer", "message": f"Final score: {MOCK_PIPELINE_SCORE}/{MAX_SCORE} ({MOCK_PIPELINE_BAND.value.upper()} band)"},
        ],
    }


@pytest.fixture(autouse=True)
def _clear_store():
    assessments_store.clear()
    yield
    assessments_store.clear()


# ── E2E Tests ──


@pytest.mark.asyncio
async def test_e2e_upload_to_pipeline_trigger():
    """Upload documents then trigger pipeline — verify 202 Accepted."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Step 1: Upload
        resp = await ac.post(
            "/api/upload",
            data={
                "company_name": "XYZ Steel Pvt Ltd",
                "sector": "Steel Manufacturing",
                "loan_type": "Working Capital",
                "loan_amount": "₹50 Cr",
                "loan_amount_numeric": 5000.0,
                "cin": "L27100MH2005PLC123456",
                "promoter_name": "Rajesh K. Agarwal",
            },
            files=[("files", ("ar.txt", b"Annual Report content", "text/plain"))],
        )
        assert resp.status_code == 201
        session_id = resp.json()["session_id"]

        # Step 2: Trigger pipeline
        with patch(
            "backend.api.routes.pipeline.run_pipeline",
            new_callable=AsyncMock,
            return_value=_mock_pipeline_result(session_id),
        ):
            resp = await ac.post(f"/api/pipeline/{session_id}/run")
            assert resp.status_code == 202
            assert resp.json()["status"] == "pipeline_started"


@pytest.mark.asyncio
async def test_e2e_pipeline_updates_store():
    """After pipeline completes, assessment store has score + outcome."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Upload
        resp = await ac.post(
            "/api/upload",
            data={
                "company_name": "XYZ Steel Pvt Ltd",
                "sector": "Steel Manufacturing",
                "loan_type": "Working Capital",
                "loan_amount": "₹50 Cr",
                "loan_amount_numeric": 5000.0,
            },
            files=[("files", ("ar.txt", b"Annual Report text", "text/plain"))],
        )
        session_id = resp.json()["session_id"]

    # Run pipeline directly (not via background task) for deterministic testing
    from backend.api.routes.pipeline import _execute_pipeline

    with patch(
        "backend.api.routes.pipeline.run_pipeline",
        new_callable=AsyncMock,
        return_value=_mock_pipeline_result(session_id),
    ):
        await _execute_pipeline(session_id)

    # Verify store was updated
    assessment = assessments_store[session_id]
    assert assessment.score == MOCK_PIPELINE_SCORE
    assert assessment.score_band == MOCK_PIPELINE_BAND
    assert assessment.outcome == MOCK_PIPELINE_OUTCOME
    assert assessment.cam_path is not None
    assert session_id in assessment.cam_path


@pytest.mark.asyncio
async def test_e2e_score_endpoint_after_pipeline():
    """Score endpoint returns data after pipeline completes."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Upload
        resp = await ac.post(
            "/api/upload",
            data={
                "company_name": "XYZ Steel Pvt Ltd",
                "sector": "Steel Manufacturing",
                "loan_type": "Working Capital",
                "loan_amount": "₹50 Cr",
                "loan_amount_numeric": 5000.0,
            },
            files=[("files", ("ar.txt", b"Annual Report text", "text/plain"))],
        )
        session_id = resp.json()["session_id"]

    # Run pipeline
    from backend.api.routes.pipeline import _execute_pipeline

    with patch(
        "backend.api.routes.pipeline.run_pipeline",
        new_callable=AsyncMock,
        return_value=_mock_pipeline_result(session_id),
    ):
        await _execute_pipeline(session_id)

    # Check score endpoint
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(f"/api/score/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == MOCK_PIPELINE_SCORE
        assert data["score_band"].upper() == MOCK_PIPELINE_BAND.value.upper()
        assert data["company_name"] == "XYZ Steel Pvt Ltd"


@pytest.mark.asyncio
async def test_e2e_pipeline_status_after_completion():
    """Pipeline status shows completed after execution."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/upload",
            data={
                "company_name": "XYZ Steel Pvt Ltd",
                "sector": "Steel Manufacturing",
                "loan_type": "Working Capital",
                "loan_amount": "₹50 Cr",
                "loan_amount_numeric": 5000.0,
            },
        )
        session_id = resp.json()["session_id"]

    from backend.api.routes.pipeline import _execute_pipeline

    with patch(
        "backend.api.routes.pipeline.run_pipeline",
        new_callable=AsyncMock,
        return_value=_mock_pipeline_result(session_id),
    ):
        await _execute_pipeline(session_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(f"/api/pipeline/{session_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_running"] is False
        assert data["progress"]["percent"] > 0


@pytest.mark.asyncio
async def test_e2e_pipeline_not_found():
    """Pipeline trigger returns 404 for unknown session."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/pipeline/ghost-session/run")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_e2e_pipeline_failure_handled():
    """Pipeline failure is stored in assessment without crashing."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/upload",
            data={
                "company_name": "Failing Corp",
                "sector": "IT",
                "loan_type": "Term Loan",
                "loan_amount": "₹10 Cr",
                "loan_amount_numeric": 1000.0,
            },
        )
        session_id = resp.json()["session_id"]

    from backend.api.routes.pipeline import _execute_pipeline

    with patch(
        "backend.api.routes.pipeline.run_pipeline",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Neo4j connection refused"),
    ):
        await _execute_pipeline(session_id)

    # Assessment should record the error, not crash
    assessment = assessments_store[session_id]
    assert assessment.error is not None
    assert "Neo4j" in assessment.error


@pytest.mark.asyncio
async def test_e2e_upload_with_auto_run():
    """Upload with auto_run=true triggers pipeline automatically."""
    with patch(
        "backend.api.routes.pipeline._execute_pipeline",
        new_callable=AsyncMock,
    ) as mock_exec:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/upload",
                data={
                    "company_name": "Auto Corp",
                    "sector": "FMCG",
                    "loan_type": "Working Capital",
                    "loan_amount": "₹20 Cr",
                    "loan_amount_numeric": 2000.0,
                    "auto_run": "true",
                },
                files=[("files", ("report.txt", b"revenue data", "text/plain"))],
            )
        assert resp.status_code == 201


@pytest.mark.asyncio
async def test_e2e_full_demo_flow():
    """
    🎯 Hackathon Demo Flow: Upload → Pipeline → Score → Assessment list.
    
    This is the primary demo path that must work flawlessly.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # 1. Upload company documents
        resp = await ac.post(
            "/api/upload",
            data={
                "company_name": "XYZ Steel Pvt Ltd",
                "sector": "Steel Manufacturing",
                "loan_type": "Working Capital",
                "loan_amount": "₹50 Cr",
                "loan_amount_numeric": 5000.0,
                "cin": "L27100MH2005PLC123456",
                "gstin": "27AABCU9603R1ZM",
                "pan": "AABCU9603R",
                "incorporation_year": 2005,
                "promoter_name": "Rajesh K. Agarwal",
            },
            files=[
                ("files", ("annual_report.txt", b"AR content for XYZ Steel", "text/plain")),
                ("files", ("gst_returns.txt", b"GST data for XYZ Steel", "text/plain")),
            ],
        )
        assert resp.status_code == 201
        session_id = resp.json()["session_id"]
        assert resp.json()["company"]["name"] == "XYZ Steel Pvt Ltd"
        assert len(resp.json()["documents"]) == 2

    # 2. Run pipeline (direct call for determinism)
    from backend.api.routes.pipeline import _execute_pipeline

    with patch(
        "backend.api.routes.pipeline.run_pipeline",
        new_callable=AsyncMock,
        return_value=_mock_pipeline_result(session_id),
    ):
        await _execute_pipeline(session_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # 3. Check score
        resp = await ac.get(f"/api/score/{session_id}")
        assert resp.status_code == 200
        score_data = resp.json()
        assert score_data["score"] == MOCK_PIPELINE_SCORE
        assert score_data["score_band"].upper() == MOCK_PIPELINE_BAND.value.upper()
        assert score_data["company_name"] == "XYZ Steel Pvt Ltd"
        assert score_data["base_score"] == BASE_SCORE

        # 4. Check pipeline status
        resp = await ac.get(f"/api/pipeline/{session_id}/status")
        assert resp.status_code == 200
        assert resp.json()["is_running"] is False

        # 5. Check assessment appears in listing
        resp = await ac.get("/api/assessments")
        assert resp.status_code == 200
        listing = resp.json()
        session_ids = [a["session_id"] for a in listing]
        assert session_id in session_ids

        # 6. Check individual assessment detail
        resp = await ac.get(f"/api/assessment/{session_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["score"] == MOCK_PIPELINE_SCORE
        assert detail["company"]["name"] == "XYZ Steel Pvt Ltd"
