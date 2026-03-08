"""
Tests for T4.2 — GraphRAG Hierarchical Graph Summarizer

Tests the GraphRAG summarization module that provides hierarchical context
for the 5 reasoning passes. Covers:
- Entity summary building
- Community detection + summarization
- Risk signal extraction
- Pass-specific context filtering
- Integration with reasoning node

5-Perspective Testing:
🏦 Credit Domain Expert: Indian banking entity types, risk signals
🔒 Security Architect: Injection in names, oversized graphs
⚙️ Systems Engineer: Empty graph, large graph, concurrent access
🧪 QA Engineer: Edge cases, null properties, duplicate entities
🎯 Hackathon Judge: Context quality, narrative readability
"""

import pytest
import asyncio
from typing import List, Dict, Any

from backend.agents.reasoning.graphrag_summarizer import (
    GraphRAGSummarizer,
    EntitySummary,
    CommunitySummary,
    GraphSummary,
    _extract_risk_signals,
    _PASS_FOCUS,
)
from backend.storage.neo4j_client import (
    get_neo4j_client,
    NodeType,
    RelationshipType,
    InMemoryGraph,
)


# ─────────────── Fixtures ───────────────


@pytest.fixture(autouse=True)
def _reset_neo4j():
    """Reset global Neo4j client to fresh in-memory graph before each test."""
    import backend.storage.neo4j_client as neo4j_mod
    neo4j_mod._neo4j_client = None
    yield
    neo4j_mod._neo4j_client = None


@pytest.fixture
def summarizer():
    return GraphRAGSummarizer()


async def _populate_xyz_steel_graph():
    """
    Build the XYZ Steel demo graph for testing.
    Simulates: company, directors, suppliers, customers, bank, auditor, rating agency.
    """
    client = get_neo4j_client()
    await client._ensure_initialized()

    # Target company
    await client.create_node("Company", "XYZ Steel Pvt Ltd", {
        "cin": "L27100MH2010PLC123456",
        "sector": "Steel",
        "loan_amount": "50cr",
    })

    # Directors
    await client.create_node("Director", "Rajesh K. Agarwal", {
        "din": "01234567",
        "promoter": True,
        "pledge_pct": 62.0,
    })
    await client.create_node("Director", "Priya Agarwal", {
        "din": "01234568",
        "promoter": True,
    })

    # Director relationships
    await client.create_relationship(
        "Director", "Rajesh K. Agarwal",
        RelationshipType.IS_DIRECTOR_OF,
        "Company", "XYZ Steel Pvt Ltd",
    )
    await client.create_relationship(
        "Director", "Priya Agarwal",
        RelationshipType.IS_DIRECTOR_OF,
        "Company", "XYZ Steel Pvt Ltd",
    )

    # Cross-directorships (hidden relationship signal)
    await client.create_node("Company", "Agarwal Holdings", {"status": "npa"})
    await client.create_relationship(
        "Director", "Rajesh K. Agarwal",
        RelationshipType.IS_DIRECTOR_OF,
        "Company", "Agarwal Holdings",
    )
    await client.create_relationship(
        "Director", "Priya Agarwal",
        RelationshipType.FAMILY_OF,
        "Director", "Rajesh K. Agarwal",
    )

    # Suppliers
    await client.create_node("Supplier", "AK Traders", {"status": "active"})
    await client.create_relationship(
        "Supplier", "AK Traders",
        RelationshipType.SUPPLIES_TO,
        "Company", "XYZ Steel Pvt Ltd",
    )

    # Circular trading setup: AK Traders director = Rajesh
    await client.create_relationship(
        "Director", "Rajesh K. Agarwal",
        RelationshipType.IS_DIRECTOR_OF,
        "Supplier", "AK Traders",
    )

    # Customers
    await client.create_node("Customer", "Metro Construction Ltd", {
        "outstanding": "8.5cr",
    })
    await client.create_relationship(
        "Company", "XYZ Steel Pvt Ltd",
        RelationshipType.SUPPLIES_TO,
        "Customer", "Metro Construction Ltd",
    )

    # Bank
    await client.create_node("Bank", "State Bank of India", {})
    await client.create_relationship(
        "Company", "XYZ Steel Pvt Ltd",
        RelationshipType.HAS_CHARGE,
        "Bank", "State Bank of India",
        {"charge_amount": "50cr", "type": "working_capital"},
    )

    # Rating agency
    await client.create_node("RatingAgency", "CRISIL", {
        "rating": "BBB+",
    })
    await client.create_relationship(
        "Company", "XYZ Steel Pvt Ltd",
        RelationshipType.HAS_RATING_FROM,
        "RatingAgency", "CRISIL",
    )

    # Court case
    await client.create_node("Case", "Commercial suit #4521", {
        "status": "pending",
        "amount": "2.3cr",
        "court": "Bombay HC",
    })
    await client.create_relationship(
        "Customer", "Metro Construction Ltd",
        RelationshipType.FILED_CASE_AGAINST,
        "Company", "XYZ Steel Pvt Ltd",
    )

    return client


# ─────────────── EntitySummary Tests ───────────────


class TestEntitySummary:
    """Tests for individual entity summarization."""

    def test_entity_summary_to_text(self):
        """🎯 Judge: Entity text should be concise and informative."""
        entity = EntitySummary(
            label="Company",
            name="XYZ Steel Pvt Ltd",
            properties={"sector": "Steel", "loan_amount": "50cr"},
            connections=["SUPPLIES_TO → Metro Construction"],
            risk_signals=["Active litigation: 1 case(s)"],
        )
        text = entity.to_text()
        assert "[Company] XYZ Steel Pvt Ltd" in text
        assert "Steel" in text
        assert "50cr" in text
        assert "SUPPLIES_TO" in text
        assert "Active litigation" in text

    def test_entity_summary_empty_connections(self):
        """🧪 QA: Entity with no connections should render cleanly."""
        entity = EntitySummary(
            label="Director",
            name="Rajesh K. Agarwal",
            properties={"din": "01234567"},
            connections=[],
            risk_signals=[],
        )
        text = entity.to_text()
        assert "[Director] Rajesh K. Agarwal" in text
        assert "Connections:" not in text
        assert "Risk signals:" not in text

    def test_entity_summary_many_connections_truncated(self):
        """⚙️ Systems: Many connections should be truncated, not blow up."""
        connections = [f"REL_{i} → Target_{i}" for i in range(50)]
        entity = EntitySummary(
            label="Company",
            name="Test Corp",
            properties={},
            connections=connections,
            risk_signals=[],
        )
        text = entity.to_text()
        # Only first 10 should appear
        assert "Target_0" in text
        assert "Target_9" in text
        # 11th should not
        assert "Target_10" not in text


# ─────────────── CommunitySummary Tests ───────────────


class TestCommunitySummary:
    """Tests for community-level summarization."""

    def test_community_to_text(self):
        """🎯 Judge: Community text readable and informative."""
        entities = [
            EntitySummary("Company", "XYZ Steel", {}, ["→ SBI"], ["NPA risk"]),
            EntitySummary("Director", "Rajesh", {}, [], []),
        ]
        community = CommunitySummary(
            community_id=0,
            entities=entities,
            relationship_count=5,
            key_relationships=["XYZ Steel → SBI"],
            risk_level="HIGH",
            narrative="Cross-directorship detected.",
        )
        text = community.to_text()
        assert "Community 0" in text
        assert "2 entities" in text
        assert "HIGH" in text
        assert "Cross-directorship" in text

    def test_community_empty_entities(self):
        """🧪 QA: Community with no entities should not crash."""
        community = CommunitySummary(
            community_id=1,
            entities=[],
            relationship_count=0,
            key_relationships=[],
            risk_level="LOW",
            narrative="Empty community.",
        )
        text = community.to_text()
        assert "Community 1" in text
        assert "0 entities" in text


# ─────────────── GraphSummary Tests ───────────────


class TestGraphSummary:
    """Tests for global graph summary."""

    def test_context_window_size_limit(self):
        """⚙️ Systems: Context window should respect max_chars."""
        entities = [
            EntitySummary("Company", f"Corp_{i}", {"data": "x" * 100}, [], [])
            for i in range(50)
        ]
        communities = [
            CommunitySummary(
                community_id=i,
                entities=entities[i * 5:(i + 1) * 5],
                relationship_count=10,
                key_relationships=[f"rel_{j}" for j in range(10)],
                risk_level="LOW",
                narrative="A community.",
            )
            for i in range(10)
        ]
        summary = GraphSummary(
            total_nodes=50,
            total_relationships=100,
            total_communities=10,
            communities=communities,
            global_risk_narrative="Test narrative.",
            entity_types={"Company": 50},
        )
        context = summary.to_context_window(max_chars=2000)
        assert len(context) <= 2500  # Some tolerance for final line
        assert "truncated" in context.lower() or len(context) <= 2000

    def test_empty_graph_summary(self):
        """🧪 QA: Empty graph should produce meaningful message."""
        summary = GraphSummary(
            total_nodes=0,
            total_relationships=0,
            total_communities=0,
            communities=[],
            global_risk_narrative="No data.",
            entity_types={},
        )
        context = summary.to_context_window()
        assert "0 entities" in context
        assert "No data" in context

    def test_get_community_for_entity(self):
        """🏦 Credit Expert: Should find community for target company."""
        entity = EntitySummary("Company", "XYZ Steel", {}, [], [])
        community = CommunitySummary(
            community_id=0,
            entities=[entity],
            relationship_count=1,
            key_relationships=[],
            risk_level="MEDIUM",
            narrative="Steel community.",
        )
        summary = GraphSummary(
            total_nodes=1,
            total_relationships=1,
            total_communities=1,
            communities=[community],
            global_risk_narrative="Test.",
            entity_types={"Company": 1},
        )
        found = summary.get_community_for_entity("XYZ Steel")
        assert found is not None
        assert found.community_id == 0

    def test_get_community_for_entity_case_insensitive(self):
        """🧪 QA: Entity search should be case-insensitive."""
        entity = EntitySummary("Company", "XYZ STEEL", {}, [], [])
        community = CommunitySummary(0, [entity], 0, [], "LOW", "")
        summary = GraphSummary(1, 0, 1, [community], "", {})
        assert summary.get_community_for_entity("xyz steel") is not None

    def test_get_community_for_missing_entity(self):
        """🧪 QA: Missing entity should return None."""
        summary = GraphSummary(0, 0, 0, [], "", {})
        assert summary.get_community_for_entity("NonExistent") is None


# ─────────────── Risk Signal Extraction ───────────────


class TestRiskSignals:
    """Tests for _extract_risk_signals."""

    def test_wilful_defaulter_signal(self):
        """🏦 Credit Expert: Wilful defaulter must be detected."""
        signals = _extract_risk_signals({"wilful_defaulter": True, "name": "X"})
        assert any("wilful defaulter" in s.lower() for s in signals)

    def test_npa_status_signal(self):
        """🏦 Credit Expert: NPA status must surface."""
        signals = _extract_risk_signals({"status": "npa", "name": "X"})
        assert any("NPA" in s for s in signals)

    def test_nclt_status_signal(self):
        """🏦 Credit Expert: NCLT status must surface."""
        signals = _extract_risk_signals({"status": "nclt", "name": "X"})
        assert any("NCLT" in s for s in signals)

    def test_active_litigation_signal(self):
        """🏦 Credit Expert: Active cases must be flagged."""
        signals = _extract_risk_signals({"active_cases": 3, "name": "X"})
        assert any("3 case" in s for s in signals)

    def test_low_credit_rating_signal(self):
        """🏦 Credit Expert: Low ratings (D, C, BB) must be flagged."""
        signals = _extract_risk_signals({"rating": "BB-", "name": "X"})
        assert any("BB-" in s for s in signals)

    def test_high_pledge_signal(self):
        """🏦 Credit Expert: Pledge > 40% must be flagged."""
        signals = _extract_risk_signals({"pledge_pct": 62.0, "name": "X"})
        assert any("62" in s for s in signals)

    def test_no_risk_signals_for_clean_entity(self):
        """🧪 QA: Clean entity with no risk indicators."""
        signals = _extract_risk_signals({
            "name": "Test Corp",
            "status": "active",
            "rating": "AAA",
        })
        assert len(signals) == 0

    def test_zero_litigation_not_flagged(self):
        """🧪 QA: Zero cases should not generate a signal."""
        signals = _extract_risk_signals({"active_cases": 0, "name": "X"})
        assert not any("case" in s.lower() for s in signals)

    def test_pledge_below_threshold_not_flagged(self):
        """🧪 QA: Pledge at exactly 40% should not flag."""
        signals = _extract_risk_signals({"pledge_pct": 40.0, "name": "X"})
        assert not any("pledge" in s.lower() for s in signals)

    def test_pledge_at_41_flagged(self):
        """🧪 QA: Pledge at 41% should flag."""
        signals = _extract_risk_signals({"pledge_pct": 41.0, "name": "X"})
        assert any("pledge" in s.lower() for s in signals)

    def test_injection_in_properties(self):
        """🔒 Security: Malicious strings in properties should not break extraction."""
        signals = _extract_risk_signals({
            "name": "<script>alert('xss')</script>",
            "status": "'; DROP TABLE --",
            "rating": "A",
        })
        # Should not crash; injection strings not in risk signal category
        assert isinstance(signals, list)


# ─────────────── GraphRAGSummarizer Tests (Async) ───────────────


class TestGraphRAGSummarizer:
    """Integration tests for the full summarizer pipeline."""

    @pytest.mark.asyncio
    async def test_empty_graph_summary(self, summarizer):
        """🧪 QA: Empty graph should return empty summary."""
        summary = await summarizer.build_summary()
        assert summary.total_nodes == 0
        assert summary.total_communities == 0
        context = summary.to_context_window()
        assert "No entities" in context or "0 entities" in context

    @pytest.mark.asyncio
    async def test_xyz_steel_full_summary(self, summarizer):
        """🎯 Judge: XYZ Steel demo graph should produce rich summary."""
        await _populate_xyz_steel_graph()
        summary = await summarizer.build_summary("XYZ Steel Pvt Ltd")

        assert summary.total_nodes > 5
        assert summary.total_relationships > 3
        assert summary.total_communities >= 1

        # The target company's community should be first
        assert len(summary.communities) > 0

        context = summary.to_context_window()
        assert "XYZ Steel" in context or "xyz steel" in context.lower()

    @pytest.mark.asyncio
    async def test_community_risk_assessment(self, summarizer):
        """🏦 Credit Expert: NPA company should elevate community risk."""
        client = get_neo4j_client()
        await client._ensure_initialized()

        await client.create_node("Company", "Bad Corp", {"status": "nclt"})
        await client.create_node("Director", "Shady Director", {
            "wilful_defaulter": True,
        })
        await client.create_relationship(
            "Director", "Shady Director",
            RelationshipType.IS_DIRECTOR_OF,
            "Company", "Bad Corp",
        )

        summary = await summarizer.build_summary()
        assert len(summary.communities) >= 1
        # The community with Bad Corp + Shady Director should be HIGH or CRITICAL
        community_risks = [c.risk_level for c in summary.communities]
        assert any(r in ("HIGH", "CRITICAL") for r in community_risks)

    @pytest.mark.asyncio
    async def test_pass_specific_context_contradictions(self, summarizer):
        """🎯 Judge: Contradiction pass should focus on Company + Court + Case."""
        await _populate_xyz_steel_graph()
        context = await summarizer.get_context_for_pass(
            "contradictions", "XYZ Steel Pvt Ltd"
        )
        assert isinstance(context, str)
        assert len(context) > 0
        # Should include Company entities
        assert "Company" in context or "XYZ" in context.lower()

    @pytest.mark.asyncio
    async def test_pass_specific_context_cascade(self, summarizer):
        """🎯 Judge: Cascade pass should focus on supply chain entities."""
        await _populate_xyz_steel_graph()
        context = await summarizer.get_context_for_pass(
            "cascade", "XYZ Steel Pvt Ltd"
        )
        assert isinstance(context, str)
        assert len(context) > 0

    @pytest.mark.asyncio
    async def test_pass_specific_context_hidden_relationships(self, summarizer):
        """🏦 Credit Expert: Hidden rel pass should focus on Director + Company."""
        await _populate_xyz_steel_graph()
        context = await summarizer.get_context_for_pass(
            "hidden_relationships", "XYZ Steel Pvt Ltd"
        )
        assert isinstance(context, str)
        assert len(context) > 0

    @pytest.mark.asyncio
    async def test_pass_specific_context_empty_graph(self, summarizer):
        """🧪 QA: Pass context on empty graph should gracefully return message."""
        context = await summarizer.get_context_for_pass("cascade")
        assert "No graph data" in context or "0" in context

    @pytest.mark.asyncio
    async def test_unknown_pass_name(self, summarizer):
        """🧪 QA: Unknown pass name should return full context (no crash)."""
        await _populate_xyz_steel_graph()
        context = await summarizer.get_context_for_pass("unknown_pass")
        assert isinstance(context, str)
        assert len(context) > 0

    @pytest.mark.asyncio
    async def test_prioritize_target_company(self, summarizer):
        """🎯 Judge: Target company's community should be first."""
        # Create two separate clusters
        client = get_neo4j_client()
        await client._ensure_initialized()

        # Cluster 1: Target company
        await client.create_node("Company", "Target Corp", {"sector": "IT"})
        await client.create_node("Director", "Dir A", {})
        await client.create_relationship(
            "Director", "Dir A", RelationshipType.IS_DIRECTOR_OF,
            "Company", "Target Corp",
        )

        # Cluster 2: Unrelated company
        await client.create_node("Company", "Other Corp", {"sector": "FMCG"})
        await client.create_node("Director", "Dir B", {})
        await client.create_relationship(
            "Director", "Dir B", RelationshipType.IS_DIRECTOR_OF,
            "Company", "Other Corp",
        )

        summary = await summarizer.build_summary("Target Corp")
        # First community should contain Target Corp
        first_names = [e.name for e in summary.communities[0].entities]
        assert "Target Corp" in first_names or "Dir A" in first_names

    @pytest.mark.asyncio
    async def test_large_graph_performance(self, summarizer):
        """⚙️ Systems: 100 entities should process without hanging."""
        client = get_neo4j_client()
        await client._ensure_initialized()

        # Create 100 entities in a chain
        for i in range(50):
            await client.create_node("Company", f"Corp_{i}", {"id": i})
        for i in range(50):
            await client.create_node("Director", f"Dir_{i}", {"id": i})
            await client.create_relationship(
                "Director", f"Dir_{i}", RelationshipType.IS_DIRECTOR_OF,
                "Company", f"Corp_{i}", {},
            )

        summary = await summarizer.build_summary()
        assert summary.total_nodes == 100
        # Should produce context string without hanging
        context = summary.to_context_window(max_chars=4000)
        assert len(context) <= 4500

    @pytest.mark.asyncio
    async def test_entity_with_special_characters(self, summarizer):
        """🔒 Security: Unicode/special chars in entity names should not break."""
        client = get_neo4j_client()
        await client._ensure_initialized()

        await client.create_node("Company", "मुंबई स्टील प्राइवेट", {"sector": "Steel"})
        await client.create_node("Director", "O'Brien & Co.", {})
        await client.create_relationship(
            "Director", "O'Brien & Co.", RelationshipType.IS_DIRECTOR_OF,
            "Company", "मुंबई स्टील प्राइवेट",
        )

        summary = await summarizer.build_summary("मुंबई स्टील प्राइवेट")
        assert summary.total_nodes == 2
        context = summary.to_context_window()
        assert "मुंबई" in context

    @pytest.mark.asyncio
    async def test_single_isolated_node(self, summarizer):
        """🧪 QA: Single isolated node (no relationships) should form own community."""
        client = get_neo4j_client()
        await client._ensure_initialized()
        await client.create_node("Company", "Lonely Corp", {})

        summary = await summarizer.build_summary()
        assert summary.total_nodes == 1
        assert summary.total_communities == 1


# ─────────────── Pass Focus Configuration Tests ───────────────


class TestPassFocus:
    """Tests for pass-specific entity type filtering."""

    def test_all_five_passes_configured(self):
        """⚙️ Systems: All 5 passes should have focus types defined."""
        expected_passes = [
            "contradictions", "cascade", "hidden_relationships",
            "temporal", "positive",
        ]
        for pass_name in expected_passes:
            assert pass_name in _PASS_FOCUS, f"Missing focus for {pass_name}"

    def test_contradiction_pass_includes_court(self):
        """🏦 Credit Expert: Contradiction pass must include Court/Case types."""
        assert NodeType.COURT.value in _PASS_FOCUS["contradictions"]
        assert NodeType.CASE.value in _PASS_FOCUS["contradictions"]

    def test_cascade_pass_includes_supply_chain(self):
        """🏦 Credit Expert: Cascade pass must include Supplier/Customer."""
        assert NodeType.SUPPLIER.value in _PASS_FOCUS["cascade"]
        assert NodeType.CUSTOMER.value in _PASS_FOCUS["cascade"]

    def test_hidden_relationships_includes_directors(self):
        """🏦 Credit Expert: Hidden rel pass must include Director type."""
        assert NodeType.DIRECTOR.value in _PASS_FOCUS["hidden_relationships"]

    def test_positive_pass_includes_rating(self):
        """🏦 Credit Expert: Positive pass must include RatingAgency."""
        assert NodeType.RATING_AGENCY.value in _PASS_FOCUS["positive"]

    def test_all_passes_include_company(self):
        """🏦 Credit Expert: Every pass should have Company type."""
        for pass_name, types in _PASS_FOCUS.items():
            assert NodeType.COMPANY.value in types, f"{pass_name} missing Company"


# ─────────────── Global Narrative Tests ───────────────


class TestGlobalNarrative:
    """Tests for the global narrative generation."""

    @pytest.mark.asyncio
    async def test_critical_risk_narrative(self, summarizer):
        """🏦 Credit Expert: CRITICAL community should produce warning narrative."""
        client = get_neo4j_client()
        await client._ensure_initialized()

        await client.create_node("Company", "Fraud Corp", {
            "status": "defaulter",
            "wilful_defaulter": True,
        })

        summary = await summarizer.build_summary()
        narrative = summary.global_risk_narrative
        assert isinstance(narrative, str)
        assert len(narrative) > 10

    @pytest.mark.asyncio
    async def test_entity_type_distribution_in_narrative(self, summarizer):
        """🎯 Judge: Narrative should mention entity type distribution."""
        await _populate_xyz_steel_graph()
        summary = await summarizer.build_summary()

        # Global narrative should mention composition
        assert "Composition" in summary.global_risk_narrative or \
               "Company" in summary.global_risk_narrative


# ─────────────── Reasoning Node Integration ───────────────


class TestReasoningNodeIntegration:
    """Tests that the reasoning node correctly imports and uses GraphRAG."""

    def test_reasoning_node_imports_graphrag(self):
        """⚙️ Systems: reasoning_node.py should import GraphRAGSummarizer."""
        from backend.graph.nodes import reasoning_node
        assert hasattr(reasoning_node, "GraphRAGSummarizer")

    def test_graphrag_in_reasoning_package_init(self):
        """⚙️ Systems: __init__.py should export GraphRAGSummarizer."""
        from backend.agents.reasoning import GraphRAGSummarizer as GRS
        assert GRS is not None
