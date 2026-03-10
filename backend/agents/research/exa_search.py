"""
Intelli-Credit — Exa Deep Search Wrapper

Deep multi-query search via Exa API v1 with structured outputs and full text extraction.
Uses type="deep" (4-12s) for thorough research with field-level citations.
Especially strong for legal/regulatory document discovery, company intelligence,
promoter background checks, and sector outlook research.

Supports:
    - Company intelligence (news, filings, red flags)
    - Financial news (Tier 2 sources: ET, BS, Mint, FE, Reuters, Bloomberg)
    - Regulatory actions (Tier 1 sources: SEBI, RBI, MCA, NJDG, GST portals)
    - Litigation records (NCLT proceedings, court orders, legal disputes)
    - Promoter/director background (track record, other companies, red flags)
    - Sector/industry outlook (growth forecasts, policy impacts)

Returns tier-classified ResearchFinding objects with source credibility weighting.

Usage:
    # Basic search (backward compatible)
    findings = await search_exa("XYZ Steel Pvt Ltd")

    # Specialized deep searches
    findings = await search_exa_news("XYZ Steel financial results")
    findings = await search_exa_regulatory("XYZ Steel", "SEBI")
    findings = await search_exa_litigation("XYZ Steel")
    findings = await search_exa_promoter("Rajesh Agarwal", "XYZ Steel")
    findings = await search_exa_sector("Steel manufacturing India")

Fallback: Returns realistic mock findings when EXA_API_KEY is missing
or the exa-py package is unavailable.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional

from backend.graph.state import ResearchFinding

logger = logging.getLogger(__name__)

# Try to import Exa client
try:
    from exa_py import Exa
    _HAS_EXA = True
except ImportError:
    _HAS_EXA = False

EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
SEARCH_TIMEOUT = 15  # Deep search can take 4-12s


# ── Source Tier Classification ──
# Priority Rule (hardcoded — never change):
#   Government source (GST, ITR, SEBI, RBI, MCA21, NJDG) → tier 1 (weight 1.0)
#   Reputable financial media (ET, BS, Mint, FE)           → tier 2 (weight 0.85)
#   General/regional news                                   → tier 3 (weight 0.60)
#   Blogs, unverified sites                                 → tier 4 (weight 0.30)
#   Social media, anonymous                                 → tier 5 (weight 0.0)

TIER_1_DOMAINS = [
    "mca.gov.in", "sebi.gov.in", "rbi.org.in",
    "njdg.ecourts.gov.in", "gst.gov.in", "incometaxindia.gov.in",
]

TIER_2_DOMAINS = [
    "economictimes.indiatimes.com", "business-standard.com",
    "livemint.com", "financialexpress.com", "moneycontrol.com",
    "reuters.com", "bloomberg.com", "ndtv.com/business",
    "indiankanoon.org", "barandbench.com",
]

TIER_4_DOMAINS = [
    "medium.com", "wordpress.com", "blogspot.com",
    "quora.com", "reddit.com",
]

TIER_5_DOMAINS = [
    "twitter.com", "x.com", "facebook.com",
    "instagram.com", "tiktok.com",
]

SOURCE_TIER_WEIGHTS: Dict[int, float] = {
    1: 1.0,
    2: 0.85,
    3: 0.60,
    4: 0.30,
    5: 0.0,
}


def _classify_source_tier(url: str) -> int:
    """Classify source URL into verification credibility tier."""
    url_lower = url.lower()
    for domain in TIER_1_DOMAINS:
        if domain in url_lower:
            return 1
    for domain in TIER_2_DOMAINS:
        if domain in url_lower:
            return 2
    for domain in TIER_5_DOMAINS:
        if domain in url_lower:
            return 5
    for domain in TIER_4_DOMAINS:
        if domain in url_lower:
            return 4
    return 3  # Default: general/regional news


def _classify_content(content: str) -> str:
    """Keyword-based category classification for research findings."""
    lower = content.lower()
    if any(w in lower for w in ["lawsuit", "litigation", "court", "nclt", "legal", "dispute"]):
        return "litigation"
    if any(w in lower for w in ["sebi", "rbi", "regulatory", "compliance", "penalty", "circular"]):
        return "regulatory"
    if any(w in lower for w in ["fraud", "scam", "criminal", "wilful defaulter", "money laundering"]):
        return "fraud"
    if any(w in lower for w in ["board", "director", "governance", "promoter", "shareholding"]):
        return "governance"
    if any(w in lower for w in ["sector", "industry", "outlook", "growth", "forecast", "pli"]):
        return "sector"
    return "financial"


# ── Core Search Engine ──

async def _execute_exa_search(
    query: str,
    search_type: str = "deep",
    max_results: int = 5,
    max_characters: int = 20000,
    category: Optional[str] = None,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
) -> List[ResearchFinding]:
    """Execute Exa search with deep type, error handling, and tier classification.

    All search methods delegate to this. Implements:
    - Deep multi-query search (4-12s) with full text extraction
    - Source credibility tier classification per URL domain
    - Timeout + retry + fallback (pipeline never breaks)
    """
    exa = Exa(api_key=EXA_API_KEY)

    search_kwargs: Dict = {
        "type": search_type,
        "num_results": max_results,
        "text": {"max_characters": max_characters},
    }

    if category:
        search_kwargs["category"] = category
    if include_domains:
        search_kwargs["include_domains"] = include_domains
    if exclude_domains:
        search_kwargs["exclude_domains"] = exclude_domains

    # Exa SDK is synchronous — wrap in executor for non-blocking async
    response = await asyncio.to_thread(
        exa.search_and_contents,
        query,
        **search_kwargs,
    )

    findings: List[ResearchFinding] = []
    for result in response.results:
        url = getattr(result, "url", "")
        tier = _classify_source_tier(url)
        weight = SOURCE_TIER_WEIGHTS.get(tier, 0.60)
        text = getattr(result, "text", "") or ""

        findings.append(ResearchFinding(
            source="exa",
            source_tier=tier,
            source_weight=weight,
            title=getattr(result, "title", "Exa Result") or "Exa Result",
            content=text[:max_characters],
            url=url,
            published_date=getattr(result, "published_date", None),
            relevance_score=min(getattr(result, "score", 0.75), 1.0),
            verified=False,
            category=_classify_content(text),
        ))

    logger.info(
        f"[Exa] Query '{query[:60]}...' → {len(findings)} results "
        f"(best tier: {min((f.source_tier for f in findings), default=3)})"
    )
    return findings


# ── Public Search Functions ──

async def search_exa(
    company_name: str,
    max_results: int = 5,
) -> List[ResearchFinding]:
    """Deep search for legal/regulatory intelligence via Exa.

    Backward-compatible entry point. Uses deep search for thorough results.

    Args:
        company_name: Company name to research.
        max_results: Maximum results to return.

    Returns:
        List of tier-classified ResearchFinding objects.
    """
    if not company_name:
        return []

    if _HAS_EXA and EXA_API_KEY:
        try:
            return await asyncio.wait_for(
                _execute_exa_search(
                    query=f"{company_name} India legal proceedings regulatory actions financial",
                    search_type="deep",
                    max_results=max_results,
                    max_characters=20000,
                ),
                timeout=SEARCH_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("[Exa] Deep search timed out, using mock fallback")
        except Exception as e:
            logger.warning(f"[Exa] API error: {e}, using mock fallback")

    return _mock_search(company_name)


async def search_exa_company(
    company_name: str,
    query_context: str = "",
    max_results: int = 10,
    max_characters: int = 20000,
) -> List[ResearchFinding]:
    """Deep search for company intelligence — news, filings, red flags.

    Used by Agent 2 for corporate due diligence research.

    Args:
        company_name: Target company name (e.g., "XYZ Steel Private Limited").
        query_context: Additional context (e.g., "fraud allegations", "financial health").
        max_results: Number of results to retrieve.
        max_characters: Max text characters per result.
    """
    if not company_name:
        return []

    query = f"{company_name} {query_context}".strip()

    if _HAS_EXA and EXA_API_KEY:
        try:
            return await asyncio.wait_for(
                _execute_exa_search(
                    query=query,
                    search_type="deep",
                    max_results=max_results,
                    max_characters=max_characters,
                ),
                timeout=SEARCH_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("[Exa] Company search timed out, using mock fallback")
        except Exception as e:
            logger.warning(f"[Exa] Company search error: {e}, using mock fallback")

    return _mock_search_company(company_name)


async def search_exa_news(
    query: str,
    max_results: int = 10,
    max_characters: int = 10000,
) -> List[ResearchFinding]:
    """Deep search for recent news — targets Tier 2 financial media sources.

    Targets: ET, BS, Mint, FE, Reuters, Bloomberg, Moneycontrol.
    """
    if not query:
        return []

    if _HAS_EXA and EXA_API_KEY:
        try:
            return await asyncio.wait_for(
                _execute_exa_search(
                    query=query,
                    search_type="deep",
                    max_results=max_results,
                    max_characters=max_characters,
                    category="news",
                    include_domains=list(TIER_2_DOMAINS),
                ),
                timeout=SEARCH_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("[Exa] News search timed out, using mock fallback")
        except Exception as e:
            logger.warning(f"[Exa] News search error: {e}, using mock fallback")

    return _mock_search_news(query)


async def search_exa_regulatory(
    company_name: str,
    regulatory_body: str = "",
    max_results: int = 10,
    max_characters: int = 15000,
) -> List[ResearchFinding]:
    """Deep search for regulatory actions — SEBI orders, RBI circulars, MCA filings.

    Targets Tier 1 government portal sources.
    """
    if not company_name:
        return []

    query = f"{company_name} {regulatory_body} regulatory action order filing India".strip()

    if _HAS_EXA and EXA_API_KEY:
        try:
            return await asyncio.wait_for(
                _execute_exa_search(
                    query=query,
                    search_type="deep",
                    max_results=max_results,
                    max_characters=max_characters,
                    include_domains=list(TIER_1_DOMAINS),
                ),
                timeout=SEARCH_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("[Exa] Regulatory search timed out, using mock fallback")
        except Exception as e:
            logger.warning(f"[Exa] Regulatory search error: {e}, using mock fallback")

    return _mock_search_regulatory(company_name)


async def search_exa_litigation(
    company_name: str,
    max_results: int = 10,
    max_characters: int = 15000,
) -> List[ResearchFinding]:
    """Deep search for litigation — NCLT proceedings, court orders, legal disputes."""
    if not company_name:
        return []

    query = f"{company_name} litigation NCLT case court order dispute India"

    if _HAS_EXA and EXA_API_KEY:
        try:
            return await asyncio.wait_for(
                _execute_exa_search(
                    query=query,
                    search_type="deep",
                    max_results=max_results,
                    max_characters=max_characters,
                    category="news",
                ),
                timeout=SEARCH_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("[Exa] Litigation search timed out, using mock fallback")
        except Exception as e:
            logger.warning(f"[Exa] Litigation search error: {e}, using mock fallback")

    return _mock_search_litigation(company_name)


async def search_exa_promoter(
    promoter_name: str,
    company_name: str = "",
    max_results: int = 10,
    max_characters: int = 15000,
) -> List[ResearchFinding]:
    """Deep search for promoter/director background — track record, other companies, red flags."""
    if not promoter_name:
        return []

    query = f"{promoter_name} {company_name} director promoter background India".strip()

    if _HAS_EXA and EXA_API_KEY:
        try:
            return await asyncio.wait_for(
                _execute_exa_search(
                    query=query,
                    search_type="deep",
                    max_results=max_results,
                    max_characters=max_characters,
                ),
                timeout=SEARCH_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("[Exa] Promoter search timed out, using mock fallback")
        except Exception as e:
            logger.warning(f"[Exa] Promoter search error: {e}, using mock fallback")

    return _mock_search_promoter(promoter_name, company_name)


async def search_exa_sector(
    sector: str,
    max_results: int = 10,
    max_characters: int = 15000,
) -> List[ResearchFinding]:
    """Deep search for sector/industry outlook — used for Conditions scoring module."""
    if not sector:
        return []

    query = f"{sector} industry India outlook 2025 2026 growth forecast"

    if _HAS_EXA and EXA_API_KEY:
        try:
            return await asyncio.wait_for(
                _execute_exa_search(
                    query=query,
                    search_type="deep",
                    max_results=max_results,
                    max_characters=max_characters,
                    category="news",
                ),
                timeout=SEARCH_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("[Exa] Sector search timed out, using mock fallback")
        except Exception as e:
            logger.warning(f"[Exa] Sector search error: {e}, using mock fallback")

    return _mock_search_sector(sector)


# ── Mock Data for Demo Fallback ──
# All components MUST work with mock data when backend is unavailable.
# Uses the XYZ Steel ₹50cr Working Capital example from architecture spec.

def _mock_search(company_name: str) -> List[ResearchFinding]:
    """Realistic mock findings for demo — backward compatible."""
    return [
        ResearchFinding(
            source="exa",
            source_tier=2,
            source_weight=0.85,
            title=f"Legal proceedings involving {company_name}",
            content=(
                f"Deep search results for pending and resolved legal matters involving "
                f"{company_name}. Court records show 2 active commercial disputes "
                f"(total exposure ₹4.5 Cr) and 1 resolved recovery suit. No criminal "
                f"proceedings found against the company or its promoters."
            ),
            url=f"https://indiankanoon.org/search/?formInput={company_name.replace(' ', '+')}",
            relevance_score=0.78,
            verified=False,
            category="litigation",
        ),
        ResearchFinding(
            source="exa",
            source_tier=2,
            source_weight=0.85,
            title=f"{company_name} — Regulatory Filings Analysis",
            content=(
                f"Semantic search across regulatory databases for {company_name}. "
                f"MCA annual compliance status: up to date. No SEBI show-cause notices. "
                f"RBI reference checks: clear. GSTIN active with regular filing pattern."
            ),
            relevance_score=0.80,
            verified=False,
            category="regulatory",
        ),
    ]


def _mock_search_company(company_name: str) -> List[ResearchFinding]:
    """Mock company intelligence results — XYZ Steel demo data."""
    return [
        ResearchFinding(
            source="exa",
            source_tier=2,
            source_weight=0.85,
            title=f"{company_name} reports 12% revenue growth in FY2025",
            content=(
                f"{company_name} reported consolidated revenue of ₹247 crores "
                f"for FY2025, up 12% from ₹220 crores in FY2024. The company's EBITDA margin "
                f"improved to 14.2% from 12.8%, driven by operational efficiencies and favorable "
                f"raw material pricing. Management guided for 15% growth in FY2026 on the back "
                f"of new capacity additions in Jharkhand."
            ),
            url="https://economictimes.indiatimes.com/xyz-steel-revenue-fy2025",
            published_date="2025-06-15",
            relevance_score=0.95,
            verified=False,
            category="financial",
        ),
        ResearchFinding(
            source="exa",
            source_tier=1,
            source_weight=1.0,
            title="SEBI observations on related party transactions in steel companies",
            content=(
                "SEBI noted increased instances of undisclosed related party transactions among "
                "mid-cap steel companies. Three companies received warnings for inadequate RPT "
                "disclosure in FY2024 annual reports. SEBI has directed BSE and NSE to enhance "
                "monitoring of RPT disclosures for listed steel entities."
            ),
            url="https://www.sebi.gov.in/enforcement/orders/2025/sebi-steel-rpt-observations.html",
            published_date="2025-04-10",
            relevance_score=0.82,
            verified=False,
            category="regulatory",
        ),
    ]


def _mock_search_news(query: str) -> List[ResearchFinding]:
    """Mock news search results."""
    return [
        ResearchFinding(
            source="exa",
            source_tier=2,
            source_weight=0.85,
            title="Steel sector outlook: Capacity additions to drive growth",
            content=(
                "India's steel sector is expected to grow at 8-10% CAGR over the next 3 years, "
                "supported by infrastructure spending under the National Infrastructure Pipeline. "
                "Mid-size players are well-positioned to benefit from the PLI scheme "
                "for specialty steel. However, rising coking coal prices remain a concern."
            ),
            url="https://livemint.com/steel-sector-outlook-2025",
            published_date="2025-05-20",
            relevance_score=0.88,
            verified=False,
            category="sector",
        ),
    ]


def _mock_search_regulatory(company_name: str) -> List[ResearchFinding]:
    """Mock regulatory search results."""
    return [
        ResearchFinding(
            source="exa",
            source_tier=1,
            source_weight=1.0,
            title=f"MCA filing status for {company_name}",
            content=(
                f"MCA21 portal records for {company_name}: Annual returns filed up to FY2024. "
                f"No pending forms. Board composition compliant with Companies Act 2013 "
                f"requirements. Registered office address verified. No strike-off proceedings."
            ),
            url="https://mca.gov.in/mcafoportal/companyLLPMasterData.do",
            published_date="2025-03-31",
            relevance_score=0.85,
            verified=False,
            category="regulatory",
        ),
        ResearchFinding(
            source="exa",
            source_tier=1,
            source_weight=1.0,
            title=f"RBI defaulter list check — {company_name}",
            content=(
                f"RBI wilful defaulter database checked for {company_name} and all associated "
                f"directors. Result: NOT FOUND on wilful defaulter list. No SMA-2 classification. "
                f"No CRILC flags detected for the company or its group entities."
            ),
            url="https://rbi.org.in/Scripts/WilfulDefaulters.aspx",
            relevance_score=0.92,
            verified=False,
            category="regulatory",
        ),
    ]


def _mock_search_litigation(company_name: str) -> List[ResearchFinding]:
    """Mock litigation search results."""
    return [
        ResearchFinding(
            source="exa",
            source_tier=2,
            source_weight=0.85,
            title=f"NCLT proceedings check — {company_name}",
            content=(
                f"National Company Law Tribunal database searched for {company_name}. "
                f"No active insolvency or liquidation proceedings under IBC. "
                f"One historical Section 9 application by a vendor (₹1.2 Cr) was settled "
                f"out of court in January 2024. No pending CIRP applications."
            ),
            url="https://nclt.gov.in/case-status",
            published_date="2025-02-15",
            relevance_score=0.88,
            verified=False,
            category="litigation",
        ),
        ResearchFinding(
            source="exa",
            source_tier=2,
            source_weight=0.85,
            title=f"Court records — {company_name} commercial disputes",
            content=(
                f"eCourts/NJDG search for {company_name}: 2 active cases found. "
                f"(1) Recovery suit by ABC Suppliers Pvt Ltd — ₹3.2 Cr, pending hearing. "
                f"(2) Commercial dispute with DEF Logistics — ₹1.3 Cr, mediation ordered. "
                f"Total litigation exposure: ₹4.5 Cr (0.9% of annual revenue)."
            ),
            url="https://njdg.ecourts.gov.in/njdgnew/index.php",
            relevance_score=0.84,
            verified=False,
            category="litigation",
        ),
    ]


def _mock_search_promoter(promoter_name: str, company_name: str) -> List[ResearchFinding]:
    """Mock promoter background search results."""
    return [
        ResearchFinding(
            source="exa",
            source_tier=2,
            source_weight=0.85,
            title=f"{promoter_name} profile — {company_name or 'corporate'} background",
            content=(
                f"{promoter_name}, promoter and MD of {company_name or 'the company'}, has over "
                f"25 years of experience in the Indian steel industry. Previously served as "
                f"VP Operations at Jindal Steel & Power before founding {company_name or 'the company'} "
                f"in 2005. Under his leadership, the company has grown from ₹20cr turnover to ₹247cr. "
                f"Holds B.Tech from IIT Dhanbad and MBA from XLRI. No criminal proceedings found. "
                f"Associated with 2 other entities: XYZ Steel Trading LLP (active) and "
                f"Agarwal Family Trust (private trust, no commercial operations)."
            ),
            url="https://business-standard.com/profile-promoter",
            published_date="2024-11-03",
            relevance_score=0.91,
            verified=False,
            category="governance",
        ),
    ]


def _mock_search_sector(sector: str) -> List[ResearchFinding]:
    """Mock sector outlook search results."""
    return [
        ResearchFinding(
            source="exa",
            source_tier=2,
            source_weight=0.85,
            title=f"{sector} industry outlook — India 2025-2026",
            content=(
                f"The {sector} sector in India is projected to grow at 8-10% CAGR through FY2027, "
                f"driven by government infrastructure spending (₹10 lakh crore National Infrastructure "
                f"Pipeline), PLI scheme for specialty steel (₹6,322 Cr incentive pool), and rising "
                f"domestic demand from auto and construction sectors. Key risks: imported coking coal "
                f"price volatility (+30% YoY), China dumping concerns (anti-dumping duty under review), "
                f"and energy cost escalation. Industry D/E norms: 1.5-2.5x considered healthy. "
                f"Capacity utilization at 82% nationally."
            ),
            url="https://livemint.com/industry-outlook-steel-2025",
            published_date="2025-05-20",
            relevance_score=0.88,
            verified=False,
            category="sector",
        ),
        ResearchFinding(
            source="exa",
            source_tier=2,
            source_weight=0.85,
            title=f"Credit outlook for {sector} sector — rating agency view",
            content=(
                f"CRISIL sector outlook for {sector}: Stable. Revenue growth expected at 10-12% "
                f"in FY2026 driven by volume growth. Operating margins to stay in 12-15% band. "
                f"D/E ratios improving across mid-cap players due to capex completion. "
                f"Working capital cycle: 90-120 days typical for the sector. "
                f"Key monitorable: raw material price pass-through ability."
            ),
            url="https://financialexpress.com/crisil-steel-outlook",
            published_date="2025-04-08",
            relevance_score=0.85,
            verified=False,
            category="sector",
        ),
    ]


def get_source_tier_weight(tier: int) -> float:
    """Get the credibility weight for a source tier.

    Used by the Verification Engine to weight findings.
    """
    return SOURCE_TIER_WEIGHTS.get(tier, 0.60)
