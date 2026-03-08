"""
Intelli-Credit — T3.2 Pipeline Trigger Tests

Tests for:
- POST /api/pipeline/{session_id}/run — trigger pipeline
- GET  /api/pipeline/{session_id}/status — pipeline status
- POST /api/pipeline/{session_id}/cancel — cancel pipeline
- Upload auto_run parameter
- Background execution + store update

5-Perspective Testing:
🏦 Credit Domain Expert — pipeline produces correct score/band/outcome flow
🔒 Security Architect — session isolation, invalid session handling, double-start prevention
⚙️ Systems Engineer — concurrent pipelines, failure recovery, state consistency
🧪 QA Engineer — edge cases: empty docs, missing session, cancellation timing
🎯 Hackathon Judge — end-to-end demo flow, upload → pipeline → results
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routes._store import assessments_store
from backend.api.routes.pipeline import _running_pipelines, _execute_pipeline
from backend.models.schemas import (
    AssessmentSummary,
    AssessmentOutcome,
    CompanyInfo,
    DocumentMeta,
    DocumentType,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
    WorkerStatus,
    WorkerStatusEnum,
    ScoreBand,
)


client = TestClient(app)


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
    )
    defaults.update(overrides)
    return CompanyInfo(**defaults)


def _make_assessment(session_id: str = "test-pipe-001", **overrides) -> AssessmentSummary:
    defaults = dict(
        session_id=session_id,
        company=_make_company(),
        documents=[
            DocumentMeta(filename="annual_report.pdf", document_type=DocumentType.ANNUAL_REPORT, file_size=1024),
            DocumentMeta(filename="bank_stmt.pdf", document_type=DocumentType.BANK_STATEMENT, file_size=2048),
        ],
        pipeline_stages=[
            PipelineStage(stage=PipelineStageEnum.UPLOAD, status=PipelineStageStatus.COMPLETED),
            PipelineStage(stage=PipelineStageEnum.WORKERS, status=PipelineStageStatus.PENDING),
            PipelineStage(stage=PipelineStageEnum.CONSOLIDATION, status=PipelineStageStatus.PENDING),
            PipelineStage(stage=PipelineStageEnum.VALIDATION, status=PipelineStageStatus.PENDING),
            PipelineStage(stage=PipelineStageEnum.ORGANIZATION, status=PipelineStageStatus.PENDING),
            PipelineStage(stage=PipelineStageEnum.RESEARCH, status=PipelineStageStatus.PENDING),
            PipelineStage(stage=PipelineStageEnum.REASONING, status=PipelineStageStatus.PENDING),
            PipelineStage(stage=PipelineStageEnum.EVIDENCE, status=PipelineStageStatus.PENDING),
            PipelineStage(stage=PipelineStageEnum.TICKETS, status=PipelineStageStatus.PENDING),
            PipelineStage(stage=PipelineStageEnum.RECOMMENDATION, status=PipelineStageStatus.PENDING),
        ],
        workers=[
            WorkerStatus(worker_id="W1", document_type=DocumentType.ANNUAL_REPORT, status=WorkerStatusEnum.QUEUED, current_task="Queued"),
        ],
        outcome=AssessmentOutcome.PENDING,
        documents_analyzed=2,
        created_at=datetime.utcnow(),
    )
    defaults.update(overrides)
    return AssessmentSummary(**defaults)


@pytest.fixture(autouse=True)
def clean_stores():
    """Clean all stores before each test."""
    assessments_store.clear()
    _running_pipelines.clear()
    yield
    assessments_store.clear()
    _running_pipelines.clear()


# ──────────────────────────────────────────────
# 🏦 Credit Domain Expert — Pipeline Produces Correct Results
# ──────────────────────────────────────────────

class TestCreditPipelineFlow:
    """🏦 Pipeline must produce correct credit assessment results."""

    def test_pipeline_status_shows_pending_before_run(self):
        """Status endpoint shows PENDING before pipeline starts."""
        assessment = _make_assessment("credit-001")
        assessments_store["credit-001"] = assessment

        resp = client.get("/api/pipeline/credit-001/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_running"] is False
        assert data["outcome"] == "PENDING"
        assert data["score"] is None

    def test_pipeline_status_shows_stage_progress(self):
        """Status shows completed vs pending stages."""
        assessment = _make_assessment("credit-002")
        # Simulate some stages completed
        assessment.pipeline_stages[0].status = PipelineStageStatus.COMPLETED
        assessment.pipeline_stages[1].status = PipelineStageStatus.COMPLETED
        assessment.pipeline_stages[2].status = PipelineStageStatus.ACTIVE
        assessments_store["credit-002"] = assessment

        resp = client.get("/api/pipeline/credit-002/status")
        data = resp.json()
        assert data["progress"]["completed"] == 2
        assert data["current_stage"] == PipelineStageEnum.CONSOLIDATION.value

    def test_pipeline_status_shows_score_when_complete(self):
        """Status shows score and band when pipeline is done."""
        assessment = _make_assessment("credit-003")
        assessment.score = 477
        assessment.score_band = ScoreBand.POOR
        assessment.outcome = AssessmentOutcome.CONDITIONAL
        for stage in assessment.pipeline_stages:
            stage.status = PipelineStageStatus.COMPLETED
        assessments_store["credit-003"] = assessment

        resp = client.get("/api/pipeline/credit-003/status")
        data = resp.json()
        assert data["score"] == 477
        assert data["score_band"] == "Poor"
        assert data["outcome"] == "CONDITIONAL"
        assert data["progress"]["percent"] == 100

    @pytest.mark.asyncio
    async def test_execute_pipeline_updates_store(self):
        """🏦 Background execution updates the assessment store with results."""
        assessment = _make_assessment("credit-004")
        assessments_store["credit-004"] = assessment

        # Mock run_pipeline to return a successful state dict
        mock_state = {
            "score": 650,
            "score_band": ScoreBand.GOOD,
            "outcome": AssessmentOutcome.CONDITIONAL,
            "cam_path": "/data/cam/credit-004.docx",
            "pipeline_stages": assessment.pipeline_stages,
        }

        with patch("backend.api.routes.pipeline.run_pipeline", new_callable=AsyncMock, return_value=mock_state):
            await _execute_pipeline("credit-004")

        updated = assessments_store["credit-004"]
        assert updated.score == 650
        assert updated.score_band == ScoreBand.GOOD
        assert updated.outcome == AssessmentOutcome.CONDITIONAL
        assert updated.cam_path == "/data/cam/credit-004.docx"

    @pytest.mark.asyncio
    async def test_execute_pipeline_marks_stages_completed(self):
        """Pipeline execution marks all stages as completed."""
        assessment = _make_assessment("credit-005")
        assessments_store["credit-005"] = assessment

        mock_state = {"score": 700, "score_band": ScoreBand.GOOD, "outcome": AssessmentOutcome.APPROVED}
        with patch("backend.api.routes.pipeline.run_pipeline", new_callable=AsyncMock, return_value=mock_state):
            await _execute_pipeline("credit-005")

        updated = assessments_store["credit-005"]
        for stage in updated.pipeline_stages:
            assert stage.status == PipelineStageStatus.COMPLETED


# ──────────────────────────────────────────────
# 🔒 Security Architect — Session Isolation & Validation
# ──────────────────────────────────────────────

class TestSecurityPipeline:
    """🔒 Pipeline endpoints must validate inputs and prevent abuse."""

    def test_trigger_nonexistent_session_returns_404(self):
        """Cannot trigger pipeline for non-existent session."""
        resp = client.post("/api/pipeline/fake-session/run")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_status_nonexistent_session_returns_404(self):
        """Cannot get status for non-existent session."""
        resp = client.get("/api/pipeline/nonexistent/status")
        assert resp.status_code == 404

    def test_cancel_nonexistent_session_returns_404(self):
        """Cannot cancel non-existent session."""
        resp = client.post("/api/pipeline/nonexistent/cancel")
        assert resp.status_code == 404

    def test_double_trigger_returns_409(self):
        """Cannot trigger pipeline twice for same session (race prevention)."""
        assessment = _make_assessment("sec-001")
        assessments_store["sec-001"] = assessment
        _running_pipelines["sec-001"] = True  # Simulate running

        resp = client.post("/api/pipeline/sec-001/run")
        assert resp.status_code == 409
        assert "already running" in resp.json()["detail"].lower()

    def test_cancel_not_running_returns_409(self):
        """Cannot cancel a pipeline that is not running."""
        assessment = _make_assessment("sec-002")
        assessments_store["sec-002"] = assessment

        resp = client.post("/api/pipeline/sec-002/cancel")
        assert resp.status_code == 409
        assert "no running pipeline" in resp.json()["detail"].lower()

    def test_session_isolation_status(self):
        """Status of one session doesn't leak into another."""
        a1 = _make_assessment("sec-003")
        a1.score = 700
        a2 = _make_assessment("sec-004")
        a2.score = 400
        assessments_store["sec-003"] = a1
        assessments_store["sec-004"] = a2

        r1 = client.get("/api/pipeline/sec-003/status")
        r2 = client.get("/api/pipeline/sec-004/status")
        assert r1.json()["score"] == 700
        assert r2.json()["score"] == 400


# ──────────────────────────────────────────────
# ⚙️ Systems Engineer — Reliability & State Consistency
# ──────────────────────────────────────────────

class TestReliabilityPipeline:
    """⚙️ Pipeline must handle failures gracefully."""

    @pytest.mark.asyncio
    async def test_pipeline_failure_marks_stage_failed(self):
        """When pipeline crashes, current stage marked FAILED."""
        assessment = _make_assessment("rel-001")
        assessments_store["rel-001"] = assessment

        with patch(
            "backend.api.routes.pipeline.run_pipeline",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Neo4j connection refused"),
        ):
            await _execute_pipeline("rel-001")

        updated = assessments_store["rel-001"]
        # Check at least one stage is failed
        failed = [s for s in updated.pipeline_stages if s.status == PipelineStageStatus.FAILED]
        assert len(failed) >= 1
        assert "Neo4j connection refused" in failed[0].message

    @pytest.mark.asyncio
    async def test_pipeline_failure_records_error(self):
        """Pipeline error stored in assessment."""
        assessment = _make_assessment("rel-002")
        assessments_store["rel-002"] = assessment

        with patch(
            "backend.api.routes.pipeline.run_pipeline",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid DSCR computation"),
        ):
            await _execute_pipeline("rel-002")

        updated = assessments_store["rel-002"]
        assert updated.error == "Invalid DSCR computation"

    @pytest.mark.asyncio
    async def test_pipeline_cleans_running_flag_on_success(self):
        """Running flag cleaned up after successful pipeline."""
        assessment = _make_assessment("rel-003")
        assessments_store["rel-003"] = assessment

        mock_state = {"score": 600, "outcome": AssessmentOutcome.CONDITIONAL}
        with patch("backend.api.routes.pipeline.run_pipeline", new_callable=AsyncMock, return_value=mock_state):
            await _execute_pipeline("rel-003")

        assert "rel-003" not in _running_pipelines

    @pytest.mark.asyncio
    async def test_pipeline_cleans_running_flag_on_failure(self):
        """Running flag cleaned up even when pipeline fails."""
        assessment = _make_assessment("rel-004")
        assessments_store["rel-004"] = assessment

        with patch(
            "backend.api.routes.pipeline.run_pipeline",
            new_callable=AsyncMock,
            side_effect=Exception("Catastrophic failure"),
        ):
            await _execute_pipeline("rel-004")

        assert "rel-004" not in _running_pipelines

    @pytest.mark.asyncio
    async def test_execute_pipeline_missing_session_no_crash(self):
        """_execute_pipeline silently returns if session doesn't exist."""
        await _execute_pipeline("nonexistent-session")
        # Should not raise — just log and return

    def test_status_progress_percent_zero_stages(self):
        """Progress percent handles zero-stage edge case."""
        assessment = _make_assessment("rel-005")
        assessment.pipeline_stages = []  # Edge: no stages
        assessments_store["rel-005"] = assessment

        resp = client.get("/api/pipeline/rel-005/status")
        data = resp.json()
        assert data["progress"]["percent"] == 0
        assert data["progress"]["total"] == 0


# ──────────────────────────────────────────────
# 🧪 QA Engineer — Edge Cases & Regression
# ──────────────────────────────────────────────

class TestEdgeCasesPipeline:
    """🧪 Edge cases and boundary conditions for pipeline endpoints."""

    def test_trigger_returns_202_accepted(self):
        """Trigger endpoint returns 202 (Accepted), not 200."""
        assessment = _make_assessment("qa-001")
        assessments_store["qa-001"] = assessment

        resp = client.post("/api/pipeline/qa-001/run")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "pipeline_started"
        assert "qa-001" in data["session_id"]

    def test_cancel_marks_stage_failed(self):
        """Cancel marks in-progress stage as failed with message."""
        assessment = _make_assessment("qa-002")
        assessment.pipeline_stages[1].status = PipelineStageStatus.ACTIVE
        assessments_store["qa-002"] = assessment
        _running_pipelines["qa-002"] = True

        resp = client.post("/api/pipeline/qa-002/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Check stage was marked
        updated = assessments_store["qa-002"]
        workers_stage = updated.pipeline_stages[1]
        assert workers_stage.status == PipelineStageStatus.FAILED
        assert "cancelled" in workers_stage.message.lower()

    def test_cancel_removes_running_flag(self):
        """Cancel removes session from running pipelines."""
        assessment = _make_assessment("qa-003")
        assessments_store["qa-003"] = assessment
        _running_pipelines["qa-003"] = True

        client.post("/api/pipeline/qa-003/cancel")
        assert "qa-003" not in _running_pipelines

    def test_status_no_in_progress_stage(self):
        """Status current_stage is null when nothing is in progress."""
        assessment = _make_assessment("qa-004")
        assessments_store["qa-004"] = assessment

        resp = client.get("/api/pipeline/qa-004/status")
        data = resp.json()
        assert data["current_stage"] is None

    def test_status_counts_failed_stages(self):
        """Status counts failed stages separately."""
        assessment = _make_assessment("qa-005")
        assessment.pipeline_stages[1].status = PipelineStageStatus.FAILED
        assessment.pipeline_stages[1].message = "Worker timeout"
        assessments_store["qa-005"] = assessment

        resp = client.get("/api/pipeline/qa-005/status")
        data = resp.json()
        assert data["progress"]["failed"] == 1

    def test_status_stage_timestamps(self):
        """Status includes stage timestamps."""
        assessment = _make_assessment("qa-006")
        now = datetime.utcnow()
        assessment.pipeline_stages[0].started_at = now
        assessment.pipeline_stages[0].completed_at = now
        assessments_store["qa-006"] = assessment

        resp = client.get("/api/pipeline/qa-006/status")
        stages = resp.json()["stages"]
        upload_stage = stages[0]
        assert upload_stage["started_at"] is not None
        assert upload_stage["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_execute_pipeline_with_pydantic_state_object(self):
        """Pipeline handles both dict and Pydantic state returns."""
        assessment = _make_assessment("qa-007")
        assessments_store["qa-007"] = assessment

        # Return a non-dict object to test the __dict__ fallback path
        class FakeState:
            def __init__(self):
                self.score = 550
                self.score_band = ScoreBand.FAIR
                self.outcome = AssessmentOutcome.CONDITIONAL
                self.cam_path = None
                self.pipeline_stages = []

        with patch("backend.api.routes.pipeline.run_pipeline", new_callable=AsyncMock, return_value=FakeState()):
            await _execute_pipeline("qa-007")

        updated = assessments_store["qa-007"]
        assert updated.score == 550


# ──────────────────────────────────────────────
# 🎯 Hackathon Judge — E2E Demo Flow
# ──────────────────────────────────────────────

class TestDemoPipeline:
    """🎯 Pipeline endpoints support compelling demo flow."""

    def test_trigger_response_includes_tracking_info(self):
        """Trigger response tells the user how to track progress."""
        assessment = _make_assessment("demo-001")
        assessments_store["demo-001"] = assessment

        resp = client.post("/api/pipeline/demo-001/run")
        data = resp.json()
        assert "session_id" in data
        assert "status" in data
        assert "message" in data
        assert "progress" in data["message"].lower() or "track" in data["message"].lower()

    def test_status_response_tells_complete_story(self):
        """Status response has all fields a demo needs."""
        assessment = _make_assessment("demo-002")
        assessment.score = 477
        assessment.score_band = ScoreBand.POOR
        assessment.outcome = AssessmentOutcome.CONDITIONAL
        for s in assessment.pipeline_stages:
            s.status = PipelineStageStatus.COMPLETED
        assessments_store["demo-002"] = assessment

        resp = client.get("/api/pipeline/demo-002/status")
        data = resp.json()

        # All fields present for demo
        assert "session_id" in data
        assert "is_running" in data
        assert "outcome" in data
        assert "score" in data
        assert "score_band" in data
        assert "progress" in data
        assert "stages" in data
        assert len(data["stages"]) == 10  # All 10 pipeline stages

    def test_full_lifecycle_trigger_status_cancel(self):
        """Full lifecycle: trigger → check status → cancel."""
        assessment = _make_assessment("demo-003")
        assessments_store["demo-003"] = assessment

        # 1. Trigger
        r1 = client.post("/api/pipeline/demo-003/run")
        assert r1.status_code == 202

        # 2. Simulate running
        _running_pipelines["demo-003"] = True
        assessment.pipeline_stages[1].status = PipelineStageStatus.ACTIVE

        # 3. Status while running
        r2 = client.get("/api/pipeline/demo-003/status")
        assert r2.json()["is_running"] is True
        assert r2.json()["current_stage"] is not None

        # 4. Cancel
        r3 = client.post("/api/pipeline/demo-003/cancel")
        assert r3.status_code == 200
        assert r3.json()["status"] == "cancelled"

    def test_upload_has_auto_run_param(self):
        """Upload endpoint accepts auto_run parameter."""
        # Just verify the endpoint accepts auto_run by checking it doesn't error
        # with minimal form data (no files needed)
        resp = client.post(
            "/api/upload",
            data={
                "company_name": "Demo Corp",
                "sector": "IT",
                "loan_type": "Term Loan",
                "loan_amount": "₹25 Crore",
                "loan_amount_numeric": 25.0,
                "auto_run": "true",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["company"]["name"] == "Demo Corp"

    @pytest.mark.asyncio
    async def test_pipeline_produces_processing_time(self):
        """Pipeline records processing time for demo display."""
        assessment = _make_assessment("demo-005")
        assessments_store["demo-005"] = assessment

        mock_state = {"score": 477, "outcome": AssessmentOutcome.CONDITIONAL}
        with patch("backend.api.routes.pipeline.run_pipeline", new_callable=AsyncMock, return_value=mock_state):
            await _execute_pipeline("demo-005")

        updated = assessments_store["demo-005"]
        assert updated.processing_time is not None
        assert len(updated.processing_time) > 0
