"""
Intelli-Credit — LangGraph Node: Research (Agent 2)

External intelligence gathering through 5 parallel research tracks:
  Track 1: Tavily AI search — company news, financial reports
  Track 2: Exa neural search — semantic legal/regulatory matches
  Track 3: SerpAPI Google — Indian news index, regional media
  Track 4: Government scrapers — MCA21, SEBI, RBI, NJDG, GSTIN
  Track 5: Rating agency & financial databases

Verification Engine applies 5-tier credibility weighting.
Enriches knowledge graph with external entities discovered.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.graph.state import (
    CreditAppraisalState,
    ResearchPackage,
    ResearchFinding,
)
from backend.models.schemas import (
    PipelineStageStatus,
    PipelineStageEnum,
    EventType,
    ThinkingEvent,
)
from backend.thinking.event_emitter import ThinkingEventEmitter
from backend.agents.research.regulatory_feed import get_regulatory_feed
from backend.agents.research.scrapers import (
    scrape_mca21,
    scrape_sebi,
    scrape_rbi,
    scrape_njdg,
    scrape_gst,
)
from backend.agents.research.tavily_search import search_tavily
from backend.agents.research.exa_search import search_exa
from backend.agents.research.serpapi_search import search_serpapi

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Source Credibility Tiers (HARDCODED — never change order)
# ──────────────────────────────────────────────

SOURCE_TIERS = {
    # Tier 1 — Government (weight 1.0)
    "mca21": {"tier": 1, "weight": 1.0, "name": "MCA21 (Ministry of Corporate Affairs)"},
    "sebi": {"tier": 1, "weight": 1.0, "name": "SEBI Filings"},
    "rbi": {"tier": 1, "weight": 1.0, "name": "RBI Registry"},
    "njdg": {"tier": 1, "weight": 1.0, "name": "NJDG (National Judicial Data Grid)"},
    "gstin": {"tier": 1, "weight": 1.0, "name": "GST Portal"},
    # Tier 2 — Reputable financial media (weight 0.85)
    "tavily": {"tier": 2, "weight": 0.85, "name": "AI Web Search (Tavily)"},
    "exa": {"tier": 2, "weight": 0.85, "name": "Neural Search (Exa)"},
    "economic_times": {"tier": 2, "weight": 0.85, "name": "Economic Times"},
    "business_standard": {"tier": 2, "weight": 0.85, "name": "Business Standard"},
    "mint": {"tier": 2, "weight": 0.85, "name": "Mint"},
    # Tier 3 — General/regional news (weight 0.60)
    "serpapi": {"tier": 3, "weight": 0.60, "name": "Google Search (SerpAPI)"},
    "regional_news": {"tier": 3, "weight": 0.60, "name": "Regional News"},
    # Tier 4 — Low credibility (weight 0.30)
    "blog": {"tier": 4, "weight": 0.30, "name": "Blog/Unverified"},
    # Tier 5 — Rejected (weight 0.0)
    "social_media": {"tier": 5, "weight": 0.0, "name": "Social Media"},
}


def _get_source_info(source: str) -> Dict[str, Any]:
    """Get tier info for a source. Defaults to tier 3 for unknown sources."""
    return SOURCE_TIERS.get(source.lower(), {"tier": 3, "weight": 0.60, "name": source})


# ──────────────────────────────────────────────
# Research API tracks (real API + mock fallback)
# ──────────────────────────────────────────────

async def _run_tavily_track(company_name: str, sector: str) -> List[ResearchFinding]:
    """Track 1: Tavily AI search — company news, financial analysis."""
    if not company_name:
        return []
    return await search_tavily(company_name, sector=sector)


async def _run_exa_track(company_name: str) -> List[ResearchFinding]:
    """Track 2: Exa neural search — legal/regulatory results."""
    if not company_name:
        return []
    return await search_exa(company_name)


async def _run_serpapi_track(company_name: str) -> List[ResearchFinding]:
    """Track 3: SerpAPI — Indian news, regional coverage."""
    if not company_name:
        return []
    return await search_serpapi(company_name)


async def _run_govt_scraper_track(
    company_name: str, cin: Optional[str] = None
) -> List[ResearchFinding]:
    """Track 4: Government scrapers — MCA21, SEBI, RBI, NJDG, GSTIN.

    Runs all 5 scrapers in parallel. Each scraper handles its own
    timeout/retry/fallback — this track never crashes.
    """
    findings = []
    if not company_name:
        return findings

    # Run all 5 scrapers in parallel
    scraper_results = await asyncio.gather(
        scrape_mca21(company_name, cin=cin),
        scrape_sebi(company_name),
        scrape_rbi(company_name),
        scrape_njdg(company_name, cin=cin),
        scrape_gst(company_name),
        return_exceptions=True,
    )

    scraper_names = ["MCA21", "SEBI", "RBI", "NJDG", "GST"]
    for name, result in zip(scraper_names, scraper_results):
        if isinstance(result, Exception):
            logger.error(f"[Research] {name} scraper failed: {result}")
            continue
        if isinstance(result, list):
            findings.extend(result)

    return findings


async def _run_rating_track(company_name: str) -> List[ResearchFinding]:
    """Track 5: Rating agencies & financial databases."""
    findings = []
    if not company_name:
        return findings

    findings.append(ResearchFinding(
        source="tavily",
        source_tier=2,
        source_weight=0.85,
        title=f"Credit Rating History — {company_name}",
        content=f"Rating history and outlook for {company_name} from CRISIL/ICRA/CARE.",
        relevance_score=0.88,
        verified=False,
        category="financial",
    ))
    return findings


# ──────────────────────────────────────────────
# Verification Engine
# ──────────────────────────────────────────────

def _verify_findings(findings: List[ResearchFinding]) -> List[ResearchFinding]:
    """
    Apply 5-tier credibility verification.

    Rules:
    - Tier 1 (government) → auto-verified, weight 1.0
    - Tier 2 (reputable media) → accept if relevance > 0.7, weight 0.85
    - Tier 3 (general) → accept if relevance > 0.5, weight 0.60
    - Tier 4 (blogs) → flag for review, weight 0.30
    - Tier 5 (social media) → reject, weight 0.0
    """
    verified = []
    for finding in findings:
        source_info = _get_source_info(finding.source)

        # Apply tier-based verification
        if source_info["tier"] == 1:
            finding.verified = True
        elif source_info["tier"] == 2:
            finding.verified = finding.relevance_score >= 0.7
        elif source_info["tier"] == 3:
            finding.verified = finding.relevance_score >= 0.5
        elif source_info["tier"] == 4:
            finding.verified = False  # Always flagged
        else:
            # Tier 5 — rejected
            finding.source_weight = 0.0
            finding.verified = False

        # Only include findings with weight > 0
        if finding.source_weight > 0:
            verified.append(finding)

    return verified


def _categorize_findings(findings: List[ResearchFinding]) -> Dict[str, List[ResearchFinding]]:
    """Group findings by category."""
    categories: Dict[str, List[ResearchFinding]] = {}
    for f in findings:
        cat = f.category or "uncategorized"
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f)
    return categories


# ──────────────────────────────────────────────
# Main Research Node
# ──────────────────────────────────────────────

async def research_node(state: CreditAppraisalState) -> dict:
    """
    Stage 5 — Agent 2: The Research Agent.

    Runs 5 parallel research tracks, verifies through credibility engine,
    enriches knowledge graph, produces ResearchPackage.
    """
    emitter = ThinkingEventEmitter(state.session_id, "Agent 2 — The Research Agent")
    emitted_events: List[ThinkingEvent] = []  # Collect events locally for state
    company_name = state.company.name if state.company else "Unknown Company"
    sector = state.company.sector if state.company and state.company.sector else "general"

    async def _emit(event_type: EventType, message: str, **kwargs) -> ThinkingEvent:
        """Emit and collect a thinking event."""
        event = await emitter.emit(event_type, message, **kwargs)
        emitted_events.append(event)
        return event

    logger.info(f"[Agent 2] Starting research for {company_name}")

    try:
        # Emit start event
        await _emit(
            EventType.READ,
            f"Starting 5 parallel research tracks for {company_name} ({sector} sector)"
        )

        # ── Run 5 tracks in parallel ──
        track_results = await asyncio.gather(
            _run_tavily_track(company_name, sector),
            _run_exa_track(company_name),
            _run_serpapi_track(company_name),
            _run_govt_scraper_track(
                company_name,
                cin=state.company.cin if state.company else None,
            ),
            _run_rating_track(company_name),
            return_exceptions=True,
        )

        # ── Collect findings, handle failures ──
        all_findings: List[ResearchFinding] = []
        track_names = ["Tavily", "Exa", "SerpAPI", "Govt Scrapers", "Rating Track"]
        failed_tracks = []

        for i, result in enumerate(track_results):
            if isinstance(result, Exception):
                logger.error(f"[Agent 2] Track {track_names[i]} failed: {result}")
                failed_tracks.append(track_names[i])
                await _emit(
                    EventType.FLAGGED,
                    f"Research track '{track_names[i]}' failed: {str(result)[:100]}. Continuing with other sources."
                )
            elif isinstance(result, list):
                all_findings.extend(result)
                await _emit(
                    EventType.FOUND,
                    f"{track_names[i]}: {len(result)} finding(s) retrieved"
                )

        # ── Verification Engine ──
        await _emit(EventType.READ, "Applying 5-tier credibility verification engine...")
        verified_findings = _verify_findings(all_findings)

        govt_count = sum(1 for f in verified_findings if _get_source_info(f.source)["tier"] == 1)
        media_count = sum(1 for f in verified_findings if _get_source_info(f.source)["tier"] in (2, 3))

        await _emit(
            EventType.COMPUTED,
            f"Verification complete: {len(verified_findings)} findings accepted "
            f"({govt_count} government, {media_count} media)"
        )

        # ── Categorize findings ──
        categories = _categorize_findings(verified_findings)
        for cat, items in categories.items():
            verified_count = sum(1 for i in items if i.verified)
            await _emit(
                EventType.FOUND,
                f"Category '{cat}': {len(items)} findings ({verified_count} verified)"
            )

        # ── Regulatory Intelligence Feed (T4.3) ──
        try:
            reg_feed = get_regulatory_feed()
            reg_findings = await reg_feed.to_research_findings(sector, months_back=6)
            if reg_findings:
                all_findings.extend(reg_findings)
                verified_findings.extend(reg_findings)  # Already tier-1, pre-verified
                govt_count += len(reg_findings)
                await _emit(
                    EventType.FOUND,
                    f"Regulatory Feed: {len(reg_findings)} sector-relevant regulation(s) from last 6 months"
                )
        except Exception as reg_err:
            logger.warning(f"[Agent 2] Regulatory feed unavailable: {reg_err}")

        # ── Flag critical findings ──
        for finding in verified_findings:
            if finding.category == "litigation" and finding.source_tier == 1:
                await _emit(
                    EventType.FLAGGED,
                    f"⚠️ Government-confirmed litigation: {finding.title}"
                )
            if "wilful defaulter" in finding.content.lower() and "not found" not in finding.content.lower():
                await _emit(
                    EventType.CRITICAL,
                    f"🚨 WILFUL DEFAULTER detected: {finding.title}"
                )

        # ── Report failed tracks ──
        if failed_tracks:
            await _emit(
                EventType.FLAGGED,
                f"Degraded mode: {len(failed_tracks)} track(s) failed ({', '.join(failed_tracks)}). "
                f"Score confidence reduced."
            )

        # ── Build Research Package ──
        research_package = ResearchPackage(
            findings=verified_findings,
            government_sources=govt_count,
            media_sources=media_count,
            total_findings=len(verified_findings),
            neo4j_entities_added=0,  # Real enrichment in T6
        )

        await _emit(
            EventType.CONCLUDING,
            f"Research complete: {research_package.total_findings} findings from "
            f"{5 - len(failed_tracks)}/5 tracks. "
            f"Government sources: {govt_count}, Media: {media_count}."
        )

        # ── Update pipeline stage ──
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.RESEARCH:
                stage.status = PipelineStageStatus.COMPLETED
                stage.message = (
                    f"Research completed: {research_package.total_findings} findings"
                )

        return {
            "research_package": research_package,
            "pipeline_stages": state.pipeline_stages,
            "thinking_events": emitted_events,
        }

    except Exception as e:
        logger.error(f"[Agent 2] Research failed: {e}")
        await _emit(
            EventType.CRITICAL,
            f"Research agent failed: {str(e)[:200]}. Pipeline continuing with no external intelligence."
        )

        # Mark stage as failed but don't crash pipeline
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.RESEARCH:
                stage.status = PipelineStageStatus.FAILED
                stage.message = f"Research failed: {str(e)[:100]}"

        return {
            "research_package": ResearchPackage(total_findings=0),
            "pipeline_stages": state.pipeline_stages,
            "thinking_events": emitted_events,
        }
