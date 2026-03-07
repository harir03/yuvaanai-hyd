"""
Tests for T1.3 — Neo4j Knowledge Graph (Entity-Relationship Network)

Covers:
1. InMemoryGraph — CRUD, multi-hop, shared directors, circular trading, clusters
2. Neo4jClient — singleton, fallback, node/relationship operations
3. GraphBuilder — build_knowledge_graph from W1/W2/W3 worker data
4. Neo4jEnricher — enrich_graph_from_research, mock MCA21/NJDG
5. Integration — build graph + enrich + query
"""

import pytest
from backend.storage.neo4j_client import (
    InMemoryGraph,
    Neo4jClient,
    NodeType,
    RelationshipType,
    get_neo4j_client,
    reset_neo4j_client,
)
from backend.agents.organizer.graph_builder import build_knowledge_graph
from backend.agents.research.neo4j_enricher import (
    enrich_graph_from_research,
    enrich_with_mock_mca21,
    enrich_with_mock_njdg,
)


# ── Fixtures ──

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the Neo4j singleton before/after each test."""
    reset_neo4j_client()
    yield
    reset_neo4j_client()


@pytest.fixture
def graph():
    """Fresh InMemoryGraph for unit tests."""
    return InMemoryGraph()


# ══════════════════════════════════════════════
#  1. InMemoryGraph — Unit Tests
# ══════════════════════════════════════════════

class TestInMemoryGraphCRUD:
    """Test basic node and relationship operations."""

    async def test_create_node(self, graph):
        node_id = await graph.create_node("Company", "XYZ Steel")
        assert node_id == "Company::xyz steel"
        assert await graph.get_node_count() == 1

    async def test_create_node_with_properties(self, graph):
        await graph.create_node("Director", "Rajesh Kumar", {"din": "00123456"})
        node = await graph.get_node("Director", "Rajesh Kumar")
        assert node is not None
        assert node["name"] == "Rajesh Kumar"
        assert node["din"] == "00123456"

    async def test_create_node_idempotent(self, graph):
        """Creating same node twice should merge, not duplicate."""
        await graph.create_node("Company", "XYZ Steel", {"cin": "L27100"})
        await graph.create_node("Company", "XYZ Steel", {"revenue": 14230})
        assert await graph.get_node_count() == 1
        node = await graph.get_node("Company", "XYZ Steel")
        assert node["cin"] == "L27100"
        assert node["revenue"] == 14230

    async def test_get_node_not_found(self, graph):
        result = await graph.get_node("Company", "Nonexistent")
        assert result is None

    async def test_get_nodes_by_label(self, graph):
        await graph.create_node("Director", "Rajesh Kumar")
        await graph.create_node("Director", "Priya Sharma")
        await graph.create_node("Company", "XYZ Steel")
        directors = await graph.get_nodes_by_label("Director")
        assert len(directors) == 2

    async def test_create_relationship(self, graph):
        created = await graph.create_relationship(
            "Director", "Rajesh Kumar",
            "IS_DIRECTOR_OF",
            "Company", "XYZ Steel",
        )
        assert created is True
        # Nodes should be auto-created
        assert await graph.get_node_count() == 2
        assert await graph.get_relationship_count() == 1

    async def test_relationship_idempotent(self, graph):
        """Creating same relationship twice returns False."""
        await graph.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "XYZ",
        )
        created_again = await graph.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "XYZ",
        )
        assert created_again is False
        assert await graph.get_relationship_count() == 1

    async def test_get_relationships_filtered(self, graph):
        await graph.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "XYZ",
        )
        await graph.create_relationship(
            "Auditor", "RST & Associates", "IS_AUDITOR_OF", "Company", "XYZ",
        )
        rels = await graph.get_relationships(rel_type="IS_DIRECTOR_OF")
        assert len(rels) == 1
        assert rels[0]["relationship"] == "IS_DIRECTOR_OF"

    async def test_get_relationships_by_from_node(self, graph):
        await graph.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "XYZ",
        )
        await graph.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "ABC Holdings",
        )
        rels = await graph.get_relationships(
            from_label="Director", from_name="Rajesh",
        )
        assert len(rels) == 2

    async def test_clear(self, graph):
        await graph.create_node("Company", "XYZ")
        await graph.create_relationship("A", "a", "R", "B", "b")
        await graph.clear()
        assert await graph.get_node_count() == 0
        assert await graph.get_relationship_count() == 0


class TestInMemoryGraphQueries:
    """Test graph intelligence queries."""

    async def test_multi_hop_query(self, graph):
        """Test BFS from Company through Director to another Company."""
        await graph.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "XYZ Steel",
        )
        await graph.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "Agarwal Holdings",
        )

        paths = await graph.multi_hop_query("Company", "XYZ Steel", max_hops=2)
        assert len(paths) >= 1
        # Should reach Rajesh at hop 1, Agarwal Holdings at hop 2
        end_names = [p["end_node"].get("name") for p in paths]
        assert "Rajesh" in end_names
        assert "Agarwal Holdings" in end_names

    async def test_multi_hop_respects_max(self, graph):
        """Cannot reach beyond max_hops."""
        await graph.create_relationship("A", "a", "R1", "B", "b")
        await graph.create_relationship("B", "b", "R2", "C", "c")
        await graph.create_relationship("C", "c", "R3", "D", "d")

        paths = await graph.multi_hop_query("A", "a", max_hops=2)
        end_names = [p["end_node"].get("name") for p in paths]
        assert "b" in end_names
        assert "c" in end_names
        assert "d" not in end_names

    async def test_multi_hop_nonexistent_start(self, graph):
        paths = await graph.multi_hop_query("Company", "Nonexistent")
        assert paths == []

    async def test_find_shared_directors(self, graph):
        """Director linked to multiple companies."""
        await graph.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "XYZ Steel",
        )
        await graph.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "Agarwal Holdings",
        )
        await graph.create_relationship(
            "Director", "Priya", "IS_DIRECTOR_OF", "Company", "XYZ Steel",
        )

        shared = await graph.find_shared_directors()
        assert len(shared) == 1
        assert shared[0]["director"] == "Rajesh"
        assert len(shared[0]["companies"]) == 2

    async def test_find_shared_directors_none(self, graph):
        """No shared directors if each director is on one company."""
        await graph.create_relationship(
            "Director", "A", "IS_DIRECTOR_OF", "Company", "C1",
        )
        await graph.create_relationship(
            "Director", "B", "IS_DIRECTOR_OF", "Company", "C2",
        )
        shared = await graph.find_shared_directors()
        assert shared == []

    async def test_detect_circular_trading(self, graph):
        """A supplies to B, B supplies to C, C supplies to A."""
        await graph.create_relationship(
            "Company", "A", "SUPPLIES_TO", "Company", "B",
        )
        await graph.create_relationship(
            "Company", "B", "SUPPLIES_TO", "Company", "C",
        )
        await graph.create_relationship(
            "Company", "C", "SUPPLIES_TO", "Company", "A",
        )
        cycles = await graph.detect_circular_trading()
        assert len(cycles) >= 1
        # Cycle should include A, B, C
        cycle_names = cycles[0]
        assert set(cycle_names) == {"A", "B", "C"}

    async def test_detect_circular_trading_none(self, graph):
        """No cycle in a linear supply chain."""
        await graph.create_relationship(
            "Company", "A", "SUPPLIES_TO", "Company", "B",
        )
        await graph.create_relationship(
            "Company", "B", "SUPPLIES_TO", "Company", "C",
        )
        cycles = await graph.detect_circular_trading()
        assert cycles == []

    async def test_community_clusters(self, graph):
        """Two disconnected groups should form two clusters."""
        # Group 1
        await graph.create_relationship("A", "a1", "R", "A", "a2")
        # Group 2
        await graph.create_relationship("B", "b1", "R", "B", "b2")

        clusters = await graph.get_community_clusters()
        assert len(clusters) == 2

    async def test_stats(self, graph):
        await graph.create_node("Company", "XYZ")
        await graph.create_node("Director", "Rajesh")
        await graph.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "XYZ",
        )
        stats = await graph.get_stats()
        assert stats["total_nodes"] == 2
        assert stats["total_relationships"] == 1
        assert stats["nodes_by_label"]["Company"] == 1
        assert stats["nodes_by_label"]["Director"] == 1
        assert stats["relationships_by_type"]["IS_DIRECTOR_OF"] == 1


# ══════════════════════════════════════════════
#  2. Neo4jClient — Singleton & Fallback
# ══════════════════════════════════════════════

class TestNeo4jClient:
    """Test Neo4j client singleton and in-memory fallback."""

    async def test_singleton(self):
        client1 = get_neo4j_client()
        client2 = get_neo4j_client()
        assert client1 is client2

    async def test_singleton_reset(self):
        client1 = get_neo4j_client()
        reset_neo4j_client()
        client2 = get_neo4j_client()
        assert client1 is not client2

    async def test_fallback_to_memory(self):
        """No URI → in-memory fallback."""
        client = get_neo4j_client()
        await client.initialize()
        assert client.backend == "memory"
        assert client.is_initialized is True

    async def test_client_create_node(self):
        client = get_neo4j_client()
        await client.initialize()
        result = await client.create_node("Company", "XYZ Steel", {"cin": "L27100"})
        assert result is not None
        node = await client.get_node("Company", "XYZ Steel")
        assert node is not None
        assert node["cin"] == "L27100"

    async def test_client_create_relationship(self):
        client = get_neo4j_client()
        await client.initialize()
        created = await client.create_relationship(
            "Director", "Rajesh",
            "IS_DIRECTOR_OF",
            "Company", "XYZ Steel",
        )
        assert created is True

    async def test_client_get_nodes_by_label(self):
        client = get_neo4j_client()
        await client.initialize()
        await client.create_node("Director", "Rajesh")
        await client.create_node("Director", "Priya")
        directors = await client.get_nodes_by_label("Director")
        assert len(directors) == 2

    async def test_client_multi_hop(self):
        client = get_neo4j_client()
        await client.initialize()
        await client.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "XYZ",
        )
        await client.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "ABC",
        )
        paths = await client.multi_hop_query("Company", "XYZ", max_hops=2)
        assert len(paths) >= 1

    async def test_client_shared_directors(self):
        client = get_neo4j_client()
        await client.initialize()
        await client.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "XYZ",
        )
        await client.create_relationship(
            "Director", "Rajesh", "IS_DIRECTOR_OF", "Company", "ABC",
        )
        shared = await client.find_shared_directors()
        assert len(shared) == 1

    async def test_client_circular_trading(self):
        client = get_neo4j_client()
        await client.initialize()
        await client.create_relationship("Company", "A", "SUPPLIES_TO", "Company", "B")
        await client.create_relationship("Company", "B", "SUPPLIES_TO", "Company", "C")
        await client.create_relationship("Company", "C", "SUPPLIES_TO", "Company", "A")
        cycles = await client.detect_circular_trading()
        assert len(cycles) >= 1

    async def test_client_stats(self):
        client = get_neo4j_client()
        await client.initialize()
        await client.create_node("Company", "XYZ")
        stats = await client.get_stats()
        assert stats["total_nodes"] == 1

    async def test_client_clear(self):
        client = get_neo4j_client()
        await client.initialize()
        await client.create_node("Company", "XYZ")
        await client.clear()
        stats = await client.get_stats()
        assert stats["total_nodes"] == 0


# ══════════════════════════════════════════════
#  3. Graph Builder — From Worker Outputs
# ══════════════════════════════════════════════

# Mock worker outputs matching real worker data structures

MOCK_W1_DATA = {
    "company_name": "XYZ Steel Industries Ltd",
    "cin": "L27100MH2001PLC123456",
    "directors": [
        {"name": "Rajesh Kumar", "designation": "Managing Director", "din": "00123456"},
        {"name": "Priya Sharma", "designation": "Independent Director", "din": "00789012"},
        {"name": "Vikram Desai", "designation": "CFO", "din": "00345678"},
    ],
    "auditor": {
        "name": "M/s. RST & Associates",
        "type": "Statutory Auditor",
        "opinion": "Qualified (with Emphasis of Matter)",
    },
    "rpts": {
        "count": 5,
        "total_amount": 1840.0,
        "transactions": [
            {"party": "ABC Trading (promoter entity)", "amount": 720.0, "nature": "purchases"},
            {"party": "PQR Logistics (director interest)", "amount": 480.0, "nature": "services"},
            {"party": "Steel Suppliers Pvt Ltd (group co)", "amount": 340.0, "nature": "purchases"},
            {"party": "XYZ Foundation (promoter trust)", "amount": 180.0, "nature": "donations"},
            {"party": "Green Energy Pvt Ltd (KMP interest)", "amount": 120.0, "nature": "services"},
        ],
    },
    "litigation_disclosure": {
        "cases_disclosed": 2,
        "cases": [
            {"type": "tax_dispute", "amount": 320.0, "status": "pending", "forum": "ITAT"},
            {"type": "commercial", "amount": 180.0, "status": "pending", "forum": "NCLT"},
        ],
    },
}

MOCK_W2_DATA = {
    "bank_name": "HDFC Bank",
    "account_type": "Current Account",
    "emi_regularity": {"monthly_emi_amount": 42.0},
}


class TestGraphBuilder:
    """Test building the knowledge graph from worker outputs."""

    async def test_build_from_w1(self):
        """W1 produces Company + Directors + Auditor + RPT parties + Litigation."""
        result = await build_knowledge_graph(
            session_id="test-session-001",
            worker_outputs={"W1": MOCK_W1_DATA},
            company_name="XYZ Steel Industries Ltd",
        )
        assert result["nodes_created"] > 0
        assert result["relationships_created"] > 0

        # Verify via client
        client = get_neo4j_client()
        directors = await client.get_nodes_by_label(NodeType.DIRECTOR)
        assert len(directors) == 3

        # Check auditor
        auditor = await client.get_node(NodeType.AUDITOR, "M/s. RST & Associates")
        assert auditor is not None

        # Check RPT suppliers are created
        suppliers = await client.get_nodes_by_label(NodeType.SUPPLIER)
        assert len(suppliers) == 5

    async def test_build_from_w1_directors_linked(self):
        """All 3 directors should be IS_DIRECTOR_OF the company."""
        await build_knowledge_graph(
            session_id="test-session-002",
            worker_outputs={"W1": MOCK_W1_DATA},
        )
        client = get_neo4j_client()
        rels = await client.get_relationships(rel_type=RelationshipType.IS_DIRECTOR_OF)
        assert len(rels) == 3

    async def test_build_from_w1_auditor_linked(self):
        """Auditor should be IS_AUDITOR_OF the company."""
        await build_knowledge_graph(
            session_id="test-session-003",
            worker_outputs={"W1": MOCK_W1_DATA},
        )
        client = get_neo4j_client()
        rels = await client.get_relationships(rel_type=RelationshipType.IS_AUDITOR_OF)
        assert len(rels) == 1

    async def test_build_from_w1_litigation(self):
        """Litigation creates Court + Case nodes with FILED_CASE_AGAINST."""
        await build_knowledge_graph(
            session_id="test-session-004",
            worker_outputs={"W1": MOCK_W1_DATA},
        )
        client = get_neo4j_client()
        courts = await client.get_nodes_by_label(NodeType.COURT)
        assert len(courts) == 2  # ITAT and NCLT

        cases = await client.get_nodes_by_label(NodeType.CASE)
        assert len(cases) == 2

        rels = await client.get_relationships(rel_type=RelationshipType.FILED_CASE_AGAINST)
        assert len(rels) == 2

    async def test_build_from_w2(self):
        """W2 produces Bank node with HAS_CHARGE relationship."""
        await build_knowledge_graph(
            session_id="test-session-005",
            worker_outputs={"W1": MOCK_W1_DATA, "W2": MOCK_W2_DATA},
        )
        client = get_neo4j_client()
        banks = await client.get_nodes_by_label(NodeType.BANK)
        assert len(banks) == 1
        assert banks[0]["name"] == "HDFC Bank"

        rels = await client.get_relationships(rel_type=RelationshipType.HAS_CHARGE)
        assert len(rels) == 1

    async def test_build_combined_w1_w2(self):
        """Combined build produces all expected entities."""
        result = await build_knowledge_graph(
            session_id="test-session-006",
            worker_outputs={"W1": MOCK_W1_DATA, "W2": MOCK_W2_DATA},
        )
        client = get_neo4j_client()
        stats = await client.get_stats()
        assert stats["total_nodes"] >= 12  # 1 company + 3 directors + 1 auditor + 5 suppliers + 2 courts + 2 cases + 1 bank
        assert stats["total_relationships"] >= 10

    async def test_build_empty_workers(self):
        """No workers → only the target company node."""
        result = await build_knowledge_graph(
            session_id="test-session-007",
            worker_outputs={},
            company_name="Empty Corp",
        )
        assert result["nodes_created"] == 1
        assert result["relationships_created"] == 0

    async def test_build_company_name_from_w1(self):
        """Company name derived from W1 data if not provided."""
        result = await build_knowledge_graph(
            session_id="test-session-008",
            worker_outputs={"W1": MOCK_W1_DATA},
        )
        client = get_neo4j_client()
        node = await client.get_node(NodeType.COMPANY, "XYZ Steel Industries Ltd")
        assert node is not None

    async def test_build_returns_stats(self):
        """Result includes graph stats."""
        result = await build_knowledge_graph(
            session_id="test-session-009",
            worker_outputs={"W1": MOCK_W1_DATA},
        )
        assert "stats" in result
        assert "nodes_created" in result
        assert "relationships_created" in result
        assert "entities" in result


# ══════════════════════════════════════════════
#  4. Neo4j Enricher — External Research
# ══════════════════════════════════════════════

class TestNeo4jEnricher:
    """Test external enrichment from research sources."""

    async def test_enrich_mca21_directorships(self):
        """MCA21 enrichment adds external directorships."""
        # First build internal graph
        await build_knowledge_graph(
            session_id="test-enrich-001",
            worker_outputs={"W1": MOCK_W1_DATA},
        )

        # Now enrich with mock MCA21
        result = await enrich_with_mock_mca21(
            "test-enrich-001", "XYZ Steel Industries Ltd",
        )
        assert result["nodes_added"] > 0
        assert result["relationships_added"] > 0

        # Rajesh should now be director of 3 companies
        client = get_neo4j_client()
        shared = await client.find_shared_directors()
        assert len(shared) >= 1
        rajesh_entry = [s for s in shared if s["director"] == "Rajesh Kumar"]
        assert len(rajesh_entry) == 1
        assert len(rajesh_entry[0]["companies"]) == 3

    async def test_enrich_njdg_cases(self):
        """NJDG enrichment adds undisclosed litigation."""
        await build_knowledge_graph(
            session_id="test-enrich-002",
            worker_outputs={"W1": MOCK_W1_DATA},
        )

        result = await enrich_with_mock_njdg(
            "test-enrich-002", "XYZ Steel Industries Ltd",
        )
        assert result["nodes_added"] > 0

        client = get_neo4j_client()
        cases = await client.get_nodes_by_label(NodeType.CASE)
        # 2 from W1 + 2 from NJDG = 4 total
        assert len(cases) == 4

    async def test_enrich_empty_findings(self):
        """Empty findings list → no changes."""
        result = await enrich_graph_from_research(
            "test-enrich-003", "XYZ Steel", [],
        )
        assert result["nodes_added"] == 0
        assert result["relationships_added"] == 0

    async def test_enrich_unknown_source(self):
        """Unknown source type → silently skipped."""
        result = await enrich_graph_from_research(
            "test-enrich-004", "XYZ Steel",
            [{"source": "unknown_api", "data": {"key": "val"}}],
        )
        assert result["nodes_added"] == 0

    async def test_enrich_mca21_charges(self):
        """MCA21 charges create Bank → HAS_CHARGE → Company."""
        result = await enrich_with_mock_mca21(
            "test-enrich-005", "XYZ Steel Industries Ltd",
        )
        client = get_neo4j_client()
        banks = await client.get_nodes_by_label(NodeType.BANK)
        assert any(b["name"] == "State Bank of India" for b in banks)

        rels = await client.get_relationships(
            from_label=NodeType.BANK, from_name="State Bank of India",
            rel_type=RelationshipType.HAS_CHARGE,
        )
        assert len(rels) == 1


# ══════════════════════════════════════════════
#  5. Integration — Build + Enrich + Query
# ══════════════════════════════════════════════

class TestGraphIntegration:
    """End-to-end: build internal graph, enrich, run queries."""

    async def test_full_pipeline(self):
        """Build graph from W1+W2, enrich with MCA21+NJDG, run intelligence queries."""
        # Step 1: Build internal graph
        build_result = await build_knowledge_graph(
            session_id="test-integration-001",
            worker_outputs={"W1": MOCK_W1_DATA, "W2": MOCK_W2_DATA},
        )
        assert build_result["nodes_created"] > 10

        # Step 2: Enrich with MCA21
        mca_result = await enrich_with_mock_mca21(
            "test-integration-001", "XYZ Steel Industries Ltd",
        )
        assert mca_result["nodes_added"] > 0

        # Step 3: Enrich with NJDG
        njdg_result = await enrich_with_mock_njdg(
            "test-integration-001", "XYZ Steel Industries Ltd",
        )
        assert njdg_result["nodes_added"] > 0

        # Step 4: Query — shared directors (Rajesh on XYZ + Agarwal + AK Traders)
        client = get_neo4j_client()
        shared = await client.find_shared_directors()
        assert len(shared) >= 1

        # Step 5: Multi-hop from XYZ Steel
        paths = await client.multi_hop_query(
            NodeType.COMPANY, "XYZ Steel Industries Ltd", max_hops=3,
        )
        assert len(paths) > 0

        # Step 6: Get clusters
        clusters = await client.get_community_clusters()
        assert len(clusters) >= 1

        # Step 7: Final stats
        stats = await client.get_stats()
        assert stats["total_nodes"] > 15
        assert stats["total_relationships"] > 10

    async def test_cross_directorship_detection(self):
        """
        Demo scenario: Rajesh Kumar is director of XYZ Steel (from W1),
        AND director of Agarwal Holdings and AK Traders (from MCA21).
        This 3-hop path is what the chatbot narrates.
        """
        await build_knowledge_graph(
            session_id="test-cross-dir",
            worker_outputs={"W1": MOCK_W1_DATA},
        )
        await enrich_with_mock_mca21("test-cross-dir", "XYZ Steel Industries Ltd")

        client = get_neo4j_client()

        # Multi-hop from XYZ Steel should find Agarwal Holdings
        paths = await client.multi_hop_query(
            NodeType.COMPANY, "XYZ Steel Industries Ltd", max_hops=2,
        )
        end_names = [p["end_node"].get("name") for p in paths]
        assert "Agarwal Holdings Pvt Ltd" in end_names or "AK Traders LLP" in end_names

    async def test_graph_stats_after_full_build(self):
        """Verify expected node types are all present after full build."""
        await build_knowledge_graph(
            session_id="test-stats",
            worker_outputs={"W1": MOCK_W1_DATA, "W2": MOCK_W2_DATA},
        )
        client = get_neo4j_client()
        stats = await client.get_stats()

        expected_labels = {"Company", "Director", "Auditor", "Supplier", "Bank", "Court", "Case"}
        actual_labels = set(stats["nodes_by_label"].keys())
        assert expected_labels.issubset(actual_labels), (
            f"Missing labels: {expected_labels - actual_labels}"
        )
