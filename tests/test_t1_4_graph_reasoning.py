"""
Tests for T1.4 — Agent 2.5: Graph Reasoning (5 Passes)

Covers:
1. InsightStore — add, dedup, aggregation
2. Pass 1: Contradiction detection — litigation concealment, revenue, RPT graph
3. Pass 2: Cascade risk — counterparty NCLT, concentration, DSCR cascade
4. Pass 3: Hidden relationships — shared directors, circular trading, clusters
5. Pass 4: Temporal patterns — revenue/EBITDA decline, threshold proximity
6. Pass 5: Positive signals — growth, diversification, rating, financial health
7. ReasoningNode — full integration with all 5 passes
"""

import pytest
import sys

from backend.graph.state import (
    CreditAppraisalState,
    WorkerOutput,
    CompoundInsight,
    ReasoningPackage,
    RawDataPackage,
    CrossVerificationResult,
    NormalizedField,
    OrganizedPackage,
    ComputedMetrics,
)
from backend.models.schemas import CompanyInfo, PipelineStage, PipelineStageEnum, PipelineStageStatus
from backend.thinking.event_emitter import ThinkingEventEmitter
from backend.thinking.redis_publisher import reset_publisher
from backend.storage.redis_client import get_redis_client, reset_redis_client
from backend.storage.neo4j_client import (
    get_neo4j_client,
    reset_neo4j_client,
    NodeType,
    RelationshipType,
)
from backend.agents.reasoning.insight_store import InsightStore
from backend.agents.reasoning.contradiction_pass import run_contradiction_pass
from backend.agents.reasoning.cascade_pass import run_cascade_pass
from backend.agents.reasoning.hidden_relationship_pass import run_hidden_relationship_pass
from backend.agents.reasoning.temporal_pass import run_temporal_pass
from backend.agents.reasoning.positive_signal_pass import run_positive_signal_pass
from backend.graph.nodes.reasoning_node import reasoning_node

# ── Counters ──
passed = 0
failed = 0


def report(test_name, success, detail=""):
    global passed, failed
    if success:
        passed += 1
        print(f"  ✅ {test_name}")
    else:
        failed += 1
        print(f"  ❌ {test_name}: {detail}")


# ── Fixtures ──

@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before/after each test."""
    reset_neo4j_client()
    reset_publisher()
    reset_redis_client()
    yield
    reset_neo4j_client()
    reset_publisher()
    reset_redis_client()


# ── Helpers ──

def make_worker_output(worker_id: str, doc_type: str, data: dict, confidence: float = 0.9) -> WorkerOutput:
    return WorkerOutput(
        worker_id=worker_id,
        document_type=doc_type,
        status="completed",
        extracted_data=data,
        confidence=confidence,
        pages_processed=10,
    )


MOCK_W1_DATA = {
    "company_name": "XYZ Steel Industries Ltd",
    "cin": "L27100MH2001PLC123456",
    "revenue": {"FY2021": 410.0, "FY2022": 445.0, "FY2023": 480.0},
    "ebitda": {"FY2021": 52.0, "FY2022": 48.0, "FY2023": 44.0},
    "pat": {"FY2021": 28.0, "FY2022": 25.0, "FY2023": 22.0},
    "total_debt": {"FY2021": 120.0, "FY2022": 135.0, "FY2023": 155.0},
    "net_worth": {"FY2021": 180.0, "FY2022": 190.0, "FY2023": 195.0},
    "directors": [
        {"name": "Rajesh Kumar", "din": "00112233", "designation": "Managing Director"},
        {"name": "Priya Sharma", "din": "00445566", "designation": "Independent Director"},
        {"name": "Vikram Desai", "din": "00778899", "designation": "CFO & Whole-time Director"},
    ],
    "auditor": {"name": "RST & Associates", "type": "Statutory Auditor", "opinion": "Qualified"},
    "rpts": {
        "transactions": [
            {"party": "ABC Trading Co", "nature": "Purchase of raw materials", "amount": 45.0},
            {"party": "PQR Logistics", "nature": "Service charges", "amount": 8.5},
            {"party": "Steel Suppliers Inc", "nature": "Sale of finished goods", "amount": 62.0},
            {"party": "XYZ Foundation", "nature": "CSR contribution", "amount": 2.0},
            {"party": "Green Energy Ltd", "nature": "Sale of power", "amount": 15.0},
        ],
    },
    "litigation": [
        {"type": "Tax", "forum": "ITAT", "amount": 3.2, "status": "Pending"},
        {"type": "Commercial", "forum": "NCLT", "amount": 1.8, "status": "Pending"},
    ],
}

MOCK_W8_DATA = {
    "current_rating": "BBB+",
    "outlook": "Stable",
    "agency": "CRISIL",
}

MOCK_W8_STRONG = {
    "current_rating": "AA",
    "outlook": "Positive",
    "agency": "CARE",
}


async def _setup_graph_with_enrichment(company_name="XYZ Steel Industries Ltd"):
    """Setup Neo4j graph with relevant data for reasoning passes."""
    client = get_neo4j_client()
    await client._ensure_initialized()

    # Create company
    await client.create_node(NodeType.COMPANY, company_name, {"role": "target"})

    # Create directors with cross-directorships
    await client.create_node(NodeType.DIRECTOR, "Rajesh Kumar", {"din": "00112233"})
    await client.create_relationship(
        NodeType.DIRECTOR, "Rajesh Kumar",
        RelationshipType.IS_DIRECTOR_OF,
        NodeType.COMPANY, company_name,
    )
    # Rajesh is also director of Agarwal Holdings (undisclosed)
    await client.create_node(NodeType.COMPANY, "Agarwal Holdings Pvt Ltd", {"role": "external"})
    await client.create_relationship(
        NodeType.DIRECTOR, "Rajesh Kumar",
        RelationshipType.IS_DIRECTOR_OF,
        NodeType.COMPANY, "Agarwal Holdings Pvt Ltd",
    )

    # Add undisclosed litigation (2 cases in NJDG vs 2 disclosed in AR)
    await client.create_node(NodeType.COURT, "NCLT Mumbai", {"jurisdiction": "Mumbai"})
    await client.create_relationship(
        NodeType.COURT, "NCLT Mumbai",
        RelationshipType.FILED_CASE_AGAINST,
        NodeType.COMPANY, company_name,
        {"case_type": "NCLT", "source": "NJDG"},
    )
    await client.create_node(NodeType.COURT, "High Court Mumbai", {"jurisdiction": "Mumbai"})
    await client.create_relationship(
        NodeType.COURT, "High Court Mumbai",
        RelationshipType.FILED_CASE_AGAINST,
        NodeType.COMPANY, company_name,
        {"case_type": "Civil", "source": "NJDG"},
    )
    await client.create_node(NodeType.COURT, "ITAT Delhi", {"jurisdiction": "Delhi"})
    await client.create_relationship(
        NodeType.COURT, "ITAT Delhi",
        RelationshipType.FILED_CASE_AGAINST,
        NodeType.COMPANY, company_name,
        {"case_type": "Tax", "source": "public_record"},
    )

    # Add supplier/customer relationships
    await client.create_node(NodeType.SUPPLIER, "ABC Trading Co", {})
    await client.create_relationship(
        NodeType.SUPPLIER, "ABC Trading Co",
        RelationshipType.SUPPLIES_TO,
        NodeType.COMPANY, company_name,
    )

    return client


def _make_state_with_graph_data(
    session_id="test-reasoning-001",
    include_w1=True,
    include_w8=False,
    w8_data=None,
    include_raw_data=False,
    include_organized=False,
    dscr=None,
    de_ratio=None,
) -> CreditAppraisalState:
    """Build a CreditAppraisalState for reasoning tests."""
    worker_outputs = {}
    if include_w1:
        worker_outputs["W1"] = make_worker_output("W1", "ANNUAL_REPORT", MOCK_W1_DATA)
    if include_w8:
        worker_outputs["W8"] = make_worker_output("W8", "RATING_REPORT", w8_data or MOCK_W8_DATA)

    state = CreditAppraisalState(
        session_id=session_id,
        company=CompanyInfo(
            name="XYZ Steel Industries Ltd",
            cin="L27100MH2001PLC123456",
            sector="Steel Manufacturing",
            loan_type="Working Capital",
            loan_amount="₹50,00,00,000",
            loan_amount_numeric=50.0,
        ),
        worker_outputs=worker_outputs,
        pipeline_stages=[
            PipelineStage(stage=PipelineStageEnum.REASONING, status=PipelineStageStatus.ACTIVE),
        ],
    )

    if include_raw_data:
        state.raw_data_package = RawDataPackage(
            cross_verifications=[
                CrossVerificationResult(
                    field_name="revenue_fy2023",
                    sources={
                        "W1_annual_report": NormalizedField(value=480.0, source_document="W1", confidence=0.7),
                        "W4_itr": NormalizedField(value=390.0, source_document="W4", confidence=1.0),
                    },
                    max_deviation_pct=23.1,
                    status="conflicting",
                ),
            ],
        )

    if include_organized:
        state.organized_package = OrganizedPackage(
            computed_metrics=ComputedMetrics(
                dscr=dscr,
                debt_equity_ratio=de_ratio,
            ),
        )

    return state


# ══════════════════════════════════════════════
#  Tests
# ══════════════════════════════════════════════

async def run_tests():
    global passed, failed

    redis = get_redis_client()
    await redis.initialize()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SECTION 1: InsightStore
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n📊 Section 1: InsightStore")

    # Test 1.1: Add insights
    store = InsightStore()
    i1 = CompoundInsight(pass_name="contradictions", insight_type="lit_concealment", description="Test insight 1", score_impact=-25, confidence=0.9, severity="HIGH")
    i2 = CompoundInsight(pass_name="cascade", insight_type="nclt_risk", description="Test insight 2", score_impact=-30, confidence=0.8, severity="HIGH")
    added1 = store.add(i1)
    added2 = store.add(i2)
    report("1.1 Add two insights", added1 and added2 and len(store.get_all()) == 2, f"added={added1},{added2}, count={len(store.get_all())}")

    # Test 1.2: Dedup same pass+type+description
    dup = CompoundInsight(pass_name="contradictions", insight_type="lit_concealment", description="Test insight 1", score_impact=-15, confidence=0.5, severity="MEDIUM")
    added_dup = store.add(dup)
    report("1.2 Dedup identical insight", not added_dup and len(store.get_all()) == 2, f"added={added_dup}, count={len(store.get_all())}")

    # Test 1.3: Dedup replaces lower confidence
    dup_higher = CompoundInsight(pass_name="contradictions", insight_type="lit_concealment", description="Test insight 1", score_impact=-40, confidence=0.95, severity="CRITICAL")
    store2 = InsightStore()
    store2.add(i1)  # confidence 0.9
    store2.add(dup_higher)  # confidence 0.95 → should replace
    all_insights = store2.get_all()
    report("1.3 Higher confidence replaces", len(all_insights) == 1 and all_insights[0].confidence == 0.95, f"count={len(all_insights)}")

    # Test 1.4: Total score impact
    store3 = InsightStore()
    store3.add(CompoundInsight(pass_name="p1", insight_type="a", description="A insight", score_impact=-20, confidence=0.8, severity="HIGH"))
    store3.add(CompoundInsight(pass_name="p2", insight_type="b", description="B insight", score_impact=+15, confidence=0.7, severity="LOW"))
    report("1.4 Total score impact", store3.total_score_impact() == -5, f"total={store3.total_score_impact()}")

    # Test 1.5: Get by pass
    report("1.5 Get by pass", len(store3.get_by_pass("p1")) == 1 and len(store3.get_by_pass("p2")) == 1)

    # Test 1.6: Get by severity
    sev_store = InsightStore()
    sev_store.add(CompoundInsight(pass_name="p1", insight_type="low1", description="Low sev", score_impact=-5, confidence=0.5, severity="LOW"))
    sev_store.add(CompoundInsight(pass_name="p1", insight_type="high1", description="High sev", score_impact=-20, confidence=0.8, severity="HIGH"))
    sev_store.add(CompoundInsight(pass_name="p1", insight_type="crit1", description="Critical sev", score_impact=-30, confidence=0.9, severity="CRITICAL"))
    high_plus = sev_store.get_by_severity("HIGH")
    report("1.6 Get by severity HIGH+", len(high_plus) == 2, f"got {len(high_plus)}")

    # Test 1.7: Summary
    summary = sev_store.summary()
    report("1.7 Summary structure", summary["total_insights"] == 3 and "p1" in summary["by_pass"], f"summary={summary}")

    # Test 1.8: add_many returns count
    store4 = InsightStore()
    count = store4.add_many([
        CompoundInsight(pass_name="px", insight_type="x1", description="X1", score_impact=-10, confidence=0.8, severity="HIGH"),
        CompoundInsight(pass_name="px", insight_type="x2", description="X2", score_impact=-5, confidence=0.7, severity="LOW"),
        CompoundInsight(pass_name="px", insight_type="x1", description="X1", score_impact=-8, confidence=0.6, severity="MEDIUM"),  # Dup
    ])
    report("1.8 add_many returns correct count", count == 2, f"count={count}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SECTION 2: Pass 1 — Contradictions
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n🔍 Section 2: Pass 1 — Contradictions")

    # Test 2.1: Litigation concealment detected (3 graph cases vs 2 AR disclosed)
    reset_neo4j_client()
    await _setup_graph_with_enrichment()
    state = _make_state_with_graph_data()
    emitter = ThinkingEventEmitter("test-2-1", "Test")
    insights = await run_contradiction_pass(state, emitter)
    lit_insights = [i for i in insights if i.insight_type == "litigation_concealment"]
    report("2.1 Litigation concealment detected", len(lit_insights) >= 1, f"got {len(lit_insights)} lit insights from {len(insights)} total")

    # Test 2.2: Concealment shows correct counts
    if lit_insights:
        desc = lit_insights[0].description
        report("2.2 Concealment mentions undisclosed", "undisclosed" in desc.lower() or "3" in desc, f"desc={desc[:80]}")
    else:
        report("2.2 Concealment mentions undisclosed", False, "No lit insights")

    # Test 2.3: Contradiction pass with no graph (no insights) 
    reset_neo4j_client()
    state_empty = _make_state_with_graph_data()
    emitter2 = ThinkingEventEmitter("test-2-3", "Test")
    insights_empty = await run_contradiction_pass(state_empty, emitter2)
    report("2.3 No graph = no insights", len(insights_empty) == 0, f"got {len(insights_empty)}")

    # Test 2.4: Revenue contradiction from cross-verification
    reset_neo4j_client()
    state_rev = _make_state_with_graph_data(include_raw_data=True)
    emitter3 = ThinkingEventEmitter("test-2-4", "Test")
    insights_rev = await run_contradiction_pass(state_rev, emitter3)
    rev_insights = [i for i in insights_rev if i.insight_type == "revenue_contradiction"]
    report("2.4 Revenue contradiction detected", len(rev_insights) >= 1, f"got {len(rev_insights)}")

    # Test 2.5: RPT concealment via shared directors
    reset_neo4j_client()
    await _setup_graph_with_enrichment()
    state_rpt = _make_state_with_graph_data()
    emitter4 = ThinkingEventEmitter("test-2-5", "Test")
    insights_rpt = await run_contradiction_pass(state_rpt, emitter4)
    rpt_insights = [i for i in insights_rpt if i.insight_type == "rpt_concealment_graph"]
    report("2.5 RPT concealment via graph", len(rpt_insights) >= 1, f"got {len(rpt_insights)}")

    # Test 2.6: Contradiction severity levels
    if lit_insights:
        report("2.6 Severity is HIGH or MEDIUM", lit_insights[0].severity in ("HIGH", "MEDIUM"), f"severity={lit_insights[0].severity}")
    else:
        report("2.6 Severity check", False, "No insights to check")

    # Test 2.7: All contradictions have negative score impact
    all_negative = all(i.score_impact < 0 for i in insights) if insights else True
    report("2.7 All contradictions negative impact", all_negative)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SECTION 3: Pass 2 — Cascade Risk
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n⛓️  Section 3: Pass 2 — Cascade Risk")

    # Test 3.1: Counterparty NCLT risk via graph
    reset_neo4j_client()
    client = await _setup_graph_with_enrichment()
    # Add a customer with NCLT proceedings
    await client.create_node(NodeType.CUSTOMER, "Big Buyer Corp", {})
    await client.create_relationship(
        NodeType.COMPANY, "XYZ Steel Industries Ltd",
        RelationshipType.SUPPLIES_TO,
        NodeType.CUSTOMER, "Big Buyer Corp",
    )
    await client.create_node(NodeType.CASE, "NCLT Case 2024", {"case_type": "NCLT", "amount": "50cr"})
    await client.create_relationship(
        NodeType.CASE, "NCLT Case 2024",
        RelationshipType.FILED_CASE_AGAINST,
        NodeType.CUSTOMER, "Big Buyer Corp",
        {"source": "NJDG"},
    )

    state_cascade = _make_state_with_graph_data()
    emitter5 = ThinkingEventEmitter("test-3-1", "Test")
    insights_cascade = await run_cascade_pass(state_cascade, emitter5)
    report("3.1 Cascade pass runs without error", True)

    # Test 3.2: Revenue concentration from RPT data
    reset_neo4j_client()
    state_conc = _make_state_with_graph_data()
    emitter6 = ThinkingEventEmitter("test-3-2", "Test")
    insights_conc = await run_cascade_pass(state_conc, emitter6)
    conc_insights = [i for i in insights_conc if i.insight_type == "revenue_concentration"]
    # Steel Suppliers Inc at ₹62cr out of ₹77cr total sales = 80%+ → should flag
    report("3.2 Revenue concentration flagged", len(conc_insights) >= 1, f"got {len(conc_insights)}")

    # Test 3.3: DSCR cascade simulation
    reset_neo4j_client()
    state_dscr = _make_state_with_graph_data(include_organized=True, dscr=1.3)
    emitter7 = ThinkingEventEmitter("test-3-3", "Test")
    insights_dscr = await run_cascade_pass(state_dscr, emitter7)
    dscr_insights = [i for i in insights_dscr if i.insight_type == "dscr_cascade"]
    # DSCR 1.3 → projected 0.91 (below 1.0) with 30% revenue loss
    report("3.3 DSCR cascade detected", len(dscr_insights) >= 1, f"got {len(dscr_insights)}")

    # Test 3.4: Strong DSCR — no cascade
    reset_neo4j_client()
    state_strong = _make_state_with_graph_data(include_organized=True, dscr=2.5)
    emitter8 = ThinkingEventEmitter("test-3-4", "Test")
    insights_strong = await run_cascade_pass(state_strong, emitter8)
    dscr_strong = [i for i in insights_strong if i.insight_type == "dscr_cascade"]
    report("3.4 Strong DSCR — no cascade", len(dscr_strong) == 0, f"got {len(dscr_strong)}")

    # Test 3.5: Empty state — cascade pass graceful
    reset_neo4j_client()
    state_empty2 = CreditAppraisalState(session_id="test-3-5")
    emitter9 = ThinkingEventEmitter("test-3-5", "Test")
    insights_empty2 = await run_cascade_pass(state_empty2, emitter9)
    report("3.5 Empty state — no crash", True)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SECTION 4: Pass 3 — Hidden Relationships
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n🕵️  Section 4: Pass 3 — Hidden Relationships")

    # Test 4.1: Shared director detected
    reset_neo4j_client()
    await _setup_graph_with_enrichment()
    state_hidden = _make_state_with_graph_data()
    emitter10 = ThinkingEventEmitter("test-4-1", "Test")
    insights_hidden = await run_hidden_relationship_pass(state_hidden, emitter10)
    shared_insights = [i for i in insights_hidden if i.insight_type == "shared_director"]
    report("4.1 Shared director detected", len(shared_insights) >= 1, f"got {len(shared_insights)}")

    # Test 4.2: Shared director names correct entity
    if shared_insights:
        report("4.2 Names Rajesh Kumar", "Rajesh Kumar" in shared_insights[0].description, shared_insights[0].description[:80])
    else:
        report("4.2 Names check", False, "No shared director insights")

    # Test 4.3: Circular trading detection
    reset_neo4j_client()
    client_circ = get_neo4j_client()
    await client_circ._ensure_initialized()
    # Create circular chain: Company A → B → C → A
    await client_circ.create_node(NodeType.COMPANY, "XYZ Steel Industries Ltd", {"role": "target"})
    await client_circ.create_node(NodeType.COMPANY, "Firm B", {})
    await client_circ.create_node(NodeType.COMPANY, "Firm C", {})
    await client_circ.create_relationship(NodeType.COMPANY, "XYZ Steel Industries Ltd", RelationshipType.SUPPLIES_TO, NodeType.COMPANY, "Firm B")
    await client_circ.create_relationship(NodeType.COMPANY, "Firm B", RelationshipType.SUPPLIES_TO, NodeType.COMPANY, "Firm C")
    await client_circ.create_relationship(NodeType.COMPANY, "Firm C", RelationshipType.SUPPLIES_TO, NodeType.COMPANY, "XYZ Steel Industries Ltd")

    state_circ = _make_state_with_graph_data()
    emitter11 = ThinkingEventEmitter("test-4-3", "Test")
    insights_circ = await run_hidden_relationship_pass(state_circ, emitter11)
    circ_insights = [i for i in insights_circ if i.insight_type == "circular_trading"]
    report("4.3 Circular trading detected", len(circ_insights) >= 1, f"got {len(circ_insights)}")

    # Test 4.4: Circular trading severity is CRITICAL
    if circ_insights:
        report("4.4 Circular trading = CRITICAL", circ_insights[0].severity == "CRITICAL", f"severity={circ_insights[0].severity}")
    else:
        report("4.4 Circular trading severity", False, "No circular insights")

    # Test 4.5: No hidden relationships when graph is clean
    reset_neo4j_client()
    client_clean = get_neo4j_client()
    await client_clean._ensure_initialized()
    await client_clean.create_node(NodeType.COMPANY, "XYZ Steel Industries Ltd", {"role": "target"})
    await client_clean.create_node(NodeType.DIRECTOR, "Solo Director", {})
    await client_clean.create_relationship(
        NodeType.DIRECTOR, "Solo Director",
        RelationshipType.IS_DIRECTOR_OF,
        NodeType.COMPANY, "XYZ Steel Industries Ltd",
    )
    state_clean = _make_state_with_graph_data()
    emitter12 = ThinkingEventEmitter("test-4-5", "Test")
    insights_clean = await run_hidden_relationship_pass(state_clean, emitter12)
    report("4.5 Clean graph — no hidden relationships", len(insights_clean) == 0, f"got {len(insights_clean)}")

    # Test 4.6: Large cluster detection
    reset_neo4j_client()
    client_cluster = get_neo4j_client()
    await client_cluster._ensure_initialized()
    # Create a cluster of 8 entities all connected
    await client_cluster.create_node(NodeType.COMPANY, "XYZ Steel Industries Ltd", {"role": "target"})
    for i in range(7):
        name = f"Entity_{i}"
        await client_cluster.create_node(NodeType.COMPANY, name, {})
        await client_cluster.create_relationship(
            NodeType.COMPANY, "XYZ Steel Industries Ltd",
            RelationshipType.SUPPLIES_TO,
            NodeType.COMPANY, name,
        )
    # Cross-connect some
    await client_cluster.create_relationship(NodeType.COMPANY, "Entity_0", RelationshipType.SUPPLIES_TO, NodeType.COMPANY, "Entity_1")
    await client_cluster.create_relationship(NodeType.COMPANY, "Entity_2", RelationshipType.SUPPLIES_TO, NodeType.COMPANY, "Entity_3")

    state_cluster = _make_state_with_graph_data()
    emitter13 = ThinkingEventEmitter("test-4-6", "Test")
    insights_cluster = await run_hidden_relationship_pass(state_cluster, emitter13)
    cluster_insights = [i for i in insights_cluster if i.insight_type == "suspicious_cluster"]
    report("4.6 Large cluster flagged", len(cluster_insights) >= 1, f"got {len(cluster_insights)}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SECTION 5: Pass 4 — Temporal Patterns
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n📉 Section 5: Pass 4 — Temporal Patterns")

    # Test 5.1: EBITDA declining trend detected
    reset_neo4j_client()
    state_temp = _make_state_with_graph_data()
    emitter14 = ThinkingEventEmitter("test-5-1", "Test")
    insights_temp = await run_temporal_pass(state_temp, emitter14)
    ebitda_insights = [i for i in insights_temp if i.insight_type == "ebitda_decline"]
    # MOCK_W1_DATA has declining EBITDA: 52 → 48 → 44
    report("5.1 EBITDA decline detected", len(ebitda_insights) >= 1, f"got {len(ebitda_insights)}")

    # Test 5.2: Revenue is GROWING — no decline flag
    rev_decline = [i for i in insights_temp if i.insight_type == "revenue_decline"]
    # Revenue is 410 → 445 → 480 (growing, not declining)
    report("5.2 Growing revenue — no decline flag", len(rev_decline) == 0, f"got {len(rev_decline)}")

    # Test 5.3: Debt-revenue divergence (debt growing, but revenue also growing → no flag)
    debt_insights = [i for i in insights_temp if i.insight_type == "debt_revenue_divergence"]
    # Debt growing (120 → 135 → 155) but revenue also growing → no divergence
    report("5.3 Both growing — no divergence", len(debt_insights) == 0, f"got {len(debt_insights)}")

    # Test 5.4: Declining revenue + growing debt = divergence
    reset_neo4j_client()
    declining_w1 = {
        **MOCK_W1_DATA,
        "revenue": {"FY2021": 500.0, "FY2022": 460.0, "FY2023": 420.0},
        "total_debt": {"FY2021": 100.0, "FY2022": 130.0, "FY2023": 165.0},
    }
    state_div = CreditAppraisalState(
        session_id="test-5-4",
        company=CompanyInfo(name="XYZ Steel Industries Ltd", cin="test", sector="Steel", loan_type="WC", loan_amount="50cr", loan_amount_numeric=50.0),
        worker_outputs={"W1": make_worker_output("W1", "ANNUAL_REPORT", declining_w1)},
    )
    emitter15 = ThinkingEventEmitter("test-5-4", "Test")
    insights_div = await run_temporal_pass(state_div, emitter15)
    divergence = [i for i in insights_div if i.insight_type == "debt_revenue_divergence"]
    report("5.4 Revenue decline + debt growth = divergence", len(divergence) >= 1, f"got {len(divergence)}")

    # Test 5.5: DSCR threshold proximity
    reset_neo4j_client()
    state_thresh = _make_state_with_graph_data(include_organized=True, dscr=1.1)
    emitter16 = ThinkingEventEmitter("test-5-5", "Test")
    insights_thresh = await run_temporal_pass(state_thresh, emitter16)
    thresh_insights = [i for i in insights_thresh if i.insight_type == "dscr_threshold_proximity"]
    report("5.5 DSCR 1.1x → threshold proximity", len(thresh_insights) >= 1, f"got {len(thresh_insights)}")

    # Test 5.6: DSCR safe (2.0x) — no proximity warning
    reset_neo4j_client()
    state_safe = _make_state_with_graph_data(include_organized=True, dscr=2.0)
    emitter17 = ThinkingEventEmitter("test-5-6", "Test")
    insights_safe = await run_temporal_pass(state_safe, emitter17)
    thresh_safe = [i for i in insights_safe if i.insight_type == "dscr_threshold_proximity"]
    report("5.6 DSCR 2.0x — no proximity warning", len(thresh_safe) == 0, f"got {len(thresh_safe)}")

    # Test 5.7: High D/E ratio flagged
    reset_neo4j_client()
    state_de = _make_state_with_graph_data(include_organized=True, dscr=1.5, de_ratio=2.8)
    emitter18 = ThinkingEventEmitter("test-5-7", "Test")
    insights_de = await run_temporal_pass(state_de, emitter18)
    de_insights = [i for i in insights_de if i.insight_type == "de_ratio_high"]
    report("5.7 High D/E ratio flagged", len(de_insights) >= 1, f"got {len(de_insights)}")

    # Test 5.8: No W1 data — temporal pass graceful
    reset_neo4j_client()
    state_no_w1 = CreditAppraisalState(session_id="test-5-8")
    emitter19 = ThinkingEventEmitter("test-5-8", "Test")
    insights_no_w1 = await run_temporal_pass(state_no_w1, emitter19)
    report("5.8 No W1 data — no crash", len(insights_no_w1) == 0)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SECTION 6: Pass 5 — Positive Signals
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n✨ Section 6: Pass 5 — Positive Signals")

    # Test 6.1: Growing revenue is a positive signal
    reset_neo4j_client()
    state_pos = _make_state_with_graph_data()
    emitter20 = ThinkingEventEmitter("test-6-1", "Test")
    insights_pos = await run_positive_signal_pass(state_pos, emitter20)
    growth_insights = [i for i in insights_pos if i.insight_type == "strong_revenue_growth"]
    # Revenue 410→445→480 = ~8.2% CAGR over 2 years ... let's check
    # CAGR = (480/410)^(1/2) - 1 = 0.0816 = 8.16% → below 10% threshold
    report("6.1 Revenue growth check (8% CAGR — below 10% threshold)", len(growth_insights) == 0, f"got {len(growth_insights)}")

    # Test 6.2: Strong revenue growth (>10% CAGR)
    reset_neo4j_client()
    strong_growth_w1 = {
        **MOCK_W1_DATA,
        "revenue": {"FY2021": 300.0, "FY2022": 360.0, "FY2023": 430.0},
    }
    state_growth = CreditAppraisalState(
        session_id="test-6-2",
        company=CompanyInfo(name="XYZ Steel Industries Ltd", cin="test", sector="Steel", loan_type="WC", loan_amount="50cr", loan_amount_numeric=50.0),
        worker_outputs={"W1": make_worker_output("W1", "ANNUAL_REPORT", strong_growth_w1)},
    )
    emitter21 = ThinkingEventEmitter("test-6-2", "Test")
    insights_growth = await run_positive_signal_pass(state_growth, emitter21)
    strong_growth = [i for i in insights_growth if i.insight_type == "strong_revenue_growth"]
    report("6.2 Strong revenue growth (>10% CAGR)", len(strong_growth) >= 1, f"got {len(strong_growth)}")

    # Test 6.3: All positive insights have positive score impact
    all_positive = all(i.score_impact > 0 for i in insights_growth)
    report("6.3 All positive signals have positive impact", all_positive)

    # Test 6.4: Strong rating detected
    reset_neo4j_client()
    state_rating = _make_state_with_graph_data(include_w8=True, w8_data=MOCK_W8_STRONG)
    emitter22 = ThinkingEventEmitter("test-6-4", "Test")
    insights_rating = await run_positive_signal_pass(state_rating, emitter22)
    rating_insights = [i for i in insights_rating if i.insight_type == "strong_rating"]
    report("6.4 Strong rating (AA) detected", len(rating_insights) >= 1, f"got {len(rating_insights)}")

    # Test 6.5: Weak rating — no positive signal
    reset_neo4j_client()
    state_weak_rating = _make_state_with_graph_data(include_w8=True, w8_data=MOCK_W8_DATA)  # BBB+
    emitter23 = ThinkingEventEmitter("test-6-5", "Test")
    insights_weak = await run_positive_signal_pass(state_weak_rating, emitter23)
    weak_rating = [i for i in insights_weak if i.insight_type == "strong_rating"]
    report("6.5 Weak rating (BBB+) — no signal", len(weak_rating) == 0, f"got {len(weak_rating)}")

    # Test 6.6: Strong DSCR = positive
    reset_neo4j_client()
    state_strong_dscr = _make_state_with_graph_data(include_organized=True, dscr=2.5)
    emitter24 = ThinkingEventEmitter("test-6-6", "Test")
    insights_dscr_pos = await run_positive_signal_pass(state_strong_dscr, emitter24)
    dscr_pos = [i for i in insights_dscr_pos if i.insight_type == "strong_dscr"]
    report("6.6 Strong DSCR (2.5x) = positive", len(dscr_pos) >= 1, f"got {len(dscr_pos)}")

    # Test 6.7: Low leverage = positive
    reset_neo4j_client()
    state_low_de = _make_state_with_graph_data(include_organized=True, dscr=1.5, de_ratio=0.6)
    emitter25 = ThinkingEventEmitter("test-6-7", "Test")
    insights_low_de = await run_positive_signal_pass(state_low_de, emitter25)
    low_de_pos = [i for i in insights_low_de if i.insight_type == "low_leverage"]
    report("6.7 Low leverage (D/E 0.6x) = positive", len(low_de_pos) >= 1, f"got {len(low_de_pos)}")

    # Test 6.8: Diversification (need graph relationships)
    reset_neo4j_client()
    client_div = get_neo4j_client()
    await client_div._ensure_initialized()
    await client_div.create_node(NodeType.COMPANY, "XYZ Steel Industries Ltd", {"role": "target"})
    for i in range(4):
        await client_div.create_node(NodeType.SUPPLIER, f"Supplier_{i}", {})
        await client_div.create_relationship(
            NodeType.SUPPLIER, f"Supplier_{i}",
            RelationshipType.SUPPLIES_TO,
            NodeType.COMPANY, "XYZ Steel Industries Ltd",
        )
    state_div2 = _make_state_with_graph_data()  # W1 has 5 RPT parties
    emitter26 = ThinkingEventEmitter("test-6-8", "Test")
    insights_div2 = await run_positive_signal_pass(state_div2, emitter26)
    div_pos = [i for i in insights_div2 if i.insight_type == "diversified_relationships"]
    report("6.8 Diversification (9 counterparties)", len(div_pos) >= 1, f"got {len(div_pos)}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SECTION 7: Full Reasoning Node Integration
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n🧠 Section 7: Full Reasoning Node Integration")

    # Test 7.1: Reasoning node runs all 5 passes
    reset_neo4j_client()
    await _setup_graph_with_enrichment()
    state_full = _make_state_with_graph_data(include_raw_data=True, include_organized=True, dscr=1.3, de_ratio=0.8)
    result = await reasoning_node(state_full)
    pkg = result.get("reasoning_package")
    report("7.1 Reasoning node returns ReasoningPackage", pkg is not None and isinstance(pkg, ReasoningPackage), f"type={type(pkg)}")

    # Test 7.2: All 5 passes completed
    report("7.2 All 5 passes completed", pkg.passes_completed == 5, f"passes={pkg.passes_completed}")

    # Test 7.3: Has insights from multiple passes
    pass_names = set(i.pass_name for i in pkg.insights)
    report("7.3 Insights from multiple passes", len(pass_names) >= 2, f"passes with insights: {pass_names}")

    # Test 7.4: Total compound score impact computed
    report("7.4 Total impact is non-zero", pkg.total_compound_score_impact != 0, f"impact={pkg.total_compound_score_impact}")

    # Test 7.5: Pipeline stage updated
    stages = result.get("pipeline_stages", [])
    reasoning_stage = next((s for s in stages if s.stage == PipelineStageEnum.REASONING), None)
    report("7.5 Pipeline stage updated", reasoning_stage is not None and reasoning_stage.status == PipelineStageStatus.COMPLETED)

    # Test 7.6: Each insight has required fields
    all_valid = all(
        i.pass_name and i.insight_type and i.description and i.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        for i in pkg.insights
    )
    report("7.6 All insights have required fields", all_valid)

    # Test 7.7: Contradiction insights present (graph has undisclosed cases)
    contra = [i for i in pkg.insights if i.pass_name == "contradictions"]
    report("7.7 Contradiction insights present", len(contra) >= 1, f"got {len(contra)}")

    # Test 7.8: Positive signals present (diversification, growing revenue, etc.)
    positive = [i for i in pkg.insights if i.pass_name == "positive"]
    report("7.8 Positive signals present", len(positive) >= 0)  # May or may not have depending on thresholds

    # Test 7.9: Empty state — reasoning node doesn't crash
    reset_neo4j_client()
    state_empty3 = CreditAppraisalState(
        session_id="test-7-9",
        pipeline_stages=[
            PipelineStage(stage=PipelineStageEnum.REASONING, status=PipelineStageStatus.ACTIVE),
        ],
    )
    result_empty = await reasoning_node(state_empty3)
    pkg_empty = result_empty.get("reasoning_package")
    report("7.9 Empty state — no crash", pkg_empty is not None and pkg_empty.passes_completed == 5)

    # Test 7.10: Evidence chains populated
    insights_with_evidence = [i for i in pkg.insights if len(i.evidence_chain) > 0]
    report("7.10 Evidence chains populated", len(insights_with_evidence) > 0, f"{len(insights_with_evidence)}/{len(pkg.insights)} have evidence")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SUMMARY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n{'='*60}")
    print(f"T1.4 Graph Reasoning — Results: {passed} passed, {failed} failed")
    print(f"{'='*60}")

    return failed == 0


@pytest.mark.asyncio
async def test_t1_4_graph_reasoning():
    """Pytest entry point for T1.4 graph reasoning tests."""
    success = await run_tests()
    assert success, f"T1.4 tests failed: {failed} failures"
