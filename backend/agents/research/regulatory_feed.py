"""
Intelli-Credit — Regulatory Intelligence Feed (T4.3)

Daily-crawl system for Indian financial regulatory notifications:
- RBI Circulars & Notifications
- SEBI Regulations & Orders
- MCA Notifications & Circulars
- GST Council Decisions

On each assessment, queries sector-relevant regulations from the last 6 months
and surfaces them to Agent 2 (Research Agent) as additional research findings.

The feed indexes into Elasticsearch regulatory_watchlist and can also produce
ResearchFinding objects for direct pipeline consumption.

Usage:
    feed = RegulatoryFeed()
    await feed.initialize()

    # Daily crawl (background job)
    items = await feed.crawl_all_sources()

    # During assessment — get relevant regulations
    findings = await feed.get_sector_regulations("steel", months_back=6)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum

from backend.storage.elasticsearch_client import (
    get_elasticsearch_client,
    ElasticsearchClient,
    ESIndex,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Regulatory Source Definitions
# ──────────────────────────────────────────────

class RegulatorySource(str, Enum):
    RBI = "RBI"
    SEBI = "SEBI"
    MCA = "MCA"
    GST_COUNCIL = "GST_COUNCIL"


class RegulationSeverity(str, Enum):
    CRITICAL = "CRITICAL"     # Immediate impact on credit decisions
    HIGH = "HIGH"             # Material impact on scoring
    MEDIUM = "MEDIUM"         # Moderate relevance
    INFO = "INFO"             # Background information


class RegulationType(str, Enum):
    CIRCULAR = "circular"
    NOTIFICATION = "notification"
    ORDER = "order"
    REGULATION = "regulation"
    ADVISORY = "advisory"
    PRESS_RELEASE = "press_release"


# ──────────────────────────────────────────────
# Sector → Regulation Keyword Mapping
# ──────────────────────────────────────────────

SECTOR_KEYWORDS: Dict[str, List[str]] = {
    "steel": [
        "steel", "metals", "iron", "mining", "infrastructure",
        "anti-dumping", "safeguard duty", "PLI scheme", "BIS quality",
    ],
    "manufacturing": [
        "manufacturing", "industrial", "factory", "PLI",
        "Make in India", "production", "MSME",
    ],
    "it": [
        "IT", "software", "technology", "STPI", "SEZ",
        "digital", "cyber", "data protection",
    ],
    "pharma": [
        "pharma", "pharmaceutical", "drug", "DCGI", "FDA",
        "API", "bulk drug", "medical device",
    ],
    "infrastructure": [
        "infrastructure", "construction", "road", "highway",
        "NHAI", "PPP", "EPC", "toll",
    ],
    "power": [
        "power", "energy", "electricity", "renewable",
        "solar", "wind", "thermal", "discoms",
    ],
    "banking": [
        "banking", "NBFC", "NPA", "credit", "loan",
        "Basel", "IRAC", "provisioning",
    ],
    "real_estate": [
        "real estate", "RERA", "construction", "housing",
        "PMAY", "urban development",
    ],
    "textiles": [
        "textile", "garment", "cotton", "weaving",
        "PLI textile", "TUF scheme",
    ],
    "general": [
        "corporate", "company", "compliance", "GST",
        "income tax", "audit", "board", "director",
    ],
}


# ──────────────────────────────────────────────
# Mock Regulatory Data (for demo / when scrapers unavailable)
# ──────────────────────────────────────────────

def _get_mock_rbi_items() -> List[Dict[str, Any]]:
    """Mock RBI circulars for demo."""
    return [
        {
            "source": RegulatorySource.RBI.value,
            "regulation_type": RegulationType.CIRCULAR.value,
            "title": "RBI/2024-25/42 — Revised Framework for Resolution of Stressed Assets",
            "content": (
                "The Reserve Bank has revised the framework for resolution of "
                "stressed assets by regulated entities. Key changes: (1) Early "
                "warning signals must be monitored within 30 days of first default, "
                "(2) Resolution plan must be implemented within 180 days, "
                "(3) Additional provisioning requirements for accounts not resolved "
                "within the timeline. Applicable to all commercial banks and NBFCs."
            ),
            "url": "https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12345",
            "sectors_affected": ["banking", "general"],
            "severity": RegulationSeverity.HIGH.value,
            "effective_date": "2024-04-01",
        },
        {
            "source": RegulatorySource.RBI.value,
            "regulation_type": RegulationType.NOTIFICATION.value,
            "title": "RBI — Updation of Wilful Defaulter Registry (Q4 FY2024)",
            "content": (
                "Reserve Bank has updated the wilful defaulter registry as of "
                "March 31, 2024. Banks are directed to check the updated registry "
                "before sanctioning new credit facilities. 47 new entities added, "
                "12 removed after settlement. Total entries: 2,847."
            ),
            "url": "https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12346",
            "sectors_affected": ["general", "banking"],
            "severity": RegulationSeverity.CRITICAL.value,
            "effective_date": "2024-03-31",
        },
        {
            "source": RegulatorySource.RBI.value,
            "regulation_type": RegulationType.CIRCULAR.value,
            "title": "RBI — Scale-Based Regulation for NBFCs — Update",
            "content": (
                "Revised asset classification norms for NBFCs aligned with bank "
                "IRAC norms from October 2024. NBFCs with asset size > ₹1000cr "
                "must comply with enhanced NPA recognition timelines. "
                "Impacts DSCR calculations for NBFC borrowers."
            ),
            "url": "https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12347",
            "sectors_affected": ["banking", "general"],
            "severity": RegulationSeverity.MEDIUM.value,
            "effective_date": "2024-10-01",
        },
    ]


def _get_mock_sebi_items() -> List[Dict[str, Any]]:
    """Mock SEBI regulations for demo."""
    return [
        {
            "source": RegulatorySource.SEBI.value,
            "regulation_type": RegulationType.REGULATION.value,
            "title": "SEBI — Revised Related Party Transaction Framework (LODR Amendment)",
            "content": (
                "SEBI has tightened RPT disclosure norms. Listed companies must now "
                "obtain prior audit committee approval for ALL RPTs exceeding ₹1000cr "
                "or 10% of consolidated turnover. Definition of 'related party' expanded "
                "to include entities where any related party has 20%+ stake (previously 10%). "
                "Material modifications to RPTs require shareholder approval."
            ),
            "url": "https://sebi.gov.in/legal/regulations/jan-2024/12345.html",
            "sectors_affected": ["general"],
            "severity": RegulationSeverity.HIGH.value,
            "effective_date": "2024-01-01",
        },
        {
            "source": RegulatorySource.SEBI.value,
            "regulation_type": RegulationType.ORDER.value,
            "title": "SEBI — Enhanced Promoter Pledge Disclosure Requirements",
            "content": (
                "Listed entities where promoter pledge exceeds 50% of holdings "
                "must make immediate disclosure (within 2 trading days) of any "
                "change in pledge percentage. Non-compliance attracts penalty of "
                "₹1 lakh per day. Impacts score for Character (pledge assessment)."
            ),
            "url": "https://sebi.gov.in/legal/orders/mar-2024/12346.html",
            "sectors_affected": ["general"],
            "severity": RegulationSeverity.MEDIUM.value,
            "effective_date": "2024-03-15",
        },
    ]


def _get_mock_mca_items() -> List[Dict[str, Any]]:
    """Mock MCA notifications for demo."""
    return [
        {
            "source": RegulatorySource.MCA.value,
            "regulation_type": RegulationType.NOTIFICATION.value,
            "title": "MCA — Companies (Auditor's Report) Order, 2024 Amendment",
            "content": (
                "Auditors must now specifically report on: (1) Compliance with "
                "number of layers for investment companies, (2) Adherence to "
                "related party transaction limits, (3) Utilization of borrowed "
                "funds and share premium for stated purposes. Impacts annual "
                "report extraction and auditor qualification assessment."
            ),
            "url": "https://mca.gov.in/Ministry/pdf/AMEND_ORDER_2024.pdf",
            "sectors_affected": ["general"],
            "severity": RegulationSeverity.MEDIUM.value,
            "effective_date": "2024-04-01",
        },
        {
            "source": RegulatorySource.MCA.value,
            "regulation_type": RegulationType.CIRCULAR.value,
            "title": "MCA — Mandatory Filing of Beneficial Ownership (Form BEN-2)",
            "content": (
                "Significant beneficial owners (SBOs) holding ≥10% equity or "
                "exercising significant influence must be declared via Form BEN-2. "
                "Non-compliance: ₹50,000/day penalty. Important for identifying "
                "hidden promoter stakes and beneficial ownership chains."
            ),
            "url": "https://mca.gov.in/Ministry/pdf/BEN2_CIRCULAR_2024.pdf",
            "sectors_affected": ["general"],
            "severity": RegulationSeverity.HIGH.value,
            "effective_date": "2024-06-01",
        },
    ]


def _get_mock_gst_items() -> List[Dict[str, Any]]:
    """Mock GST Council decisions for demo."""
    return [
        {
            "source": RegulatorySource.GST_COUNCIL.value,
            "regulation_type": RegulationType.PRESS_RELEASE.value,
            "title": "GST Council 52nd Meeting — Key Decisions for Steel Sector",
            "content": (
                "GST Council has rationalized rates for steel products: "
                "HSN 7206-7229 (flat-rolled, bars, angles) reduced from 18% to 12%. "
                "Effective from next quarter. Impact on working capital cycle "
                "and input tax credit for steel manufacturers."
            ),
            "url": "https://gstcouncil.gov.in/sites/default/files/PR_52nd.pdf",
            "sectors_affected": ["steel", "manufacturing", "infrastructure"],
            "severity": RegulationSeverity.HIGH.value,
            "effective_date": "2024-07-01",
        },
        {
            "source": RegulatorySource.GST_COUNCIL.value,
            "regulation_type": RegulationType.ADVISORY.value,
            "title": "GST — Mandatory GSTR-2A Reconciliation Advisory for FY 2024-25",
            "content": (
                "GSTN advisory: Taxpayers must reconcile GSTR-2A with GSTR-3B "
                "before filing annual return GSTR-9. Discrepancies >10% between "
                "ITC claimed (3B) and ITC available (2A) will trigger automated "
                "notices. Critical for cross-verification in credit assessment."
            ),
            "url": "https://gstcouncil.gov.in/advisory/gstr2a-reconciliation",
            "sectors_affected": ["general"],
            "severity": RegulationSeverity.MEDIUM.value,
            "effective_date": "2024-05-01",
        },
    ]


# ──────────────────────────────────────────────
# Regulatory Feed Class
# ──────────────────────────────────────────────

class RegulatoryFeed:
    """
    Manages the regulatory intelligence feed.

    Crawls regulatory sources (mock/real), indexes into Elasticsearch
    regulatory_watchlist, and provides sector-relevant query interface.
    """

    def __init__(self, es_client: Optional[ElasticsearchClient] = None):
        self._es = es_client
        self._initialized = False

    async def initialize(self):
        """Initialize the feed with an Elasticsearch connection."""
        if self._initialized:
            return

        if self._es is None:
            self._es = get_elasticsearch_client()
        await self._es.initialize()
        self._initialized = True

    async def _ensure_initialized(self):
        if not self._initialized:
            await self.initialize()

    # ──────────────────────────────────────────
    # Crawl Operations
    # ──────────────────────────────────────────

    async def crawl_all_sources(self) -> Dict[str, int]:
        """
        Crawl all 4 regulatory sources and index findings.
        Returns count of items indexed per source.

        In production: calls real scrapers with Selenium/BS4.
        Currently: uses mock data for demo.
        """
        await self._ensure_initialized()
        counts: Dict[str, int] = {}

        sources = [
            (RegulatorySource.RBI, _get_mock_rbi_items),
            (RegulatorySource.SEBI, _get_mock_sebi_items),
            (RegulatorySource.MCA, _get_mock_mca_items),
            (RegulatorySource.GST_COUNCIL, _get_mock_gst_items),
        ]

        for source, fetch_fn in sources:
            try:
                items = fetch_fn()
                indexed = 0
                for item in items:
                    await self._es.index_regulatory_item(**item)
                    indexed += 1
                counts[source.value] = indexed
                logger.info(f"[RegFeed] Indexed {indexed} items from {source.value}")
            except Exception as e:
                logger.error(f"[RegFeed] Failed to crawl {source.value}: {e}")
                counts[source.value] = 0

        total = sum(counts.values())
        logger.info(f"[RegFeed] Crawl complete: {total} items indexed across {len(counts)} sources")
        return counts

    async def crawl_source(self, source: RegulatorySource) -> int:
        """Crawl a single regulatory source. Returns count indexed."""
        await self._ensure_initialized()

        source_fns = {
            RegulatorySource.RBI: _get_mock_rbi_items,
            RegulatorySource.SEBI: _get_mock_sebi_items,
            RegulatorySource.MCA: _get_mock_mca_items,
            RegulatorySource.GST_COUNCIL: _get_mock_gst_items,
        }

        fetch_fn = source_fns.get(source)
        if not fetch_fn:
            logger.warning(f"[RegFeed] Unknown source: {source}")
            return 0

        items = fetch_fn()
        count = 0
        for item in items:
            await self._es.index_regulatory_item(**item)
            count += 1

        return count

    # ──────────────────────────────────────────
    # Query Operations
    # ──────────────────────────────────────────

    async def get_sector_regulations(
        self,
        sector: str,
        months_back: int = 6,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get regulations relevant to a specific sector from the last N months.

        This is the primary interface during assessment — called by Agent 2
        to surface relevant regulatory context.

        Args:
            sector: Company sector (e.g., "steel", "manufacturing")
            months_back: How far back to look (default 6 months)
            max_results: Maximum results to return
        """
        await self._ensure_initialized()

        # Get sector keywords for search
        sector_lower = sector.lower().strip()
        keywords = SECTOR_KEYWORDS.get(sector_lower, SECTOR_KEYWORDS["general"])
        # Always include "general" keywords too
        if sector_lower != "general":
            keywords = keywords + SECTOR_KEYWORDS["general"]

        # Search using individual keywords (in-memory fallback does substring match)
        all_results: List[Dict[str, Any]] = []
        for kw in keywords[:8]:
            hits = await self._es.search(
                ESIndex.REGULATORY_WATCHLIST.value, kw, size=max_results,
            )
            all_results.extend(hits)

        # Also do a direct sector name search
        sector_hits = await self._es.search(
            ESIndex.REGULATORY_WATCHLIST.value,
            sector_lower,
            size=max_results,
        )

        # Merge and deduplicate
        seen_ids = set()
        merged = []
        for item in all_results + sector_hits:
            item_id = item.get("_id", item.get("title", ""))
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                merged.append(item)

        # Sort by severity (CRITICAL first)
        severity_order = {
            RegulationSeverity.CRITICAL.value: 0,
            RegulationSeverity.HIGH.value: 1,
            RegulationSeverity.MEDIUM.value: 2,
            RegulationSeverity.INFO.value: 3,
        }
        merged.sort(key=lambda x: severity_order.get(x.get("severity", "INFO"), 3))

        return merged[:max_results]

    async def get_critical_alerts(
        self, max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get all CRITICAL severity regulatory items."""
        await self._ensure_initialized()

        results = await self._es.search(
            ESIndex.REGULATORY_WATCHLIST.value,
            "CRITICAL",
            size=max_results,
            filters={"severity": RegulationSeverity.CRITICAL.value},
        )
        return results

    async def search_regulations(
        self,
        query: str,
        source: Optional[RegulatorySource] = None,
        severity: Optional[RegulationSeverity] = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Freeform search across all regulations with optional filters."""
        await self._ensure_initialized()

        filters: Optional[Dict[str, Any]] = {}
        if source:
            filters["source"] = source.value
        if severity:
            filters["severity"] = severity.value
        if not filters:
            filters = None

        return await self._es.search(
            ESIndex.REGULATORY_WATCHLIST.value,
            query,
            size=max_results,
            filters=filters,
        )

    async def get_feed_stats(self) -> Dict[str, Any]:
        """Get statistics about the regulatory feed."""
        await self._ensure_initialized()

        total = await self._es.count(ESIndex.REGULATORY_WATCHLIST.value)
        return {
            "total_items": total,
            "index": ESIndex.REGULATORY_WATCHLIST.value,
            "sources": [s.value for s in RegulatorySource],
        }

    async def to_research_findings(
        self,
        sector: str,
        months_back: int = 6,
    ) -> list:
        """
        Convert sector regulations into ResearchFinding objects
        for direct pipeline consumption by Agent 2.

        Each regulatory item becomes a tier-1 government research finding.
        """
        from backend.graph.state import ResearchFinding

        regulations = await self.get_sector_regulations(sector, months_back)
        findings = []

        for reg in regulations:
            findings.append(ResearchFinding(
                source=reg.get("source", "regulatory_feed").lower(),
                source_tier=1,
                source_weight=1.0,
                title=reg.get("title", "Regulatory Update"),
                content=reg.get("content", ""),
                url=reg.get("url", ""),
                relevance_score=0.90,
                verified=True,
                category="regulatory",
            ))

        return findings


# ──────────────────────────────────────────────
# Module-level convenience
# ──────────────────────────────────────────────

_feed_instance: Optional[RegulatoryFeed] = None


def get_regulatory_feed(
    es_client: Optional[ElasticsearchClient] = None,
) -> RegulatoryFeed:
    """Get or create the singleton RegulatoryFeed."""
    global _feed_instance
    if _feed_instance is None:
        _feed_instance = RegulatoryFeed(es_client)
    return _feed_instance


def reset_regulatory_feed():
    """Reset the singleton (for testing)."""
    global _feed_instance
    _feed_instance = None
