"""
Intelli-Credit — Research API Wrappers + Decision Store + Bug Fixes Test Suite

Tests:
  1. Tavily search wrapper (mock fallback)
  2. Exa search wrapper (mock fallback)
  3. SerpAPI search wrapper (mock fallback)
  4. Research node integration (all 5 tracks wired)
  5. Decision Store PostgreSQL wiring
  6. ITR key fix (consolidator reads "turnover" not "total_income")

Five-persona coverage:
  🏦 Credit Domain Expert — source tier correctness, content quality
  🔒 Security Architect — API key handling, injection safety
  ⚙️ Systems Engineer — timeout/fallback, parallel execution
  🧪 QA Engineer — empty inputs, edge cases
  🎯 Hackathon Judge — demo quality, storytelling
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASSED = 0
FAILED = 0
RESULTS: list = []


def report(name: str, ok: bool, detail: str = ""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        RESULTS.append(("PASS", name))
    else:
        FAILED += 1
        RESULTS.append(("FAIL", name, detail))
        print(f"  FAIL: {name}" + (f" — {detail}" if detail else ""))


def _run(coro):
    """Run async coroutine in test context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ──────────────────────────────────────────────────────────
# Section 1: Tavily Search Wrapper
# ──────────────────────────────────────────────────────────

def test_tavily_import():
    """Tavily wrapper imports without error."""
    try:
        from backend.agents.research.tavily_search import search_tavily
        report("tavily import", True)
    except Exception as e:
        report("tavily import", False, str(e))


def test_tavily_mock_returns_findings():
    """Tavily mock fallback returns findings. ⚙️"""
    from backend.agents.research.tavily_search import search_tavily
    results = _run(search_tavily("XYZ Steel Pvt Ltd", sector="Steel"))
    report("tavily mock findings", isinstance(results, list) and len(results) >= 2)


def test_tavily_tier_2():
    """Tavily findings are tier 2, weight 0.85. 🏦"""
    from backend.agents.research.tavily_search import search_tavily
    results = _run(search_tavily("XYZ Steel Pvt Ltd"))
    ok = all(f.source_tier == 2 and f.source_weight == 0.85 for f in results)
    report("tavily tier 2", ok)


def test_tavily_source_name():
    """Tavily findings have source='tavily'."""
    from backend.agents.research.tavily_search import search_tavily
    results = _run(search_tavily("Test Corp"))
    report("tavily source name", all(f.source == "tavily" for f in results))


def test_tavily_empty_company():
    """Empty company name returns empty list. 🧪"""
    from backend.agents.research.tavily_search import search_tavily
    results = _run(search_tavily(""))
    report("tavily empty company", results == [])


def test_tavily_categories():
    """Mock findings have financial/governance categories. 🎯"""
    from backend.agents.research.tavily_search import search_tavily
    results = _run(search_tavily("XYZ Steel Pvt Ltd", sector="Steel"))
    cats = {f.category for f in results}
    report("tavily categories", "financial" in cats or "governance" in cats)


def test_tavily_content_quality():
    """Mock content is narrative, not generic stub. 🎯"""
    from backend.agents.research.tavily_search import search_tavily
    results = _run(search_tavily("XYZ Steel Pvt Ltd", sector="Steel"))
    long_content = all(len(f.content) > 50 for f in results)
    has_rupee = any("₹" in f.content for f in results)
    report("tavily content quality", long_content and has_rupee)


# ──────────────────────────────────────────────────────────
# Section 2: Exa Search Wrapper
# ──────────────────────────────────────────────────────────

def test_exa_import():
    """Exa wrapper imports without error."""
    try:
        from backend.agents.research.exa_search import search_exa
        report("exa import", True)
    except Exception as e:
        report("exa import", False, str(e))


def test_exa_mock_returns_findings():
    """Exa mock fallback returns findings. ⚙️"""
    from backend.agents.research.exa_search import search_exa
    results = _run(search_exa("XYZ Steel Pvt Ltd"))
    report("exa mock findings", isinstance(results, list) and len(results) >= 2)


def test_exa_tier_2():
    """Exa findings are tier 2, weight 0.85. 🏦"""
    from backend.agents.research.exa_search import search_exa
    results = _run(search_exa("Test Corp"))
    ok = all(f.source_tier == 2 and f.source_weight == 0.85 for f in results)
    report("exa tier 2", ok)


def test_exa_source_name():
    """Exa findings have source='exa'."""
    from backend.agents.research.exa_search import search_exa
    results = _run(search_exa("Test Corp"))
    report("exa source name", all(f.source == "exa" for f in results))


def test_exa_empty_company():
    """Empty company name returns empty list. 🧪"""
    from backend.agents.research.exa_search import search_exa
    results = _run(search_exa(""))
    report("exa empty company", results == [])


def test_exa_litigation_category():
    """Exa mock includes litigation/regulatory categories. 🏦"""
    from backend.agents.research.exa_search import search_exa
    results = _run(search_exa("XYZ Steel Pvt Ltd"))
    cats = {f.category for f in results}
    report("exa categories", "litigation" in cats or "regulatory" in cats)


# ──────────────────────────────────────────────────────────
# Section 3: SerpAPI Search Wrapper
# ──────────────────────────────────────────────────────────

def test_serpapi_import():
    """SerpAPI wrapper imports without error."""
    try:
        from backend.agents.research.serpapi_search import search_serpapi
        report("serpapi import", True)
    except Exception as e:
        report("serpapi import", False, str(e))


def test_serpapi_mock_returns_findings():
    """SerpAPI mock fallback returns findings. ⚙️"""
    from backend.agents.research.serpapi_search import search_serpapi
    results = _run(search_serpapi("XYZ Steel Pvt Ltd"))
    report("serpapi mock findings", isinstance(results, list) and len(results) >= 2)


def test_serpapi_tier_3():
    """SerpAPI findings are tier 3, weight 0.60. 🏦"""
    from backend.agents.research.serpapi_search import search_serpapi
    results = _run(search_serpapi("Test Corp"))
    ok = all(f.source_tier == 3 and f.source_weight == 0.60 for f in results)
    report("serpapi tier 3", ok)


def test_serpapi_source_name():
    """SerpAPI findings have source='serpapi'."""
    from backend.agents.research.serpapi_search import search_serpapi
    results = _run(search_serpapi("Test Corp"))
    report("serpapi source name", all(f.source == "serpapi" for f in results))


def test_serpapi_empty_company():
    """Empty company name returns empty list. 🧪"""
    from backend.agents.research.serpapi_search import search_serpapi
    results = _run(search_serpapi(""))
    report("serpapi empty company", results == [])


def test_serpapi_has_dates():
    """Mock findings include publish dates. 🎯"""
    from backend.agents.research.serpapi_search import search_serpapi
    results = _run(search_serpapi("XYZ Steel Pvt Ltd"))
    has_dates = any(f.published_date for f in results)
    report("serpapi dates", has_dates)


# ──────────────────────────────────────────────────────────
# Section 4: Research Node Integration (⚙️)
# ──────────────────────────────────────────────────────────

def test_research_node_imports_all():
    """Research node imports all 3 API wrappers + 5 scrapers."""
    from backend.graph.nodes.research_node import (
        _run_tavily_track, _run_exa_track, _run_serpapi_track,
        _run_govt_scraper_track, _run_rating_track,
    )
    report("research node all tracks", True)


def test_all_tracks_parallel():
    """All 5 research tracks run concurrently. ⚙️"""
    from backend.graph.nodes.research_node import (
        _run_tavily_track, _run_exa_track, _run_serpapi_track,
        _run_govt_scraper_track, _run_rating_track,
    )

    async def run_all():
        return await asyncio.gather(
            _run_tavily_track("Test Corp", "Steel"),
            _run_exa_track("Test Corp"),
            _run_serpapi_track("Test Corp"),
            _run_govt_scraper_track("Test Corp"),
            _run_rating_track("Test Corp"),
            return_exceptions=True,
        )

    results = _run(run_all())
    all_lists = all(isinstance(r, list) for r in results)
    total = sum(len(r) for r in results if isinstance(r, list))
    report("all tracks parallel", all_lists and total >= 10)


def test_source_diversity():
    """Combined findings cover all source types. 🏦"""
    from backend.graph.nodes.research_node import (
        _run_tavily_track, _run_exa_track, _run_serpapi_track,
        _run_govt_scraper_track, _run_rating_track,
    )

    async def gather_all():
        results = await asyncio.gather(
            _run_tavily_track("Test Corp", "Steel"),
            _run_exa_track("Test Corp"),
            _run_serpapi_track("Test Corp"),
            _run_govt_scraper_track("Test Corp"),
            _run_rating_track("Test Corp"),
        )
        return [f for group in results for f in group]

    findings = _run(gather_all())
    sources = {f.source for f in findings}
    expected = {"tavily", "exa", "serpapi", "mca21", "sebi", "rbi", "njdg", "gstin"}
    missing = expected - sources
    report("source diversity", len(missing) == 0, f"missing: {missing}")


def test_tier_distribution():
    """Combined findings include tier 1, 2, and 3 sources. 🏦"""
    from backend.graph.nodes.research_node import (
        _run_tavily_track, _run_exa_track, _run_serpapi_track,
        _run_govt_scraper_track,
    )

    async def gather_all():
        results = await asyncio.gather(
            _run_tavily_track("Test Corp", "Steel"),
            _run_exa_track("Test Corp"),
            _run_serpapi_track("Test Corp"),
            _run_govt_scraper_track("Test Corp"),
        )
        return [f for group in results for f in group]

    findings = _run(gather_all())
    tiers = {f.source_tier for f in findings}
    report("tier distribution", {1, 2, 3}.issubset(tiers))


# ──────────────────────────────────────────────────────────
# Section 5: Decision Store Persistence
# ──────────────────────────────────────────────────────────

def test_decision_store_imports():
    """Decision store imports PostgreSQL client."""
    from backend.graph.nodes.decision_store_node import decision_store_node, decision_records
    from backend.storage.postgres_client import DatabaseClient
    report("decision store imports", True)


def test_decision_store_in_memory_fallback():
    """Decision store still has in-memory dict as fallback. ⚙️"""
    from backend.graph.nodes.decision_store_node import decision_records
    ok = isinstance(decision_records, dict)
    report("decision store in-memory", ok)


def test_decision_store_build_record():
    """_build_decision_record produces a complete record. 🧪"""
    from backend.graph.nodes.decision_store_node import _build_decision_record
    from backend.graph.state import CreditAppraisalState, CompanyInfo

    state = CreditAppraisalState(
        session_id="test-ds-001",
        company=CompanyInfo(
            name="XYZ Steel Pvt Ltd",
            sector="Steel",
            loan_type="Working Capital",
            loan_amount="₹50 Cr",
            loan_amount_numeric=50.0,
        ),
        score=477,
    )
    record = _build_decision_record(state)
    checks = [
        record["session_id"] == "test-ds-001",
        record["company_name"] == "XYZ Steel Pvt Ltd",
        record["score"] == 477,
        record["sector"] == "Steel",
        "completed_at" in record,
    ]
    report("build decision record", all(checks))


def test_decision_store_node_writes():
    """decision_store_node writes to in-memory dict. ⚙️"""
    from backend.graph.nodes.decision_store_node import decision_store_node, decision_records
    from backend.graph.state import CreditAppraisalState, CompanyInfo
    from backend.models.schemas import ScoreBand, AssessmentOutcome

    state = CreditAppraisalState(
        session_id="test-ds-002",
        company=CompanyInfo(
            name="Test Corp",
            sector="Manufacturing",
            loan_type="Term Loan",
            loan_amount="₹10 Cr",
            loan_amount_numeric=10.0,
        ),
        score=650,
        score_band=ScoreBand.GOOD,
        outcome=AssessmentOutcome.CONDITIONAL,
    )
    result = _run(decision_store_node(state))
    ok = "test-ds-002" in decision_records
    report("decision store node writes", ok)


# ──────────────────────────────────────────────────────────
# Section 6: ITR Key Bug Fix
# ──────────────────────────────────────────────────────────

def test_consolidator_itr_key():
    """Consolidator reads 'turnover' key from ITR data (not 'total_income'). 🏦"""
    import re
    with open(os.path.join(os.path.dirname(__file__), "..", "backend", "graph", "nodes", "consolidator_node.py"), encoding="utf-8") as f:
        content = f.read()
    # Should use "turnover", not "total_income"
    uses_turnover = 'itr_rev.get("turnover")' in content
    no_total_income = 'itr_rev.get("total_income")' not in content
    report("ITR key fix: turnover", uses_turnover and no_total_income,
           "consolidator should use 'turnover' key from W4")


def test_itr_worker_key_consistency():
    """W4 ITR worker output contains 'turnover' key. 🧪"""
    from backend.workers.w4_itr import ITRWorker
    worker = ITRWorker(session_id="test-itr-001", file_path="/tmp/dummy.pdf")
    extracted, pages, conf = _run(worker._extract())
    itr_rev = extracted.get("revenue_from_itr", {})
    report("W4 turnover key exists", "turnover" in itr_rev,
           f"revenue_from_itr keys: {list(itr_rev.keys())}")


def test_cross_verify_uses_all_4_sources():
    """Consolidator cross-verifies using AR, Bank, GST, and ITR. 🏦"""
    import re
    with open(os.path.join(os.path.dirname(__file__), "..", "backend", "graph", "nodes", "consolidator_node.py"), encoding="utf-8") as f:
        content = f.read()
    has_ar = "revenue" in content and "W1" in content
    has_bank = "revenue_from_bank" in content
    has_gst = "revenue_from_gst" in content
    has_itr = "revenue_from_itr" in content
    report("4-way cross-verify",
           has_ar and has_bank and has_gst and has_itr)


# ──────────────────────────────────────────────────────────
# Section 7: Security (🔒)
# ──────────────────────────────────────────────────────────

def test_api_key_not_in_findings():
    """API keys never leak into finding content. 🔒"""
    from backend.agents.research.tavily_search import search_tavily, TAVILY_API_KEY
    from backend.agents.research.exa_search import search_exa, EXA_API_KEY
    from backend.agents.research.serpapi_search import search_serpapi, SERPAPI_API_KEY

    async def gather_all():
        return await asyncio.gather(
            search_tavily("Test Corp"),
            search_exa("Test Corp"),
            search_serpapi("Test Corp"),
        )

    all_results = _run(gather_all())
    findings = [f for group in all_results for f in group]
    # Check no API keys in content (they're empty strings, but test the pattern)
    for f in findings:
        combined = f.content + (f.url or "") + f.title
        if TAVILY_API_KEY and TAVILY_API_KEY in combined:
            report("api key not in findings", False, "Tavily key leaked")
            return
        if EXA_API_KEY and EXA_API_KEY in combined:
            report("api key not in findings", False, "Exa key leaked")
            return
        if SERPAPI_API_KEY and SERPAPI_API_KEY in combined:
            report("api key not in findings", False, "SerpAPI key leaked")
            return
    report("api key not in findings", True)


def test_injection_in_search():
    """SQL injection in company name doesn't crash search wrappers. 🔒"""
    from backend.agents.research.tavily_search import search_tavily
    malicious = "'; DROP TABLE companies; --"
    results = _run(search_tavily(malicious))
    report("injection safe search", isinstance(results, list))


# ──────────────────────────────────────────────────────────
# Section 8: Demo Quality (🎯)
# ──────────────────────────────────────────────────────────

def test_demo_all_findings_have_content():
    """All mock findings from all APIs have substantial content. 🎯"""
    from backend.agents.research.tavily_search import search_tavily
    from backend.agents.research.exa_search import search_exa
    from backend.agents.research.serpapi_search import search_serpapi

    async def gather_all():
        return await asyncio.gather(
            search_tavily("XYZ Steel Pvt Ltd", sector="Steel"),
            search_exa("XYZ Steel Pvt Ltd"),
            search_serpapi("XYZ Steel Pvt Ltd"),
        )

    all_results = _run(gather_all())
    findings = [f for group in all_results for f in group]
    all_good = all(
        f.title and len(f.content) > 50 and f.relevance_score > 0
        for f in findings
    )
    report("demo content quality", all_good)


def test_demo_verification_engine():
    """Verification engine correctly filters tier 2 vs tier 3. 🎯"""
    from backend.graph.nodes.research_node import _verify_findings
    from backend.agents.research.tavily_search import search_tavily
    from backend.agents.research.serpapi_search import search_serpapi

    async def gather():
        return await asyncio.gather(
            search_tavily("Test Corp"),
            search_serpapi("Test Corp"),
        )

    t_results, s_results = _run(gather())
    all_findings = t_results + s_results
    verified = _verify_findings(all_findings)
    # Tavily (tier 2, relevance>0.7) should be verified, some serpapi may not
    verified_sources = {f.source for f in verified if f.verified}
    report("demo verification engine", "tavily" in verified_sources)


# ──────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────

def test_zz_summary():
    """Final summary of research & persistence tests."""
    print(f"\n  Research + Persistence Tests: {PASSED} passed, {FAILED} failed")
    if FAILED > 0:
        print("  Failed tests:")
        for entry in RESULTS:
            if entry[0] == "FAIL":
                detail = f" — {entry[2]}" if len(entry) > 2 and entry[2] else ""
                print(f"    ✗ {entry[1]}{detail}")
    assert FAILED == 0, f"{FAILED} tests failed"


# ──────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in test_funcs:
        try:
            fn()
        except AssertionError:
            pass
        except Exception as e:
            report(fn.__name__, False, str(e))
    print(f"\n{'='*60}")
    print(f"Research + Persistence Tests: {PASSED} passed, {FAILED} failed")
    print(f"{'='*60}")
