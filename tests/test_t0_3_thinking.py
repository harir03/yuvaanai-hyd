"""
T0.3 — ThinkingEvent Bus Tests

Tests:
1. RedisPublisher initializes in memory mode (no Redis)
2. Publish stores events in event log
3. Subscribe + publish delivers events to subscriber
4. Unsubscribe stops delivery
5. ThinkingEventEmitter emits proper ThinkingEvent
6. Emitter shorthand methods work (read, found, flagged, etc.)
7. Event formatter returns correct icons and colors
8. Event log replay returns historical events
9. Multiple subscribers receive same event
10. Event count tracks correctly
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.thinking.redis_publisher import RedisPublisher, reset_publisher, get_publisher
from backend.thinking.event_emitter import ThinkingEventEmitter
from backend.thinking.event_formatter import (
    get_event_display,
    format_event_message,
    enrich_event_dict,
    format_source_citation,
)
from backend.models.schemas import EventType, ThinkingEvent

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


# ──────────────────────────────────────────────
# Test 1: RedisPublisher memory mode
# ──────────────────────────────────────────────
def test_publisher_memory_mode():
    reset_publisher()
    try:
        pub = RedisPublisher(redis_url=None)
        asyncio.run(pub.initialize())
        report("Publisher initializes in memory mode", not pub._use_redis)
    except Exception as e:
        report("Publisher initializes in memory mode", False, str(e))


# ──────────────────────────────────────────────
# Test 2: Publish stores in event log
# ──────────────────────────────────────────────
def test_publish_stores_events():
    reset_publisher()
    try:
        pub = RedisPublisher(redis_url=None)

        async def _run():
            await pub.initialize()
            await pub.publish("sess-001", {"event_type": "READ", "message": "Reading..."})
            await pub.publish("sess-001", {"event_type": "FOUND", "message": "Found data"})
            return pub.get_event_log("sess-001")

        log = asyncio.run(_run())
        ok = len(log) == 2 and log[0]["event_type"] == "READ" and log[1]["event_type"] == "FOUND"
        report("Publish stores events in log", ok, f"Got {len(log)} events")
    except Exception as e:
        report("Publish stores events in log", False, str(e))


# ──────────────────────────────────────────────
# Test 3: Subscribe receives events
# ──────────────────────────────────────────────
def test_subscribe_receives():
    reset_publisher()
    try:
        pub = RedisPublisher(redis_url=None)
        received = []

        async def callback(event):
            received.append(event)

        async def _run():
            await pub.initialize()
            await pub.subscribe("sess-002", callback)
            await pub.publish("sess-002", {"event_type": "FLAGGED", "message": "Flag!"})
            await pub.publish("sess-002", {"event_type": "CRITICAL", "message": "Alert!"})
            return received

        result = asyncio.run(_run())
        ok = len(result) == 2 and result[0]["event_type"] == "FLAGGED"
        report("Subscribe receives published events", ok, f"Got {len(result)} events")
    except Exception as e:
        report("Subscribe receives published events", False, str(e))


# ──────────────────────────────────────────────
# Test 4: Unsubscribe stops delivery
# ──────────────────────────────────────────────
def test_unsubscribe():
    reset_publisher()
    try:
        pub = RedisPublisher(redis_url=None)
        received = []

        async def callback(event):
            received.append(event)

        async def _run():
            await pub.initialize()
            await pub.subscribe("sess-003", callback)
            await pub.publish("sess-003", {"message": "first"})
            await pub.unsubscribe("sess-003", callback)
            await pub.publish("sess-003", {"message": "second"})
            return received

        result = asyncio.run(_run())
        ok = len(result) == 1 and result[0]["message"] == "first"
        report("Unsubscribe stops delivery", ok, f"Got {len(result)} events")
    except Exception as e:
        report("Unsubscribe stops delivery", False, str(e))


# ──────────────────────────────────────────────
# Test 5: ThinkingEventEmitter emits proper events
# ──────────────────────────────────────────────
def test_emitter_emit():
    reset_publisher()
    try:
        async def _run():
            pub = get_publisher()
            await pub.initialize()

            emitter = ThinkingEventEmitter("sess-emit-001", "Agent 0.5 — The Consolidator")
            event = await emitter.emit(
                EventType.FOUND,
                "Revenue FY2023: ₹142.3 crores",
                source_document="annual_report.pdf",
                source_page=42,
                confidence=0.95,
            )
            return event

        event = asyncio.run(_run())
        ok = (
            isinstance(event, ThinkingEvent)
            and event.session_id == "sess-emit-001"
            and event.agent == "Agent 0.5 — The Consolidator"
            and event.event_type == EventType.FOUND
            and "142.3" in event.message
            and event.source_document == "annual_report.pdf"
            and event.source_page == 42
            and event.confidence == 0.95
        )
        report("Emitter creates proper ThinkingEvent", ok)
    except Exception as e:
        report("Emitter creates proper ThinkingEvent", False, str(e))


# ──────────────────────────────────────────────
# Test 6: Emitter shorthand methods
# ──────────────────────────────────────────────
def test_emitter_shorthands():
    reset_publisher()
    try:
        async def _run():
            pub = get_publisher()
            await pub.initialize()

            emitter = ThinkingEventEmitter("sess-short-001", "Agent 2")
            e1 = await emitter.read("Reading bank statement...")
            e2 = await emitter.found("Found monthly inflow pattern")
            e3 = await emitter.flagged("EMI bounce detected")
            e4 = await emitter.critical("Wilful defaulter match!")
            e5 = await emitter.concluding("Risk assessment complete")
            return [e1, e2, e3, e4, e5], emitter.event_count

        events, count = asyncio.run(_run())
        type_map = {
            0: EventType.READ,
            1: EventType.FOUND,
            2: EventType.FLAGGED,
            3: EventType.CRITICAL,
            4: EventType.CONCLUDING,
        }
        ok = count == 5 and all(
            events[i].event_type == type_map[i] for i in range(5)
        )
        report("Emitter shorthands work (5 methods)", ok, f"count={count}")
    except Exception as e:
        report("Emitter shorthands work (5 methods)", False, str(e))


# ──────────────────────────────────────────────
# Test 7: Event formatter display properties
# ──────────────────────────────────────────────
def test_event_formatter():
    try:
        # Check display properties for each event type
        checks = [
            (EventType.ACCEPTED, "green", "✅"),
            (EventType.FLAGGED, "amber", "⚠️"),
            (EventType.CRITICAL, "red", "🚨"),
            (EventType.READ, "slate", "📄"),
            (EventType.CONNECTING, "purple", "🔗"),
            (EventType.CONCLUDING, "teal", "💡"),
        ]
        all_ok = True
        for etype, expected_color, expected_icon in checks:
            display = get_event_display(etype)
            if display["color"] != expected_color or display["icon"] != expected_icon:
                report(f"Formatter {etype.value}", False,
                       f"got color={display['color']}, icon={display['icon']}")
                all_ok = False

        # Check formatted message
        msg = format_event_message(EventType.ACCEPTED, "Revenue verified")
        ok_msg = msg == "✅ Revenue verified"

        # Check source citation
        cite = format_source_citation("annual_report.pdf", 42, "Revenue was ₹142cr")
        ok_cite = "annual_report.pdf" in cite and "p.42" in cite and "₹142cr" in cite

        if all_ok:
            report("Event formatter display properties", ok_msg and ok_cite)
        else:
            pass  # Individual failures already reported
    except Exception as e:
        report("Event formatter display properties", False, str(e))


# ──────────────────────────────────────────────
# Test 8: Event log replay
# ──────────────────────────────────────────────
def test_event_log_replay():
    reset_publisher()
    try:
        async def _run():
            pub = get_publisher()
            await pub.initialize()

            emitter = ThinkingEventEmitter("sess-replay-001", "Test Agent")
            await emitter.read("Step 1")
            await emitter.found("Step 2")
            await emitter.accepted("Step 3")

            log = emitter.get_event_log()
            return log

        log = asyncio.run(_run())
        ok = (
            len(log) == 3
            and log[0]["event_type"] == "READ"
            and log[1]["event_type"] == "FOUND"
            and log[2]["event_type"] == "ACCEPTED"
        )
        report("Event log replay", ok, f"Got {len(log)} events")
    except Exception as e:
        report("Event log replay", False, str(e))


# ──────────────────────────────────────────────
# Test 9: Multiple subscribers
# ──────────────────────────────────────────────
def test_multiple_subscribers():
    reset_publisher()
    try:
        pub = RedisPublisher(redis_url=None)
        received_a = []
        received_b = []

        async def cb_a(event):
            received_a.append(event)

        async def cb_b(event):
            received_b.append(event)

        async def _run():
            await pub.initialize()
            await pub.subscribe("sess-multi", cb_a)
            await pub.subscribe("sess-multi", cb_b)
            await pub.publish("sess-multi", {"message": "hello"})
            return received_a, received_b

        a, b = asyncio.run(_run())
        ok = len(a) == 1 and len(b) == 1 and a[0]["message"] == "hello"
        report("Multiple subscribers receive event", ok)
    except Exception as e:
        report("Multiple subscribers receive event", False, str(e))


# ──────────────────────────────────────────────
# Test 10: Enrich event dict adds display metadata
# ──────────────────────────────────────────────
def test_enrich_event():
    try:
        raw = {"event_type": "FLAGGED", "message": "Revenue mismatch"}
        enriched = enrich_event_dict(raw)
        ok = (
            "display" in enriched
            and enriched["display"]["color"] == "amber"
            and enriched["display"]["icon"] == "⚠️"
            and enriched["display"]["label"] == "Flagged"
            and enriched["message"] == "Revenue mismatch"  # original preserved
        )
        report("Enrich event dict adds display metadata", ok)
    except Exception as e:
        report("Enrich event dict adds display metadata", False, str(e))


# ──────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  T0.3 — ThinkingEvent Bus Tests")
    print("=" * 55 + "\n")

    test_publisher_memory_mode()
    test_publish_stores_events()
    test_subscribe_receives()
    test_unsubscribe()
    test_emitter_emit()
    test_emitter_shorthands()
    test_event_formatter()
    test_event_log_replay()
    test_multiple_subscribers()
    test_enrich_event()

    print(f"\n{'=' * 55}")
    print(f"  Results: {PASSED} passed, {FAILED} failed, {PASSED + FAILED} total")
    print(f"{'=' * 55}\n")

    sys.exit(0 if FAILED == 0 else 1)
