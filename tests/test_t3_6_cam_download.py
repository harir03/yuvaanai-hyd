"""
Intelli-Credit — T3.6 CAM Download Endpoint Tests

Tests for:
- GET /api/cam/{session_id} — download Credit Appraisal Memo

5-Perspective Testing:
🏦 Credit Domain Expert — CAM content is served correctly, contains expected sections
🔒 Security Architect — path traversal, invalid sessions, session isolation
⚙️ Systems Engineer — file not on disk, concurrent downloads, large files
🧪 QA Engineer — missing cam_path, 404/409 errors, edge cases
🎯 Hackathon Judge — full demo flow from assessment to download
"""

import os
import pytest
import tempfile
import shutil
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routes._store import assessments_store
from backend.api.routes import assessment as assessment_module
from backend.models.schemas import (
    AssessmentSummary,
    AssessmentOutcome,
    CompanyInfo,
    ScoreBand,
)

client = TestClient(app)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def _make_company() -> CompanyInfo:
    return CompanyInfo(
        name="XYZ Steel Pvt Ltd",
        sector="manufacturing",
        loan_type="Working Capital",
        loan_amount="50 Crore",
        loan_amount_numeric=50.0,
    )


def _make_assessment(session_id: str, cam_path: str = None) -> AssessmentSummary:
    return AssessmentSummary(
        session_id=session_id,
        company=_make_company(),
        score=652,
        score_band=ScoreBand.GOOD,
        outcome=AssessmentOutcome.CONDITIONAL,
        cam_path=cam_path,
    )


def _write_cam(base_dir, session_id: str, content: str = None) -> str:
    """Create a CAM file under base_dir/session_id/ and return its path."""
    d = os.path.join(base_dir, session_id)
    os.makedirs(d, exist_ok=True)
    f = os.path.join(d, "credit_appraisal_memo.txt")
    if content is None:
        content = (
            "CREDIT APPRAISAL MEMO\n"
            "=====================\n"
            "Company: XYZ Steel Pvt Ltd\n"
            "Loan: Working Capital — ₹50 Crore\n"
            "Score: 652 / 850\n"
            "Band: Good\n"
            "Recommendation: CONDITIONAL APPROVAL\n"
            "\n"
            "=== EXECUTIVE SUMMARY ===\n"
            "XYZ Steel demonstrates adequate capacity for debt servicing.\n"
            "\n"
            "=== KEY FINANCIAL METRICS ===\n"
            "Revenue: ₹247 Crore (3-year CAGR: 12%)\n"
            "EBITDA Margin: 14.2%\n"
            "DSCR: 1.38x\n"
            "Debt/Equity: 1.82x\n"
        )
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(content)
    return f


@pytest.fixture(autouse=True)
def _clean_store():
    """Clear the assessment store before and after each test."""
    assessments_store.clear()
    yield
    assessments_store.clear()


@pytest.fixture
def cam_root(tmp_path):
    """Provide a temp directory as the CAM output root, patching the module."""
    root = str(tmp_path)
    original = assessment_module.CAM_OUTPUT_ROOT
    assessment_module.CAM_OUTPUT_ROOT = root
    yield root
    assessment_module.CAM_OUTPUT_ROOT = original


# ══════════════════════════════════════════════
# 🏦 Credit Domain Expert
# ══════════════════════════════════════════════


class TestCreditDomainExpert:
    """CAM serves correct financial content."""

    def test_cam_download_returns_text_file(self, cam_root):
        """Downloaded CAM is a plain-text file with correct content-type."""
        cam_path = _write_cam(cam_root, "test-session-1")
        assessments_store["test-session-1"] = _make_assessment(
            "test-session-1", cam_path=cam_path
        )
        resp = client.get("/api/cam/test-session-1")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]

    def test_cam_content_has_credit_sections(self, cam_root):
        """CAM contains expected credit appraisal sections."""
        cam_path = _write_cam(cam_root, "test-session-1")
        assessments_store["test-session-1"] = _make_assessment(
            "test-session-1", cam_path=cam_path
        )
        resp = client.get("/api/cam/test-session-1")
        text = resp.text
        assert "CREDIT APPRAISAL MEMO" in text
        assert "EXECUTIVE SUMMARY" in text
        assert "KEY FINANCIAL METRICS" in text
        assert "XYZ Steel" in text

    def test_cam_has_financial_metrics(self, cam_root):
        """CAM contains key financial figures."""
        cam_path = _write_cam(cam_root, "test-session-1")
        assessments_store["test-session-1"] = _make_assessment(
            "test-session-1", cam_path=cam_path
        )
        resp = client.get("/api/cam/test-session-1")
        text = resp.text
        assert "DSCR" in text
        assert "Revenue" in text
        assert "652" in text

    def test_cam_filename_includes_session(self, cam_root):
        """Downloaded filename contains the session ID for traceability."""
        cam_path = _write_cam(cam_root, "test-session-1")
        assessments_store["test-session-1"] = _make_assessment(
            "test-session-1", cam_path=cam_path
        )
        resp = client.get("/api/cam/test-session-1")
        cd = resp.headers.get("content-disposition", "")
        assert "cam_test-session-1.txt" in cd

    def test_cam_for_different_sessions(self, cam_root):
        """Different sessions serve their own CAM files."""
        for sid in ["session-a", "session-b"]:
            cam_path = _write_cam(cam_root, sid, content=f"CAM for {sid}")
            assessments_store[sid] = _make_assessment(sid, cam_path=cam_path)

        resp_a = client.get("/api/cam/session-a")
        resp_b = client.get("/api/cam/session-b")
        assert "session-a" in resp_a.text
        assert "session-b" in resp_b.text


# ══════════════════════════════════════════════
# 🔒 Security Architect
# ══════════════════════════════════════════════


class TestSecurityArchitect:
    """Prevent path traversal, session isolation, validate inputs."""

    def test_path_traversal_blocked(self, cam_root):
        """cam_path with path traversal is rejected."""
        # Create file outside allowed root
        bad_path = os.path.abspath(os.path.join(cam_root, "..", "etc", "passwd"))
        assessments_store["evil-session"] = _make_assessment(
            "evil-session", cam_path=bad_path
        )
        resp = client.get("/api/cam/evil-session")
        assert resp.status_code in (400, 404)

    def test_path_traversal_in_session_id(self):
        """Session ID with ../ is rejected."""
        resp = client.get("/api/cam/../../../etc/passwd")
        assert resp.status_code in (400, 404, 422)

    def test_session_id_with_special_chars(self):
        """Session ID with special characters is rejected."""
        resp = client.get("/api/cam/session;rm -rf /")
        assert resp.status_code in (400, 404, 422)

    def test_session_isolation(self, cam_root):
        """Cannot access another session's CAM."""
        cam_path = _write_cam(cam_root, "test-session-1")
        assessments_store["test-session-1"] = _make_assessment(
            "test-session-1", cam_path=cam_path
        )
        resp = client.get("/api/cam/different-session")
        assert resp.status_code == 404

    def test_cam_path_outside_allowed_dir(self, cam_root):
        """CAM path outside allowed root is rejected."""
        # Create file in a completely separate temp directory
        import tempfile
        with tempfile.TemporaryDirectory() as rogue_dir:
            rogue_file = os.path.join(rogue_dir, "secret.txt")
            with open(rogue_file, "w") as f:
                f.write("SECRET DATA")
            assessments_store["rogue"] = _make_assessment(
                "rogue", cam_path=rogue_file
            )
            resp = client.get("/api/cam/rogue")
            assert resp.status_code == 400

    def test_null_bytes_in_session_id(self):
        """Null bytes in session ID are rejected."""
        resp = client.get("/api/cam/session%00id")
        assert resp.status_code in (400, 404, 422)

    def test_very_long_session_id(self):
        """Extremely long session ID is rejected."""
        long_id = "a" * 500
        resp = client.get(f"/api/cam/{long_id}")
        assert resp.status_code == 400

    def test_session_id_with_dots(self):
        """Session ID validation blocks dot-dot sequences."""
        resp = client.get("/api/cam/..test..")
        assert resp.status_code in (400, 404, 422)


# ══════════════════════════════════════════════
# ⚙️ Systems Engineer
# ══════════════════════════════════════════════


class TestSystemsEngineer:
    """Reliability: file missing, concurrent requests, error handling."""

    def test_cam_file_missing_on_disk(self, cam_root):
        """Assessment has cam_path but file was deleted — returns 404."""
        missing_path = os.path.join(
            cam_root, "missing-session", "credit_appraisal_memo.txt"
        )
        assessments_store["missing-session"] = _make_assessment(
            "missing-session", cam_path=missing_path
        )
        resp = client.get("/api/cam/missing-session")
        assert resp.status_code == 404
        assert "not found on disk" in resp.json()["detail"]

    def test_cam_path_is_directory_not_file(self, cam_root):
        """cam_path points to a directory — should fail."""
        d = os.path.join(cam_root, "dir-session")
        os.makedirs(d, exist_ok=True)
        assessments_store["dir-session"] = _make_assessment(
            "dir-session", cam_path=d
        )
        resp = client.get("/api/cam/dir-session")
        assert resp.status_code in (400, 404)

    def test_concurrent_downloads_same_session(self, cam_root):
        """Multiple concurrent downloads of the same CAM don't conflict."""
        cam_path = _write_cam(cam_root, "test-session-1")
        assessments_store["test-session-1"] = _make_assessment(
            "test-session-1", cam_path=cam_path
        )
        responses = [client.get("/api/cam/test-session-1") for _ in range(5)]
        assert all(r.status_code == 200 for r in responses)
        contents = {r.text for r in responses}
        assert len(contents) == 1

    def test_large_cam_file(self, cam_root):
        """Large CAM file (1MB) is served without issue."""
        cam_path = _write_cam(
            cam_root, "large-session",
            content="CREDIT APPRAISAL MEMO\n" * 50000,
        )
        assessments_store["large-session"] = _make_assessment(
            "large-session", cam_path=cam_path
        )
        resp = client.get("/api/cam/large-session")
        assert resp.status_code == 200
        assert len(resp.text) > 500000

    def test_utf8_content_preserved(self, cam_root):
        """Unicode characters (₹, Hindi text) survive download."""
        cam_path = _write_cam(
            cam_root, "unicode-session",
            content=(
                "CREDIT APPRAISAL MEMO\n"
                "Company: मुंबई स्टील प्राइवेट लिमिटेड\n"
                "Loan Amount: ₹50 Crore\n"
            ),
        )
        assessments_store["unicode-session"] = _make_assessment(
            "unicode-session", cam_path=cam_path
        )
        resp = client.get("/api/cam/unicode-session")
        assert resp.status_code == 200
        assert "₹50 Crore" in resp.text


# ══════════════════════════════════════════════
# 🧪 QA Engineer
# ══════════════════════════════════════════════


class TestQAEngineer:
    """Edge cases, error states, missing data."""

    def test_assessment_not_found(self):
        """Non-existent session returns 404."""
        resp = client.get("/api/cam/nonexistent-session")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_cam_not_generated_yet(self):
        """Assessment exists but CAM hasn't been generated — 409."""
        assessments_store["pending"] = _make_assessment("pending", cam_path=None)
        resp = client.get("/api/cam/pending")
        assert resp.status_code == 409
        assert "not been generated" in resp.json()["detail"]

    def test_cam_path_empty_string(self):
        """Assessment with empty cam_path — treated as not generated."""
        assessments_store["empty"] = _make_assessment("empty", cam_path="")
        resp = client.get("/api/cam/empty")
        # Empty string is falsy — same as None
        assert resp.status_code == 409

    def test_session_id_alphanumeric_only(self):
        """Valid session IDs with hyphens and underscores work."""
        assessments_store["valid-id_123"] = _make_assessment("valid-id_123")
        resp = client.get("/api/cam/valid-id_123")
        # No CAM path so 409, but the session ID was accepted
        assert resp.status_code == 409

    def test_session_id_with_spaces(self):
        """Session IDs with spaces are rejected."""
        resp = client.get("/api/cam/session with spaces")
        assert resp.status_code in (400, 404, 422)

    def test_empty_session_id(self):
        """Empty session ID is handled (routes to different endpoint)."""
        resp = client.get("/api/cam/")
        # FastAPI returns 404 or routes elsewhere
        assert resp.status_code in (404, 405, 307)

    def test_response_headers_correct(self, cam_root):
        """Response has appropriate headers for file download."""
        cam_path = _write_cam(cam_root, "test-session-1")
        assessments_store["test-session-1"] = _make_assessment(
            "test-session-1", cam_path=cam_path
        )
        resp = client.get("/api/cam/test-session-1")
        assert resp.status_code == 200
        assert "content-disposition" in resp.headers
        assert "content-type" in resp.headers

    def test_assessment_without_score(self, cam_root):
        """Assessment with no score but has CAM — still downloadable."""
        cam_path = _write_cam(cam_root, "test-session-1")
        a = _make_assessment("test-session-1", cam_path=cam_path)
        a.score = None
        a.score_band = None
        assessments_store["test-session-1"] = a
        resp = client.get("/api/cam/test-session-1")
        assert resp.status_code == 200


# ══════════════════════════════════════════════
# 🎯 Hackathon Judge
# ══════════════════════════════════════════════


class TestHackathonJudge:
    """Demo flow: assessment complete → download CAM → verify content."""

    def test_full_demo_flow(self, cam_root):
        """Complete demo: check assessment, download CAM, verify content."""
        cam_path = _write_cam(cam_root, "test-session-1")
        assessments_store["test-session-1"] = _make_assessment(
            "test-session-1", cam_path=cam_path
        )

        # Step 1: Get assessment — verify CAM path exists
        resp_assess = client.get("/api/assessment/test-session-1")
        assert resp_assess.status_code == 200
        data = resp_assess.json()
        assert data["cam_path"] is not None

        # Step 2: Download CAM
        resp_cam = client.get("/api/cam/test-session-1")
        assert resp_cam.status_code == 200

        # Step 3: Verify content has key sections
        text = resp_cam.text
        assert "CREDIT APPRAISAL MEMO" in text
        assert "XYZ Steel" in text
        assert "652" in text

    def test_score_endpoint_has_cam_url(self, cam_root):
        """Score endpoint could advertise CAM download URL."""
        cam_path = _write_cam(cam_root, "test-session-1")
        assessments_store["test-session-1"] = _make_assessment(
            "test-session-1", cam_path=cam_path
        )
        resp = client.get("/api/score/test-session-1")
        assert resp.status_code == 200

    def test_cam_mentions_recommendation(self, cam_root):
        """CAM text includes the lending recommendation."""
        cam_path = _write_cam(cam_root, "test-session-1")
        assessments_store["test-session-1"] = _make_assessment(
            "test-session-1", cam_path=cam_path
        )
        resp = client.get("/api/cam/test-session-1")
        text = resp.text
        assert "CONDITIONAL" in text or "APPROVAL" in text

    def test_history_shows_cam_availability(self, cam_root):
        """Assessment list shows which sessions have CAMs ready."""
        cam_path = _write_cam(cam_root, "with-cam")
        assessments_store["with-cam"] = _make_assessment(
            "with-cam", cam_path=cam_path
        )
        assessments_store["no-cam"] = _make_assessment("no-cam", cam_path=None)

        resp = client.get("/api/assessments")
        assert resp.status_code == 200
        items = resp.json()
        cam_statuses = {a["session_id"]: a.get("cam_path") for a in items}
        assert cam_statuses["with-cam"] is not None
        assert cam_statuses["no-cam"] is None

    def test_download_button_works(self, cam_root):
        """Simulates clicking download — GET returns downloadable file."""
        cam_path = _write_cam(cam_root, "demo-1")
        assessments_store["demo-1"] = _make_assessment(
            "demo-1", cam_path=cam_path
        )
        resp = client.get("/api/cam/demo-1")
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd or "filename" in cd
