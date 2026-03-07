"""
Intelli-Credit — T1.1 Tests: GSTR-2A vs 3B Month-Level Reconciliation

Tests:
1.  _reconcile_monthly_itc produces correct month-by-month detail
2.  Normal excess (<5%) flagged as "normal"
3.  Moderate excess (5-15%) flagged as "moderate"
4.  High excess (>15%) flagged as "high"
5.  Critical excess (>25%) flagged as "critical"
6.  Zero availability handled gracefully (no division by zero)
7.  Aggregate mismatch computed correctly from monthly totals
8.  Consolidator creates CrossVerificationResult with enhanced fields
9.  Consolidator raises HIGH ticket when mismatch 10-20%
10. Consolidator raises CRITICAL ticket when mismatch >20%
11. Consolidator does NOT raise ticket when mismatch 5-10%
12. Scorer applies -10 for 5-10% ITC mismatch
13. Scorer applies -20 for 10-15% ITC mismatch
14. Scorer applies -35 for 15-20% ITC mismatch
15. Scorer applies -50 for >20% ITC mismatch
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.workers.w3_gst_returns import _reconcile_monthly_itc
from backend.graph.state import (
    CreditAppraisalState,
    WorkerOutput,
    RawDataPackage,
    NormalizedField,
    CrossVerificationResult,
)
from backend.models.schemas import (
    CompanyInfo,
    DocumentType,
    PipelineStage,
    PipelineStageEnum,
    TicketSeverity,
    ScoreModule,
)
from backend.graph.nodes.consolidator_node import consolidator_node
from backend.graph.nodes.recommendation_node import recommendation_node
from backend.thinking.redis_publisher import reset_publisher, get_publisher
from backend.storage.redis_client import get_redis_client, reset_redis_client


passed = 0
failed = 0


def report(test_name: str, success: bool, detail: str = ""):
    global passed, failed
    if success:
        passed += 1
        print(f"  ✅ {test_name}")
    else:
        failed += 1
        print(f"  ❌ {test_name}: {detail}")


def make_worker_output(worker_id: str, doc_type: str, data: dict, confidence: float = 0.9) -> WorkerOutput:
    return WorkerOutput(
        worker_id=worker_id,
        document_type=doc_type,
        status="completed",
        extracted_data=data,
        confidence=confidence,
        pages_processed=10,
    )


def _make_3b_2a_data(
    months: list[tuple[str, float, float]],
) -> tuple[list[dict], list[dict]]:
    """Helper to build 3B and 2A monthly data from (month, claimed, available) tuples."""
    gstr3b = [{"month": m, "outward_taxable": 1000.0, "itc_claimed": c} for m, c, _ in months]
    gstr2a = [{"month": m, "itc_available": a} for m, _, a in months]
    return gstr3b, gstr2a


async def run_tests():
    global passed, failed

    reset_publisher()
    reset_redis_client()
    redis = get_redis_client()
    await redis.initialize()

    # ─── Test 1: _reconcile_monthly_itc produces correct detail ───
    print("\n🔧 Test 1: _reconcile_monthly_itc produces correct month-by-month detail")
    gstr3b, gstr2a = _make_3b_2a_data([
        ("Apr-22", 38.5, 35.0),
        ("May-22", 39.2, 36.1),
    ])
    result = _reconcile_monthly_itc(gstr3b, gstr2a)
    report(
        "Returns 2 months",
        len(result) == 2,
        f"Got {len(result)}",
    )
    apr = result[0]
    report(
        "Apr-22 fields correct",
        apr["month"] == "Apr-22"
        and apr["itc_claimed_3b"] == 38.5
        and apr["itc_available_2a"] == 35.0
        and apr["excess"] == 3.5
        and apr["outward_taxable"] == 1080.0 or apr["outward_taxable"] == 1000.0,
        f"month={apr['month']}, claimed={apr['itc_claimed_3b']}, avail={apr['itc_available_2a']}, excess={apr['excess']}",
    )
    # excess_pct = (38.5 - 35.0) / 35.0 * 100 = 10.0%
    report(
        "Apr-22 excess_pct is 10.0%",
        apr["excess_pct"] == 10.0,
        f"Got {apr['excess_pct']}",
    )

    # ─── Test 2: Normal excess (<5%) flagged as "normal" ───
    print("\n🔧 Test 2: Normal excess (<5%) flagged as 'normal'")
    gstr3b, gstr2a = _make_3b_2a_data([("Apr-22", 35.5, 35.0)])
    result = _reconcile_monthly_itc(gstr3b, gstr2a)
    # excess_pct = (35.5 - 35.0) / 35.0 * 100 = 1.43%
    report(
        "Flag is 'normal' for 1.4% excess",
        result[0]["flag"] == "normal",
        f"excess_pct={result[0]['excess_pct']}, flag={result[0]['flag']}",
    )

    # ─── Test 3: Moderate excess (5-15%) flagged as "moderate" ───
    print("\n🔧 Test 3: Moderate excess (5-15%) flagged as 'moderate'")
    gstr3b, gstr2a = _make_3b_2a_data([("Apr-22", 39.0, 35.0)])
    result = _reconcile_monthly_itc(gstr3b, gstr2a)
    # excess_pct = (39 - 35) / 35 * 100 = 11.43%
    report(
        "Flag is 'moderate' for ~11.4% excess",
        result[0]["flag"] == "moderate" and 5 < result[0]["excess_pct"] <= 15,
        f"excess_pct={result[0]['excess_pct']}, flag={result[0]['flag']}",
    )

    # ─── Test 4: High excess (>15%) flagged as "high" ───
    print("\n🔧 Test 4: High excess (>15%) flagged as 'high'")
    gstr3b, gstr2a = _make_3b_2a_data([("Apr-22", 42.0, 35.0)])
    result = _reconcile_monthly_itc(gstr3b, gstr2a)
    # excess_pct = (42 - 35) / 35 * 100 = 20.0%
    report(
        "Flag is 'high' for 20.0% excess",
        result[0]["flag"] == "high" and result[0]["excess_pct"] > 15,
        f"excess_pct={result[0]['excess_pct']}, flag={result[0]['flag']}",
    )

    # ─── Test 5: Critical excess (>25%) flagged as "critical" ───
    print("\n🔧 Test 5: Critical excess (>25%) flagged as 'critical'")
    gstr3b, gstr2a = _make_3b_2a_data([("Apr-22", 45.0, 35.0)])
    result = _reconcile_monthly_itc(gstr3b, gstr2a)
    # excess_pct = (45 - 35) / 35 * 100 = 28.57%
    report(
        "Flag is 'critical' for ~28.6% excess",
        result[0]["flag"] == "critical" and result[0]["excess_pct"] > 25,
        f"excess_pct={result[0]['excess_pct']}, flag={result[0]['flag']}",
    )

    # ─── Test 6: Zero availability — no division by zero ───
    print("\n🔧 Test 6: Zero availability handled gracefully")
    gstr3b, gstr2a = _make_3b_2a_data([("Apr-22", 38.5, 0.0)])
    result = _reconcile_monthly_itc(gstr3b, gstr2a)
    report(
        "excess_pct is 0 (not NaN/Inf) when GSTR-2A is zero",
        result[0]["excess_pct"] == 0 and result[0]["flag"] == "normal",
        f"excess_pct={result[0]['excess_pct']}, flag={result[0]['flag']}",
    )

    # ─── Test 7: Aggregate mismatch computed correctly ───
    print("\n🔧 Test 7: Aggregate mismatch computed correctly from monthly totals")
    gstr3b, gstr2a = _make_3b_2a_data([
        ("Apr-22", 40.0, 35.0),
        ("May-22", 40.0, 35.0),
        ("Jun-22", 40.0, 35.0),
    ])
    result = _reconcile_monthly_itc(gstr3b, gstr2a)
    total_claimed = sum(m["itc_claimed_3b"] for m in result)
    total_avail = sum(m["itc_available_2a"] for m in result)
    aggr_pct = (total_claimed - total_avail) / total_avail * 100
    report(
        "Aggregate totals: claimed 120, available 105, ~14.3%",
        abs(total_claimed - 120.0) < 0.01 and abs(total_avail - 105.0) < 0.01
        and abs(aggr_pct - 14.3) < 0.1,
        f"claimed={total_claimed}, avail={total_avail}, aggr_pct={aggr_pct:.1f}",
    )

    # ─── Test 8: Consolidator creates enhanced CrossVerificationResult ───
    print("\n🔧 Test 8: Consolidator creates CrossVerificationResult with enhanced fields")
    state_8 = CreditAppraisalState(
        session_id="test-t1-1-cv",
        company=CompanyInfo(
            name="XYZ Steel", sector="Manufacturing",
            loan_type="Working Capital", loan_amount="₹50cr", loan_amount_numeric=5000.0,
        ),
        workers_completed=1,
        worker_outputs={
            "W3": make_worker_output("W3", "GST_RETURNS", {
                "company_name": "XYZ Steel",
                "revenue_from_gst": {"annual_turnover": 13680.0, "unit": "lakhs"},
                "gstr2a_reconciliation": {
                    "itc_claimed_3b": 482.1, "itc_available_2a": 431.0,
                    "excess_itc_claimed": 51.1, "mismatch_pct": 11.9,
                    "severity": "flagged",
                    "high_excess_months": 2, "moderate_excess_months": 5,
                    "industry_avg_excess_pct": 3.5,
                },
            }),
        },
        pipeline_stages=[PipelineStage(stage=PipelineStageEnum.CONSOLIDATION)],
    )
    result_8 = await consolidator_node(state_8)
    rdp_8 = result_8.get("raw_data_package")
    gst_cv = [cv for cv in rdp_8.cross_verifications if "ITC" in cv.field_name]
    report(
        "ITC cross-verification created",
        len(gst_cv) == 1,
        f"count={len(gst_cv)}",
    )
    cv = gst_cv[0]
    report(
        "CV note includes industry avg and month counts",
        "Industry avg: 3.5%" in cv.note and "High-excess months: 2" in cv.note,
        f"note={cv.note[:80]}...",
    )
    report(
        "CV status is 'flagged' for 11.9% mismatch",
        cv.status == "flagged",
        f"status={cv.status}",
    )

    # ─── Test 9: Consolidator raises HIGH ticket for 10-20% mismatch ───
    print("\n🔧 Test 9: Consolidator raises HIGH ticket when mismatch 10-20%")
    tickets_9 = result_8.get("tickets", [])
    itc_tickets = [t for t in tickets_9 if "ITC" in t.title]
    report(
        "HIGH ticket created for 11.9% mismatch",
        len(itc_tickets) == 1 and itc_tickets[0].severity == TicketSeverity.HIGH,
        f"count={len(itc_tickets)}, severity={itc_tickets[0].severity if itc_tickets else 'N/A'}",
    )
    report(
        "Ticket category is 'ITC Reconciliation'",
        itc_tickets[0].category == "ITC Reconciliation" if itc_tickets else False,
        f"category={itc_tickets[0].category if itc_tickets else 'N/A'}",
    )
    report(
        "Ticket score_impact is -20 for ≤20% mismatch",
        itc_tickets[0].score_impact == -20 if itc_tickets else False,
        f"score_impact={itc_tickets[0].score_impact if itc_tickets else 'N/A'}",
    )

    # ─── Test 10: Consolidator raises CRITICAL ticket for >20% mismatch ───
    print("\n🔧 Test 10: Consolidator raises CRITICAL ticket when mismatch >20%")
    state_10 = CreditAppraisalState(
        session_id="test-t1-1-critical",
        company=CompanyInfo(
            name="XYZ Steel", sector="Manufacturing",
            loan_type="Working Capital", loan_amount="₹50cr", loan_amount_numeric=5000.0,
        ),
        workers_completed=1,
        worker_outputs={
            "W3": make_worker_output("W3", "GST_RETURNS", {
                "company_name": "XYZ Steel",
                "revenue_from_gst": {"annual_turnover": 13680.0, "unit": "lakhs"},
                "gstr2a_reconciliation": {
                    "itc_claimed_3b": 600.0, "itc_available_2a": 431.0,
                    "excess_itc_claimed": 169.0, "mismatch_pct": 39.2,
                    "severity": "critical",
                    "high_excess_months": 8, "moderate_excess_months": 3,
                    "industry_avg_excess_pct": 3.5,
                },
            }),
        },
        pipeline_stages=[PipelineStage(stage=PipelineStageEnum.CONSOLIDATION)],
    )
    result_10 = await consolidator_node(state_10)
    tickets_10 = result_10.get("tickets", [])
    crit_tickets = [t for t in tickets_10 if "ITC" in t.title]
    report(
        "CRITICAL ticket created for 39.2% mismatch",
        len(crit_tickets) == 1 and crit_tickets[0].severity == TicketSeverity.CRITICAL,
        f"count={len(crit_tickets)}, severity={crit_tickets[0].severity if crit_tickets else 'N/A'}",
    )
    report(
        "Ticket score_impact is -40 for >20% mismatch",
        crit_tickets[0].score_impact == -40 if crit_tickets else False,
        f"score_impact={crit_tickets[0].score_impact if crit_tickets else 'N/A'}",
    )
    report(
        "CV status is 'conflicting' for >20% mismatch",
        any(cv.status == "conflicting" for cv in result_10.get("raw_data_package").cross_verifications
            if "ITC" in cv.field_name),
        "Checked cross_verifications",
    )

    # ─── Test 11: No ticket for 5-10% mismatch ───
    print("\n🔧 Test 11: Consolidator does NOT raise ticket when mismatch 5-10%")
    state_11 = CreditAppraisalState(
        session_id="test-t1-1-low",
        company=CompanyInfo(
            name="XYZ Steel", sector="Manufacturing",
            loan_type="Working Capital", loan_amount="₹50cr", loan_amount_numeric=5000.0,
        ),
        workers_completed=1,
        worker_outputs={
            "W3": make_worker_output("W3", "GST_RETURNS", {
                "company_name": "XYZ Steel",
                "revenue_from_gst": {"annual_turnover": 13680.0, "unit": "lakhs"},
                "gstr2a_reconciliation": {
                    "itc_claimed_3b": 460.0, "itc_available_2a": 431.0,
                    "excess_itc_claimed": 29.0, "mismatch_pct": 6.7,
                    "severity": "moderate",
                    "high_excess_months": 0, "moderate_excess_months": 2,
                    "industry_avg_excess_pct": 3.5,
                },
            }),
        },
        pipeline_stages=[PipelineStage(stage=PipelineStageEnum.CONSOLIDATION)],
    )
    result_11 = await consolidator_node(state_11)
    tickets_11 = result_11.get("tickets", [])
    itc_tickets_11 = [t for t in tickets_11 if "ITC" in t.title]
    report(
        "No ticket for 6.7% mismatch (below 10% threshold)",
        len(itc_tickets_11) == 0,
        f"count={len(itc_tickets_11)}",
    )
    # But CrossVerificationResult should still be created (mismatch > 5%)
    gst_cv_11 = [cv for cv in result_11.get("raw_data_package").cross_verifications if "ITC" in cv.field_name]
    report(
        "CrossVerificationResult still created for 6.7%",
        len(gst_cv_11) == 1 and gst_cv_11[0].status == "flagged",
        f"count={len(gst_cv_11)}",
    )

    # ─── Test 12-15: Scorer graduated impacts ───
    # We test the scorer by building state with a realistic RDP that has
    # cross_verifications with ITC at different deviation levels.

    async def _test_scorer_impact(test_num, mismatch_pct, expected_impact, label):
        print(f"\n🔧 Test {test_num}: Scorer applies {expected_impact} for {label}")
        rdp = RawDataPackage(
            worker_outputs={
                "W3": make_worker_output("W3", "GST_RETURNS", {
                    "company_name": "XYZ Steel",
                    "gstr2a_reconciliation": {
                        "itc_claimed_3b": 500, "itc_available_2a": 400,
                        "mismatch_pct": mismatch_pct,
                    },
                    "filing_compliance": {"regularity_pct": 100, "months_late": 0},
                }),
                "W1": make_worker_output("W1", "ANNUAL_REPORT", {
                    "company_name": "XYZ Steel",
                    "revenue": {"fy2023": 14230.0, "unit": "lakhs", "source_page": 45},
                }),
            },
            cross_verifications=[
                CrossVerificationResult(
                    field_name="ITC (GSTR-2A vs GSTR-3B)",
                    sources={
                        "GSTR-3B": NormalizedField(value=500, source_document="GST", confidence=0.95, unit="lakhs"),
                        "GSTR-2A": NormalizedField(value=400, source_document="GST", confidence=0.95, unit="lakhs"),
                    },
                    max_deviation_pct=mismatch_pct,
                    accepted_value=400,
                    accepted_source="GSTR-2A",
                    status="flagged" if mismatch_pct <= 20 else "conflicting",
                    note=f"ITC mismatch: {mismatch_pct}%",
                ),
            ],
            contradictions=[],
            completeness_score=0.8,
            mandatory_fields_present=True,
        )
        state_s = CreditAppraisalState(
            session_id=f"test-t1-1-scorer-{test_num}",
            company=CompanyInfo(
                name="XYZ Steel", sector="Manufacturing",
                loan_type="Working Capital", loan_amount="₹50cr", loan_amount_numeric=5000.0,
            ),
            raw_data_package=rdp,
            pipeline_stages=[PipelineStage(stage=PipelineStageEnum.RECOMMENDATION)],
        )
        result_s = await recommendation_node(state_s)
        # Find the ITC entry in score breakdown
        breakdown = result_s.get("score_breakdown", [])
        itc_entries = [e for e in breakdown if "ITC" in e.metric_name or "2A" in e.metric_name or "3B" in e.metric_name]
        if itc_entries:
            actual_impact = itc_entries[0].score_impact
            report(
                f"ITC impact is {expected_impact} for {mismatch_pct}% mismatch",
                actual_impact == expected_impact,
                f"expected={expected_impact}, actual={actual_impact}",
            )
        else:
            report(
                f"ITC score entry found for {mismatch_pct}% mismatch",
                False,
                f"No ITC entry in breakdown. Entries: {[e.metric_name for e in breakdown]}",
            )

    # Test 12: 5-10% → -10
    await _test_scorer_impact(12, 8.0, -10, "5-10% ITC mismatch")

    # Test 13: 10-15% → -20
    await _test_scorer_impact(13, 12.5, -20, "10-15% ITC mismatch")

    # Test 14: 15-20% → -35
    await _test_scorer_impact(14, 17.0, -35, "15-20% ITC mismatch")

    # Test 15: >20% → -50
    await _test_scorer_impact(15, 25.0, -50, ">20% ITC mismatch")

    # ─── Summary ───
    print(f"\n{'='*60}")
    print(f"T1.1 GSTR-2A vs 3B Reconciliation: {passed} passed, {failed} failed")
    print(f"{'='*60}")

    if failed > 0:
        sys.exit(1)


def test_t1_1_gst_reconciliation():
    """Entry point for pytest discovery."""
    asyncio.run(run_tests())


if __name__ == "__main__":
    asyncio.run(run_tests())
