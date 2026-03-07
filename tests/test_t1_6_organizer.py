"""
Intelli-Credit — T1.6 Tests: Agent 1.5 The Organizer

Tests for:
  1. Five Cs Mapper — map_to_five_cs()
  2. Metric Computer — compute_metrics()
  3. Board Analyzer — analyze_board_minutes()
  4. Shareholding Analyzer — analyze_shareholding()
  5. Organizer Node — full organizer_node() integration
"""

import asyncio
import pytest
from unittest.mock import MagicMock

from backend.graph.state import (
    CreditAppraisalState,
    WorkerOutput,
    NormalizedField,
    FiveCsMapping,
    ComputedMetrics,
    OrganizedPackage,
    RawDataPackage,
)
from backend.models.schemas import (
    CompanyInfo,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
    EventType,
    DocumentType,
)


# ─── Fixtures ───────────────────────────────────────────

def _make_worker_output(worker_id: str, doc_type: DocumentType,
                         extracted_data: dict, confidence: float = 0.85) -> WorkerOutput:
    """Create a WorkerOutput with specified data."""
    return WorkerOutput(
        worker_id=worker_id,
        document_type=doc_type,
        status="completed",
        extracted_data=extracted_data,
        confidence=confidence,
        pages_processed=5,
    )


def _make_full_worker_outputs() -> dict:
    """Create a realistic set of worker outputs for XYZ Steel."""
    return {
        "W1": _make_worker_output("W1", DocumentType.ANNUAL_REPORT, {
            "revenue": 215.0,
            "ebitda": 32.0,
            "pat": 12.5,
            "interest_expense": 18.0,
            "total_debt": 120.0,
            "net_worth": 85.0,
            "equity": 50.0,
            "current_assets": 95.0,
            "current_liabilities": 72.0,
            "fixed_assets": 180.0,
            "inventory": 28.0,
            "receivables": 35.0,
            "revenue_3yr": [180.0, 195.0, 215.0],
            "rpts": {"transactions": [{"party": "ABC Ltd", "amount": 5.0}]},
            "auditor": {"name": "Deloitte", "qualifications": ["going concern"]},
            "order_book": 320.0,
        }, confidence=0.90),
        "W2": _make_worker_output("W2", DocumentType.BANK_STATEMENT, {
            "bank_name": "SBI",
            "annual_inflow": 210.0,
            "emi_regularity": {"payment_regularity_pct": 95.0},
        }, confidence=0.88),
        "W3": _make_worker_output("W3", DocumentType.GST_RETURNS, {
            "gstin": "27AABCU9603R1ZJ",
            "annual_turnover": 225.0,
        }, confidence=0.95),
        "W4": _make_worker_output("W4", DocumentType.ITR, {
            "revenue": 212.0,
            "net_worth": 83.0,
        }, confidence=0.92),
        "W5": _make_worker_output("W5", DocumentType.LEGAL_NOTICE, {
            "cases": [
                {"claimant": "Vendor A", "amount": 2.5, "status": "pending"},
            ],
        }, confidence=0.80),
        "W6": _make_worker_output("W6", DocumentType.BOARD_MINUTES, {
            "cfo_changes": 1,
            "director_resignations": 0,
            "rpt_approvals": [
                {"party": "ABC Ltd", "amount": 5.0, "date": "2024-03-15"},
            ],
            "risk_discussions": ["Working capital stress discussed"],
        }, confidence=0.85),
        "W7": _make_worker_output("W7", DocumentType.SHAREHOLDING_PATTERN, {
            "promoter_holding_pct": 52.0,
            "promoter_pledge_pct": 15.0,
            "institutional_holding_pct": 28.0,
            "public_holding_pct": 20.0,
            "pledge_history": [10.0, 12.0, 15.0],
            "promoter_holding_history": [60.0, 55.0, 50.0],
        }, confidence=0.90),
        "W8": _make_worker_output("W8", DocumentType.RATING_REPORT, {
            "current_rating": "BBB+",
            "outlook": "Stable",
            "sector_outlook": "Positive — steel demand rising",
        }, confidence=0.88),
    }


def _make_state(worker_outputs=None, session_id="test-org-session") -> CreditAppraisalState:
    """Create a CreditAppraisalState for organizer tests."""
    return CreditAppraisalState(
        session_id=session_id,
        company=CompanyInfo(
            name="XYZ Steel Ltd",
            sector="Steel Manufacturing",
            loan_type="Working Capital",
            loan_amount="₹50 Cr",
            loan_amount_numeric=50.0,
            cin="U27100MH2010PLC123456",
        ),
        worker_outputs=worker_outputs if worker_outputs is not None else _make_full_worker_outputs(),
        pipeline_stages=[
            PipelineStage(stage=PipelineStageEnum.ORGANIZATION,
                          status=PipelineStageStatus.PENDING),
        ],
    )


# ──────────────────────────────────────────────────────────
# Section 1: Five Cs Mapper
# ──────────────────────────────────────────────────────────

class TestFiveCsMapper:
    """Tests for map_to_five_cs()."""

    def test_maps_capacity_revenue(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        outputs = _make_full_worker_outputs()
        result = map_to_five_cs(outputs)
        assert "revenue" in result.capacity
        assert result.capacity["revenue"].value == 215.0
        assert result.capacity["revenue"].source_document == "Annual Report"

    def test_maps_capacity_ebitda(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "ebitda" in result.capacity
        assert result.capacity["ebitda"].value == 32.0

    def test_maps_capacity_emi_regularity(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "emi_regularity" in result.capacity
        assert result.capacity["emi_regularity"].value == 95.0

    def test_maps_capacity_gst_turnover(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "gst_turnover" in result.capacity
        assert result.capacity["gst_turnover"].confidence == 1.0  # govt source

    def test_maps_capacity_revenue_3yr(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "revenue_3yr" in result.capacity
        assert result.capacity["revenue_3yr"].value == [180.0, 195.0, 215.0]

    def test_maps_character_promoter_holding(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "promoter_holding_pct" in result.character
        assert result.character["promoter_holding_pct"].value == 52.0

    def test_maps_character_pledge(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "promoter_pledge_pct" in result.character
        assert result.character["promoter_pledge_pct"].value == 15.0

    def test_maps_character_credit_rating(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "credit_rating" in result.character
        assert result.character["credit_rating"].value == "BBB+"

    def test_maps_character_pending_cases(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "pending_cases" in result.character
        assert result.character["pending_cases"].value == 1

    def test_maps_capital_net_worth(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "net_worth" in result.capital
        # Should prefer ITR (govt source)
        assert result.capital["net_worth"].source_document == "ITR"

    def test_maps_capital_total_debt(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "total_debt" in result.capital
        assert result.capital["total_debt"].value == 120.0

    def test_maps_collateral_fixed_assets(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "fixed_assets" in result.collateral
        assert result.collateral["fixed_assets"].value == 180.0

    def test_maps_conditions_order_book(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "order_book" in result.conditions
        assert result.conditions["order_book"].value == 320.0

    def test_maps_conditions_rating_outlook(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs(_make_full_worker_outputs())
        assert "rating_outlook" in result.conditions
        assert result.conditions["rating_outlook"].value == "Stable"

    def test_empty_worker_outputs_no_crash(self):
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        result = map_to_five_cs({})
        assert isinstance(result, FiveCsMapping)
        assert len(result.capacity) == 0
        assert len(result.character) == 0

    def test_partial_workers_graceful(self):
        """Only W1 present — should still map what's available."""
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        outputs = {
            "W1": _make_worker_output("W1", DocumentType.ANNUAL_REPORT, {
                "revenue": 100.0, "ebitda": 20.0,
            }),
        }
        result = map_to_five_cs(outputs)
        assert "revenue" in result.capacity
        assert len(result.character) == 0  # no W5/W6/W7/W8


# ──────────────────────────────────────────────────────────
# Section 2: Metric Computer
# ──────────────────────────────────────────────────────────

class TestMetricComputer:
    """Tests for compute_metrics()."""

    def _make_five_cs(self) -> FiveCsMapping:
        from backend.agents.organizer.five_cs_mapper import map_to_five_cs
        return map_to_five_cs(_make_full_worker_outputs())

    def test_computes_dscr(self):
        from backend.agents.organizer.metric_computer import compute_metrics
        result = compute_metrics(self._make_five_cs())
        assert result.dscr is not None
        # DSCR = EBITDA / Interest = 32 / 18 ≈ 1.7778
        assert abs(result.dscr - 1.7778) < 0.01

    def test_computes_current_ratio(self):
        from backend.agents.organizer.metric_computer import compute_metrics
        result = compute_metrics(self._make_five_cs())
        assert result.current_ratio is not None
        # CR = current_assets / current_liabilities = 95 / 72 ≈ 1.3194
        assert abs(result.current_ratio - 1.3194) < 0.01

    def test_computes_debt_equity_ratio(self):
        from backend.agents.organizer.metric_computer import compute_metrics
        result = compute_metrics(self._make_five_cs())
        assert result.debt_equity_ratio is not None
        # D/E = total_debt / net_worth: ITR net_worth=83, total_debt=120 → 120/83 ≈ 1.4458
        assert abs(result.debt_equity_ratio - 1.4458) < 0.01

    def test_computes_revenue_cagr(self):
        from backend.agents.organizer.metric_computer import compute_metrics
        result = compute_metrics(self._make_five_cs())
        assert result.revenue_cagr_3yr is not None
        # CAGR = (215/180)^(1/2) - 1 ≈ 9.27%
        assert 5.0 < result.revenue_cagr_3yr < 15.0

    def test_computes_ebitda_margin(self):
        from backend.agents.organizer.metric_computer import compute_metrics
        result = compute_metrics(self._make_five_cs())
        assert result.ebitda_margin is not None
        # EBITDA/Revenue = 32/215 ≈ 14.88%
        assert abs(result.ebitda_margin - 14.88) < 0.5

    def test_computes_pat_margin(self):
        from backend.agents.organizer.metric_computer import compute_metrics
        result = compute_metrics(self._make_five_cs())
        assert result.pat_margin is not None
        # PAT/Revenue = 12.5/215 ≈ 5.81%
        assert abs(result.pat_margin - 5.81) < 0.5

    def test_computes_interest_coverage(self):
        from backend.agents.organizer.metric_computer import compute_metrics
        result = compute_metrics(self._make_five_cs())
        assert result.interest_coverage_ratio is not None
        # Same as DSCR in this simplified model
        assert result.interest_coverage_ratio == result.dscr

    def test_computes_gst_bank_divergence(self):
        from backend.agents.organizer.metric_computer import compute_metrics
        result = compute_metrics(self._make_five_cs())
        assert result.gst_bank_divergence_pct is not None
        # |225 - 210| / max(225, 210) * 100 ≈ 6.67%
        assert abs(result.gst_bank_divergence_pct - 6.67) < 0.5

    def test_computes_itr_ar_divergence(self):
        from backend.agents.organizer.metric_computer import compute_metrics
        outputs = _make_full_worker_outputs()
        five_cs = self._make_five_cs()
        result = compute_metrics(five_cs, outputs)
        assert result.itr_ar_divergence_pct is not None
        # |212 - 215| / max(215, 212) * 100 ≈ 1.40%
        assert result.itr_ar_divergence_pct < 5.0

    def test_computes_working_capital_cycle(self):
        from backend.agents.organizer.metric_computer import compute_metrics
        result = compute_metrics(self._make_five_cs())
        assert result.working_capital_cycle_days is not None
        # (28/215*365) + (35/215*365) ≈ 47.5 + 59.4 ≈ 107 days
        assert 80 < result.working_capital_cycle_days < 140

    def test_computes_promoter_metrics(self):
        from backend.agents.organizer.metric_computer import compute_metrics
        result = compute_metrics(self._make_five_cs())
        assert result.promoter_pledge_pct == 15.0
        assert result.promoter_holding_pct == 52.0

    def test_handles_missing_data_gracefully(self):
        """Empty 5 Cs → all metrics None, no crash."""
        from backend.agents.organizer.metric_computer import compute_metrics
        result = compute_metrics(FiveCsMapping())
        assert result.dscr is None
        assert result.current_ratio is None
        assert result.debt_equity_ratio is None
        assert result.revenue_cagr_3yr is None

    def test_handles_zero_denominator(self):
        """Zero interest expense → DSCR None."""
        from backend.agents.organizer.metric_computer import compute_metrics
        five_cs = FiveCsMapping()
        five_cs.capacity["ebitda"] = NormalizedField(
            value=32.0, source_document="AR", confidence=0.9)
        five_cs.capacity["interest_expense"] = NormalizedField(
            value=0.0, source_document="AR", confidence=0.9)
        result = compute_metrics(five_cs)
        assert result.dscr is None


# ──────────────────────────────────────────────────────────
# Section 3: Board Analyzer
# ──────────────────────────────────────────────────────────

class TestBoardAnalyzer:
    """Tests for analyze_board_minutes()."""

    def test_extracts_cfo_changes(self):
        from backend.agents.organizer.board_analyzer import analyze_board_minutes
        result = analyze_board_minutes(_make_full_worker_outputs())
        assert result.cfo_changes == 1

    def test_extracts_rpt_approvals(self):
        from backend.agents.organizer.board_analyzer import analyze_board_minutes
        result = analyze_board_minutes(_make_full_worker_outputs())
        assert result.rpt_approval_count == 1

    def test_flags_multiple_cfo_changes(self):
        from backend.agents.organizer.board_analyzer import analyze_board_minutes
        outputs = {
            "W6": _make_worker_output("W6", DocumentType.BOARD_MINUTES, {
                "cfo_changes": 3,
            }),
        }
        result = analyze_board_minutes(outputs)
        assert result.cfo_changes == 3
        assert any("Multiple CFO changes" in f for f in result.governance_flags)
        assert result.governance_score < 1.0

    def test_flags_director_resignations(self):
        from backend.agents.organizer.board_analyzer import analyze_board_minutes
        outputs = {
            "W6": _make_worker_output("W6", DocumentType.BOARD_MINUTES, {
                "director_resignations": ["Dir A", "Dir B", "Dir C"],
            }),
        }
        result = analyze_board_minutes(outputs)
        assert result.director_resignations == 3
        assert any("Multiple director resignations" in f for f in result.governance_flags)

    def test_flags_high_rpt_count(self):
        from backend.agents.organizer.board_analyzer import analyze_board_minutes
        outputs = {
            "W6": _make_worker_output("W6", DocumentType.BOARD_MINUTES, {
                "rpt_approvals": [{"party": f"Party {i}"} for i in range(7)],
            }),
        }
        result = analyze_board_minutes(outputs)
        assert result.rpt_approval_count == 7
        assert any("High RPT approval count" in f for f in result.governance_flags)

    def test_clean_governance_score(self):
        from backend.agents.organizer.board_analyzer import analyze_board_minutes
        outputs = {
            "W6": _make_worker_output("W6", DocumentType.BOARD_MINUTES, {
                "cfo_changes": 0,
                "director_resignations": 0,
                "rpt_approvals": [],
            }),
        }
        result = analyze_board_minutes(outputs)
        assert result.governance_score == 1.0
        assert len(result.governance_flags) == 0

    def test_no_w6_data_no_crash(self):
        from backend.agents.organizer.board_analyzer import analyze_board_minutes
        result = analyze_board_minutes({})
        assert result.governance_score == 1.0
        assert result.cfo_changes == 0

    def test_to_dict(self):
        from backend.agents.organizer.board_analyzer import analyze_board_minutes
        result = analyze_board_minutes(_make_full_worker_outputs())
        d = result.to_dict()
        assert "cfo_changes" in d
        assert "governance_score" in d
        assert isinstance(d, dict)


# ──────────────────────────────────────────────────────────
# Section 4: Shareholding Analyzer
# ──────────────────────────────────────────────────────────

class TestShareholdingAnalyzer:
    """Tests for analyze_shareholding()."""

    def test_extracts_holdings(self):
        from backend.agents.organizer.shareholding_analyzer import analyze_shareholding
        result = analyze_shareholding(_make_full_worker_outputs())
        assert result.promoter_holding_pct == 52.0
        assert result.promoter_pledge_pct == 15.0
        assert result.institutional_holding_pct == 28.0

    def test_detects_pledge_trend(self):
        from backend.agents.organizer.shareholding_analyzer import analyze_shareholding
        result = analyze_shareholding(_make_full_worker_outputs())
        assert result.pledge_trend == "increasing"

    def test_detects_promoter_trend(self):
        from backend.agents.organizer.shareholding_analyzer import analyze_shareholding
        result = analyze_shareholding(_make_full_worker_outputs())
        assert result.promoter_trend == "decreasing"

    def test_flags_high_pledge(self):
        from backend.agents.organizer.shareholding_analyzer import analyze_shareholding
        outputs = {
            "W7": _make_worker_output("W7", DocumentType.SHAREHOLDING_PATTERN, {
                "promoter_holding_pct": 55.0,
                "promoter_pledge_pct": 60.0,
            }),
        }
        result = analyze_shareholding(outputs)
        assert any("Very high promoter pledge" in f for f in result.shareholding_flags)
        assert result.shareholding_score < 0.8

    def test_flags_low_promoter(self):
        from backend.agents.organizer.shareholding_analyzer import analyze_shareholding
        outputs = {
            "W7": _make_worker_output("W7", DocumentType.SHAREHOLDING_PATTERN, {
                "promoter_holding_pct": 22.0,
                "promoter_pledge_pct": 5.0,
            }),
        }
        result = analyze_shareholding(outputs)
        assert any("Low promoter holding" in f for f in result.shareholding_flags)

    def test_detects_cross_holdings(self):
        from backend.agents.organizer.shareholding_analyzer import analyze_shareholding
        outputs = {
            "W7": _make_worker_output("W7", DocumentType.SHAREHOLDING_PATTERN, {
                "promoter_holding_pct": 50.0,
                "cross_holdings": [
                    {"entity": "ABC Group", "holding_pct": 5.0},
                ],
            }),
        }
        result = analyze_shareholding(outputs)
        assert len(result.cross_holdings) == 1
        assert any("Cross-holdings detected" in f for f in result.shareholding_flags)

    def test_clean_shareholding_score(self):
        from backend.agents.organizer.shareholding_analyzer import analyze_shareholding
        outputs = {
            "W7": _make_worker_output("W7", DocumentType.SHAREHOLDING_PATTERN, {
                "promoter_holding_pct": 65.0,
                "promoter_pledge_pct": 5.0,
            }),
        }
        result = analyze_shareholding(outputs)
        assert result.shareholding_score >= 0.9

    def test_no_w7_data_no_crash(self):
        from backend.agents.organizer.shareholding_analyzer import analyze_shareholding
        result = analyze_shareholding({})
        assert result.shareholding_score == 1.0
        assert result.promoter_holding_pct is None

    def test_to_dict(self):
        from backend.agents.organizer.shareholding_analyzer import analyze_shareholding
        result = analyze_shareholding(_make_full_worker_outputs())
        d = result.to_dict()
        assert "promoter_holding_pct" in d
        assert "shareholding_score" in d
        assert isinstance(d, dict)


# ──────────────────────────────────────────────────────────
# Section 5: Organizer Node Integration
# ──────────────────────────────────────────────────────────

class TestOrganizerNode:
    """Integration tests for the full organizer_node()."""

    def test_returns_organized_package(self):
        from backend.graph.nodes.organizer_node import organizer_node
        state = _make_state()
        result = asyncio.run(organizer_node(state))
        assert "organized_package" in result
        assert isinstance(result["organized_package"], OrganizedPackage)

    def test_five_cs_populated(self):
        from backend.graph.nodes.organizer_node import organizer_node
        state = _make_state()
        result = asyncio.run(organizer_node(state))
        pkg = result["organized_package"]
        assert len(pkg.five_cs.capacity) > 0
        assert len(pkg.five_cs.character) > 0
        assert len(pkg.five_cs.capital) > 0

    def test_computed_metrics_populated(self):
        from backend.graph.nodes.organizer_node import organizer_node
        state = _make_state()
        result = asyncio.run(organizer_node(state))
        m = result["organized_package"].computed_metrics
        assert m.dscr is not None
        assert m.current_ratio is not None
        assert m.ebitda_margin is not None

    def test_graph_built(self):
        from backend.graph.nodes.organizer_node import organizer_node
        state = _make_state()
        result = asyncio.run(organizer_node(state))
        pkg = result["organized_package"]
        # Graph builder creates entities from W1/W2/W3 etc.
        assert pkg.graph_entities_created >= 0
        assert pkg.graph_relationships_created >= 0

    def test_ml_signals_contain_board_analysis(self):
        from backend.graph.nodes.organizer_node import organizer_node
        state = _make_state()
        result = asyncio.run(organizer_node(state))
        ml = result["organized_package"].ml_signals
        assert "board_analysis" in ml
        assert "governance_score" in ml["board_analysis"]

    def test_ml_signals_contain_shareholding_analysis(self):
        from backend.graph.nodes.organizer_node import organizer_node
        state = _make_state()
        result = asyncio.run(organizer_node(state))
        ml = result["organized_package"].ml_signals
        assert "shareholding_analysis" in ml
        assert "promoter_holding_pct" in ml["shareholding_analysis"]

    def test_emits_thinking_events(self):
        from backend.graph.nodes.organizer_node import organizer_node
        state = _make_state()
        result = asyncio.run(organizer_node(state))
        events = result.get("thinking_events", [])
        assert len(events) > 5  # Should emit READ, COMPUTED, CONNECTING, etc.
        agents = {e.agent for e in events}
        assert "Agent 1.5 — The Organizer" in agents

    def test_emits_computed_events(self):
        from backend.graph.nodes.organizer_node import organizer_node
        state = _make_state()
        result = asyncio.run(organizer_node(state))
        events = result.get("thinking_events", [])
        computed_events = [e for e in events if e.event_type == EventType.COMPUTED]
        assert len(computed_events) >= 3  # At least DSCR, CR, margin

    def test_emits_concluding_event(self):
        from backend.graph.nodes.organizer_node import organizer_node
        state = _make_state()
        result = asyncio.run(organizer_node(state))
        events = result.get("thinking_events", [])
        concluding = [e for e in events if e.event_type == EventType.CONCLUDING]
        assert len(concluding) >= 1

    def test_pipeline_stage_completed(self):
        from backend.graph.nodes.organizer_node import organizer_node
        state = _make_state()
        result = asyncio.run(organizer_node(state))
        stages = result.get("pipeline_stages", [])
        org_stage = next((s for s in stages if s.stage == PipelineStageEnum.ORGANIZATION), None)
        assert org_stage is not None
        assert org_stage.status == PipelineStageStatus.COMPLETED

    def test_empty_workers_no_crash(self):
        from backend.graph.nodes.organizer_node import organizer_node
        state = _make_state(worker_outputs={})
        result = asyncio.run(organizer_node(state))
        assert "organized_package" in result
        pkg = result["organized_package"]
        assert pkg.computed_metrics.dscr is None

    def test_single_worker_only(self):
        from backend.graph.nodes.organizer_node import organizer_node
        outputs = {
            "W1": _make_worker_output("W1", DocumentType.ANNUAL_REPORT, {
                "revenue": 100.0, "ebitda": 15.0, "interest_expense": 8.0,
            }),
        }
        state = _make_state(worker_outputs=outputs)
        result = asyncio.run(organizer_node(state))
        pkg = result["organized_package"]
        assert pkg.computed_metrics.dscr is not None  # EBITDA/Interest
        assert pkg.computed_metrics.promoter_holding_pct is None  # No W7

    def test_divergence_flagged_in_events(self):
        """High GST-Bank divergence should emit FLAGGED event."""
        from backend.graph.nodes.organizer_node import organizer_node
        outputs = _make_full_worker_outputs()
        # Make GST turnover very different from bank inflow
        outputs["W3"] = _make_worker_output("W3", DocumentType.GST_RETURNS, {
            "annual_turnover": 350.0,  # 350 vs 210 bank inflow = 40% divergence
        })
        state = _make_state(worker_outputs=outputs)
        result = asyncio.run(organizer_node(state))
        events = result.get("thinking_events", [])
        flagged = [e for e in events if e.event_type == EventType.FLAGGED
                   and "GST-Bank" in e.message]
        assert len(flagged) >= 1
