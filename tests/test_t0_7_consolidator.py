"""
Intelli-Credit — T0.7 Tests: Agent 0.5 Consolidator

Tests:
1.  Consolidator merges worker outputs from state
2.  Revenue cross-verification: 3 sources agree (verified)
3.  Revenue cross-verification: minor deviation (flagged)
4.  Revenue cross-verification: major conflict (conflicting)
5.  Cross-verification uses source credibility weights
6.  GSTR-2A vs 3B mismatch detected
7.  Mandatory fields check works
8.  Contradiction detection finds mismatched names
9.  Consolidator emits ThinkingEvents
10. Consolidator handles empty worker outputs gracefully
11. Full integration with workers_node → consolidator_node
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.graph.state import (
    CreditAppraisalState,
    WorkerOutput,
    RawDataPackage,
    NormalizedField,
    CrossVerificationResult,
)
from backend.models.schemas import (
    CompanyInfo,
    DocumentMeta,
    DocumentType,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
)
from backend.graph.nodes.consolidator_node import (
    consolidator_node,
    _cross_verify_revenue,
    _detect_contradictions,
    _check_mandatory_fields,
)
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


async def run_tests():
    global passed, failed

    reset_publisher()
    reset_redis_client()
    redis = get_redis_client()
    await redis.initialize()

    # ─── Test 1: Consolidator merges worker outputs ───
    print("\n🔧 Test 1: Consolidator merges worker outputs from state")
    state = CreditAppraisalState(
        session_id="test-consolidator-1",
        company=CompanyInfo(
            name="XYZ Steel", sector="Manufacturing",
            loan_type="Working Capital", loan_amount="₹50cr", loan_amount_numeric=5000.0,
        ),
        workers_completed=3,
        worker_outputs={
            "W1": make_worker_output("W1", "ANNUAL_REPORT", {
                "company_name": "XYZ Steel", "revenue": {"fy2023": 14230.0, "unit": "lakhs", "source_page": 45},
            }),
            "W2": make_worker_output("W2", "BANK_STATEMENT", {
                "company_name": "XYZ Steel", "revenue_from_bank": {"annual_credits": 14860.0, "unit": "lakhs"},
            }),
            "W3": make_worker_output("W3", "GST_RETURNS", {
                "company_name": "XYZ Steel",
                "revenue_from_gst": {"annual_turnover": 13680.0, "unit": "lakhs"},
                "gstr2a_reconciliation": {
                    "itc_claimed_3b": 482.1, "itc_available_2a": 431.0,
                    "excess_itc_claimed": 51.1, "mismatch_pct": 10.6,
                },
            }),
        },
        pipeline_stages=[
            PipelineStage(stage=PipelineStageEnum.CONSOLIDATION),
        ],
    )
    result = await consolidator_node(state)
    rdp = result.get("raw_data_package")
    report(
        "Consolidator returns RawDataPackage",
        rdp is not None and isinstance(rdp, RawDataPackage),
        f"Type: {type(rdp)}",
    )
    report(
        "Worker outputs merged",
        len(rdp.worker_outputs) == 3,
        f"Count: {len(rdp.worker_outputs)}",
    )
    report(
        "Cross-verifications performed",
        len(rdp.cross_verifications) >= 1,  # Revenue + GSTR 2A/3B
        f"Count: {len(rdp.cross_verifications)}",
    )

    # ─── Test 2: Revenue cross-verification — sources agree ───
    print("\n🔧 Test 2: Revenue cross-verification — sources agree (verified)")
    sources_agree = {
        "ANNUAL_REPORT": NormalizedField(value=14230.0, source_document="AR", confidence=0.9, unit="lakhs"),
        "BANK_STATEMENT": NormalizedField(value=14350.0, source_document="Bank", confidence=0.9, unit="lakhs"),
        "GST_RETURNS": NormalizedField(value=14180.0, source_document="GST", confidence=0.95, unit="lakhs"),
    }
    cv = _cross_verify_revenue(sources_agree)
    report(
        "Status is 'verified' when deviation < 5%",
        cv.status == "verified" and cv.max_deviation_pct < 5,
        f"status={cv.status}, deviation={cv.max_deviation_pct}%",
    )

    # ─── Test 3: Revenue cross-verification — minor deviation ───
    print("\n🔧 Test 3: Revenue cross-verification — minor deviation (flagged)")
    sources_flagged = {
        "ANNUAL_REPORT": NormalizedField(value=14230.0, source_document="AR", confidence=0.9, unit="lakhs"),
        "BANK_STATEMENT": NormalizedField(value=15800.0, source_document="Bank", confidence=0.9, unit="lakhs"),
        "GST_RETURNS": NormalizedField(value=13680.0, source_document="GST", confidence=0.95, unit="lakhs"),
    }
    cv2 = _cross_verify_revenue(sources_flagged)
    report(
        "Status is 'flagged' when deviation 5-15%",
        cv2.status == "flagged" and 5 <= cv2.max_deviation_pct <= 15,
        f"status={cv2.status}, deviation={cv2.max_deviation_pct}%",
    )

    # ─── Test 4: Revenue cross-verification — major conflict ───
    print("\n🔧 Test 4: Revenue cross-verification — major conflict")
    sources_conflict = {
        "ANNUAL_REPORT": NormalizedField(value=14230.0, source_document="AR", confidence=0.9, unit="lakhs"),
        "BANK_STATEMENT": NormalizedField(value=20000.0, source_document="Bank", confidence=0.9, unit="lakhs"),
    }
    cv3 = _cross_verify_revenue(sources_conflict)
    report(
        "Status is 'conflicting' when deviation > 15%",
        cv3.status == "conflicting" and cv3.max_deviation_pct > 15,
        f"status={cv3.status}, deviation={cv3.max_deviation_pct}%",
    )

    # ─── Test 5: Cross-verification uses source credibility weights ───
    print("\n🔧 Test 5: Cross-verification prefers government sources")
    sources_weighted = {
        "GST_RETURNS": NormalizedField(value=13680.0, source_document="GST", confidence=0.95, unit="lakhs"),
        "ANNUAL_REPORT": NormalizedField(value=14230.0, source_document="AR", confidence=0.9, unit="lakhs"),
    }
    cv4 = _cross_verify_revenue(sources_weighted)
    report(
        "Accepted from GST (weight 1.0) over AR (weight 0.70)",
        cv4.accepted_source == "GST_RETURNS" and cv4.accepted_value == 13680.0,
        f"accepted_source={cv4.accepted_source}, value={cv4.accepted_value}",
    )

    # ─── Test 6: GSTR-2A vs 3B mismatch ───
    print("\n🔧 Test 6: GSTR-2A vs 3B mismatch detected")
    # Already tested via consolidator_node in Test 1 — check cross_verifications
    gst_cv = [cv for cv in rdp.cross_verifications if "ITC" in cv.field_name]
    report(
        "ITC mismatch cross-verification created",
        len(gst_cv) == 1 and gst_cv[0].status == "flagged",
        f"Found: {len(gst_cv)}, status: {gst_cv[0].status if gst_cv else 'N/A'}",
    )

    # ─── Test 7: Mandatory fields check ───
    print("\n🔧 Test 7: Mandatory fields check")
    outputs_with_fields = {
        "W1": make_worker_output("W1", "ANNUAL_REPORT", {"company_name": "XYZ", "revenue": {"fy2023": 100}}),
    }
    outputs_without_fields = {
        "W1": make_worker_output("W1", "ANNUAL_REPORT", {"other_data": "nothing useful"}),
    }
    report(
        "Mandatory fields detected when present",
        _check_mandatory_fields(outputs_with_fields) is True,
    )
    report(
        "Mandatory fields missing detected",
        _check_mandatory_fields(outputs_without_fields) is False,
    )

    # ─── Test 8: Contradiction detection ───
    print("\n🔧 Test 8: Contradiction detection for mismatched names")
    outputs_mismatch = {
        "W1": make_worker_output("W1", "ANNUAL_REPORT", {"company_name": "XYZ Steel Industries Ltd"}),
        "W3": make_worker_output("W3", "GST_RETURNS", {"company_name": "XYZ Steel Pvt Ltd"}),
    }
    contradictions = _detect_contradictions(outputs_mismatch)
    report(
        "Company name mismatch detected",
        len(contradictions) >= 1 and contradictions[0]["type"] == "company_name_mismatch",
        f"Contradictions: {contradictions}",
    )

    # ─── Test 9: ThinkingEvents emitted ───
    print("\n🔧 Test 9: Consolidator emits ThinkingEvents")
    publisher = get_publisher()
    events = publisher.get_event_log("test-consolidator-1")
    report(
        "ThinkingEvents emitted during consolidation",
        len(events) >= 5,  # READ + multiple FOUNDs + FLAGGED + CONCLUDING
        f"Event count: {len(events)}",
    )

    # Check event types
    event_types = {e.get("event_type") for e in events}
    report(
        "Diverse event types emitted",
        "READ" in event_types and "FOUND" in event_types and "CONCLUDING" in event_types,
        f"Types: {event_types}",
    )

    # ─── Test 10: Empty worker outputs ───
    print("\n🔧 Test 10: Consolidator handles empty outputs")
    reset_publisher()
    state_empty = CreditAppraisalState(
        session_id="test-consolidator-empty",
        workers_completed=0,
        worker_outputs={},
        pipeline_stages=[PipelineStage(stage=PipelineStageEnum.CONSOLIDATION)],
    )
    result_empty = await consolidator_node(state_empty)
    rdp_empty = result_empty.get("raw_data_package")
    report(
        "Returns empty RawDataPackage",
        rdp_empty is not None
        and rdp_empty.completeness_score == 0.0
        and rdp_empty.mandatory_fields_present is False,
        f"completeness={rdp_empty.completeness_score if rdp_empty else 'N/A'}",
    )

    # ─── Test 11: Full integration workers → consolidator ───
    print("\n🔧 Test 11: Integration workers_node → consolidator_node")
    reset_publisher()
    reset_redis_client()
    redis2 = get_redis_client()
    await redis2.initialize()

    with tempfile.TemporaryDirectory() as tmpdir:
        ar = os.path.join(tmpdir, "annual_report.pdf")
        bs = os.path.join(tmpdir, "bank_statement.pdf")
        gst = os.path.join(tmpdir, "gst_returns.pdf")
        for p in [ar, bs, gst]:
            with open(p, "w") as f:
                f.write("Mock content")

        from backend.graph.nodes.workers_node import workers_node

        state_full = CreditAppraisalState(
            session_id="test-integration-07",
            company=CompanyInfo(
                name="XYZ Steel", sector="Manufacturing",
                loan_type="Term Loan", loan_amount="₹50cr", loan_amount_numeric=5000.0,
            ),
            documents=[
                DocumentMeta(filename="annual_report.pdf", document_type=DocumentType.ANNUAL_REPORT, file_size=1024, file_path=ar),
                DocumentMeta(filename="bank_statement.pdf", document_type=DocumentType.BANK_STATEMENT, file_size=512, file_path=bs),
                DocumentMeta(filename="gst_returns.pdf", document_type=DocumentType.GST_RETURNS, file_size=256, file_path=gst),
            ],
            pipeline_stages=[
                PipelineStage(stage=PipelineStageEnum.WORKERS),
                PipelineStage(stage=PipelineStageEnum.CONSOLIDATION),
            ],
        )

        # Step 1: Run workers
        worker_result = await workers_node(state_full)

        # Apply worker results to state (simulating LangGraph state merge)
        state_full.worker_outputs = worker_result.get("worker_outputs", {})
        state_full.workers_completed = worker_result.get("workers_completed", 0)

        # Step 2: Run consolidator
        consol_result = await consolidator_node(state_full)
        rdp_full = consol_result.get("raw_data_package")

        report(
            "Full pipeline: workers → consolidator succeeds",
            rdp_full is not None
            and len(rdp_full.worker_outputs) == 3
            and rdp_full.completeness_score > 0
            and rdp_full.mandatory_fields_present is True,
            f"outputs={len(rdp_full.worker_outputs)}, "
            f"completeness={rdp_full.completeness_score}, "
            f"mandatory={rdp_full.mandatory_fields_present}",
        )

        # Verify revenue cross-verification happened
        rev_cvs = [cv for cv in rdp_full.cross_verifications if cv.field_name == "Revenue"]
        report(
            "Revenue cross-verified across 3 sources",
            len(rev_cvs) == 1 and len(rev_cvs[0].sources) == 3,
            f"Revenue CVs: {len(rev_cvs)}, sources: {len(rev_cvs[0].sources) if rev_cvs else 0}",
        )

    # ─── Summary ───
    print(f"\n{'='*60}")
    print(f"  T0.7 Consolidator Test Results: {passed}/{passed+failed} passed")
    print(f"{'='*60}")
    if failed > 0:
        print(f"\n  ⚠️  {failed} test(s) FAILED")
        sys.exit(1)
    else:
        print(f"\n  🎉 All tests passed!")


if __name__ == "__main__":
    asyncio.run(run_tests())
