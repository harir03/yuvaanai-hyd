"""
Intelli-Credit — T0.6 Tests: Celery Workers

Tests:
1. Worker registry: all 3 workers registered
2. Worker class lookup by DocumentType
3. W1 Annual Report: processes mock file, extracts data
4. W2 Bank Statement: processes mock file, extracts data
5. W3 GST Returns: processes mock file, extracts data
6. Workers emit ThinkingEvents during processing
7. Worker output staged in Redis
8. Worker handles missing file gracefully
9. Task registry dispatches correct workers
10. Workers_node integration: full dispatch cycle
"""

import asyncio
import os
import sys
import tempfile
import json

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.schemas import DocumentType, WorkerStatusEnum
from backend.graph.state import WorkerOutput
from backend.workers.base_worker import BaseDocumentWorker
from backend.workers.w1_annual_report import AnnualReportWorker
from backend.workers.w2_bank_statement import BankStatementWorker
from backend.workers.w3_gst_returns import GSTReturnsWorker
from backend.workers.task_registry import (
    WORKER_REGISTRY,
    get_worker_class,
    get_worker_id,
    list_registered_workers,
    dispatch_workers,
)
from backend.workers.celery_app import is_celery_available
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


async def run_tests():
    global passed, failed

    # Reset singletons for clean state
    reset_publisher()
    reset_redis_client()
    redis = get_redis_client()
    await redis.initialize()

    # Create a temp directory with mock files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock document files
        ar_path = os.path.join(tmpdir, "annual_report.pdf")
        bs_path = os.path.join(tmpdir, "bank_statement.pdf")
        gst_path = os.path.join(tmpdir, "gst_returns.pdf")

        for p in [ar_path, bs_path, gst_path]:
            with open(p, "w") as f:
                f.write("Mock document content for testing")

        session_id = "test-t06-session"

        # ─── Test 1: Worker registry has 3 workers ───
        print("\n🔧 Test 1: Worker registry has 3 workers")
        registered = list_registered_workers()
        report(
            "3 workers registered",
            len(registered) == 3 and "W1" in registered and "W2" in registered and "W3" in registered,
            f"Got: {registered}",
        )

        # ─── Test 2: Worker class lookup ───
        print("\n🔧 Test 2: Worker class lookup by DocumentType")
        w1_cls = get_worker_class(DocumentType.ANNUAL_REPORT)
        w2_cls = get_worker_class(DocumentType.BANK_STATEMENT)
        w3_cls = get_worker_class(DocumentType.GST_RETURNS)
        w_none = get_worker_class(DocumentType.ITR)  # Not implemented yet
        report(
            "Correct worker classes returned",
            w1_cls is AnnualReportWorker
            and w2_cls is BankStatementWorker
            and w3_cls is GSTReturnsWorker
            and w_none is None,
            f"W1={w1_cls}, W2={w2_cls}, W3={w3_cls}, ITR={w_none}",
        )

        # ─── Test 3: W1 Annual Report processing ───
        print("\n🔧 Test 3: W1 Annual Report extraction")
        w1 = AnnualReportWorker(session_id, ar_path)
        output1 = await w1.process()
        report(
            "W1 completed successfully",
            output1.status == "completed"
            and output1.worker_id == "W1"
            and output1.document_type == DocumentType.ANNUAL_REPORT.value
            and output1.confidence > 0.5
            and output1.pages_processed > 0,
            f"status={output1.status}, confidence={output1.confidence}, pages={output1.pages_processed}",
        )

        # Verify extracted data structure
        data1 = output1.extracted_data
        report(
            "W1 extracted revenue data",
            "revenue" in data1
            and data1["revenue"].get("fy2023") is not None
            and "rpts" in data1
            and "directors" in data1,
            f"Keys: {list(data1.keys())}",
        )

        # ─── Test 4: W2 Bank Statement processing ───
        print("\n🔧 Test 4: W2 Bank Statement extraction")
        w2 = BankStatementWorker(session_id, bs_path)
        output2 = await w2.process()
        report(
            "W2 completed successfully",
            output2.status == "completed"
            and output2.worker_id == "W2"
            and output2.confidence > 0.5,
            f"status={output2.status}, confidence={output2.confidence}",
        )

        data2 = output2.extracted_data
        report(
            "W2 extracted bank data",
            "monthly_summary" in data2
            and "bounces" in data2
            and "emi_regularity" in data2
            and "revenue_from_bank" in data2,
            f"Keys: {list(data2.keys())}",
        )

        # ─── Test 5: W3 GST Returns processing ───
        print("\n🔧 Test 5: W3 GST Returns extraction")
        w3 = GSTReturnsWorker(session_id, gst_path)
        output3 = await w3.process()
        report(
            "W3 completed successfully",
            output3.status == "completed"
            and output3.worker_id == "W3"
            and output3.confidence > 0.5,
            f"status={output3.status}, confidence={output3.confidence}",
        )

        data3 = output3.extracted_data
        report(
            "W3 extracted GST data with 2A/3B reconciliation",
            "gstr3b_monthly" in data3
            and "gstr2a_reconciliation" in data3
            and data3["gstr2a_reconciliation"].get("mismatch_pct") is not None
            and "revenue_from_gst" in data3,
            f"Keys: {list(data3.keys())}",
        )

        # ─── Test 6: ThinkingEvents emitted during processing ───
        print("\n🔧 Test 6: ThinkingEvents emitted during processing")
        publisher = get_publisher()
        event_log = publisher.get_event_log(session_id)
        # Each worker emits multiple events (READ, FOUND, FLAGGED, ACCEPTED)
        report(
            "ThinkingEvents emitted by workers",
            len(event_log) >= 15,  # At least 5 per worker × 3 workers
            f"Total events: {len(event_log)}",
        )

        # ─── Test 7: Worker outputs staged in Redis ───
        print("\n🔧 Test 7: Worker outputs staged in Redis")
        staged = await redis.get_all_staged_outputs(session_id)
        report(
            "All 3 worker outputs staged",
            len(staged) == 3
            and "W1" in staged
            and "W2" in staged
            and "W3" in staged,
            f"Staged worker IDs: {list(staged.keys())}",
        )

        # Verify staged data is deserializable
        staged_w1 = staged.get("W1", {})
        report(
            "Staged data is valid JSON with expected fields",
            staged_w1.get("worker_id") == "W1"
            and staged_w1.get("status") == "completed"
            and "extracted_data" in staged_w1,
            f"Staged W1 keys: {list(staged_w1.keys())}",
        )

        # ─── Test 8: Worker handles missing file ───
        print("\n🔧 Test 8: Worker handles missing file gracefully")
        w_missing = AnnualReportWorker("test-missing", "/nonexistent/file.pdf")
        output_missing = await w_missing.process()
        report(
            "Missing file returns failed status",
            output_missing.status == "failed"
            and len(output_missing.errors) > 0,
            f"status={output_missing.status}, errors={output_missing.errors}",
        )

        # ─── Test 9: Dispatch workers via task registry ───
        print("\n🔧 Test 9: Task registry dispatch")
        dispatch_session = "test-dispatch"
        documents = [
            {"document_type": DocumentType.ANNUAL_REPORT, "file_path": ar_path},
            {"document_type": DocumentType.BANK_STATEMENT, "file_path": bs_path},
            {"document_type": DocumentType.GST_RETURNS, "file_path": gst_path},
            {"document_type": DocumentType.ITR, "file_path": "/fake/itr.pdf"},  # Not implemented
        ]
        results = await dispatch_workers(dispatch_session, documents)
        report(
            "Dispatch returns results for all documents",
            len(results) >= 3
            and results.get("W1") is not None
            and results["W1"].status == "completed"
            and results.get("W2") is not None
            and results["W2"].status == "completed"
            and results.get("W3") is not None
            and results["W3"].status == "completed",
            f"Results: { {k: v.status for k, v in results.items()} }",
        )

        # Check ITR was skipped
        itr_key = "W?-ITR"
        report(
            "Unimplemented worker returns skipped status",
            itr_key in results and results[itr_key].status == "skipped",
            f"ITR result: {results.get(itr_key)}",
        )

        # ─── Test 10: workers_node integration ───
        print("\n🔧 Test 10: workers_node integration")
        from backend.graph.state import CreditAppraisalState
        from backend.models.schemas import (
            CompanyInfo,
            DocumentMeta,
            PipelineStage,
            PipelineStageEnum,
        )
        from backend.graph.nodes.workers_node import workers_node

        state = CreditAppraisalState(
            session_id="test-node-integration",
            company=CompanyInfo(
                name="XYZ Steel",
                sector="Manufacturing",
                loan_type="Working Capital",
                loan_amount="₹50,00,00,000",
                loan_amount_numeric=5000.0,
            ),
            documents=[
                DocumentMeta(
                    filename="annual_report.pdf",
                    document_type=DocumentType.ANNUAL_REPORT,
                    file_size=1024,
                    file_path=ar_path,
                ),
                DocumentMeta(
                    filename="bank_statement.pdf",
                    document_type=DocumentType.BANK_STATEMENT,
                    file_size=512,
                    file_path=bs_path,
                ),
            ],
            pipeline_stages=[
                PipelineStage(stage=PipelineStageEnum.WORKERS),
            ],
        )

        result = await workers_node(state)
        report(
            "workers_node returns correct structure",
            result.get("workers_completed") == 2
            and result.get("workers_total") == 2
            and len(result.get("worker_outputs", {})) == 2
            and len(result.get("workers", [])) == 2,
            f"completed={result.get('workers_completed')}, total={result.get('workers_total')}, "
            f"outputs={len(result.get('worker_outputs', {}))}, statuses={len(result.get('workers', []))}",
        )

        # Verify worker statuses
        worker_statuses = result.get("workers", [])
        all_completed = all(ws.status == WorkerStatusEnum.COMPLETED for ws in worker_statuses)
        report(
            "All worker statuses are COMPLETED",
            all_completed,
            f"Statuses: {[ws.status.value for ws in worker_statuses]}",
        )

    # ─── Summary ───
    print(f"\n{'='*60}")
    print(f"  T0.6 Workers Test Results: {passed}/{passed+failed} passed")
    print(f"{'='*60}")
    if failed > 0:
        print(f"\n  ⚠️  {failed} test(s) FAILED")
        sys.exit(1)
    else:
        print(f"\n  🎉 All tests passed!")


if __name__ == "__main__":
    asyncio.run(run_tests())
