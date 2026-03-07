"""
Intelli-Credit — T1.2 Tests: RPT Concealment Detection (Board Minutes vs Annual Report)

Tests:
1.  Both sources missing → no concealment detected
2.  W1 only (no W6) → no concealment, cannot cross-verify
3.  W6 only (no W1) → no concealment, cannot cross-verify
4.  Both present, zero RPTs → no concealment
5.  BM has RPTs, AR discloses all → no concealment (consistent)
6.  BM has 3 RPTs, AR discloses 2 → concealment detected (count mismatch = 1)
7.  BM has 5 RPTs, AR discloses 2 → critical severity (count mismatch ≥ 3)
8.  BM has 3 RPTs, AR discloses 1 → high severity (count mismatch ≥ 2)
9.  Amount mismatch without count mismatch → concealment via amount diff > 20%
10. Missing counterparties detected correctly
11. Party name normalization works (Pvt Ltd, lower case, parenthetical)
12. Consolidator emits RPT ticket when concealment detected (1 missing)
13. Consolidator emits CRITICAL ticket when ≥3 RPTs concealed
14. Consolidator adds rpt_concealment to contradictions list
15. Consolidator does NOT raise ticket when RPTs are consistent
16. Scorer applies -35 for RPT concealment
17. Scorer does NOT apply concealment penalty when no concealment
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.consolidator.contradiction_detector import (
    detect_rpt_concealment,
    _normalize_party_name,
    RPTConcealmentResult,
)
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


# ── Mock data builders ──

def _w1_data_with_rpts(count: int, total: float, transactions: list) -> dict:
    """Build W1 extracted data with RPT section."""
    return {
        "company_name": "XYZ Steel Industries Ltd",
        "financial_year": "FY2023",
        "revenue": {"fy2023": 14230.0, "unit": "lakhs", "source_page": 45},
        "rpts": {
            "count": count,
            "total_amount": total,
            "transactions": transactions,
            "source_page": 68,
        },
    }


def _w6_data_with_rpts(count: int, total: float, transactions: list) -> dict:
    """Build W6 extracted data with RPT approvals."""
    return {
        "company_name": "XYZ Steel Industries Ltd",
        "rpt_approvals": {
            "count": count,
            "total_amount": total,
            "transactions": transactions,
            "source_page": 14,
        },
        "director_attendance": {"average_pct": 82.5},
    }


# ── Standard transactions for reuse ──

BM_3_TRANSACTIONS = [
    {"party": "ABC Trading (promoter entity)", "amount": 720.0, "nature": "purchases"},
    {"party": "PQR Logistics Pvt Ltd", "amount": 480.0, "nature": "services"},
    {"party": "Steel Suppliers Private Limited", "amount": 340.0, "nature": "purchases"},
]

AR_2_TRANSACTIONS = [
    {"party": "ABC Trading (promoter entity)", "amount": 720.0, "nature": "purchases"},
    {"party": "PQR Logistics (director interest)", "amount": 480.0, "nature": "services"},
]

AR_3_TRANSACTIONS = [
    {"party": "ABC Trading (promoter entity)", "amount": 720.0, "nature": "purchases"},
    {"party": "PQR Logistics (director interest)", "amount": 480.0, "nature": "services"},
    {"party": "Steel Suppliers (group co)", "amount": 340.0, "nature": "purchases"},
]


async def run_tests():
    global passed, failed

    reset_publisher()
    reset_redis_client()
    redis = get_redis_client()
    await redis.initialize()

    # ─── Test 1: Both sources missing → no concealment ───
    print("\n🔧 Test 1: Both sources missing → no concealment detected")
    r1 = detect_rpt_concealment(None, None)
    report("No concealment", not r1.concealment_detected, f"detected={r1.concealment_detected}")
    report("Severity is none", r1.severity == "none", f"severity={r1.severity}")
    report("Detail mentions missing data", "missing" in r1.detail.lower(), f"detail={r1.detail}")

    # ─── Test 2: W1 only (no W6) → cannot cross-verify ───
    print("\n🔧 Test 2: W1 only (no W6) → no concealment")
    w1 = _w1_data_with_rpts(5, 1840.0, AR_3_TRANSACTIONS)
    r2 = detect_rpt_concealment(w1, None)
    report("No concealment", not r2.concealment_detected, f"detected={r2.concealment_detected}")

    # ─── Test 3: W6 only (no W1) → cannot cross-verify ───
    print("\n🔧 Test 3: W6 only (no W1) → no concealment")
    w6 = _w6_data_with_rpts(3, 1540.0, BM_3_TRANSACTIONS)
    r3 = detect_rpt_concealment(None, w6)
    report("No concealment", not r3.concealment_detected, f"detected={r3.concealment_detected}")

    # ─── Test 4: Both present, zero RPTs ───
    print("\n🔧 Test 4: Both present, zero RPTs → no concealment")
    r4 = detect_rpt_concealment(
        _w1_data_with_rpts(0, 0.0, []),
        _w6_data_with_rpts(0, 0.0, []),
    )
    report("No concealment", not r4.concealment_detected, f"detected={r4.concealment_detected}")
    report("Detail mentions no RPTs", "no rpt" in r4.detail.lower(), f"detail={r4.detail}")

    # ─── Test 5: BM has 3, AR discloses 3 → consistent ───
    print("\n🔧 Test 5: BM has 3 RPTs, AR discloses all 3 → no concealment")
    r5 = detect_rpt_concealment(
        _w1_data_with_rpts(3, 1540.0, AR_3_TRANSACTIONS),
        _w6_data_with_rpts(3, 1540.0, BM_3_TRANSACTIONS),
    )
    report("No concealment", not r5.concealment_detected, f"detected={r5.concealment_detected}")
    report("Severity is none", r5.severity == "none", f"severity={r5.severity}")
    report("Detail mentions consistent", "consistent" in r5.detail.lower(), f"detail={r5.detail}")

    # ─── Test 6: BM has 3, AR discloses 2 → moderate concealment (1 missing) ───
    print("\n🔧 Test 6: BM has 3 RPTs, AR discloses 2 → moderate concealment")
    r6 = detect_rpt_concealment(
        _w1_data_with_rpts(2, 1200.0, AR_2_TRANSACTIONS),
        _w6_data_with_rpts(3, 1540.0, BM_3_TRANSACTIONS),
    )
    report("Concealment detected", r6.concealment_detected, f"detected={r6.concealment_detected}")
    report("Count mismatch = 1", r6.count_mismatch == 1, f"mismatch={r6.count_mismatch}")
    report("Concealed amount = 340.0", r6.concealed_amount == 340.0, f"amount={r6.concealed_amount}")
    report("Severity is moderate", r6.severity == "moderate", f"severity={r6.severity}")
    report(
        "Missing party includes Steel Suppliers",
        any("steel suppliers" in p.lower() for p in r6.missing_parties),
        f"missing={r6.missing_parties}",
    )

    # ─── Test 7: BM has 5, AR discloses 2 → critical (≥3 concealed) ───
    print("\n🔧 Test 7: BM has 5 RPTs, AR discloses 2 → critical severity")
    bm_5 = BM_3_TRANSACTIONS + [
        {"party": "Green Energy Pvt Ltd", "amount": 180.0, "nature": "services"},
        {"party": "XYZ Foundation", "amount": 120.0, "nature": "donations"},
    ]
    r7 = detect_rpt_concealment(
        _w1_data_with_rpts(2, 1200.0, AR_2_TRANSACTIONS),
        _w6_data_with_rpts(5, 1840.0, bm_5),
    )
    report("Concealment detected", r7.concealment_detected, f"detected={r7.concealment_detected}")
    report("Count mismatch = 3", r7.count_mismatch == 3, f"mismatch={r7.count_mismatch}")
    report("Severity is critical", r7.severity == "critical", f"severity={r7.severity}")

    # ─── Test 8: BM has 3, AR discloses 1 → high (≥2 concealed) ───
    print("\n🔧 Test 8: BM has 3 RPTs, AR discloses 1 → high severity")
    r8 = detect_rpt_concealment(
        _w1_data_with_rpts(1, 720.0, [AR_2_TRANSACTIONS[0]]),
        _w6_data_with_rpts(3, 1540.0, BM_3_TRANSACTIONS),
    )
    report("Concealment detected", r8.concealment_detected, f"detected={r8.concealment_detected}")
    report("Count mismatch = 2", r8.count_mismatch == 2, f"mismatch={r8.count_mismatch}")
    report("Severity is high", r8.severity == "high", f"severity={r8.severity}")

    # ─── Test 9: Same count but amount mismatch > 20% ───
    print("\n🔧 Test 9: Same count, amount mismatch > 20% → concealment via amounts")
    r9 = detect_rpt_concealment(
        _w1_data_with_rpts(3, 1000.0, AR_3_TRANSACTIONS),
        _w6_data_with_rpts(3, 1540.0, BM_3_TRANSACTIONS),
    )
    # Counts match, but BM total (1540) vs AR total (1000) → 35% diff
    # However, counterparty matching may still detect missing parties
    # The key test: amount diff >20% triggers concealment
    report("Concealment detected", r9.concealment_detected, f"detected={r9.concealment_detected}")

    # ─── Test 10: Missing counterparties detected ───
    print("\n🔧 Test 10: Missing counterparties detected correctly")
    # BM has 3 specific parties, AR has only 2 (missing Steel Suppliers)
    r10 = detect_rpt_concealment(
        _w1_data_with_rpts(2, 1200.0, AR_2_TRANSACTIONS),
        _w6_data_with_rpts(3, 1540.0, BM_3_TRANSACTIONS),
    )
    report(
        "Missing parties list is non-empty",
        len(r10.missing_parties) > 0,
        f"missing={r10.missing_parties}",
    )
    report(
        "Steel Suppliers in missing list",
        any("steel suppliers" in p.lower() for p in r10.missing_parties),
        f"missing={r10.missing_parties}",
    )

    # ─── Test 11: Party name normalization ───
    print("\n🔧 Test 11: Party name normalization works")
    report(
        "Pvt Ltd removed",
        _normalize_party_name("ABC Trading Pvt Ltd") == "abc trading",
        f"got={_normalize_party_name('ABC Trading Pvt Ltd')}",
    )
    report(
        "Private Limited removed",
        _normalize_party_name("ABC Trading Private Limited") == "abc trading",
        f"got={_normalize_party_name('ABC Trading Private Limited')}",
    )
    report(
        "Parenthetical removed",
        _normalize_party_name("ABC Trading (promoter entity)") == "abc trading",
        f"got={_normalize_party_name('ABC Trading (promoter entity)')}",
    )
    report(
        "Case normalized",
        _normalize_party_name("ABC TRADING LTD") == "abc trading",
        f"got={_normalize_party_name('ABC TRADING LTD')}",
    )
    report(
        "Empty string handled",
        _normalize_party_name("") == "",
        f"got='{_normalize_party_name('')}'",
    )

    # ─── Test 12: Consolidator raises HIGH ticket for 1-missing concealment ───
    print("\n🔧 Test 12: Consolidator raises HIGH ticket when 1 RPT concealed")
    state_12 = CreditAppraisalState(
        session_id="test-t1-2-ticket-high",
        company=CompanyInfo(
            name="XYZ Steel", sector="Manufacturing",
            loan_type="Working Capital", loan_amount="₹50cr", loan_amount_numeric=5000.0,
        ),
        workers_completed=2,
        worker_outputs={
            "W1": make_worker_output("W1", "ANNUAL_REPORT", _w1_data_with_rpts(2, 1200.0, AR_2_TRANSACTIONS)),
            "W6": make_worker_output("W6", "BOARD_MINUTES", _w6_data_with_rpts(3, 1540.0, BM_3_TRANSACTIONS)),
        },
        pipeline_stages=[PipelineStage(stage=PipelineStageEnum.CONSOLIDATION)],
    )
    result_12 = await consolidator_node(state_12)
    tickets_12 = result_12.get("tickets", [])
    rpt_tickets_12 = [t for t in tickets_12 if "RPT" in t.title]
    report(
        "RPT ticket created",
        len(rpt_tickets_12) == 1,
        f"count={len(rpt_tickets_12)}",
    )
    if rpt_tickets_12:
        report(
            "Ticket severity is HIGH",
            rpt_tickets_12[0].severity == TicketSeverity.HIGH,
            f"severity={rpt_tickets_12[0].severity}",
        )
        report(
            "Ticket category is 'RPT Concealment'",
            rpt_tickets_12[0].category == "RPT Concealment",
            f"category={rpt_tickets_12[0].category}",
        )
        report(
            "Ticket score_impact is -35",
            rpt_tickets_12[0].score_impact == -35,
            f"impact={rpt_tickets_12[0].score_impact}",
        )

    # ─── Test 13: Consolidator raises CRITICAL ticket for ≥3 concealed ───
    print("\n🔧 Test 13: Consolidator raises CRITICAL ticket when ≥3 RPTs concealed")
    bm_5_tx = BM_3_TRANSACTIONS + [
        {"party": "Green Energy Pvt Ltd", "amount": 180.0, "nature": "services"},
        {"party": "XYZ Foundation", "amount": 120.0, "nature": "donations"},
    ]
    state_13 = CreditAppraisalState(
        session_id="test-t1-2-ticket-critical",
        company=CompanyInfo(
            name="XYZ Steel", sector="Manufacturing",
            loan_type="Working Capital", loan_amount="₹50cr", loan_amount_numeric=5000.0,
        ),
        workers_completed=2,
        worker_outputs={
            "W1": make_worker_output("W1", "ANNUAL_REPORT", _w1_data_with_rpts(2, 1200.0, AR_2_TRANSACTIONS)),
            "W6": make_worker_output("W6", "BOARD_MINUTES", _w6_data_with_rpts(5, 1840.0, bm_5_tx)),
        },
        pipeline_stages=[PipelineStage(stage=PipelineStageEnum.CONSOLIDATION)],
    )
    result_13 = await consolidator_node(state_13)
    tickets_13 = result_13.get("tickets", [])
    rpt_tickets_13 = [t for t in tickets_13 if "RPT" in t.title]
    report(
        "CRITICAL ticket created",
        len(rpt_tickets_13) == 1 and rpt_tickets_13[0].severity == TicketSeverity.CRITICAL,
        f"count={len(rpt_tickets_13)}, severity={rpt_tickets_13[0].severity if rpt_tickets_13 else 'N/A'}",
    )

    # ─── Test 14: Consolidator adds rpt_concealment to contradictions ───
    print("\n🔧 Test 14: Consolidator adds rpt_concealment to contradictions list")
    rdp_12 = result_12.get("raw_data_package")
    rpt_contras = [c for c in rdp_12.contradictions if c.get("type") == "rpt_concealment"]
    report(
        "rpt_concealment in contradictions",
        len(rpt_contras) == 1,
        f"count={len(rpt_contras)}",
    )
    if rpt_contras:
        c = rpt_contras[0]
        report(
            "Contradiction has correct fields",
            c.get("board_minutes_count") == 3
            and c.get("annual_report_count") == 2
            and c.get("count_mismatch") == 1
            and c.get("concealed_amount") == 340.0,
            f"bm={c.get('board_minutes_count')}, ar={c.get('annual_report_count')}, "
            f"mismatch={c.get('count_mismatch')}, amount={c.get('concealed_amount')}",
        )

    # ─── Test 15: Consolidator does NOT raise ticket when consistent ───
    print("\n🔧 Test 15: Consolidator does NOT raise RPT ticket when consistent")
    state_15 = CreditAppraisalState(
        session_id="test-t1-2-no-ticket",
        company=CompanyInfo(
            name="XYZ Steel", sector="Manufacturing",
            loan_type="Working Capital", loan_amount="₹50cr", loan_amount_numeric=5000.0,
        ),
        workers_completed=2,
        worker_outputs={
            "W1": make_worker_output("W1", "ANNUAL_REPORT", _w1_data_with_rpts(3, 1540.0, AR_3_TRANSACTIONS)),
            "W6": make_worker_output("W6", "BOARD_MINUTES", _w6_data_with_rpts(3, 1540.0, BM_3_TRANSACTIONS)),
        },
        pipeline_stages=[PipelineStage(stage=PipelineStageEnum.CONSOLIDATION)],
    )
    result_15 = await consolidator_node(state_15)
    tickets_15 = result_15.get("tickets", [])
    rpt_tickets_15 = [t for t in tickets_15 if "RPT" in t.title]
    report(
        "No RPT ticket when consistent",
        len(rpt_tickets_15) == 0,
        f"count={len(rpt_tickets_15)}",
    )
    # Also verify contradictions don't contain rpt_concealment
    rdp_15 = result_15.get("raw_data_package")
    rpt_c_15 = [c for c in rdp_15.contradictions if c.get("type") == "rpt_concealment"]
    report(
        "No rpt_concealment in contradictions when consistent",
        len(rpt_c_15) == 0,
        f"count={len(rpt_c_15)}",
    )

    # ─── Test 16: Scorer applies -35 for RPT concealment ───
    print("\n🔧 Test 16: Scorer applies -35 for RPT concealment")
    rdp_16 = RawDataPackage(
        worker_outputs={},
        cross_verifications=[],
        contradictions=[{
            "type": "rpt_concealment",
            "description": "BM: 3 RPTs, AR: 2 RPTs",
            "severity": "HIGH",
            "confidence": 0.88,
            "board_minutes_count": 3,
            "annual_report_count": 2,
            "count_mismatch": 1,
            "concealed_amount": 340.0,
            "missing_parties": ["Steel Suppliers Private Limited"],
        }],
        completeness_score=0.8,
        mandatory_fields_present=True,
    )
    state_16 = CreditAppraisalState(
        session_id="test-t1-2-scorer-conceal",
        company=CompanyInfo(
            name="XYZ Steel", sector="Manufacturing",
            loan_type="Working Capital", loan_amount="₹50cr", loan_amount_numeric=5000.0,
        ),
        # W1 data for the scorer to read RPTs as well
        worker_outputs={
            "W1": make_worker_output("W1", "ANNUAL_REPORT", _w1_data_with_rpts(2, 1200.0, AR_2_TRANSACTIONS)),
        },
        raw_data_package=rdp_16,
        pipeline_stages=[PipelineStage(stage=PipelineStageEnum.RECOMMENDATION)],
    )
    result_16 = await recommendation_node(state_16)
    breakdown_16 = result_16.get("score_breakdown", [])
    conceal_entries = [
        e for e in breakdown_16
        if "concealment" in e.metric_name.lower() or "bm vs ar" in e.metric_name.lower()
    ]
    report(
        "RPT Concealment entry found in breakdown",
        len(conceal_entries) == 1,
        f"count={len(conceal_entries)}, metrics={[e.metric_name for e in breakdown_16]}",
    )
    if conceal_entries:
        report(
            "Score impact is -35",
            conceal_entries[0].score_impact == -35,
            f"impact={conceal_entries[0].score_impact}",
        )
        report(
            "Module is CHARACTER",
            conceal_entries[0].module == ScoreModule.CHARACTER,
            f"module={conceal_entries[0].module}",
        )

    # ─── Test 17: Scorer does NOT apply concealment when none detected ───
    print("\n🔧 Test 17: Scorer does NOT apply concealment penalty when no concealment")
    rdp_17 = RawDataPackage(
        worker_outputs={},
        cross_verifications=[],
        contradictions=[],  # No rpt_concealment
        completeness_score=0.8,
        mandatory_fields_present=True,
    )
    state_17 = CreditAppraisalState(
        session_id="test-t1-2-scorer-clean",
        company=CompanyInfo(
            name="XYZ Steel", sector="Manufacturing",
            loan_type="Working Capital", loan_amount="₹50cr", loan_amount_numeric=5000.0,
        ),
        worker_outputs={
            "W1": make_worker_output("W1", "ANNUAL_REPORT", _w1_data_with_rpts(3, 1540.0, AR_3_TRANSACTIONS)),
        },
        raw_data_package=rdp_17,
        pipeline_stages=[PipelineStage(stage=PipelineStageEnum.RECOMMENDATION)],
    )
    result_17 = await recommendation_node(state_17)
    breakdown_17 = result_17.get("score_breakdown", [])
    conceal_entries_17 = [
        e for e in breakdown_17
        if "concealment" in e.metric_name.lower() or "bm vs ar" in e.metric_name.lower()
    ]
    report(
        "No concealment entry when clean",
        len(conceal_entries_17) == 0,
        f"count={len(conceal_entries_17)}, metrics={[e.metric_name for e in breakdown_17]}",
    )

    # ─── Summary ───
    print(f"\n{'='*60}")
    print(f"T1.2 RPT Concealment Detection: {passed} passed, {failed} failed")
    print(f"{'='*60}")

    if failed > 0:
        sys.exit(1)


def test_t1_2_rpt_concealment():
    """Entry point for pytest discovery."""
    asyncio.run(run_tests())


if __name__ == "__main__":
    asyncio.run(run_tests())
