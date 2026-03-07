"""
T0.4 — PostgreSQL Schema + Client Tests (using SQLite in-memory)

Tests:
1. DatabaseClient initializes with SQLite fallback
2. All 8 tables are created
3. Save and retrieve assessment
4. Update assessment status
5. Save and retrieve score breakdown entries
6. Save and retrieve findings
7. Save and resolve ticket
8. Save and retrieve thinking events (batch)
9. Save rejection event
10. Save fraud investigation
11. Analytics aggregation
12. List assessments with filtering
"""

import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.storage.postgres_client import DatabaseClient, reset_db_client
from backend.storage.database_models import (
    Base, AssessmentDB, ScoreBreakdownDB, FindingDB, TicketDB,
    ThinkingEventDB, RejectionEventDB, FraudInvestigationDB,
)

PASSED = 0
FAILED = 0


def report(name: str, ok: bool, detail: str = ""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED += 1
        print(f"  FAIL  {name}  —  {detail}")


def make_session_id():
    return f"test-{uuid.uuid4().hex[:8]}"


# ──────────────────────────────────────────────
# Test 1: Initialize with SQLite
# ──────────────────────────────────────────────
def test_initialize():
    try:
        async def _run():
            db = DatabaseClient()  # No URL → in-memory SQLite
            await db.initialize()
            ok = db.is_initialized and db.backend == "sqlite"
            await db.close()
            return ok

        ok = asyncio.run(_run())
        report("Initialize with SQLite fallback", ok)
    except Exception as e:
        report("Initialize with SQLite fallback", False, str(e))


# ──────────────────────────────────────────────
# Test 2: All tables created
# ──────────────────────────────────────────────
def test_tables_created():
    try:
        async def _run():
            db = DatabaseClient()
            await db.initialize()

            from sqlalchemy import inspect as sa_inspect

            async with db._engine.connect() as conn:
                tables = await conn.run_sync(
                    lambda sync_conn: sa_inspect(sync_conn).get_table_names()
                )

            await db.close()
            return tables

        tables = asyncio.run(_run())
        expected = {
            "assessments", "score_breakdown", "findings_store", "tickets",
            "decision_outcomes", "thinking_events", "rejection_events",
            "fraud_investigations",
        }
        missing = expected - set(tables)
        report("All 8 tables created", len(missing) == 0, f"Missing: {missing}" if missing else "")
    except Exception as e:
        report("All 8 tables created", False, str(e))


# ──────────────────────────────────────────────
# Test 3: Save and retrieve assessment
# ──────────────────────────────────────────────
def test_save_get_assessment():
    try:
        sid = make_session_id()

        async def _run():
            db = DatabaseClient()
            await db.initialize()

            await db.save_assessment({
                "session_id": sid,
                "company_name": "XYZ Steel Pvt Ltd",
                "sector": "Steel Manufacturing",
                "loan_type": "Working Capital",
                "loan_amount": "₹50,00,00,000",
                "loan_amount_numeric": 50_00_00_000.0,
                "status": "processing",
            })

            result = await db.get_assessment(sid)
            await db.close()
            return result

        result = asyncio.run(_run())
        ok = (
            result is not None
            and result.session_id == sid
            and result.company_name == "XYZ Steel Pvt Ltd"
            and result.loan_amount_numeric == 50_00_00_000.0
            and result.status == "processing"
        )
        report("Save and retrieve assessment", ok)
    except Exception as e:
        report("Save and retrieve assessment", False, str(e))


# ──────────────────────────────────────────────
# Test 4: Update assessment status
# ──────────────────────────────────────────────
def test_update_status():
    try:
        sid = make_session_id()

        async def _run():
            db = DatabaseClient()
            await db.initialize()

            await db.save_assessment({
                "session_id": sid,
                "company_name": "Update Corp",
                "sector": "Tech",
                "loan_type": "Term Loan",
                "loan_amount": "₹10cr",
                "loan_amount_numeric": 10_00_00_000.0,
            })

            updated = await db.update_assessment_status(
                sid, "completed", score=677, score_band="GOOD", outcome="APPROVED"
            )

            result = await db.get_assessment(sid)
            await db.close()
            return updated, result

        updated, result = asyncio.run(_run())
        ok = (
            updated is True
            and result.status == "completed"
            and result.score == 677
            and result.score_band == "GOOD"
        )
        report("Update assessment status", ok)
    except Exception as e:
        report("Update assessment status", False, str(e))


# ──────────────────────────────────────────────
# Test 5: Score breakdown
# ──────────────────────────────────────────────
def test_score_breakdown():
    try:
        sid = make_session_id()

        async def _run():
            db = DatabaseClient()
            await db.initialize()

            await db.save_assessment({
                "session_id": sid, "company_name": "Score Corp",
                "sector": "Finance", "loan_type": "WC",
                "loan_amount": "₹5cr", "loan_amount_numeric": 5_00_00_000.0,
            })

            count = await db.save_score_entries(sid, [
                {
                    "module": "CAPACITY", "metric_name": "DSCR",
                    "metric_value": "1.38x", "score_impact": 35,
                    "reasoning": "Above benchmark of 1.25x",
                },
                {
                    "module": "CHARACTER", "metric_name": "Promoter Track Record",
                    "metric_value": "Clean", "score_impact": 20,
                    "reasoning": "No defaults in last 10 years",
                },
            ])

            entries = await db.get_score_breakdown(sid)
            await db.close()
            return count, entries

        count, entries = asyncio.run(_run())
        ok = count == 2 and len(entries) == 2
        report("Score breakdown save/retrieve", ok, f"saved={count}, retrieved={len(entries)}")
    except Exception as e:
        report("Score breakdown save/retrieve", False, str(e))


# ──────────────────────────────────────────────
# Test 6: Findings
# ──────────────────────────────────────────────
def test_findings():
    try:
        sid = make_session_id()

        async def _run():
            db = DatabaseClient()
            await db.initialize()

            await db.save_assessment({
                "session_id": sid, "company_name": "Finding Corp",
                "sector": "Mfg", "loan_type": "WC",
                "loan_amount": "₹3cr", "loan_amount_numeric": 3_00_00_000.0,
            })

            await db.save_finding({
                "session_id": sid, "finding_type": "research",
                "source": "tavily", "source_tier": 2,
                "title": "SEBI penalty", "content": "₹10L penalty for disclosure lapse",
                "category": "regulatory",
            })
            await db.save_finding({
                "session_id": sid, "finding_type": "compound",
                "title": "Circular trading", "content": "Detected 3-entity circular pattern",
                "category": "fraud", "severity": "HIGH",
            })

            all_f = await db.get_findings(sid)
            research_f = await db.get_findings(sid, finding_type="research")
            await db.close()
            return all_f, research_f

        all_f, research_f = asyncio.run(_run())
        ok = len(all_f) == 2 and len(research_f) == 1
        report("Findings save/retrieve", ok)
    except Exception as e:
        report("Findings save/retrieve", False, str(e))


# ──────────────────────────────────────────────
# Test 7: Ticket + resolve
# ──────────────────────────────────────────────
def test_tickets():
    try:
        sid = make_session_id()

        async def _run():
            db = DatabaseClient()
            await db.initialize()

            await db.save_assessment({
                "session_id": sid, "company_name": "Ticket Corp",
                "sector": "NBFC", "loan_type": "TL",
                "loan_amount": "₹20cr", "loan_amount_numeric": 20_00_00_000.0,
            })

            tid = str(uuid.uuid4())
            await db.save_ticket({
                "id": tid, "session_id": sid,
                "title": "Revenue mismatch",
                "description": "AR says ₹142cr, ITR says ₹130cr",
                "severity": "HIGH", "raised_by": "Agent 0.5",
            })

            # Retrieve open tickets
            open_tickets = await db.get_tickets(sid, status="OPEN")

            # Resolve
            resolved = await db.resolve_ticket(tid, "ITR figure accepted", "Credit Officer")

            # Retrieve resolved tickets
            all_tickets = await db.get_tickets(sid)
            await db.close()
            return open_tickets, resolved, all_tickets

        open_t, resolved, all_t = asyncio.run(_run())
        ok = (
            len(open_t) == 1
            and resolved is True
            and len(all_t) == 1
            and all_t[0].status == "RESOLVED"
            and all_t[0].resolution == "ITR figure accepted"
        )
        report("Ticket save/resolve", ok)
    except Exception as e:
        report("Ticket save/resolve", False, str(e))


# ──────────────────────────────────────────────
# Test 8: Thinking events batch
# ──────────────────────────────────────────────
def test_thinking_events():
    try:
        sid = make_session_id()

        async def _run():
            db = DatabaseClient()
            await db.initialize()

            await db.save_assessment({
                "session_id": sid, "company_name": "Think Corp",
                "sector": "IT", "loan_type": "WC",
                "loan_amount": "₹1cr", "loan_amount_numeric": 1_00_00_000.0,
            })

            count = await db.save_thinking_events_batch([
                {"session_id": sid, "agent": "Agent 0.5", "event_type": "READ", "message": "Reading AR"},
                {"session_id": sid, "agent": "Agent 0.5", "event_type": "FOUND", "message": "Revenue: ₹142cr"},
                {"session_id": sid, "agent": "Agent 2", "event_type": "FLAGGED", "message": "SEBI penalty found"},
            ])

            all_events = await db.get_thinking_events(sid)
            agent_events = await db.get_thinking_events(sid, agent="Agent 2")
            await db.close()
            return count, all_events, agent_events

        count, all_e, agent_e = asyncio.run(_run())
        ok = count == 3 and len(all_e) == 3 and len(agent_e) == 1
        report("Thinking events batch save/filter", ok)
    except Exception as e:
        report("Thinking events batch save/filter", False, str(e))


# ──────────────────────────────────────────────
# Test 9: Rejection event
# ──────────────────────────────────────────────
def test_rejection_event():
    try:
        sid = make_session_id()

        async def _run():
            db = DatabaseClient()
            await db.initialize()

            await db.save_assessment({
                "session_id": sid, "company_name": "Reject Corp",
                "sector": "Steel", "loan_type": "WC",
                "loan_amount": "₹5cr", "loan_amount_numeric": 5_00_00_000.0,
            })

            event = await db.save_rejection_event({
                "session_id": sid,
                "rejection_reason": "Wilful defaulter on RBI list",
                "rejection_stage": "RECOMMENDATION",
                "hard_block_trigger": "WILFUL_DEFAULTER",
                "score_at_rejection": 200,
                "evidence_snapshot_json": {"rbi_match": True},
            })
            await db.close()
            return event

        event = asyncio.run(_run())
        ok = (
            event is not None
            and event.hard_block_trigger == "WILFUL_DEFAULTER"
            and event.score_at_rejection == 200
        )
        report("Rejection event save", ok)
    except Exception as e:
        report("Rejection event save", False, str(e))


# ──────────────────────────────────────────────
# Test 10: Fraud investigation
# ──────────────────────────────────────────────
def test_fraud_investigation():
    try:
        sid = make_session_id()

        async def _run():
            db = DatabaseClient()
            await db.initialize()

            await db.save_assessment({
                "session_id": sid, "company_name": "Fraud Corp",
                "sector": "Trading", "loan_type": "WC",
                "loan_amount": "₹25cr", "loan_amount_numeric": 25_00_00_000.0,
            })

            inv = await db.save_fraud_investigation({
                "session_id": sid,
                "fraud_type": "circular_trading",
                "detection_method": "GNN",
                "confidence": 0.87,
                "severity": "HIGH",
                "description": "Detected 3-entity circular trading ring",
                "score_impact": -75,
            })

            results = await db.get_fraud_investigations(sid)
            await db.close()
            return inv, results

        inv, results = asyncio.run(_run())
        ok = inv is not None and len(results) == 1 and results[0].fraud_type == "circular_trading"
        report("Fraud investigation save/retrieve", ok)
    except Exception as e:
        report("Fraud investigation save/retrieve", False, str(e))


# ──────────────────────────────────────────────
# Test 11: Analytics
# ──────────────────────────────────────────────
def test_analytics():
    try:
        async def _run():
            db = DatabaseClient()
            await db.initialize()

            # Create 3 assessments
            for i in range(3):
                sid = make_session_id()
                status = "completed" if i < 2 else "processing"
                score = 600 + (i * 50) if i < 2 else None
                await db.save_assessment({
                    "session_id": sid, "company_name": f"Analytics Corp {i}",
                    "sector": "IT", "loan_type": "WC",
                    "loan_amount": "₹1cr", "loan_amount_numeric": 1_00_00_000.0,
                    "status": status, "score": score,
                })

            analytics = await db.get_analytics()
            await db.close()
            return analytics

        analytics = asyncio.run(_run())
        ok = (
            analytics["total_assessments"] == 3
            and analytics["completed_assessments"] == 2
            and analytics["average_score"] is not None
            and analytics["processing"] == 1
        )
        report("Analytics aggregation", ok, str(analytics))
    except Exception as e:
        report("Analytics aggregation", False, str(e))


# ──────────────────────────────────────────────
# Test 12: List with filter
# ──────────────────────────────────────────────
def test_list_filter():
    try:
        async def _run():
            db = DatabaseClient()
            await db.initialize()

            for i in range(4):
                sid = make_session_id()
                status = "completed" if i % 2 == 0 else "processing"
                await db.save_assessment({
                    "session_id": sid, "company_name": f"List Corp {i}",
                    "sector": "Finance", "loan_type": "TL",
                    "loan_amount": "₹2cr", "loan_amount_numeric": 2_00_00_000.0,
                    "status": status,
                })

            all_a = await db.list_assessments()
            completed_a = await db.list_assessments(status="completed")
            count = await db.get_assessment_count()
            await db.close()
            return all_a, completed_a, count

        all_a, completed_a, count = asyncio.run(_run())
        ok = len(all_a) == 4 and len(completed_a) == 2 and count == 4
        report("List assessments with filter", ok,
               f"all={len(all_a)}, completed={len(completed_a)}, count={count}")
    except Exception as e:
        report("List assessments with filter", False, str(e))


# ──────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  T0.4 — PostgreSQL Schema + Client Tests")
    print("=" * 55 + "\n")

    test_initialize()
    test_tables_created()
    test_save_get_assessment()
    test_update_status()
    test_score_breakdown()
    test_findings()
    test_tickets()
    test_thinking_events()
    test_rejection_event()
    test_fraud_investigation()
    test_analytics()
    test_list_filter()

    print(f"\n{'=' * 55}")
    print(f"  Results: {PASSED} passed, {FAILED} failed, {PASSED + FAILED} total")
    print(f"{'=' * 55}\n")

    sys.exit(0 if FAILED == 0 else 1)
