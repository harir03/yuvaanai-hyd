"""
T1.7 — Ticket Resolution Interface (Backend)

Tests:
  Section 1: ticket_node (LangGraph node)
    1. No tickets — pipeline proceeds, no blocking
    2. LOW only — pipeline continues, no blocking
    3. HIGH tickets — pipeline blocked
    4. CRITICAL tickets — pipeline blocked
    5. Mixed tickets — blocking if any HIGH/CRITICAL
    6. Already resolved tickets — not blocking
    7. Precedent lookup — finds similar resolved tickets
    8. ThinkingEvents — correct event types emitted

  Section 2: get_ticket_statistics
    9. Empty tickets — zeroed stats
   10. Mixed tickets — correct counts
   11. Score impact — sum of absolute values
   12. Blocking flag — True if unresolved HIGH/CRITICAL

  Section 3: store_precedent / _find_precedents
   13. Store resolved ticket → appears in precedent store
   14. Unresolved ticket → not stored
   15. Precedent search by category match
   16. Precedent search by title similarity
   17. Precedent limit — max 3 returned

  Section 4: _titles_similar
   18. Exact match → True
   19. High overlap → True
   20. No overlap → False
   21. Empty strings → False

  Section 5: API Routes (unit tests)
   22. GET /api/tickets/{session_id} — 200
   23. GET /api/tickets/{session_id} — 404 for unknown session
   24. GET /api/tickets/{session_id}/stats — 200
   25. GET /api/tickets/detail/{ticket_id} — 200
   26. GET /api/tickets/detail/{ticket_id} — 404 for unknown
   27. POST /api/tickets/{ticket_id}/resolve — 200
   28. POST /api/tickets/{ticket_id}/resolve — 409 already resolved
   29. POST /api/tickets/{ticket_id}/escalate — 200
   30. POST /api/tickets/{ticket_id}/escalate — 409 already escalated
   31. POST /api/tickets/{ticket_id}/escalate — 409 already resolved
"""

import asyncio
import pytest

from backend.graph.state import CreditAppraisalState
from backend.models.schemas import (
    Ticket,
    TicketSeverity,
    TicketStatus,
    TicketResolveRequest,
    ThinkingEvent,
    EventType,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
)
from backend.graph.nodes.ticket_node import (
    ticket_node,
    store_precedent,
    get_ticket_statistics,
    _find_precedents,
    _titles_similar,
    _precedent_store,
)


# ─────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────

def _ticket(
    ticket_id="TKT-001",
    session_id="test-session",
    title="Revenue Mismatch",
    severity=TicketSeverity.LOW,
    status=TicketStatus.OPEN,
    category="cross_verification",
    score_impact=-20,
    **kwargs,
) -> Ticket:
    return Ticket(
        id=ticket_id,
        session_id=session_id,
        title=title,
        description=kwargs.get("description", f"Test ticket: {title}"),
        severity=severity,
        status=status,
        category=category,
        source_a=kwargs.get("source_a", "Annual Report"),
        source_b=kwargs.get("source_b", "GST Returns"),
        ai_recommendation=kwargs.get("ai_recommendation", "Review divergence"),
        score_impact=score_impact,
    )


def _state(tickets=None, session_id="test-ticket-session") -> CreditAppraisalState:
    stages = [
        PipelineStage(stage=PipelineStageEnum.TICKETS, status=PipelineStageStatus.PENDING),
    ]
    return CreditAppraisalState(
        session_id=session_id,
        tickets=tickets or [],
        pipeline_stages=stages,
    )


# ─────────────────────────────────────────────────
# Section 1: ticket_node (LangGraph node)
# ─────────────────────────────────────────────────

class TestTicketNode:
    """Tests 1–8: ticket_node behavior."""

    def test_01_no_tickets_no_blocking(self):
        """No tickets → pipeline proceeds, tickets_blocking=False."""
        state = _state(tickets=[])
        result = asyncio.run(ticket_node(state))
        assert result["tickets_blocking"] is False
        # Thinking event says pipeline proceeding
        events = result["thinking_events"]
        assert any("No tickets" in e.message for e in events)

    def test_02_low_tickets_no_blocking(self):
        """LOW-only tickets → pipeline continues."""
        tickets = [
            _ticket("TKT-L1", severity=TicketSeverity.LOW),
            _ticket("TKT-L2", severity=TicketSeverity.LOW, title="GST Divergence"),
        ]
        state = _state(tickets=tickets)
        result = asyncio.run(ticket_node(state))
        assert result["tickets_blocking"] is False
        # Check events mention LOW tickets
        events = result["thinking_events"]
        assert any("LOW" in e.message for e in events)

    def test_03_high_tickets_blocking(self):
        """HIGH tickets → pipeline blocked."""
        tickets = [
            _ticket("TKT-H1", severity=TicketSeverity.HIGH, title="Revenue Cross-Check Failed"),
        ]
        state = _state(tickets=tickets)
        result = asyncio.run(ticket_node(state))
        assert result["tickets_blocking"] is True
        events = result["thinking_events"]
        assert any("PAUSED" in e.message or "blocking" in e.message.lower() for e in events)

    def test_04_critical_tickets_blocking(self):
        """CRITICAL tickets → pipeline blocked."""
        tickets = [
            _ticket("TKT-C1", severity=TicketSeverity.CRITICAL, title="Wilful Defaulter Match"),
        ]
        state = _state(tickets=tickets)
        result = asyncio.run(ticket_node(state))
        assert result["tickets_blocking"] is True
        events = result["thinking_events"]
        assert any(e.event_type == EventType.CRITICAL for e in events)

    def test_05_mixed_tickets_blocking_if_high_or_critical(self):
        """Mixed LOW+HIGH → blocking because of HIGH."""
        tickets = [
            _ticket("TKT-L1", severity=TicketSeverity.LOW),
            _ticket("TKT-H1", severity=TicketSeverity.HIGH, title="Net Worth Mismatch"),
        ]
        state = _state(tickets=tickets)
        result = asyncio.run(ticket_node(state))
        assert result["tickets_blocking"] is True

    def test_06_resolved_tickets_not_blocking(self):
        """Already resolved HIGH tickets → not blocking."""
        tickets = [
            _ticket("TKT-H1", severity=TicketSeverity.HIGH, status=TicketStatus.RESOLVED,
                    title="Revenue Mismatch"),
            _ticket("TKT-L1", severity=TicketSeverity.LOW),
        ]
        state = _state(tickets=tickets)
        result = asyncio.run(ticket_node(state))
        assert result["tickets_blocking"] is False

    def test_07_precedent_lookup(self):
        """Tickets get precedents attached if similar resolved tickets exist."""
        # Clear and seed precedent store
        _precedent_store.clear()
        _precedent_store.append({
            "ticket_id": "PREC-001",
            "session_id": "old-session",
            "category": "cross_verification",
            "title": "Revenue Mismatch AR vs GST",
            "severity": "HIGH",
            "resolution": "AR figure accepted — GST filing delayed",
            "resolved_by": "Officer A",
            "score_impact": -15,
            "source_a": "AR",
            "source_b": "GST",
        })

        tickets = [
            _ticket("TKT-NEW", category="cross_verification",
                    title="Revenue Mismatch AR vs ITR"),
        ]
        state = _state(tickets=tickets)
        result = asyncio.run(ticket_node(state))
        # The ticket should have precedents attached
        found_ticket = result["tickets"][0]
        assert len(found_ticket.precedents) > 0

        _precedent_store.clear()

    def test_08_thinking_events_correct_types(self):
        """Correct ThinkingEvent types for mixed tickets."""
        tickets = [
            _ticket("TKT-C1", severity=TicketSeverity.CRITICAL, title="Fraud Signal"),
            _ticket("TKT-H1", severity=TicketSeverity.HIGH, title="D/E Concern"),
            _ticket("TKT-L1", severity=TicketSeverity.LOW, title="Minor Discrepancy"),
        ]
        state = _state(tickets=tickets)
        result = asyncio.run(ticket_node(state))
        events = result["thinking_events"]
        event_types = {e.event_type for e in events}
        # Should have READ (overview), CRITICAL, FLAGGED, QUESTIONING (LOW + blocking)
        assert EventType.READ in event_types
        assert EventType.CRITICAL in event_types
        assert EventType.FLAGGED in event_types
        assert EventType.QUESTIONING in event_types


# ─────────────────────────────────────────────────
# Section 2: get_ticket_statistics
# ─────────────────────────────────────────────────

class TestTicketStatistics:
    """Tests 9–12: get_ticket_statistics."""

    def test_09_empty_tickets(self):
        """No tickets → zeroed stats."""
        stats = get_ticket_statistics([])
        assert stats["total"] == 0
        assert stats["by_severity"]["LOW"] == 0
        assert stats["by_severity"]["HIGH"] == 0
        assert stats["by_severity"]["CRITICAL"] == 0
        assert stats["blocking"] is False

    def test_10_mixed_tickets_correct_counts(self):
        """Correct severity and status counts."""
        tickets = [
            _ticket("T1", severity=TicketSeverity.LOW, status=TicketStatus.OPEN),
            _ticket("T2", severity=TicketSeverity.HIGH, status=TicketStatus.OPEN),
            _ticket("T3", severity=TicketSeverity.CRITICAL, status=TicketStatus.RESOLVED),
            _ticket("T4", severity=TicketSeverity.LOW, status=TicketStatus.RESOLVED),
        ]
        stats = get_ticket_statistics(tickets)
        assert stats["total"] == 4
        assert stats["by_severity"]["LOW"] == 2
        assert stats["by_severity"]["HIGH"] == 1
        assert stats["by_severity"]["CRITICAL"] == 1
        assert stats["by_status"]["OPEN"] == 2
        assert stats["by_status"]["RESOLVED"] == 2

    def test_11_score_impact_sum(self):
        """Total score impact is sum of absolute values."""
        tickets = [
            _ticket("T1", score_impact=-20),
            _ticket("T2", score_impact=-35),
            _ticket("T3", score_impact=-5),
        ]
        stats = get_ticket_statistics(tickets)
        assert stats["total_score_impact"] == 60  # |20| + |35| + |5|

    def test_12_blocking_flag(self):
        """Blocking=True when unresolved HIGH/CRITICAL exists."""
        tickets_blocking = [
            _ticket("T1", severity=TicketSeverity.HIGH, status=TicketStatus.OPEN),
        ]
        tickets_not_blocking = [
            _ticket("T2", severity=TicketSeverity.HIGH, status=TicketStatus.RESOLVED),
            _ticket("T3", severity=TicketSeverity.LOW, status=TicketStatus.OPEN),
        ]
        assert get_ticket_statistics(tickets_blocking)["blocking"] is True
        assert get_ticket_statistics(tickets_not_blocking)["blocking"] is False


# ─────────────────────────────────────────────────
# Section 3: store_precedent / _find_precedents
# ─────────────────────────────────────────────────

class TestPrecedentSystem:
    """Tests 13–17: precedent store and search."""

    def setup_method(self):
        _precedent_store.clear()

    def test_13_store_resolved_ticket(self):
        """Resolved ticket is stored as precedent."""
        t = _ticket("P1", status=TicketStatus.RESOLVED, category="fraud")
        t.resolution = "Confirmed false positive"
        t.resolved_by = "Officer A"
        store_precedent(t)
        assert len(_precedent_store) == 1
        assert _precedent_store[0]["ticket_id"] == "P1"
        assert _precedent_store[0]["category"] == "fraud"

    def test_14_unresolved_ticket_not_stored(self):
        """Unresolved ticket is NOT stored."""
        t = _ticket("P2", status=TicketStatus.OPEN)
        store_precedent(t)
        assert len(_precedent_store) == 0

    def test_15_find_precedents_by_category(self):
        """Precedents found by matching category."""
        _precedent_store.append({
            "ticket_id": "OLD-1",
            "session_id": "old",
            "category": "cross_verification",
            "title": "Some old ticket",
            "severity": "HIGH",
            "resolution": "AR accepted",
            "resolved_by": "OfficerA",
            "score_impact": -10,
            "source_a": "AR",
            "source_b": "GST",
        })
        new_ticket = _ticket("NEW-1", category="cross_verification",
                             title="Completely Different Title")
        matches = _find_precedents(new_ticket)
        assert len(matches) == 1
        assert matches[0]["ticket_id"] == "OLD-1"

    def test_16_find_precedents_by_title_similarity(self):
        """Precedents found by title keyword overlap."""
        _precedent_store.append({
            "ticket_id": "OLD-2",
            "session_id": "old",
            "category": "other_category",
            "title": "Revenue Mismatch Between AR and GST",
            "severity": "HIGH",
            "resolution": "Rechecked figures",
            "resolved_by": "OfficerB",
            "score_impact": -15,
            "source_a": "AR",
            "source_b": "GST",
        })
        # Different category but similar title
        new_ticket = _ticket("NEW-2", category="different",
                             title="Revenue Mismatch AR GST Divergence")
        matches = _find_precedents(new_ticket)
        assert len(matches) >= 1
        assert matches[0]["ticket_id"] == "OLD-2"

    def test_17_precedent_limit_max_3(self):
        """At most 3 precedents returned."""
        for i in range(5):
            _precedent_store.append({
                "ticket_id": f"OLD-{i}",
                "session_id": "old",
                "category": "cross_verification",
                "title": f"Revenue issue {i}",
                "severity": "LOW",
                "resolution": "OK",
                "resolved_by": "Auto",
                "score_impact": -5,
                "source_a": "AR",
                "source_b": "GST",
            })
        new_ticket = _ticket("NEW-3", category="cross_verification")
        matches = _find_precedents(new_ticket)
        assert len(matches) <= 3


# ─────────────────────────────────────────────────
# Section 4: _titles_similar
# ─────────────────────────────────────────────────

class TestTitleSimilarity:
    """Tests 18–21: _titles_similar helper."""

    def test_18_exact_match(self):
        assert _titles_similar("Revenue Mismatch", "Revenue Mismatch") is True

    def test_19_high_overlap(self):
        assert _titles_similar(
            "Revenue Mismatch AR GST", "Revenue Mismatch Between AR GST"
        ) is True

    def test_20_no_overlap(self):
        assert _titles_similar("Alpha Beta Gamma", "Delta Epsilon Zeta") is False

    def test_21_empty_strings(self):
        assert _titles_similar("", "test") is False
        assert _titles_similar("test", "") is False
        assert _titles_similar("", "") is False


# ─────────────────────────────────────────────────
# Section 5: API Routes (unit-level via TestClient)
# ─────────────────────────────────────────────────

class TestTicketRoutes:
    """Tests 22–31: FastAPI routes unit tests."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """Create test client and seed an assessment with tickets."""
        from fastapi.testclient import TestClient
        from backend.api.main import app
        from backend.api.routes._store import assessments_store
        from backend.models.schemas import AssessmentSummary, CompanyInfo

        # Clear store
        assessments_store.clear()
        # Clear precedent store
        _precedent_store.clear()

        # Seed assessment with tickets
        assessment = AssessmentSummary(
            session_id="test-sess-77",
            company=CompanyInfo(
                name="Test Corp", sector="Manufacturing",
                loan_type="Working Capital", loan_amount="50 Cr",
                loan_amount_numeric=50_00_00_000.0,
            ),
            tickets=[
                _ticket("TKT-A", session_id="test-sess-77",
                        severity=TicketSeverity.HIGH, title="Revenue Cross-Check"),
                _ticket("TKT-B", session_id="test-sess-77",
                        severity=TicketSeverity.LOW, title="Minor GST Gap"),
            ],
        )
        assessments_store["test-sess-77"] = assessment

        self.client = TestClient(app)
        self.store = assessments_store
        yield
        assessments_store.clear()

    def test_22_get_tickets_200(self):
        resp = self.client.get("/api/tickets/test-sess-77")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_23_get_tickets_404(self):
        resp = self.client.get("/api/tickets/nonexistent")
        assert resp.status_code == 404

    def test_24_get_ticket_stats_200(self):
        resp = self.client.get("/api/tickets/test-sess-77/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["by_severity"]["HIGH"] == 1
        assert data["by_severity"]["LOW"] == 1

    def test_25_get_ticket_detail_200(self):
        resp = self.client.get("/api/tickets/detail/TKT-A")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TKT-A"
        assert data["title"] == "Revenue Cross-Check"

    def test_26_get_ticket_detail_404(self):
        resp = self.client.get("/api/tickets/detail/NONEXISTENT")
        assert resp.status_code == 404

    def test_27_resolve_ticket_200(self):
        resp = self.client.post(
            "/api/tickets/TKT-A/resolve",
            json={"resolution": "AR figure accepted", "resolved_by": "Officer X"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "RESOLVED"
        assert data["resolution"] == "AR figure accepted"
        assert data["resolved_by"] == "Officer X"
        # Check assessment counter updated
        assert self.store["test-sess-77"].tickets_resolved == 1
        # Check precedent was stored
        assert len(_precedent_store) == 1

    def test_28_resolve_ticket_409_already_resolved(self):
        # Resolve first
        self.client.post(
            "/api/tickets/TKT-A/resolve",
            json={"resolution": "OK", "resolved_by": "Test"},
        )
        # Try resolve again
        resp = self.client.post(
            "/api/tickets/TKT-A/resolve",
            json={"resolution": "Again", "resolved_by": "Test"},
        )
        assert resp.status_code == 409

    def test_29_escalate_ticket_200(self):
        resp = self.client.post("/api/tickets/TKT-B/escalate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ESCALATED"

    def test_30_escalate_ticket_409_already_escalated(self):
        self.client.post("/api/tickets/TKT-B/escalate")
        resp = self.client.post("/api/tickets/TKT-B/escalate")
        assert resp.status_code == 409

    def test_31_escalate_ticket_409_already_resolved(self):
        # Resolve first
        self.client.post(
            "/api/tickets/TKT-B/resolve",
            json={"resolution": "Fixed", "resolved_by": "Test"},
        )
        # Try to escalate resolved ticket
        resp = self.client.post("/api/tickets/TKT-B/escalate")
        assert resp.status_code == 409
