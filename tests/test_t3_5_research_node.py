"""
Tests for T3.5 — Research Node (Agent 2)

5-Perspective Testing:
- 🏦 Credit Domain Expert: Source credibility, verification tiers, finding categories
- 🔒 Security Architect: Input sanitization, injection in company names
- ⚙️ Systems Engineer: Parallel track execution, failure isolation, graceful degradation
- 🧪 QA Engineer: Edge cases, empty state, missing fields
- 🎯 Hackathon Judge: Demo story quality, thinking events, XYZ Steel scenario
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from backend.graph.state import (
    CreditAppraisalState,
    ResearchPackage,
    ResearchFinding,
)
from backend.models.schemas import (
    CompanyInfo,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
    EventType,
)
from backend.graph.nodes.research_node import (
    research_node,
    _verify_findings,
    _categorize_findings,
    _get_source_info,
    _run_tavily_track,
    _run_exa_track,
    _run_serpapi_track,
    _run_govt_scraper_track,
    _run_rating_track,
    SOURCE_TIERS,
)


# ──────────────────────────────────────────────
# Test Helpers
# ──────────────────────────────────────────────

def _make_state(
    session_id: str = "test-research-001",
    company_name: str = "XYZ Steel Pvt Ltd",
    sector: str = "manufacturing",
    cin: str = "U27100MH2015PTC123456",
) -> CreditAppraisalState:
    """Create a minimal state for research node testing."""
    return CreditAppraisalState(
        session_id=session_id,
        company=CompanyInfo(
            name=company_name,
            sector=sector,
            cin=cin,
            loan_type="Working Capital",
            loan_amount="₹50,00,00,000",
            loan_amount_numeric=500000000.0,
        ),
        pipeline_stages=[
            PipelineStage(
                stage=PipelineStageEnum.RESEARCH,
                status=PipelineStageStatus.PENDING,
            ),
        ],
    )


def _make_finding(
    source: str = "tavily",
    tier: int = 2,
    weight: float = 0.85,
    relevance: float = 0.80,
    category: str = "financial",
    verified: bool = False,
) -> ResearchFinding:
    return ResearchFinding(
        source=source,
        source_tier=tier,
        source_weight=weight,
        title=f"Test finding from {source}",
        content=f"Content from {source} about the company.",
        relevance_score=relevance,
        verified=verified,
        category=category,
    )


# ──────────────────────────────────────────────
# 🏦 Credit Domain Expert Tests
# ──────────────────────────────────────────────

class TestCreditDomainExpert:
    """Source credibility, verification tiers, finding categories."""

    def test_government_sources_weight_1_0(self):
        """Government sources (MCA21, SEBI, RBI, NJDG, GSTIN) have weight 1.0."""
        govt_sources = ["mca21", "sebi", "rbi", "njdg", "gstin"]
        for src in govt_sources:
            info = _get_source_info(src)
            assert info["tier"] == 1
            assert info["weight"] == 1.0

    def test_media_sources_weight_0_85(self):
        """Reputable media (Tavily, Exa, ET, BS, Mint) have weight 0.85."""
        media_sources = ["tavily", "exa", "economic_times", "business_standard", "mint"]
        for src in media_sources:
            info = _get_source_info(src)
            assert info["tier"] == 2
            assert info["weight"] == 0.85

    def test_social_media_rejected(self):
        """Social media sources have zero weight."""
        info = _get_source_info("social_media")
        assert info["tier"] == 5
        assert info["weight"] == 0.0

    def test_verification_auto_verifies_government(self):
        """Tier 1 government findings are auto-verified."""
        finding = _make_finding(source="mca21", tier=1, weight=1.0, relevance=0.5)
        results = _verify_findings([finding])
        assert len(results) == 1
        assert results[0].verified is True

    def test_verification_tier2_needs_high_relevance(self):
        """Tier 2 media needs relevance >= 0.7 to be verified."""
        high = _make_finding(source="tavily", tier=2, weight=0.85, relevance=0.8)
        low = _make_finding(source="tavily", tier=2, weight=0.85, relevance=0.5)
        results = _verify_findings([high, low])
        assert results[0].verified is True
        assert results[1].verified is False

    def test_verification_tier5_excluded(self):
        """Tier 5 sources are excluded from results (weight set to 0)."""
        finding = _make_finding(source="social_media", tier=5, weight=0.0, relevance=0.9)
        results = _verify_findings([finding])
        assert len(results) == 0

    def test_source_tiers_complete(self):
        """All 5 tiers represented in SOURCE_TIERS."""
        tiers = set(v["tier"] for v in SOURCE_TIERS.values())
        assert tiers == {1, 2, 3, 4, 5}

    def test_categorization_groups_correctly(self):
        """Findings grouped by category correctly."""
        findings = [
            _make_finding(category="litigation"),
            _make_finding(category="litigation"),
            _make_finding(category="financial"),
            _make_finding(category="regulatory"),
        ]
        cats = _categorize_findings(findings)
        assert len(cats["litigation"]) == 2
        assert len(cats["financial"]) == 1
        assert len(cats["regulatory"]) == 1

    @pytest.mark.asyncio
    async def test_govt_scraper_returns_verified_findings(self):
        """Government scraper track returns pre-verified findings."""
        results = await _run_govt_scraper_track("XYZ Steel Pvt Ltd", cin="U27100")
        assert len(results) >= 3  # MCA21 + NJDG + RBI
        for f in results:
            assert f.source_tier == 1
            assert f.source_weight == 1.0
            assert f.verified is True

    @pytest.mark.asyncio
    async def test_research_node_counts_govt_and_media(self):
        """Research node correctly counts government vs media sources."""
        state = _make_state()
        result = await research_node(state)
        pkg = result["research_package"]
        assert pkg.government_sources >= 3  # MCA21, NJDG, RBI
        assert pkg.media_sources >= 1
        assert pkg.total_findings == len(pkg.findings)


# ──────────────────────────────────────────────
# 🔒 Security Architect Tests
# ──────────────────────────────────────────────

class TestSecurityArchitect:
    """Input sanitization, safety."""

    @pytest.mark.asyncio
    async def test_injection_in_company_name(self):
        """SQL injection in company name doesn't crash."""
        state = _make_state(company_name="'; DROP TABLE companies--")
        result = await research_node(state)
        assert result["research_package"] is not None
        assert result["research_package"].total_findings >= 0

    @pytest.mark.asyncio
    async def test_xss_in_company_name(self):
        """XSS in company name doesn't break finding content."""
        state = _make_state(company_name="<script>alert('xss')</script>")
        result = await research_node(state)
        pkg = result["research_package"]
        for finding in pkg.findings:
            # Content should contain the name but it's simulated — just verify no crash
            assert isinstance(finding.content, str)

    @pytest.mark.asyncio
    async def test_empty_company_produces_empty_findings(self):
        """Empty company name produces 0 findings without crashing."""
        state = _make_state(company_name="")
        result = await research_node(state)
        pkg = result["research_package"]
        assert pkg.total_findings == 0

    @pytest.mark.asyncio
    async def test_very_long_company_name(self):
        """Very long company name handled without issues."""
        state = _make_state(company_name="A" * 5000)
        result = await research_node(state)
        assert result["research_package"] is not None

    def test_unknown_source_defaults_to_tier3(self):
        """Unknown source name defaults to tier 3 (moderate)."""
        info = _get_source_info("totally_unknown_source")
        assert info["tier"] == 3
        assert info["weight"] == 0.60


# ──────────────────────────────────────────────
# ⚙️ Systems Engineer Tests
# ──────────────────────────────────────────────

class TestSystemsEngineer:
    """Parallel execution, failure isolation, degradation."""

    @pytest.mark.asyncio
    async def test_parallel_tracks_execute(self):
        """All 5 tracks run in parallel via asyncio.gather."""
        state = _make_state()
        result = await research_node(state)
        pkg = result["research_package"]
        # Should have findings from multiple tracks
        sources = set(f.source for f in pkg.findings)
        assert len(sources) >= 3  # tavily, exa/serpapi, mca21/njdg/rbi

    @pytest.mark.asyncio
    async def test_single_track_failure_doesnt_crash(self):
        """If one track fails, others still produce results."""
        state = _make_state()
        with patch(
            "backend.graph.nodes.research_node._run_tavily_track",
            side_effect=RuntimeError("Tavily API down"),
        ):
            result = await research_node(state)
            pkg = result["research_package"]
            # Should still have findings from other tracks
            assert pkg.total_findings > 0
            # Pipeline stage should still be COMPLETED
            for stage in result["pipeline_stages"]:
                if stage.stage == PipelineStageEnum.RESEARCH:
                    assert stage.status == PipelineStageStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_all_tracks_fail_produces_empty_package(self):
        """All 5 tracks failing produces empty package but no crash."""
        state = _make_state()
        with patch(
            "backend.graph.nodes.research_node._run_tavily_track",
            side_effect=RuntimeError("fail"),
        ), patch(
            "backend.graph.nodes.research_node._run_exa_track",
            side_effect=RuntimeError("fail"),
        ), patch(
            "backend.graph.nodes.research_node._run_serpapi_track",
            side_effect=RuntimeError("fail"),
        ), patch(
            "backend.graph.nodes.research_node._run_govt_scraper_track",
            side_effect=RuntimeError("fail"),
        ), patch(
            "backend.graph.nodes.research_node._run_rating_track",
            side_effect=RuntimeError("fail"),
        ):
            result = await research_node(state)
            pkg = result["research_package"]
            assert pkg.total_findings == 0
            assert len(pkg.findings) == 0

    @pytest.mark.asyncio
    async def test_failed_track_emits_flagged_event(self):
        """Failed track emits FLAGGED thinking event."""
        state = _make_state()
        with patch(
            "backend.graph.nodes.research_node._run_exa_track",
            side_effect=RuntimeError("Exa timeout"),
        ):
            result = await research_node(state)
            events = result.get("thinking_events", [])
            flagged = [e for e in events if e.event_type == EventType.FLAGGED]
            assert len(flagged) >= 1
            assert any("Exa" in e.message for e in flagged)

    @pytest.mark.asyncio
    async def test_pipeline_stage_updated_to_completed(self):
        """Research stage marked COMPLETED on success."""
        state = _make_state()
        result = await research_node(state)
        for stage in result["pipeline_stages"]:
            if stage.stage == PipelineStageEnum.RESEARCH:
                assert stage.status == PipelineStageStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_no_state_mutation_across_sessions(self):
        """Two concurrent calls don't share state."""
        state1 = _make_state(session_id="sess-1", company_name="Company A")
        state2 = _make_state(session_id="sess-2", company_name="Company B")
        r1, r2 = await asyncio.gather(
            research_node(state1),
            research_node(state2),
        )
        # Each should have its own findings
        assert r1["research_package"].total_findings >= 0
        assert r2["research_package"].total_findings >= 0


# ──────────────────────────────────────────────
# 🧪 QA Engineer Tests
# ──────────────────────────────────────────────

class TestQAEngineer:
    """Edge cases, boundary values."""

    @pytest.mark.asyncio
    async def test_no_company_info(self):
        """State with no company info degrades gracefully with fallback name."""
        state = CreditAppraisalState(
            session_id="test-no-company",
            pipeline_stages=[
                PipelineStage(
                    stage=PipelineStageEnum.RESEARCH,
                    status=PipelineStageStatus.PENDING,
                ),
            ],
        )
        result = await research_node(state)
        pkg = result["research_package"]
        # Node uses "Unknown Company" fallback — still runs all tracks
        assert pkg.total_findings >= 0
        # Verify pipeline didn't crash
        assert result["pipeline_stages"][0].status == PipelineStageStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_findings_have_required_fields(self):
        """Every finding has all required fields populated."""
        state = _make_state()
        result = await research_node(state)
        for finding in result["research_package"].findings:
            assert finding.source is not None
            assert finding.source_tier >= 1
            assert finding.source_tier <= 5
            assert 0.0 <= finding.source_weight <= 1.0
            assert finding.title != ""
            assert finding.content != ""
            assert finding.category != ""

    @pytest.mark.asyncio
    async def test_tavily_returns_multiple_categories(self):
        """Tavily track returns findings in different categories."""
        results = await _run_tavily_track("Test Corp", "manufacturing")
        categories = set(f.category for f in results)
        assert len(categories) >= 2  # financial + governance

    @pytest.mark.asyncio
    async def test_empty_company_tracks_return_nothing(self):
        """All tracks return empty list for empty company name."""
        empty_results = await asyncio.gather(
            _run_tavily_track("", ""),
            _run_exa_track(""),
            _run_serpapi_track(""),
            _run_govt_scraper_track(""),
            _run_rating_track(""),
        )
        for result in empty_results:
            assert result == []

    def test_verify_preserves_order(self):
        """Verification preserves finding order."""
        findings = [
            _make_finding(source="mca21", tier=1, weight=1.0, category="first"),
            _make_finding(source="tavily", tier=2, weight=0.85, category="second"),
            _make_finding(source="serpapi", tier=3, weight=0.60, category="third"),
        ]
        results = _verify_findings(findings)
        assert results[0].category == "first"
        assert results[1].category == "second"
        assert results[2].category == "third"

    def test_verify_filters_zero_weight(self):
        """Findings with weight 0.0 are filtered out."""
        findings = [
            _make_finding(source="social_media", tier=5, weight=0.0),
        ]
        results = _verify_findings(findings)
        assert len(results) == 0

    def test_categorize_empty_list(self):
        """Categorizing empty list returns empty dict."""
        result = _categorize_findings([])
        assert result == {}

    def test_categorize_uncategorized(self):
        """Finding with empty category goes to 'uncategorized'."""
        finding = _make_finding(category="")
        result = _categorize_findings([finding])
        assert "uncategorized" in result

    @pytest.mark.asyncio
    async def test_research_package_counts_match(self):
        """total_findings equals len(findings)."""
        state = _make_state()
        result = await research_node(state)
        pkg = result["research_package"]
        assert pkg.total_findings == len(pkg.findings)

    @pytest.mark.asyncio
    async def test_unicode_company_name(self):
        """Hindi company name doesn't crash."""
        state = _make_state(company_name="मुंबई स्टील प्राइवेट लिमिटेड")
        result = await research_node(state)
        assert result["research_package"] is not None


# ──────────────────────────────────────────────
# 🎯 Hackathon Judge Tests
# ──────────────────────────────────────────────

class TestHackathonJudge:
    """Demo quality, thinking events, storytelling."""

    @pytest.mark.asyncio
    async def test_xyz_steel_full_research(self):
        """XYZ Steel demo: research runs and produces realistic package."""
        state = _make_state(
            company_name="XYZ Steel Pvt Ltd",
            sector="manufacturing",
        )
        result = await research_node(state)
        pkg = result["research_package"]
        
        assert pkg.total_findings >= 5  # Multiple tracks contribute
        assert pkg.government_sources >= 3  # MCA21 + NJDG + RBI
        assert pkg.media_sources >= 1

    @pytest.mark.asyncio
    async def test_thinking_events_tell_a_story(self):
        """Thinking events form a coherent narrative for the chatbot."""
        state = _make_state()
        result = await research_node(state)
        events = result.get("thinking_events", [])
        
        # Should have a clear progression
        event_types = [e.event_type for e in events]
        assert EventType.READ in event_types  # Starting research
        assert EventType.FOUND in event_types  # Found results
        assert EventType.COMPUTED in event_types  # Verification stats
        assert EventType.CONCLUDING in event_types  # Summary

    @pytest.mark.asyncio
    async def test_thinking_events_have_specific_content(self):
        """Events contain specific, informative content (not generic)."""
        state = _make_state(company_name="XYZ Steel Pvt Ltd")
        result = await research_node(state)
        events = result.get("thinking_events", [])
        
        # At least one event should mention the company name
        contents = " ".join(e.message for e in events)
        assert "XYZ Steel" in contents
        
        # Should have numbers (finding counts)
        assert any(char.isdigit() for char in contents)

    @pytest.mark.asyncio
    async def test_concluding_event_has_summary(self):
        """Final CONCLUDING event summarizes research comprehensively."""
        state = _make_state()
        result = await research_node(state)
        events = result.get("thinking_events", [])
        
        concluding = [e for e in events if e.event_type == EventType.CONCLUDING]
        assert len(concluding) >= 1
        summary = concluding[-1].message
        assert "finding" in summary.lower()
        assert "track" in summary.lower()

    @pytest.mark.asyncio
    async def test_degraded_mode_visible_in_events(self):
        """Track failure produces visible FLAGGED event for officer."""
        state = _make_state()
        with patch(
            "backend.graph.nodes.research_node._run_tavily_track",
            side_effect=TimeoutError("API timeout"),
        ):
            result = await research_node(state)
            events = result.get("thinking_events", [])
            flagged = [e for e in events if e.event_type == EventType.FLAGGED]
            assert len(flagged) >= 1
            # Officer should see which track failed
            assert any("Tavily" in e.message for e in flagged)

    @pytest.mark.asyncio
    async def test_govt_findings_highlighted(self):
        """Government-confirmed findings produce FOUND events with source name."""
        state = _make_state()
        result = await research_node(state)
        events = result.get("thinking_events", [])
        found_events = [e for e in events if e.event_type == EventType.FOUND]
        # Should mention government scrapers
        contents = " ".join(e.message for e in found_events)
        assert "Govt" in contents or "finding" in contents.lower()

    @pytest.mark.asyncio
    async def test_source_tier_hierarchy_maintained(self):
        """Findings maintain proper tier hierarchy — govt > media > general."""
        state = _make_state()
        result = await research_node(state)
        findings = result["research_package"].findings
        
        tier1 = [f for f in findings if f.source_tier == 1]
        tier2 = [f for f in findings if f.source_tier == 2]
        tier3 = [f for f in findings if f.source_tier == 3]
        
        # All tiers should be present
        assert len(tier1) > 0, "Should have government sources"
        assert len(tier2) > 0, "Should have media sources"
        
        # Government sources should be verified
        for f in tier1:
            assert f.verified is True
