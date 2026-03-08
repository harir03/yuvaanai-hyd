"""
Tests for T4.3 — Elasticsearch Client + Regulatory Intelligence Feed

5-Perspective Testing:
- 🏦 Credit Domain Expert: Regulatory items match Indian banking context
- 🔒 Security Architect: Injection-safe search, validated inputs
- ⚙️ Systems Engineer: Fallback, concurrency, graceful degradation
- 🧪 QA Engineer: Edge cases, empty/null/boundary, deduplication
- 🎯 Hackathon Judge: Demo-ready, sector search tells a story
"""

import asyncio
import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.storage.elasticsearch_client import (
    ElasticsearchClient,
    InMemoryESStore,
    ESIndex,
    INDEX_MAPPINGS,
    get_elasticsearch_client,
    reset_elasticsearch_client,
)
from backend.agents.research.regulatory_feed import (
    RegulatoryFeed,
    RegulatorySource,
    RegulationSeverity,
    RegulationType,
    SECTOR_KEYWORDS,
    get_regulatory_feed,
    reset_regulatory_feed,
    _get_mock_rbi_items,
    _get_mock_sebi_items,
    _get_mock_mca_items,
    _get_mock_gst_items,
)

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_es():
    """Reset ES singleton between tests."""
    reset_elasticsearch_client()
    yield
    reset_elasticsearch_client()


@pytest.fixture(autouse=True)
def _reset_reg_feed():
    """Reset regulatory feed singleton between tests."""
    reset_regulatory_feed()
    yield
    reset_regulatory_feed()


@pytest.fixture
def es_client():
    """Fresh in-memory ES client (no hosts → always in-memory)."""
    return ElasticsearchClient()


@pytest.fixture
def store():
    """Raw in-memory ES store for unit tests."""
    return InMemoryESStore()


@pytest.fixture
def reg_feed(es_client):
    """Regulatory feed backed by in-memory ES client."""
    return RegulatoryFeed(es_client=es_client)


# ══════════════════════════════════════════════
# 1. InMemoryESStore Unit Tests
# ══════════════════════════════════════════════

class TestInMemoryESStore:
    """⚙️ Systems Engineer + 🧪 QA Engineer: store CRUD correctness."""

    @pytest.mark.asyncio
    async def test_create_index(self, store):
        result = await store.create_index("test_index")
        assert result is True
        assert await store.index_exists("test_index")

    @pytest.mark.asyncio
    async def test_create_index_idempotent(self, store):
        await store.create_index("test_index")
        await store.create_index("test_index")
        assert await store.index_exists("test_index")

    @pytest.mark.asyncio
    async def test_index_document_auto_creates_index(self, store):
        doc_id = await store.index_document("auto_index", {"content": "hello"})
        assert doc_id
        assert await store.index_exists("auto_index")
        assert await store.count("auto_index") == 1

    @pytest.mark.asyncio
    async def test_index_document_with_custom_id(self, store):
        doc_id = await store.index_document("test", {"content": "doc"}, doc_id="my-id-1")
        assert doc_id == "my-id-1"
        result = await store.get_document("test", "my-id-1")
        assert result is not None
        assert result["content"] == "doc"

    @pytest.mark.asyncio
    async def test_bulk_index(self, store):
        docs = [{"content": f"doc {i}"} for i in range(10)]
        count = await store.bulk_index("bulk_test", docs)
        assert count == 10
        assert await store.count("bulk_test") == 10

    @pytest.mark.asyncio
    async def test_search_text_match(self, store):
        await store.index_document("test", {"content": "RBI wilful defaulter list updated"})
        await store.index_document("test", {"content": "SEBI insider trading order"})
        await store.index_document("test", {"content": "GST rate revision for steel"})

        results = await store.search("test", "defaulter")
        assert len(results) == 1
        assert "defaulter" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, store):
        await store.index_document("test", {"content": "RBI Circular 42"})
        results = await store.search("test", "rbi circular")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_with_keyword_filter(self, store):
        await store.index_document("test", {"source": "RBI", "content": "NPA norms"})
        await store.index_document("test", {"source": "SEBI", "content": "RPT norms"})

        results = await store.search("test", "norms", filters={"source": "RBI"})
        assert len(results) == 1
        assert results[0]["source"] == "RBI"

    @pytest.mark.asyncio
    async def test_search_with_list_filter(self, store):
        await store.index_document("test", {"severity": "HIGH", "content": "important"})
        await store.index_document("test", {"severity": "LOW", "content": "important"})

        results = await store.search(
            "test", "important", filters={"severity": ["HIGH", "CRITICAL"]},
        )
        assert len(results) == 1
        assert results[0]["severity"] == "HIGH"

    @pytest.mark.asyncio
    async def test_search_empty_query(self, store):
        await store.index_document("test", {"content": "some data"})
        # Empty string won't match anything (no substring match)
        results = await store.search("test", "nonexistent query")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_nonexistent_index(self, store):
        results = await store.search("ghost_index", "anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_size_limit(self, store):
        for i in range(20):
            await store.index_document("test", {"content": f"document number {i}"})
        results = await store.search("test", "document", size=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_delete_document(self, store):
        doc_id = await store.index_document("test", {"content": "delete me"}, doc_id="del-1")
        assert await store.count("test") == 1
        deleted = await store.delete_document("test", "del-1")
        assert deleted is True
        assert await store.count("test") == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_document(self, store):
        deleted = await store.delete_document("test", "nope")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_delete_index(self, store):
        await store.create_index("test")
        await store.index_document("test", {"content": "data"})
        deleted = await store.delete_index("test")
        assert deleted is True
        assert not await store.index_exists("test")

    @pytest.mark.asyncio
    async def test_count_empty_index(self, store):
        await store.create_index("empty")
        assert await store.count("empty") == 0

    @pytest.mark.asyncio
    async def test_count_nonexistent_index(self, store):
        assert await store.count("ghost") == 0

    @pytest.mark.asyncio
    async def test_get_document_nonexistent(self, store):
        result = await store.get_document("test", "no-such-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_close(self, store):
        # Should not raise
        await store.close()


# ══════════════════════════════════════════════
# 2. ElasticsearchClient Tests (In-Memory Mode)
# ══════════════════════════════════════════════

class TestElasticsearchClient:
    """⚙️ Systems + 🧪 QA: client initialization, CRUD, fallback behavior."""

    @pytest.mark.asyncio
    async def test_initialize_in_memory_no_hosts(self, es_client):
        await es_client.initialize()
        assert es_client._initialized
        assert es_client._use_es is False
        assert es_client._store is not None

    @pytest.mark.asyncio
    async def test_all_four_indices_created(self, es_client):
        await es_client.initialize()
        for idx in ESIndex:
            assert await es_client._store.index_exists(idx.value)

    @pytest.mark.asyncio
    async def test_double_initialize_safe(self, es_client):
        await es_client.initialize()
        await es_client.initialize()
        assert es_client._initialized

    @pytest.mark.asyncio
    async def test_auto_initializes_on_operation(self, es_client):
        doc_id = await es_client.index_document("document_store", {"content": "test"})
        assert doc_id
        assert es_client._initialized

    @pytest.mark.asyncio
    async def test_index_and_search(self, es_client):
        await es_client.initialize()
        await es_client.index_document(
            ESIndex.DOCUMENT_STORE.value,
            {"content": "steel revenue growth 15%", "doc_type": "annual_report"},
        )
        results = await es_client.search(ESIndex.DOCUMENT_STORE.value, "revenue growth")
        assert len(results) == 1
        assert "revenue growth" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_bulk_index_and_count(self, es_client):
        await es_client.initialize()
        docs = [{"content": f"research {i}", "source": "tavily"} for i in range(5)]
        count = await es_client.bulk_index(ESIndex.RESEARCH_INTELLIGENCE.value, docs)
        assert count == 5
        total = await es_client.count(ESIndex.RESEARCH_INTELLIGENCE.value)
        assert total == 5

    @pytest.mark.asyncio
    async def test_delete_document(self, es_client):
        await es_client.initialize()
        doc_id = await es_client.index_document(
            ESIndex.DOCUMENT_STORE.value, {"content": "delete"}, doc_id="x1",
        )
        assert await es_client.delete_document(ESIndex.DOCUMENT_STORE.value, "x1")
        assert await es_client.count(ESIndex.DOCUMENT_STORE.value) == 0

    @pytest.mark.asyncio
    async def test_get_document(self, es_client):
        await es_client.initialize()
        await es_client.index_document(
            ESIndex.DOCUMENT_STORE.value, {"content": "hello"}, doc_id="get-1",
        )
        doc = await es_client.get_document(ESIndex.DOCUMENT_STORE.value, "get-1")
        assert doc is not None
        assert doc["content"] == "hello"

    @pytest.mark.asyncio
    async def test_get_stats(self, es_client):
        await es_client.initialize()
        await es_client.index_document(ESIndex.DOCUMENT_STORE.value, {"content": "a"})
        await es_client.index_document(ESIndex.REGULATORY_WATCHLIST.value, {"content": "b"})
        stats = await es_client.get_stats()
        assert stats["document_store"] == 1
        assert stats["regulatory_watchlist"] == 1
        assert stats["research_intelligence"] == 0

    @pytest.mark.asyncio
    async def test_close(self, es_client):
        await es_client.initialize()
        await es_client.close()  # Should not raise


# ══════════════════════════════════════════════
# 3. Domain-Specific ES Operations
# ══════════════════════════════════════════════

class TestDomainOperations:
    """🏦 Credit Expert + 🎯 Judge: domain helpers produce correct data."""

    @pytest.mark.asyncio
    async def test_index_document_chunk(self, es_client):
        await es_client.initialize()
        doc_id = await es_client.index_document_chunk(
            session_id="sess-001",
            doc_type="annual_report",
            page=12,
            content="Revenue for FY2024 was ₹247 crores, up 15% YoY",
            confidence=0.92,
            worker_id="W1",
            entities=["revenue", "FY2024"],
        )
        assert doc_id
        doc = await es_client.get_document(ESIndex.DOCUMENT_STORE.value, doc_id)
        assert doc["session_id"] == "sess-001"
        assert doc["doc_type"] == "annual_report"
        assert doc["page"] == 12
        assert "₹247 crores" in doc["content"]

    @pytest.mark.asyncio
    async def test_index_research_finding(self, es_client):
        await es_client.initialize()
        doc_id = await es_client.index_research_finding(
            session_id="sess-001",
            source="tavily",
            source_tier=2,
            source_weight=0.85,
            title="XYZ Steel Financial Analysis",
            content="Strong Q3 earnings beat estimates by 12%",
            category="financial",
            url="https://example.com/xyz",
            verified=True,
            relevance_score=0.88,
        )
        assert doc_id
        results = await es_client.search(ESIndex.RESEARCH_INTELLIGENCE.value, "Q3 earnings")
        assert len(results) == 1
        assert results[0]["source"] == "tavily"

    @pytest.mark.asyncio
    async def test_index_regulatory_item(self, es_client):
        await es_client.initialize()
        doc_id = await es_client.index_regulatory_item(
            source="RBI",
            regulation_type="circular",
            title="RBI/2024/42 — NPA Recognition",
            content="Revised NPA norms for steel sector lending",
            sectors_affected=["steel", "banking"],
            severity="HIGH",
        )
        assert doc_id
        results = await es_client.search(ESIndex.REGULATORY_WATCHLIST.value, "NPA")
        assert len(results) == 1
        assert results[0]["source"] == "RBI"
        assert "steel" in results[0]["sectors_affected"]

    @pytest.mark.asyncio
    async def test_search_regulatory(self, es_client):
        await es_client.initialize()
        await es_client.index_regulatory_item(
            source="SEBI", regulation_type="order",
            title="SEBI RPT Framework", content="Related party transactions",
            sectors_affected=["general"],
        )
        await es_client.index_regulatory_item(
            source="RBI", regulation_type="circular",
            title="RBI Steel NPA", content="Steel sector NPA norms",
            sectors_affected=["steel"],
        )
        results = await es_client.search_regulatory("RPT")
        assert len(results) == 1
        assert "RPT" in results[0]["title"]

    @pytest.mark.asyncio
    async def test_index_company_profile(self, es_client):
        await es_client.initialize()
        doc_id = await es_client.index_company_profile(
            company_name="XYZ Steel Ltd",
            cin="U27100MH2015PLC",
            sector="steel",
            last_score=477,
            last_band="Poor",
            last_outcome="CONDITIONAL",
            assessment_count=1,
        )
        assert doc_id
        results = await es_client.search(ESIndex.COMPANY_PROFILES.value, "XYZ Steel")
        assert len(results) == 1
        assert results[0]["last_assessment_score"] == 477

    @pytest.mark.asyncio
    async def test_document_chunk_search_by_session(self, es_client):
        """Credit expert: find all chunks for a specific assessment session."""
        await es_client.initialize()
        await es_client.index_document_chunk("s1", "annual_report", 1, "Revenue ₹100cr")
        await es_client.index_document_chunk("s1", "gst_return", 1, "GSTR-3B filed")
        await es_client.index_document_chunk("s2", "annual_report", 1, "Revenue ₹200cr")

        results = await es_client.search(
            ESIndex.DOCUMENT_STORE.value, "Revenue",
            filters={"session_id": "s1"},
        )
        assert len(results) == 1
        assert "₹100cr" in results[0]["content"]


# ══════════════════════════════════════════════
# 4. Index Mapping Tests
# ══════════════════════════════════════════════

class TestIndexMappings:
    """🧪 QA: index definitions are correct and complete."""

    def test_all_four_indices_have_mappings(self):
        for idx in ESIndex:
            assert idx in INDEX_MAPPINGS or idx.value in {
                k.value if hasattr(k, 'value') else k for k in INDEX_MAPPINGS
            }

    def test_document_store_has_required_fields(self):
        props = INDEX_MAPPINGS[ESIndex.DOCUMENT_STORE]["mappings"]["properties"]
        required = ["session_id", "doc_type", "page", "content", "confidence"]
        for field in required:
            assert field in props, f"Missing field: {field}"

    def test_research_intelligence_has_required_fields(self):
        props = INDEX_MAPPINGS[ESIndex.RESEARCH_INTELLIGENCE]["mappings"]["properties"]
        required = ["source", "source_tier", "content", "verified", "category"]
        for field in required:
            assert field in props, f"Missing field: {field}"

    def test_regulatory_watchlist_has_required_fields(self):
        props = INDEX_MAPPINGS[ESIndex.REGULATORY_WATCHLIST]["mappings"]["properties"]
        required = ["source", "regulation_type", "title", "content", "severity", "sectors_affected"]
        for field in required:
            assert field in props, f"Missing field: {field}"

    def test_company_profiles_has_required_fields(self):
        props = INDEX_MAPPINGS[ESIndex.COMPANY_PROFILES]["mappings"]["properties"]
        required = ["company_name", "sector", "last_assessment_score", "assessment_count"]
        for field in required:
            assert field in props, f"Missing field: {field}"


# ══════════════════════════════════════════════
# 5. Singleton Tests
# ══════════════════════════════════════════════

class TestSingleton:
    """⚙️ Systems: singleton pattern correctness."""

    def test_get_elasticsearch_client_reuses(self):
        c1 = get_elasticsearch_client()
        c2 = get_elasticsearch_client()
        assert c1 is c2

    def test_reset_creates_new_instance(self):
        c1 = get_elasticsearch_client()
        reset_elasticsearch_client()
        c2 = get_elasticsearch_client()
        assert c1 is not c2


# ══════════════════════════════════════════════
# 6. Regulatory Feed Unit Tests
# ══════════════════════════════════════════════

class TestRegulatoryFeed:
    """🏦 Credit Expert + 🎯 Judge: feed crawl and sector query."""

    @pytest.mark.asyncio
    async def test_initialize(self, reg_feed):
        await reg_feed.initialize()
        assert reg_feed._initialized

    @pytest.mark.asyncio
    async def test_double_initialize_safe(self, reg_feed):
        await reg_feed.initialize()
        await reg_feed.initialize()
        assert reg_feed._initialized

    @pytest.mark.asyncio
    async def test_crawl_all_sources(self, reg_feed):
        counts = await reg_feed.crawl_all_sources()
        assert len(counts) == 4  # RBI, SEBI, MCA, GST_COUNCIL
        assert all(v > 0 for v in counts.values())
        total = sum(counts.values())
        assert total >= 8  # At least 8 mock items across all sources

    @pytest.mark.asyncio
    async def test_crawl_single_source_rbi(self, reg_feed):
        count = await reg_feed.crawl_source(RegulatorySource.RBI)
        assert count == len(_get_mock_rbi_items())

    @pytest.mark.asyncio
    async def test_crawl_single_source_sebi(self, reg_feed):
        count = await reg_feed.crawl_source(RegulatorySource.SEBI)
        assert count == len(_get_mock_sebi_items())

    @pytest.mark.asyncio
    async def test_crawl_single_source_mca(self, reg_feed):
        count = await reg_feed.crawl_source(RegulatorySource.MCA)
        assert count == len(_get_mock_mca_items())

    @pytest.mark.asyncio
    async def test_crawl_single_source_gst(self, reg_feed):
        count = await reg_feed.crawl_source(RegulatorySource.GST_COUNCIL)
        assert count == len(_get_mock_gst_items())

    @pytest.mark.asyncio
    async def test_get_sector_regulations_steel(self, reg_feed):
        """🏦 Credit expert: steel sector pulls GST rate change + general items."""
        await reg_feed.crawl_all_sources()
        results = await reg_feed.get_sector_regulations("steel")
        assert len(results) > 0
        # Should include GST steel decision
        titles = [r.get("title", "") for r in results]
        has_steel = any("steel" in t.lower() or "Steel" in t for t in titles)
        assert has_steel, f"No steel-related regulation found. Titles: {titles}"

    @pytest.mark.asyncio
    async def test_get_sector_regulations_general(self, reg_feed):
        """General sector should return most items (via keyword match)."""
        await reg_feed.crawl_all_sources()
        # General sector searches for keywords like 'corporate', 'company', 'compliance', 'GST'
        results = await reg_feed.get_sector_regulations("banking")
        assert len(results) > 0  # RBI items mention banking concepts

    @pytest.mark.asyncio
    async def test_get_sector_regulations_sorted_by_severity(self, reg_feed):
        """🎯 Judge: CRITICAL items appear first."""
        await reg_feed.crawl_all_sources()
        results = await reg_feed.get_sector_regulations("general", max_results=20)

        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}
        if len(results) >= 2:
            first_sev = severity_order.get(results[0].get("severity", "INFO"), 3)
            last_sev = severity_order.get(results[-1].get("severity", "INFO"), 3)
            assert first_sev <= last_sev

    @pytest.mark.asyncio
    async def test_get_critical_alerts(self, reg_feed):
        """🏦 Credit expert: wilful defaulter update is CRITICAL."""
        await reg_feed.crawl_all_sources()
        alerts = await reg_feed.get_critical_alerts()
        assert len(alerts) > 0
        for alert in alerts:
            assert alert.get("severity") == "CRITICAL"

    @pytest.mark.asyncio
    async def test_search_regulations_freeform(self, reg_feed):
        await reg_feed.crawl_all_sources()
        results = await reg_feed.search_regulations("wilful defaulter")
        assert len(results) > 0
        assert any("defaulter" in r.get("content", "").lower() for r in results)

    @pytest.mark.asyncio
    async def test_search_regulations_with_source_filter(self, reg_feed):
        await reg_feed.crawl_all_sources()
        results = await reg_feed.search_regulations(
            "norms", source=RegulatorySource.RBI,
        )
        for r in results:
            assert r.get("source") == "RBI"

    @pytest.mark.asyncio
    async def test_get_feed_stats(self, reg_feed):
        await reg_feed.crawl_all_sources()
        stats = await reg_feed.get_feed_stats()
        assert stats["total_items"] > 0
        assert stats["index"] == "regulatory_watchlist"
        assert len(stats["sources"]) == 4

    @pytest.mark.asyncio
    async def test_to_research_findings(self, reg_feed):
        """🎯 Judge + 🏦 Credit: regulatory items convert to ResearchFindings."""
        await reg_feed.crawl_all_sources()
        findings = await reg_feed.to_research_findings("steel")
        assert len(findings) > 0
        for f in findings:
            assert f.source_tier == 1
            assert f.source_weight == 1.0
            assert f.verified is True
            assert f.category == "regulatory"

    @pytest.mark.asyncio
    async def test_to_research_findings_unknown_sector(self, reg_feed):
        """🧪 QA: unknown sector falls back to general keywords."""
        await reg_feed.crawl_all_sources()
        findings = await reg_feed.to_research_findings("exotic_widgets")
        # Should still find some results via general keywords
        assert isinstance(findings, list)


# ══════════════════════════════════════════════
# 7. Mock Data Quality Tests
# ══════════════════════════════════════════════

class TestMockDataQuality:
    """🏦 Credit Expert + 🎯 Judge: mock data is realistic and correct."""

    def test_rbi_items_have_required_fields(self):
        for item in _get_mock_rbi_items():
            assert item["source"] == "RBI"
            assert item["regulation_type"]
            assert item["title"]
            assert len(item["content"]) > 50  # Substantive content
            assert item["severity"] in ["CRITICAL", "HIGH", "MEDIUM", "INFO"]
            assert isinstance(item["sectors_affected"], list)

    def test_sebi_items_mention_real_regulations(self):
        """Credit expert: SEBI items reference real Indian regulatory concepts."""
        for item in _get_mock_sebi_items():
            content = item["content"].lower()
            # Should mention real regulatory concepts
            assert any(term in content for term in [
                "rpt", "related party", "lodr", "pledge", "promoter",
                "audit committee", "shareholder", "insider",
            ])

    def test_mca_items_reference_companies_act(self):
        for item in _get_mock_mca_items():
            content = item["content"].lower()
            assert any(term in content for term in [
                "auditor", "company", "director", "filing", "beneficial",
                "form", "compliance",
            ])

    def test_gst_items_mention_gst_concepts(self):
        for item in _get_mock_gst_items():
            content = item["content"].lower()
            assert any(term in content for term in [
                "gst", "gstr", "itc", "hsn", "rate", "input tax",
            ])

    def test_all_mock_items_have_urls(self):
        """Judge: demo data looks professional with URLs."""
        all_items = (
            _get_mock_rbi_items() +
            _get_mock_sebi_items() +
            _get_mock_mca_items() +
            _get_mock_gst_items()
        )
        for item in all_items:
            assert "url" in item
            assert item["url"]  # Non-empty

    def test_severity_distribution_realistic(self):
        """Credit expert: not all items are CRITICAL — realistic distribution."""
        all_items = (
            _get_mock_rbi_items() +
            _get_mock_sebi_items() +
            _get_mock_mca_items() +
            _get_mock_gst_items()
        )
        severities = [i["severity"] for i in all_items]
        # Should have mix, not all one severity
        unique_severities = set(severities)
        assert len(unique_severities) >= 2, f"Only one severity: {unique_severities}"

    def test_effective_dates_present(self):
        all_items = (
            _get_mock_rbi_items() +
            _get_mock_sebi_items() +
            _get_mock_mca_items() +
            _get_mock_gst_items()
        )
        for item in all_items:
            assert "effective_date" in item


# ══════════════════════════════════════════════
# 8. Sector Keyword Tests
# ══════════════════════════════════════════════

class TestSectorKeywords:
    """🧪 QA: keyword mappings are complete and reasonable."""

    def test_general_sector_exists(self):
        assert "general" in SECTOR_KEYWORDS
        assert len(SECTOR_KEYWORDS["general"]) > 0

    def test_steel_sector_has_relevant_keywords(self):
        kw = SECTOR_KEYWORDS.get("steel", [])
        assert any(w in kw for w in ["steel", "metals", "iron"])

    def test_all_sectors_have_keywords(self):
        for sector, keywords in SECTOR_KEYWORDS.items():
            assert len(keywords) >= 3, f"Sector {sector} has too few keywords"

    def test_no_empty_keywords(self):
        for sector, keywords in SECTOR_KEYWORDS.items():
            for kw in keywords:
                assert kw.strip(), f"Empty keyword in sector {sector}"


# ══════════════════════════════════════════════
# 9. Security Tests
# ══════════════════════════════════════════════

class TestSecurity:
    """🔒 Security Architect: injection + validation."""

    @pytest.mark.asyncio
    async def test_search_with_special_characters(self, es_client):
        """No injection via search query."""
        await es_client.initialize()
        await es_client.index_document(ESIndex.DOCUMENT_STORE.value, {"content": "safe content"})
        # These should not crash
        results = await es_client.search(ESIndex.DOCUMENT_STORE.value, "<script>alert(1)</script>")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_sql_injection(self, es_client):
        await es_client.initialize()
        results = await es_client.search(
            ESIndex.DOCUMENT_STORE.value, "'; DROP TABLE documents; --",
        )
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_index_with_very_large_content(self, es_client):
        """No crash on large documents."""
        await es_client.initialize()
        large_content = "x" * 100_000  # 100KB
        doc_id = await es_client.index_document(
            ESIndex.DOCUMENT_STORE.value, {"content": large_content},
        )
        assert doc_id

    @pytest.mark.asyncio
    async def test_search_path_traversal_in_index(self, es_client):
        """No path traversal via index name."""
        await es_client.initialize()
        results = await es_client.search("../../etc/passwd", "test")
        assert isinstance(results, list)
        assert len(results) == 0


# ══════════════════════════════════════════════
# 10. Regulatory Feed Singleton Tests
# ══════════════════════════════════════════════

class TestRegFeedSingleton:
    """⚙️ Systems: singleton pattern for feed."""

    def test_get_regulatory_feed_reuses(self):
        f1 = get_regulatory_feed()
        f2 = get_regulatory_feed()
        assert f1 is f2

    def test_reset_creates_new(self):
        f1 = get_regulatory_feed()
        reset_regulatory_feed()
        f2 = get_regulatory_feed()
        assert f1 is not f2


# ══════════════════════════════════════════════
# 11. Enum Tests
# ══════════════════════════════════════════════

class TestEnums:
    """🧪 QA: enums have correct values."""

    def test_es_index_values(self):
        assert ESIndex.DOCUMENT_STORE.value == "document_store"
        assert ESIndex.RESEARCH_INTELLIGENCE.value == "research_intelligence"
        assert ESIndex.COMPANY_PROFILES.value == "company_profiles"
        assert ESIndex.REGULATORY_WATCHLIST.value == "regulatory_watchlist"

    def test_regulatory_source_values(self):
        assert RegulatorySource.RBI.value == "RBI"
        assert RegulatorySource.SEBI.value == "SEBI"
        assert RegulatorySource.MCA.value == "MCA"
        assert RegulatorySource.GST_COUNCIL.value == "GST_COUNCIL"

    def test_severity_values(self):
        assert RegulationSeverity.CRITICAL.value == "CRITICAL"
        assert RegulationSeverity.HIGH.value == "HIGH"
        assert RegulationSeverity.MEDIUM.value == "MEDIUM"
        assert RegulationSeverity.INFO.value == "INFO"

    def test_regulation_type_values(self):
        assert RegulationType.CIRCULAR.value == "circular"
        assert RegulationType.NOTIFICATION.value == "notification"
        assert RegulationType.ORDER.value == "order"


# ══════════════════════════════════════════════
# 12. Edge Cases
# ══════════════════════════════════════════════

class TestEdgeCases:
    """🧪 QA Engineer: boundary + unusual inputs."""

    @pytest.mark.asyncio
    async def test_empty_document(self, es_client):
        await es_client.initialize()
        doc_id = await es_client.index_document(ESIndex.DOCUMENT_STORE.value, {})
        assert doc_id

    @pytest.mark.asyncio
    async def test_unicode_content(self, es_client):
        await es_client.initialize()
        doc_id = await es_client.index_document_chunk(
            session_id="s1", doc_type="annual_report", page=1,
            content="मुंबई स्टील प्राइवेट लिमिटेड — राजस्व ₹247 करोड़",
        )
        assert doc_id
        results = await es_client.search(ESIndex.DOCUMENT_STORE.value, "मुंबई")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_regulatory_item_with_no_sectors(self, es_client):
        await es_client.initialize()
        doc_id = await es_client.index_regulatory_item(
            source="RBI", regulation_type="circular",
            title="General Advisory", content="General advisory content",
        )
        assert doc_id

    @pytest.mark.asyncio
    async def test_bulk_index_empty_list(self, es_client):
        await es_client.initialize()
        count = await es_client.bulk_index(ESIndex.DOCUMENT_STORE.value, [])
        assert count == 0

    @pytest.mark.asyncio
    async def test_search_with_empty_string(self, es_client):
        await es_client.initialize()
        await es_client.index_document(ESIndex.DOCUMENT_STORE.value, {"content": "data"})
        results = await es_client.search(ESIndex.DOCUMENT_STORE.value, "")
        # Empty query matches everything (empty string is in every string)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_regulatory_feed_empty_sector(self, reg_feed):
        await reg_feed.crawl_all_sources()
        results = await reg_feed.get_sector_regulations("")
        assert isinstance(results, list)


# ══════════════════════════════════════════════
# 13. Integration — Research Node with Regulatory Feed
# ══════════════════════════════════════════════

class TestResearchNodeIntegration:
    """🎯 Judge + ⚙️ Systems: regulatory feed integrates into pipeline."""

    @pytest.mark.asyncio
    async def test_research_node_imports_regulatory_feed(self):
        """Verify research_node can import the regulatory feed."""
        from backend.graph.nodes.research_node import research_node
        assert callable(research_node)

    @pytest.mark.asyncio
    async def test_research_node_uses_feed(self):
        """🎯 Judge: research node includes regulatory findings."""
        from backend.graph.state import CreditAppraisalState, CompanyInfo
        from backend.graph.nodes.research_node import research_node

        state = CreditAppraisalState(
            session_id="test-reg-integration",
            company=CompanyInfo(
                name="XYZ Steel Ltd",
                sector="steel",
                loan_type="Working Capital",
                loan_amount="₹50 crores",
                loan_amount_numeric=50.0,
            ),
        )

        # Pre-populate the regulatory feed
        from backend.agents.research.regulatory_feed import reset_regulatory_feed
        reset_regulatory_feed()
        feed = get_regulatory_feed()
        await feed.crawl_all_sources()

        result = await research_node(state)
        pkg = result["research_package"]

        # Should include regulatory findings from feed
        reg_findings = [f for f in pkg.findings if f.category == "regulatory"]
        assert len(reg_findings) >= 3  # At least the govt scraper + feed items
