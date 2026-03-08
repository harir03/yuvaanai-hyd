"""
T2.5 — Decision Store + History Tests

Tests GET /api/decisions, GET /api/decisions/{session_id},
POST /api/decisions/{session_id}/notes, and new Pydantic models.
"""

from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.api.routes._store import assessments_store, officer_notes_store
from backend.models.schemas import (
    AddNoteRequest,
    AssessmentOutcome,
    AssessmentSummary,
    CompanyInfo,
    DecisionRecord,
    HistoryRecord,
    OfficerNote,
    ScoreBand,
    ScoreBreakdownEntry,
    ScoreModule,
    ScoreModuleSummary,
)
from config.scoring_constants import LOAN_EXCELLENT_SANCTION_PCT, LOAN_EXCELLENT_RATE


# ── fixtures ──


@pytest.fixture(autouse=True)
def _clear_stores():
    assessments_store.clear()
    officer_notes_store.clear()
    yield
    assessments_store.clear()
    officer_notes_store.clear()


def _make_company(name="TestCorp", sector="Manufacturing"):
    return CompanyInfo(
        name=name,
        sector=sector,
        loan_type="Working Capital",
        loan_amount="₹50 Cr",
        loan_amount_numeric=5000.0,
    )


def _make_assessment(
    session_id="sess-1",
    name="TestCorp",
    sector="Manufacturing",
    score=650,
    band=ScoreBand.GOOD,
    outcome=AssessmentOutcome.APPROVED,
    created_at=None,
) -> AssessmentSummary:
    return AssessmentSummary(
        session_id=session_id,
        company=_make_company(name, sector),
        score=score,
        score_band=band,
        outcome=outcome,
        created_at=created_at or datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )


# ── GET /api/decisions ──


@pytest.mark.asyncio
async def test_list_decisions_empty():
    """Returns empty list when no assessments exist."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_decisions_returns_all():
    """Returns all assessments as HistoryRecords."""
    assessments_store["s1"] = _make_assessment("s1", "Corp A")
    assessments_store["s2"] = _make_assessment("s2", "Corp B")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_decisions_filter_sector():
    """Filters by sector."""
    assessments_store["s1"] = _make_assessment("s1", "Steel Co", "Manufacturing")
    assessments_store["s2"] = _make_assessment("s2", "IT Co", "IT")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions?sector=IT")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["company_name"] == "IT Co"


@pytest.mark.asyncio
async def test_list_decisions_filter_band():
    """Filters by score band."""
    assessments_store["s1"] = _make_assessment("s1", band=ScoreBand.GOOD)
    assessments_store["s2"] = _make_assessment("s2", band=ScoreBand.POOR)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions?band=Good")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["session_id"] == "s1"


@pytest.mark.asyncio
async def test_list_decisions_filter_outcome():
    """Filters by assessment outcome."""
    assessments_store["s1"] = _make_assessment("s1", outcome=AssessmentOutcome.APPROVED)
    assessments_store["s2"] = _make_assessment("s2", outcome=AssessmentOutcome.REJECTED)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions?outcome=REJECTED")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["session_id"] == "s2"


@pytest.mark.asyncio
async def test_list_decisions_pagination():
    """Supports limit and offset."""
    for i in range(5):
        assessments_store[f"s{i}"] = _make_assessment(
            f"s{i}",
            created_at=datetime.utcnow() - timedelta(hours=i),
        )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions?limit=2&offset=0")
    data = resp.json()
    assert len(data) == 2
    # Newest first
    assert data[0]["session_id"] == "s0"


@pytest.mark.asyncio
async def test_list_decisions_offset_pagination():
    """Offset skips records."""
    for i in range(5):
        assessments_store[f"s{i}"] = _make_assessment(
            f"s{i}",
            created_at=datetime.utcnow() - timedelta(hours=i),
        )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions?limit=2&offset=2")
    data = resp.json()
    assert len(data) == 2
    assert data[0]["session_id"] == "s2"


@pytest.mark.asyncio
async def test_list_decisions_sorted_newest_first():
    """Results sorted by created_at descending."""
    assessments_store["old"] = _make_assessment(
        "old", created_at=datetime.utcnow() - timedelta(days=10)
    )
    assessments_store["new"] = _make_assessment(
        "new", created_at=datetime.utcnow()
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions")
    data = resp.json()
    assert data[0]["session_id"] == "new"
    assert data[1]["session_id"] == "old"


# ── GET /api/decisions/{session_id} ──


@pytest.mark.asyncio
async def test_get_decision_success():
    """Returns full DecisionRecord."""
    assessments_store["s1"] = _make_assessment("s1")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions/s1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "s1"
    assert data["company_name"] == "TestCorp"
    assert data["score"] == 650
    assert data["officer_notes"] == []


@pytest.mark.asyncio
async def test_get_decision_not_found():
    """Returns 404 for unknown session."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_decision_includes_loan_terms():
    """DecisionRecord includes loan terms when scored."""
    assessments_store["s1"] = _make_assessment("s1", band=ScoreBand.EXCELLENT, score=800)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions/s1")
    terms = resp.json()["loan_terms"]
    assert terms["sanction_pct"] == int(LOAN_EXCELLENT_SANCTION_PCT)
    assert terms["rate"] == LOAN_EXCELLENT_RATE


@pytest.mark.asyncio
async def test_get_decision_no_loan_terms_when_unscored():
    """DecisionRecord has null loan_terms when not scored."""
    a = _make_assessment("s1")
    a.score = None
    a.score_band = None
    assessments_store["s1"] = a
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions/s1")
    assert resp.json()["loan_terms"] is None


@pytest.mark.asyncio
async def test_get_decision_with_notes():
    """DecisionRecord includes officer notes."""
    assessments_store["s1"] = _make_assessment("s1")
    officer_notes_store["s1"] = [
        OfficerNote(text="Looks good", author="John"),
    ]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/decisions/s1")
    notes = resp.json()["officer_notes"]
    assert len(notes) == 1
    assert notes[0]["text"] == "Looks good"


# ── POST /api/decisions/{session_id}/notes ──


@pytest.mark.asyncio
async def test_add_note_success():
    """POST creates a note and returns it."""
    assessments_store["s1"] = _make_assessment("s1")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/decisions/s1/notes",
            json={"text": "Reviewed financials", "author": "Jane"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Reviewed financials"
    assert data["author"] == "Jane"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_add_note_not_found():
    """POST returns 404 for unknown session."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/decisions/nonexistent/notes",
            json={"text": "Note"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_note_persists():
    """Added note appears in subsequent GET."""
    assessments_store["s1"] = _make_assessment("s1")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.post("/api/decisions/s1/notes", json={"text": "First note"})
        await ac.post("/api/decisions/s1/notes", json={"text": "Second note"})
        resp = await ac.get("/api/decisions/s1")
    notes = resp.json()["officer_notes"]
    assert len(notes) == 2


@pytest.mark.asyncio
async def test_add_note_empty_text_rejected():
    """POST rejects empty text."""
    assessments_store["s1"] = _make_assessment("s1")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/decisions/s1/notes",
            json={"text": ""},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_note_default_author():
    """POST uses default author when not specified."""
    assessments_store["s1"] = _make_assessment("s1")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/decisions/s1/notes", json={"text": "Note"})
    assert resp.json()["author"] == "Credit Officer"


# ── Model tests ──


def test_decision_record_model():
    """DecisionRecord validates correctly."""
    r = DecisionRecord(
        session_id="s1",
        company_name="X",
        sector="IT",
        loan_type="WC",
        loan_amount="10Cr",
        score=500,
        score_band=ScoreBand.POOR,
        outcome=AssessmentOutcome.CONDITIONAL,
    )
    assert r.officer_notes == []
    assert r.modules == []


def test_officer_note_model():
    """OfficerNote has auto-generated id and timestamp."""
    n = OfficerNote(text="Test")
    assert n.id
    assert n.created_at
    assert n.author == "Credit Officer"


def test_add_note_request_validation():
    """AddNoteRequest enforces min_length."""
    with pytest.raises(Exception):
        AddNoteRequest(text="")
